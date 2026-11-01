import json
import os
import subprocess
import sys
from unittest.mock import Mock
import numpy as np
from floter.audio.listener import AudioListener, SpeechEndpoint, stream_vosk

def test_endpoint_waits_for_speech_then_silence():
    endpoint = SpeechEndpoint()
    assert not endpoint.feed(0., 2)
    assert not endpoint.feed(.1, .4)
    assert not endpoint.feed(0., .3)
    assert endpoint.feed(0., .3)
    assert endpoint.elapsed < 3.5

def test_stream_partials_do_not_execute():
    recognizer = Mock()
    recognizer.AcceptWaveform.side_effect = [False, False, True]
    recognizer.PartialResult.side_effect = [json.dumps({'partial':'open'}), json.dumps({'partial':'open note'})]
    recognizer.Result.return_value = json.dumps({'text':'open notepad'})
    stream = Mock()
    stream.__enter__ = Mock(return_value=stream)
    stream.__exit__ = Mock(return_value=False)
    stream.read.return_value = (bytes(2560), False)
    sd = Mock()
    sd.RawInputStream.return_value = stream
    events = []
    text = stream_vosk(sd, np, object(), lambda *args: recognizer, '', lambda *args:events.append(args))
    assert text == 'open notepad'
    assert ('partial_transcript','open') in events
    assert not any(event[0] == 'transcript' for event in events)

def test_final_submitted_once_after_audio_idle(monkeypatch):
    events = []
    listener = AudioListener(on_transcription=lambda t:events.append(('final',t)),
                             on_state_change=lambda s:events.append(('state',s)))
    monkeypatch.setattr('floter.audio.listener.run_isolated', Mock(return_value='open notepad'))
    listener._lock.acquire()
    listener._record_and_transcribe(3.5)
    assert events == [('state','Idle'), ('final','open notepad')]

def test_qt_final_submits_without_enter_and_partial_does_not():
    script = '''
from unittest.mock import Mock
from PySide6.QtGui import QGuiApplication
from floter.ui.bridge import FloterBridge
app=QGuiApplication([])
bridge=FloterBridge()
bridge.orchestrator.process_query_async=Mock(return_value=True)
bridge.partialTranscriptReady.emit('open note')
app.processEvents()
bridge.orchestrator.process_query_async.assert_not_called()
bridge.transcriptReady.emit('open notepad')
app.processEvents()
bridge.orchestrator.process_query_async.assert_called_once_with('open notepad')
bridge.orchestrator._lock.acquire()
bridge.transcriptReady.emit('open calculator')
app.processEvents()
assert len(bridge._voice_queue)==1
bridge.orchestrator._lock.release()
bridge._drain_voice_queue()
assert bridge.orchestrator.process_query_async.call_count==2
bridge.shutdown()
'''
    result = subprocess.run([sys.executable,'-c',script], env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),
                            capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stderr
