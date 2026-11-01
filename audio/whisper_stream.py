"""Rolling local Whisper transcription with independent, bounded audio capture."""
from pathlib import Path
import ctypes
import os
import queue
import sys
import threading
import time
from floter.config import config

_dll_handles = []
# 100 ms audio blocks with the driver's high-latency buffering: an occasional busy
# moment on the PC no longer drops audio. Voice commands don't need lower latency.
BLOCK_SAMPLES = 1600
# Live text only re-transcribes the most recent audio; the final command uses all of it.
PARTIAL_WINDOW_SECONDS = 6

def configure_cuda_paths():
    roots = [Path(sys.prefix) / 'Lib' / 'site-packages', Path(getattr(sys, '_MEIPASS', ''))]
    for root in roots:
        for package in ('cublas', 'cudnn', 'cuda_nvrtc'):
            directory = root / 'nvidia' / package / 'bin'
            if directory.is_dir():
                os.environ['PATH'] = str(directory) + os.pathsep + os.environ.get('PATH', '')
                if hasattr(os, 'add_dll_directory'):
                    _dll_handles.append(os.add_dll_directory(str(directory)))

def load_model(emit=lambda *args: None):
    from faster_whisper import WhisperModel
    import ctranslate2
    configure_cuda_paths()
    device = config.WHISPER_DEVICE.lower()
    if device not in ('auto', 'cuda', 'cpu'):
        raise ValueError('WHISPER_DEVICE must be auto, cuda, or cpu')
    available = ctranslate2.get_cuda_device_count() > 0
    if available and sys.platform == 'win32':
        try:
            ctypes.WinDLL('cublas64_12.dll')
            ctypes.WinDLL('cudnn64_9.dll')
        except OSError:
            available = False
    if device == 'cuda' and not available:
        raise RuntimeError('CUDA requested but CUDA 12/cuDNN 9 runtime is unavailable; install runtimes or use WHISPER_DEVICE=cpu')
    chosen = 'cuda' if device != 'cpu' and available else 'cpu'
    path = config.WHISPER_MODEL_PATH
    if not Path(path).is_dir():
        raise RuntimeError('Run scripts/provision_whisper.py to provision the local speech model')
    try:
        model = WhisperModel(path, device=chosen, compute_type='int8_float16' if chosen == 'cuda' else 'int8', local_files_only=True)
        # Exercise inference as loading alone does not validate all CUDA libraries.
        import numpy as np
        segments, _ = model.transcribe(np.zeros(1600, dtype=np.float32), language='en', beam_size=1)
        list(segments)
    except Exception:
        if device != 'auto' or chosen != 'cuda':
            raise
        chosen = 'cpu'
        model = WhisperModel(path, device='cpu', compute_type='int8', local_files_only=True)
    emit('engine', f'Faster Whisper · {chosen.upper()} · {Path(path).name}')
    return model

def decode(model, audio, final=False):
    segments, _ = model.transcribe(audio, language='en', beam_size=3 if final else 1, vad_filter=True,
                                  condition_on_previous_text=False, temperature=0,
                                  initial_prompt='Hey Rex. FLOTER desktop assistant. Open Notepad. Write text in Notepad. Search the internet.')
    return ' '.join(s.text.strip() for s in segments if s.text.strip()).strip()

class WakeSession:
    def __init__(self, phrase, followup_seconds):
        self.phrase = phrase
        self.followup = max(0, min(60, followup_seconds))
        self.until = 0.

    def accept(self, text, now=None):
        from floter.audio.listener import extract_wake_command
        now = time.monotonic() if now is None else now
        command = extract_wake_command(text, self.phrase)
        if command is not None:
            self.until = now + self.followup
            return command
        if now < self.until:
            self.until = now + self.followup
            return text
        return None

