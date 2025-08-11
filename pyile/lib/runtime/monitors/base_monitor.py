from pyile.lib.utils.common import open_file_rw, write_text, close_fd, join_path, get_username
from pyile.lib.utils.os_version import is_windows_11
from pyile.lib.utils.logging import log_error, log_info, log_debug
from pyile.lib.runtime.internal.constants import (
    FILE_LIST_DIRECTORY, FILE_SHARE_READ, FILE_SHARE_DELETE, FILE_SHARE_WRITE, 
    OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, FILE_FLAG_OPEN_REPARSE_POINT, 
    FILE_FLAG_OVERLAPPED, FILE_NOTIFY_FLAGS,  TRANSIENT_ERRORS,  FAST_POLL_INTERVAL, 
    ERROR_SLEEP_INTERVAL, BUFFER_SIZE, MAX_ERRORS
)

import os
import time
import win32file # type: ignore
import threading
from typing import Optional, List, Tuple, Any
import ctypes
from ctypes import wintypes

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    _CancelIoEx = _kernel32.CancelIoEx
    _CancelIoEx.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    _CancelIoEx.restype = wintypes.BOOL
except AttributeError:
    _CancelIoEx = None

def _cancel_pending_read(handle: Any) -> bool:
    if not handle:
        return False
    
    try:
        raw = int(getattr(handle, "handle", handle))
    except Exception:
        raw = handle

    if _CancelIoEx is not None:
        try:
            res = _CancelIoEx(wintypes.HANDLE(raw), None)
            if res:
                return True
            else:
                err = ctypes.get_last_error()
                log_debug(f"kernel32.CancelIoEx returned 0 (no-op). GetLastError={err}")
        except Exception as e:
            log_debug(f"kernel32.CancelIoEx threw: {e}")

    try:
        if win32file.CancelIo(handle):
            return True
    except Exception as e:
        log_debug(f"CancelIo failed: {e}")
        pass

    log_debug(f"Both I/O cancellations failed")
    return False

class BaseMonitor:
    __slots__ = (
        'path', 'log_console', 'is_running', '_handle', '_error_count', 
        '_max_errors', '_handle_lock', '_monitor_symlinks'
    )
    
    def __init__(self, path: str) -> None:
        self.path = path
        self.is_running = True 

        self._handle = None
        self._error_count = 0
        self._max_errors = MAX_ERRORS
        self._handle_lock = threading.Lock()
        self._monitor_symlinks = False 
        # self._monitor_symlinks = is_windows_11 # not tested

    def _get_handle_unlocked(self) -> Optional[Any]:
        with self._handle_lock:
            return self._handle
        
    def get_handle(self) -> Optional[Any]:
        # need to add SECURITY_ATTRIBUTES handling
        
        try:
            desired_access = FILE_LIST_DIRECTORY
            share_mode = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
            flags = FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OVERLAPPED
            if self._monitor_symlinks:
                flags |= FILE_FLAG_OPEN_REPARSE_POINT

            return win32file.CreateFile(
                self.path,
                desired_access,
                share_mode,
                None,
                OPEN_EXISTING,
                flags,
                None
            )
            
        except Exception as e:
            log_error(f"Failed to create handle: {e}")
            return None

    def get_changes(self) -> List[Tuple[int, str]]:
        handle = self._get_handle_unlocked()
        if not handle:
            return []

        if is_windows_11():
            buffer_size = min(BUFFER_SIZE, 32768)  
        else:
            buffer_size = min(BUFFER_SIZE, 8192)

        try:
            # custom buffers do not work with synchronous calling i think,
            # ReadDirectoryChangesW will allocate its own buffer internally
            # so passing in a int(buffer) for it will work fine.

            results = win32file.ReadDirectoryChangesW(
                handle,
                buffer_size,
                True,
                FILE_NOTIFY_FLAGS,
                None,
            )
            
            return results if results else []

        except win32file.error as e:
            if hasattr(e, "winerror") and e.winerror in TRANSIENT_ERRORS:
                log_debug(f"Transient FS error code: {e.winerror}")
                return []
            raise
        except Exception as e:
            log_error(f"Failed to get changes: {e}")
            self._error_count += 1
            return []

    def _recreate_handle(self) -> None:
        with self._handle_lock:
            try:
                self._safe_close_handle()
                handle = self.get_handle()
                if handle:
                    self._handle = handle
                    log_info("Recreated monitoring handle")
                else:
                    log_error("Failed to recreate handle: get_handle() returned None")
            except Exception as e:
                log_error(f"Failed to recreate handle: {e}")

    def _safe_close_handle(self) -> None:
        handle = self._get_handle_unlocked()
        if not handle:
            return None
        try:
            win32file.CloseHandle(handle)
        except Exception:
            pass 

    def monitor_handle(self, path_filename: str, action: int, username: Optional[str] = None) -> None:
        raise NotImplementedError("monitor_handle must be implemented by subclass")

    def _can_monitor(self) -> bool:
        return bool(self.is_running) and int(self._error_count) < self._max_errors
    
    def main(self) -> None:
        try:
            self._handle = self.get_handle()
        except Exception as e:
            log_error(f"Failed to obtain handle: {e}")
            return

        while self._can_monitor():
            # handle = self._handle
            handle = self._get_handle_unlocked()
            if not handle:
                break

            try:
                changes = self.get_changes()
                if not changes:
                    time.sleep(FAST_POLL_INTERVAL)
                    continue

                for action, filename in changes:
                    if not self.is_running:
                        break

                    path_filename = join_path(self.path, filename)
                    username = None
                    try:
                        username = get_username(path_filename)
                    except Exception as e:
                        log_debug(f"Failed to fetch username for {path_filename}: {e}")
                        username = "Unknown"
                    
                    self.monitor_handle(path_filename, action, username=username)
                
                self._error_count = 0
            except Exception as e:
                self._error_count += 1
                log_error(f"Monitor runtime error: {e}")
                if not self.is_running:
                    break
                time.sleep(ERROR_SLEEP_INTERVAL)

    def _nudge(self) -> None:
        # CancelIoEx should be fully fixed now on all windows version.
        # this should almost never trigger now

        # HACK: writing a temp file and then removing it within the monitored(s) dirs
        # this unblocks the blocking call of ReadDirectoryChangesW and allows for fast shutdowns
        df = join_path(self.path, "~.MGSuj$_nudge.tmp")
        try:
            fd = open_file_rw(df, extra_flags=os.O_TRUNC)
            if fd is not None:
                write_text(fd, "0") 
                close_fd(fd)
                os.unlink(df)
        except Exception:
            pass

    def stop(self) -> None:
        self.is_running = False

        handle = self._get_handle_unlocked()
        cancel_success = False
        if handle:
            try:
                cancel_success = _cancel_pending_read(handle)
            except Exception as e:
                log_debug(f"_cancel_pending_read threw: {e}")
        

        if not cancel_success:
            log_debug("I/O cancellation failed — ReadDirectoryChangesW may still be blocking")
            self._nudge()

        time.sleep(FAST_POLL_INTERVAL)

        try:
            self._safe_close_handle()
            log_debug("Handle closed (stop completed)")
        except Exception as e:
            log_error(f"Failed to close handle during stop(): {e}")

  