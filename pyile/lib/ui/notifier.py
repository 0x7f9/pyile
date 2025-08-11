from pyile.lib.runtime.lifecycle import start_thread_if_needed, shutdown_thread
from pyile.lib.utils.common import file_exists, get_project_root, join_path
from pyile.lib.utils.logging import log_error, log_debug, log_warning, log_info
from pyile.lib.runtime.internal.constants import (
    PARAM_DESTROY, PARAM_CLICKED, NIIF_NOSOUND, NIF_ICON, NIF_MESSAGE,
    NIF_TIP, NIF_INFO, NIM_ADD, NIM_MODIFY, NIM_DELETE, NIN_BALLOONSHOW,
    TITLE, NOTIFICATION_DELAY
)
from pyile.lib.utils.lazy import LazyInit

import threading
import time
import winsound
from queue import Queue, Empty, Full
from functools import partial
from typing import Optional, Callable, Any
from win32api import GetModuleHandle  # type: ignore
from win32gui import (  # type: ignore
    WNDCLASS, RegisterClass, CreateWindow, UpdateWindow, LoadImage,
    PumpWaitingMessages, DestroyWindow, UnregisterClass, PostQuitMessage, Shell_NotifyIcon
)
from winsound import SND_FILENAME, SND_ASYNC, MessageBeep
from win32con import (  # type: ignore
    WS_OVERLAPPED, WS_SYSMENU, CW_USEDEFAULT, LR_DEFAULTSIZE,
    IMAGE_ICON, WM_USER, LR_LOADFROMFILE
)

class NotificationManager(LazyInit):
    __slots__ = ( 
        "_n_q", "_is_running", "_thread_key", "_delay", 
        "_notification_sound_enabled", "_hwnd", "_hicon", 
        "_class_atom", "_click_callback", "_sound_lock", 
        "_sound_allowed",
    )
        
    def __init__(self) -> None:
        self._n_q  = Queue(maxsize=50)
        self._is_running = False
        self._thread_key = "notifier_thread"
        self._delay = NOTIFICATION_DELAY
        self._notification_sound_enabled = False
        self._hwnd = None
        self._hicon = None
        self._class_atom = None
        self._click_callback = None
        self._sound_lock = threading.Lock()
        self._sound_allowed = True

    def start(self):
        if not self._is_running:
            log_info("Starting notification manager")
            self._is_running = True
            start_thread_if_needed(self._thread_key, self._worker)

    def clear_queue(self) -> None:
        while not self._n_q .empty():
            try:
                item = self._n_q .get_nowait()
                self._n_q .task_done()
            except Empty:
                break

    def stop(self) -> None:
        log_info("Stopping notification manager")
        self._is_running = False
        self.clear_queue()
        shutdown_thread(self._thread_key)
        log_info("Notification manager stopped")

    def set_sound_enabled(self, enabled: bool) -> None:
        self._notification_sound_enabled = enabled

    def _worker(self) -> None:
        try:
            self._create_window()
        except Exception as e:
            log_error(f"Failed to initialize notification window: {e}")
            self._is_running = False
            return

        while self._is_running:
            try:
                data = self._n_q .get(timeout=0.1)
            except Empty:
                PumpWaitingMessages()
                continue

            if not self._is_running or data is None:
                self._n_q .task_done()
                break

            title, msg, on_click = data
            self._click_callback = on_click
            try:
                self._update(title, msg)
            except Exception as e:
                log_error(f"Notification update error: {e}")
            finally:
                self._n_q .task_done()

            PumpWaitingMessages()
            time.sleep(self._delay)

        self._destroy_window()
        log_debug("Notification worker thread exiting")

    def _create_window(self) -> None:
        wc = WNDCLASS()
        hinst = wc.hInstance = GetModuleHandle(None) # type: ignore
        wc.lpszClassName = str(TITLE)  # type: ignore
        wc.lpfnWndProc = partial(self.wnd_proc)  # type: ignore
        self._class_atom = RegisterClass(wc)

        style = WS_OVERLAPPED | WS_SYSMENU
        self._hwnd = CreateWindow(
            self._class_atom, None, style,
            0, 0, CW_USEDEFAULT, CW_USEDEFAULT,
            0, 0, hinst, None
        )
        UpdateWindow(self._hwnd)

        icon_path = join_path(get_project_root(levels_up=2), "assets", "images", "icon.ico")
        if file_exists(icon_path):
            icon_flags = LR_LOADFROMFILE | LR_DEFAULTSIZE
            self._hicon = LoadImage(hinst, icon_path, IMAGE_ICON, 0, 0, icon_flags)
        else:
            self._hicon = None

        flags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid = (self._hwnd, 0, flags, WM_USER + 20, self._hicon, "Pyile Notification")
        Shell_NotifyIcon(NIM_ADD, nid)  # type: ignore

    def _update(self, title: str, msg: str) -> None:
        try:
            Shell_NotifyIcon(NIM_MODIFY, (  # type: ignore
                self._hwnd, 0, NIF_INFO, WM_USER+20,
                self._hicon, "tooltip", title, 200, msg, NIIF_NOSOUND
            ))
        except Exception as e:
            log_error(f"Shell_NotifyIcon modify failed: {e}")

    def _destroy_window(self) -> None:
        try:
            if self._hwnd:
                Shell_NotifyIcon(NIM_DELETE, (self._hwnd, 0))  # type: ignore
                DestroyWindow(self._hwnd)
            if self._class_atom:
                UnregisterClass(self._class_atom, GetModuleHandle(None))
        except Exception as e:
            log_error(f"Error destroying notification window: {e}")
        finally:
            self._hwnd = None
            self._hicon = None
            self._class_atom = None

    def _allow_sound_again(self):
        # HACK: this is a small hack to prevent sound spam. 
        # the NIN_BALLOONSHOW flag seems to trigger when the banner
        # hits the notification manager bubble list, 
        # not actually shown to screen 

        time.sleep(4)
        with self._sound_lock:
            self._sound_allowed = True

    def _play_notification_sound(self):
        try:
            sound_path = join_path(get_project_root(levels_up=2), "assets", "sounds", "notification_sound.wav")
            if file_exists(sound_path):
                winsound.PlaySound(sound_path, SND_FILENAME | SND_ASYNC)
        except Exception as e:
            log_error(f"Could not play notification sound {e}")

    def wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int, **kwargs: Any) -> int:
        if msg != WM_USER + 20:
            return 0

        if lparam == PARAM_CLICKED:
            self._handle_click()
            return 0

        if lparam == PARAM_DESTROY:
            return 0

        if lparam == NIN_BALLOONSHOW:
            self._handle_balloon_show()
            return 0

        return 0

    def _handle_click(self):
        if not self._click_callback:
            return
        try:
            cb = self._click_callback
            self._click_callback = None
            cb()
        except Exception as e:
            log_error(f"Error in notification callback {e}")

    def _handle_balloon_show(self):
        if not self._notification_sound_enabled:
            return

        with self._sound_lock:
            if self._sound_allowed:
                self._play_notification_sound()
                self._sound_allowed = False
                threading.Thread(target=self._allow_sound_again, daemon=True).start()

    def _queue(self, title: str, msg: str, on_click: Optional[Callable] = None) -> None:
        if not self._is_running:
            return None
        
        data = (title, msg, on_click)
        try:
            self._n_q .put(data, timeout=0.1)
        except Full:
            log_warning("Notification queue full, dropping notification")

def trigger_notfication(title: str, msg: str, duration: Optional[int] = None, on_click: Optional[Callable] = None) -> None:
    nm = NotificationManager.get()
    nm._queue(title, msg, on_click)