def stream_whisper(sd, np, model, wake_word, emit, finish=None):
    from floter.audio.listener import SpeechEndpoint, extract_wake_command
    from collections import deque
    frames = queue.Queue(maxsize=400)
    glitch = threading.Event()
    def callback(indata, frame_count, timing, status):
        # A dropped audio block is a hiccup, not a failure: note it and keep listening.
        if status:
            glitch.set()
        try:
            frames.put_nowait(indata[:, 0].copy())
        except queue.Full:
            glitch.set()
    gate = WakeSession(wake_word, config.VOICE_FOLLOWUP_SECONDS) if wake_word else None
    silence = max(.35, min(2., config.SPEECH_SILENCE_SECONDS))
    detector = SpeechEndpoint(silence=silence, max_seconds=20)
    chunks, preroll = [], deque(maxlen=6)
    next_partial = 0.
    started_at = time.monotonic()
    active = False
    # After a hiccup, ignore the rest of the interrupted sentence until the speaker pauses.
    resync, quiet_run = False, 0.
    def listening(value):
        nonlocal active
        if value != active:
            active = value
            emit('wake_active', value)
        emit('state', 'Listening' if value or not gate else 'Waiting')
    listening(not bool(gate))
    with sd.InputStream(samplerate=16000, channels=1, dtype='float32', blocksize=BLOCK_SAMPLES,
                        latency='high', callback=callback):
        while True:
            if glitch.is_set():
                glitch.clear()
                if detector.started:
                    # Audio is missing from this command, so never act on it; ask again instead.
                    chunks, preroll = [], deque(maxlen=6)
                    detector = SpeechEndpoint(silence=silence, max_seconds=20)
                    started_at = time.monotonic()
                    resync, quiet_run = True, 0.
                    emit('level', 0.)
                    if active or not gate:
                        emit('partial_transcript', "Sorry, I didn't catch that. Please say it again.")
            try:
                chunk = frames.get(timeout=.1)
            except queue.Empty:
                continue
            rms = float(np.sqrt(np.mean(chunk**2)))
            if gate and active and not detector.started and time.monotonic() >= gate.until:
                listening(False)
            emit('level', min(1., rms * 4))
            if resync:
                quiet_run = quiet_run + len(chunk)/16000 if rms < detector.threshold else 0.
                resync = quiet_run < silence
                started_at = time.monotonic()
                continue
            was_started = detector.started
            detector.feed(rms, len(chunk)/16000)
            if not was_started:
                preroll.append(chunk)
                if detector.started:
                    detector.elapsed = len(chunk)/16000
                    chunks.extend(preroll)
            else:
                chunks.append(chunk)
            finishing = finish is not None and finish.is_set()
            if finishing:
                finish.clear()
            if detector.started and detector.elapsed >= 20 and detector.quiet < silence:
                raise RuntimeError('Command exceeded 20 seconds; no partial command was executed')
            complete = detector.started and (detector.quiet >= silence or finishing)
            if complete:
                emit('state', 'Thinking')
                text = decode(model, np.concatenate(chunks), final=True)
                chunks, preroll = [], deque(maxlen=6)
                detector = SpeechEndpoint(silence=silence, max_seconds=20)
                started_at = time.monotonic()
                emit('level', 0.)
                if text:
                    if not gate:
                        emit('partial_transcript', text)
                        return extract_wake_command(text, config.WAKE_WORD) or text
                    command = gate.accept(text)
                    if command is not None:
                        listening(True)
                        emit('partial_transcript', command)
                        if command:
                            emit('transcript', command)
                listening(bool(gate and time.monotonic() < gate.until))
            elif chunks and frames.empty() and time.monotonic() >= next_partial:
                decode_started = time.monotonic()
                text = decode(model, np.concatenate(chunks)[-16000 * PARTIAL_WINDOW_SECONDS:])
                decode_seconds = time.monotonic() - decode_started
                if text:
                    if gate:
                        # Wake detection may arm listening from a partial, but only
                        # a silence-finalized utterance can execute an action.
                        command = extract_wake_command(text, wake_word)
                        if command is not None:
                            gate.until = time.monotonic() + max(2., gate.followup)
                            listening(True)
                        if active:
                            emit('partial_transcript', command if command is not None else text)
                    else:
                        emit('partial_transcript', text)
                # On a slow PC, refresh live text less often so audio is never starved.
                next_partial = time.monotonic() + max(.3, config.SPEECH_PARTIAL_SECONDS, 2 * decode_seconds)
            elif not gate and not detector.started and (finishing or time.monotonic()-started_at > 12):
                return ''
