"""
Utility functions for the Ultimate Image Compressor.

Provides path resolution, logging setup, tool discovery, and update checking
without any GUI dependencies (no messagebox calls).
"""

import hashlib
import json
import logging
import os
import sys
import tempfile
import urllib.request
import urllib.error
import ctypes
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Logging — writes to %APPDATA% for safety (fixes Issue #11)
# ---------------------------------------------------------------------------
_HAS_ERROR_OCCURRED: bool = False
_LOG_DIR: str = os.path.join(
    os.environ.get("APPDATA", tempfile.gettempdir()),
    "UltimateImageCompressor",
)
os.makedirs(_LOG_DIR, exist_ok=True)
LOG_FILE_PATH: str = os.path.join(_LOG_DIR, "compressor_log.txt")
CONFIG_FILE_PATH: str = os.path.join(_LOG_DIR, "config.json")
CRASH_STATE_FILE_PATH: str = os.path.join(_LOG_DIR, ".crash_state.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config: dict) -> None:
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        log_error(f"Failed to save config: {e}")

def save_crash_state(files: list[str]) -> None:
    try:
        with open(CRASH_STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump({"files": files}, f)
    except Exception as e:
        log_error(f"Failed to save crash state: {e}")

def load_crash_state() -> list[str]:
    if os.path.exists(CRASH_STATE_FILE_PATH):
        try:
            with open(CRASH_STATE_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("files", [])
        except Exception:
            pass
    return []

def clear_crash_state() -> None:
    if os.path.exists(CRASH_STATE_FILE_PATH):
        try:
            os.remove(CRASH_STATE_FILE_PATH)
        except OSError:
            pass

def setup_logging() -> None:
    """Configure the root logger (called once on first error)."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            filename=LOG_FILE_PATH,
            filemode="w",
        )


def log_error(message: str, exc_info: bool = False) -> None:
    """Log an error message. Sets up logging on first call."""
    global _HAS_ERROR_OCCURRED
    if not _HAS_ERROR_OCCURRED:
        setup_logging()
    _HAS_ERROR_OCCURRED = True
    logging.error(message, exc_info=exc_info)


def log_info(message: str) -> None:
    """Log an informational message."""
    if not logging.getLogger().handlers:
        setup_logging()
    logging.info(message)


# ---------------------------------------------------------------------------
# Path resolution — works in both dev and PyInstaller environments
# ---------------------------------------------------------------------------
def get_resource_path(relative_path: str) -> str:
    """Get absolute path to a bundled resource.

    In PyInstaller builds, resources are extracted to ``sys._MEIPASS``.
    In development, the script directory is used, but we check if the file
    exists in the parent directory (project root) if it's missing in `src`.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path: str = sys._MEIPASS  # type: ignore[attr-defined]
        return os.path.join(base_path, relative_path)
    except AttributeError:
        # Dev mode
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        target = os.path.join(base_path, relative_path)
        if not os.path.exists(target):
            # If running via `python -m src`, sys.argv[0] is `src/__main__.py`
            # so base_path is `src/`. If resource is `icon.ico` (root), try going up one level.
            parent_target = os.path.join(os.path.dirname(base_path), relative_path)
            if os.path.exists(parent_target):
                return parent_target
        return target


def get_tool_path(tool_name: str) -> Optional[str]:
    """Locate an external tool binary.

    Returns the absolute path or *None* if the tool is missing.
    **No GUI calls** — the caller decides how to report the error.
    """
    path = get_resource_path(os.path.join("tools", tool_name))
    if not os.path.exists(path):
        log_error(f"Tool not found at expected path: {path}")
        return None
    return path


# ---------------------------------------------------------------------------
# Fonts & App Control
# ---------------------------------------------------------------------------
def load_custom_fonts() -> None:
    """Load bundled Vazirmatn fonts into Windows memory."""
    if os.name != "nt":
        return
    FR_PRIVATE = 0x10
    
    # Try searching for fonts in common locations
    search_dirs = ["tools", "fonts"]
    font_files = ["Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf"]
    
    for font in font_files:
        for folder in search_dirs:
            path = get_resource_path(os.path.join(folder, font))
            if os.path.exists(path):
                try:
                    ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)
                    break
                except Exception as e:
                    log_error(f"Failed to load font {font}: {e}")

def restart_app() -> None:
    """Restart the current Python application."""
    try:
        if getattr(sys, 'frozen', False):
            # PyInstaller executable
            import subprocess
            env = os.environ.copy()
            # Remove PyInstaller specific env vars so the new process unpacks properly
            env.pop('_MEIPASS2', None)
            # Use DETACHED_PROCESS (0x00000008) and close_fds to avoid holding locks
            # on the temporary _MEIxxxx folder that PyInstaller attempts to delete.
            creation_flags = 0x00000008 if os.name == 'nt' else 0
            subprocess.Popen([sys.executable] + sys.argv[1:], env=env, close_fds=True, creationflags=creation_flags)
            sys.exit(0)
        else:
            # Python script
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        log_error(f"Failed to restart app: {e}")

# ---------------------------------------------------------------------------
# Tool integrity verification (Issue #9)
# ---------------------------------------------------------------------------
_TOOL_HASHES_FILE: str = os.path.join(_LOG_DIR, "tool_hashes.json")


def _compute_sha256(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_tool_integrity(tool_path: str) -> bool:
    """Verify that an external tool binary has not been tampered with.

    On first run, stores the hash as a baseline. On subsequent runs,
    compares against the stored hash.

    Returns True if the tool is trusted, False if tampered.
    """
    stored_hashes: dict[str, str] = {}
    if os.path.exists(_TOOL_HASHES_FILE):
        try:
            with open(_TOOL_HASHES_FILE, "r", encoding="utf-8") as f:
                stored_hashes = json.load(f)
        except (json.JSONDecodeError, OSError):
            stored_hashes = {}

    tool_name = os.path.basename(tool_path)
    current_hash = _compute_sha256(tool_path)

    if tool_name in stored_hashes:
        if stored_hashes[tool_name] != current_hash:
            log_error(
                f"SECURITY WARNING: Hash mismatch for {tool_name}! "
                f"Expected {stored_hashes[tool_name]}, got {current_hash}. "
                f"The binary may have been tampered with."
            )
            return False
        return True
    else:
        # First run — store the baseline hash
        stored_hashes[tool_name] = current_hash
        try:
            with open(_TOOL_HASHES_FILE, "w", encoding="utf-8") as f:
                json.dump(stored_hashes, f, indent=2)
        except OSError as e:
            log_error(f"Could not save tool hash baseline: {e}")
        return True


# ---------------------------------------------------------------------------
# Human-readable file size
# ---------------------------------------------------------------------------
def format_file_size(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


# ---------------------------------------------------------------------------
# GitHub Update Checker
# ---------------------------------------------------------------------------
def check_for_updates() -> Tuple[bool, Optional[str], Optional[str]]:
    """Check GitHub API for the latest release.

    Returns:
        (update_available, latest_version, release_url)
    """
    # Replace with the actual GitHub repo
    GITHUB_REPO = "yakat-web/Ultimate-Compressor"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "UltimateCompressor"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            latest_version = data.get("tag_name", "").lstrip("v")
            html_url = data.get("html_url", "")

            try:
                from .constants import VERSION
            except ImportError:
                from constants import VERSION
                
            # Simple version comparison (assumes format X.Y.Z)
            current_parts = [int(p) for p in VERSION.split(".") if p.isdigit()]
            latest_parts = [int(p) for p in latest_version.split(".") if p.isdigit()]

            # Padding to same length just in case
            length = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (length - len(current_parts)))
            latest_parts.extend([0] * (length - len(latest_parts)))

            is_newer = False
            for c, l in zip(current_parts, latest_parts):
                if l > c:
                    is_newer = True
                    break
                elif l < c:
                    break

            if is_newer:
                return True, latest_version, html_url
            return False, latest_version, None

    except Exception as e:
        log_error(f"Failed to check for updates: {e}")
        return False, None, None
