"""Start the local OmniParser service on demand and stop it when FLOTER exits."""
import atexit
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from floter.workers import CancelledError

_started = None

def home():
    """Folder holding .tools/omniparser-env and scripts/omniparser_service.py."""
    configured = os.getenv('OMNIPARSER_HOME')
    if configured:
        return Path(configured)
    if not getattr(sys, 'frozen', False):
        return Path(__file__).resolve().parents[1]
    return None

def listening(host, port):
    try:
        with socket.create_connection((host, port), timeout=.5):
            return True
    except OSError:
        return False

def ensure_running(host, port, token_path, cancel, log, timeout=None):
    """Return once the service accepts connections, starting it if needed."""
    global _started
    if listening(host, port):
        return
    root = home()
    python = root / '.tools' / 'omniparser-env' / 'Scripts' / 'python.exe' if root else None
    script = root / 'scripts' / 'omniparser_service.py' if root else None
    if not python or not python.is_file() or not script.is_file():
        raise RuntimeError('OmniParser is not running and was not found. Set OMNIPARSER_HOME in '
                           '%USERPROFILE%\\.floter\\.env to the FLOTER source folder that contains .tools\\omniparser-env.')
    device = os.getenv('OMNIPARSER_DEVICE', 'cuda')
    if device not in ('cuda', 'cpu'):
        raise ValueError('OMNIPARSER_DEVICE must be cuda or cpu')
    logs = Path.home() / '.floter' / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    started_at = time.time()
    log('Starting the local OmniParser screen parser (the first start can take a minute)…')
    with open(logs / 'omniparser-service.log', 'ab') as out, open(logs / 'omniparser-service-errors.log', 'ab') as err:
        _started = subprocess.Popen([str(python), str(script), '--device', device, '--port', str(port),
                                     '--token-file', str(token_path)],
                                    cwd=str(root), stdout=out, stderr=err, shell=False,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    deadline = time.monotonic() + (timeout or float(os.getenv('OMNIPARSER_START_SECONDS', '180')))
    while True:
        if cancel is not None and cancel.wait(1):
            raise CancelledError('Navigation stopped')
        if _started.poll() is not None:
            raise RuntimeError('OmniParser stopped during startup; see %USERPROFILE%\\.floter\\logs\\omniparser-service-errors.log')
        # A token left by an earlier run does not count; wait for this run's token.
        fresh = token_path.is_file() and token_path.stat().st_mtime >= started_at
        if fresh and listening(host, port):
            log('OmniParser is ready.')
            return
        if time.monotonic() > deadline:
            raise TimeoutError('OmniParser did not become ready in time; check the OmniParser logs')

def stop():
    """Stop the service only if this FLOTER session started it."""
    global _started
    process, _started = _started, None
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            process.kill()

atexit.register(stop)
