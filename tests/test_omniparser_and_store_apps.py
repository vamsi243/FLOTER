"""OmniParser on-demand start and Store-app window matching across updates."""
import os
import threading
from unittest.mock import Mock
import pytest
from floter.tools import omniparser_launcher, desktop_actions

def test_running_service_is_not_restarted(monkeypatch):
    monkeypatch.setattr(omniparser_launcher, 'listening', lambda host, port: True)
    popen = Mock(); monkeypatch.setattr(omniparser_launcher.subprocess, 'Popen', popen)
    omniparser_launcher.ensure_running('127.0.0.1', 8766, None, threading.Event(), print)
    popen.assert_not_called()

def test_missing_environment_explains_setting(monkeypatch, tmp_path):
    monkeypatch.setattr(omniparser_launcher, 'listening', lambda host, port: False)
    monkeypatch.setenv('OMNIPARSER_HOME', str(tmp_path))
    with pytest.raises(RuntimeError, match='OMNIPARSER_HOME'):
        omniparser_launcher.ensure_running('127.0.0.1', 8766, tmp_path/'t', threading.Event(), print)

def test_stale_token_is_not_trusted(monkeypatch, tmp_path):
    (tmp_path/'.tools/omniparser-env/Scripts').mkdir(parents=True); (tmp_path/'.tools/omniparser-env/Scripts/python.exe').write_bytes(b'')
    (tmp_path/'scripts').mkdir(); (tmp_path/'scripts/omniparser_service.py').write_text('')
    token = tmp_path/'token'; token.write_text('old'); os.utime(token, (1, 1))
    monkeypatch.setenv('OMNIPARSER_HOME', str(tmp_path))
    monkeypatch.setattr(omniparser_launcher, 'listening', lambda host, port: False)
    process = Mock(); process.poll.return_value = None
    monkeypatch.setattr(omniparser_launcher.subprocess, 'Popen', Mock(return_value=process))
    monkeypatch.setattr(omniparser_launcher.Path, 'home', lambda: tmp_path)
    with pytest.raises(TimeoutError):
        omniparser_launcher.ensure_running('127.0.0.1', 8766, token, threading.Event(), print, timeout=1.5)
    omniparser_launcher.stop()
    process.terminate.assert_called_once()

def test_store_app_matches_any_version():
    entry = {'kind':'registered','target':'Claude_pzs8sxrjxfjjc!Claude',
             'executable':r'C:\Program Files\WindowsApps\Claude_2.9939.2.0_x64__pzs8sxrjxfjjc\app\claude.exe'}
    package = desktop_actions.store_package(entry)
    newer = os.path.normcase(r'C:\Program Files\WindowsApps\Claude_3.0.0.0_x64__pzs8sxrjxfjjc\app\claude.exe')
    other = os.path.normcase(r'C:\Program Files\WindowsApps\Evil_1.0.0.0_x64__pzs8sxrjxfjjc\app\claude.exe')
    assert desktop_actions.package_match(newer, [package])
    assert not desktop_actions.package_match(other, [package])
