"""Browser worker transport, cancellation and restart, using a fake session."""
import threading
import time
import pytest
from floter.tools import browser_worker
from floter.tools.browser_worker import BrowserWorker
from floter.workers import CancelledError

class FakeSession:
    def __init__(self, **kwargs):
        if kwargs.get('fail'): raise RuntimeError('Microsoft Edge is not installed.')
    def goto(self, url):
        if url == 'slow': time.sleep(2)
        return {'url': url, 'title': 'T'}
    def observe(self): return {'snapshot': 's', 'url': 'u', 'title': 't', 'elements': []}
    def execute(self, snapshot, action): raise PermissionError('Blocked: password field')
    def alive(self): return True
    def close(self): pass

FACTORY = __name__ + ':FakeSession'

def test_round_trip_and_worker_errors():
    worker = BrowserWorker(FACTORY, channel='msedge')
    try:
        assert worker.call(None, 'goto', 'https://a.test')['url'] == 'https://a.test'
        with pytest.raises(RuntimeError, match='password'):
            worker.call(None, 'execute', 's', {})
        with pytest.raises(RuntimeError, match='Unsupported'):
            worker.call(None, 'close')
    finally:
        worker.close()

def test_startup_failure_is_reported():
    with pytest.raises(RuntimeError, match='not installed'):
        BrowserWorker(FACTORY, fail=True)

def test_cancel_discards_late_reply():
    worker = BrowserWorker(FACTORY)
    cancel = threading.Event()
    try:
        threading.Timer(.3, cancel.set).start()
        with pytest.raises(CancelledError):
            worker.call(cancel, 'goto', 'slow')
        assert worker.call(None, 'goto', 'https://b.test')['url'] == 'https://b.test'
    finally:
        worker.close()

def test_manager_restarts_dead_worker(monkeypatch):
    monkeypatch.setattr(browser_worker, 'DEFAULT_FACTORY', FACTORY)
    first = browser_worker.get_worker()
    first.process.kill(); first.process.join(5)
    second = browser_worker.get_worker()
    try:
        assert second is not first and second.call(None, 'alive') is True
    finally:
        browser_worker.stop()
    assert browser_worker._worker is None

def test_frozen_smoke_test_uses_throwaway_profile(monkeypatch):
    from floter import app
    created = {}
    class FakeWorker:
        def __init__(self, **kwargs): created.update(kwargs)
        def call(self, cancel, operation): return True if operation == 'alive' else {'elements': []}
        def close(self): created['closed'] = True
    monkeypatch.setattr('floter.tools.browser_worker.BrowserWorker', FakeWorker)
    assert app.browser_smoke_test() == 0
    assert 'floter-browser-smoke-' in created['profile_dir'] and created['input_sites'] == [] and created['closed']
