from pyile.lib.runtime.internal.dataclasses import SECURITY_ATTRIBUTES

import ctypes
from ctypes import wintypes

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

CancelIoEx = _kernel32.CancelIoEx
CancelIoEx.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
CancelIoEx.restype = wintypes.BOOL

CreateFileW = _kernel32.CreateFileW
CreateFileW.argtypes = [
    wintypes.LPCWSTR, 
    wintypes.DWORD, 
    wintypes.DWORD,
    ctypes.POINTER(SECURITY_ATTRIBUTES), 
    wintypes.DWORD,
    wintypes.DWORD, 
    wintypes.HANDLE
]
CreateFileW.restype = wintypes.HANDLE

ReadDirectoryChangesW = _kernel32.ReadDirectoryChangesW
ReadDirectoryChangesW.argtypes = [
    wintypes.HANDLE,     
    wintypes.LPVOID,   
    wintypes.DWORD,         
    wintypes.BOOL,          
    wintypes.DWORD,          
    wintypes.LPVOID,          
    wintypes.LPVOID,       
    wintypes.LPVOID          
]
ReadDirectoryChangesW.restype = wintypes.BOOL

InitializeSecurityDescriptor = _advapi32.InitializeSecurityDescriptor
InitializeSecurityDescriptor.argtypes = [
    wintypes.LPVOID, 
    wintypes.DWORD
]
InitializeSecurityDescriptor.restype  = wintypes.BOOL

SetSecurityDescriptorDacl = _advapi32.SetSecurityDescriptorDacl
SetSecurityDescriptorDacl.argtypes = [
    wintypes.LPVOID, 
    wintypes.BOOL, 
    wintypes.LPVOID, 
    wintypes.BOOL
]
SetSecurityDescriptorDacl.restype  = wintypes.BOOL