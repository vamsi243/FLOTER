"""Opt-in local voice recognition isolated from the UI for hard cancellation."""
import re
import json
import threading
from collections import deque
from pathlib import Path
from floter.config import config
from floter.workers import run_isolated, CancelledError

def extract_wake_command(text, wake_word):
    """Match the wake phrase case-insensitively; return the rest exactly as spoken."""
    words = list(re.finditer(r"[\w']+", text))
    wake = re.findall(r"[\w']+", wake_word.lower())
    if not wake or [w.group().lower() for w in words[:len(wake)]] != wake:
        return None
    # Keep dictated case and punctuation; drop only separators after the wake phrase.
    return text[words[len(wake)-1].end():].lstrip(' \t,.:;!?-–—').strip()

def _voice_worker(duration, wake_word, finish=None, emit=None):
    if emit is None:
        emit = lambda event, value: None
    import numpy as np
    import sounddevice as sd
    emit('state','Thinking')
    engine = config.STT_ENGINE.lower()
    if engine in ('auto', 'faster-whisper'):
        from floter.audio.whisper_stream import load_model, stream_whisper
        return stream_whisper(sd, np, load_model(emit), wake_word, emit, finish)
    if engine == 'vosk':
        from vosk import Model, KaldiRecognizer
        if not Path(config.VOSK_MODEL_PATH).is_dir():
            raise RuntimeError('Set VOSK_MODEL_PATH to an extracted offline Vosk model')
        model = Model(config.VOSK_MODEL_PATH)
        return stream_vosk(sd, np, model, KaldiRecognizer, wake_word, emit)
    raise ValueError('STT_ENGINE must be auto, faster-whisper or vosk')


class SpeechEndpoint:
    """End an utterance after speech followed by silence, with bounded recording."""
    def __init__(self, silence=.55, max_seconds=12, threshold=.005):
        self.silence = silence
        self.max_seconds = max_seconds
        self.threshold = threshold
        self.started = False
        self.quiet = 0
        self.elapsed = 0

    def feed(self, rms, seconds):
        self.elapsed += seconds
        if rms >= self.threshold:
            self.started = True
            self.quiet = 0
        elif self.started:
            self.quiet += seconds
        return self.elapsed >= self.max_seconds or (self.started and self.quiet >= self.silence)


def stream_vosk(sd, np, model, recognizer_type, wake_word, emit):
    """Decode 80 ms frames locally; partials are display-only, finals execute once."""
    recognizer = recognizer_type(model, 16000)
    elapsed = 0
    previous = ''
    emit('state', 'Listening')
    with sd.RawInputStream(samplerate=16000, channels=1, dtype='int16', blocksize=1280) as stream:
        while True:
            frame, overflow = stream.read(1280)
            if overflow:
                raise RuntimeError('Microphone overflow')
            raw = bytes(frame)
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
            emit('level', min(1., float(np.sqrt(np.mean(samples**2))) * 4))
            elapsed += .08
            final = recognizer.AcceptWaveform(raw)
            # Never execute a truncated command just because the maximum elapsed.
            if not final and elapsed >= 12:
                recognizer.Reset()
                elapsed = 0
                if not wake_word:
                    raise RuntimeError('No complete utterance within 12 seconds; try a shorter command')
                emit('partial_transcript', 'Listening for a complete wake command…')
                continue
            if final:
                text = json.loads(recognizer.Result()).get('text', '').strip()
                elapsed = 0
                previous = ''
                if not text:
                    continue
                emit('level', 0.)
                if not wake_word:
                    return text
                command = extract_wake_command(text, wake_word)
                if command:
                    emit('partial_transcript', command)
                    emit('transcript', command)
                else:
                    emit('partial_transcript', f'Heard: "{text}" (say "{wake_word} <command>")')
            else:
                partial = json.loads(recognizer.PartialResult()).get('partial', '').strip()
                if partial and partial != previous:
                    emit('partial_transcript', partial)
                    previous = partial

