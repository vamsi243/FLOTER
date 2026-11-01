import json
from unittest.mock import Mock
import pytest
from floter.app_catalog import load_catalog, ENABLED_APPLICATIONS, launch_registered
from floter.config import config
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tiers.jev_tier import JevActionEnum as Action, JevDecision, routing_choices
from floter.tools import desktop_actions

def test_catalog_filters_unrequested_apps_and_urls(tmp_path):
    payload={'applications':{
        'whatsapp':{'name':'WhatsApp','kind':'registered','target':'5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App'},
        'unrequested':{'name':'Other','kind':'registered','target':'Other.App!App'},
        'instagram':{'name':'Instagram','kind':'registered','target':'https://example.com'},
    }}
    path=tmp_path/'apps.json'; path.write_text(json.dumps(payload))
    assert set(load_catalog(path))=={'whatsapp'}
    assert len(ENABLED_APPLICATIONS)==9
    assert {'claude','codex'} <= ENABLED_APPLICATIONS

def test_launch_uses_exact_argument_vector(monkeypatch):
    launch=Mock()
    monkeypatch.setattr('floter.app_catalog.subprocess.Popen',launch)
    entry={'name':'WhatsApp','kind':'registered','target':'5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App'}
    launch_registered(entry)
    assert launch.call_args.args[0][1]=='shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App'
    assert launch.call_args.kwargs['shell'] is False

def test_desktop_chatgpt_and_website_are_separate(monkeypatch):
    app=FloterOrchestrator()
    app.jev.triage_and_route=Mock(return_value=JevDecision(Action.OPEN_WEB,'chatgpt',1,1,True,'test',1))
    website=Mock(return_value='Opened website')
    launch=Mock()
    monkeypatch.setattr('floter.tools.mcp_tools.FastMCPToolRegistry.open_website',website)
    monkeypatch.setattr('floter.tools.mcp_tools.FastMCPToolRegistry.launch_application',launch)
    assert app.process_query('open ChatGPT website')['status']=='success'
    website.assert_called_once_with('chatgpt', None)
    launch.assert_not_called()

@pytest.mark.parametrize('windows,preferred,should_close', [([],None,False),([11,22],None,False),([11,22],22,True),([11],None,True)])
def test_close_requires_a_single_identified_window(monkeypatch,windows,preferred,should_close):
    monkeypatch.setattr(desktop_actions,'application_windows',lambda paths, packages=(): windows)
    request=Mock(return_value=False)
    monkeypatch.setattr(desktop_actions,'request_window_close',request)
    if should_close:
        result=desktop_actions.close_application('notepad',preferred)
        assert result['closed'] is False
        assert 'save prompt' in result['message']
        request.assert_called_once_with(preferred or windows[0])
    else:
        with pytest.raises(RuntimeError): desktop_actions.close_application('notepad',preferred)
        request.assert_not_called()

@pytest.mark.parametrize('confidence',[1,.5])
def test_tab_request_does_not_close_whole_app_or_call_hermes(monkeypatch,confidence):
    app=FloterOrchestrator()
    app.jev.triage_and_route=Mock(return_value=JevDecision(Action.UNSUPPORTED_TAB,None,confidence,1,True,'test',confidence))
    close=Mock(); monkeypatch.setattr(desktop_actions,'close_application',close)
    app.hermes.execute_complex_plan=Mock()
    result=app.process_query('close the tab on Notepad')
    assert result['status']=='error' and 'individual tabs' in result['error']
    close.assert_not_called()
    app.hermes.execute_complex_plan.assert_not_called()

def test_close_uses_registered_runtime_behind_launcher(monkeypatch,tmp_path):
    runtime=tmp_path/'packaged-notepad.exe'
    monkeypatch.setattr('floter.security.executables.registered_runtime',lambda name:runtime)
    windows=Mock(return_value=[11])
    monkeypatch.setattr(desktop_actions,'application_windows',windows)
    monkeypatch.setattr(desktop_actions,'request_window_close',lambda handle:True)
    assert desktop_actions.close_application('notepad')['closed'] is True
    assert str(runtime) in windows.call_args.args[0]

def test_successful_search_reports_completion(monkeypatch):
    completed=Mock(); app=FloterOrchestrator(on_completed=completed)
    app.jev.triage_and_route=Mock(return_value=JevDecision(Action.WEB_SEARCH,None,1,1,True,'test',1))
    app.desktop_tools['web_search']=Mock()
    app.desktop_tools['web_search'].invoke.return_value={'status':'success'}
    result=app.process_query('search for Sydney trains')
    completed.assert_called_once_with('search for Sydney trains', result)
