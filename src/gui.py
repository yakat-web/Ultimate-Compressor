"""
Modern GUI for the Ultimate Image Compressor.

Features a Custom Top Bar, Toggleable Control Panels, and Vazirmatn font support.
"""

import os
import pathlib
import re
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox
from typing import Optional, Callable

from PIL import Image, ImageTk

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

if ctk is not None:
    try:
        from utils import load_config, save_config, restart_app, load_custom_fonts, get_resource_path, check_for_updates, log_error, save_crash_state, load_crash_state, clear_crash_state
    except ImportError:
        from utils import load_config, save_config, restart_app, load_custom_fonts, get_resource_path, check_for_updates, log_error, save_crash_state, load_crash_state, clear_crash_state
        
    load_custom_fonts()
    
    _cfg = load_config()
    saved_theme = _cfg.get("theme", "Dark")
    
    if saved_theme == "Light": ctk.set_appearance_mode("light")
    elif saved_theme == "System": ctk.set_appearance_mode("system")
    else: ctk.set_appearance_mode("dark")    
    ctk.set_default_color_theme("blue")
else:
    def load_config(): return {}
    def save_config(c): pass
    def restart_app(): pass
    _cfg = {}

try:
    from .constants import (
        FILETYPES_FILTER,
        OUTPUT_FORMATS,
        STRINGS,
        SUPPORTED_IMAGE_EXTENSIONS,
        VERSION,
        set_language,
        CURRENT_LANGUAGE,
    )
    from .processor import ImageProcessor
    from .utils import format_file_size, get_resource_path, log_error, check_for_updates
except ImportError:
    from constants import (
        FILETYPES_FILTER,
        OUTPUT_FORMATS,
        STRINGS,
        SUPPORTED_IMAGE_EXTENSIONS,
        VERSION,
        set_language,
        CURRENT_LANGUAGE,
    )
    from processor import ImageProcessor
    from utils import format_file_size, get_resource_path, log_error, check_for_updates


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
APP_FONT = "Vazirmatn"

def _validate_suffix(value: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_\-]*$", value))

def _clamp_quality(value: int) -> int:
    return max(1, min(100, value))

def create_rtl_label(parent, text, font_size=11, weight="normal", text_color="white", bg_color="#2b2b2b", anchor="w", justify="left"):
    """Creates a standard tk.Label to ensure proper RTL (Persian) text rendering."""
    fnt = (APP_FONT, font_size, weight)
    lbl = tk.Label(parent, text=text, font=fnt, bg=bg_color, fg=text_color, anchor=anchor, justify=justify)
    return lbl

