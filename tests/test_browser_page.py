"""Pure page rules shared by the browser session and the agent validator."""
import pytest
from floter.tools.browser_page import url_allowed, input_host_allowed, blocked_reason, trim_elements, SNAPSHOT_JS

@pytest.mark.parametrize('url,ok', [
    ('https://www.youtube.com', True), ('https://example.com/a?b=1', True),
    ('http://127.0.0.1:8000/', True), ('http://localhost/x', True),
    ('http://example.com', False), ('file:///C:/Windows/win.ini', False),
    ('https://user:pw@example.com', False), ('javascript:alert(1)', False), ('https://', False)])
def test_url_allowed(url, ok):
    assert url_allowed(url) is ok

@pytest.mark.parametrize('url,ok', [
    ('https://www.youtube.com/results', True), ('https://youtube.com', True), ('https://m.youtube.com', True),
    ('https://notyoutube.com', False), ('https://youtube.com.evil.test', False), ('https://mail.google.com', True)])
def test_input_host_allowed(url, ok):
    assert input_host_allowed(url, ['youtube.com', 'google.com']) is ok

@pytest.mark.parametrize('label', ['Send', 'Send message', 'Buy now', 'Place order', 'Delete video', 'Sign out', 'Log out', 'Checkout'])
def test_outward_or_irreversible_controls_blocked(label):
    assert blocked_reason({'label': label, 'password': False})

def test_password_blocked_and_ordinary_controls_allowed():
    assert blocked_reason({'label': 'Enter code', 'password': True}) == 'password field'
    for label in ('Search', 'Shorts', 'Ed Sheeran - Shape of You', 'Posts', 'Sender info'):
        assert blocked_reason({'label': label, 'password': False}) is None

def test_trim_puts_visible_first_and_caps():
    raw = [{'id': i, 'in_viewport': i >= 500} for i in range(1000)]
    kept = trim_elements(raw, limit=300)
    assert len(kept) == 300
    assert [e['id'] for e in kept[:3]] == [500, 501, 502]
    assert all(e['in_viewport'] for e in kept)

def test_snapshot_script_tags_elements():
    assert 'data-floter-id' in SNAPSHOT_JS and 'data-floter-snap' in SNAPSHOT_JS
