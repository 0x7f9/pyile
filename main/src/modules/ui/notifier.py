import os
import time
import threading
import winsound
from win32api import *
from win32gui import *
from winsound import SND_FILENAME, SND_ASYNC
from win32con import WS_OVERLAPPED, WS_SYSMENU, CW_USEDEFAULT, CW_USEDEFAULT, LR_DEFAULTSIZE, IMAGE_ICON, WM_USER

PARAM_DESTROY = 1028
PARAM_CLICKED = 1029

# removes the default notification sound
NIIF_NOSOUND = 0x00000010

class notifer:
    thread = False

    # added on_click callback function from https://github.com/vardecab/win10toast-click 
    @staticmethod
    def _decorator(func, callback=None):
        """
        :param func: callable to decorate
        :param callback: callable to run on mouse click within notification window
        :return: callable
        """
        def inner(*args, **kwargs):
            kwargs.update({'callback': callback})
            # func(*args, **kwargs)  
            # added return function to reduce errors
            return func(*args, **kwargs)  
        return inner

    
    def notify(self, title, msg, duration, on_click):
        print("Notification triggered")

        wc = WNDCLASS()
        hinst = wc.hInstance = GetModuleHandle(None)
        wc.lpszClassName = str("Pyile")
        # wc.lpfnWndProc = message_map # simple mapping
        wc.lpfnWndProc = self._decorator(self.wnd_proc, on_click) 
        classAtom = RegisterClass(wc)
        style = WS_OVERLAPPED | WS_SYSMENU
        hwnd = CreateWindow(classAtom, None, style,
                                 0, 0, CW_USEDEFAULT, 
                                 CW_USEDEFAULT, 
                                 0, 0, hinst, None
        )
        UpdateWindow(hwnd)
        
        # icon
        iconPathName = os.path.abspath(os.path.join("main\\src\\modules\\ui\\images\\icon.ico"))
        icon_flags = LR_LOADFROMFILE | LR_DEFAULTSIZE
        hicon = LoadImage(hinst, iconPathName, IMAGE_ICON, 0, 0, icon_flags)
        flags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid = (hwnd, 0, flags, WM_USER+20, hicon, "Pyile Notification")
        Shell_NotifyIcon(NIM_ADD, nid)
        Shell_NotifyIcon(NIM_MODIFY, (hwnd, 0, NIF_INFO, WM_USER+20,
                                      hicon,"tooltip",title,200,msg,NIIF_NOSOUND)
        )
        # new notification sound
        winsound.PlaySound("main\\src\\modules\\ui\\sounds\\notification_sound.wav", SND_FILENAME | SND_ASYNC)
        
        PumpMessages()
        time.sleep(duration)
        DestroyWindow(hwnd)
        UnregisterClass(wc.lpszClassName, None)
        notifer.thread = False 


    def on_destroy(self, hwnd):
        try:
            nid = (hwnd, 0)
            Shell_NotifyIcon(NIM_DELETE, nid)
            PostQuitMessage(0) 
            return 0
        except:
            pass


    def thread_start(self, title, msg, duration, on_click):
        if notifer.thread:
            # prevent more than one notfication thread at once
            return
        else:
            notifer.thread = True 
            print("Starting new notification thread")
            notification_thread = threading.Thread(target=self.notify, args=(title, msg, duration, on_click))
            notification_thread.start()
            notification_thread.join()
            # print(notification_thread, "STOP")


    def wnd_proc(self, hwnd, msg, wparam, lparam, **kwargs):
        if lparam == PARAM_CLICKED:
            # callback goes here
            if kwargs.get('callback'):
                kwargs.pop('callback')()
            self.on_destroy(hwnd)
            return 0    

        elif lparam == PARAM_DESTROY:
            self.on_destroy(hwnd) 
            return 0    

        return 0


def trigger_notfication(title, msg, duration, on_click):
    start=notifer()
    start.thread_start(title, msg, duration, on_click)

