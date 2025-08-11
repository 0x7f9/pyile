from pyile.lib.runtime.internal.dataclasses import OSVERSIONINFOEXW, WindowsVersion

import sys
import ctypes
from typing import Optional, Tuple

def _get_rtl() -> Optional[Tuple[int, int, int]]:
    try:
        osvi = OSVERSIONINFOEXW()
        osvi.dwOSVersionInfoSize = ctypes.sizeof(OSVERSIONINFOEXW)
        if ctypes.windll.ntdll.RtlGetVersion(ctypes.byref(osvi)) == 0:
            return (osvi.dwMajorVersion, osvi.dwMinorVersion, osvi.dwBuildNumber)
    except Exception:
        pass
    return None

def get_windows_ver() -> WindowsVersion:
    ver = _get_rtl()
    if ver:
        return WindowsVersion(*ver)
    sys_ver = sys.getwindowsversion()
    return WindowsVersion(sys_ver.major, sys_ver.minor, sys_ver.build)

def is_windows_11() -> bool:
    v = get_windows_ver()
    return (v.major == 10 and v.build >= 22000) or v.major >= 11

