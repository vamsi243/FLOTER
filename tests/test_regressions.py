import os
import json
import threading
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock
import pytest
from floter.config import config, FloterConfig
from floter.security.sandbox import SafeFileSystem, GuardrailViolationError
from floter.tools.mcp_tools import FastMCPToolRegistry as Tools
from floter.tiers.jev_tier import JevReflexTier, JevActionEnum as Action, JevDecision
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tiers.gemini_tier import GeminiMultimodalTier
from floter.tiers.hermes_tier import HermesAgentOrchestrator

@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    for name in ('JEV_API_KEY', 'GEMINI_API_KEY', 'HERMES_API_KEY', 'OPENROUTER_API_KEY'):
        monkeypatch.setattr(config, name, '')
    monkeypatch.setattr(config, 'HOME_DIR', tmp_path)
    monkeypatch.setattr(config, 'SNIPPY_CACHE_DIR', tmp_path / 'cache')

@pytest.mark.parametrize('query,target', [('open chrome','chrome'),('open brave','brave'),('open vs code','vscode'),('open calculator','calculator'),('open youtube','youtube'),('open github','github')])
def test_app_commands_require_jev(query,target):
    with pytest.raises(RuntimeError, match='Local routing is disabled'):
        JevReflexTier().triage_and_route(query)

def test_storage_requires_jev():
    with pytest.raises(RuntimeError):
        JevReflexTier().triage_and_route('extract system storage info from all drives')

@pytest.mark.parametrize('query', ['open brave and chrome', 'open encoded file', 'start notepad with commands'])
def test_no_offline_guess(query):
    with pytest.raises(RuntimeError): JevReflexTier().triage_and_route(query)

@pytest.mark.parametrize('query', ['look at this screen','what is on my screen'])
def test_vision_requires_jev(query):
    with pytest.raises(RuntimeError): JevReflexTier().triage_and_route(query)

@pytest.mark.parametrize('query', ['rm file', 'taskkill /f', 'format c:'])
def test_no_local_keyword_classifier(query):
    with pytest.raises(RuntimeError): JevReflexTier().triage_and_route(query)

def route(app, action):
    app.jev.triage_and_route = Mock(return_value=JevDecision(action,None,1,1,True,'test',1))

def test_config_reads_environment_on_instantiation(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'new-key')
    assert FloterConfig().GEMINI_API_KEY == 'new-key'

@pytest.mark.parametrize('binary', [False,True])
def test_no_overwrite(tmp_path,binary):
    file=tmp_path/'report'
    write=SafeFileSystem.write_new_bytes if binary else SafeFileSystem.write_new_text
    content=b'original' if binary else 'original'
    write(file,content)
    with pytest.raises(GuardrailViolationError): write(file,content)
    assert file.read_bytes()==b'original'

def test_bounded_reads(tmp_path):
    file=tmp_path/'large.log'; file.write_text('a'*100)
    assert SafeFileSystem.read_text(file,5).startswith('aaaaa\n...')

@pytest.mark.parametrize('name', ['../escape','a/b','a\\b','C:escape'])
def test_report_traversal(name):
    with pytest.raises(GuardrailViolationError):
        Tools.generate_notepad_document(name,'text')

def test_prose_not_treated_as_shell():
    Tools.generate_notepad_document('notes','Please format this report and drop the heading.')

def test_capture_failure_is_not_fake(monkeypatch):
    from PIL import ImageGrab
    monkeypatch.setattr(ImageGrab,'grab',Mock(side_effect=OSError('No display')))
    with pytest.raises(OSError): Tools.snippy_capture()
    assert not config.SNIPPY_CACHE_DIR.exists()

def test_unknown_app_never_launches(monkeypatch):
    launch=Mock(); monkeypatch.setattr('subprocess.Popen',launch)
    with pytest.raises(GuardrailViolationError): Tools.launch_application('anything.exe')
    launch.assert_not_called()

def test_empty_query():
    assert FloterOrchestrator().process_query(' ')['status']=='ignored'

def test_triage_error_resets_state(monkeypatch):
    states=[]; app=FloterOrchestrator(on_state_change=states.append)
    monkeypatch.setattr(app.jev,'triage_and_route',Mock(side_effect=ValueError('broken')))
    assert app.process_query('hello')['status']=='error'
    assert states[-1]=='Idle'
    assert not app._lock.locked()

