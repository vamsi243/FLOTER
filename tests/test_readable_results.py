from unittest.mock import Mock
import pytest
from floter.tiers.jev_tier import JevActionEnum as Action, JevDecision
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tools.mcp_tools import FastMCPToolRegistry

GIB = 1024 ** 3


def run(action, target=None, **patches):
    logs = []
    app = FloterOrchestrator(on_log_message=logs.append)
    app.jev.triage_and_route = Mock(return_value=JevDecision(action, target, 1, 1, True, 'test', 1))
    app.hermes.ensure_configured = Mock()
    for name, value in patches.items():
        setattr(app.hermes if name == 'execute_complex_plan' else app.skills, name, value)
    result = app.process_query('a request')
    return result, logs


def test_advice_shows_only_the_answer_without_markdown_bold():
    answer = {'analysis': '**Keep a pad.**\n\nUse **kwargs in Python.', 'mode': 'advisory'}
    result, logs = run(Action.ESCALATE_TO_HERMES, execute_complex_plan=Mock(return_value=answer))
    assert logs[-1] == 'Keep a pad.\n\nUse **kwargs in Python.'
    assert result['result'] == answer


@pytest.mark.parametrize('names,expected', [
    ([], 'No saved skills yet.'),
    (['morning', 'standup'], 'Saved skills: morning, standup'),
])
def test_skill_list_is_a_sentence(names, expected):
    result, logs = run(Action.LIST_SKILLS, names=Mock(return_value=names))
    assert logs[-1] == expected
    assert result['result'] == names


def test_storage_is_summarized_without_listing_paths(monkeypatch):
    report = {'status': 'success', 'read_only': True, 'drives': [
        {'drive': 'C:\\', 'paths': [{'path': 'C:\\private.txt', 'is_dir': False, 'size_bytes': 5}, {'path': 'C:\\Users', 'is_dir': True, 'size_bytes': None}],
         'total_bytes': 200 * GIB, 'used_bytes': 150 * GIB, 'free_bytes': 50 * GIB},
        {'drive': 'E:\\', 'paths': [], 'error': 'PermissionError'},
    ]}
    monkeypatch.setattr(FastMCPToolRegistry, 'inspect_storage_all_drives', Mock(return_value=report))
    result, logs = run(Action.INSPECT_STORAGE)
    assert logs[-1] == 'C:\\ — 50.0 GB free of 200.0 GB (2 top-level items)\nE:\\ — could not be read'
    assert result['result'] == report
