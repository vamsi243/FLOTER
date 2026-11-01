"""Browser agent: schema and safety validation, review of every action, loop behaviour."""
import threading
from unittest.mock import Mock
import pytest
from floter.config import config
from floter.tools.browser_agent import BrowserAgent, validate_browser_action
from floter.workers import CancelledError

def element(id, role, label, password=False):
    return {'id': id, 'role': role, 'tag': 'x', 'label': label, 'password': password, 'top': id * 10, 'in_viewport': True}

OBS = {'snapshot': 's1', 'url': 'https://www.youtube.com/results?search_query=x', 'title': 'YouTube',
       'elements': [element(0, 'searchbox', 'Search'), element(3, 'link', 'Ed Sheeran - Shape of You'),
                    element(4, 'button', 'Send'), element(5, 'textbox', 'Password', password=True)]}
SITES = ['youtube.com']

@pytest.mark.parametrize('action,error', [
    ({'action': 'click', 'element': 99, 'reason': 'r'}, ValueError),
    ({'action': 'click', 'element': True, 'reason': 'r'}, ValueError),
    ({'action': 'click', 'element': 3}, ValueError),
    ({'action': 'click', 'element': 3, 'reason': 'r', 'js': 'x'}, ValueError),
    ({'action': 'fill', 'element': 3, 'text': 'x', 'reason': 'r'}, ValueError),
    ({'action': 'press_enter', 'element': 3, 'reason': 'r'}, ValueError),
    ({'action': 'fill', 'element': 0, 'text': 'a\nb', 'reason': 'r'}, ValueError),
    ({'action': 'fill', 'element': 0, 'text': 'x' * 501, 'reason': 'r'}, ValueError),
    ({'action': 'scroll', 'direction': 'left', 'reason': 'r'}, ValueError),
    ({'action': 'navigate', 'url': 'https://x', 'reason': 'r'}, ValueError),
    ({'action': 'click', 'element': 4, 'reason': 'r'}, PermissionError),
    ({'action': 'fill', 'element': 5, 'text': 'x', 'reason': 'r'}, PermissionError),
])
def test_invalid_or_unsafe_actions_rejected(action, error):
    with pytest.raises(error):
        validate_browser_action(action, OBS, SITES)

def test_input_on_unlisted_site_rejected():
    with pytest.raises(PermissionError, match='BROWSER_INPUT_SITES'):
        validate_browser_action({'action': 'click', 'element': 3, 'reason': 'r'}, dict(OBS, url='https://mail.google.com'), SITES)

def test_valid_actions_pass():
    for action in ({'action': 'fill', 'element': 0, 'text': 'shape of you', 'reason': 'r'},
                   {'action': 'press_enter', 'element': 0, 'reason': 'r'}, {'action': 'click', 'element': 3, 'reason': 'r'},
                   {'action': 'scroll', 'direction': 'down', 'reason': 'r'}, {'action': 'back', 'reason': 'r'},
                   {'action': 'done', 'evidence': 3, 'reason': 'r'}, {'action': 'ask', 'reason': 'which one?'}):
        assert validate_browser_action(action, OBS, SITES) == action

def worker_returning(observation):
    worker = Mock()
    worker.call.side_effect = lambda cancel, op, *args: observation if op == 'observe' else 'ok'
    return worker

def executes(worker):
    return [c.args[2:] for c in worker.call.call_args_list if c.args[1] == 'execute']

def test_search_then_finish_reviews_every_step(monkeypatch):
    monkeypatch.setattr(config, 'BROWSER_INPUT_SITES', SITES)
    worker = worker_returning(OBS)
    fill = {'action': 'fill', 'element': 0, 'text': 'shape of you', 'reason': 'type query'}
    enter = {'action': 'press_enter', 'element': 0, 'reason': 'submit'}
    reasoner = Mock(); reasoner.call.side_effect = [fill, enter, {'action': 'done', 'evidence': 3, 'reason': 'results visible'}]
    review = Mock()
    result = BrowserAgent(threading.Event(), review, Mock(), worker, reasoner).run('search for shape of you')
    assert result == {'status': 'success', 'message': 'results visible', 'url': OBS['url']}
    assert executes(worker) == [('s1', fill), ('s1', enter)]
    assert review.call_count == 4 and all(c.kwargs['hide'] is False for c in review.call_args_list)
    assert 'Text: shape of you' in review.call_args_list[1].args[1]
    payload = reasoner.call.call_args.args[1]
    assert payload['goal'] == 'search for shape of you' and payload['url'] == OBS['url']
    assert reasoner.call.call_args.args[2] == 'choose the next browser step'

def test_rejected_review_stops_before_acting(monkeypatch):
    monkeypatch.setattr(config, 'BROWSER_INPUT_SITES', SITES)
    worker = worker_returning(OBS)
    reasoner = Mock(); reasoner.call.return_value = {'action': 'click', 'element': 3, 'reason': 'open video'}
    review = Mock(side_effect=[None, CancelledError('Desktop action rejected')])
    with pytest.raises(CancelledError):
        BrowserAgent(threading.Event(), review, Mock(), worker, reasoner).run('play the first video')
    assert executes(worker) == []

def test_invalid_model_reply_never_acts(monkeypatch):
    monkeypatch.setattr(config, 'BROWSER_INPUT_SITES', SITES)
    worker = worker_returning(OBS)
    reasoner = Mock(); reasoner.call.return_value = {'action': 'click', 'element': 42, 'reason': 'invented'}
    with pytest.raises(ValueError):
        BrowserAgent(threading.Event(), Mock(), Mock(), worker, reasoner).run('click it')
    assert executes(worker) == []

def test_ask_returns_question():
    reasoner = Mock(); reasoner.call.return_value = {'action': 'ask', 'reason': 'Which video?'}
    result = BrowserAgent(threading.Event(), Mock(), Mock(), worker_returning(OBS), reasoner).run('open the video')
    assert result == {'status': 'needs_input', 'message': 'Which video?'}
