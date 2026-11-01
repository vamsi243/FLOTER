import json
from unittest.mock import Mock
import pytest
from floter.config import config
from floter.tiers.jev_tier import JevReflexTier, JevDecision, JevActionEnum as Action, routing_choices
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tools.mcp_tools import FastMCPToolRegistry as Tools

def response(selected='app:notepad', confidence=.97, probability=.98):
    probabilities = {key: 0. for key in routing_choices()}
    probabilities[selected] = probability
    probabilities['advice'] += 1 - probability
    return {'answers': {'route': {'type': 'choice', 'choice': selected, 'probabilities': probabilities,
                                  'confidence': confidence}}}

@pytest.mark.parametrize('text', ['Can you please open the notepad?', 'take a screenshot',
                                 'plan open notepad', 'snippy tools', 'list skills', 'write in notepad: hello'])
def test_every_prompt_goes_to_model_unchanged(monkeypatch, text):
    transport = Mock(return_value=response())
    monkeypatch.setattr('floter.tiers.jev_tier.request_json', transport)
    tier = JevReflexTier(api_key='fake', endpoint='https://ai-gateway.vercel.sh/typesafe')
    decision = tier.triage_and_route(text)
    request = transport.call_args.args[0]
    # Old Vercel endpoints migrate to the native TypeSafe API.
    assert request.full_url == 'https://api.typesafe.ai/v1/systemone'
    assert request.get_header('Authorization') == 'Bearer fake'
    assert json.loads(request.data)['model'] == 'jev-latest'
    assert json.loads(request.data)['state']['request'] == text
    assert decision.confidence == .97
    assert decision.probability == .98

@pytest.mark.parametrize('bad', [None, float('nan'), float('inf'), -1, 1.1, True, '0.9'])
def test_bad_or_missing_confidence_fails_closed(monkeypatch, bad):
    monkeypatch.setattr('floter.tiers.jev_tier.request_json', Mock(return_value=response(confidence=bad)))
    with pytest.raises(RuntimeError): JevReflexTier(api_key='fake').triage_and_route('open notepad')

def test_http_failure_never_falls_back(monkeypatch):
    monkeypatch.setattr('floter.tiers.jev_tier.request_json', Mock(side_effect=TimeoutError))
    with pytest.raises(RuntimeError): JevReflexTier(api_key='fake').triage_and_route('open notepad')

@pytest.mark.parametrize('query', ['plan open notepad', 'snippy tools', 'list skills',
                                  'write in notepad: hello', 'show storage'])
def test_orchestrator_cannot_bypass_jev(monkeypatch, query):
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(side_effect=RuntimeError('Unavailable'))
    app.hermes.execute_complex_plan = Mock()
    assert app.process_query(query)['status'] == 'error'
    app.jev.triage_and_route.assert_called_once_with(query)
    app.hermes.execute_complex_plan.assert_not_called()

@pytest.mark.parametrize('confidence,probability,executed', [(1,1,True),(.8,1,False),(1,.8,False)])
def test_only_confident_simple_actions_autoexecute(monkeypatch, confidence, probability, executed):
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.LAUNCH_APP,'notepad',confidence,1,True,'test',probability))
    app.hermes.execute_complex_plan = Mock(return_value={'analysis':'Please clarify'})
    app.hermes.ensure_configured = Mock()  # Simulate a configured advisory provider.
    launch = Mock(return_value='Opened Notepad')
    monkeypatch.setattr(app.notepad, 'open', launch)
    result = app.process_query('Can you bring up Notepad?')
    # Uncertain actions ask the user to rephrase; they are never guessed or sent to the advisor.
    assert result['status'] == ('success' if executed else 'needs_input')
    assert launch.called == executed
    app.hermes.execute_complex_plan.assert_not_called()

def test_unsafe_storage_does_not_scan(monkeypatch):
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.INSPECT_STORAGE,None,1,1,False,'unsafe',1))
    scan = Mock()
    monkeypatch.setattr(Tools, 'inspect_storage_all_drives', scan)
    assert app.process_query('storage')['status'] == 'blocked'
    scan.assert_not_called()

def test_native_contract(monkeypatch):
    body = response(confidence=.97)
    transport = Mock(return_value=body)
    monkeypatch.setattr('floter.tiers.jev_tier.request_json', transport)
    tier = JevReflexTier(api_key='fake',endpoint='https://api.typesafe.ai/v1/systemone')
    assert tier.triage_and_route('open notepad').confidence == .97
    assert json.loads(transport.call_args.args[0].data)['model'] == 'jev-latest'

def test_cancel_after_jev_reply_prevents_action(monkeypatch):
    app = FloterOrchestrator()
    def reply(query):
        app._cancel.set()
        return JevDecision(Action.LAUNCH_APP,'notepad',1,1,True,'test',1)
    app.jev.triage_and_route = reply
    launch = Mock()
    monkeypatch.setattr(app.notepad, 'open', launch)
    assert app.process_query('open notepad')['status'] == 'cancelled'
    launch.assert_not_called()
