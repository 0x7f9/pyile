from pyile.lib.runtime.internal.thread_safe import AtomicFlag
from pyile.lib.utils.common import (
    get_project_root, open_file_rwa, write_text, 
    close_fd, ensure_dir_exists, join_path
)
from pyile.lib.utils.lazy import LazyInit

import customtkinter
import tkinter as tk
import datetime
import os
from queue import Queue, Empty
from datetime import datetime
import logging
from logging import Logger
from typing import Optional

_log_dir = join_path(get_project_root(levels_up=2), "logs")
ensure_dir_exists(_log_dir)
_PYILE_LOG = join_path(_log_dir, "pyile.log")
_DEBUG_LOG = join_path(_log_dir, "debug.log")

_l_q = Queue()
_stop_thread = AtomicFlag(True)

class _DebugLogger(LazyInit):
    __slots__ = ("_is_init", "_logger")
    
    def __init__(self) -> None:
        self._is_init = False
        self._logger = None

    def start(self):
        if not self._is_init:
            ensure_dir_exists(os.path.dirname(_DEBUG_LOG))
            self._logger = logging.getLogger("debug")
            self._logger.setLevel(logging.DEBUG)
            self._logger.propagate = False
            if not self._logger.handlers:
                handler = logging.FileHandler(
                    _DEBUG_LOG, mode="w", encoding="utf-8", delay=True
                )
                formatter = logging.Formatter(
                    "%(asctime)s %(levelname)s - %(message)s"
                )
                handler.setFormatter(formatter)
                self._logger.addHandler(handler)
            self._is_init = True

    @classmethod
    def get_logger(cls) -> Logger:
        instance = cls.get()
        if not instance._is_init:
            instance.start()
        assert instance._logger is not None
        return instance._logger

def log_info(msg: str, *args, exc_info: bool = False, **kwargs):
    _DebugLogger.get_logger().info(msg, *args, exc_info=exc_info, **kwargs)

def log_debug(msg: str, *args, exc_info: bool = False, **kwargs):
    _DebugLogger.get_logger().debug(msg, *args, exc_info=exc_info, **kwargs)

def log_error(msg: str, *args, exc_info: bool = True, **kwargs):
    _DebugLogger.get_logger().error(msg, *args, exc_info=exc_info, **kwargs)

def log_warning(msg: str, *args, exc_info: bool = False, **kwargs):
    _DebugLogger.get_logger().warning(msg, *args, exc_info=exc_info, **kwargs)

def _log_writer_thread() -> None:
    while _stop_thread or not _l_q.empty():

        try:
            msg = _l_q.get(timeout=0.5)
        except Empty:
            continue

        try:
            fd = open_file_rwa(_PYILE_LOG)
            if fd is not None:
                write_text(fd, msg)
                close_fd(fd)
        except Exception as e:
            log_error(f"[log_writer_thread] Failed to write log {e}")

def start_log_thread() -> None:
    from pyile.lib.runtime.lifecycle import start_thread_if_needed
    start_thread_if_needed("log_writer", target_fn=_log_writer_thread)

def stop_log_thread() -> None:
    _stop_thread.clear()
    from pyile.lib.runtime.lifecycle import shutdown_thread
    shutdown_thread("log_writer")

def log_console(
        log_area: customtkinter.CTkTextbox, 
        message: str, 
        auto_scroll: bool = True
) -> None:
    try:
        log_area.insert(tk.END, message + "\n")
        if auto_scroll:
            log_area.see(tk.END)
    except Exception as e:
        log_error(f"Log error {e}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    _l_q.put(f"{timestamp} {message}\n")

def clear_console(log_area: tk.Text) -> None:
    try:
        log_area.delete("1.0", tk.END)
    except Exception as e:
        log_error(f"Clear console error {e}")

