"""Run before every git push: fails if files Git would commit contain your keys.

    python scripts/check_secrets.py

Checks every tracked or untracked-but-not-ignored file for the actual key values in
%USERPROFILE%\\.floter\\.env (and a source-folder .env), plus common API-key patterns.
Prints file names only, never the secrets.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r'AIza[0-9A-Za-z_\-]{30,}|\bsk-[A-Za-z0-9]{20,}|vck_[A-Za-z0-9]{10,}|Bearer [A-Za-z0-9._\-]{25,}'
                     r'|ghp_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY')

def secret_values():
    values = set()
    for env in (Path.home() / '.floter' / '.env', ROOT / '.env'):
        if env.is_file():
            for line in env.read_text(encoding='utf-8').splitlines():
                key, _, value = line.partition('=')
                if not line.lstrip().startswith('#') and ('KEY' in key.upper() or 'TOKEN' in key.upper()) and len(value.strip()) >= 12:
                    values.add(value.strip())
    token = Path.home() / '.floter' / 'omniparser.token'
    if token.is_file():
        values.add(token.read_text().strip())
    return values

def main():
    listed = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    values, problems = secret_values(), []
    for name in listed:
        path = ROOT / name
        if not path.is_file() or name.startswith('THIRD_PARTY_NOTICES/'):
            continue
        text = path.read_bytes().decode('utf-8', errors='ignore')
        if any(value in text for value in values):
            problems.append(f'{name}: contains one of your real keys')
        elif PATTERN.search(text):
            problems.append(f'{name}: looks like it contains an API key')
    for name in ('.env', 'applications.json'):
        if name in listed:
            problems.append(f'{name}: private file is not ignored')
    for problem in problems:
        print('BLOCK', problem)
    print(f'Checked {len(listed)} files; {len(problems)} problem(s).')
    return 1 if problems else 0

if __name__ == '__main__':
    sys.exit(main())
