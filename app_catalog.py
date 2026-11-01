"""Explicit, user-owned application registrations; never search arbitrary PATH."""
import json
import os
from pathlib import Path
import re
import subprocess

CATALOG_PATH = Path.home() / '.floter' / 'applications.json'
ENABLED_APPLICATIONS = {
    'notepad-plus-plus', 'antigravity-ide', 'whatsapp', 'instagram',
    'microsoft-store', 'chatgpt', 'codex', 'gemini', 'claude'
}

def load_catalog(path=CATALOG_PATH):
    if not path.is_file():
        return {}
    if path.stat().st_size > 2_000_000:
        raise ValueError('Application catalog is too large')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    result = {}
    for name, entry in data.get('applications', {}).items():
        if name not in ENABLED_APPLICATIONS:
            continue
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', name):
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str):
            continue
        kind, target = entry.get('kind'), entry.get('target', '')
        if not isinstance(target, str) or len(target) > 1000 or any(ord(c)<32 for c in target):
            continue
        if kind == 'exe' and Path(target).is_absolute() and Path(target).suffix.lower() == '.exe':
            result[name] = entry
        elif kind == 'registered' and re.fullmatch(r'[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+', target):
            result[name] = entry
    return result

def launch_registered(entry):
    if entry['kind'] == 'exe':
        binary = Path(entry['target'])
        if not binary.is_file():
            raise FileNotFoundError('Configured application moved or was removed; refresh the application inventory')
        subprocess.Popen([str(binary)], shell=False, cwd=str(binary.parent))
    else:
        explorer = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'explorer.exe'
        subprocess.Popen([str(explorer), 'shell:AppsFolder\\' + entry['target']], shell=False, cwd=str(explorer.parent))
    return f"Launch requested: {entry['name']}"
