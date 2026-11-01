import urllib.request
from unittest.mock import Mock

import pytest

from floter.workers import request_json, _http_json


def test_sync_requests_use_bounded_nonredirecting_transport(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b'x' * 2_000_001
    opener = Mock()
    opener.open.return_value = response
    factory = Mock(return_value=opener)
    monkeypatch.setattr(urllib.request, 'build_opener', factory)
    with pytest.raises(ValueError, match='too large'):
        request_json(urllib.request.Request('https://example.com'), 1)
    response.read.assert_called_once_with(2_000_001)
    handler = factory.call_args.args[0]
    with pytest.raises(ValueError, match='redirects'):
        handler.redirect_request(None, None, 302, 'redirect', {}, 'https://elsewhere.example')

def test_jev_transient_retry_is_bounded(monkeypatch):
    import urllib.error
    opener = Mock()
    opener.open.side_effect = urllib.error.HTTPError('https://ai-gateway.vercel.sh/v4/ai/evaluation-model',503,'Unavailable',{},None)
    monkeypatch.setattr(urllib.request,'build_opener',Mock(return_value=opener))
    pause = Mock()
    monkeypatch.setattr('floter.workers.time.sleep',pause)
    with pytest.raises(urllib.error.HTTPError):
        _http_json('https://ai-gateway.vercel.sh/v4/ai/evaluation-model',b'{}',{},1)
    assert opener.open.call_count == 3
    assert pause.call_count == 2

def test_auth_errors_are_not_retried(monkeypatch):
    import urllib.error
    opener = Mock()
    opener.open.side_effect = urllib.error.HTTPError('https://ai-gateway.vercel.sh/v4/ai/evaluation-model',401,'Unauthorized',{},None)
    monkeypatch.setattr(urllib.request,'build_opener',Mock(return_value=opener))
    with pytest.raises(urllib.error.HTTPError):
        _http_json('https://ai-gateway.vercel.sh/v4/ai/evaluation-model',b'{}',{},1)
    assert opener.open.call_count == 1