def test_vision_actually_called(monkeypatch):
    app=FloterOrchestrator(); app.gemini.api_key='test'
    route(app, Action.ESCALATE_TO_GEMINI)
    monkeypatch.setattr(Tools,'snippy_capture',Mock(return_value='screen.png'))
    analyze=Mock(return_value={'analysis':'actual'}); monkeypatch.setattr(app.gemini,'analyze_visual_and_logs',analyze)
    result=app.process_query('what is on my screen')
    assert result['tier']=='Gemini'
    analyze.assert_called_once()

def test_missing_provider_does_not_capture(monkeypatch):
    capture=Mock(); monkeypatch.setattr(Tools,'snippy_capture',capture)
    app=FloterOrchestrator(); route(app, Action.ESCALATE_TO_GEMINI)
    assert app.process_query('what is on my screen')['status']=='error'
    capture.assert_not_called()

def test_single_flight(monkeypatch):
    app=FloterOrchestrator(); entered=threading.Event(); release=threading.Event()
    route(app, Action.ESCALATE_TO_HERMES)
    def reply(query):
        entered.set(); release.wait(5); return {'analysis':'done'}
    monkeypatch.setattr(app.hermes,'execute_complex_plan',reply)
    monkeypatch.setattr(app.hermes,'ensure_configured',Mock())
    worker=threading.Thread(target=app.process_query,args=('hello',)); worker.start()
    try:
        assert entered.wait(3)
        assert app.process_query('second')['status']=='busy'
        assert not app.process_query_async('third')
    finally:
        release.set(); worker.join(5)

def test_no_fake_gemini():
    with pytest.raises(RuntimeError): GeminiMultimodalTier().analyze_visual_and_logs('test')

def test_no_fake_hermes():
    with pytest.raises(RuntimeError): HermesAgentOrchestrator().execute_complex_plan('hello')

class Response:
    def __init__(self,data): self.data=json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self, limit=-1): return self.data if limit < 0 else self.data[:limit]

@pytest.fixture(autouse=True)
def mock_safe_http_transport(monkeypatch):
    # Preserve the request assertions while exercising the shared bounded reader.
    opener = Mock()
    opener.open.side_effect = lambda request, timeout: __import__('urllib.request', fromlist=['urlopen']).urlopen(request, timeout=timeout)
    monkeypatch.setattr('urllib.request.build_opener', Mock(return_value=opener))

def test_local_hermes_request(monkeypatch):
    monkeypatch.setattr(config,'HERMES_API_BASE','http://localhost:11434/v1')
    request=Mock(return_value=Response({'choices':[{'message':{'content':'Proposed plan'}}]}))
    monkeypatch.setattr('urllib.request.urlopen',request)
    assert HermesAgentOrchestrator().execute_complex_plan('hello')['mode']=='advisory'
    assert request.call_args.args[0].full_url.endswith('/v1/chat/completions')
    assert json.loads(request.call_args.args[0].data)['messages'][-1]['content']=='hello'

@pytest.mark.parametrize('confidence', [float('nan'),-1,2])
def test_malformed_remote_confidence(monkeypatch,confidence):
    monkeypatch.setattr('urllib.request.urlopen',Mock(return_value=Response({'selected_class':'launch_application','confidence':confidence,'target':'brave'})))
    tier=JevReflexTier(api_key='test')
    with pytest.raises(RuntimeError): tier._call_jev_remote_api('hello')

def test_remote_blocked_preserved(monkeypatch):
    from floter.tiers.jev_tier import routing_choices
    probabilities={key:float(key=='blocked') for key in routing_choices()}
    body={'answers':{'route':{'type':'choice','choice':'blocked','probabilities':probabilities,'confidence':1}}}
    monkeypatch.setattr('urllib.request.urlopen',Mock(return_value=Response(body)))
    assert not JevReflexTier(api_key='test')._call_jev_remote_api('hello').is_safe

def test_transcription_uses_actual_segments(monkeypatch):
    monkeypatch.setattr(config, 'STT_ENGINE', 'faster-whisper')
    from floter.audio.listener import AudioListener
    from types import SimpleNamespace
    listener=AudioListener()
    listener.whisper_model=Mock()
    listener.whisper_model.transcribe.return_value=([SimpleNamespace(text='open calculator')],None)
    assert listener.transcribe_file_or_audio('audio')=='open calculator'

