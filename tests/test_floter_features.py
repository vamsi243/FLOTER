import json
from unittest.mock import Mock
import pytest
from floter.audio.whisper_stream import WakeSession
from floter.tiers.jev_tier import JevReflexTier, JevDecision, JevActionEnum as Action
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tools.desktop_actions import search_url, NotepadSession

def test_wake_and_bounded_followup():
    session = WakeSession('hey rex', 20)
    assert session.accept('open notepad', now=1) is None
    assert session.accept('Hey Rex, open notepad', now=2) == 'open notepad'
    assert session.accept('write hello in notepad', now=10) == 'write hello in notepad'
    assert session.accept('open calculator', now=31) is None
    assert session.accept('hey rex', now=32) == ''
    assert session.accept('open calculator', now=33) == 'open calculator'

def test_search_is_a_bounded_encoded_url():
    from urllib.parse import urlparse, parse_qs
    query = 'C++ & Python; $(not a shell) #examples'
    url = search_url(query)
    assert urlparse(url).netloc == 'www.google.com'
    assert parse_qs(urlparse(url).query)['q'] == [query]
    with pytest.raises(ValueError): search_url(' ')
    with pytest.raises(ValueError): search_url('x'*2001)

def test_followup_keeps_context_and_dispatches_literal_tool(monkeypatch):
    app = FloterOrchestrator()
    app.notepad.open = Mock(return_value='Opened')
    app.jev.triage_and_route = Mock(side_effect=[
        JevDecision(Action.LAUNCH_APP,'notepad',1,1,True,'test',1),
        JevDecision(Action.TYPE_NOTEPAD,'notepad',1,1,True,'test',1)])
    app.jev.extract_argument = Mock(return_value='how are you doing')
    typed = Mock()
    typed.invoke.return_value = {'status':'success'}
    app.desktop_tools['type_notepad'] = typed
    assert app.process_query('can you try opening a note pad')['status'] == 'success'
    assert app.process_query('try write how are you doing on the notepad')['status'] == 'success'
    assert app.jev.context['last_target'] == 'notepad'
    typed.invoke.assert_called_once_with({'text':'how are you doing'})

@pytest.mark.parametrize('extracted,expected',[
    ('hiking trails near Sydney with train access','hiking trails near Sydney with train access'),
    (ValueError('unsure'),'look up hiking trails near Sydney with train access')])
def test_search_uses_literal_topic_or_falls_back_to_entire_request(extracted,expected):
    app = FloterOrchestrator()
    app.jev.triage_and_route = Mock(return_value=JevDecision(Action.WEB_SEARCH,None,1,1,True,'test',1,browser='brave'))
    app.jev.extract_argument = Mock(side_effect=[extracted])
    search = Mock()
    search.invoke.return_value = {'status':'success'}
    app.desktop_tools['web_search'] = search
    query = 'look up hiking trails near Sydney with train access'
    assert app.process_query(query)['status'] == 'success'
    search.invoke.assert_called_once_with({'query':expected,'browser':'brave'})

@pytest.mark.parametrize('confidence,accepted',[(.8,True),(.5,False),(None,False)])
def test_argument_requires_valid_boundary_confidence(monkeypatch,confidence,accepted):
    def response(request, *args):
        payload = json.loads(request.data)
        keys = payload['questions']['start']['criteria']
        return {'answers':{edge:{'type':'choice','choice':choice,'confidence':edge_confidence,'probabilities':{
            key:float(key==choice) for key in keys}} for edge,choice,edge_confidence in [('start','2',confidence),('end','5',.9)]}}
    monkeypatch.setattr('floter.tiers.jev_tier.request_json', response)
    tier = JevReflexTier(api_key='test',endpoint='https://api.typesafe.ai/v1/systemone')
    command = 'try write how are you doing on the notepad'
    if accepted:
        assert tier.extract_argument(command,'literal words to append to Notepad') == 'how are you doing'
    else:
        with pytest.raises(ValueError): tier.extract_argument(command,'literal words to append to Notepad')

