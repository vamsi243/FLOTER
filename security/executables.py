"""Executable resolution never searches the process PATH or current directory."""
import os
import sys
from pathlib import Path
from floter.config import config
from floter.security.sandbox import GuardrailViolationError

def approved_roots():
    if sys.platform == 'win32':
        return [Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32',
                Path(os.environ.get('ProgramFiles', 'C:/Program Files')),
                Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')),
                Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Programs']
    return [Path('/usr/bin'), Path('/bin'), Path('/usr/local/bin'), Path('/Applications')]

def registered_runtime(binary_name):
    """Resolve a trusted App Paths registration behind a Windows launcher."""
    if sys.platform != 'win32' or Path(binary_name).name != binary_name:
        return None
    import winreg
    roots = [p.resolve() for p in approved_roots()]
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, 'Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\' + binary_name) as key:
                value = winreg.QueryValueEx(key, '')[0]
            path = Path(os.path.expandvars(value).strip('"')).resolve()
            if path.suffix.lower() == '.exe' and path.is_file() and any(path.is_relative_to(root) for root in roots):
                return path
        except (OSError, TypeError, ValueError):
            continue
    return None

def resolve_application(target):
    if target not in config.WHITELISTED_APPS:
        raise GuardrailViolationError('Application is not allowlisted')
    roots = [p.resolve() for p in approved_roots()]
    candidates = list(config.WHITELISTED_APPS[target])
    if sys.platform == 'win32':
        local = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
        candidates += {
            'vscode': [str(local / 'Programs/Microsoft VS Code/Code.exe')],
            'terminal': [str(roots[0] / 'WindowsPowerShell/v1.0/powershell.exe')],
        }.get(target, [])
    for candidate in candidates:
        path = Path(candidate)
        choices = [path] if path.is_absolute() else [root / path for root in roots]
        for choice in choices:
            resolved = choice.resolve()
            if not any(resolved.is_relative_to(root) for root in roots):
                continue
            if sys.platform == 'win32' and resolved.suffix.lower() != '.exe':
                continue
            if resolved.is_file():
                return resolved
    raise FileNotFoundError(f'No executable in trusted installation locations for {target}')
