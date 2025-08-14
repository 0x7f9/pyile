from pyile.lib.utils.common import (
    get_project_root, ensure_dir_exists, file_exists, 
    is_directory, is_gui_env, join_path, get_norm_path
)
from pyile.lib.utils.logging import log_error, log_debug, log_warning, stop_log_thread, log_info
from pyile.lib.utils.config import flush_config_q
from pyile.lib.runtime.lifecycle import start_thread_if_needed, shutdown_thread, _thread_state
from pyile.lib.ui.notifier import NotificationManager
from pyile.lib.runtime.monitors.backup_monitor import BackupMonitor
from pyile.lib.runtime.monitors.file_monitor import Monitor
from pyile.lib.utils.os_version import is_windows_11
from pyile.lib.runtime.internal.constants import STARTING_COLOR, STOPPING_COLOR, POLL_INTERVAL
from pyile.lib.ui.gui.state.dir_state import DirState

import os
import subprocess
import threading
import time
from typing import Optional, Any
from tkinter import filedialog
import customtkinter
from pathlib import Path

class GUIHandlers:
    __slots__ = ("gui")
    
    def __init__(self, gui_instance: Any) -> None:
        self.gui = gui_instance

    def on_window_close(self):
        if self.gui.minimise_to_tray:
            self.gui.hide_window()
        else:
            self.gui.exit_application()

    def copy_console_content(self) -> None:
        try:
            content = self.gui.console.get("1.0", "end-1c")
            self.gui.clipboard_clear()
            self.gui.clipboard_append(content)
            self.gui.log_to_console("Console content copied to clipboard")
        except Exception as e:
            log_error(f"Failed to copy content: {e}")

    def open_log_folder(self) -> None:
        try:
            if self.gui.custom_log_path:
                logs_dir = self.gui.custom_log_path
            else:
                logs_dir = join_path(get_project_root(levels_up=2), "logs")
            
            if not file_exists(logs_dir):
                ensure_dir_exists(logs_dir)
            
            subprocess.Popen(
                ["explorer", logs_dir], 
                shell=False, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
                
            self.gui.log_to_console(f"Opened logs folder: {logs_dir}")
            
        except Exception as e:
            log_error(f"Failed to open logs folder {e}")

    def set_folder(self, attr_name: str, label: str) -> None:
        try:
            folder_path = self._prompt()
            if not folder_path:
                return

            if file_exists(folder_path) and is_directory(folder_path):
                setattr(self.gui, attr_name, folder_path)
                self.gui.get_config.save_common_config(
                    log_folder_path=self.gui.custom_log_path, 
                    backup_folder_path=self.gui.custom_backup_path
                )
                self.gui.log_to_console(f"{label} folder set to: {folder_path}")
            else:
                self.gui.log_to_console(f"[ERROR] Invalid {label} folder path: {folder_path}")

        except Exception as e:
            log_error(f"Failed to set {label} folder: {e}")
            self.gui.log_to_console(f"[ERROR] Failed to set {label} folder: {e}")

    def set_log_folder(self) -> None:
        self.set_folder("custom_log_path", "Log")

    def set_backup_folder(self) -> None:
        self.set_folder("custom_backup_path", "Backup")

    # def toggle_appearance(self):
    #     if self.gui.appearance_switch.get() == 1:
    #         customtkinter.set_appearance_mode("Dark")
    #         self.gui.appearance_icon.configure(image=self.gui.icon_moon)
    #     else:
    #         customtkinter.set_appearance_mode("Light")
    #         self.gui.appearance_icon.configure(image=self.gui.icon_sun)

    def toggle_appearance(self) -> None:
        if self.gui.appearance_switch.get() == 1:
            customtkinter.set_appearance_mode("Dark")
            self.gui.appearance_switch.configure(text="Light Mode")
        else:  
            customtkinter.set_appearance_mode("Light")
            self.gui.appearance_switch.configure(text="Dark Mode")

    def start_icon_thread(self) -> None:
        self.gui.icon.run()

    def create_icon(self) -> None:
        if not is_gui_env():
            log_debug("GUI environment not available, skipping system tray icon")
            return
      
        self.gui.tray_icon_thread = True
        tooltip = "Pyile - File Monitor"

        try:
            import pystray # type: ignore
            from PIL import Image # type: ignore
            from pystray import MenuItem as item # type: ignore

            tray_icon_path = join_path(get_project_root(levels_up=2), "assets", "images", "tray_icon.png")
            if not file_exists(tray_icon_path):
                log_warning("Tray icon not found, using default colour square.")
                image = Image.new("RGBA", (16, 16), (0, 120, 215, 255))
            else:
                image = Image.open(tray_icon_path)
            
            if is_windows_11():
                menu = (
                    item("show", self.icon_clicked, default=True, visible=False),
                    item("exit", self.icon_clicked),
                )
            else:
                menu = (
                    item("exit", self.icon_clicked), 
                    item("show", self.icon_clicked, default=True, visible=False)
                )
            
            try:
                self.gui.icon = pystray.Icon("pyile", image, tooltip, menu)
                self.gui.icon.title = tooltip
                
                start_thread_if_needed(
                    self.gui.icon_thread_key, 
                    self.start_icon_thread,
                )
                
            except Exception as e:
                log_error(f"Failed to create pystray icon: {e}")
                self.gui.tray_icon_thread = False
                return
            
        except Exception as e:
            log_error(f"Failed to start system tray icon: {e}")
            self.gui.tray_icon_thread = False

    def stop_icon_thread(self) -> None:
        try:
            if not self.gui.icon or not self.gui.tray_icon_thread:
                return

            self.gui.tray_icon_thread = False
            self.gui.icon.stop()
            shutdown_thread(self.gui.icon_thread_key)

        except Exception as e:
            log_error(f"Error stopping icon thread: {e}")

    def exit_application(self) -> None:
        # todo - if backup running do a backup before quiting 
        # self.start_backup(directory, self.custom_backup_path)

        flush_config_q()

        if self.gui.monitoring_active:
            self._stop_monitoring()
        
        self.gui.stop_icon_thread()
        
        stop_log_thread()
        
        # WindowClassRegistry.get().unregister(log_error)

        NotificationManager.get().stop()

        from pyile.lib.runtime.internal.executor_pool import ExecutorPool
        ExecutorPool.get().shutdown()
        
        if self.gui.delete_logs_on_exit:
            self._truncate_logs_on_exit()
        
        from pyile.lib.runtime.cache_manager.cache import SlabCache
        cache = SlabCache.get()
        try:
            cache.save()
            # log_warning("[WARNING] Failed to save cache")
        except Exception as e:
            log_error(f"Cache save failed: {e}")
        finally:
            cache.close()
        
        for thread_key in list(_thread_state.keys()):
            shutdown_thread(thread_key)
        
        self.gui.destroy()
        self.gui.quit()
        exit()

    def icon_clicked(self, none: Any, item: Any) -> None:
        if item.text == "exit":
            self.gui.after(0, self.exit_application)
        elif item.text == "show":
            self.gui.deiconify()

    def hide_window(self) -> None:
        self.gui.iconify()
        self.gui.withdraw()
        if not self.gui.tray_icon_thread:
            self.create_icon()

    def _start_backup(self, directory: str, custom_backup_path: Optional[str]) -> None:
        _monitor = BackupMonitor(directory, custom_backup_path, log_console=lambda msg: self.gui.log_to_console(msg))
        start_thread_if_needed("backup_monitor", _monitor.main)
        self.gui.log_to_console(f"Started backups for {directory}")

    def back_up(self) -> None:
        try:
            directory = self._prompt()
            if not directory:
                return

            self.gui.log_to_console(f"Backup feature is not implemented yet")
            # working on it still
            # log_console(self.console, f"Backing up {directory} to {self.custom_backup_path}")
            # self._start_backup(directory, self.custom_backup_path)
        except Exception as e:
            log_error(f"Backup error: {e}")

    def toggle_monitoring(self) -> None:
        if self.gui.monitoring_active:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self) -> None:
        self.gui.PATHS = self.gui.get_config.return_paths()
        self.gui.EXCLUDE = self.gui.get_config.return_excluded_paths()
        
        excluded_cache = [
            tuple(Path(get_norm_path(p).lower()).parts) for p in (self.gui.EXCLUDE or [])
        ]

        from pyile.lib.runtime.internal.executor_pool import ExecutorPool
        ExecutorPool.get().restart()

        nm = NotificationManager.get()
        nm.set_sound_enabled(self.gui.notification_sound_enabled)
        nm.start()

        if not self.gui.PATHS:
            self.gui.log_to_console("There are no directories to monitor")
            return
        
        self.gui.sidebar_button_1.configure(text="Stop monitoring")
        self.gui.monitoring_active = True
        self.gui.update_status_indicator(True)
        self.gui.progress_label.configure(text="Status: Monitoring", text_color=STARTING_COLOR)
        
        for i, path in enumerate(self.gui.PATHS):
            monitor_key = f"file_monitor_{i}"
            updater_key = f"updater_{i}"
            
            file_monitor = Monitor(
                path, 
                excluded_cache=excluded_cache, 
                check_current_files=self.gui.check_current_files, 
                notification_enabled=self.gui.notification_enabled, 
                exclude_system_extensions=self.gui.exclude_system_extensions,
                exclude_temp_extensions=self.gui.exclude_temp_extensions,
                log_console=self.gui.log_to_console,
            )
            
            with self.gui.monitor_lock:
                state = DirState(path)
                state.set_monitor(file_monitor) 
                self.gui.monitor_states[path] = state
            
            start_thread_if_needed(monitor_key, file_monitor.main)
            start_thread_if_needed(updater_key, self._updater, file_monitor=file_monitor)

    def _updater(self, file_monitor: Monitor) -> None:
        while self.gui.monitoring_active:
            try:
                last_file, count, match = file_monitor.return_value()
                self.gui.after(0, lambda: self._update_values(last_file, count, match))
                time.sleep(POLL_INTERVAL) 
            except Exception as e:
                log_error(f"Updater error: {e}")
                break

    def _update_values(self, last_file: Optional[str], count: int, match: int) -> None:
        if match:
            self.gui.heading_label.configure(text=f"{match} Files are the same")
        if count:
            self.gui.heading_label_2.configure(text=f"{count} Files checked today")
        if last_file:
            self.gui.heading_label_3.configure(text=f"Last file checked - {last_file}")

    def _stop_monitoring(self) -> None:
        self.gui.monitoring_active = False
        self.gui.sidebar_button_1.configure(text="Stopping...")
        self.gui.update_status_indicator(False, is_stopping=True)
        self.gui.progress_label.configure(text="Status: Stopping monitoring...", text_color=STOPPING_COLOR)

        NotificationManager.get().stop()

        try:
            from pyile.lib.runtime.cache_manager.cache import SlabCache, get_cache_stats
            stats = get_cache_stats()
            log_info(f"Cache entries: {stats['slab_entries']}")
            self.gui.log_to_console(f"Cache entries: {stats['slab_entries']} slab entries")
            
            cache = SlabCache.get()
            if not cache.save():
                fail_msg = "[WARNING] Failed to save cache"
                self.gui.log_to_console(fail_msg)
                log_warning(fail_msg)
            else:
                save_msg = "Saved cache"
                # self.gui.log_to_console(save_msg)
                log_info(save_msg)
        except Exception as e:
            log_error(f"Error during final cache print/save: {e}")
        
        from pyile.lib.runtime.internal.executor_pool import ExecutorPool
        ExecutorPool.get().shutdown()

        def cleanup_threads() -> None:
            try:
                stop_threads = []
                states = self.gui.get_monitor_states()
                
                for dir_state in states:
                    if not dir_state or not dir_state.get_monitor():
                        continue

                    def stop_monitor(state=dir_state):
                        try:
                            log_info(f"Stopping monitor {state.path} at {time.monotonic():.2f}")
                            state.cleanup() 
                            log_info(f"Monitor {state.path} stopped at {time.monotonic():.2f}")
                        except Exception as e:
                            log_error(f"Monitor {state.path} stop failed: {e}")

                    t = threading.Thread(target=stop_monitor, daemon=True)
                    t.start()
                    stop_threads.append(t)

                for t in stop_threads:
                    t.join(timeout=5)

                kill_threads = []
                thread_keys = []
                
                with _thread_state._lock:  
                    thread_keys = list(_thread_state._dict.keys())
                
                batch_size = 5
                for i in range(0, len(thread_keys), batch_size):
                    batch = thread_keys[i:i + batch_size]
                    
                    def kill_thread_batch(batch_keys=batch):
                        for k in batch_keys:
                            try:
                                log_info(f"Shutting down thread {k} at {time.monotonic():.2f}")
                                shutdown_thread(k)
                            except Exception as e:
                                log_error(f"Failed to kill {k}: {e}")

                    t = threading.Thread(target=kill_thread_batch, daemon=True)
                    t.start()
                    kill_threads.append(t)

                for t in kill_threads:
                    t.join()

            except Exception as e:
                log_error(f"During thread cleanup: {e}")
                
            finally:
                self.gui.after(0, self._cleanup_complete)

        threading.Thread(target=cleanup_threads, daemon=True).start()

    def _cleanup_complete(self) -> None:
        with self.gui.monitor_lock:
            self.gui.monitor_states.clear()
        
        self.gui.sidebar_button_1.configure(text="Start monitoring")
        self.gui.update_status_indicator(False)
        self.gui.progress_label.configure(text="Status: Idle", text_color="gray")

    def get_save_directory(self) -> None:
        directory = self._prompt()
        if not directory:
            return

        path = self.gui.get_config.add_path(directory)

        if not self.gui.save_dirs_for_next_session:
            return
        
        if path:
            self.gui.get_config.save_directories_config(path)
            self.gui.log_to_console(f"[SUCCESS] Added directory: {path}")
        else:
            self.gui.log_to_console(f"Directory already exists: {path}")

    def get_exclude_directory(self) -> None:
        directory = self._prompt()
        if not directory:
            return

        path = self.gui.get_config.add_excluded_path(directory)
        if not self.gui.save_dirs_for_next_session:
            return

        if path:
            self.gui.get_config.save_excluded_directories_config(path)
            self.gui.log_to_console(f"[SUCCESS] Added excluded directory: {path}")
        else:
            self.gui.log_to_console(f"Excluded directory already exists: {path}")

    def _prompt(self) -> Optional[str]:
        directory = filedialog.askdirectory()
        if not directory:
            self.gui.log_to_console("Directory selection cancelled")
            return None

        self.gui.log_to_console(f"selected directory {directory}")
        return directory

    def _truncate_logs_on_exit(self) -> None:
        try:
            logs_dir = self.gui.custom_log_path or join_path(get_project_root(levels_up=2), "logs")

            if file_exists(logs_dir) and is_directory(logs_dir):
                import glob
                log_files = glob.glob(join_path(logs_dir, "*.log"))

                from pyile.lib.utils.common import open_file_rw, close_fd
                for log_file in log_files:
                    try:
                        fd = open_file_rw(log_file, extra_flags=os.O_TRUNC)
                        if fd is not None:
                            close_fd(fd)
                    except Exception as e:
                        log_error(f"Failed to truncate log file {log_file}: {e}")
                
        except Exception as e:
            log_error(f"Failed to truncate logs on exit: {e}")

    def _update_checkbox(self, checkbox: int, new_value: bool, *, save: bool = False) -> None:
        self.gui.checkbox_states[checkbox] = new_value

        checkbox_widget = getattr(self.gui, f"checkbox_{checkbox}", None)
        if checkbox_widget:
            if new_value:
                checkbox_widget.select()
            else:
                checkbox_widget.deselect()

        handler_name = f"_on_checkbox_{checkbox}_changed"
        handler = getattr(self, handler_name, None)
        if callable(handler):
            handler(new_value)

        if save:
            self.gui.get_config.save_checkbox_config(self.gui.checkbox_states)

    def get_checkbox_states(self) -> None:
        config = self.gui.get_config.load_checkbox_config()
        if not config:
            return

        for i in range(1, 10):
            val_str = config.get(f"Checkbox{i}_value")
            is_checked = (str(val_str).lower() == "true")
            self._update_checkbox(i, is_checked, save=False)

    def checkbox_checked(self, checkbox: int) -> None:
        current = self.gui.checkbox_states.get(checkbox, False)
        new_value = not current
        self._update_checkbox(checkbox, new_value, save=True)

    def _on_checkbox_1_changed(self, is_checked: bool) -> None:
        self.gui.save_dirs_for_next_session = is_checked
        if is_checked:
            paths = self.gui.get_config.return_paths()
            excluded_paths = self.gui.get_config.return_excluded_paths()
            
            for path in paths:
                 self.gui.get_config.save_directories_config(path)

            for path in excluded_paths:
                 self.gui.get_config.save_excluded_directories_config(path)

    def _on_checkbox_2_changed(self, is_checked: bool) -> None:
        self.gui.exclude_system_extensions = is_checked
        if is_checked:
            self.gui.log_to_console("System extension filtering enabled")
        else:
            self.gui.log_to_console("System extension filtering disabled")

    def _on_checkbox_3_changed(self, is_checked: bool) -> None:
        self.gui.check_current_files = is_checked

    def _on_checkbox_4_changed(self, is_checked: bool) -> None:
        self.gui.minimise_to_tray = is_checked
        if not is_checked:
            self.stop_icon_thread()

    def _on_checkbox_5_changed(self, is_checked: bool) -> None:
        prev = self.gui.notification_enabled
        if is_checked != prev:
            self.gui.notification_enabled = is_checked

            if is_checked:
                if self.gui.notification_sound_enabled:
                    self.gui.log_to_console("Notifications enabled with sound")
                else:
                    self.gui.log_to_console("Notifications enabled")

                nm = NotificationManager.get()
                nm.set_sound_enabled(self.gui.notification_sound_enabled)
                nm.start()

            else:
                self.gui.log_to_console("Notifications disabled")
                NotificationManager.get().stop()

    def _on_checkbox_6_changed(self, is_checked: bool) -> None:
        prev = self.gui.notification_sound_enabled
        if is_checked != prev:
            self.gui.notification_sound_enabled = is_checked
            if is_checked:
                self.gui.log_to_console("Notification sound enabled")
            else:
                self.gui.log_to_console("Notification sound disabled")

            if self.gui.notification_enabled:
                NotificationManager.get().set_sound_enabled(is_checked)

    def _on_checkbox_7_changed(self, is_checked: bool) -> None:
        self.gui.exclude_temp_extensions = is_checked
        if is_checked:
            self.gui.log_to_console("Temp extension filtering enabled")
        else:
            self.gui.log_to_console("Temp extension filtering disabled")

    def _on_checkbox_8_changed(self, is_checked: bool) -> None:
        self.gui.delete_logs_on_exit = is_checked
        if is_checked:
            self.gui.log_to_console("Delete logs on exit enabled")
        else:
            self.gui.log_to_console("Delete logs on exit disabled")

    def _on_checkbox_9_changed(self, is_checked: bool) -> None:
        self.gui.auto_scroll_console = is_checked
        if is_checked:
            self.gui.log_to_console("Auto-scroll console enabled")
        else:
            self.gui.log_to_console("Auto-scroll console disabled")
    
