"""Package entry point — allows ``python -m src``."""

from tkinter import messagebox

from .app import main
from .utils import log_error

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"A top-level exception occurred: {e}", exc_info=True)
        messagebox.showerror(
            "Fatal Error",
            "A fatal error occurred. Please check the log file for details.",
        )
