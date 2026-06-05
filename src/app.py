"""
Core application logic for the Ultimate Image Compressor.

Contains the main() entry point and High-DPI setup.
Both ``python -m src`` and the PyInstaller entry point call this.
"""

import ctypes
import os
import sys
from tkinter import messagebox

try:
    from .constants import STRINGS
    from .gui import UltimateCompressorGUI
    from .processor import ImageProcessor
    from .utils import log_error
except ImportError:
    from constants import STRINGS
    from gui import UltimateCompressorGUI
    from processor import ImageProcessor
    from utils import log_error


def _enable_high_dpi() -> None:
    """Enable High-DPI awareness on Windows (fixes Issue #28)."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


def main() -> None:
    _enable_high_dpi()

    # --- Parse arguments ---
    is_shift_requested = "--shift" in sys.argv
    argv_files = [
        arg for arg in sys.argv[1:]
        if arg != "--shift" and os.path.isfile(arg)
    ]

    is_shift_pressed = False
    try:
        is_shift_pressed = (
            ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000 != 0
        )
    except (AttributeError, OSError):
        pass

    open_gui = is_shift_pressed or is_shift_requested or not argv_files

    if open_gui:
        # Always open GUI directly — files can be added later via menu
        app = UltimateCompressorGUI(argv_files)
        app.mainloop()
    else:
        # Headless / quick mode — compress with defaults
        processor = ImageProcessor()
        options = {
            "mode": "quality",
            "quality": 75,
            "resize_enabled": False,
            "output_dir": STRINGS["original_folder"],
            "suffix": "-tiny",
            "format": STRINGS["keep_original_format"],
            "overwrite": False,
            "max_png": False,
            "auto_convert_png": True,
        }
        success_count = 0
        error_msgs: list[str] = []
        for file_path in argv_files:
            is_success, msg = processor.process_file(file_path, options)
            if is_success:
                success_count += 1
            else:
                error_msgs.append(
                    f"- {os.path.basename(file_path)}:\n  {msg}"
                )

        if not error_msgs and success_count > 0:
            messagebox.showinfo(
                STRINGS["success_title"],
                STRINGS["headless_success"].format(count=success_count),
            )
        elif error_msgs:
            report = ""
            if success_count > 0:
                report += (
                    f"Successfully processed {success_count} file(s).\n\n"
                )
            report += (
                f"Encountered {len(error_msgs)} error(s):\n"
                + "\n".join(error_msgs)
            )
            messagebox.showerror(STRINGS["report_title"], report)
