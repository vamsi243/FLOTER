"""Check wheel contents and start the frozen application outside its source tree."""
import os
import argparse
from pathlib import Path
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--bundle-dir', type=Path, default=root / 'dist' / 'FLOTER')
bundle = parser.parse_args().bundle_dir.resolve()
from PyInstaller.archive.readers import CArchiveReader
camera_code = CArchiveReader(str(bundle / 'FLOTER.exe')).open_embedded_archive('PYZ.pyz').extract('floter.tools.camera')
assert camera_code == compile((root / 'tools/camera.py').read_text(encoding='utf-8'), camera_code.co_filename, 'exec'), 'Frozen camera source is stale'
for module, source in [('floter.ui.bridge','ui/bridge.py'),('floter.tools.gui_agent','tools/gui_agent.py'),('floter.tools.gui_worker','tools/gui_worker.py')]:
    code=CArchiveReader(str(bundle/'FLOTER.exe')).open_embedded_archive('PYZ.pyz').extract(module)
    assert code == compile((root/source).read_text(encoding='utf-8'),code.co_filename,'exec'), 'Stale frozen module: '+module
wheel = sorted((root / 'dist').glob('*.whl'), key=lambda p:p.stat().st_mtime)[-1]
with zipfile.ZipFile(wheel) as archive:
    names = set(archive.namelist())
    for resource in ('floter/app_catalog.py', 'floter/ui/orb.qml', 'floter/ui/RobotFace.qml', 'floter/ui/Camera.qml', 'floter/tools/camera.py', 'floter/assets/branding/floter.ico', 'floter/assets/branding/floter-logo.png'):
        assert resource in names, resource
    assert not any(name.endswith('.env') for name in names)
    assert any(name.endswith('/LICENSE') for name in names), 'Wheel MIT license missing'
for name in ('LICENSE', 'README.md', 'CONFIGURATION.md', 'ARCHITECTURE.md', 'FEATURES.md',
             'codeexplainer.md', 'INSTRUCTION_MANUAL.md', 'RELEASE_CHECKLIST.md', 'CLEANUP.md', '.env.example'):
    assert (bundle / '_internal' / name).is_file(), f'Missing bundled documentation: {name}'
for asset in ('floter.ico', 'floter-logo.png'):
    assert (bundle / '_internal/floter/assets/branding' / asset).read_bytes() == (root / 'assets/branding' / asset).read_bytes(), f'Stale branding: {asset}'
for resource in ('orb.qml', 'RobotFace.qml', 'Camera.qml'):
    assert (bundle / '_internal' / 'floter' / 'ui' / resource).read_bytes() == (root / 'ui' / resource).read_bytes(), f'Stale bundled UI: {resource}'
for name in ('applications.json', 'applications.before-selected-apps.json', 'acceptance-output'):
    assert not (bundle / '_internal' / name).exists(), 'Private machine catalog/report included'
for path in bundle.rglob('*'):
    if path.is_file():
        assert path.name != '.env' and not (path.name.startswith('.env.') and path.name != '.env.example'), 'Private dotenv file included'
        assert path.suffix.lower() not in {'.pfx', '.p12'}, 'Private signing material included'
        assert path.name not in {'settings.bin','omniparser.token'}, 'Private user settings included'
assert not (bundle / '_internal' / 'icuuc.dll').exists(), 'Foreign ICU DLL shadows Windows ICU'
import importlib.util
if importlib.util.find_spec('playwright'):
    assert (bundle / '_internal' / 'playwright' / 'driver' / 'node.exe').is_file(), 'Playwright driver missing from bundle'
with tempfile.TemporaryDirectory() as directory:
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    env.pop('PYTHONPATH', None)
    executable = str(bundle / 'FLOTER.exe')
    subprocess.run([executable, '--smoke-test'], cwd=directory, env=env, timeout=45, check=True)
    subprocess.run([executable, '--worker-smoke-test'], cwd=directory, env=env, timeout=45, check=True)
    subprocess.run([executable, '--gui-worker-smoke-test'], cwd=directory, env=env, timeout=45, check=True)
    if importlib.util.find_spec('playwright'):
        subprocess.run([executable, '--browser-worker-smoke-test'], cwd=directory, env=env, timeout=90, check=True)
    subprocess.run([executable, '--camera-smoke-test'], cwd=directory, env=env, timeout=45, check=True)
    sample = root / 'acceptance-output' / 'synthetic-command.wav'
    if sample.is_file():
        import json
        voice_report = root / 'acceptance-output' / 'packaged-voice.json'
        voice_env = dict(env, STT_ENGINE='faster-whisper', WHISPER_DEVICE='auto', WHISPER_MODEL_PATH=str(bundle / '_internal' / 'models' / 'faster-whisper-small.en'))
        subprocess.run([executable, '--diagnostics', '--transcribe', str(sample), '--expected',
                        'can you please open the notepad', '--output', str(voice_report)],
                       cwd=directory, env=voice_env, timeout=90, check=True)
        assert json.loads(voice_report.read_text())['transcription']['expected_exact_match'], 'Frozen Whisper recognition failed'
    report = Path(directory) / 'missing-snippy.json'
    absent_env = dict(env, SNIPPY_URL='', SNIPPY_COMMAND='C:/nonexistent-floter-test/Snippy.exe')
    result = subprocess.run([executable, '--diagnostics', '--snippy', '--output', str(report)], cwd=directory, env=absent_env, timeout=30)
    assert result.returncode == 1 and report.exists(), 'Packaged Snippy diagnostics missing or invalid'

print('Wheel resources and frozen startup passed.')
