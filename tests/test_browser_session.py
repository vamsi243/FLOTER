"""Real-browser checks against a local page; opt in with FLOTER_BROWSER_TESTS=1."""
import importlib.util
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from floter.tools.browser_session import launch_error

FIXTURE = b'''<!doctype html><title>Fixture</title>
<input id=q type=search aria-label="Search" placeholder="Search"> <button>Go</button>
<input type=password aria-label="Password"> <button>Send message</button>
<p id=out></p>
<ol><li><a href="/watch?v=1">Result one</a></li><li><a href="/watch?v=2">Result two</a></li></ol>
<a href="/popup" target="_blank">Open in new tab</a>
<div style="height:3000px"></div><a href="/far">Far link</a>
<script>q.addEventListener('keydown', e => { if (e.key === 'Enter') out.textContent = 'Results for ' + q.value; });</script>'''

def test_launch_error_messages():
    assert 'Microsoft Edge is not installed' in launch_error('msedge', Exception("Chromium distribution 'msedge' is not found at C:\\x"))
    assert 'BROWSER_CHANNEL' in launch_error('chrome', Exception("Chromium distribution 'chrome' is not found"))
    assert 'already in use' in launch_error('msedge', Exception('ProcessSingleton: profile in use'))
    assert launch_error('msedge', ValueError('boom')) == 'Could not start Microsoft Edge for browser automation (ValueError).'
    assert 'Brave is not installed' in launch_error('brave', FileNotFoundError('No executable in trusted installation locations for brave'))

def test_launch_options_per_browser(monkeypatch, tmp_path):
    from floter.tools.browser_session import launch_options
    brave = tmp_path / 'brave.exe'
    monkeypatch.setattr('floter.security.executables.resolve_application', lambda target: brave if target == 'brave' else None)
    assert launch_options('brave') == {'executable_path': str(brave)}
    assert launch_options('msedge') == {'channel': 'msedge'}
    assert launch_options('chrome') == {'channel': 'chrome'}

needs_browser = pytest.mark.skipif(os.getenv('FLOTER_BROWSER_TESTS') != '1' or importlib.util.find_spec('playwright') is None,
                                   reason='Set FLOTER_BROWSER_TESTS=1 with Playwright and the browser in FLOTER_BROWSER_TEST_CHANNEL (default msedge) installed')
CHANNEL = os.getenv('FLOTER_BROWSER_TEST_CHANNEL', 'msedge')

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = FIXTURE if self.path == '/' else b'<title>' + self.path.encode() + b'</title><a href="/">Home</a>'
        self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass

@pytest.fixture(scope='module')
def site():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_address[1]}'
    server.shutdown()

@pytest.fixture
def session(tmp_path):
    from floter.tools.browser_session import BrowserSession
    s = BrowserSession(CHANNEL, str(tmp_path / 'profile'), ['127.0.0.1'])
    yield s
    s.close()

def by_label(observation, label):
    return next(e for e in observation['elements'] if e['label'] == label)

@needs_browser
def test_observe_lists_controls_in_page_order(session, site):
    session.goto(site + '/')
    obs = session.observe()
    labels = [e['label'] for e in obs['elements']]
    assert labels.index('Result one') < labels.index('Result two')
    assert by_label(obs, 'Search')['role'] == 'searchbox'
    assert by_label(obs, 'Password')['password'] is True
    assert by_label(obs, 'Far link')['in_viewport'] is False and labels[-1] == 'Far link'

@needs_browser
def test_fill_and_enter_then_stale_snapshot(session, site):
    session.goto(site + '/')
    obs = session.observe(); box = by_label(obs, 'Search')['id']
    session.execute(obs['snapshot'], {'action': 'fill', 'element': box, 'text': 'shape of you', 'reason': 'r'})
    with pytest.raises(RuntimeError, match='stale'):
        session.execute(obs['snapshot'], {'action': 'press_enter', 'element': box, 'reason': 'r'})
    obs = session.observe()
    session.execute(obs['snapshot'], {'action': 'press_enter', 'element': by_label(obs, 'Search')['id'], 'reason': 'r'})
    assert session.page().inner_text("#out") == 'Results for shape of you'

@needs_browser
def test_navigation_after_observe_rejects_action(session, site):
    session.goto(site + '/')
    obs = session.observe()
    session.page().goto(site + '/other')
    with pytest.raises(RuntimeError, match='changed'):
        session.execute(obs['snapshot'], {'action': 'click', 'element': by_label(obs, 'Result one')['id'], 'reason': 'r'})

@needs_browser
def test_blocked_and_password_controls_rejected(session, site):
    session.goto(site + '/')
    obs = session.observe()
    with pytest.raises(PermissionError, match='irreversible'):
        session.execute(obs['snapshot'], {'action': 'click', 'element': by_label(obs, 'Send message')['id'], 'reason': 'r'})
    obs = session.observe()
    with pytest.raises(PermissionError, match='password'):
        session.execute(obs['snapshot'], {'action': 'fill', 'element': by_label(obs, 'Password')['id'], 'text': 'x', 'reason': 'r'})

@needs_browser
def test_input_only_on_allowed_sites(tmp_path, site):
    from floter.tools.browser_session import BrowserSession
    s = BrowserSession(CHANNEL, str(tmp_path / 'other-profile'), ['example.com'])
    try:
        s.goto(site + '/')
        obs = s.observe()
        with pytest.raises(PermissionError, match='BROWSER_INPUT_SITES'):
            s.execute(obs['snapshot'], {'action': 'click', 'element': by_label(obs, 'Result one')['id'], 'reason': 'r'})
    finally:
        s.close()

@needs_browser
def test_new_tab_becomes_current_page(session, site):
    session.goto(site + '/')
    obs = session.observe()
    with session.context.expect_page() as opened:
        session.execute(obs['snapshot'], {'action': 'click', 'element': by_label(obs, 'Open in new tab')['id'], 'reason': 'r'})
    opened.value.wait_for_load_state()
    assert session.observe()['url'].endswith('/popup')

@needs_browser
@pytest.mark.parametrize('url', ['http://example.com', 'file:///C:/Windows/win.ini'])
def test_goto_rejects_disallowed_urls(session, url):
    with pytest.raises(ValueError):
        session.goto(url)

@needs_browser
def test_closed_window_reported(tmp_path):
    from floter.tools.browser_session import BrowserSession
    s = BrowserSession(CHANNEL, str(tmp_path / 'closing-profile'), [])
    assert s.alive() is True
    s.context.close()
    assert s.alive() is False
    s.close()
