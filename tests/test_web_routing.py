"""Websites, named browsers and low-risk confidence handling for web routes."""
import json
from unittest.mock import Mock
import pytest
from floter.config import config
from floter.tiers.jev_tier import JevReflexTier, JevDecision, JevActionEnum as Action, routing_choices
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tools import desktop_actions

def jev_response(selected, browser=None, browser_probability=.9, confidence=.9):
    probabilities = {key: 0. for key in routing_choices()}
    probabilities[selected] = confidence
    probabilities['advice'] += 1 - confidence
    answers = {'route': {'type':'choice','choice':selected,'probabilities':probabilities,'confidence':confidence}}
    if browser:
        answers['browser'] = {'type':'choice','choice':browser,'probabilities':{browser:browser_probability}}
    return {'answers':answers}

def test_common_web_apps_have_routes():
    choices = routing_choices()
    for site in ('gmail','youtube','google-drive','outlook'):
        assert choices['web:'+site][:2] == (Action.OPEN_WEB, site)
    assert choices['web:other'][0] == Action.OPEN_OTHER_WEB

@pytest.mark.parametrize('browser,probability,expected',[('brave',.9,'brave'),('brave',.4,None),(None,0,None)])
def test_browser_is_asked_in_the_same_request(monkeypatch,browser,probability,expected):
    monkeypatch.setattr('floter.tiers.jev_tier.available_browsers', lambda: ['brave','chrome'])
    transport = Mock(return_value=jev_response('web:gmail', browser, probability))
    monkeypatch.setattr('floter.tiers.jev_tier.request_json', transport)
    decision = JevReflexTier(api_key='fake').triage_and_route('Can you open Gmail on Brave browser?')
    questions = json.loads(transport.call_args.args[0].data)['questions']
    assert set(questions['browser']['criteria']) == {'default','brave','chrome'}
    assert (decision.action, decision.target, decision.browser) == (Action.OPEN_WEB, 'gmail', expected)

def test_open_site_in_named_browser(monkeypatch):
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.OPEN_WEB,'gmail',.7,1,True,'test',.7,browser='brave'))
    opened = Mock()
    monkeypatch.setattr(desktop_actions, 'open_url', opened)
    result = app.process_query('Can you open Gmail on Brave browser?')
    assert result['status'] == 'success'
    opened.assert_called_once_with(config.WHITELISTED_URL_MAP['gmail'], 'brave')
    assert app.session_context['last_browser'] == 'brave'

def test_uncertain_non_web_action_asks_to_rephrase_without_provider(monkeypatch):
    monkeypatch.setattr(config,'HERMES_API_KEY',''); monkeypatch.setattr(config,'OPENROUTER_API_KEY','')
    app = FloterOrchestrator()
    probabilities = {'gui:brave':.68,'app:brave':.2,'advice':.12}
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.GUI_NAVIGATE,'brave',.67,1,True,'test',.68,probabilities))
    result = app.process_query('do the thing in brave')
    assert result['status'] == 'needs_input'
    assert 'navigate inside Brave' in result['message'] and 'open the Brave app' in result['message']

@pytest.mark.parametrize('site,url',[('example.com','https://example.com'),('https://BBC.co.uk/news','https://bbc.co.uk/news'),('amazon',None)])
def test_other_site_address_or_search(monkeypatch,site,url):
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.OPEN_OTHER_WEB,None,.9,1,True,'test',.9))
    app.jev.extract_argument = Mock(return_value=site)
    opened = Mock(); search = Mock(); search.invoke.return_value = {'status':'success'}
    monkeypatch.setattr(desktop_actions,'open_url',opened); app.desktop_tools['web_search'] = search
    assert app.process_query('open '+site)['status'] == 'success'
    if url:
        opened.assert_called_once_with(url, None); search.invoke.assert_not_called()
    else:
        search.invoke.assert_called_once_with({'query':site,'browser':None}); opened.assert_not_called()

@pytest.mark.parametrize('url',['http://example.com','file:///C:/x','https://user:pw@example.com'])
def test_only_plain_https_urls_open(url):
    with pytest.raises(ValueError): desktop_actions.open_url(url)

def test_named_browser_launches_trusted_executable(monkeypatch, tmp_path):
    exe = tmp_path/'brave.exe'; exe.write_bytes(b'x')
    monkeypatch.setattr('floter.security.executables.resolve_application', lambda name: exe)
    popen = Mock(); monkeypatch.setattr(desktop_actions.subprocess,'Popen',popen)
    assert desktop_actions.open_url('https://mail.google.com','brave') == 'brave'
    assert popen.call_args.args[0] == [str(exe),'https://mail.google.com'] and popen.call_args.kwargs['shell'] is False

@pytest.mark.parametrize('probabilities,navigates',[
    ({'gui:claude':.75,'gui:current':.22,'advice':.03}, True),
    ({'gui:claude':.58,'gui:current':.35,'advice':.07}, True),
    ({'gui:claude':.55,'app:claude':.30,'advice':.15}, False)])
def test_split_between_navigation_targets_still_navigates(monkeypatch,probabilities,navigates):
    monkeypatch.setitem(config.WHITELISTED_APPS, 'claude', [])
    app = FloterOrchestrator()
    top = max(probabilities.values())
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.GUI_NAVIGATE,'claude',top,1,True,'test',top,probabilities))
    agent = Mock(); agent.return_value.run.return_value = {'status':'success','message':'done'}
    monkeypatch.setattr('floter.tools.gui_agent.GuiAgent', agent)
    result = app.process_query('click on co-work')
    assert agent.called == navigates
    assert result['status'] == ('success' if navigates else 'needs_input')
    if navigates:
        assert app.session_context['last_target'] == 'claude'
