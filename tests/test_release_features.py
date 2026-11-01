import json
import multiprocessing
import threading
import time
from pathlib import Path
from unittest.mock import Mock
import pytest
from floter.config import config
from floter.security.plans import ApprovalGate, SkillStore, validate_plan
from floter.security.sandbox import GuardrailViolationError
from floter.security.executables import resolve_application
from floter.tools.mcp_tools import FastMCPToolRegistry as Tools
from floter.workers import run_isolated, CancelledError
from floter.audio.listener import extract_wake_command

@pytest.fixture
def plan():
    return {'version':1,'summary':'Open Notepad','actions':[{'tool':'launch_application','arguments':{'target':'notepad'}}]}

@pytest.mark.parametrize('mutation', ['tool','extra','target','shell'])
def test_plan_rejects_unsupported(plan,mutation):
    if mutation=='tool': plan['actions'][0]['tool']='run_shell'
    elif mutation=='extra': plan['extra']='hidden command'
    elif mutation=='target': plan['actions'][0]['arguments']['target']='notepad && calc'
    else: plan['actions'][0]['arguments']['command']='cmd.exe'
    with pytest.raises(GuardrailViolationError): validate_plan(plan)

def test_approval_binds_snapshot_and_is_single_use(plan):
    gate=ApprovalGate(); ticket=gate.propose(plan)
    plan['actions'][0]['arguments']['target']='calculator'
    ticket['plan']['actions'][0]['arguments']['target']='calculator'
    approved=gate.consume(ticket['token'])
    assert approved['actions'][0]['arguments']['target']=='notepad'
    with pytest.raises(GuardrailViolationError): gate.consume(ticket['token'])

def test_expired_approval(plan):
    gate=ApprovalGate(ttl=-1); ticket=gate.propose(plan)
    with pytest.raises(GuardrailViolationError): gate.consume(ticket['token'])

def test_reject_invalidates(plan):
    gate=ApprovalGate(); ticket=gate.propose(plan); gate.reject()
    with pytest.raises(GuardrailViolationError): gate.consume(ticket['token'])

def test_skill_round_trip_and_tampering(tmp_path,plan):
    skills=SkillStore(tmp_path); skills.save('notepad',plan)
    assert skills.load('notepad')==plan
    assert skills.names()==['notepad']
    with pytest.raises(GuardrailViolationError): skills.save('notepad',plan)
    (tmp_path/'notepad.json').write_text('{"version":1,"actions":[{"tool":"shell"}]}')
    with pytest.raises(GuardrailViolationError): skills.load('notepad')

@pytest.mark.parametrize('name',['../escape','UPPER','a/b','a\\b',''])
def test_skill_name_safety(tmp_path,name,plan):
    with pytest.raises(ValueError): SkillStore(tmp_path).save(name,plan)

def test_app_resolution_ignores_path_and_cwd(tmp_path,monkeypatch):
    fake=tmp_path/'notepad.exe'; fake.write_bytes(b'fake')
    monkeypatch.chdir(tmp_path); monkeypatch.setenv('PATH',str(tmp_path))
    monkeypatch.setattr('floter.security.executables.approved_roots',lambda:[tmp_path/'trusted'])
    monkeypatch.setattr(config,'WHITELISTED_APPS',{'notepad':['notepad.exe']})
    with pytest.raises(FileNotFoundError): resolve_application('notepad')

def test_app_resolution_uses_trusted_root(tmp_path,monkeypatch):
    fake=tmp_path/'notepad.exe'; fake.write_bytes(b'test')
    monkeypatch.setattr('floter.security.executables.approved_roots',lambda:[tmp_path])
    monkeypatch.setattr(config,'WHITELISTED_APPS',{'notepad':['notepad.exe']})
    assert resolve_application('notepad')==fake

def test_storage_all_drives_is_read_only_and_bounded(monkeypatch):
    monkeypatch.setattr('floter.tools.mcp_tools.sys.platform', 'linux')
    report = Tools.inspect_storage_all_drives(time_budget=1, max_entries_per_drive=2)
    assert report['read_only'] is True
    assert report['drives'] and len(report['drives'][0]['paths']) <= 2

def sleeping_operation():
    time.sleep(30)
    return 'late result'

def test_worker_hard_timeout_leaves_no_child():
    before={p.pid for p in multiprocessing.active_children()}
    started=time.monotonic()
    with pytest.raises(TimeoutError): run_isolated(sleeping_operation,timeout=.3)
    assert time.monotonic()-started<5
    assert {p.pid for p in multiprocessing.active_children()}==before

def test_worker_hard_cancel_leaves_no_child():
    stop=threading.Event(); timer=threading.Timer(.3,stop.set()); timer.start()
    before={p.pid for p in multiprocessing.active_children()}
    try:
        with pytest.raises(CancelledError): run_isolated(sleeping_operation,cancel=stop,timeout=20)
    finally: timer.cancel()
    assert {p.pid for p in multiprocessing.active_children()}==before

def test_precancel_does_not_start_worker():
    stop=threading.Event(); stop.set()
    with pytest.raises(CancelledError): run_isolated(sleeping_operation,cancel=stop)

@pytest.mark.parametrize('text,expected',[('Hey Floter, open Notepad.','open Notepad.'),('hey floter',''),('Hey Floter.',''),
    ('they said hey floter open notepad',None),('hello floter',None),
    ('Hey Floter, write Hello, World! in Notepad','write Hello, World! in Notepad'),
    ('hey floter: ask Claude what is 2+2?','ask Claude what is 2+2?')])
def test_wake_phrase(text,expected):
    assert extract_wake_command(text,'hey floter')==expected

def test_mica_fallback(monkeypatch):
    from floter.ui import backdrop
    monkeypatch.setattr(backdrop.sys,'platform','linux')
    assert backdrop.apply_mica(0) is False

def test_notepad_plan_requires_approval(monkeypatch):
    from floter.tiers.orchestrator import FloterOrchestrator
    action=Mock(return_value='done'); monkeypatch.setattr(Tools,'write_notepad',action)
    tickets=[]; app=FloterOrchestrator(on_approval=tickets.append)
    app.hermes.ensure_configured=Mock()
    from floter.tiers.jev_tier import JevDecision, JevActionEnum
    app.jev.triage_and_route=Mock(return_value=JevDecision(JevActionEnum.PLAN,None,1,1,True,'test',1))
    app.hermes.execute_complex_plan=Mock(return_value={'plan':{'version':1,'summary':'Create note',
        'actions':[{'tool':'write_notepad','arguments':{'file_name':'test.txt','content':'test'}}]}})
    assert app.process_query('write in notepad: test')['status']=='approval_required'
    action.assert_not_called()
    app.approve_plan(tickets[0]['token']); app._thread.join(3)
    action.assert_called_once()

def test_invalid_mcp_tool_is_rejected():
    from floter.tools.snippy_mcp import call_snippy
    with pytest.raises(ValueError): call_snippy('run_shell')

@pytest.mark.parametrize('spoken',['Run skill Morning.','run skill morning','RUN SKILL MORNING!'])
def test_spoken_skill_names_are_normalized(spoken):
    from floter.tiers.orchestrator import FloterOrchestrator
    from floter.tiers.jev_tier import JevDecision, JevActionEnum
    app=FloterOrchestrator()
    app.jev.triage_and_route=Mock(return_value=JevDecision(JevActionEnum.RUN_SKILL,None,1,1,True,'test',1))
    app.skills.load=Mock(side_effect=FileNotFoundError('missing'))
    app.process_query(spoken)
    app.skills.load.assert_called_once_with('morning')
