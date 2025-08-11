from pyile.lib.runtime.internal.constants import (
    FOREGROUND_COLOR, CONSOLE_COLOR, STARTING_COLOR, STOPPING_COLOR,
    BUTTON_WIDTH, BUTTON_HEIGHT, BUTTON_CORNER_RADIUS, CONSOLE_FG_COLOR,
    FONT_SIZE_SMALL, FONT_SIZE_NORMAL, TEXT_COLOR, HOVER_COLOR, 
    ACCENT_COLOR, IDLE_COLOR, 
)

def load_custom_font(font_path: str) -> None:
    try:
        import ctypes
        from pyile.lib.runtime.internal.constants import FR_PRIVATE
        ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
    except Exception:
        pass 

def setup_appearance() -> None:
    import customtkinter
    customtkinter.set_appearance_mode("dark")
    customtkinter.set_default_color_theme("dark-blue")

def get_sidebar_button_config() -> dict:
    return {
        "width": BUTTON_WIDTH,
        "height": BUTTON_HEIGHT,
        "font": ("Inter", FONT_SIZE_NORMAL, "bold"),
        "corner_radius": BUTTON_CORNER_RADIUS,
        "fg_color": FOREGROUND_COLOR,
        "hover_color": HOVER_COLOR,
        "text_color": TEXT_COLOR
    }

def get_label_config(font_size: int = FONT_SIZE_NORMAL, bold: bool = False) -> dict:
    font_weight = "bold" if bold else "normal"
    return {
        "font": ("Inter", font_size, font_weight),
        "text_color": TEXT_COLOR
    }

def get_frame_config() -> dict:
    return {
        "fg_color": "transparent",
        "corner_radius": 0
    }

def get_console_config() -> dict:
    return {
        "fg_color": CONSOLE_FG_COLOR,
        "text_color": CONSOLE_COLOR,
        "font": ("JetBrains Mono", FONT_SIZE_SMALL),
        "wrap": "word"
    }

def get_checkbox_config() -> dict:
    return {
        "font": ("Inter", FONT_SIZE_NORMAL),
        "checkbox_width": 14,
        "checkbox_height": 14,
        "corner_radius": 3,
        "fg_color": FOREGROUND_COLOR,
        "hover_color": HOVER_COLOR,
        "text_color": TEXT_COLOR,
        "border_color": "#6B7280",
        "border_width": 1.5,
        "checkmark_color": ACCENT_COLOR
    }

def get_switch_config() -> dict:
    return {
        "font": ("Inter", FONT_SIZE_NORMAL)
    }

def get_status_colors() -> dict:
    return {
        "starting": STARTING_COLOR,
        "stopping": STOPPING_COLOR,
        "idle": IDLE_COLOR
    }
    
