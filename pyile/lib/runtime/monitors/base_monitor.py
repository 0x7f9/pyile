from pyile.lib.utils.common import open_file_rw, write_text, close_fd, join_path, get_username
from pyile.lib.utils.logging import log_error, log_debug
from pyile.lib.runtime.internal.constants import (
    FILE_LIST_DIRECTORY, FILE_SHARE_READ, FILE_SHARE_DELETE, FILE_SHARE_WRITE, 
    OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, FILE_FLAG_OPEN_REPARSE_POINT, 
    FILE_FLAG_OVERLAPPED, FILE_NOTIFY_FLAGS,  TRANSIENT_ERRORS,  FAST_POLL_INTERVAL, 
    ERROR_SLEEP_INTERVAL, BUFFER_SIZE, MAX_ERRORS, FILE_READ_ATTRIBUTES, SECURITY_DESCRIPTOR_REVISION
)
from pyile.lib.runtime.internal.dataclasses import SECURITY_ATTRIBUTES
from pyile.lib.runtime.internal.win32_api import (
    CancelIoEx, InitializeSecurityDescriptor, SetSecurityDescriptorDacl, 
    CreateFileW, ReadDirectoryChangesW
)

import os
import time
import win32file # type: ignore
import threading
import ctypes
from ctypes import wintypes
from typing import Optional, List, Tuple, Any

def _cancel_pending_read(handle: Any) -> bool:
    if not handle:
        return False
    
    try:
        raw = int(getattr(handle, "handle", handle))
    except Exception:
        raw = handle

    try:
        res = CancelIoEx(wintypes.HANDLE(raw), None)
        if res:
            return True
        else:
            err = ctypes.get_last_error()
            log_debug(f"kernel32.CancelIoEx returned 0. GetLastError={err}")
    except Exception as e:
        log_debug(f"kernel32.CancelIoEx: {e}")

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
        "path", "log_console", "is_running", "_handle", "_error_count", 
        "_max_errors", "_handle_lock", "_monitor_symlinks", "_watch_subtree",
        "_buffer_size", "_buf", "_bytes_returned"
    )
    
    def __init__(self, path: str) -> None:
        self.path = path
        self.is_running = True 

        self._handle = None
        self._watch_subtree = True
        self._buffer_size = BUFFER_SIZE
        self._buf = ctypes.create_string_buffer(self._buffer_size)
        self._bytes_returned = wintypes.DWORD(0)

        self._error_count = 0
        self._max_errors = MAX_ERRORS
        self._handle_lock = threading.Lock()
        self._monitor_symlinks = False 
        # self._monitor_symlinks = is_windows_11 # not tested
    
    def _get_handle_safe(self) -> Optional[Any]:
        with self._handle_lock:
            return self._handle
        
    def get_handle(self) -> Optional[Any]:
        try:
            desired_access = FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES
            share_mode = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE

            flags = FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OVERLAPPED
            if self._monitor_symlinks:
                flags |= FILE_FLAG_OPEN_REPARSE_POINT

            sd = ctypes.create_string_buffer(20)  
            if not InitializeSecurityDescriptor(sd, SECURITY_DESCRIPTOR_REVISION):
                raise ctypes.WinError(ctypes.get_last_error())

            if not SetSecurityDescriptorDacl(sd, True, None, False):
                raise ctypes.WinError(ctypes.get_last_error())

            sa = SECURITY_ATTRIBUTES()
            sa.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
            sa.lpSecurityDescriptor = ctypes.cast(sd, wintypes.LPVOID)
            sa.bInheritHandle = False  

            handle = CreateFileW(
                self.path,
                desired_access,
                share_mode,
                ctypes.byref(sa),
                OPEN_EXISTING,
                flags,
                None
            )
            return handle

        except Exception as e:
            print(f"Failed to create handle: {e}")
            return None

    def get_changes(self) -> List[Tuple[int, str]]:
        handle = self._get_handle_safe()
        if not handle:
            return []
        
        try:
            ok = ReadDirectoryChangesW(
                handle,
                ctypes.byref(self._buf),
                self._buffer_size,
                self._watch_subtree,
                FILE_NOTIFY_FLAGS,
                ctypes.byref(self._bytes_returned),
                None, 
                None
            )

            if not ok:
                raise ctypes.WinError(ctypes.get_last_error())

            return self._parse_results()

        except OSError as e:
            if hasattr(e, "winerror") and e.winerror in TRANSIENT_ERRORS:
                log_debug(f"Transient FS error code: {e.winerror}")
                return []
            raise
        except Exception as e:
            log_error(f"Failed to get changes: {e}")
            self._error_count += 1
            return []
            
    def _parse_results(self) -> List[Tuple[int, str]]:
        results = []
        offset = 0
        buf = self._buf.raw
        bytes_returned = self._bytes_returned.value

        # log_debug(f"FILE_NOTIFY_INFORMATION: {bytes_returned} bytes returned")

        while offset < bytes_returned:
            try:
                if offset + 12 > bytes_returned:
                    log_error(f"Buffer too small for entry at offset {offset}, stopping")
                    break

                next_offset = int.from_bytes(buf[offset:offset+4], "little")
                action = int.from_bytes(buf[offset+4:offset+8], "little")
                name_len = int.from_bytes(buf[offset+8:offset+12], "little")

                if name_len % 2 != 0 or offset + 12 + name_len > bytes_returned:
                    log_error(
                        f"Invalid name length {name_len} at offset {offset}, stopping"
                    )
                    break

                name_bytes = buf[offset+12:offset+12+name_len]
                name = name_bytes.decode("utf-16le", errors="ignore")

                # log_debug(f"entry at offset {offset}: action={action}, name={name}")

                results.append((action, name))

                if next_offset == 0:
                    break

                if next_offset <= 0:
                    log_error(
                        f"Issue with NextEntryOffset {next_offset} at offset {offset}, stopping"
                    )
                    break

                offset += next_offset

            except Exception as e:
                log_error(f"Issue parsing buffer at offset {offset} {e}")
                break

        return results

    def _safe_close_handle(self) -> None:
        handle = self._get_handle_safe()
        if not handle:
            return
        try:
            win32file.CloseHandle(handle)
        except Exception:
            pass
        finally:
            self._handle = None

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
            handle = self._get_handle_safe()
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
        cancel_success = False

        # handle = self._handle # no lock grabbing here
        handle = self._get_handle_safe()
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

  