def test_notepad_refuses_unbound_target():
    with pytest.raises(RuntimeError,match='open Notepad first'):
        NotepadSession().append('hello')

def test_long_wake_idle_does_not_truncate_next_utterance(monkeypatch):
    import numpy as np
    import floter.audio.whisper_stream as speech
    silent = np.zeros(480,dtype=np.float32)
    tone = np.full(480,.1,dtype=np.float32)
    frames = iter([silent]*800 + [tone]*20 + [silent]*30)
    class Queue:
        def __init__(self,**kw): pass
        def get(self,**kw): return next(frames)
        def empty(self): return True
    class Stream:
        def __init__(self,**kw): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
    class Done(Exception): pass
    class Device: InputStream=Stream
    monkeypatch.setattr(speech.queue,'Queue',Queue)
    monkeypatch.setattr(speech,'decode',lambda *args,**kw:'hey rex open notepad')
    events=[]
    def emit(event,value):
        events.append((event,value))
        if event=='transcript': raise Done()
    with pytest.raises(Done):
        speech.stream_whisper(Device,np,object(),'hey rex',emit)
    assert [e for e in events if e[0]=='transcript'] == [('transcript','open notepad')]

def test_background_speech_before_wake_neither_displays_nor_executes(monkeypatch):
    import numpy as np
    import floter.audio.whisper_stream as speech
    frames = iter([np.full(480,.1,dtype=np.float32)]*20 + [np.zeros(480,dtype=np.float32)]*30)
    class Queue:
        def __init__(self,**kw): pass
        def get(self,**kw): return next(frames)
        def empty(self): return True
    class Stream:
        def __init__(self,**kw): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
    class Device: InputStream=Stream
    monkeypatch.setattr(speech.queue,'Queue',Queue)
    monkeypatch.setattr(speech,'decode',lambda *args,**kw:'open notepad')
    events=[]
    with pytest.raises(StopIteration):
        speech.stream_whisper(Device,np,object(),'hey rex',lambda *args:events.append(args))
    assert not any(e[0] in ('partial_transcript','transcript','wake_active') for e in events)

def test_audio_glitch_discards_only_the_current_command(monkeypatch):
    import numpy as np
    import floter.audio.whisper_stream as speech
    silent = np.zeros(1600,dtype=np.float32); tone = np.full(1600,.1,dtype=np.float32)
    plan = [silent]*5 + [tone]*8 + [silent]*12 + [tone]*8 + [silent]*12
    state = {'index':0, 'callback':None}
    class Queue:
        def __init__(self,**kw): pass
        def put_nowait(self,item): pass
        def empty(self): return True
        def get(self,**kw):
            state['index'] += 1
            if state['index'] == 9:  # mid-way through the first command
                state['callback'](np.zeros((1,1)),1,None,'input overflow')
            return plan[state['index']-1]
    class Stream:
        def __init__(self,**kw):
            state['callback'] = kw['callback']
            assert kw['blocksize'] == speech.BLOCK_SAMPLES and kw['latency'] == 'high'
        def __enter__(self): return self
        def __exit__(self,*args): pass
    class Device: InputStream=Stream
    monkeypatch.setattr(speech.queue,'Queue',Queue)
    finals=[]
    def decode(model,audio,final=False):
        if final: finals.append(len(audio))
        return 'open notepad'
    monkeypatch.setattr(speech,'decode',decode)
    events=[]
    result = speech.stream_whisper(Device,np,object(),'',lambda *args:events.append(args))
    assert result == 'open notepad'
    assert ('partial_transcript',"Sorry, I didn't catch that. Please say it again.") in events
    # Only the second, complete command is decoded; the interrupted sentence's tail is ignored.
    assert len(finals) == 1 and finals[0] >= 8 * 1600