class AudioListener:
    def __init__(self,on_audio_level=None,on_transcription=None,on_state_change=None,on_error=None,on_partial_transcription=None,on_wake_active=None):
        self.on_audio_level=on_audio_level or (lambda value:None)
        self.on_transcription=on_transcription or (lambda text:None)
        self.on_state_change=on_state_change or (lambda state:None)
        self.on_error=on_error or (lambda text:None)
        self.on_partial_transcription=on_partial_transcription or (lambda text:None)
        self.on_wake_active=on_wake_active or (lambda value:None)
        self.whisper_model=None
        self._lock=threading.Lock()
        self._stop=threading.Event()
        import multiprocessing
        self._finish = multiprocessing.get_context('spawn').Event()
        self._thread=None
        self.wake_enabled=False

    def start_background_stream(self):
        # Only the explicit UI toggle enables continuous recording.
        return False

    def _progress(self,event,value):
        if self._stop.is_set():
            return
        if event=='level': self.on_audio_level(value)
        elif event=='state': self.on_state_change(value)
        elif event=='transcript': self.on_transcription(value)
        elif event=='partial_transcript': self.on_partial_transcription(value)
        elif event=='engine': self.on_error(value)
        elif event=='wake_active': self.on_wake_active(bool(value))

    def stop_stream(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(3)
        self.wake_enabled=False

    def set_wake_enabled(self,enabled):
        self.stop_stream()
        if enabled:
            return self._start(4.0,True)
        return True

    def _start(self,duration,wake=False):
        if not self._lock.acquire(False):
            return False
        self._stop.clear()
        self._finish.clear()
        self.wake_enabled=wake
        self._thread=threading.Thread(target=self._record_and_transcribe,args=(duration,wake),daemon=True)
        self._thread.start()
        return True

    def trigger_push_to_talk(self,duration_sec=3.5):
        if self.wake_enabled:
            return False
        return self._start(duration_sec)

    def finish_utterance(self):
        self._finish.set()

    def _record_and_transcribe(self,duration_sec,wake=False):
        completed_text = ''
        try:
            text=run_isolated(_voice_worker,(duration_sec,config.WAKE_WORD if wake else '',self._finish),
                              self._stop,timeout=86400 if wake else 180,on_progress=self._progress)
            if not self._stop.is_set():
                if text:
                    self.on_partial_transcription(text)
                    completed_text = text
                else: self.on_error('No speech detected.')
        except CancelledError:
            pass
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(f'Voice unavailable: {exc}. Check the microphone and local speech model; text remains available.')
        finally:
            self.wake_enabled=False
            self.on_wake_active(False)
            self.on_audio_level(0.0)
            self.on_state_change('Idle')
            self._lock.release()
        if completed_text and not self._stop.is_set():
            self.on_transcription(completed_text)

    def transcribe_file_or_audio(self,audio_data):
        # Used by diagnostics and tests; production voice uses the killable worker.
        engine = config.STT_ENGINE.lower()
        if engine == 'auto':
            engine = 'faster-whisper'
        if engine == 'vosk':
            import wave
            from vosk import Model, KaldiRecognizer
            recognizer = KaldiRecognizer(Model(config.VOSK_MODEL_PATH), 16000)
            texts = []
            with wave.open(str(audio_data), 'rb') as source:
                if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
                    raise ValueError('Vosk diagnostics require a mono 16 kHz 16-bit PCM WAV')
                while frame := source.readframes(1280):
                    if recognizer.AcceptWaveform(frame):
                        texts.append(json.loads(recognizer.Result()).get('text', ''))
            texts.append(json.loads(recognizer.FinalResult()).get('text', ''))
            return ' '.join(text for text in texts if text).strip()
        if self.whisper_model is None:
            from floter.audio.whisper_stream import load_model
            self.whisper_model=load_model()
        segments,_=self.whisper_model.transcribe(audio_data,beam_size=2,vad_filter=True)
        return ' '.join(segment.text for segment in segments).strip()
