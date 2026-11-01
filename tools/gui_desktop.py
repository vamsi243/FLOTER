"""Windows desktop adapter with pinned window identity and fresh target checks."""
import os
import time

def rectangle_tuple(rect):
    return (rect.left,rect.top,rect.right,rect.bottom)

class DesktopSession:
    def __init__(self, owner_pid=None):
        import ctypes
        try: ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except AttributeError: pass
        import pythoncom
        from pywinauto import Desktop
        self.com=pythoncom
        self.com.CoInitialize()
        self.desktop=Desktop(backend='uia')
        self.user32=ctypes.windll.user32
        from ctypes import wintypes
        self.user32.GetForegroundWindow.restype=wintypes.HWND
        self.user32.IsWindow.argtypes=[wintypes.HWND]
        self.user32.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
        self.user32.GetAncestor.restype=wintypes.HWND
        self.bound=None
        self.owner_pid=owner_pid or os.getpid()

    def windows(self):
        import psutil
        import ctypes
        from ctypes import wintypes
        result=[]
        self.user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        self.user32.IsWindowVisible.argtypes=[wintypes.HWND]
        self.user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        @callback_type
        def collect(handle,_):
            try:
                if not self.user32.IsWindowVisible(handle): return True
                title=ctypes.create_unicode_buffer(512)
                self.user32.GetWindowTextW(handle,title,512)
                if not title.value: return True
                pid=wintypes.DWORD()
                self.user32.GetWindowThreadProcessId(handle,ctypes.byref(pid))
                process=psutil.Process(pid.value)
                if process.pid in {os.getpid(),self.owner_pid}: return True
                name=process.name().lower()
                if name in {'cmd.exe','powershell.exe','pwsh.exe','windowsterminal.exe','consent.exe','credentialuibroker.exe'}: return True
                result.append({'handle':int(handle),'title':title.value[:200],'process':name})
            except (psutil.Error,RuntimeError): pass
            return True
        self.user32.EnumWindows(collect,0)
        return result[:80]

    def bind(self, handle):
        import psutil
        if handle not in {w['handle'] for w in self.windows()}:
            raise ValueError('Selected window is no longer available')
        self.bound=self.desktop.window(handle=handle).wrapper_object()
        self.pid=self.bound.process_id()
        self.created=psutil.Process(self.pid).create_time()
        self.focus(initial=True)

    def focus(self, initial=False):
        import psutil
        if self.user32.GetAsyncKeyState(0x1B)&0x8000:
            raise RuntimeError('Escape pressed: desktop navigation stopped')
        if not self.bound or not self.user32.IsWindow(self.bound.handle) or psutil.Process(self.pid).create_time()!=self.created:
            raise RuntimeError('Target application closed or changed')
        foreground=self.user32.GetForegroundWindow()
        if not initial and foreground != self.bound.handle:
            active=self.desktop.window(handle=foreground).wrapper_object()
            if active.process_id()!=self.owner_pid:
                raise RuntimeError('Another window took focus; navigation stopped')
        self.bound.set_focus()
        if self.user32.GetForegroundWindow()!=self.bound.handle:
            raise RuntimeError('Cannot focus target window')

    def observe(self):
        from PIL import ImageGrab
        self.focus()
        rect=self.bound.rectangle()
        if rect.width()<=0 or rect.height()<=0 or rect.width()*rect.height()>20_000_000:
            raise ValueError('Unsupported target window dimensions')
        bounds=(rect.left,rect.top,rect.right,rect.bottom)
        elements=[]; controls={}
        for control in self.bound.descendants()[:700]:
            try:
                if not control.is_visible() or not control.is_enabled(): continue
                info=control.element_info
                if info.control_type in {'Pane','Window','TitleBar'}: continue
                r=control.rectangle()
                if r.width()<=0 or r.height()<=0 or r.left<rect.left or r.top<rect.top or r.right>rect.right or r.bottom>rect.bottom: continue
                if getattr(info,'is_password',False): continue
                index=len(elements)
                elements.append({'id':index,'role':info.control_type,'label':control.window_text()[:300],
                    'box':[(r.left-rect.left)/rect.width(),(r.top-rect.top)/rect.height(),(r.right-rect.left)/rect.width(),(r.bottom-rect.top)/rect.height()]})
                controls[index]=(control,rectangle_tuple(r),control.window_text(),tuple(info.runtime_id or []))
            except Exception: continue
        return {'elements':elements,'controls':controls,'bounds':bounds,'image':ImageGrab.grab(bbox=bounds,all_screens=True),'time':time.monotonic()}

    def add_visual(self, observation, regions):
        for region in regions:
            observation['elements'].append(dict(region,id=len(observation['elements'])))

    def execute(self, observation, action):
        from PIL import ImageGrab, ImageChops, ImageStat
        from pywinauto import mouse
        self.focus()
        if time.monotonic()-observation['time']>180:
            raise RuntimeError('Observation expired; request navigation again')
        if rectangle_tuple(self.bound.rectangle())!=observation['bounds']:
            raise RuntimeError('Window moved or resized; stale coordinates rejected')
        element=next(e for e in observation['elements'] if e['id']==action['element'])
        current=ImageGrab.grab(bbox=observation['bounds'],all_screens=True)
        box=element['box']; width,height=current.size
        crop=(int(box[0]*width),int(box[1]*height),int(box[2]*width),int(box[3]*height))
        difference=ImageChops.difference(current.crop(crop).convert('RGB'),observation['image'].crop(crop).convert('RGB'))
        if max(ImageStat.Stat(difference).mean)>8:
            raise RuntimeError('Target appearance changed; stale action rejected')
        control=None
        if action['element'] in observation['controls']:
            control,rect,label,runtime=observation['controls'][action['element']]
            if rectangle_tuple(control.rectangle())!=rect or control.window_text()!=label or tuple(control.element_info.runtime_id or [])!=runtime or not control.is_enabled():
                raise RuntimeError('Accessible target changed; action rejected')
        if action['action']=='type':
            if control is None or getattr(control.element_info,'is_password',False):
                raise RuntimeError('Typing requires a non-password accessible field')
            # ValuePattern avoids keystroke syntax, shortcuts and implicit Enter.
            control.iface_value.SetValue(action['text'])
        elif action['action']=='click' and control is not None:
            try: invoke = control.iface_invoke
            except Exception:
                self._point_action(element,observation,'click',mouse)
            else: invoke.Invoke()
        else:
            self._point_action(element,observation,action['action'],mouse,action.get('direction'))

    def _point_action(self,element,observation,kind,mouse,direction=None):
        import ctypes
        from ctypes import wintypes
        l,t,r,b=observation['bounds']; box=element['box']
        x=round(l+(box[0]+box[2])*(r-l)/2); y=round(t+(box[1]+box[3])*(b-t)/2)
        self.user32.WindowFromPoint.argtypes=[wintypes.POINT]
        self.user32.WindowFromPoint.restype=wintypes.HWND
        hit=self.user32.WindowFromPoint(wintypes.POINT(x,y))
        if self.user32.GetAncestor(hit,2)!=self.bound.handle:
            raise RuntimeError('Target is covered by another window')
        if kind=='click': mouse.click(coords=(x,y))
        elif kind=='scroll': mouse.scroll(coords=(x,y),wheel_dist=3 if direction=='up' else -3)
        else: raise ValueError('Unsupported input')

    def close(self):
        self.com.CoUninitialize()
