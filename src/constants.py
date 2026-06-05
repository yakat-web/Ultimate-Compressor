"""
Central constants for the Ultimate Image Compressor.

All configuration values, string resources, and supported formats
are defined here for easy maintenance and localization.
"""

try:
    from .utils import load_config, save_config
except ImportError:
    from utils import load_config, save_config

# Load config
_config = load_config()

# --- Version (single source of truth — fixes Issue #24) ---
VERSION: str = "2.0.1"

# --- Supported file extensions ---
SUPPORTED_IMAGE_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".ico",
}

FILETYPES_FILTER: list[tuple[str, str]] = [
    ("Image Files", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif"),
    ("JPEG Files", "*.jpg *.jpeg"),
    ("PNG Files", "*.png"),
    ("WebP Files", "*.webp"),
    ("BMP Files", "*.bmp"),
    ("TIFF Files", "*.tiff *.tif"),
    ("All Files", "*.*"),
]

# --- ICO sizes (fixes Issue #27 — added 16×16, 128×128, 256×256) ---
ICO_SIZES: list[tuple[int, int]] = [
    (16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256),
]

# --- Output format options ---
OUTPUT_FORMATS: list[str] = ["Keep Original", "JPEG", "PNG", "WEBP", "ICO"]

# --- Multi-language Strings (i18n) ---
CURRENT_LANGUAGE = _config.get("language", "fa")

STRINGS_DICT = {
    "en": {
        # Application
        "app_title": "Ultimate Image Compressor",
        "app_version": VERSION,

        # Status messages
        "status_ready": "Ready",
        "status_processing": "Processing file {current}/{total}: {filename}",
        "status_done": "Operation complete.",
        "status_estimating": "Estimating size...",
        "status_resized": "Resized to {w}×{h}",
        "status_finding_quality": "Finding best quality for < {size} KB...",
        "status_estimated_size": "Estimated size: ~{size:.1f} KB",
        "status_already_optimized": "Already Optimized",
        "status_cancelled": "Operation cancelled by user.",
        "status_normalizing": "Normalizing image for compatibility...",

        # Titles
        "error_title": "Error",
        "success_title": "Success",
        "report_title": "Compression Report",

        # Error messages
        "unsupported_type": "Unsupported file type",
        "overwrite_format_error": "Cannot overwrite file when changing its format.",
        "quality_out_of_range": "Quality must be between 1 and 100.",
        "invalid_suffix": "Suffix must contain only English letters, numbers, hyphens, and underscores.",

        # Section labels
        "resize_label": "Resize",
        "width_label": "Width:",
        "height_label": "Height:",
        "original_dims_label": "Original:",
        "aspect_ratio_label": "Keep Aspect Ratio",
        "fit_to_label": "Fit to Bounding Box",
        "do_not_enlarge_label": "Do not enlarge",
        "compression_label": "Compression Settings",
        "mode_quality": "Target Quality",
        "mode_size": "Target File Size (JPEG/WEBP only)",
        "quality_label": "Quality (1-100):",
        "size_label": "Target Size (KB):",
        "output_options_label": "Output Options",
        "output_dir_label": "Save to:",
        "suffix_label": "Filename Suffix:",
        "output_format_label": "Convert Format:",
        "overwrite_label": "Overwrite original file",
        "keep_original_format": "Keep Original",
        "original_folder": "Original Folder",

        # Buttons
        "compress_button": "⚡ Compress Files",
        "cancel_button": "Cancel",
        "browse_button": "Browse",
        "add_files_button": "Add Files",
        "add_folder_button": "Add Folder",
        "remove_button": "Remove Selected",
        "clear_button": "Clear All",

        # File list
        "files_label": "Files to Process",
        "no_file_selected": "Please select a file from the list.",
        "include_subfolders": "Include subfolders",
        "files_found": "{count} image(s) found",

        # Headless mode
        "headless_success": "{count} file(s) processed successfully.",

        # Compression options
        "max_png_label": "Max PNG Compression (Slow)",
        "auto_convert_png_label": "Auto-convert opaque PNG to JPG",

        # Preview
        "preview_label": "Preview",
        "file_info_format": "{width}×{height} px  |  {size}  |  {format}",

        # Sidebar & Updates
        "settings_sidebar": "Settings",
        "language_label": "Language",
        "theme_label": "Theme",
        "theme_system": "System",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "check_updates": "Check for Updates",
        "no_updates": "You are running the latest version.",
        "update_available": "A new version ({new_ver}) is available. Do you want to download it?",

        # Menu Bar
        "menu_file": "File",
        "menu_options": "Options",
        "menu_help": "Help",
        "exit_button": "Exit",
        "quality_settings": "Quality Settings",
    },
    "fa": {
        # Application
        "app_title": "نرم‌افزار فشرده‌ساز تصاویر",
        "app_version": VERSION,

        # Status messages
        "status_ready": "آماده به کار",
        "status_processing": "‏در حال پردازش {current}/{total}: ‪{filename}‬",
        "status_saving": "در حال ذخیره: {filename}...",
        "status_optimizing": "در حال بهینه‌سازی {filename}...",
        "status_done": "عملیات با موفقیت پایان یافت.",
        "status_estimating": "تخمین حجم...",
        "status_resized": "تغییر سایز به {w}×{h}",
        "status_finding_quality": "یافتن کیفیت برای < {size} کیلوبایت...",
        "status_estimated_size": "حجم تخمینی: ~{size:.1f} KB",
        "status_already_optimized": "از قبل بهینه‌تر است",
        "status_cancelled": "عملیات توسط کاربر لغو شد.",
        "status_normalizing": "آماده‌سازی تصویر برای فرمت هدف...",

        # Titles
        "error_title": "خطا",
        "success_title": "موفقیت",
        "report_title": "گزارش فشرده‌سازی",

        # Error messages
        "unsupported_type": "فرمت فایل پشتیبانی نمی‌شود",
        "overwrite_format_error": "هنگام تغییر فرمت نمی‌توانید روی فایل اصلی ذخیره کنید.",
        "quality_out_of_range": "کیفیت باید بین ۱ تا ۱۰۰ باشد.",
        "invalid_suffix": "پسوند فقط می‌تواند شامل حروف، اعداد، خط تیره و زیرخط باشد.",

        # Section labels
        "resize_label": "تغییر سایز",
        "width_label": "عرض:",
        "height_label": "ارتفاع:",
        "original_dims_label": "اصلی:",
        "aspect_ratio_label": "حفظ تناسب ابعاد",
        "fit_to_label": "تناسب با باکس",
        "do_not_enlarge_label": "بزرگتر از سایز اصلی نشود",
        "compression_label": "تنظیمات فشرده‌سازی",
        "mode_quality": "کیفیت نهایی",
        "mode_size": "حجم نهایی \u202B(JPEG/WEBP)\u202C",
        "quality_label": "کیفیت (۱-۱۰۰):",
        "size_label": "حجم نهایی (KB):",
        "output_options_label": "تنظیمات خروجی",
        "output_dir_label": "مسیر ذخیره:",
        "suffix_label": "پسوند فایل:",
        "output_format_label": "فرمت خروجی:",
        "overwrite_label": "جایگزینی فایل اصلی",
        "keep_original_format": "فرمت اصلی",
        "original_folder": "پوشه اصلی",

        # Buttons
        "compress_button": "⚡ شروع فشرده‌سازی",
        "cancel_button": "لغو",
        "browse_button": "مرور",
        "add_files_button": "افزودن فایل",
        "add_folder_button": "افزودن پوشه",
        "remove_button": "حذف انتخاب‌شده",
        "clear_button": "پاک کردن همه",

        # File list
        "files_label": "لیست تصاویر",
        "no_file_selected": "لطفاً یک فایل از لیست انتخاب کنید.",
        "include_subfolders": "شامل زیرپوشه‌ها",
        "files_found": "\u202B{count} تصویر یافت شد\u202C",

        # Headless mode
        "headless_success": "{count} فایل با موفقیت پردازش شد.",

        # Compression options
        "max_png_label": "فشرده‌سازی حداکثری (کند)",
        "auto_convert_png_label": "\u202Bتبدیل خودکار \u200FPNG\u200F به \u200FJPG\u200F\u202C",

        # Preview
        "preview_label": "پیش‌نمایش",
        "file_info_format": "\u202B\u200F{format}\u200F  |  \u200F{width}×{height} پیکسل\u200F  |  \u200F{size}\u200F\u202C",

        # Sidebar & Updates
        "settings_sidebar": "تنظیمات",
        "language_label": "زبان",
        "theme_label": "پوسته",
        "theme_system": "سیستم",
        "theme_light": "روشن",
        "theme_dark": "تاریک",
        "check_updates": "بررسی آپدیت‌ها",
        "no_updates": "شما از آخرین نسخه استفاده می‌کنید.",
        "update_available": "نسخه جدید ({new_ver}) در دسترس است. آیا مایل به دانلود آن هستید؟",

        # Menu Bar
        "menu_file": "فایل",
        "menu_options": "تنظیمات",
        "menu_help": "راهنما",
        "exit_button": "خروج",
        "quality_settings": "تنظیمات کیفیت",
    }
}

# Proxy object for backward compatibility
class _StringsProxy:
    def __getitem__(self, key: str) -> str:
        return STRINGS_DICT[CURRENT_LANGUAGE].get(key, STRINGS_DICT["en"].get(key, key))
    
    def get(self, key: str, default: str = "") -> str:
        return STRINGS_DICT[CURRENT_LANGUAGE].get(key, STRINGS_DICT["en"].get(key, default))

STRINGS = _StringsProxy()

def set_language(lang_code: str) -> None:
    global CURRENT_LANGUAGE
    if lang_code in STRINGS_DICT:
        CURRENT_LANGUAGE = lang_code
        c = load_config()
        c["language"] = lang_code
        save_config(c)