# ------------------------------------------------------------------
# Main GUI
# ------------------------------------------------------------------
class UltimateCompressorGUI(ctk.CTk if ctk else tk.Tk):  # type: ignore[misc]
    """The main application window."""

    PREVIEW_SIZE = 260

    def __init__(self, files: list[str] | tuple[str, ...] = ()) -> None:
        super().__init__()
        self.files: list[str] = list(files)
        self.processor = ImageProcessor(status_callback=self._safe_update_status)
        self.original_dims: dict[str, tuple[int, int]] = {}
        self._after_id: Optional[str] = None
        
        mode = ctk.get_appearance_mode() if ctk else "Light"
        self.bg_color = "#2b2b2b" if mode == "Dark" else "#dbdbdb"
        self.fg_color = "white" if mode == "Dark" else "black"
        self.win_bg = "#242424" if mode == "Dark" else "#ebebeb"
        self.dropdown_bg = "#3f3f46" if mode == "Dark" else "#f4f4f5"
        self.hover_color = "#52525b" if mode == "Dark" else "#e4e4e7"
        self.dim_color = "#a1a1aa" if mode == "Dark" else "#71717a"

        self._compression_thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._estimation_cancel_event = threading.Event()
        self._estimation_thread: Optional[threading.Thread] = None

        self._preview_photo = None
        self._preview_pil = None
        self._zoom_level = 1.0
        self._pan_start = None
        self._pan_offset = (0, 0)

        # RTL support
        self._is_rtl = (CURRENT_LANGUAGE == "fa")
        self.S = "right" if self._is_rtl else "left"    # Start side
        self.E = "left" if self._is_rtl else "right"    # End side
        self.anc_s = "e" if self._is_rtl else "w"       # Start anchor
        self.anc_e = "w" if self._is_rtl else "e"       # End anchor

        # Settings
        self.show_output = tk.BooleanVar(value=False)
        self.show_quality = tk.BooleanVar(value=False)
        self.show_resize = tk.BooleanVar(value=False)
        
        self.keep_aspect_ratio = tk.BooleanVar(value=True)
        self.fit_to_box = tk.BooleanVar(value=False)
        self.do_not_enlarge = tk.BooleanVar(value=False)
        self.width_var = tk.StringVar()
        self.height_var = tk.StringVar()
        
        self.width_var.trace_add("write", lambda *args: self._on_dim_change("width"))
        self.height_var.trace_add("write", lambda *args: self._on_dim_change("height"))
        
        self.comp_mode_str = tk.StringVar(value=STRINGS["mode_quality"])
        self.quality_var = tk.IntVar(value=75)
        self.size_var = tk.IntVar(value=150)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.suffix_var = tk.StringVar(value="-tiny")
        self.format_var = tk.StringVar(value=STRINGS.get("keep_original_format", "Keep Original"))
        self.output_dir_var = tk.StringVar(value=STRINGS.get("original_folder", "Original Folder"))
        self.auto_convert_png_var = tk.BooleanVar(value=True)
        self.max_png_var = tk.BooleanVar(value=False)

        self.quality_var.trace_add("write", self._on_quality_change)
        self.format_var.trace_add("write", self._on_quality_change)

        self.title(f"{STRINGS['app_title']} v{VERSION}")
        self.geometry("850x700")
        self.minsize(800, 550)

        try:
            icon_path = get_resource_path("icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self._menu_active = False
        self._create_custom_menu_bar()
        self._create_widgets()

        if self.files:
            self.file_listbox.selection_set(0)
            self._on_file_select(None)
            
        self.after(100, self._toggle_panels)
        self.after(200, self._check_crash_state)

    def _check_crash_state(self) -> None:
        crashed_files = load_crash_state()
        if crashed_files:
            msg = "It seems the program crashed previously. Do you want to continue processing the remaining files?" if CURRENT_LANGUAGE != "fa" else "به نظر می‌رسد برنامه در اجرای قبلی کرش کرده است. آیا مایل هستید فایل‌های باقی‌مانده را بازیابی کنید؟"
            if self._custom_askyesno("Crash Recovery" if CURRENT_LANGUAGE != "fa" else "بازیابی اطلاعات", msg):
                self._append_files(crashed_files)
            clear_crash_state()

    # ==================================================================
    # Custom Menu Bar
    # ==================================================================
    def _create_custom_menu_bar(self):
        self.top_bar = ctk.CTkFrame(self, height=45, corner_radius=0, fg_color=self.bg_color)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)

        fnt = ctk.CTkFont(family=APP_FONT, size=14)
        btn_args = {"fg_color": "transparent", "text_color": self.fg_color, "hover_color": self.hover_color, "font": fnt, "width": 60, "height": 35}

        self._active_dropdown = None
        self._active_submenu = None

        btn_file = ctk.CTkButton(self.top_bar, text=STRINGS["menu_file"], **btn_args)
        btn_file.pack(side=self.S, padx=5, pady=5)
        self._wrap_top_btn(btn_file, lambda: self._show_file_menu(btn_file))

        btn_options = ctk.CTkButton(self.top_bar, text=STRINGS["menu_options"], **btn_args)
        btn_options.pack(side=self.S, padx=5, pady=5)
        self._wrap_top_btn(btn_options, lambda: self._show_options_menu(btn_options))

        btn_help = ctk.CTkButton(self.top_bar, text=STRINGS["menu_help"], **btn_args)
        btn_help.pack(side=self.S, padx=5, pady=5)
        self._wrap_top_btn(btn_help, lambda: self._show_help_menu(btn_help))

    def _wrap_top_btn(self, btn, command):
        def wrapper():
            if getattr(self, "_active_top_btn", None) == btn:
                return
            if not self._menu_active:
                self._menu_active = True
                self.after(200, self._check_menu_hover)
            command()
            
        btn.configure(command=wrapper)
        btn.bind("<Enter>", lambda e: wrapper(), add="+")

    def _check_menu_hover(self):
        if not self._menu_active:
            return
            
        try:
            x, y = self.winfo_pointerx(), self.winfo_pointery()
            root_x, root_y = self.winfo_rootx(), self.winfo_rooty()
            local_x, local_y = x - root_x, y - root_y
            
            in_top_bar = 0 <= local_y <= self.top_bar.winfo_height()
            
            in_dropdown = False
            if self._active_dropdown:
                dx, dy = self._active_dropdown.winfo_x(), self._active_dropdown.winfo_y()
                dw, dh = self._active_dropdown.winfo_width(), self._active_dropdown.winfo_height()
                if dx - 10 <= local_x <= dx + dw + 10 and dy - 10 <= local_y <= dy + dh + 10:
                    in_dropdown = True
                    
            in_submenu = False
            if self._active_submenu:
                sx, sy = self._active_submenu.winfo_x(), self._active_submenu.winfo_y()
                sw, sh = self._active_submenu.winfo_width(), self._active_submenu.winfo_height()
                if sx - 10 <= local_x <= sx + sw + 10 and sy - 10 <= local_y <= sy + sh + 10:
                    in_submenu = True
                    
            if not (in_top_bar or in_dropdown or in_submenu):
                self._hover_out_count = getattr(self, "_hover_out_count", 0) + 1
                if self._hover_out_count >= 2:
                    self._close_dropdown()
                    self._hover_out_count = 0
                    return
            else:
                self._hover_out_count = 0
        except Exception:
            pass
            
        self.after(200, self._check_menu_hover)

    def _close_dropdown(self, event=None):
        if hasattr(self, "_active_top_btn") and self._active_top_btn:
            self._active_top_btn.configure(fg_color="transparent")
            self._active_top_btn = None
            
        if self._active_dropdown:
            if event and hasattr(event, "widget"):
                w = event.widget
                try:
                    while w:
                        if w == self._active_dropdown or w == self._active_submenu or w == self.top_bar:
                            return
                        w = w.master
                except Exception:
                    pass
            if self._active_submenu:
                self._active_submenu.destroy()
                self._active_submenu = None
                self._active_submenu_type = None
            self._active_dropdown.destroy()
            self._active_dropdown = None
            self._menu_active = False
            
    def _create_dropdown(self, parent_btn):
        self._close_dropdown()
        self._menu_active = True
        self._active_top_btn = parent_btn
        parent_btn.configure(fg_color=self.hover_color)
        
        dropdown = ctk.CTkFrame(self, fg_color=self.dropdown_bg, corner_radius=8, bg_color="transparent")
        self._active_dropdown = dropdown
        return dropdown

    def _add_dropdown_btn(self, parent, text, command, has_submenu=False):
        fnt = ctk.CTkFont(family=APP_FONT, size=13)
        anc = "e" if self._is_rtl else "w"
        
        if has_submenu:
            btn = ctk.CTkButton(parent, text=text, command=command, 
                                fg_color="transparent", text_color=self.fg_color, hover_color=self.hover_color, 
                                font=fnt, anchor=anc, corner_radius=6)
            btn.pack(fill="x", padx=6, pady=3)
            
            arrow_text = "◀" if self._is_rtl else "▶"
            arr_relx = 0.04 if self._is_rtl else 0.96
            arr_anchor = "w" if self._is_rtl else "e"
            arr = ctk.CTkLabel(btn, text=arrow_text, font=fnt, text_color="gray", fg_color="transparent")
            arr.place(relx=arr_relx, rely=0.5, anchor=arr_anchor)
            btn._submenu_arrow = arr
            
            # Unified hover: open submenu + sync arrow bg
            def _on_enter(e, _btn=btn, _arr=arr):
                _btn._on_enter()
                _arr.configure(fg_color=self.hover_color)
                command()
                
            def _on_leave(e, _btn=btn, _arr=arr):
                _btn._on_leave()
                _arr.configure(fg_color="transparent")
                
            btn.bind("<Enter>", _on_enter)
            btn.bind("<Leave>", _on_leave)
            arr.bind("<Enter>", _on_enter)
            arr.bind("<Leave>", _on_leave)
        else:
            def cmd_wrapper(cmd=command):
                self._close_dropdown()
                self.after(50, cmd)
                
            btn = ctk.CTkButton(parent, text=text, command=cmd_wrapper, 
                                fg_color="transparent", text_color=self.fg_color, hover_color=self.hover_color, 
                                font=fnt, anchor=anc, corner_radius=6)
            btn.pack(fill="x", padx=6, pady=3)
            
        return btn
        
    def _rtl_option_menu(self, menu_widget):
        if self._is_rtl:
            try:
                dropdown = menu_widget._dropdown_menu
                dropdown.delete(0, "end")
                
                font = dropdown.cget("font")
                measure_fn = getattr(font, "measure", None)
                
                if measure_fn:
                    space_w = measure_fn("\u00A0")
                    if space_w <= 0: space_w = 4
                else:
                    space_w = 4
                    measure_fn = lambda x: len(str(x)) * 7
                
                max_w = max(measure_fn(str(v)) for v in dropdown._values)
                
                btn_width = menu_widget.winfo_width()
                if btn_width < 10: btn_width = menu_widget.cget("width")
                
                # Ensure the text is padded enough to make the menu at least as wide as the button
                # The native menu overhead is approx 40-50px.
                target_text_w = max(max_w, btn_width - 40)
                
                for value in dropdown._values:
                    # RLE mark
                    rtl_val = "\u202B" + value + "\u202C"
                    
                    w = measure_fn(str(value))
                    diff = target_text_w - w
                    spaces_count = int(diff / space_w) if diff > 0 else 0
                    
                    # Pad using No-Break Space
                    padded_val = ("\u00A0" * spaces_count) + rtl_val
                    dropdown.add_command(label=padded_val, command=lambda v=value: dropdown._button_callback(v))
                
                def _rtl_open():
                    menu_widget.update_idletasks()
                    import sys
                    
                    # Calculate how far to shift the menu to the left so the right edges align.
                    # Based on the target_text_w and native menu overhead (which can vary).
                    # We add 65px as a safe overhead estimate to ensure it doesn't stick out to the right.
                    estimated_width = target_text_w + 65
                    
                    if estimated_width < menu_widget.winfo_width():
                        estimated_width = menu_widget.winfo_width()
                    
                    x = menu_widget.winfo_rootx() + menu_widget.winfo_width() - estimated_width
                    y = menu_widget.winfo_rooty() + menu_widget._apply_widget_scaling(menu_widget._current_height)
                    
                    if sys.platform == "darwin":
                        y += menu_widget._apply_widget_scaling(8)
                    else:
                        y += menu_widget._apply_widget_scaling(3)
                        
                    if sys.platform == "darwin" or sys.platform.startswith("win"):
                        dropdown.post(int(x), int(y))
                    else:
                        dropdown.tk_popup(int(x), int(y))
                
                menu_widget._open_dropdown_menu = _rtl_open
            except Exception:
                pass

    def _rtl_checkbox(self, cb):
        """Swap checkbox icon to the right side of text for RTL layouts."""
        if self._is_rtl:
            try:
                # Swap: text goes to column 0 (was canvas), canvas goes to column 2 (was text)
                cb._text_label.grid_configure(column=0, sticky="e")
                cb._text_label.configure(anchor="e", justify="right")
                cb._canvas.grid_configure(column=2, sticky="e")
                # Make column 0 expandable so text pushes checkbox to the right
                cb.grid_columnconfigure(0, weight=1)
                cb.grid_columnconfigure(2, weight=0)
            except Exception:
                pass
        return cb

    def _add_dropdown_checkbox(self, parent, text, variable, command=None):
        fnt = ctk.CTkFont(family=APP_FONT, size=13)
        cb = ctk.CTkCheckBox(parent, text=text, variable=variable, font=fnt, command=command, text_color=self.fg_color)
        self._rtl_checkbox(cb)
        cb.pack(fill="x", padx=10, pady=8, anchor=self.anc_s)

    def _show_file_menu(self, btn):
        menu = self._create_dropdown(btn)
        ctk.CTkFrame(menu, fg_color="transparent", height=4).pack()
        self._add_dropdown_btn(menu, STRINGS["add_files_button"], self._add_files)
        self._add_dropdown_btn(menu, STRINGS["add_folder_button"], self._add_folder)
        self._add_dropdown_btn(menu, STRINGS["remove_button"], self._remove_selected)
        self._add_dropdown_btn(menu, STRINGS["clear_button"], self._clear_files)
        self._add_dropdown_btn(menu, STRINGS.get("exit_button", "Exit"), self.destroy)
        ctk.CTkFrame(menu, fg_color="transparent", height=4).pack()
        
        menu.update_idletasks()
        if self._is_rtl:
            menu.place(x=btn.winfo_x() + btn.winfo_width() - menu.winfo_reqwidth(), y=self.top_bar.winfo_height())
        else:
            menu.place(x=btn.winfo_x(), y=self.top_bar.winfo_height())
        menu.lift()

    def _show_options_menu(self, btn):
        menu = self._create_dropdown(btn)
        ctk.CTkFrame(menu, fg_color="transparent", height=4).pack()
        self._add_dropdown_checkbox(menu, STRINGS["output_options_label"], self.show_output, self._toggle_panels)
        self._add_dropdown_checkbox(menu, STRINGS.get("quality_settings", "Quality Settings"), self.show_quality, self._toggle_panels)
        self._add_dropdown_checkbox(menu, STRINGS["resize_label"], self.show_resize, self._toggle_panels)
        ctk.CTkFrame(menu, fg_color="transparent", height=4).pack()
        
        menu.update_idletasks()
        if self._is_rtl:
            menu.place(x=btn.winfo_x() + btn.winfo_width() - menu.winfo_reqwidth(), y=self.top_bar.winfo_height())
        else:
            menu.place(x=btn.winfo_x(), y=self.top_bar.winfo_height())
        menu.lift()

    def _show_help_menu(self, btn):
        menu = self._create_dropdown(btn)
        ctk.CTkFrame(menu, fg_color="transparent", height=4).pack()
        
        self._add_dropdown_btn(menu, STRINGS["language_label"], lambda: self._show_submenu_for(menu, "language"), has_submenu=True)
        self._add_dropdown_btn(menu, STRINGS["theme_label"], lambda: self._show_submenu_for(menu, "theme"), has_submenu=True)
        
        self._add_dropdown_btn(menu, STRINGS["check_updates"], self._do_update_check)
        ctk.CTkFrame(menu, fg_color="transparent", height=4).pack()
        
        menu.update_idletasks()
        if self._is_rtl:
            menu.place(x=btn.winfo_x() + btn.winfo_width() - menu.winfo_reqwidth(), y=self.top_bar.winfo_height())
        else:
            menu.place(x=btn.winfo_x(), y=self.top_bar.winfo_height())
        menu.lift()

    def _show_submenu_for(self, parent_menu, menu_type):
        if getattr(self, "_active_submenu_type", None) == menu_type:
            return
            
        if self._active_submenu:
            self._active_submenu.destroy()
            
        self._active_submenu_type = menu_type
        
        if self._is_rtl:
            x = parent_menu.winfo_x() - 4
        else:
            x = parent_menu.winfo_x() + parent_menu.winfo_width() - 4
        y = parent_menu.winfo_y()
        
        submenu = ctk.CTkFrame(self, fg_color=self.dropdown_bg, corner_radius=8, bg_color="transparent")
        self._active_submenu = submenu
        
        ctk.CTkFrame(submenu, fg_color="transparent", height=4).pack()
        if menu_type == "theme":
            self._add_dropdown_btn(submenu, STRINGS["theme_system"], lambda: self._apply_theme("System"))
            self._add_dropdown_btn(submenu, STRINGS["theme_light"], lambda: self._apply_theme("Light"))
            self._add_dropdown_btn(submenu, STRINGS["theme_dark"], lambda: self._apply_theme("Dark"))
        elif menu_type == "language":
            self._add_dropdown_btn(submenu, "English", lambda: self._apply_language("en"))
            self._add_dropdown_btn(submenu, "فارسی", lambda: self._apply_language("fa"))
        ctk.CTkFrame(submenu, fg_color="transparent", height=4).pack()
        
        submenu.update_idletasks()
        if self._is_rtl:
            x = parent_menu.winfo_x() - submenu.winfo_reqwidth() + 4
        submenu.place(x=x, y=y)
        submenu.lift()

    def _apply_icon(self, dialog):
        try:
            icon_path = get_resource_path("icon.ico")
            if os.path.exists(icon_path):
                dialog.after(250, lambda: dialog.iconbitmap(icon_path))
                dialog.after(300, lambda: dialog.wm_iconbitmap(icon_path))
        except Exception:
            pass

    def _custom_askyesno(self, title, message):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._apply_icon(dialog)
        
        ctk.CTkLabel(dialog, text=message, font=(APP_FONT, 14), wraplength=350).pack(pady=30)
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        
        result = [False]
        def on_yes():
            result[0] = True
            dialog.destroy()
        def on_no():
            dialog.destroy()
            
        yes_text = "بله" if CURRENT_LANGUAGE == "fa" else "Yes"
        no_text = "خیر" if CURRENT_LANGUAGE == "fa" else "No"
            
        ctk.CTkButton(btn_frame, text=yes_text, command=on_yes, width=100, font=(APP_FONT, 13)).pack(side="left", expand=True)
        ctk.CTkButton(btn_frame, text=no_text, command=on_no, width=100, fg_color="#dc2626", hover_color="#b91c1c", font=(APP_FONT, 13)).pack(side="right", expand=True)
        
        self.wait_window(dialog)
        return result[0]

    def _custom_messagebox(self, title, message, color="#2563eb"):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("400x180")
        dialog.transient(self)
        dialog.grab_set()
        self._apply_icon(dialog)
        
        ctk.CTkLabel(dialog, text=message, font=(APP_FONT, 14), wraplength=350).pack(pady=30)
        
        ok_text = "تایید" if CURRENT_LANGUAGE == "fa" else "OK"
        ctk.CTkButton(dialog, text=ok_text, command=dialog.destroy, width=120, fg_color=color, font=(APP_FONT, 13)).pack(pady=10)
        
        self.wait_window(dialog)

    def _custom_report(self, title, message, retry_callback=None):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("600x400")
        dialog.transient(self)
        dialog.grab_set()
        self._apply_icon(dialog)
        
        txt = ctk.CTkTextbox(dialog, font=(APP_FONT, 13), wrap="word", fg_color=self.bg_color)
        txt.pack(fill="both", expand=True, padx=15, pady=15)
        txt.insert("1.0", message)
        txt.configure(state="disabled")
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        
        ok_text = "تایید" if CURRENT_LANGUAGE == "fa" else "OK"
        if retry_callback:
            retry_text = "تلاش مجدد برای ناموفق‌ها" if CURRENT_LANGUAGE == "fa" else "Retry Failed Files"
            
            def on_retry():
                dialog.destroy()
                retry_callback()
                
            ctk.CTkButton(btn_frame, text=retry_text, command=on_retry, width=150, font=(APP_FONT, 14), fg_color="#ea580c", hover_color="#c2410c").pack(side="left", expand=True)
            ctk.CTkButton(btn_frame, text=ok_text, command=dialog.destroy, width=120, font=(APP_FONT, 14)).pack(side="right", expand=True)
        else:
            ctk.CTkButton(btn_frame, text=ok_text, command=dialog.destroy, width=120, font=(APP_FONT, 14)).pack(pady=0)
        
        self.wait_window(dialog)

    def _apply_theme(self, theme_name):
        if theme_name != saved_theme:
            msg = "برای اعمال پوسته باید برنامه را ری‌استارت کنید. آیا موافقید؟" if CURRENT_LANGUAGE == "fa" else "The application must restart to fully apply the theme. Restart now?"
            if self._custom_askyesno("Restart Required", msg):
                c = load_config()
                c["theme"] = theme_name
                save_config(c)
                restart_app()

    def _apply_language(self, lang_code):
        if lang_code != CURRENT_LANGUAGE:
            msg = "برای تغییر زبان باید برنامه را ری‌استارت کنید. آیا موافقید؟" if CURRENT_LANGUAGE == "fa" else "The application must restart to change the language. Restart now?"
            if self._custom_askyesno("Restart Required", msg):
                c = load_config()
                c["language"] = lang_code
                save_config(c)
                restart_app()

    def _browse_output_dir(self, var) -> None:
        directory = filedialog.askdirectory(title="Select Output Folder")
        if directory: var.set(directory)

    # ==================================================================
    # Main UI Layout
    # ==================================================================
    def _create_widgets(self) -> None:
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))
        
        self._create_status_bar(main_frame)
        self._create_progress_section(main_frame)
        
        # PanedWindows for flexible resizing
        self.v_paned = tk.PanedWindow(main_frame, orient=tk.VERTICAL, bd=0, sashwidth=6, bg=self.win_bg, borderwidth=0)
        self.v_paned.pack(side="top", fill=tk.BOTH, expand=True, pady=(0, 10))

        self.h_paned = tk.PanedWindow(self.v_paned, orient=tk.HORIZONTAL, bd=0, sashwidth=6, bg=self.win_bg, borderwidth=0)
        self.v_paned.add(self.h_paned, stretch="always")

        self.list_frame = ctk.CTkFrame(self.h_paned, fg_color="transparent")
        self.preview_frame = ctk.CTkFrame(self.h_paned, fg_color="transparent", width=self.PREVIEW_SIZE + 20)
        
        if self._is_rtl:
            self.h_paned.add(self.preview_frame, stretch="never", minsize=200)
            self.h_paned.add(self.list_frame, stretch="always", minsize=200)
        else:
            self.h_paned.add(self.list_frame, stretch="always", minsize=200)
            self.h_paned.add(self.preview_frame, stretch="never", minsize=200)

        self._create_file_list(self.list_frame)
        self._create_preview_panel(self.preview_frame)

        self._create_control_panels(self.v_paned)
        
        self.bind("<Button-1>", lambda e: self._close_dropdown(e), add="+")

    # ------------------------------------------------------------------
    def _create_file_list(self, parent) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill=tk.BOTH, expand=True)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 8))

        create_rtl_label(header, STRINGS["files_label"], font_size=12, weight="bold", bg_color=self.win_bg, text_color=self.fg_color).pack(side=self.S)

        self.file_count_var = tk.StringVar(value=STRINGS["files_found"].format(count=len(self.files)))
        self.count_lbl = create_rtl_label(header, STRINGS["files_found"].format(count=len(self.files)), font_size=11, bg_color=self.win_bg, text_color="gray")
        self.count_lbl.pack(side=self.E)

        list_container = ctk.CTkFrame(frame, corner_radius=10, fg_color=self.bg_color)
        list_container.pack(fill=tk.BOTH, expand=True)
        self.file_listbox = tk.Listbox(
            list_container, selectmode=tk.EXTENDED, exportselection=False,
            bg=self.bg_color, fg=self.fg_color, selectbackground="#3b82f6", selectforeground="white",
            font=(APP_FONT, 12), borderwidth=0, highlightthickness=0,
            justify="right" if self._is_rtl else "left",
        )

        scrollbar = ctk.CTkScrollbar(list_container, command=self.file_listbox.yview)
        self.file_listbox.config(yscrollcommand=scrollbar.set)
        
        if self._is_rtl:
            scrollbar.pack(side=tk.LEFT, fill=tk.Y, pady=8, padx=(8, 0))
            self.file_listbox.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 8), pady=8)
        else:
            self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=8, padx=(0,8))

        for f in self.files:
            self.file_listbox.insert(tk.END, os.path.basename(f))
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_select)

    # ------------------------------------------------------------------
    def _create_preview_panel(self, parent) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill=tk.BOTH, expand=True)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 8))

        create_rtl_label(header, STRINGS["preview_label"], font_size=12, weight="bold", bg_color=self.win_bg, text_color=self.fg_color).pack(side=self.S)

        self.file_info_lbl = create_rtl_label(header, STRINGS["no_file_selected"], font_size=10, bg_color=self.win_bg, text_color="gray")
        self.file_info_lbl.pack(side=self.E)

        canvas_container = ctk.CTkFrame(frame, corner_radius=10, fg_color=self.bg_color)
        canvas_container.pack(side="top", fill=tk.BOTH, expand=True)
        self.preview_canvas = tk.Canvas(
            canvas_container, bg=self.bg_color, highlightthickness=0, borderwidth=0, cursor="hand2",
        )
        self.preview_canvas.pack(padx=2, pady=2, fill=tk.BOTH, expand=True)

        self.preview_canvas.bind("<Configure>", lambda e: self._render_preview())
        self.preview_canvas.bind("<MouseWheel>", self._on_preview_scroll)
        self.preview_canvas.bind("<Double-1>", self._on_preview_reset_zoom)
        self.preview_canvas.bind("<ButtonPress-1>", self._on_preview_pan_start)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_pan_drag)

    # ------------------------------------------------------------------
    def _create_control_panels(self, parent) -> None:
        self.controls_wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        self.controls_container = ctk.CTkScrollableFrame(self.controls_wrapper, corner_radius=10, fg_color=self.bg_color, height=180)
        self.controls_container.pack(fill="both", expand=True)
        fnt = ctk.CTkFont(family=APP_FONT, size=13)

        # 1. Output Panel
        self.output_panel = ctk.CTkFrame(self.controls_container, fg_color="transparent")
        create_rtl_label(self.output_panel, STRINGS["output_options_label"], font_size=12, weight="bold", bg_color=self.bg_color, text_color="#3b82f6").pack(anchor=self.anc_s, pady=(0, 5))
        
        o_row1 = ctk.CTkFrame(self.output_panel, fg_color="transparent")
        o_row1.pack(fill="x", pady=2)
        chk_overwrite = ctk.CTkCheckBox(o_row1, text=STRINGS["overwrite_label"], variable=self.overwrite_var, command=self._toggle_output_widgets, font=fnt)
        self._rtl_checkbox(chk_overwrite)
        chk_overwrite.pack(side=self.S, padx=(0 if not self._is_rtl else 20, 20 if not self._is_rtl else 0))
        
        self.lbl_format = create_rtl_label(o_row1, STRINGS["output_format_label"], bg_color=self.bg_color, text_color=self.fg_color)
        self.lbl_format.pack(side=self.S, padx=5)
        
        translated_formats = [STRINGS.get("keep_original_format", "Keep Original")] + OUTPUT_FORMATS[1:]
        self.format_menu = ctk.CTkOptionMenu(o_row1, variable=self.format_var, values=translated_formats, width=120, font=fnt, dropdown_font=fnt, corner_radius=6, 
                                             fg_color=self.dropdown_bg, button_color=self.dropdown_bg, button_hover_color=self.hover_color, text_color=self.fg_color, anchor=self.anc_s)
        self._rtl_option_menu(self.format_menu)
        self.format_menu.pack(side=self.S, padx=(0 if not self._is_rtl else 20, 20 if not self._is_rtl else 0))
        
        self.lbl_suffix = create_rtl_label(o_row1, STRINGS["suffix_label"], bg_color=self.bg_color, text_color=self.fg_color)
        self.lbl_suffix.pack(side=self.S, padx=5)
        self.suffix_entry = ctk.CTkEntry(o_row1, textvariable=self.suffix_var, width=80, font=fnt)
        self.suffix_entry.pack(side=self.S, padx=(0 if not self._is_rtl else 20, 20 if not self._is_rtl else 0))
        
        o_row2 = ctk.CTkFrame(self.output_panel, fg_color="transparent")
        o_row2.pack(fill="x", pady=2)
        self.lbl_dir = create_rtl_label(o_row2, STRINGS["output_dir_label"], bg_color=self.bg_color, text_color=self.fg_color)
        self.lbl_dir.pack(side=self.S, padx=5)
        self.dir_entry = ctk.CTkEntry(o_row2, textvariable=self.output_dir_var, font=fnt, justify="right" if self._is_rtl else "left")
        self.dir_entry.pack(side=self.S, padx=5, fill="x", expand=True)
        self.dir_btn = ctk.CTkButton(o_row2, text=STRINGS.get("browse_button", "Browse"), width=60, font=fnt, command=lambda: self._browse_output_dir(self.output_dir_var))
        self.dir_btn.pack(side=self.S)

        # 2. Quality Panel
        self.quality_panel = ctk.CTkFrame(self.controls_container, fg_color="transparent")
        create_rtl_label(self.quality_panel, STRINGS.get("quality_settings", "Quality Settings"), font_size=12, weight="bold", bg_color=self.bg_color, text_color="#3b82f6").pack(anchor=self.anc_s, pady=(10, 5))
        
        q_row1 = ctk.CTkFrame(self.quality_panel, fg_color="transparent")
        q_row1.pack(fill="x", pady=2)
        
        modes = [STRINGS["mode_quality"], STRINGS["mode_size"]]
        self.comp_mode_str.set(STRINGS["mode_quality"])
        self.mode_menu = ctk.CTkOptionMenu(q_row1, variable=self.comp_mode_str, values=modes, command=self._on_mode_change, width=120, font=fnt, dropdown_font=fnt, corner_radius=6,
                                           fg_color=self.dropdown_bg, button_color=self.dropdown_bg, button_hover_color=self.hover_color, text_color=self.fg_color, anchor=self.anc_s)
        self._rtl_option_menu(self.mode_menu)
        self.mode_menu.pack(side=self.S, padx=(0 if not self._is_rtl else 15, 15 if not self._is_rtl else 0))
        
        self.quality_container = ctk.CTkFrame(q_row1, fg_color="transparent")
        self.quality_container.pack(side=self.S, fill="x")
        self.quality_lbl = create_rtl_label(self.quality_container, STRINGS["quality_label"], bg_color=self.bg_color, text_color=self.fg_color)
        self.quality_lbl.pack(side=self.S, padx=5)
        self.quality_entry = ctk.CTkEntry(self.quality_container, textvariable=self.quality_var, width=60, font=fnt)
        self.quality_entry.pack(side=self.S, padx=(0 if not self._is_rtl else 20, 20 if not self._is_rtl else 0))

        self.size_container = ctk.CTkFrame(q_row1, fg_color="transparent")
        self.size_lbl = create_rtl_label(self.size_container, STRINGS["size_label"], bg_color=self.bg_color, text_color=self.fg_color)
        self.size_lbl.pack(side=self.S, padx=5)
        self.size_entry = ctk.CTkEntry(self.size_container, textvariable=self.size_var, width=80, font=fnt)
        self.size_entry.pack(side=self.S, padx=(0 if not self._is_rtl else 20, 20 if not self._is_rtl else 0))
        
        q_row2 = ctk.CTkFrame(self.quality_panel, fg_color="transparent")
        q_row2.pack(fill="x", pady=2)
        self.chk_max_png = ctk.CTkCheckBox(q_row2, text=STRINGS["max_png_label"], variable=self.max_png_var, command=self._toggle_png_widgets, font=fnt)
        self._rtl_checkbox(self.chk_max_png)
        self.chk_max_png.pack(side=self.S, padx=(0 if not self._is_rtl else 15, 15 if not self._is_rtl else 0))
        self.chk_auto_png = ctk.CTkCheckBox(q_row2, text=STRINGS["auto_convert_png_label"], variable=self.auto_convert_png_var, font=fnt)
        self._rtl_checkbox(self.chk_auto_png)
        self.chk_auto_png.pack(side=self.S)

        # 3. Resize Panel
        self.resize_panel = ctk.CTkFrame(self.controls_container, fg_color="transparent")
        create_rtl_label(self.resize_panel, STRINGS["resize_label"], font_size=12, weight="bold", bg_color=self.bg_color, text_color="#3b82f6").pack(anchor=self.anc_s, pady=(10, 5))
        
        r_row1 = ctk.CTkFrame(self.resize_panel, fg_color="transparent")
        r_row1.pack(fill="x", pady=2)
        
        create_rtl_label(r_row1, STRINGS["width_label"], bg_color=self.bg_color, text_color=self.fg_color).pack(side=self.S, padx=5)
        self.width_entry = ctk.CTkEntry(r_row1, textvariable=self.width_var, width=60, font=fnt)
        self.width_entry.pack(side=self.S, padx=(0 if not self._is_rtl else 10, 10 if not self._is_rtl else 0))
        
        def toggle_aspect():
            self.keep_aspect_ratio.set(not self.keep_aspect_ratio.get())
            c = "#3b82f6" if self.keep_aspect_ratio.get() else self.dropdown_bg
            self.aspect_btn.configure(fg_color=c)

        bg_aspect = "#3b82f6" if self.keep_aspect_ratio.get() else self.dropdown_bg
        self.aspect_btn = ctk.CTkButton(r_row1, text="🔗", width=30, fg_color=bg_aspect, font=fnt, command=toggle_aspect)
        self.aspect_btn.pack(side=self.S, padx=(0 if not self._is_rtl else 10, 10 if not self._is_rtl else 0))
        
        create_rtl_label(r_row1, STRINGS["height_label"], bg_color=self.bg_color, text_color=self.fg_color).pack(side=self.S, padx=5)
        self.height_entry = ctk.CTkEntry(r_row1, textvariable=self.height_var, width=60, font=fnt)
        self.height_entry.pack(side=self.S, padx=(0 if not self._is_rtl else 20, 20 if not self._is_rtl else 0))
        
        r_row2 = ctk.CTkFrame(self.resize_panel, fg_color="transparent")
        r_row2.pack(fill="x", pady=2)
        
        self.chk_fit_to = ctk.CTkCheckBox(r_row2, text=STRINGS.get("fit_to_label", "Fit to Bounding Box"), variable=self.fit_to_box, font=fnt)
        self._rtl_checkbox(self.chk_fit_to)
        self.chk_fit_to.pack(side=self.S, padx=(0 if not self._is_rtl else 15, 15 if not self._is_rtl else 0))
        
        self.chk_no_enlarge = ctk.CTkCheckBox(r_row2, text=STRINGS.get("do_not_enlarge_label", "Do not enlarge"), variable=self.do_not_enlarge, font=fnt)
        self._rtl_checkbox(self.chk_no_enlarge)
        self.chk_no_enlarge.pack(side=self.S)

        self._on_mode_change(self.comp_mode_str.get())
        self._toggle_output_widgets()
        self._toggle_png_widgets()
        
    def _toggle_panels(self):
        count = 0
        for p in (self.output_panel, self.quality_panel, self.resize_panel):
            p.pack_forget()
            
        if self.show_output.get():
            self.output_panel.pack(fill="x", padx=10, pady=(0,5))
            count += 1
        if self.show_quality.get():
            self.quality_panel.pack(fill="x", padx=10, pady=(0,5))
            count += 1
        if self.show_resize.get():
            self.resize_panel.pack(fill="x", padx=10, pady=(0,5))
            self.width_entry.configure(state="normal")
            self.height_entry.configure(state="normal")
            self.aspect_btn.configure(state="normal")
            self.chk_fit_to.configure(state="normal")
            self.chk_no_enlarge.configure(state="normal")
            count += 1
        else:
            self.width_entry.configure(state="disabled")
            self.height_entry.configure(state="disabled")
            self.aspect_btn.configure(state="disabled")
            self.chk_fit_to.configure(state="disabled")
            self.chk_no_enlarge.configure(state="disabled")
            
        if count == 0:
            if str(self.controls_wrapper) in self.v_paned.panes():
                self.v_paned.remove(self.controls_wrapper)
        else:
            if str(self.controls_wrapper) not in self.v_paned.panes():
                self.v_paned.add(self.controls_wrapper, minsize=100)
            
        if hasattr(self, "file_listbox"):
            self._on_file_select(None)

    def _on_mode_change(self, selected_mode):
        if selected_mode == STRINGS["mode_quality"]:
            self.size_container.pack_forget()
            self.quality_container.pack(side=self.S, fill="x")
            self._on_quality_change()
        else:
            self.quality_container.pack_forget()
            self.size_container.pack(side=self.S, fill="x")
            if hasattr(self, "est_lbl"):
                self.est_lbl.config(text="")

    def _on_dim_change(self, changed_var, *args):
        if getattr(self, "_is_updating_dims", False):
            return
            
        if not self.keep_aspect_ratio.get() or not self.show_resize.get():
            return
            
        try:
            if not hasattr(self, "file_listbox"): return
            sel = self.file_listbox.curselection()
            if not sel: return
            f_path = self.files[sel[0]]
            orig_w, orig_h = self.original_dims.get(f_path, (0, 0))
        except Exception:
            return
            
        if orig_w <= 0 or orig_h <= 0:
            return
            
        self._is_updating_dims = True
        try:
            if changed_var == "width":
                w_str = self.width_var.get()
                if w_str.isdigit() and int(w_str) > 0:
                    w = int(w_str)
                    h = int(round(w * orig_h / orig_w))
                    self.height_var.set(str(max(1, h)))
                elif w_str == "":
                    self.height_var.set("")
            elif changed_var == "height":
                h_str = self.height_var.get()
                if h_str.isdigit() and int(h_str) > 0:
                    h = int(h_str)
                    w = int(round(h * orig_w / orig_h))
                    self.width_var.set(str(max(1, w)))
                elif h_str == "":
                    self.width_var.set("")
        finally:
            self._is_updating_dims = False

    def _toggle_output_widgets(self):
        state = "disabled" if self.overwrite_var.get() else "normal"
        color = self.dim_color if self.overwrite_var.get() else self.fg_color
        
        self.format_menu.configure(state=state)
        self.suffix_entry.configure(state=state)
        self.dir_entry.configure(state=state)
        self.dir_btn.configure(state=state)
        
        self.lbl_format.configure(fg=color)
        self.lbl_suffix.configure(fg=color)
        self.lbl_dir.configure(fg=color)
        
        self._toggle_png_widgets()
        
    def _toggle_png_widgets(self):
        state = "disabled" if self.max_png_var.get() or self.overwrite_var.get() else "normal"
        self.chk_auto_png.configure(state=state)

    # ------------------------------------------------------------------
    def _create_progress_section(self, parent) -> None:
        self.progress_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.progress_frame.pack(side="bottom", fill=tk.X, pady=(0, 10))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, variable=self.progress_var, height=20)
        self.progress_bar.set(0)
        
        # Percentage label overlapping the progress bar
        self.progress_percent = ctk.CTkLabel(self.progress_frame, text="", font=(APP_FONT, 12, "bold"), text_color="white", bg_color="transparent")

        btn_frame = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X)

        self.compress_button = ctk.CTkButton(
            btn_frame, text=STRINGS["compress_button"], command=self._start_compression,
            font=ctk.CTkFont(family=APP_FONT, size=18, weight="bold"), height=55, corner_radius=10,
            fg_color="#2563eb", hover_color="#1d4ed8",
        )
        self.compress_button.pack(side=self.S, fill=tk.X, expand=True, padx=(0 if not self._is_rtl else 15, 15 if not self._is_rtl else 0))

        self.cancel_button = ctk.CTkButton(
            btn_frame, text=STRINGS["cancel_button"], command=self._cancel_compression,
            font=ctk.CTkFont(family=APP_FONT, size=14), height=55, corner_radius=10,
            fg_color="#dc2626", hover_color="#b91c1c", state="disabled", width=120,
        )
        self.cancel_button.pack(side=self.E)

    # ------------------------------------------------------------------
    def _create_status_bar(self, parent) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(side="bottom", fill=tk.X)

        self.status_lbl = create_rtl_label(frame, STRINGS["status_ready"], bg_color=self.win_bg, text_color=self.fg_color)
        self.status_lbl.pack(side=self.S)
        
        self.eta_lbl = create_rtl_label(frame, "", font_size=11, weight="bold", bg_color=self.win_bg, text_color="#3b82f6", anchor=self.anc_e)
        self.eta_lbl.pack(side=self.E, padx=(10, 0))
        
        self.est_lbl = create_rtl_label(frame, "", font_size=11, weight="bold", bg_color=self.win_bg, text_color="#60a5fa", anchor=self.anc_e)
        self.est_lbl.pack(side=self.E)

    # ==================================================================
    # File management
    # ==================================================================
    def _add_files(self) -> None:
        new_files = filedialog.askopenfilenames(parent=self, title=STRINGS["add_files_button"], filetypes=FILETYPES_FILTER)
        if new_files:
            self._append_files(list(new_files))

    def _add_folder(self) -> None:
        directory = filedialog.askdirectory(parent=self, title=STRINGS["add_folder_button"])
        if not directory:
            return
        found: list[str] = []
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            found.extend(str(p) for p in pathlib.Path(directory).rglob(f"*{ext}") if p.is_file())
            found.extend(str(p) for p in pathlib.Path(directory).rglob(f"*{ext.upper()}") if p.is_file() and str(p) not in found)
        if found:
            self._append_files(sorted(set(found)))
        else:
            msg = f"No supported images found in:\n{directory}" if CURRENT_LANGUAGE == "en" else f"هیچ تصویری در این پوشه یافت نشد:\n{directory}"
            self._custom_messagebox("No Images Found", msg, color="#dc2626")

    def _append_files(self, new_files: list[str]) -> None:
        existing = set(self.files)
        for f in new_files:
            if f not in existing:
                self.files.append(f)
                self.file_listbox.insert(tk.END, os.path.basename(f))
        self.count_lbl.config(text=STRINGS["files_found"].format(count=len(self.files)))

    def _remove_selected(self) -> None:
        selection = list(self.file_listbox.curselection())
        for idx in reversed(selection):
            self.file_listbox.delete(idx)
            del self.files[idx]
        self.count_lbl.config(text=STRINGS["files_found"].format(count=len(self.files)))
        self._clear_preview()

    def _clear_files(self) -> None:
        self.files.clear()
        self.file_listbox.delete(0, tk.END)
        self.count_lbl.config(text=STRINGS["files_found"].format(count=0))
        self._clear_preview()

    # ==================================================================
    # Preview with zoom
    # ==================================================================
    def _update_preview(self, file_path: str) -> None:
        try:
            with Image.open(file_path) as img:
                w, h = img.size
                fmt = img.format or os.path.splitext(file_path)[1].upper()
                self.original_dims[file_path] = (w, h)

                if not self.show_resize.get():
                    self.width_var.set("")
                    self.height_var.set("")

                full_img = img.copy()
                bg_color = self.bg_color
                if full_img.mode in ("RGBA", "P"):
                    bg = Image.new("RGB", full_img.size, bg_color)
                    if full_img.mode == "P":
                        full_img = full_img.convert("RGBA")
                    bg.paste(full_img, mask=full_img.split()[-1])
                    full_img = bg
                elif full_img.mode != "RGB":
                    full_img = full_img.convert("RGB")

                self._preview_pil = full_img
                self._zoom_level = 1.0
                self._pan_offset = (0, 0)
                self._render_preview()

            file_size = format_file_size(os.path.getsize(file_path))
            self.file_info_lbl.config(text=STRINGS["file_info_format"].format(width=w, height=h, size=file_size, format=fmt))
        except (OSError, ValueError) as e:
            self._clear_preview()
            self.file_info_lbl.config(text=f"Cannot preview: {e}")

    def _render_preview(self) -> None:
        if self._preview_pil is None:
            return

        img = self._preview_pil
        self.preview_canvas.update_idletasks()
        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()
        if canvas_w < 10: canvas_w = self.PREVIEW_SIZE
        if canvas_h < 10: canvas_h = self.PREVIEW_SIZE

        scale = min(canvas_w / img.width, canvas_h / img.height)
        display_scale = scale * self._zoom_level
        new_w = max(1, int(img.width * display_scale))
        new_h = max(1, int(img.height * display_scale))

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(resized)

        self.preview_canvas.delete("all")
        cx = canvas_w // 2 + self._pan_offset[0]
        cy = canvas_h // 2 + self._pan_offset[1]
        self.preview_canvas.create_image(cx, cy, image=self._preview_photo, anchor="center")

    def _on_preview_scroll(self, event) -> None:
        if self._preview_pil is None:
            return
        if event.delta > 0:
            self._zoom_level = min(8.0, self._zoom_level * 1.2)
        else:
            self._zoom_level = max(0.5, self._zoom_level / 1.2)
        self._render_preview()

    def _on_preview_reset_zoom(self, event) -> None:
        self._zoom_level = 1.0
        self._pan_offset = (0, 0)
        self._render_preview()

    def _on_preview_pan_start(self, event) -> None:
        self._pan_start = (event.x, event.y)

    def _on_preview_pan_drag(self, event) -> None:
        if self._pan_start is None or self._preview_pil is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._pan_offset = (self._pan_offset[0] + dx, self._pan_offset[1] + dy)
        self._pan_start = (event.x, event.y)
        self._render_preview()

    def _clear_preview(self) -> None:
        self.preview_canvas.delete("all")
        self._preview_photo = None
        self._preview_pil = None
        self._zoom_level = 1.0
        self._pan_offset = (0, 0)
        self.file_info_lbl.config(text=STRINGS["no_file_selected"])

    # ==================================================================
    # Event handlers
    # ==================================================================
    def _on_file_select(self, event) -> None:
        try:
            sel_idx = self.file_listbox.curselection()[0]
            f_path = self.files[sel_idx]
            self._update_preview(f_path)
        except (IndexError, FileNotFoundError):
            self._clear_preview()

        if self.comp_mode_str.get() == STRINGS["mode_quality"]:
            self._on_quality_change()

    def _on_quality_change(self, *args) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
        if self.comp_mode_str.get() == STRINGS["mode_quality"]:
            self._after_id = self.after(500, self._start_estimation_thread)
        else:
            if hasattr(self, "est_lbl"): self.est_lbl.config(text="")

    def _do_update_check(self) -> None:
        self.config(cursor="watch")
        self.update_idletasks()
        def run_check():
            has_update, version, url = check_for_updates()
            self.config(cursor="")
            if has_update:
                if self._custom_askyesno("Update", STRINGS["update_available"].format(new_ver=version)):
                    if url: webbrowser.open(url)
            else:
                self._custom_messagebox("Update", STRINGS["no_updates"])
        threading.Thread(target=run_check, daemon=True).start()

    def _get_target_dimensions(self, original_w, original_h):
        try: w = int(self.width_var.get())
        except ValueError: w = 0
        try: h = int(self.height_var.get())
        except ValueError: h = 0
        
        if w == 0 and h == 0:
            return original_w, original_h
            
        target_w, target_h = original_w, original_h
        
        if self.fit_to_box.get() and w > 0 and h > 0:
            ratio = min(w / original_w, h / original_h)
            target_w = int(original_w * ratio)
            target_h = int(original_h * ratio)
        else:
            if w > 0 and h > 0:
                if self.keep_aspect_ratio.get():
                    ratio = min(w / original_w, h / original_h)
                    target_w = int(original_w * ratio)
                    target_h = int(original_h * ratio)
                else:
                    target_w, target_h = w, h
            elif w > 0:
                target_w = w
                target_h = int(original_h * (w / original_w))
            elif h > 0:
                target_h = h
                target_w = int(original_w * (h / original_h))
                
        if self.do_not_enlarge.get():
            if target_w > original_w or target_h > original_h:
                target_w = original_w
                target_h = original_h
                
        return max(1, target_w), max(1, target_h)

    # ==================================================================
    # Estimation thread
    # ==================================================================
    def _start_estimation_thread(self) -> None:
        if not hasattr(self, "file_listbox") or not self.file_listbox.curselection():
            return
        self._estimation_cancel_event.set()
        self._estimation_cancel_event = threading.Event()
        self._safe_update_status(STRINGS["status_estimating"])
        self.est_lbl.config(text="...")

        cancel_event = self._estimation_cancel_event
        thread = threading.Thread(target=self._run_estimation, args=(cancel_event,), daemon=True)
        self._estimation_thread = thread
        thread.start()

    def _run_estimation(self, cancel_event: threading.Event) -> None:
        temp_files: list[str] = []
        try:
            sel_idx = self.file_listbox.curselection()
            if not sel_idx: return
            f_path = self.files[sel_idx[0]]
            quality = _clamp_quality(self.quality_var.get())
            if cancel_event.is_set(): return

            target_format_str = self.format_var.get()
            target_format = target_format_str.lower() if target_format_str != STRINGS.get("keep_original_format", "Keep Original").lower() else os.path.splitext(f_path)[1].lower().replace(".", "")
            original_ext = os.path.splitext(f_path)[1].lower()

            if self.auto_convert_png_var.get() and original_ext == ".png" and not self.max_png_var.get():
                if self.processor.is_png_fully_opaque(f_path):
                    target_format = "jpeg"

            current_path = f_path
            safe_path, safe_copy = self.processor._safe_copy_for_processing(current_path)
            if safe_copy:
                current_path = safe_path
                temp_files.append(safe_copy)

            if cancel_event.is_set(): return

            if self.show_resize.get():
                with Image.open(current_path) as img:
                    orig_w, orig_h = img.size
                    target_w, target_h = self._get_target_dimensions(orig_w, orig_h)
                    if target_w != orig_w or target_h != orig_h:
                        temp_resized = os.path.join(tempfile.gettempdir(), f"temp_estimate_{os.urandom(8).hex()}{original_ext}")
                        img.resize((target_w, target_h), Image.Resampling.LANCZOS).save(temp_resized)
                        current_path = temp_resized
                        temp_files.append(temp_resized)

            if cancel_event.is_set(): return

            current_ext = os.path.splitext(current_path)[1].lower().strip(".")
            if current_ext != target_format:
                temp_converted = self.processor._convert_image(current_path, target_format)
                current_path = temp_converted
                temp_files.append(temp_converted)

            if cancel_event.is_set(): return

            with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as temp_out:
                temp_out_name = temp_out.name
            temp_files.append(temp_out_name)

            is_success = False
            msg = ""
            if target_format in ("jpg", "jpeg"):
                is_success, msg = self.processor.compress_jpeg(current_path, temp_out_name, quality)
            elif target_format == "png":
                q_range = f"{quality - 10}-{quality}" if quality > 10 else f"0-{quality}"
                is_success, msg = self.processor.compress_png(current_path, temp_out_name, q_range, self.max_png_var.get())
            elif target_format == "webp":
                is_success, msg = self.processor.compress_webp(current_path, temp_out_name, quality)
            elif target_format == "ico":
                try: from .constants import ICO_SIZES
                except ImportError: from constants import ICO_SIZES
                with Image.open(current_path) as img:
                    img.save(temp_out_name, format="ICO", sizes=ICO_SIZES)
                is_success = True

            if cancel_event.is_set(): return

            if is_success:
                size_kb = os.path.getsize(current_path) / 1024 if msg == "Already Optimized" else os.path.getsize(temp_out_name) / 1024
                self.after(0, self._update_estimated_size_label, size_kb)
            else:
                self.after(0, self._update_estimated_size_label, -1)

        except (IndexError, ValueError):
            self.after(0, self._update_estimated_size_label, -1)
        except Exception as e:
            log_error(f"Estimation Thread Error: {e}", exc_info=True)
            self.after(0, self._update_estimated_size_label, -1)
        finally:
            for f in temp_files:
                try: os.remove(f)
                except OSError: pass

    def _update_estimated_size_label(self, size_kb: float) -> None:
        self.est_lbl.config(text=f"~{size_kb:.1f} KB" if size_kb >= 0 else "Error")
        self.status_lbl.config(text=STRINGS["status_ready"])

    # ==================================================================
    # Compression
    # ==================================================================
    def _start_compression(self) -> None:
        if not self.files:
            self._custom_messagebox("No Files", "Please add files to process.", color="#dc2626")
            return

        suffix = self.suffix_var.get()
        if not self.overwrite_var.get() and not _validate_suffix(suffix):
            self._custom_messagebox(STRINGS["error_title"], STRINGS["invalid_suffix"], color="#dc2626")
            return

        try:
            quality = self.quality_var.get()
            if not 1 <= quality <= 100: raise ValueError
        except (ValueError, tk.TclError):
            self._custom_messagebox(STRINGS["error_title"], STRINGS["quality_out_of_range"], color="#dc2626")
            return
            
        try: w = int(self.width_var.get())
        except ValueError: w = 0
        try: h = int(self.height_var.get())
        except ValueError: h = 0

        options = {
            "resize_enabled": self.show_resize.get(),
            "width": w,
            "height": h,
            "keep_aspect_ratio": self.keep_aspect_ratio.get(),
            "fit_to_box": self.fit_to_box.get(),
            "do_not_enlarge": self.do_not_enlarge.get(),
            "mode": "quality" if self.comp_mode_str.get() == STRINGS["mode_quality"] else "size",
            "quality": _clamp_quality(quality),
            "target_size": self.size_var.get(),
            "output_dir": self.output_dir_var.get(),
            "suffix": suffix,
            "format": self.format_var.get(),
            "overwrite": self.overwrite_var.get(),
            "max_png": self.max_png_var.get(),
            "auto_convert_png": self.auto_convert_png_var.get() and not self.max_png_var.get(),
        }

        self._cancel_event.clear()
        self.processor.cancel_event = self._cancel_event
        if ctk is not None:
            self.compress_button.configure(state="disabled")
            self.cancel_button.configure(state="normal")

        self.progress_bar.pack(fill=tk.X, pady=(0, 15))
        self.progress_percent.place(relx=0.5, rely=0.1, anchor="n")
        self.progress_var.set(0)
        self.progress_bar.set(0)

        self._compression_thread = threading.Thread(target=self._run_compression, args=(options,), daemon=True)
        self._compression_thread.start()

    def _run_compression(self, options: dict) -> None:
        success_msgs, error_msgs = [], []
        success_files = set()
        total = len(self.files)
        start_time = time.time()
        
        remaining_files = list(self.files)
        save_crash_state(remaining_files)

        for i, file_path in enumerate(self.files):
            if self._cancel_event.is_set():
                self.after(0, self._compression_finished, success_msgs, error_msgs, success_files, True)
                return

            progress = (i / total) if total > 0 else 0
            seconds = int((time.time() - start_time) / i * (total - i)) if i > 0 else 0
            
            if CURRENT_LANGUAGE == "fa":
                eta = f"زمان باقیمانده: {seconds} ثانیه" if i > 0 else ""
            else:
                eta = f"ETA: {seconds}s" if i > 0 else ""
            
            percent = int(progress * 100)
            self.after(0, self._update_progress, progress, f"{percent}% ({i}/{total})", STRINGS["status_processing"].format(current=i + 1, total=total, filename=os.path.basename(file_path)), eta)
            
            is_success, msg = self.processor.process_file(file_path, options)
            if is_success: 
                success_msgs.append(msg)
                success_files.add(file_path)
            else: 
                error_msgs.append(msg)
                
            if file_path in remaining_files:
                remaining_files.remove(file_path)
                save_crash_state(remaining_files)

        self.after(0, self._compression_finished, success_msgs, error_msgs, success_files, False)

    def _update_progress(self, fraction: float, percent_str: str, text: str, eta: str) -> None:
        self.progress_var.set(fraction)
        self.progress_bar.set(fraction)
        self.progress_percent.configure(text=percent_str)
        self.status_lbl.config(text=text)
        self.eta_lbl.config(text=eta)

    def _compression_finished(self, success_msgs: list[str], error_msgs: list[str], success_files: set, was_cancelled: bool) -> None:
        clear_crash_state()
        self.progress_var.set(1.0 if not was_cancelled else 0)
        if ctk is not None:
            self.progress_bar.set(1.0 if not was_cancelled else 0)
            self.compress_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            self.progress_bar.pack_forget()
            self.progress_percent.place_forget()

        if was_cancelled:
            self.status_lbl.config(text=STRINGS["status_cancelled"])
            self.eta_lbl.config(text="")
            return

        self.status_lbl.config(text=STRINGS["status_done"])
        self.eta_lbl.config(text="")

        report = ""
        if success_msgs: report += f"✅ Successfully processed {len(success_msgs)} file(s):\n" + "\n".join(f"  • {m}" for m in success_msgs)
        if error_msgs: report += f"\n\n❌ Encountered {len(error_msgs)} error(s):\n" + "\n".join(f"  • {m}" for m in error_msgs)

        if error_msgs or success_msgs:
            retry_cb = None
            if error_msgs:
                def do_retry():
                    # Remove successful files from list backwards
                    for idx in range(len(self.files)-1, -1, -1):
                        if self.files[idx] in success_files:
                            self.file_listbox.delete(idx)
                            del self.files[idx]
                    self.count_lbl.config(text=STRINGS["files_found"].format(count=len(self.files)))
                    self._clear_preview()
                retry_cb = do_retry
            self._custom_report(STRINGS["report_title"], report, retry_callback=retry_cb)

    def _cancel_compression(self) -> None:
        self._cancel_event.set()
        self.status_lbl.config(text="Cancelling...")

    def _safe_update_status(self, message: str) -> None:
        self.after(0, self._do_update_status, message)

    def _do_update_status(self, message: str) -> None:
        self.status_lbl.config(text=message)

    def update_status(self, message: str) -> None:
        self.status_lbl.config(text=message)
        self.update_idletasks()
