"""Long-lived browser process; the window persists across requests until FLOTER exits."""
import importlib
import multiprocessing as mp
import threading
import time
from floter.workers import CancelledError

CALL_TIMEOUT = 30
START_TIMEOUT = 60
DEFAULT_FACTORY = 'floter.tools.browser_session:BrowserSession'
OPERATIONS = {'goto', 'observe', 'execute', 'alive'}

def _serve(pipe, factory, kwargs):
    session = None
    try:
        try:
            module, name = factory.split(':')
            session = getattr(importlib.import_module(module), name)(**kwargs)
        except Exception as exc:
            pipe.send((0, False, str(exc)))
            return
        pipe.send((0, True, 'ready'))
        while True:
            seq, operation, args = pipe.recv()
            try:
                if operation not in OPERATIONS:
                    raise ValueError('Unsupported browser operation')
                pipe.send((seq, True, getattr(session, operation)(*args)))
            except Exception as exc:
                pipe.send((seq, False, str(exc)))
    except (EOFError, OSError):
        pass
    finally:
        if session is not None:
            try: session.close()
            except Exception: pass
        pipe.close()

class BrowserWorker:
    def __init__(self, factory=DEFAULT_FACTORY, **kwargs):
        context = mp.get_context('spawn')
        self.pipe, child = context.Pipe()
        self.process = context.Process(target=_serve, args=(child, factory, kwargs), daemon=True)
        self.process.start(); child.close()
        self._seq, self._closed = 0, False
        try:
            self._receive(0, None, START_TIMEOUT, 'Browser did not start within 60 seconds')
        except Exception:
            self.close()
            raise

    def _receive(self, seq, cancel, timeout, message):
        deadline = time.monotonic() + timeout
        while True:
            if cancel is not None and cancel.is_set():
                raise CancelledError('Browser task stopped')
            if time.monotonic() > deadline:
                self.close()
                raise TimeoutError(message)
            if self.pipe.poll(.05):
                try:
                    reply_seq, success, value = self.pipe.recv()
                except EOFError as exc:
                    raise RuntimeError('Browser worker exited') from exc
                if reply_seq != seq:
                    continue  # late reply from a cancelled call
                if not success:
                    raise RuntimeError(value)
                return value
            if not self.process.is_alive():
                raise RuntimeError('Browser worker exited')

    def call(self, cancel, operation, *args):
        if self._closed:
            raise RuntimeError('Browser worker is closed')
        if cancel is not None and cancel.is_set():
            raise CancelledError('Browser task stopped')
        self._seq += 1
        self.pipe.send((self._seq, operation, args))
        return self._receive(self._seq, cancel, CALL_TIMEOUT, 'Browser did not respond within 30 seconds')

    def healthy(self):
        if self._closed or not self.process.is_alive():
            return False
        try:
            return self.call(None, 'alive') is True
        except Exception:
            return False

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.pipe.close()  # the worker closes the browser when its pipe ends
        self.process.join(5)
        if self.process.is_alive(): self.process.terminate(); self.process.join(2)
        if self.process.is_alive(): self.process.kill(); self.process.join(2)
        self.process.close()

_lock = threading.Lock()
_worker = None

def get_worker(cancel=None, log=lambda message: None):
    """Shared browser worker; relaunched if the user closed the window or it stopped responding."""
    global _worker
    from floter.config import config
    with _lock:
        if _worker is not None and not _worker.healthy():
            _worker.close(); _worker = None
        if _worker is None:
            log("Starting FLOTER's browser…")
            _worker = BrowserWorker(DEFAULT_FACTORY, channel=config.BROWSER_CHANNEL,
                                    profile_dir=config.BROWSER_PROFILE_DIR, input_sites=config.BROWSER_INPUT_SITES)
        return _worker

def stop():
    global _worker
    with _lock:
        if _worker is not None:
            _worker.close(); _worker = None
