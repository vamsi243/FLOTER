"""Jev offers browser:page only when enabled; web routes open in FLOTER's browser unless a browser is named."""
import json
from unittest.mock import Mock
import pytest
from floter.config import config
from floter.tiers.jev_tier import JevReflexTier, JevDecision, JevActionEnum as Action, routing_choices
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tools import desktop_actions

@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(config, 'BROWSER_AUTOMATION', True)

@pytest.fixture
def floter_browser(monkeypatch):
    worker = Mock()
    worker.call.side_effect = lambda cancel, op, url: {'url': url, 'title': 'Page'}
    monkeypatch.setattr('floter.tools.browser_worker.get_worker', Mock(return_value=worker))
    return worker

def test_route_only_offered_when_enabled(monkeypatch):
    monkeypatch.setattr(config, 'BROWSER_AUTOMATION', False)
    assert 'browser:page' not in routing_choices()
    monkeypatch.setattr(config, 'BROWSER_AUTOMATION', True)
    assert routing_choices()['browser:page'][0] == Action.BROWSER_NAVIGATE
    assert 'browser:page' in routing_choices()['web_search'][2]

def test_jev_instructions_mention_follow_ups(monkeypatch, enabled):
    probabilities = {key: 0. for key in routing_choices()}; probabilities['browser:page'] = 1.
    transport = Mock(return_value={'answers': {'route': {'type': 'choice', 'choice': 'browser:page',
                                                         'probabilities': probabilities, 'confidence': .95}}})
    monkeypatch.setattr('floter.tiers.jev_tier.request_json', transport)
    monkeypatch.setattr('floter.tiers.jev_tier.available_browsers', lambda: [])
    decision = JevReflexTier(api_key='fake').triage_and_route('play the second video')
    route = json.loads(transport.call_args.args[0].data)['questions']['route']
    assert 'browser_page' in route['instructions'] and 'browser:page' in route['criteria']
    assert decision.action == Action.BROWSER_NAVIGATE

def test_open_site_uses_floter_browser(enabled, floter_browser, monkeypatch):
    opened = Mock(); monkeypatch.setattr(desktop_actions, 'open_url', opened)
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.OPEN_WEB, 'youtube', .9, 1, True, 't', .9))
    result = app.process_query('open YouTube')
    assert result['status'] == 'success' and "FLOTER's browser" in result['message']
    floter_browser.call.assert_called_once_with(app._cancel, 'goto', config.WHITELISTED_URL_MAP['youtube'])
    opened.assert_not_called()
    assert app.session_context['browser_page'] == config.WHITELISTED_URL_MAP['youtube']

def test_named_browser_keeps_users_browser(enabled, floter_browser, monkeypatch):
    opened = Mock(); monkeypatch.setattr(desktop_actions, 'open_url', opened)
    app = FloterOrchestrator(); app.session_context['browser_page'] = 'https://www.youtube.com'
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.OPEN_WEB, 'gmail', .9, 1, True, 't', .9, browser='brave'))
    assert app.process_query('open Gmail in Brave')['status'] == 'success'
    opened.assert_called_once_with(config.WHITELISTED_URL_MAP['gmail'], 'brave')
    floter_browser.call.assert_not_called()
    assert 'browser_page' not in app.session_context

def test_web_search_uses_floter_browser(enabled, floter_browser):
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.WEB_SEARCH, None, .9, 1, True, 't', .9))
    app.jev.extract_argument = Mock(return_value='shape of you')
    assert app.process_query('search the web for shape of you')['status'] == 'success'
    floter_browser.call.assert_called_once_with(app._cancel, 'goto', desktop_actions.search_url('shape of you'))

def test_disabled_feature_keeps_old_behaviour(monkeypatch, floter_browser):
    monkeypatch.setattr(config, 'BROWSER_AUTOMATION', False)
    opened = Mock(); monkeypatch.setattr(desktop_actions, 'open_url', opened)
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.OPEN_WEB, 'youtube', .9, 1, True, 't', .9))
    assert app.process_query('open YouTube')['status'] == 'success'
    opened.assert_called_once_with(config.WHITELISTED_URL_MAP['youtube'], None)
    floter_browser.call.assert_not_called()

def test_follow_up_runs_browser_agent_with_navigation_family(enabled, monkeypatch):
    agent = Mock(); agent.run.return_value = {'status': 'success', 'message': 'Playing video', 'url': 'https://www.youtube.com/watch?v=2'}
    monkeypatch.setattr('floter.tools.browser_agent.BrowserAgent', Mock(return_value=agent))
    app = FloterOrchestrator()
    probabilities = {'browser:page': .5, 'gui:current': .4, 'advice': .1}
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.BROWSER_NAVIGATE, None, .5, 1, True, 't', .5, probabilities))
    result = app.process_query('play the second video')
    agent.run.assert_called_once_with('play the second video')
    assert result['status'] == 'success' and result['tier'] == 'Jev / Browser automation'
    assert app.session_context['browser_page'] == 'https://www.youtube.com/watch?v=2'

def test_follow_up_refused_when_disabled(monkeypatch):
    monkeypatch.setattr(config, 'BROWSER_AUTOMATION', False)
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.BROWSER_NAVIGATE, None, .95, 1, True, 't', .95))
    result = app.process_query('play the second video')
    assert result['status'] == 'error' and 'BROWSER_AUTOMATION' in result['error']

def test_shutdown_stops_browser(monkeypatch):
    stop = Mock(); monkeypatch.setattr('floter.tools.browser_worker.stop', stop)
    FloterOrchestrator().shutdown()
    stop.assert_called_once()
