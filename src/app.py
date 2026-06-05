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
    from .gui import UltimateCompressorGUI, SUPPORTED_IMAGE_EXTENSIONS
    from .processor import ImageProcessor
    from .utils import log_error
except ImportError:
    from constants import STRINGS
    from gui import UltimateCompressorGUI, SUPPORTED_IMAGE_EXTENSIONS
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
    
    argv_files = []
    for arg in sys.argv[1:]:
        if arg != "--shift" and os.path.exists(arg):
            argv_files.append(arg)

    is_shift_pressed = False
    try:
        is_shift_pressed = (
            ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000 != 0
        )
    except (AttributeError, OSError):
        pass

    # If shift is not pressed, and we have files, auto-start compression.
    auto_start = not (is_shift_pressed or is_shift_requested) and len(argv_files) > 0

    # Always open GUI
    app = UltimateCompressorGUI(argv_files, auto_start=auto_start)
    app.mainloop()
