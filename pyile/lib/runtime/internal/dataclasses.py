import winerror # type: ignore
import ctypes
from ctypes import wintypes
from typing import NamedTuple

class OSVERSIONINFOEXW(ctypes.Structure):
    _fields_ = [
        ("dwOSVersionInfoSize", wintypes.DWORD),
        ("dwMajorVersion",      wintypes.DWORD),
        ("dwMinorVersion",      wintypes.DWORD),
        ("dwBuildNumber",       wintypes.DWORD),
        ("dwPlatformId",        wintypes.DWORD),
        ("szCSDVersion",        wintypes.WCHAR * 128),
        ("wServicePackMajor",   wintypes.WORD),
        ("wServicePackMinor",   wintypes.WORD),
        ("wSuiteMask",          wintypes.WORD),
        ("wProductType",        wintypes.BYTE),
        ("wReserved",           wintypes.BYTE),
    ]


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength",               wintypes.DWORD),
        ("lpSecurityDescriptor",  wintypes.LPVOID),
        ("bInheritHandle",        wintypes.BOOL)
    ]


class Rec(ctypes.Structure):
    _fields_ = [
        ("hash_value",         ctypes.c_uint64),
        ("flags",              ctypes.c_uint64)
    ]
    
    
class WindowsVersion(NamedTuple):
    major: int
    minor: int
    build: int
    
    def __str__(self) -> str:
        if self.major == 10 and self.build >= 22000:
            return "Windows 11"
        if self.major == 10:
            return "Windows 10"
        if self.major >= 11:
            return f"Windows {self.major}"
        return f"Windows {self.major}.{self.minor}"

