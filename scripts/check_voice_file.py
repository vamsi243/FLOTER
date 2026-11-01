"""Offline streaming ASR benchmark; accepts synthetic/user-supplied WAV only."""
import argparse
import json
import time
import wave
from pathlib import Path
from vosk import Model, KaldiRecognizer, SetLogLevel
from floter.config import config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('wav', type=Path)
    args = parser.parse_args()
    SetLogLevel(-1)
    start = time.perf_counter()
    model = Model(config.VOSK_MODEL_PATH)
    load_time = time.perf_counter()-start
    recognizer = KaldiRecognizer(model, 16000)
    partials = []
    finals = []
    start = time.perf_counter()
    with wave.open(str(args.wav),'rb') as audio:
        if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate()) != (1,2,16000):
            raise ValueError('Provide 16 kHz mono PCM16 WAV')
        seconds = audio.getnframes()/16000
        while raw := audio.readframes(1280):
            if recognizer.AcceptWaveform(raw):
                finals.append(json.loads(recognizer.Result()).get('text',''))
            else:
                text = json.loads(recognizer.PartialResult()).get('partial','')
                if text and (not partials or partials[-1] != text):
                    partials.append(text)
    # End-of-file finalization is for this benchmark, not the microphone path.
    finals.append(json.loads(recognizer.FinalResult()).get('text',''))
    result = {'model_load_seconds':load_time, 'decode_seconds':time.perf_counter()-start,
              'audio_seconds':seconds, 'partial_updates':partials, 'text':' '.join(t for t in finals if t)}
    output = Path(__file__).resolve().parents[1]/'acceptance-output'/'voice-file-check.json'
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__ == '__main__': main()
