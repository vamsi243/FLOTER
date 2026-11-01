# Local speech input: code explainer

Reviewed against FLOTER 0.3.8 on 27 September 2026.

## Files and flow

| File | Role |
| --- | --- |
| `listener.py` | `AudioListener` lifecycle, isolated worker callbacks, wake-prefix extraction, `SpeechEndpoint`, legacy Vosk capture |
| `whisper_stream.py` | Local model loading, CUDA DLL paths, bounded audio capture, partial/final decoding and `WakeSession` |

`AudioListener` forwards worker progress to bridge callbacks. `stream_whisper` decouples the sounddevice callback from decoding with a bounded queue. Partial decoding uses recent audio, while final decoding processes the completed utterance. `WakeSession.accept` removes a wake prefix or accepts a command within the follow-up window. Wake-prefix removal preserves the supplied command's capitalization and punctuation.

`load_model` uses `local_files_only=True` and exercises inference after loading. Automatic CUDA initialization failures can fall back to CPU; it does not download missing weights. Overflow and overly long utterances are discarded rather than submitted as clipped commands.

## Change safely

Keep capture callbacks lightweight, preserve cancellation, and never dispatch partial text. Timing changes affect responsiveness and accidental sentence splitting; validate with real microphone input as well as tests. Relevant coverage: `test_streaming_voice.py`, `test_regressions.py`, `test_floter_features.py` in [tests](../tests/README.md).

[Module overview](README.md) · [Repository code explainer](../codeexplainer.md)
