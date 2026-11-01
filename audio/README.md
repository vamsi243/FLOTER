# Local speech input

FLOTER 0.3.8 source guide, reviewed 27 September 2026.

This package captures microphone input and transcribes it locally. It supplies final commands to the UI bridge; it does not classify or execute them.

Install `.[voice]` and run `python scripts/provision_whisper.py` from the repository root. Select Speech + Text, then say `Hey Rex, open Calculator`. Say `Hey Rex` alone to arm the follow-up window. Select Text to stop wake listening. A final submitted command still requires Jev connectivity.

Faster Whisper is the default. `WHISPER_DEVICE=auto` chooses CUDA when usable and can fall back to CPU. Explicit `cuda` fails if unavailable. `STT_ENGINE=vosk` selects the separately provisioned legacy path. Configuration and model locations are in [CONFIGURATION.md](../CONFIGURATION.md).

Partial transcripts are provisional; they never execute. Follow-ups default to 20 seconds. Windows microphone permissions and the default input device determine capture availability.

See [codeexplainer.md](codeexplainer.md) for implementation details and the [main README](../README.md) for setup.
