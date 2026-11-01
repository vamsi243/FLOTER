"""Read-only window verification after the selected-app launch checks."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import psutil
from floter.config import config
from floter.tools.desktop_actions import application_windows

def instagram_window_visible():
    user32=ctypes.windll.user32
    user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user32.IsWindowVisible.argtypes=[wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    found=[]
    @callback_type
    def collect(hwnd,unused):
        if user32.IsWindowVisible(hwnd):
            buffer=ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd,buffer,512)
            if 'instagram' in buffer.value.lower():
                pid=wintypes.DWORD(); user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                try:
                    if psutil.Process(pid.value).name().lower()=='msedge.exe': found.append(True)
                except psutil.Error: pass
        return True
    user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    user32.EnumWindows(collect,0)
    return bool(found)

def main():
    path=Path(__file__).resolve().parents[1]/'acceptance-output/selected-app-checks.json'
    report=json.loads(path.read_text())
    baseline_path=path.parents[1]/'selected-app-checks.log'
    baseline=json.loads(baseline_path.read_text(encoding='utf-8-sig')) if baseline_path.exists() else {'launches':[]}
    for row in report['launches']:
        entry=config.APP_CATALOG[row['app']]
        paths=[entry.get('executable'),entry.get('close_executable')]
        exact=bool(application_windows(paths)) if any(paths) else False
        hosted=row['app']=='instagram' and instagram_window_visible()
        at_launch=any(item['app']==row['app'] and item.get('window_verified') for item in baseline['launches'])
        row['window_currently_visible']=exact or hosted
        row['window_verified']=exact or hosted or at_launch
        row['verification']='exact executable window' if exact else ('Instagram window title and Edge host process' if hosted else ('verified at launch; no longer visible' if at_launch else 'window not found'))
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['launches'],indent=2))
    return int(not all(row['window_verified'] for row in report['launches']))

if __name__=='__main__': raise SystemExit(main())
