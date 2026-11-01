"""Configuration comes from %USERPROFILE%/.floter/.env; Gemini can back reasoning."""
import pytest
from floter import config as module

def test_invalid_numbers_fall_back_with_warning(monkeypatch):
    monkeypatch.setenv('CAMERA_VIDEO_SECONDS','abc'); monkeypatch.setenv('SPEECH_SILENCE_SECONDS','x')
    module.CONFIG_WARNINGS.clear()
    fresh=module.FloterConfig()
    assert fresh.CAMERA_VIDEO_SECONDS==60 and fresh.SPEECH_SILENCE_SECONDS==.7
    assert len(module.CONFIG_WARNINGS)==2
    module.CONFIG_WARNINGS.clear()

def test_blank_hermes_base_uses_default(monkeypatch):
    monkeypatch.setenv('HERMES_API_BASE','')
    monkeypatch.setenv('GEMINI_API_KEY','')
    assert module.FloterConfig().HERMES_API_BASE==module.DEFAULT_HERMES_API_BASE

def clear_reasoning(monkeypatch):
    for name in ('HERMES_API_BASE','HERMES_API_KEY','OPENROUTER_API_KEY','HERMES_MODEL'):
        monkeypatch.delenv(name, raising=False)

def test_gemini_backs_reasoning_when_no_other_provider(monkeypatch):
    clear_reasoning(monkeypatch)
    monkeypatch.setenv('GEMINI_API_KEY','gemini-test-key'); monkeypatch.setenv('GEMINI_MODEL','gemini-test-model')
    fresh=module.FloterConfig()
    assert fresh.REASONING_PROVIDER=='gemini'
    assert (fresh.HERMES_API_BASE, fresh.HERMES_API_KEY, fresh.HERMES_MODEL)==(module.GEMINI_OPENAI_BASE,'gemini-test-key','gemini-test-model')

@pytest.mark.parametrize('env',[{'OPENROUTER_API_KEY':'x'},{'HERMES_API_BASE':'http://localhost:8000/v1'},{'GEMINI_MODEL':''}])
def test_explicit_provider_or_missing_model_keeps_hermes(monkeypatch,env):
    clear_reasoning(monkeypatch)
    monkeypatch.setenv('GEMINI_API_KEY','gemini-test-key'); monkeypatch.setenv('GEMINI_MODEL','gemini-test-model')
    for key,value in env.items(): monkeypatch.setenv(key,value)
    assert module.FloterConfig().REASONING_PROVIDER=='hermes'

@pytest.mark.parametrize('reply',['{"action":"wait","reason":"x"}','```json\n{"action":"wait","reason":"x"}\n```','```\n{"action":"wait","reason":"x"}```'])
def test_fenced_json_replies_are_accepted(reply):
    from floter.tools.gui_agent import parse_json_reply
    assert parse_json_reply(reply)=={'action':'wait','reason':'x'}

@pytest.mark.parametrize('reply',['[1,2]','not json','```json\nnope\n```'])
def test_non_object_replies_are_rejected(reply):
    from floter.tools.gui_agent import parse_json_reply
    with pytest.raises(ValueError): parse_json_reply(reply)

def test_assistant_prompt_routes_exist():
    from floter.tiers.jev_tier import routing_choices,JevActionEnum
    choices=routing_choices()
    for app in ('claude','gemini'):
        assert choices['prompt:'+app][:2]==(JevActionEnum.ASSISTANT_PROMPT,app)
