"""One Playwright-driven browser window with a FLOTER profile; lives inside the browser worker."""
import uuid
from pathlib import Path
from floter.tools.browser_page import (SNAPSHOT_JS, TEXT_ROLES, trim_elements, url_allowed,
                                       input_host_allowed, blocked_reason)

ACTION_TIMEOUT_MS = 8000
NAVIGATION_TIMEOUT_MS = 20000
BROWSER_NAMES = {'msedge': 'Microsoft Edge', 'chrome': 'Google Chrome', 'brave': 'Brave'}

def launch_options(channel):
    """Edge/Chrome through Playwright channels; Brave through its allowlisted brave.exe."""
    if channel == 'brave':
        from floter.security.executables import resolve_application
        return {'executable_path': str(resolve_application('brave'))}
    return {'channel': channel}

def launch_error(channel, exc):
    """Plain message for common launch failures; never includes a stack trace."""
    name, text = BROWSER_NAMES.get(channel, channel), str(exc)
    if 'is not found' in text or isinstance(exc, FileNotFoundError):
        return f'{name} is not installed. Install it or set BROWSER_CHANNEL to another installed browser.'
    if 'ProcessSingleton' in text or 'already in use' in text:
        return "FLOTER's browser profile is already in use; close the other FLOTER browser window."
    return f'Could not start {name} for browser automation ({type(exc).__name__}).'

class BrowserSession:
    def __init__(self, channel, profile_dir, input_sites):
        from playwright.sync_api import sync_playwright
        self.input_sites = list(input_sites)
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        try:
            # A persistent context keeps logins in FLOTER's profile only; no debugging port is opened.
            # launch_options raises FileNotFoundError when Brave is not installed; launch_error explains it.
            self.context = self._playwright.chromium.launch_persistent_context(
                profile_dir, headless=False, no_viewport=True, **launch_options(channel))
        except Exception as exc:
            self._playwright.stop()
            raise RuntimeError(launch_error(channel, exc)) from exc
        self.closed = False
        self.context.on('close', lambda _: setattr(self, 'closed', True))
        self.snapshot = self.snapshot_url = None
        self.elements = {}

    def page(self):
        """The most recently opened tab, so links that open a new tab are followed."""
        pages = [p for p in self.context.pages if not p.is_closed()]
        return pages[-1] if pages else self.context.new_page()

    def alive(self):
        return not self.closed

    def goto(self, url):
        if not url_allowed(url):
            raise ValueError('Only https addresses (or local http pages) can be opened')
        page = self.page()
        page.bring_to_front()
        page.goto(url, wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT_MS)
        self.snapshot = None
        return {'url': page.url, 'title': page.title()}

    def observe(self):
        page = self.page()
        page.wait_for_load_state('domcontentloaded', timeout=NAVIGATION_TIMEOUT_MS)
        snapshot = uuid.uuid4().hex
        elements = trim_elements(page.evaluate(SNAPSHOT_JS, snapshot))
        self.snapshot, self.snapshot_url = snapshot, page.url
        self.elements = {e['id']: e for e in elements}
        return {'snapshot': snapshot, 'url': page.url, 'title': page.title(), 'elements': elements}

    def execute(self, snapshot, action):
        if snapshot is None or snapshot != self.snapshot:
            raise RuntimeError('Page snapshot is stale; observe again')
        self.snapshot = None  # one action per observation
        page = self.page()
        if page.url != self.snapshot_url:
            raise RuntimeError('Page changed since it was observed; action rejected')
        kind = action['action']
        if kind == 'scroll':
            page.mouse.wheel(0, 700 if action['direction'] == 'down' else -700)
            return 'scrolled'
        if kind == 'back':
            page.go_back(wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT_MS)
            return 'back'
        element = self.elements.get(action.get('element'))
        if element is None:
            raise RuntimeError('Target element was not observed; action rejected')
        reason = blocked_reason(element)
        if reason:
            raise PermissionError('Blocked: ' + reason)
        if not input_host_allowed(page.url, self.input_sites):
            raise PermissionError('Input is not enabled for this site; add it to BROWSER_INPUT_SITES')
        if kind in {'fill', 'press_enter'} and element['role'] not in TEXT_ROLES:
            raise ValueError('Typing requires a text field')
        locator = page.locator(f'[data-floter-snap="{snapshot}"][data-floter-id="{element["id"]}"]')
        if locator.count() != 1:
            raise RuntimeError('Target element is gone; action rejected')
        if kind == 'click':
            locator.click(timeout=ACTION_TIMEOUT_MS)
        elif kind == 'fill':
            locator.fill(action['text'], timeout=ACTION_TIMEOUT_MS)
        elif kind == 'press_enter':
            locator.press('Enter', timeout=ACTION_TIMEOUT_MS)
        else:
            raise ValueError('Unsupported browser action')
        return kind

    def close(self):
        try:
            self.context.close()
        except Exception:
            pass
        self._playwright.stop()
