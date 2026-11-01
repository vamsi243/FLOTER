"""Persistent UIA worker; hung native accessibility calls remain cancellable."""
import multiprocessing as mp
import os
import time
import uuid
from floter.workers import CancelledError

def _serve(pipe, owner_pid):
    from floter.tools.gui_desktop import DesktopSession
    desktop=DesktopSession(owner_pid)
    observation=None
    try:
        while True:
            operation,args=pipe.recv()
            try:
                if operation=='windows': value=desktop.windows()
                elif operation=='bind': value=desktop.bind(*args)
                elif operation=='observe':
                    observation=desktop.observe()
                    observation['snapshot']=uuid.uuid4().hex
                    value={k:v for k,v in observation.items() if k!='controls'}
                elif operation=='visual':
                    snapshot,regions=args
                    if not observation or observation['snapshot']!=snapshot: raise ValueError('Stale snapshot')
                    desktop.add_visual(observation,regions)
                    value=observation['elements']
                elif operation=='execute':
                    snapshot,action=args
                    if not observation or observation['snapshot']!=snapshot: raise ValueError('Stale snapshot')
                    current=observation; observation=None
                    value=desktop.execute(current,action)
                else: raise ValueError('Unsupported worker operation')
                pipe.send((True,value))
            except Exception as exc:
                pipe.send((False,str(exc)))
    except EOFError: pass
    finally: desktop.close(); pipe.close()

class DesktopWorker:
    def __init__(self,cancel):
        self.cancel=cancel
        context=mp.get_context('spawn')
        self.pipe,child=context.Pipe()
        self.process=context.Process(target=_serve,args=(child,os.getpid()),daemon=True)
        self.process.start(); child.close()

    def call(self,operation,*args):
        if self.cancel.is_set(): raise CancelledError('Navigation stopped')
        self.pipe.send((operation,args)); deadline=time.monotonic()+20
        while not self.pipe.poll(.05):
            if self.cancel.is_set(): raise CancelledError('Navigation stopped')
            if time.monotonic()>deadline: raise TimeoutError('Windows accessibility call timed out')
            if not self.process.is_alive(): raise RuntimeError('Desktop worker exited')
        success,value=self.pipe.recv()
        if not success: raise RuntimeError(value)
        return value

    def windows(self): return self.call('windows')
    def bind(self,handle): return self.call('bind',handle)
    def observe(self): return self.call('observe')
    def add_visual(self,observation,regions):
        observation['elements']=self.call('visual',observation['snapshot'],regions)
    def execute(self,observation,action): return self.call('execute',observation['snapshot'],action)
    def close(self):
        self.pipe.close()
        if self.process.is_alive(): self.process.terminate()
        self.process.join(2)
        if self.process.is_alive(): self.process.kill(); self.process.join(2)
        self.process.close()
