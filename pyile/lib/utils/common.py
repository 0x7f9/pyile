from pyile.lib.utils.os_version import is_windows_11
from pyile.lib.runtime.internal.constants import (
    MAX_WORKERS_DEFAULT, MAX_WORKERS_WINDOWS_11, 
    FILE_MODE_DEFAULT, CHUNK_SIZE_READ
)

import os
import mmap
import time
import ctypes
from typing import Optional, List, Union
from pathlib import Path
import win32security # type: ignore
import time

PathType = Union[str, Path]

def get_username(path_filename: str) -> str:
    try:
        if not Path(path_filename).exists():
            time.sleep(0.01) 
            if not Path(path_filename).exists():
                raise FileNotFoundError(f"File not found: {path_filename}")
    
        file = win32security.GetFileSecurity(
            path_filename,
            win32security.OWNER_SECURITY_INFORMATION | win32security.DACL_SECURITY_INFORMATION
        )

        sid = file.GetSecurityDescriptorOwner()
        if sid:
            try:
                account, _, _ = win32security.LookupAccountSid("", sid)
                return account
            except Exception:
                from pyile.lib.utils.logging import log_debug
                log_debug("LookupAccountSid failed; falling back to current user SID.")
                return win32security.ConvertSidToStringSid(sid)
    except Exception as e:
        from pyile.lib.utils.logging import log_error
        log_error(f"get_username failed: {e}")

    # if nothing works we fall back to the current user
    # this will always happen when a file is deleted until
    # i find a fix for it.
    try:
        import win32api # type: ignore
        return win32api.GetUserName()
    except Exception:
        return "Unknown"

def _cpu_count() -> int:
    try:
        c = os.cpu_count() or 4
        if is_windows_11():
            return min(c, MAX_WORKERS_WINDOWS_11)
        
        return min(c, MAX_WORKERS_DEFAULT)
    except Exception:
        return MAX_WORKERS_DEFAULT

def get_thread_count() -> int:
    c = _cpu_count()
    
    if is_windows_11():
        return min(c * 2, 16) 
    
    return min(c, 8)

def setup_dpi() -> None:
    try:
        a = ctypes.c_int(2)
        ctypes.windll.shcore.SetProcessDpiAwareness(a)
        return
    except Exception:
        pass
    
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass  

def is_gui_env() -> bool:
    try:
        return bool(ctypes.windll.user32.GetSystemMetrics(0))
    except Exception:
        return False

def get_norm_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))

def get_project_root(levels_up: int = 3) -> str:
    path = os.path.dirname(os.path.abspath(__file__)) 
    for _ in range(levels_up):
        path = os.path.dirname(path)
    return path

def join_path(first: PathType, *others: PathType) -> str:
    p = Path(first)
    for other in others:
        p = p / other
    return str(p)
    
def ensure_file_dir_exists(file_path: str) -> None:
    dir_path = os.path.dirname(file_path)
    if dir_path:
        ensure_dir_exists(dir_path)

def ensure_dir_exists(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def get_cache_path(filename: str) -> str:
    cache_dir = join_path(get_project_root(levels_up=2), "cache")
    ensure_dir_exists(cache_dir)
    return join_path(cache_dir, filename)

def file_exists(path: str) -> bool:
    return os.path.exists(path)

def is_directory(path: str) -> bool:
    return os.path.isdir(path)

def is_absolute(path: str) -> bool:
    if len(path) >= 3 and path[1] == ":" and (path[2] == "\\" or path[2] == "/"):
        return True
    if path.startswith("\\\\"):
        return True
    return False

def is_file(path: str) -> bool:
    return os.path.isfile(path)

def remove_file(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except OSError:
        return False

def list_directory(path: str) -> List[str]:
    try:
        return os.listdir(path)
    except OSError:
        return []

def read_text(fd: int, chunk_size: int = CHUNK_SIZE_READ):
    while True:
        chunk = os.read(fd, chunk_size)
        if not chunk:
            break
        yield chunk

def write_text(fd: int, content: str) -> bool:
    try:
        os.write(fd, content.encode("utf-8"))
        return True
    except OSError:
        return False

def close_fd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass

def open_file_rwa(path: str, mode: int = FILE_MODE_DEFAULT) -> Optional[int]:
    try:
        return os.open(path, os.O_APPEND | os.O_WRONLY | os.O_CREAT, mode)
    except OSError:
        return None

def open_file_ro(path: str) -> Optional[int]:
    try:
        return os.open(path, os.O_RDONLY)
    except OSError:
        return None

def open_file_rw(path: str, mode: int = FILE_MODE_DEFAULT, extra_flags: int = 0) -> Optional[int]:
    try:
        flags = os.O_CREAT | os.O_RDWR | extra_flags
        return os.open(path, flags, mode)
    except OSError:
        return None
    
def create_memory_mapped_file(fd: int, size: int, access: int = mmap.ACCESS_WRITE) -> Optional[mmap.mmap]:
    try:
        return mmap.mmap(fd, size, access=access)
    except OSError:
        return None
    
def truncate_file(fd: int, size: int) -> bool:
    try:
        os.ftruncate(fd, size)
        return True
    except OSError:
        return False
    
