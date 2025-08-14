from pyile.lib.runtime.monitors.base_monitor import BaseMonitor
from pyile.lib.runtime.internal.constants import (
    FILE_ACTION_ADDED, FILE_ACTION_REMOVED, DEBOUNCE_WINDOW,
    FILE_ACTION_MODIFIED, FILE_RENAMED_FROM, FILE_RENAMED_TO,
    SYSTEM_EXTENSIONS, TEMP_EXTENSIONS, CHUNK_SIZE
)
from pyile.lib.ui.notifier import trigger_notfication
from pyile.lib.utils.common import (
    join_path, is_directory, get_norm_path, open_file_ro_retry,
    read_text, close_fd, is_file, list_directory, file_exists
)
from pyile.lib.utils.hash_manager import HashManager
from pyile.lib.runtime.cache_manager.cache import update_cache_entry, is_file_cached
from pyile.lib.runtime.internal.thread_safe import TTLCache
from pyile.lib.utils.logging import log_error, log_debug
from pyile.lib.runtime.internal.stats import GlobalStats
from pyile.lib.runtime.internal.executor_pool import ExecutorPool

import threading
import time
import os
import concurrent.futures
from pathlib import Path
from concurrent.futures import as_completed
from typing import Optional, Tuple, Callable

DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024

