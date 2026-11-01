from unittest.mock import Mock
import pytest
from floter.config import config
from floter.tiers.jev_tier import JevActionEnum as Action, JevDecision, routing_choices
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tiers.hermes_tier import REQUEST_NOT_CONFIGURED
from floter.tools.camera import CameraManager


@pytest.mark.parametrize('target', ['open','photo','record','stop','close'])
def test_confident_camera_routes_execute_only_selected_capability(target):
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.CAMERA,target,1,1,True,'test',1))
    app.camera.perform = Mock(return_value={'status':'success','message':'Camera action completed'})
    app.hermes.execute_complex_plan = Mock()
    assert app.process_query('a natural language camera request')['status'] == 'success'
    app.camera.perform.assert_called_once_with(target)
    app.hermes.execute_complex_plan.assert_not_called()
    assert routing_choices()['camera:' + target][:2] == (Action.CAMERA,target)


@pytest.mark.parametrize('action,score', [(Action.CAMERA,.5),(Action.PLAN,1),(Action.ESCALATE_TO_HERMES,1)])
def test_missing_reasoning_shows_friendly_message_without_handoff(monkeypatch,action,score):
    monkeypatch.setattr(config,'HERMES_API_KEY','')
    monkeypatch.setattr(config,'OPENROUTER_API_KEY','')
    monkeypatch.setattr(config,'HERMES_API_BASE','https://openrouter.ai/api/v1')
    logs=[]; app=FloterOrchestrator(on_log_message=logs.append)
    app.jev.triage_and_route=Mock(return_value=JevDecision(action,'photo',score,1,True,'test',score))
    app.camera.perform=Mock()
    result=app.process_query('unsupported or uncertain request')
    if score < 1:
        # Uncertain routing asks the user to rephrase instead of failing on the missing provider.
        assert result['status']=='needs_input' and 'rephrase' in result['message']
    else:
        assert result['error']==REQUEST_NOT_CONFIGURED
    assert not any('Passing' in item or 'API_KEY' in item for item in logs)
    app.camera.perform.assert_not_called()


def fake_camera_worker(action, device, output, duration, audio, stop, connection):
    """Exercise the actual child-process protocol without capturing a person."""
    try:
        if device == 'fail':
            connection.send(('done',{'status':'error','message':'No camera was found.'}))
        elif action == 'photo':
            connection.send(('done',{'status':'success','message':'Photo saved','path':output}))
        else:
            connection.send(('ready',{'status':'success','message':'Recording started'}))
            stop.wait(10)
            connection.send(('done',{'status':'success','message':'Video finalized','path':output}))
    finally:
        connection.close()


@pytest.fixture
def manager(monkeypatch,tmp_path):
    monkeypatch.setattr('floter.tools.camera.camera_worker',fake_camera_worker)
    monkeypatch.setattr(config,'CAMERA_SAVE_DIR',str(tmp_path))
    monkeypatch.setattr(config,'CAMERA_DEVICE','')
    camera=CameraManager()
    yield camera
    camera.shutdown()


def test_record_returns_while_active_and_stop_waits_for_finalization(manager):
    assert manager.perform('record')['message']=='Recording started'
    assert not manager.job.finished.is_set()
    with pytest.raises(RuntimeError,match='already capturing'): manager.perform('photo')
    assert manager.perform('stop')['message']=='Video finalized'
    assert manager.job.finished.is_set()
    assert not manager.job.process.is_alive()


def test_preview_can_be_replaced_with_photo(manager):
    manager.perform('open')
    preview=manager.job
    result=manager.perform('photo')
    assert preview.finished.is_set()
    assert result['path'].endswith('.jpg')
    assert manager.job.finished.is_set()


def test_camera_device_failure_is_reported_and_can_retry(manager,monkeypatch):
    monkeypatch.setattr(config,'CAMERA_DEVICE','fail')
    with pytest.raises(RuntimeError,match='No camera'): manager.perform('photo')
    monkeypatch.setattr(config,'CAMERA_DEVICE','')
    assert manager.perform('photo')['status']=='success'


def test_shutdown_releases_camera_child(manager):
    manager.perform('record')
    manager.shutdown()
    assert manager.job.finished.is_set()
    assert not manager.job.process.is_alive()
    with pytest.raises(RuntimeError,match='shutting down'): manager.perform('photo')


def test_invalid_camera_action_cannot_start_child(manager):
    with pytest.raises(ValueError): manager.perform('shell')
    assert manager.job is None
