"""Page-model rules for browser automation; importable without Playwright."""
import re
from urllib.parse import urlparse

MAX_ELEMENTS = 300
LOOPBACK = {'127.0.0.1', 'localhost', '::1'}
TEXT_ROLES = {'textbox', 'searchbox', 'combobox'}
# Irreversible or outward-facing controls; the agent never acts on them.
BLOCKED_LABEL = re.compile(r'\b(send|post|publish|buy|purchase|pay|checkout|place order|delete|remove|'
                           r'unsubscribe|sign out|log ?out)\b', re.IGNORECASE)

# Collects visible, enabled interactive elements in document order and tags them for later lookup.
# Labels only: field values are never read.
SNAPSHOT_JS = r'''(snap) => {
  const selector = 'a[href],button,input,textarea,select,summary,[role=button],[role=link],[role=tab],' +
    '[role=menuitem],[role=option],[role=searchbox],[role=combobox],[role=textbox],[contenteditable=""],[contenteditable=true]';
  const out = []; let id = 0;
  const vh = window.innerHeight, vw = window.innerWidth;
  for (const el of document.querySelectorAll(selector)) {
    const r = el.getBoundingClientRect(), style = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || style.visibility === 'hidden' || style.display === 'none') continue;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') continue;
    const tag = el.tagName.toLowerCase(), type = (el.getAttribute('type') || '').toLowerCase();
    let role = el.getAttribute('role') || ({a: 'link', button: 'button', select: 'combobox', textarea: 'textbox', summary: 'button'})[tag] || '';
    if (tag === 'input' && !role) role = ({search: 'searchbox', button: 'button', submit: 'button', checkbox: 'checkbox', radio: 'radio'})[type] || 'textbox';
    if (el.isContentEditable && !role) role = 'textbox';
    const label = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('title') ||
      el.getAttribute('placeholder') || el.getAttribute('alt') || '').replace(/\s+/g, ' ').trim().slice(0, 150);
    if (!label && !['textbox', 'searchbox', 'combobox'].includes(role)) continue;
    el.setAttribute('data-floter-id', String(id));
    el.setAttribute('data-floter-snap', snap);
    out.push({id, role, tag, label, password: type === 'password', top: Math.round(r.top + window.scrollY),
              in_viewport: r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw});
    id++;
  }
  return out;
}'''

def url_allowed(url):
    """Any https site, or http on loopback for local pages; never file: or embedded credentials."""
    parsed = urlparse(url)
    if parsed.username or parsed.password or not parsed.hostname:
        return False
    return parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname in LOOPBACK)

def input_host_allowed(url, sites):
    host = (urlparse(url).hostname or '').lower()
    return any(host == site or host.endswith('.' + site) for site in sites)

def blocked_reason(element):
    if element.get('password'):
        return 'password field'
    if BLOCKED_LABEL.search(element.get('label', '')):
        return 'control label suggests an irreversible or outward-facing action'
    return None

def trim_elements(raw, limit=MAX_ELEMENTS):
    """Elements on screen first, then the rest in document order; ids are kept for lookup."""
    return ([e for e in raw if e.get('in_viewport')] + [e for e in raw if not e.get('in_viewport')])[:limit]