class Monitor(BaseMonitor):
    def __init__(
            self, 
            path: Optional[str] = None, 
            excluded_cache: Optional[list[tuple[str, ...]]] = None, 
            check_current_files: Optional[bool] = None, 
            notification_enabled: Optional[bool] = None, 
            exclude_system_extensions: Optional[bool] = None,
            exclude_temp_extensions: Optional[bool] = None,
            log_console: Optional[Callable[[str], None]] = None,
            max_hash_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        ) -> None:
        
        __slots__ = ( 
            "excluded_cache", "check_current_files", "notification_enabled", 
            "exclude_system_extensions", "exclude_temp_extensions", 
            "log_console", "max_hash_file_bytes", "_system_extension_filter", 
            "_temp_extension_filter", "_debounce_timer", "_mtime_cache", 
            "_spider_files", "_stats", "_hasher", "_futures_lock", 
            "_pending_futures"
        )
                
        if path is None:
            raise ValueError("Monitor path is required")
        if log_console is None:
            raise ValueError("log_console is required")
        
        super().__init__(path)
        
        self.excluded_cache = excluded_cache
        self.check_current_files = check_current_files
        self.notification_enabled = notification_enabled
        self.exclude_system_extensions = exclude_system_extensions
        self.exclude_temp_extensions = exclude_temp_extensions
        self.log_console = log_console
        self.max_hash_file_bytes = max_hash_file_bytes
        
        self._system_extension_filter = SYSTEM_EXTENSIONS
        self._temp_extension_filter = TEMP_EXTENSIONS
        self._debounce_timer = TTLCache(maxsize=8192, ttl=DEBOUNCE_WINDOW)
        self._mtime_cache = TTLCache(maxsize=16384, ttl=None)

        self._spider_files = set()
        self._stats = GlobalStats.get()
        self._hasher = ExecutorPool.get().get_hash_executor()
        
        self._futures_lock = threading.Lock()
        self._pending_futures = set()

    def stop(self) -> None:
        log_debug(f"FileMonitor {self.path} stop() called")

        self.is_running = False

        self._cancel_pending_futures()

        super().stop()

    def _cancel_pending_futures(self) -> None:
        with self._futures_lock:
            futures = list(self._pending_futures)
            self._pending_futures.clear()

        if not futures:
            return

        cancelled = 0
        for fut in futures:
            try:
                if fut.cancel():
                    cancelled += 1
            except Exception:
                pass

        wait_secs = 0.25
        _, not_done = concurrent.futures.wait(futures, timeout=wait_secs)
        if not_done:
            log_debug(f"Pending hashing tasks remaining after cancel: {len(not_done)}")
        if cancelled:
            log_debug(f"Cancelled {cancelled} pending hashing futures")

    def _should_process_file(self, path_filename: str) -> bool:
        if not path_filename:
            return False
            
        if self.is_excluded(path_filename):
            return False
            
        _, ext = os.path.splitext(path_filename.lower())
        
        if self.exclude_system_extensions and ext in self._system_extension_filter:
            return False
            
        if self.exclude_temp_extensions and ext in self._temp_extension_filter:
            return False
            
        return True

    def _debounce_event(self, path_filename: str, action: int) -> bool:
        key = f"{path_filename}:{action}"
        now = time.monotonic()
        
        last_time = self._debounce_timer.get(key)
        if last_time and (now - last_time) < DEBOUNCE_WINDOW:
            if action == FILE_ACTION_MODIFIED and (now - last_time) > 0.1:
                self._debounce_timer[key] = now
                return True
            return False 
        
        self._debounce_timer[key] = now
        return True

    def return_value(self) -> Tuple[Optional[str], int, int]:
        last_file = self._stats.get_last_file()
        count = int(self._stats.file_count)
        match = int(self._stats.match_count)
        return last_file, count, match

    def monitor_handle(self, path_filename: str, action: int, username: Optional[str] = None) -> None:
        if not self._should_process_file(path_filename):
            return
            
        if not self._debounce_event(path_filename, action):
            return
            
        self._process_file_event(path_filename, action, username=username)

    def _process_file_event(
            self, 
            path_filename: str, 
            action: int, 
            filename: Optional[str] = None, 
            username: Optional[str] = None
    ) -> bool:
        if not path_filename:
            return False
            
        norm_path = get_norm_path(os.path.abspath(path_filename))
        
        if filename is None:
            filename = os.path.basename(path_filename)
        
        # self._stats.user_stats.increment(username, 1)
        self._track_file(filename, path_filename)
        
        try:
            if action == FILE_ACTION_ADDED:
                self.log_console(f"User: {username} Created: {path_filename}")
                if self.notification_enabled:
                    self._trigger_notification(path_filename, action)
                self._check_file_async(norm_path)
                return True
                
            elif action == FILE_ACTION_REMOVED:
                self.log_console(f"User: {username} Deleted: {path_filename}")
                if self.notification_enabled:
                    self._trigger_notification(path_filename, action)
                return True
                
            elif action == FILE_ACTION_MODIFIED:
                self.log_console(f"User: {username} Modified: {path_filename}")
                if self.notification_enabled:
                    self._trigger_notification(path_filename, action)
                self._check_file_async(norm_path)
                return True
                
            elif action == FILE_RENAMED_FROM:
                self.old_name = filename
                return True
                
            elif action == FILE_RENAMED_TO:
                self.log_console(f"User: {username} renamed: [{self.old_name}] to: [{filename}]\nPath: {path_filename}")
                return True
                
            else:
                self.log_console(f"Unknown action: {path_filename}")
                return False
        except Exception as e:
            log_error(f"Error processing file event ({path_filename}): {e}")
            return False

    def _check_file_async(self, path_filename: str) -> None:
        if path_filename is None or is_directory(path_filename):
            return

        try:
            if not file_exists(path_filename):
                log_debug(f"File disappeared before hashing: {path_filename}")
                return

            try:
                stat_mtime = os.path.getmtime(path_filename)
            except Exception:
                stat_mtime = None

            if stat_mtime is not None:
                cached_mtime = self._mtime_cache.get(path_filename)
                if cached_mtime is not None and cached_mtime == stat_mtime:
                    log_debug(f"Skipping hash (mtime unchanged): {path_filename}")
                    return

            fut = self._hasher.submit(self._process_file_hash, path_filename) # type: ignore
            self._track_future(fut)

        except Exception as e:
            log_error(f"Failed to submit hash job for {path_filename}: {e}")

    def _track_future(self, future: concurrent.futures.Future) -> None:
        with self._futures_lock:
            self._pending_futures.add(future)

        def _on_done(_fut: concurrent.futures.Future) -> None:
            with self._futures_lock:
                try:
                    self._pending_futures.discard(_fut)
                except Exception:
                    pass

        try:
            future.add_done_callback(_on_done)
        except Exception:
            pass

    def _process_file_hash(self, norm_path: str) -> bool:
        if not self.is_running:
            return False

        try:
            size = os.path.getsize(norm_path)
        except Exception as e:
            log_error(f"Failed to get size for hashing {norm_path} {e}")
            return False

        fd = open_file_ro_retry(norm_path)
        if fd is None:
            log_error(
                f"Failed to open file for hashing {norm_path}: \
                Most likely another Windows file handle is open to this file"
            )
            return False
        
        contents = bytearray()
        try:
            if size <= self.max_hash_file_bytes:
                for chunk in read_text(fd, CHUNK_SIZE):
                    if not self.is_running:
                        return False
                    contents.extend(chunk)
            else:
                chunk_size = DEFAULT_MAX_FILE_BYTES
                positions = [0]

                if size > 2 * chunk_size:
                    positions.append(size // 2)
                if size > chunk_size:
                    positions.append(size - chunk_size)

                for pos in positions:
                    try:
                        os.lseek(fd, pos, os.SEEK_SET)
                    except Exception as e:
                        log_error(f"Seek failed at position {pos} in {norm_path} {e}")
                        continue

                    bytes = min(chunk_size, size - pos)
                    for chunk in read_text(fd, CHUNK_SIZE):
                        if not self.is_running:
                            return False
                        if bytes <= 0:
                            break
                        if len(chunk) > bytes:
                            contents.extend(chunk[:bytes])
                            break
                        else:
                            contents.extend(chunk)
                            bytes -= len(chunk)

            if not contents:
                log_error(f"No data read from file for hashing for file {norm_path}")
                return False

            file_key = HashManager.hash_contents(contents)

            try:
                stat_mtime = os.path.getmtime(norm_path)
                self._mtime_cache[norm_path] = stat_mtime
            except Exception:
                pass

            if not is_file_cached(file_key):
                # self.log_console(f"[CACHE] {filename} not in cache (updating cache)")
                update_cache_entry(file_key)

            self._check_hash_fast(norm_path, file_key)
            return True

        except Exception as e:
            log_error(f"Error during hash checking: {norm_path} - {e}")
            return False
        finally:
            try:
                if fd is not None:
                    close_fd(fd)
            except Exception:
                pass
            try:
                contents.clear()
                del contents
            except Exception:
                pass

    def _check_hash_fast(self, path_filename: str, file_key: int) -> None:
        try:
            existing_file = self._stats.file_hashes.get_or_set(str(file_key), path_filename)
            
            if existing_file != path_filename:
                self._stats.match_count += 1
                self.log_console(f"Duplicate found: {path_filename} matches {existing_file}")
                
        except Exception as e:
            log_error(f"Error during hash checking: {e}")

    def _trigger_notification(self, path_filename: str, action: int) -> None:
        if not self.notification_enabled:
            return
            
        try:
            info = path_filename.split("\\")[3:]
            info = "\\".join(info)
            
            if action == FILE_ACTION_ADDED: 
                trigger_notfication("Click to open file", f"File added\n{info}", 2, on_click=lambda: self.notification(path_filename))
            elif action == FILE_ACTION_REMOVED:
                trigger_notfication("Click to close notification", f"File removed\n{info}", 2)
            elif action == FILE_ACTION_MODIFIED:
                trigger_notfication("Click to open file", f"File modified\n{info}", 2, on_click=lambda: self.notification(path_filename))
        except Exception as e:
            log_error(f"Error triggering notification: {e}")

    def _os_spider_fast(self, path: str) -> None:
        try:
            files = list_directory(path)
            total_files = len(files)

            if total_files == 0:
                self.log_console(f"No files found in {path}")
                return

            self._spider_files.clear()
            abspath_base = os.path.abspath(path)

            chunk_size = CHUNK_SIZE
            processed = completed = cancelled = 0

            for i in range(0, total_files, chunk_size):
                if not self.is_running:
                    break

                chunk = files[i:i + chunk_size]
                futures, processed_delta = self._submit_chunk_tasks(abspath_base, chunk)
                if not futures:
                    continue

                processed += processed_delta
                chunk_completed, chunk_cancelled = self._wait_for_futures(futures)
                completed += chunk_completed
                cancelled += chunk_cancelled

                self._log_progress(i, chunk_size, total_files)

            self.log_console(f"File discovery completed: {completed} processed, {cancelled} cancelled")

        except Exception as e:
            log_error(f"Error during file discovery: {e}")

    def _submit_chunk_tasks(self, base_path: str, chunk: list[str]) -> tuple[list, int]:
        futures = []
        processed_count = 0

        valid_tasks = []
        for file in chunk:
            if not self.is_running:
                break

            path_file = join_path(base_path, file)
            if self.is_excluded(path_file):
                continue

            if not is_file(path_file) or not self._should_process_file(path_file):
                continue

            norm_path = get_norm_path(path_file)
            key = (norm_path,)
            if key in self._spider_files:
                continue

            self._spider_files.add(key)
            valid_tasks.append((norm_path, file))

        for norm_path, file in valid_tasks:
            future = self._hasher.submit(self._process_file_hash, norm_path) # type: ignore
            futures.append(future)
            processed_count += 1

        return futures, processed_count

    def _wait_for_futures(self, futures: list) -> tuple[int, int]:
        completed = cancelled = 0

        try:
            from pyile.lib.runtime.internal.constants import CHUNK_TIMEOUT, FUTURE_TIMEOUT
            for future in as_completed(futures, timeout=CHUNK_TIMEOUT):
                try:
                    future.result(timeout=FUTURE_TIMEOUT)
                    completed += 1
                except concurrent.futures.TimeoutError:
                    try:
                        future.cancel()
                    except Exception:
                        pass 
                    cancelled += 1
                    self.log_console(f"[WARNING] File processing timeout - cancelled")
                except Exception as e:
                    log_error(f"File processing error: {e}")
                    cancelled += 1
        except concurrent.futures.TimeoutError:
            for future in futures:
                if not future.done():
                    try:
                        future.cancel()
                    except Exception:
                        pass
                    cancelled += 1
            self.log_console(f"[WARNING] Chunk timeout - cancelled {cancelled} files")

        return completed, cancelled

    def _log_progress(self, i: int, chunk_size: int, total: int) -> None:
        if (i + chunk_size) % 100 == 0 or (i + chunk_size) >= total:
            self.log_console(f"[PROGRESS] Scanned {min(i + chunk_size, total)}/{total} files...")

    def _track_file(self, file: str, path_filename: str) -> None:
        if not is_file(path_filename):
            return
        actual_filename = os.path.basename(file)
        self._stats.set_last_file(actual_filename)
        self._stats.file_count += 1

    def _spider_thread_main(self, path: str) -> None:
        self._os_spider_fast(path)

    def notification(self, path_filename: str) -> bool:
        try:
            if not file_exists(path_filename):
                self.log_console(f"[WARNING] File no longer exists: {path_filename}")
                return False
            
            # this blocks a file from running when the user clicks on, 
            # a notification banner triggered from a file event change
            if self._should_block_file(path_filename):
                self.log_console(f"[SECURITY] Blocked potentially unsafe file from opening: {path_filename}")
                return False

            import subprocess
            try:
                subprocess.Popen(
                    ["explorer", path_filename],
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception as e:
                msg = f"[ERROR] Explorer launch failed: {e}"
                self.log_console(msg)
                log_error(msg)

            return True

        except Exception as e:
            log_error(f"Failed to open file {path_filename}: {e}")
            return False

    def _should_block_file(self, path_filename: str) -> bool:
        try:
            _, ext = os.path.splitext(path_filename)
            ext = ext.casefold()

            if not ext:
                return False

            from pyile.lib.runtime.internal.constants import DO_NOT_RUN_EXTENSIONS
            return ext in DO_NOT_RUN_EXTENSIONS

        except Exception:
            return False

    def is_excluded(self, path_filename: str) -> bool:
        if not self.excluded_cache:
            return False

        norm_parts = Path(get_norm_path(path_filename).lower()).parts

        for excluded_parts in self.excluded_cache:
            if len(excluded_parts) > len(norm_parts):
                continue

            for i in range(len(norm_parts) - len(excluded_parts) + 1):
                if norm_parts[i:i + len(excluded_parts)] == excluded_parts:
                    return True
        return False

    def main(self) -> None:
        try:
            if self.check_current_files:
                self.log_console(f"Starting initial file discovery for {self.path}")
                self._spider_thread_main(self.path)
                self.log_console(f"Initial file discovery completed for {self.path}")
            
            self.log_console(f"Monitoring started for {self.path}")
            super().main()
            
        except Exception as e:
            log_error(f"Error in file monitor initialization: {e}")
        finally:
            self.log_console(f"Monitoring stopped for {self.path}")

