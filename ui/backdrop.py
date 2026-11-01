"""Optional Windows 11 backdrop with graceful fallback."""
import sys
import ctypes
from ctypes import wintypes

def apply_mica(window_id):
    if sys.platform != 'win32' or sys.getwindowsversion().build < 22621:
        return False
    try:
        dwm=ctypes.WinDLL('dwmapi',use_last_error=True)
        dwm.DwmSetWindowAttribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
        dwm.DwmSetWindowAttribute.restype=ctypes.c_long
        value=ctypes.c_int(2)
        return dwm.DwmSetWindowAttribute(int(window_id),38,ctypes.byref(value),ctypes.sizeof(value)) == 0
    except (OSError,AttributeError):
        return False
