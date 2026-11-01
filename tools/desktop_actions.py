"""Bounded LangChain tools: browser search and a verified Notepad editor."""
import ctypes
from ctypes import wintypes
import os
import subprocess
import time
from urllib.parse import urlencode
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from functools import wraps

def uia_thread(function):
    @wraps(function)
    def call(*args, **kwargs):
        import comtypes
        comtypes.CoInitialize()
        try:
            return function(*args, **kwargs)
        finally:
            comtypes.CoUninitialize()
    return call

class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    browser: str | None = Field(default=None, max_length=20)

class TypeInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

def search_url(query):
    query = query.strip()
    if not query or len(query) > 2000:
        raise ValueError('Search query must contain 1–2000 characters')
    return 'https://www.google.com/search?' + urlencode({'q':query})

def open_url(url, browser=None):
    """Open an https URL in an allowlisted browser, or the default browser when none is named."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only https website addresses can be opened')
    if browser:
        from floter.config import config
        from floter.security.executables import resolve_application
        if browser not in config.BROWSERS:
            raise ValueError('Unsupported browser')
        binary = resolve_application(browser)
        subprocess.Popen([str(binary), url], shell=False, cwd=str(binary.parent))
        return browser
    import webbrowser
    if not webbrowser.open(url, new=2):
        raise RuntimeError('The default browser did not accept the website')
    return 'default browser'

def site_url(name):
    """Turn a spoken site address into an https URL, or None when it is not an address."""
    import re
    text = name.strip().strip('"“”.,!?').lower()
    text = re.sub(r'^https?://', '', text)
    if re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}(?:/[^\s]*)?', text):
        return 'https://' + text
    return None

def web_search(query, browser=None):
    """Open a web search for the supplied context in the chosen or default browser."""
    url = search_url(query)
    used = open_url(url, browser)
    return {'status':'success','query':query,'url':url,'browser':used,'mode':'browser_search'}

def _message(hwnd, message, wparam=0, lparam=0):
    result = ctypes.c_size_t()
    send = ctypes.windll.user32.SendMessageTimeoutW
    send.argtypes = [wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM,wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
    send.restype = wintypes.LPARAM
    if not send(hwnd,message,wparam,lparam,2,2000,ctypes.byref(result)):
        raise RuntimeError('Notepad did not respond; no further input was sent')
    return result.value

def editor_text(hwnd):
    length = _message(hwnd, 0x000E)  # WM_GETTEXTLENGTH
    if length > 100000:
        raise ValueError('Notepad document is too large for this tool')
    buffer = ctypes.create_unicode_buffer(length + 1)
    _message(hwnd, 0x000D, length+1, ctypes.addressof(buffer))
    return buffer.value

class NotepadSession:
    """Remember one specific editor; never dispatch global keyboard shortcuts."""
    def __init__(self):
        self.window_handle = None
        self.editor_handle = None
        self.pid = None
        self.document_name = None

    @staticmethod
    def windows():
        from pywinauto import Desktop
        return [w for w in Desktop(backend='uia').windows(class_name='Notepad') if w.is_visible()]

    @uia_thread
    def open(self):
        from floter.security.executables import resolve_application
        from pathlib import Path
        import uuid
        directory = Path.home() / '.floter' / 'drafts'
        directory.mkdir(parents=True, exist_ok=True)
        document = directory / ('FLOTER-' + uuid.uuid4().hex[:10] + '.txt')
        with document.open('x', encoding='utf-8'):
            pass
        self.document_name = document.stem
        binary = resolve_application('notepad')
        subprocess.Popen([str(binary), str(document)], shell=False, cwd=str(binary.parent))
        deadline = time.monotonic()+8
        while time.monotonic() < deadline:
            windows = self.windows()
            candidates = [w for w in windows if self.document_name in w.window_text()]
            if len(candidates) == 1:
                try:
                    self.bind(candidates[0])
                    return 'Opened Notepad. Follow-up typing will use this editor.'
                except RuntimeError:
                    pass
            time.sleep(.15)
        raise RuntimeError('Notepad opened but its editor could not be identified. No typing will be performed.')

    def bind(self, window):
        import psutil
        if os.path.basename(psutil.Process(window.process_id()).exe()).lower() != 'notepad.exe':
            raise RuntimeError('Target is not Notepad')
        if not self.document_name or self.document_name not in window.window_text():
            raise RuntimeError('The selected Notepad document is not the FLOTER draft')
        editors = [e for e in window.descendants() if e.element_info.control_type in ('Edit','Document')
                   and e.element_info.class_name in ('Edit','RichEditD2DPT','RichEdit20W') and e.handle and e.is_visible()]
        if len(editors) != 1:
            raise RuntimeError('Could not uniquely identify the Notepad text editor')
        self.window_handle, self.editor_handle, self.pid = window.handle, editors[0].handle, window.process_id()

    @uia_thread
    def append(self, text):
        """Append literal text to the previously identified Notepad editor."""
        if not self.window_handle:
            raise RuntimeError('Ask FLOTER to open Notepad first so it can identify the target editor')
        from pywinauto import Desktop
        window = Desktop(backend='uia').window(handle=self.window_handle).wrapper_object()
        expected = (self.window_handle,self.editor_handle,self.pid)
        self.bind(window)
        if (self.window_handle,self.editor_handle,self.pid) != expected:
            self.window_handle = self.editor_handle = self.pid = None
            raise RuntimeError('The Notepad tab/editor changed. Ask FLOTER to open Notepad again')
        if not text.strip() or len(text) > 4000 or any(ord(c)<32 and c not in '\n\t\r' for c in text):
            raise ValueError('Invalid literal text')
        current = editor_text(self.editor_handle)
        addition = ('\r\n' if current and not current.endswith(('\n','\r')) else '') + text
        # EM_SETSEL and EM_REPLACESEL address this editor directly; no clipboard or global keys.
        utf16_length = len(current.encode('utf-16-le')) // 2
        _message(self.editor_handle, 0x00B1, utf16_length, utf16_length)
        buffer = ctypes.create_unicode_buffer(addition)
        _message(self.editor_handle, 0x00C2, 1, ctypes.addressof(buffer))
        if editor_text(self.editor_handle) != current + addition:
            raise RuntimeError('Notepad text could not be verified; it may have changed. Check the document before retrying')
        return {'status':'success','characters':len(text),'target':'Notepad','saved':False}

def desktop_tools(notepad):
    return {
        'web_search': StructuredTool.from_function(web_search, args_schema=SearchInput),
        'type_notepad': StructuredTool.from_function(notepad.append, name='type_notepad', args_schema=TypeInput),
    }

def package_match(path, packages):
    """True when an executable lives in a Store package folder (any version) of a registered app."""
    parts = os.path.normcase(path).split(os.sep)
    for name, publisher, executable in packages:
        if parts[-1] == executable and any(part.startswith(name + '_') and part.endswith('__' + publisher) for part in parts[:-1]):
            return True
    return False

def store_package(entry):
    """(package name, publisher id, exe name) for a registered Store app, so updates keep matching."""
    family = entry.get('target', '').split('!')[0]
    if entry.get('kind') != 'registered' or '_' not in family or not entry.get('executable'):
        return None
    name, publisher = family.rsplit('_', 1)
    return (os.path.normcase(name), os.path.normcase(publisher), os.path.normcase(os.path.basename(entry['executable'])))

def application_windows(executables, packages=()):
    """Find visible top-level windows by exact configured executable, never title alone."""
    import psutil
    expected = {os.path.normcase(os.path.realpath(p)) for p in executables if p}
    handles = []
    user32 = ctypes.windll.user32
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    @callback_type
    def collect(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            path = os.path.normcase(os.path.realpath(psutil.Process(pid.value).exe()))
            if pid.value != os.getpid() and (path in expected or package_match(path, packages)):
                handles.append(hwnd)
        except (psutil.Error, OSError):
            pass
        return True
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    if not user32.EnumWindows(collect, 0):
        raise RuntimeError('Windows could not enumerate application windows')
    return handles

def request_window_close(handle):
    user32 = ctypes.windll.user32
    user32.PostMessageW.argtypes = [wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    user32.IsWindow.argtypes = [wintypes.HWND]
    if not user32.PostMessageW(handle, 0x0010, 0, 0):  # WM_CLOSE: app owns save prompts
        raise RuntimeError('Windows refused the close request; no process was terminated')
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline and user32.IsWindow(handle):
        time.sleep(.05)
    return not bool(user32.IsWindow(handle))

def close_application(target, preferred_handle=None):
    from floter.config import config
    from floter.security.executables import resolve_application, registered_runtime
    if target not in config.WHITELISTED_APPS:
        raise ValueError('Application is not configured')
    entry = config.APP_CATALOG.get(target, {})
    executables = [entry.get('executable'), entry.get('close_executable')]
    try:
        resolved = resolve_application(target)
        executables.append(str(resolved))
        runtime = registered_runtime(resolved.name)
        if runtime:
            executables.append(str(runtime))
    except (FileNotFoundError, ValueError):
        pass
    package = store_package(entry)
    if not any(executables) and not package:
        raise RuntimeError('This app has a launch registration but no verified running executable; close it manually')
    windows = application_windows(executables, [package] if package else [])
    if preferred_handle in windows:
        windows = [preferred_handle]
    if not windows:
        raise RuntimeError('No matching open application window was found')
    if len(windows) != 1:
        raise RuntimeError('Multiple application windows are open. Close the intended window manually; no windows were closed')
    closed = request_window_close(windows[0])
    return {'status':'success', 'target':target, 'closed':closed,
            'message':'Window closed.' if closed else 'Close requested. Complete any save prompt in the application; it has not been force-closed.'}
