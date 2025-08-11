from pyile.lib.ui.gui.styles import get_sidebar_button_config, get_label_config, get_checkbox_config, get_status_colors
from pyile.lib.runtime.internal.constants import PADDING_SMALL, PADDING_LARGE, SECTIONS_FG_COLOR, FONT_SIZE_NORMAL, FONT_SIZE_LARGE

from typing import Callable
import customtkinter
from customtkinter import CTkFrame, CTkScrollableFrame

Frame = CTkFrame | CTkScrollableFrame

def create_sidebar_button(
    parent: customtkinter.CTkFrame,
    text: str,
    command: Callable,
    row: int,
    **kwargs
) -> customtkinter.CTkButton:
    config = get_sidebar_button_config()
    config.update(kwargs)
    
    button = customtkinter.CTkButton(
        parent,
        text=text,
        command=command,
        **config
    )
    button.grid(row=row, column=0, padx=12, pady=(4, 4), sticky="ew")
    return button

def create_section_label(
    parent: Frame,
    text: str,
    row: int,
    font_size: int = FONT_SIZE_NORMAL,
    bold: bool = True
) -> customtkinter.CTkLabel:
    config = get_label_config(font_size=font_size, bold=bold)
    
    label = customtkinter.CTkLabel(
        parent,
        text=text,
        **config
    )
    label.grid(row=row, column=0, padx=12, pady=(PADDING_LARGE, PADDING_SMALL), sticky="w")
    return label

def create_status_indicator(
    parent: customtkinter.CTkFrame,
    row: int
) -> customtkinter.CTkLabel:
    indicator = customtkinter.CTkLabel(
        parent,
        text="●",
        font=("Inter", 16, "bold"),
        text_color=get_status_colors()["idle"]
    )
    indicator.grid(row=row, column=0, padx=(0, 14), pady=(PADDING_LARGE, PADDING_SMALL), sticky="e")
    return indicator

def create_settings_frame(
    parent: Frame,
    title: str,
    row: int
) -> tuple[customtkinter.CTkFrame, customtkinter.CTkLabel]:
    frame = customtkinter.CTkFrame(parent, fg_color=SECTIONS_FG_COLOR, corner_radius=6)
    frame.grid(row=row, column=0, padx=10, pady=10, sticky="ew")
    frame.grid_columnconfigure(0, weight=1)
    
    title_label = customtkinter.CTkLabel(
        frame,
        text=title,
        **get_label_config(font_size=FONT_SIZE_LARGE, bold=True)
    )
    title_label.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
    return frame, title_label

def create_checkbox(
    parent: customtkinter.CTkFrame,
    text: str,
    command: Callable,
    row: int
) -> customtkinter.CTkCheckBox:
    config = get_checkbox_config()
    
    checkbox = customtkinter.CTkCheckBox(
        parent,
        text=text,
        command=command,
        **config
    )
    checkbox.grid(row=row, column=0, pady=(4, 8), padx=12, sticky="w")
    return checkbox

def update_status_indicator(
    indicator: customtkinter.CTkLabel,
    is_active: bool,
    is_stopping: bool = False
) -> None:
    colors = get_status_colors()
    
    if is_stopping:
        indicator.configure(text="●", text_color=colors['stopping'])
    elif is_active:
        indicator.configure(text="●", text_color=colors['starting'])
    else:
        indicator.configure(text="●", text_color=colors['idle'])

def setup_grid_configuration(parent: customtkinter.CTkFrame, rows: int, columns: int) -> None:
    for i in range(rows):
        parent.grid_rowconfigure(i, weight=1)
    for i in range(columns):
        parent.grid_columnconfigure(i, weight=1)

