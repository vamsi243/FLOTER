"""Killable workers for blocking network/native operations."""
import multiprocessing as mp
import time
import urllib.request
import urllib.error
import json

class CancelledError(RuntimeError):
    pass

def _entry(connection, operation, args, progress):
    try:
        result = operation(*args, emit=lambda event, value: connection.send((None, (event,value)))) if progress else operation(*args)
        connection.send((True, result))
    except BaseException as exc:
        # Include exception details for diagnostic clarity
        connection.send((False, f"{type(exc).__name__}: {exc}"))
    finally:
        connection.close()

def run_isolated(operation, args=(), cancel=None, timeout=35, on_progress=None):
    if cancel is not None and cancel.is_set():
        raise CancelledError('Operation cancelled')
    context = mp.get_context('spawn')
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_entry, args=(send, operation, args, on_progress is not None), daemon=True)
    process.start()
    send.close()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancel is not None and cancel.is_set():
                raise CancelledError('Operation cancelled')
            if time.monotonic() >= deadline:
                raise TimeoutError('Operation exceeded its time budget')
            if receive.poll(.05):
                try:
                    success, value = receive.recv()
                except EOFError as exc:
                    raise RuntimeError('Worker exited without a result') from exc
                if success is None:
                    on_progress(*value)
                    continue
                if not success:
                    raise RuntimeError(f'Worker failed ({value})')
                return value
            if not process.is_alive():
                raise RuntimeError('Worker exited without a result')
    finally:
        if process.is_alive():
            process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
        process.join(2)
        process.close()
        receive.close()

def _http_json(url, data, headers, timeout):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError('Provider redirects are not allowed')
    request = urllib.request.Request(url, data=data, headers=headers)
    from urllib.parse import urlparse
    # Classification is read-only. Briefly retry transient upstream failures only there.
    evaluation = urlparse(url).path in ('/v4/ai/evaluation-model', '/v1/systemone')
    for attempt in range(3 if evaluation else 1):
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
                payload = response.read(2_000_001)
            break
        except urllib.error.HTTPError as exc:
            if not evaluation or attempt == 2 or exc.code not in (429, 502, 503, 504):
                raise
            time.sleep(.3 * (attempt+1))
    if len(payload) > 2_000_000:
        raise ValueError('Provider response too large')
    return json.loads(payload)

def request_json(request, timeout, cancel=None):
    if cancel is None:
        # Synchronous entry point for API callers; UI always supplies cancellation.
        return _http_json(request.full_url, request.data, dict(request.header_items()), timeout)
    return run_isolated(_http_json, (request.full_url, request.data, dict(request.header_items()), timeout), cancel, timeout + 5)
