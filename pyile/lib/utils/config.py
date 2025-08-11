from pyile.lib.runtime.internal.thread_safe import ThreadSafeList, SafeThread
from pyile.lib.utils.logging import log_error, log_info
from pyile.lib.runtime.internal.constants import CONFIG_VERSION
from pyile.lib.utils.common import (
    join_path, is_absolute, is_directory, get_norm_path, get_project_root, 
    open_file_rw, open_file_ro, open_file_rwa, write_text, read_text, 
    close_fd, ensure_dir_exists, file_exists
)
from pyile.lib.utils.lazy import LazyInit

import os
from queue import Queue, Empty
from typing import Optional, Dict, List, Callable
COMMON_HEADER = f"version = {CONFIG_VERSION}\n\n[Common Settings Config]\n"
SAVED_DIRS_HEADER = f"version = {CONFIG_VERSION}\n\n[Saved Directories Config]\n"
EXCLUDE_DIRS_HEADER = f"version = {CONFIG_VERSION}\n\n[Excluded Directories Config]\n"
CHECKBOXES_HEADER = f"version = {CONFIG_VERSION}\n\n[Checkbox States Config]\n"

# these are now just templates at this point
# keeping it for legacy sake
DEFAULT_PATHS: List[str] = [
    # "C:\\Windows"
    # "C:\\Users\\dev\\Documents"

    # add hard coded directories here all will be loaded in on start up
] 

# add annoying paths here that you do not want to include in the config file
# this can keep the config file smaller while still blocking a good portion of dirs
DEFAULT_EXCLUDED_PATHS: List[str] = [
    # when monitoring the entire C:\ drive it will detect all changes made in the system
    # adding file paths here will reduce unnecessary output logs
    # excluded paths can be a partial path or a full path

    # notification triggers make a temp file in this location
    "\\AppData\\Local\\Microsoft\\Windows\\Explorer\\NotifyIcon",

    # when chrome is open it constantly writes user data here
    "\\AppData\\Local\\Google\\Chrome\\User Data\\Default"

    # add hard coded directories here all will be loaded in on start up
] 

COMMON_CFG = "common.cfg"
CHECKBOX_CFG = "checkbox_states.cfg"
SAVED_DIRS_CFG = "saved_directories.cfg"
EXCLUDED_DIRS_CFG = "excluded_directories.cfg"

_CONFIG_CREATORS = {
    COMMON_CFG: lambda self: self.make_common_config(),
    CHECKBOX_CFG: lambda self: self.make_checkbox_config(),
    SAVED_DIRS_CFG: lambda self: self.make_saved_directories_config(),
    EXCLUDED_DIRS_CFG: lambda self: self.make_excluded_directories_config(),
}

_c_q = Queue()

def start_config_thread() -> None:
    log_info("starting config thread")
    SafeThread.spawn(target_fn=_config_writer_thread)

def flush_config_q(timeout: float = 1.0) -> None:
    while not _c_q.empty():
        try:
            operation = _c_q.get(timeout=timeout)
            operation()
        except Exception as e:
            log_error(f"[flush_config_q] Exception: {e}")
            break

def _config_writer_thread() -> None:
    while True: 
        try:
            operation = _c_q.get(timeout=0.5)
        except Empty:
            continue
        try:
            operation()
        except Exception as e:
            log_error(f"[config_writer_thread] Failed to write to config {e}")

