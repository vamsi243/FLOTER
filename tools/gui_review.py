"""One-use, expiring desktop action review while the navigation worker waits."""
import secrets
import threading
import time
from floter.workers import CancelledError

class GuiReview:
    def __init__(self, callback, cancel):
        self.callback,self.cancel=callback,cancel
        self.lock=threading.Lock(); self.event=threading.Event(); self.pending=None

    def ask(self,title,detail,hide=True):
        """hide: minimize FLOTER after approval because screen observation or input follows."""
        token='gui:'+secrets.token_urlsafe(24)
        with self.lock:
            self.event.clear(); self.accepted=False
            self.pending=(token,time.monotonic()+120)
        self.callback({'token':token,'gui':True,'title':title,'detail':detail,'hide':hide})
        try:
            while not self.event.wait(.1):
                if self.cancel.is_set(): raise CancelledError('Navigation stopped')
                with self.lock:
                    if not self.pending or time.monotonic()>self.pending[1]:
                        raise CancelledError('Desktop action approval expired')
            if not self.accepted or self.cancel.is_set(): raise CancelledError('Desktop action rejected')
        finally:
            with self.lock: self.pending=None
            self.callback({'token':token,'gui':True,'clear':True})

    def decide(self,token,approved):
        with self.lock:
            if not self.pending or not secrets.compare_digest(token,self.pending[0]) or time.monotonic()>self.pending[1]:
                return False
            self.accepted=bool(approved); self.pending=None; self.event.set()
            return True