def test_transcription_failure_never_invents_command(monkeypatch):
    monkeypatch.setattr(config, 'STT_ENGINE', 'faster-whisper')
    from floter.audio.listener import AudioListener
    listener=AudioListener(); listener.whisper_model=Mock()
    listener.whisper_model.transcribe.side_effect=RuntimeError('failed')
    with pytest.raises(RuntimeError): listener.transcribe_file_or_audio('audio')

def test_gui_starts_from_unrelated_directory(tmp_path):
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen')
    result=subprocess.run([sys.executable,'-m','floter','--smoke-test'],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0, result.stderr
    assert 'failed' not in result.stderr.lower(), result.stderr
    assert 'ReferenceError' not in result.stderr, result.stderr

def test_atomic_create_race(tmp_path,monkeypatch):
    import floter.security.sandbox as sandbox
    file=tmp_path/'race'
    def concurrent_create(path):
        file.write_text('other process')
        return file
    monkeypatch.setattr(sandbox,'validate_file_creation_path',concurrent_create)
    with pytest.raises(FileExistsError): SafeFileSystem.write_new_text(file,'overwrite')
    assert file.read_text()=='other process'

def test_gemini_key_in_header_and_provider_json(monkeypatch):
    monkeypatch.setattr(config,'GEMINI_MODEL','test-model')
    request=Mock(return_value=Response({'candidates':[{'content':{'parts':[{'text':'{"analysis":"result"}'}]}}]}))
    monkeypatch.setattr('urllib.request.urlopen',request)
    assert GeminiMultimodalTier(api_key='secret').analyze_visual_and_logs('hello')['analysis']=='result'
    req=request.call_args.args[0]
    assert 'secret' not in req.full_url
    assert req.get_header('X-goog-api-key')=='secret'

@pytest.mark.parametrize('body', [{}, {'candidates':[]}])
def test_gemini_empty_response_is_error(monkeypatch,body):
    monkeypatch.setattr(config,'GEMINI_MODEL','test-model')
    monkeypatch.setattr('urllib.request.urlopen',Mock(return_value=Response(body)))
    with pytest.raises(RuntimeError): GeminiMultimodalTier(api_key='secret').analyze_visual_and_logs('hello')

def test_hermes_rejects_remote_plaintext(monkeypatch):
    monkeypatch.setattr(config,'HERMES_API_BASE','http://example.com/v1')
    with pytest.raises(ValueError): HermesAgentOrchestrator().execute_complex_plan('hello')

@pytest.mark.parametrize('endpoint', ['http://example.com/classify', 'https://user:password@example.com/classify'])
def test_jev_rejects_insecure_endpoint_before_request(monkeypatch, endpoint):
    request = Mock()
    monkeypatch.setattr('floter.tiers.jev_tier.request_json', request)
    with pytest.raises(ValueError):
        JevReflexTier(api_key='test', endpoint=endpoint)._call_jev_remote_api('hello')
    request.assert_not_called()

def test_shutdown_rejects_new_work():
    app=FloterOrchestrator(); app.shutdown()
    assert not app.process_query_async('open brave')
    assert app.process_query('open brave')['status']=='ignored'

def test_provider_error_not_success(monkeypatch):
    app=FloterOrchestrator()
    route(app, Action.ESCALATE_TO_HERMES)
    monkeypatch.setattr(app.hermes,'execute_complex_plan',Mock(return_value={'error':'failed'}))
    monkeypatch.setattr(app.hermes,'ensure_configured',Mock())
    assert app.process_query('hello')['status']=='error'

def test_audio_capture_failure_releases_lock(monkeypatch):
    from floter.audio.listener import AudioListener
    errors=[]; states=[]
    listener=AudioListener(on_error=errors.append,on_state_change=states.append)
    listener._lock.acquire()
    monkeypatch.setattr('floter.audio.listener.run_isolated', Mock(side_effect=RuntimeError('No microphone')))
    listener._record_and_transcribe(.01)
    assert errors
    assert states[-1]=='Idle'
    assert not listener._lock.locked()

def test_worker_bridge_updates_are_queued():
    # Separate process keeps Qt global state isolated from other GUI tests.
    script='''
from PySide6.QtGui import QGuiApplication
from floter.ui.bridge import FloterBridge
import threading
app=QGuiApplication([])
bridge=FloterBridge()
t=threading.Thread(target=bridge.stateRequested.emit,args=('Reasoning',))
t.start(); t.join()
assert bridge.stateName=='Idle'
app.processEvents()
assert bridge.stateName=='Reasoning'
bridge.shutdown()
'''
    result=subprocess.run([sys.executable,'-c',script],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