class UserConfig(LazyInit):
    def __init__(self, log_console: Callable[[str], None]) -> None:
        self.log_console = log_console
        self.config: Dict[str, str] = {}
        
        self.PATHS = []
        self.EXCLUDE = []
        self._written_paths = set()
        self.is_running = False

        for path in DEFAULT_PATHS:
            norm = get_norm_path(path)
            self.PATHS.append(norm)
            self._written_paths.add(norm)

        for path in DEFAULT_EXCLUDED_PATHS:
            norm = get_norm_path(path)
            self.EXCLUDE.append(norm)
            self._written_paths.add(norm)
            
    def start(self):
        if not self.is_running:
            self.is_running = True
            start_config_thread()

    def return_paths(self) -> List[str]:
        return list(self.PATHS)
    
    def return_excluded_paths(self) -> List[str]:
        return list(self.EXCLUDE)

    def add_path(self, path: Optional[str]) -> Optional[str]:
        if path is None:
            return None

        norm_path = get_norm_path(path)
        if norm_path not in self.PATHS:
            self.PATHS.append(norm_path)
            return norm_path
        return None

    def add_excluded_path(self, path: Optional[str]) -> Optional[str]:
        if path is None:
            return None

        norm_path = get_norm_path(path)
        if norm_path not in self.EXCLUDE:
            self.EXCLUDE.append(norm_path)
            return norm_path
        return None

    def _config_location(self, cfg_name: str) -> str:
        path = join_path(get_project_root(2), "configs")

        if not is_directory(path):
            ensure_dir_exists(path)
        return join_path(path, cfg_name)

    def _make_config_file(self, filename: str, header: str, comments: str) -> None:
        cfg = self._config_location(filename)
        if file_exists(cfg):
            return
        
        self.log_console(f"{filename} config file made - {cfg}")

        try:
            fd = open_file_rw(cfg, extra_flags=os.O_TRUNC)
            if fd is None:
                return

            content = f"{header}{comments}\n"
            write_text(fd, content)
            close_fd(fd)
            
        except Exception as e:
            log_error(f"Error making {filename} file {e}")

    def _save_path(self, filename: str, path: Optional[str], description: str) -> None:
        if path is None:
            return

        norm_path = get_norm_path(path)
        
        if norm_path in self._written_paths:
            return
    
        self._written_paths.add(norm_path)
            
        cfg = self._config_location(filename)
        self.log_console(f"Path has been added to {description} config - {norm_path}")
         
        def _task() -> None:
            try:
                fd = open_file_rwa(cfg)
                if fd is None:
                    return

                write_text(fd, f"\n-{norm_path}")
                close_fd(fd)

            except Exception as e:
                log_error(f"Error saving {filename} file {e}")
        
        _c_q.put(_task)

    def _ensure_config_exists(self, filename: str) -> None:
        cfg = self._config_location(filename)
        if file_exists(cfg):
            return

        creator = _CONFIG_CREATORS.get(filename)
        if creator:
            creator(self)

    def make_saved_directories_config(self) -> None:
        header = SAVED_DIRS_HEADER
        comments = """
# Manually add saved directories as shown below
# -C:\\Users
# -C:\\Users\\dev\\AppData
# -C:/Users/dev/AppData"""
        self._make_config_file(SAVED_DIRS_CFG, header, comments)
    
    def make_excluded_directories_config(self) -> None:
        header = EXCLUDE_DIRS_HEADER
        comments = """
# Manually add excluded directories as shown below
# Directories can be a partial path or a full path
# -C:\\Windows
# -\\AppData
# -\\dev\\AppData
# -C:/Users/dev/AppData"""
        self._make_config_file(EXCLUDED_DIRS_CFG, header, comments)

    def make_common_config(self) -> None:
        header = COMMON_HEADER
        comments = """
# Manually add directories as shown below
# log_folder_path = <path>
# backup_folder_path = <path>"""
        self._make_config_file(COMMON_CFG, header, comments)

    def make_checkbox_config(self) -> None:
        header = CHECKBOXES_HEADER
        comments = "\n# Stores checkbox state values\n# Checkbox1 = True"
        self._make_config_file(CHECKBOX_CFG, header, comments)

    def save_directories_config(self, path: str) -> None:
        self._ensure_config_exists(SAVED_DIRS_CFG)
        self._save_path(SAVED_DIRS_CFG, path, "saved directories")

    def save_excluded_directories_config(self, path: str) -> None:
        self._ensure_config_exists(EXCLUDED_DIRS_CFG)
        self._save_path(EXCLUDED_DIRS_CFG, path, "excluded directories")

    def save_checkbox_config(self, checkbox_states: dict) -> None:
        self.log_console("Saving checkbox states...")
        self._ensure_config_exists(CHECKBOX_CFG)
        cfg = self._config_location(CHECKBOX_CFG)

        checkboxes = {f"Checkbox{i}": value for i, value in checkbox_states.items()}

        def _task() -> None:
            try:
                fd = open_file_rw(cfg, extra_flags=os.O_TRUNC)
                if fd is None:
                    return

                content = CHECKBOXES_HEADER
                content += "\n".join(f"{key} = {value}" for key, value in checkboxes.items())
                write_text(fd, content)
                close_fd(fd)

            except Exception as e:
                log_error(f"Error saving checkbox states config {e}")
        
        _c_q.put(_task)

    def save_common_config(
        self, 
        log_folder_path: Optional[str] = None, 
        backup_folder_path: Optional[str] = None
    ) -> None:
        self.log_console("Saving common settings...")
        self._ensure_config_exists(COMMON_CFG)
        cfg = self._config_location(COMMON_CFG)

        def _task() -> None:
            try:
                fd = open_file_rw(cfg, extra_flags=os.O_TRUNC)
                if fd is None:
                    return None

                content = COMMON_HEADER
                content += f"log_folder_path = {log_folder_path or ""}\n"
                content += f"backup_folder_path = {backup_folder_path or ""}\n"
                write_text(fd, content)
                close_fd(fd)

            except Exception as e:
                log_error(f"Error saving common settings config {e}")
        
        _c_q.put(_task)

    def _load_config_lines(self, filename: str) -> List[str]:
        self._ensure_config_exists(filename)
        cfg = self._config_location(filename)
        try:
            fd = open_file_ro(cfg)
            if fd is None:
                return []

            content = b"".join(read_text(fd)).decode("utf-8")
            close_fd(fd)
            return content.splitlines()

        except Exception as e:
            log_error(f"Error reading {filename} config {e}")
            return []

    def load_directories_config(self) -> None:
        self.log_console("Loading saved directories...")
        lines = self._load_config_lines(SAVED_DIRS_CFG)
        for line in lines:
            if not line.startswith("-"):
                continue

            raw_path = line.strip().strip("-")
            norm_path = get_norm_path(raw_path)

            if not is_directory(norm_path):
                self.log_console(f"Path {raw_path} does not exist, remove from config")
                continue
            
            self._written_paths.add(norm_path)
            self.add_path(norm_path)

    def load_excluded_directories_config(self) -> None:
        self.log_console("Loading excluded directories...")
        lines = self._load_config_lines(EXCLUDED_DIRS_CFG)
        for line in lines:
            if not line.startswith("-"):
                continue

            raw_path = line.strip().strip("-")
            norm_path = get_norm_path(raw_path) 

            is_abs = is_absolute(raw_path)
            if is_abs:
                if not is_directory(norm_path):
                    self.log_console(f"Path {raw_path} does not exist, remove from config")
                    continue

            self._written_paths.add(norm_path)
            self.add_excluded_path(norm_path)

    def load_common_config(self) -> Dict[str, str]:
        self.log_console("Loading common settings...")
        lines = self._load_config_lines(COMMON_CFG)
        for line in lines:
            parts = line.split(" = ")
            if len(parts) != 2:
                continue

            key, value = parts[0].strip(), parts[1].strip()
            if key == "log_folder_path":
                self.config[key] = value
            elif key == "backup_folder_path":
                self.config[key] = value

        return self.config

    def load_checkbox_config(self) -> Dict[str, str]:
        self.log_console("Loading checkbox states...")
        lines = self._load_config_lines(CHECKBOX_CFG)
        for line in lines:
            parts = line.split(" = ")
            if len(parts) != 2:
                continue

            key, value = parts[0].strip(), parts[1].strip()
            if key.startswith("Checkbox"):
                self.config[f"{key}_value"] = value

        return self.config

