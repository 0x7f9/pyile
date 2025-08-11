from pyile.lib.utils.config import UserConfig
from pyile.lib.utils.common import get_project_root
from pyile.lib.ui.gui.utils import (
    create_sidebar_button, create_section_label, create_status_indicator,
    create_settings_frame, create_checkbox, update_status_indicator
)
from pyile.lib.ui.gui.styles import get_console_config, setup_appearance, load_custom_font
from pyile.lib.ui.gui.handlers import GUIHandlers
from pyile.lib.runtime.internal.constants import (
    FONT_SIZE_LARGE, TITLE, MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT, 
    SIDEBAR_WIDTH, IDLE_COLOR, SECTIONS_FG_COLOR
)
from pyile.lib.utils.logging import start_log_thread, log_console
from pyile.lib.utils.common import setup_dpi, file_exists, join_path
from pyile.lib.ui.gui.state.dir_state import DirState

from typing import Any, List
import customtkinter
import threading

setup_dpi()
setup_appearance()

font_path = join_path(get_project_root(levels_up=2), "assets", "fonts", "JetBrainsMono-Regular.ttf")
if file_exists(font_path):
    load_custom_font(font_path)

class Interface(customtkinter.CTk):
    def __init__(self) -> None:
        super().__init__()
        # self.overrideredirect(True)

        from pyile.lib.runtime.cache_manager.cache import SlabCache
        from pyile.lib.runtime.internal.thread_safe import SafeThread
        SafeThread.spawn(
            target_fn=lambda: SlabCache.get().load()
        )

        self.icon = None
        self.icon_thread_key = "icon_thread"
        self.tray_icon_thread = False
        
        # self.icon_moon = None
        # self.icon_sun = None
        # self.load_custom_assets()
        
        self.monitor_states = {}  
        self.monitor_lock = threading.Lock()    
        self.monitoring_active = False
        self.checkbox_states = {
            1: False,
            2: False,
            3: False,
            4: False,
            5: False,
            6: False,
            7: False,
            8: False,
            9: False,
        }

        self.save_dirs_for_next_session = False
        self.check_current_files = False
        self.minimise_to_tray = False
        self.notification_enabled = False
        self.notification_sound_enabled = False
        self.exclude_system_extensions = False
        self.exclude_temp_extensions = False
        self.auto_scroll_console = False
        self.delete_logs_on_exit = False

        self.PATHS = []
        self.EXCLUDE = []
        
        start_log_thread()

        self.title(TITLE)
        self.geometry(f"{MAIN_WINDOW_WIDTH}x{MAIN_WINDOW_HEIGHT}")

        icon_path = join_path(get_project_root(levels_up=2), "assets", "images", "icon.ico")
        self.iconbitmap(icon_path)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = customtkinter.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 1))
        self.sidebar_frame.grid_rowconfigure(12, weight=1)
        self.sidebar_frame.grid_columnconfigure(0, weight=0)

        # self.tabview = customtkinter.CTkTabview(self, width=TABVIEW_WIDTH)
        self.tabview = customtkinter.CTkTabview(
            self,
            corner_radius=8,
            segmented_button_selected_color=("#1E293B", "#E5E7EB"),
            segmented_button_selected_hover_color=("#334155", "#D1D5DB"),
            segmented_button_unselected_hover_color=("#2E2E32", "#E5E7EB"),
            text_color=("#F9FAFB", "#111827")
        )

        self.tabview.grid(row=0, column=1, padx=(3, 3), pady=(6, 3), sticky="nsew")
        self.tabview.add("console")
        self.tabview.add("Settings")
        self.tabview.tab("console").grid_rowconfigure(0, weight=1)
        self.tabview.tab("console").grid_columnconfigure(0, weight=1)
        self.tabview.tab("Settings").grid_rowconfigure(0, weight=1)
        self.tabview.tab("Settings").grid_columnconfigure(0, weight=1)
        self.tabview.tab("Settings").grid_columnconfigure(1, weight=1)
        self.tabview.tab("Settings").grid_propagate(False)

        self.console = customtkinter.CTkTextbox(
            self.tabview.tab("console"),
            **get_console_config()
        )
        self.console.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        self.monitoring_label = create_section_label(self.sidebar_frame, "MONITORING", row=0, bold=True)
        self.status_indicator = create_status_indicator(self.sidebar_frame, row=0)

        self.sidebar_button_1 = create_sidebar_button(
            self.sidebar_frame, "Start monitoring", self.toggle_monitoring, row=1
        )
        self.sidebar_button_2 = create_sidebar_button(
            self.sidebar_frame, "Add directory", self.get_save_directory, row=2
        )
        self.sidebar_button_3 = create_sidebar_button(
            self.sidebar_frame, "Exclude directory", self.get_exclude_directory, row=3
        )
        self.sidebar_button_4 = create_sidebar_button(
            self.sidebar_frame, "Back up", self.back_up, row=4
        )
        self.sidebar_button_5 = create_sidebar_button(
            self.sidebar_frame, "Backup location", self.set_backup_folder, row=5
        )
        self.tools_label = create_section_label(self.sidebar_frame, "MISC", row=7, bold=True)
        self.sidebar_button_6 = create_sidebar_button(
            self.sidebar_frame, "Clear log", lambda: self.console.delete("1.0", "end"), row=8
        )
        self.sidebar_button_7 = create_sidebar_button(
            self.sidebar_frame, "Copy log", self.copy_console_content, row=9
        )
        self.sidebar_button_8 = create_sidebar_button(
            self.sidebar_frame, "Open log folder", self.open_log_folder, row=10
        )
        self.sidebar_button_9 = create_sidebar_button(
            self.sidebar_frame, "Set log folder", self.set_log_folder, row=11,
        )
        self.appearance_switch = customtkinter.CTkSwitch(
            self.sidebar_frame,
            text="Light Mode",
            command=self.toggle_appearance,
            font=("Inter", 10),
            switch_width=35,       
            switch_height=15,      
            corner_radius=11,       
            progress_color=("#1B1B1D", "#1B1B1D"),  
            button_color=("white", "white"), 
            button_hover_color=("#E5E7EB", "#E5E7EB") 
        )
        self.appearance_switch.grid(row=14, column=0, padx=8, pady=3, sticky="w")
        # self.appearance_icon = customtkinter.CTkLabel(
        #     self.sidebar_frame, 
        #     image=self.icon_moon,
        #     text=""
        # )
        # self.appearance_icon.grid(row=14, column=0, padx=45, pady=5, sticky="w")

        current_mode = customtkinter.get_appearance_mode()
        self.appearance_switch.select() if current_mode == "Dark" else self.appearance_switch.deselect()
        # self.appearance_icon.configure(image=self.icon_moon if current_mode == "Dark" else self.icon_sun)

        self.settings_scrollable_frame = customtkinter.CTkScrollableFrame(
            self.tabview.tab("Settings"),
            corner_radius=0
        )
        self.settings_scrollable_frame.grid(row=0, column=0, padx=(8, 5), pady=0, sticky="nsew")
        self.settings_scrollable_frame.grid_columnconfigure(0, weight=1)
        self.settings_scrollable_frame.grid_rowconfigure(0, weight=1)

        if hasattr(self.settings_scrollable_frame, "_scrollbar"):
            self.settings_scrollable_frame._scrollbar.configure(
                button_color=("#3A3A3A", "#D4D4D4"),
                button_hover_color=("#555555", "#A3A3A3"),
                width=10
            )
        self.settings_scrollable_frame._parent_canvas.bind(
            "<Configure>", self.schedule_scrollbar_update, add="+"
        )
            
        self.settings_title = create_section_label(self.settings_scrollable_frame, "Settings", row=0, font_size=FONT_SIZE_LARGE, bold=True)
        self.session_frame, _ = create_settings_frame(self.settings_scrollable_frame, "Session", row=1)
        self.checkbox_1 = create_checkbox(
            self.session_frame, "Save directories for next logging session", lambda: self.checkbox_checked(1), row=1
        )
        self.file_filtering_frame, _ = create_settings_frame(self.settings_scrollable_frame, "File Filtering", row=2)
        self.checkbox_2 = create_checkbox(
            self.file_filtering_frame, "Exclude system extensions (.cpl, .fon, .icl, etc)", lambda: self.checkbox_checked(2), row=1
        )
        self.checkbox_7 = create_checkbox(
            self.file_filtering_frame, "Exclude temp extensions (.lock, .tmp, .dmp, etc)", lambda: self.checkbox_checked(7), row=2
        )
        self.file_frame, _ = create_settings_frame(self.settings_scrollable_frame, "File Handling", row=3)
        self.checkbox_3 = create_checkbox(
            self.file_frame, "Check current files for duplicates before logging", lambda: self.checkbox_checked(3), row=1
        )
        self.system_frame, _ = create_settings_frame(self.settings_scrollable_frame, "System", row=4)
        self.checkbox_4 = create_checkbox(
            self.system_frame, "Minimise to tray on exit", lambda: self.checkbox_checked(4), row=1
        )
        self.checkbox_5 = create_checkbox(
            self.system_frame, "Enable notifications", lambda: self.checkbox_checked(5), row=2
        )
        self.checkbox_6 = create_checkbox(
            self.system_frame, "Enable notification sound", lambda: self.checkbox_checked(6), row=3
        )
        
        self.security_frame, _ = create_settings_frame(self.settings_scrollable_frame, "Security", row=5)
        self.checkbox_8 = create_checkbox(
            self.security_frame, "Delete all logs on exit", lambda: self.checkbox_checked(8), row=1
        )
        
        self.interface_frame, _ = create_settings_frame(self.settings_scrollable_frame, "Interface", row=6)
        self.checkbox_9 = create_checkbox(
            self.interface_frame, "Auto-scroll console", lambda: self.checkbox_checked(9), row=1
        )

        self.stats_frame = customtkinter.CTkFrame(self.tabview.tab("Settings"))
        self.stats_frame.grid(row=0, column=1, padx=(8, 5), pady=0, sticky="nsew")
        self.stats_frame.grid_columnconfigure(0, weight=1)

        self.stats_title = create_section_label(self.stats_frame, "Statistics", row=0, font_size=FONT_SIZE_LARGE, bold=True)
        self.stats_content_frame = customtkinter.CTkFrame(self.stats_frame, fg_color=SECTIONS_FG_COLOR, corner_radius=8)
        self.stats_content_frame.grid(row=1, column=0, padx=8, pady=5, sticky="ew")
        self.heading_label = customtkinter.CTkLabel(
            self.stats_content_frame, text="0 Files are the same", font=("Inter", 12)
        )
        self.heading_label.grid(row=1, column=0, padx=10, pady=3, sticky="w")
        self.heading_label_2 = customtkinter.CTkLabel(
            self.stats_content_frame, text="0 Files checked in session", font=("Inter", 12)
        )
        self.heading_label_2.grid(row=2, column=0, padx=10, pady=3, sticky="w")
        self.heading_label_3 = customtkinter.CTkLabel(
            self.stats_content_frame, text="Last file checked - No files checked", font=("Inter", 12)
        )
        self.heading_label_3.grid(row=3, column=0, padx=10, pady=3, sticky="w")
        self.progress_label = customtkinter.CTkLabel(
            self.stats_content_frame, text="Status: Idle", font=("Inter", 10), text_color=IDLE_COLOR
        )
        self.progress_label.grid(row=4, column=0, padx=10, pady=(8, 3), sticky="w")

        self.get_config = UserConfig.get(log_console=self.log_to_console)
        self.get_config
        self.handlers = GUIHandlers(self)

        self.handlers.get_checkbox_states()
        self.protocol("WM_DELETE_WINDOW", self.handlers.on_window_close)
        common_config = self.get_config.load_common_config()
        self.custom_log_path = common_config.get("log_folder_path")
        self.custom_backup_path = common_config.get("backup_folder_path")
        self.get_config.load_directories_config()
        self.get_config.load_excluded_directories_config()

        from pyile.lib.runtime.cache_manager.cache import get_cache_stats
        stats = get_cache_stats()
        self.log_to_console(f"Application Cache entries: {stats['slab_entries']}")
        self.log_to_console(f"Cache Path: {stats['slab_path']}")

    # def load_custom_assets(self):
    #     from PIL import Image
    #     import customtkinter

    #     self.icon_sun = customtkinter.CTkImage(
    #         light_image=Image.open("pyile/assets/sun.png").resize((18, 18)),
    #         dark_image=Image.open("pyile/assets/sun.png").resize((18, 18)),
    #     )
    #     self.icon_moon = customtkinter.CTkImage(
    #         light_image=Image.open("pyile/assets/moon.png").resize((18, 18)),
    #         dark_image=Image.open("pyile/assets/moon.png").resize((18, 18)),
    #     )

    def get_monitor_states(self) -> List[DirState]:
        with self.monitor_lock:
            return [state for state in self.monitor_states.values() if state.is_active]

    def copy_console_content(self) -> None:
        self.handlers.copy_console_content()

    def open_log_folder(self) -> None:
        self.handlers.open_log_folder()

    def set_folder(self, attr_name: str, label: str) -> None:
        self.handlers.set_folder(attr_name, label)

    def set_log_folder(self) -> None:
        self.handlers.set_log_folder()

    def set_backup_folder(self) -> None:
        self.handlers.set_backup_folder()

    def update_status_indicator(self, is_active: bool, is_stopping: bool = False) -> None:
        update_status_indicator(self.status_indicator, is_active, is_stopping)

    def toggle_appearance(self) -> None:
        self.handlers.toggle_appearance()

    def start_icon_thread(self) -> None:
        self.handlers.start_icon_thread()

    def stop_icon_thread(self) -> None:
        self.handlers.stop_icon_thread()

    def exit_application(self) -> None:
        self.handlers.exit_application()

    def icon_clicked(self, none: Any, item: Any) -> None:
        self.handlers.icon_clicked(none, item)

    def hide_window(self) -> None:
        self.handlers.hide_window()

    def back_up(self) -> None:
        self.handlers.back_up()

    def toggle_monitoring(self) -> None:
        self.handlers.toggle_monitoring()

    def get_save_directory(self) -> None:
        self.handlers.get_save_directory()

    def get_exclude_directory(self) -> None:
        self.handlers.get_exclude_directory()

    def checkbox_checked(self, checkbox: int) -> None:
        self.handlers.checkbox_checked(checkbox)

    def log_to_console(self, msg: str) -> None:
        log_console(self.console, msg, self.auto_scroll_console)

    def update_scrollbar_visibility(self):
        canvas = self.settings_scrollable_frame._parent_canvas
        vbar = self.settings_scrollable_frame._scrollbar

        if canvas.winfo_height() >= canvas.bbox("all")[3]:
            vbar.grid_remove()
        else:
            vbar.grid()

    def schedule_scrollbar_update(self, event=None):
        self.after_idle(self.update_scrollbar_visibility)
