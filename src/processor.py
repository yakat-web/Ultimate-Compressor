"""
Image processing engine for the Ultimate Image Compressor.

Handles compression, normalization, format conversion, and resizing.
Has **zero** GUI dependencies — all UI feedback goes through callbacks.
"""

import io
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from typing import Callable, Optional

from PIL import Image

try:
    from PIL import ImageCms
except ImportError:
    ImageCms = None  # type: ignore[assignment, misc]

try:
    from .constants import ICO_SIZES, STRINGS
    from .utils import (
        format_file_size,
        get_tool_path,
        log_error,
        log_info,
        verify_tool_integrity,
    )
except ImportError:
    from constants import ICO_SIZES, STRINGS
    from utils import (
        format_file_size,
        get_tool_path,
        log_error,
        log_info,
        verify_tool_integrity,
    )


class ImageProcessor:
    """Compression engine that delegates to external CLI tools.

    Parameters
    ----------
    status_callback : callable, optional
        ``status_callback(message: str)`` is called to report progress.
    cancel_event : threading.Event, optional
        If set, long-running operations abort early.
    """

    def __init__(
        self,
        status_callback: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        self.status_callback = status_callback
        self.cancel_event = cancel_event or threading.Event()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)

    def _is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def _run_tool(self, command: list[str]) -> tuple[bool, str]:
        """Run an external CLI tool and return ``(success, message)``."""
        tool_name = os.path.basename(command[0])
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=60,
            )
            # pngquant returns 98/99 when the image is already optimized
            if tool_name == "pngquant.exe" and result.returncode in (98, 99):
                return True, "Already Optimized"
            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, command,
                    output=result.stdout, stderr=result.stderr,
                )
            return True, "Success"
        except subprocess.TimeoutExpired:
            log_error(f"Timeout: {tool_name} took longer than 60 seconds")
            return False, f"Timeout: Process took longer than 60 seconds"
        except subprocess.CalledProcessError as e:
            stderr_msg = (
                e.stderr.decode(encoding="utf-8", errors="replace").strip()
                if e.stderr else ""
            )
            stdout_msg = (
                e.stdout.decode(encoding="utf-8", errors="replace").strip()
                if e.stdout else ""
            )
            error_output = stderr_msg or stdout_msg or "No output from tool."
            full_error_msg = (
                f"Error from {tool_name} (code {e.returncode}):\n{error_output}"
            )
            log_error(full_error_msg)
            return False, full_error_msg
        except FileNotFoundError:
            log_error(f"Tool not found: {tool_name}")
            return False, f"Tool not found: {tool_name}"
        except PermissionError as e:
            log_error(f"Permission denied running {tool_name}: {e}")
            return False, f"Permission denied: {e}"
        except OSError as e:
            log_error(
                f"OS error while running {tool_name}: {e}", exc_info=True
            )
            return False, str(e)

    # ------------------------------------------------------------------
    # Image normalization (fixes Issue #15)
    # ------------------------------------------------------------------
    def _normalize_image(
        self, file_path: str, target_format: str,
    ) -> tuple[str, Optional[str]]:
        """Normalize an image so external tools can process it.

        Handles CMYK→RGB, 16-bit→8-bit, corrupt ICC profiles,
        and Palette mode conversions. Returns ``(path, temp_path)``
        where *temp_path* is ``None`` if no normalization was needed.
        """
        needs_normalization = False

        with Image.open(file_path) as img:
            # Detect conditions that require normalization
            if img.mode == "CMYK":
                needs_normalization = True
            if img.mode in ("I;16", "I"):
                needs_normalization = True
            if img.mode == "P" and target_format in ("jpeg", "jpg"):
                needs_normalization = True
            if img.mode == "RGBA" and target_format in ("jpeg", "jpg"):
                needs_normalization = True

            # Check for corrupt ICC profile
            has_corrupt_icc = False
            if "icc_profile" in img.info and ImageCms is not None:
                try:
                    ImageCms.getOpenProfile(
                        io.BytesIO(img.info["icc_profile"])
                    )
                except Exception:
                    has_corrupt_icc = True
                    needs_normalization = True

            if not needs_normalization:
                return file_path, None

            self._update_status(STRINGS["status_normalizing"])

            # --- Perform normalization ---
            if img.mode == "CMYK":
                img = img.convert("RGB")
            elif img.mode in ("I;16", "I"):
                img = img.point(lambda i: i * (1 / 256)).convert("L")
            elif img.mode == "P" and target_format in ("jpeg", "jpg"):
                img = img.convert("RGB")

            if img.mode == "RGBA" and target_format in ("jpeg", "jpg"):
                img = img.convert("RGB")

            # Build save kwargs — keep valid ICC, strip corrupt ones
            save_kwargs: dict = {}
            if "icc_profile" in img.info and not has_corrupt_icc:
                save_kwargs["icc_profile"] = img.info["icc_profile"]

            save_format = target_format.upper()
            if save_format == "JPG":
                save_format = "JPEG"

            normalized_path = os.path.join(
                tempfile.gettempdir(),
                f"norm_{uuid.uuid4().hex}.{target_format}",
            )
            img.save(normalized_path, format=save_format, **save_kwargs)

        log_info(f"Normalized image saved to {normalized_path}")
        return normalized_path, normalized_path

    # ------------------------------------------------------------------
    # Transparency check
    # ------------------------------------------------------------------
    def is_png_fully_opaque(self, file_path: str) -> bool:
        """Return True if the PNG has no transparency."""
        try:
            with Image.open(file_path) as img:
                if img.mode == "P":
                    if "transparency" in img.info:
                        return False
                if "A" in img.getbands():
                    return not any(
                        pixel < 255
                        for pixel in img.getchannel("A").getdata()
                    )
                return True
        except (OSError, ValueError) as e:
            log_error(
                f"Could not check transparency for "
                f"{os.path.basename(file_path)}: {e}"
            )
            return False

    # ------------------------------------------------------------------
    # Compression methods
    # ------------------------------------------------------------------
    def compress_jpeg(
        self, in_path: str, out_path: str, quality: int,
    ) -> tuple[bool, str]:
        """Compress an image to JPEG using MozJPEG."""
        cjpeg_path = get_tool_path("cjpeg.exe")
        if not cjpeg_path:
            return False, "cjpeg.exe not found."
        if not verify_tool_integrity(cjpeg_path):
            return False, "cjpeg.exe integrity check failed — aborting."
        return self._run_tool([
            cjpeg_path, "-quality", str(quality),
            "-progressive", "-outfile", out_path, in_path,
        ])

    def compress_webp(
        self, in_path: str, out_path: str, quality: int,
    ) -> tuple[bool, str]:
        """Compress an image to WebP using cwebp."""
        cwebp_path = get_tool_path("cwebp.exe")
        if not cwebp_path:
            return False, "cwebp.exe not found."
        if not verify_tool_integrity(cwebp_path):
            return False, "cwebp.exe integrity check failed — aborting."
        return self._run_tool([
            cwebp_path, "-q", str(quality), in_path, "-o", out_path,
        ])

    def compress_png(
        self,
        in_path: str,
        out_path: str,
        quality_range: str = "60-80",
        use_zopfli: bool = True,
    ) -> tuple[bool, str]:
        """Compress a PNG using pngquant (and optionally zopflipng)."""
        pngquant_path = get_tool_path("pngquant.exe")
        zopflipng_path = get_tool_path("zopflipng.exe")
        if not pngquant_path or not zopflipng_path:
            return False, "PNG tools (pngquant/zopflipng) not found."
        if not verify_tool_integrity(pngquant_path):
            return False, "pngquant.exe integrity check failed — aborting."
        if not verify_tool_integrity(zopflipng_path):
            return False, "zopflipng.exe integrity check failed — aborting."

        temp_path = (
            out_path
            if not use_zopfli
            else os.path.join(
                tempfile.gettempdir(),
                f"quant_{os.path.basename(out_path)}",
            )
        )
        try:
            p_command = [
                pngquant_path, "--force", "--strip",
                "--quality", quality_range, "--speed=1",
                "--output", temp_path, in_path,
            ]
            quant_success, quant_msg = self._run_tool(p_command)
            if not quant_success:
                return False, quant_msg

            if quant_msg == "Already Optimized":
                if not use_zopfli:
                    # Fix Issue #4: copy original to output when already optimized
                    shutil.copy2(in_path, out_path)
                else:
                    z_command = [
                        zopflipng_path, "-y", "--iterations=15",
                        in_path, out_path,
                    ]
                    return self._run_tool(z_command)
                return True, quant_msg

            if use_zopfli:
                z_command = [
                    zopflipng_path, "-y", "--iterations=15",
                    temp_path, out_path,
                ]
                return self._run_tool(z_command)
            else:
                return True, "Success"
        finally:
            if use_zopfli and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Binary search for target file size
    # ------------------------------------------------------------------
    def find_best_quality(
        self,
        in_path: str,
        target_kb: int,
        compress_func: Callable[..., tuple[bool, str]],
    ) -> int:
        """Binary-search for the highest quality that fits *target_kb*."""
        self._update_status(
            STRINGS["status_finding_quality"].format(size=target_kb)
        )
        target_bytes = target_kb * 1024
        low, high, best_quality = 1, 100, -1

        for _ in range(8):
            if self._is_cancelled() or low > high:
                break
            q = (low + high) // 2
            with tempfile.NamedTemporaryFile(
                suffix=".tmp", delete=False,
            ) as temp_out:
                temp_out_name = temp_out.name
            try:
                is_success, _ = compress_func(in_path, temp_out_name, q)
                if is_success and os.path.exists(temp_out_name):
                    if os.path.getsize(temp_out_name) <= target_bytes:
                        best_quality, low = q, q + 1
                    else:
                        high = q - 1
                else:
                    high = q - 1
            finally:
                if os.path.exists(temp_out_name):
                    try:
                        os.remove(temp_out_name)
                    except OSError:
                        pass

        return best_quality if best_quality != -1 else 1

    # ------------------------------------------------------------------
    # Safe filename handling for non-ASCII paths
    # ------------------------------------------------------------------
    def _safe_copy_for_processing(
        self, file_path: str,
    ) -> tuple[str, Optional[str]]:
        """Copy a file to a temp path if the filename contains non-ASCII."""
        try:
            file_path.encode("ascii")
            return file_path, None
        except UnicodeEncodeError:
            _, ext = os.path.splitext(file_path)
            safe_name = f"temp_{uuid.uuid4().hex}{ext}"
            safe_path = os.path.join(tempfile.gettempdir(), safe_name)
            shutil.copy2(file_path, safe_path)
            log_info(f"Copied non-ASCII filename to safe temp path '{safe_path}'")
            return safe_path, safe_path

    # ------------------------------------------------------------------
    # Format conversion helper
    # ------------------------------------------------------------------
    def _convert_image(
        self, source_path: str, target_format: str,
    ) -> str:
        """Convert an image to *target_format* via Pillow."""
        temp_converted_path = os.path.join(
            tempfile.gettempdir(),
            f"converted_{uuid.uuid4().hex}.{target_format}",
        )
        with Image.open(source_path) as img:
            save_options: dict = {}
            if target_format in ("jpeg", "jpg"):
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                if img.mode == "CMYK":
                    img = img.convert("RGB")
                save_options["quality"] = 98
            elif target_format == "png":
                if img.mode not in ("RGBA", "RGB", "L", "P"):
                    img = img.convert("RGBA")
            img.save(temp_converted_path, **save_options)
        return temp_converted_path

    # ------------------------------------------------------------------
    # Main processing pipeline
    # ------------------------------------------------------------------
    def process_file(
        self, file_path: str, options: dict,
    ) -> tuple[bool, str]:
        """Process a single image file according to *options*.

        Returns ``(success: bool, message: str)``.
        """
        if self._is_cancelled():
            return False, STRINGS["status_cancelled"]

        original_basename = os.path.basename(file_path)
        file_name, file_ext_orig = os.path.splitext(original_basename)
        should_overwrite: bool = options.get("overwrite", False)
        target_format_str: str = options.get(
            "format", STRINGS["keep_original_format"]
        )
        is_converting_format: bool = (
            target_format_str != STRINGS["keep_original_format"]
        )
        target_format = (
            target_format_str.lower()
            if is_converting_format
            else file_ext_orig.lower().replace(".", "")
        )

        # Auto-convert opaque PNG → JPEG
        if (
            options.get("auto_convert_png")
            and file_ext_orig.lower() == ".png"
            and not is_converting_format
        ):
            if self.is_png_fully_opaque(file_path):
                target_format = "jpeg"
                is_converting_format = True

        if should_overwrite and is_converting_format:
            msg = STRINGS["overwrite_format_error"]
            log_error(msg)
            return False, msg

        # Determine output path
        if should_overwrite:
            final_output_path = file_path
        else:
            output_dir = options.get("output_dir", os.path.dirname(file_path))
            if output_dir == STRINGS["original_folder"]:
                output_dir = os.path.dirname(file_path)
            suffix = options.get("suffix", "-tiny")
            final_output_path = os.path.join(
                output_dir, f"{file_name}{suffix}.{target_format}"
            )

        # Create a temp file for the output
        with tempfile.NamedTemporaryFile(
            suffix=f".{target_format}", delete=False,
        ) as temp_out:
            temp_output_path = temp_out.name

        current_path = file_path
        temp_files: list[str] = [temp_output_path]

        try:
            # Step 1: Safe copy for non-ASCII filenames
            current_path, safe_copy = self._safe_copy_for_processing(
                current_path
            )
            if safe_copy:
                temp_files.append(safe_copy)

            if self._is_cancelled():
                return False, STRINGS["status_cancelled"]

            # Step 2: Resize if requested
            if options.get("resize_enabled"):
                w = options.get("width", 0)
                h = options.get("height", 0)
                
                with Image.open(current_path) as img:
                    orig_w, orig_h = img.size
                    
                    if w == 0 and h == 0:
                        target_w, target_h = orig_w, orig_h
                    else:
                        target_w, target_h = orig_w, orig_h
                        if options.get("fit_to_box") and w > 0 and h > 0:
                            ratio = min(w / orig_w, h / orig_h)
                            target_w = int(orig_w * ratio)
                            target_h = int(orig_h * ratio)
                        else:
                            if w > 0 and h > 0:
                                if options.get("keep_aspect_ratio"):
                                    ratio = min(w / orig_w, h / orig_h)
                                    target_w = int(orig_w * ratio)
                                    target_h = int(orig_h * ratio)
                                else:
                                    target_w, target_h = w, h
                            elif w > 0:
                                target_w = w
                                target_h = int(orig_h * (w / orig_w))
                            elif h > 0:
                                target_h = h
                                target_w = int(orig_w * (h / orig_h))
                                
                        if options.get("do_not_enlarge"):
                            if target_w > orig_w or target_h > orig_h:
                                target_w = orig_w
                                target_h = orig_h
                                
                    target_w, target_h = max(1, target_w), max(1, target_h)
                    
                    if target_w != orig_w or target_h != orig_h:
                        _, file_ext = os.path.splitext(current_path)
                        temp_resized = os.path.join(
                            tempfile.gettempdir(),
                            f"resized_{uuid.uuid4().hex}{file_ext}",
                        )
                        img.resize((target_w, target_h), Image.Resampling.LANCZOS).save(temp_resized)
                        current_path = temp_resized
                        temp_files.append(temp_resized)
                        self._update_status(STRINGS["status_resized"].format(w=target_w, h=target_h))

            if self._is_cancelled():
                return False, STRINGS["status_cancelled"]

            # Step 3: Format conversion if needed
            current_ext_no_dot = (
                os.path.splitext(current_path)[1].lower().strip(".")
            )
            if current_ext_no_dot != target_format:
                temp_converted = self._convert_image(
                    current_path, target_format
                )
                current_path = temp_converted
                temp_files.append(temp_converted)

            # Step 4: Normalize image for external tool compatibility (#15)
            normalized_path, norm_temp = self._normalize_image(
                current_path, target_format
            )
            if norm_temp:
                current_path = normalized_path
                temp_files.append(norm_temp)

            if self._is_cancelled():
                return False, STRINGS["status_cancelled"]

            # Step 5: Compress
            quality: int = options.get("quality", 75)
            is_success = False
            message = "An unknown compression error occurred."

            if target_format in ("jpeg", "jpg"):
                if options.get("mode") == "size":
                    quality = self.find_best_quality(
                        current_path, options["target_size"],
                        self.compress_jpeg,
                    )
                is_success, message = self.compress_jpeg(
                    current_path, temp_output_path, quality
                )
                if is_success:
                    message = (
                        f"'{original_basename}' -> JPEG, quality {quality}."
                    )

            elif target_format == "png":
                quality_range = (
                    f"{quality - 10}-{quality}"
                    if quality > 10
                    else f"0-{quality}"
                )
                use_zopfli: bool = options.get("max_png", False)
                is_success, message = self.compress_png(
                    current_path, temp_output_path,
                    quality_range, use_zopfli=use_zopfli,
                )
                if is_success and message == "Already Optimized":
                    message = f"'{original_basename}' is already optimized."
                elif is_success:
                    message = f"'{original_basename}' compressed to PNG."

            elif target_format == "webp":
                if options.get("mode") == "size":
                    quality = self.find_best_quality(
                        current_path, options["target_size"],
                        self.compress_webp,
                    )
                is_success, message = self.compress_webp(
                    current_path, temp_output_path, quality
                )
                if is_success:
                    message = (
                        f"'{original_basename}' -> WEBP, quality {quality}."
                    )

            elif target_format == "ico":
                with Image.open(current_path) as img:
                    img.save(
                        temp_output_path, format="ICO", sizes=ICO_SIZES,
                    )
                is_success = True
                message = f"'{original_basename}' -> ICO."

            else:
                return False, STRINGS["unsupported_type"]

            # Step 6: Move result to final destination
            if is_success:
                already_optimized_msg = (
                    f"'{original_basename}' is already optimized."
                )
                if message != already_optimized_msg:
                    os.makedirs(
                        os.path.dirname(final_output_path), exist_ok=True,
                    )
                    shutil.move(temp_output_path, final_output_path)
                if temp_output_path in temp_files:
                    temp_files.remove(temp_output_path)
                return True, message
            else:
                return False, message

        except PermissionError as e:
            log_error(f"Permission denied: {e}", exc_info=True)
            return False, f"Permission denied: {e}"
        except OSError as e:
            log_error(f"I/O error during processing: {e}", exc_info=True)
            return False, f"I/O error: {e}"
        except Exception as e:
            log_error(
                f"A fatal error occurred during processing: {e}",
                exc_info=True,
            )
            return False, f"An unexpected error occurred: {e}"
        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except OSError:
                    pass
