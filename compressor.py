"""
PyInstaller entry point for the Ultimate Image Compressor.

This script lives at the project root so PyInstaller can discover
all modules inside ``src/`` via the ``--paths`` flag.
"""

import os
import sys
from tkinter import messagebox

# Add src/ to Python path so absolute imports work in the frozen bundle
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, _src_dir)

from app import main
from utils import log_error

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"A top-level exception occurred: {e}", exc_info=True)
        messagebox.showerror(
            "Fatal Error",
            "A fatal error occurred. Please check the log file for details.",
        )
