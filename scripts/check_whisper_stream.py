"""Play prerecorded PCM into the real streaming recognizer, without opening a mic."""
import json
from pathlib import Path
import threading
import time
import wave
import numpy as np
from floter.audio.whisper_stream import load_model, stream_whisper

class Finished(Exception):
    pass

def main():
    root = Path(__file__).resolve().parents[1]
    with wave.open(str(root/'acceptance-output'/'floter-commands.wav'), 'rb') as source:
        assert (source.getnchannels(),source.getsampwidth(),source.getframerate()) == (1,2,16000)
        audio = np.frombuffer(source.readframes(source.getnframes()),dtype=np.int16).astype(np.float32)/32768
    audio = np.concatenate([audio, np.zeros(32000, dtype=np.float32)])
    events = []
    model = load_model(lambda event,value:events.append((event,value)))
    finals = []
    start = time.monotonic()
    def emit(event,value):
        if event in ('partial_transcript','transcript','wake_active','state'):
            events.append((event,value,round(time.monotonic()-start,3)))
        if event == 'transcript':
            finals.append(value)
            if len(finals) == 2:
                raise Finished()
    class Stream:
        def __init__(self, **kw): self.callback=kw['callback']; self.stop=threading.Event()
        def __enter__(self):
            def play():
                for offset in range(0,len(audio),480):
                    if self.stop.is_set(): return
                    self.callback(audio[offset:offset+480,None],480,None,None)
                    time.sleep(.03)
                self.stop.wait(1)
            self.thread=threading.Thread(target=play,daemon=True); self.thread.start(); return self
        def __exit__(self,*args): self.stop.set(); self.thread.join(1)
    class Device: InputStream=Stream
    try:
        # The outer command has its own process timeout if endpointing never completes.
        stream_whisper(Device,np,model,'hey rex',emit)
    except Finished:
        pass
    result={'engine':events[0][1],'finals':finals,'events':events,'elapsed_seconds':time.monotonic()-start}
    (root/'acceptance-output'/'floter-whisper-stream.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    assert len(finals)==2
    activation = next(i for i,event in enumerate(events) if event[:2] == ('wake_active',True))
    first_final = next(i for i,event in enumerate(events) if event[0] == 'transcript')
    assert activation < first_final, 'Wake recognition must activate the UI before executing speech'

if __name__ == '__main__': main()
