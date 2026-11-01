"""A busy or failing Gemini model hands over to the configured fallbacks, in order."""
import json
from unittest.mock import Mock
import pytest
from floter.config import config, model_chain
from floter.tiers.gemini_tier import GeminiMultimodalTier
from floter.tiers.hermes_tier import HermesAgentOrchestrator
from floter.tools.gui_agent import Reasoner
from floter.workers import CancelledError

def test_model_chain_keeps_order_and_drops_duplicates():
    assert model_chain('a', ['b', 'a', '', 'c']) == ['a', 'b', 'c']

def test_vision_falls_back_on_busy_model(monkeypatch):
    monkeypatch.setattr(config, 'GEMINI_FALLBACK_MODELS', ['backup-1', 'backup-2'])
    reply = {'candidates': [{'content': {'parts': [{'text': '{"analysis": "ok"}'}]}}]}
    transport = Mock(side_effect=[RuntimeError('HTTP Error 503'), RuntimeError('HTTP Error 404'), reply])
    monkeypatch.setattr('floter.tiers.gemini_tier.request_json', transport)
    assert GeminiMultimodalTier(api_key='k', model='primary').analyze_visual_and_logs('hi') == {'analysis': 'ok'}
    assert [call.args[0].full_url.split('/models/')[1].split(':')[0] for call in transport.call_args_list] == ['primary', 'backup-1', 'backup-2']

def test_vision_reports_failure_after_last_fallback(monkeypatch):
    monkeypatch.setattr(config, 'GEMINI_FALLBACK_MODELS', ['backup'])
    transport = Mock(side_effect=RuntimeError('HTTP Error 503'))
    monkeypatch.setattr('floter.tiers.gemini_tier.request_json', transport)
    with pytest.raises(RuntimeError, match='Gemini request failed'):
        GeminiMultimodalTier(api_key='k', model='primary').analyze_visual_and_logs('hi')
    assert transport.call_count == 2

def test_cancel_stops_fallbacks(monkeypatch):
    monkeypatch.setattr(config, 'GEMINI_FALLBACK_MODELS', ['backup'])
    transport = Mock(side_effect=CancelledError('stopped'))
    monkeypatch.setattr('floter.tiers.gemini_tier.request_json', transport)
    with pytest.raises(CancelledError):
        GeminiMultimodalTier(api_key='k', model='primary').analyze_visual_and_logs('hi')
    assert transport.call_count == 1

def test_reasoning_and_navigation_fall_back(monkeypatch):
    monkeypatch.setattr(config, 'HERMES_API_BASE', 'https://generativelanguage.googleapis.com/v1beta/openai')
    monkeypatch.setattr(config, 'HERMES_API_KEY', 'k')
    monkeypatch.setattr(config, 'HERMES_MODEL', 'primary')
    monkeypatch.setattr(config, 'REASONING_FALLBACK_MODELS', ['backup'])
    monkeypatch.delenv('GUI_MODEL', raising=False); monkeypatch.delenv('GUI_MODEL_API_BASE', raising=False)
    reply = lambda text: {'choices': [{'message': {'content': text}}]}
    hermes = Mock(side_effect=[RuntimeError('HTTP Error 503'), reply('answer')])
    monkeypatch.setattr('floter.tiers.hermes_tier.request_json', hermes)
    assert HermesAgentOrchestrator().execute_complex_plan('question')['analysis'] == 'answer'
    assert [json.loads(c.args[0].data)['model'] for c in hermes.call_args_list] == ['primary', 'backup']
    gui = Mock(side_effect=[RuntimeError('HTTP Error 404'), reply('{"window": 1}')])
    monkeypatch.setattr('floter.tools.gui_agent.request_json', gui)
    assert Reasoner(Mock()).call('system', {}) == {'window': 1}
    assert [json.loads(c.args[0].data)['model'] for c in gui.call_args_list] == ['primary', 'backup']

def _gui_provider(monkeypatch, transport):
    monkeypatch.setattr(config, 'HERMES_API_BASE', 'https://generativelanguage.googleapis.com/v1beta/openai')
    monkeypatch.setattr(config, 'HERMES_API_KEY', 'k')
    monkeypatch.setattr(config, 'HERMES_MODEL', 'primary')
    monkeypatch.setattr(config, 'REASONING_FALLBACK_MODELS', ['backup'])
    monkeypatch.delenv('GUI_MODEL', raising=False); monkeypatch.delenv('GUI_MODEL_API_BASE', raising=False)
    monkeypatch.setattr('floter.tools.gui_agent.request_json', transport)

def test_navigation_retries_primary_once_on_transient_failure(monkeypatch):
    from floter.tools.gui_agent import REQUEST_TIMEOUT
    reply = {'choices': [{'message': {'content': '{"window": 1}'}}]}
    gui = Mock(side_effect=[RuntimeError('Worker failed (TimeoutError: The read operation timed out)'), reply])
    _gui_provider(monkeypatch, gui)
    log = []
    assert Reasoner(Mock(), log.append).call('system', {}, 'choose the application window') == {'window': 1}
    assert [json.loads(c.args[0].data)['model'] for c in gui.call_args_list] == ['primary', 'primary']
    assert all(c.args[1] == REQUEST_TIMEOUT < 30 for c in gui.call_args_list)
    assert log == ['Asking primary to choose the application window…', 'primary failed (timed out); retrying once.',
                   'Asking primary to choose the application window…']

def test_navigation_reports_each_fallback_then_fails(monkeypatch):
    gui = Mock(side_effect=RuntimeError('Worker failed (HTTPError: HTTP Error 503: Service Unavailable)'))
    _gui_provider(monkeypatch, gui)
    log = []
    with pytest.raises(RuntimeError, match='503'):
        Reasoner(Mock(), log.append).call('system', {})
    assert [json.loads(c.args[0].data)['model'] for c in gui.call_args_list] == ['primary', 'primary', 'backup']
    assert 'primary failed (HTTP Error 503); trying backup.' in log

def test_navigation_cancel_skips_retries(monkeypatch):
    gui = Mock(side_effect=CancelledError('stopped'))
    _gui_provider(monkeypatch, gui)
    with pytest.raises(CancelledError):
        Reasoner(Mock()).call('system', {})
    assert gui.call_count == 1
