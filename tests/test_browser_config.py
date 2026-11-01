"""Browser automation settings: off by default, validated like other settings."""
import os
import floter.config as config_module
from floter.config import FloterConfig

NAMES = ('BROWSER_AUTOMATION', 'BROWSER_CHANNEL', 'BROWSER_PROFILE_DIR', 'BROWSER_INPUT_SITES')

def test_defaults_keep_feature_off(monkeypatch):
    for name in NAMES: monkeypatch.delenv(name, raising=False)
    c = FloterConfig()
    assert c.BROWSER_AUTOMATION is False
    assert c.BROWSER_CHANNEL == 'msedge'
    assert c.BROWSER_PROFILE_DIR.endswith(os.path.join('.floter', 'browser-profile'))
    assert c.BROWSER_INPUT_SITES == ['youtube.com', 'google.com', 'wikipedia.org']

def test_values_are_parsed(monkeypatch, tmp_path):
    monkeypatch.setenv('BROWSER_AUTOMATION', '1')
    monkeypatch.setenv('BROWSER_CHANNEL', 'Brave')
    monkeypatch.setenv('BROWSER_PROFILE_DIR', str(tmp_path))
    monkeypatch.setenv('BROWSER_INPUT_SITES', ' YouTube.com , ,example.org')
    c = FloterConfig()
    assert (c.BROWSER_AUTOMATION, c.BROWSER_CHANNEL, c.BROWSER_PROFILE_DIR) == (True, 'brave', str(tmp_path))
    assert c.BROWSER_INPUT_SITES == ['youtube.com', 'example.org']

def test_invalid_channel_warns_and_uses_edge(monkeypatch):
    monkeypatch.setenv('BROWSER_CHANNEL', 'firefox')
    monkeypatch.setattr(config_module, 'CONFIG_WARNINGS', [])
    assert FloterConfig().BROWSER_CHANNEL == 'msedge'
    assert any('BROWSER_CHANNEL' in w for w in config_module.CONFIG_WARNINGS)
