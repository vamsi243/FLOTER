# FLOTER configuration

Experimental GUI navigation uses the additional settings and separate CUDA runtime described in [GUI_NAVIGATION.md](GUI_NAVIGATION.md).

Configuration, drafts, skills, cache and startup logs default to `%USERPROFILE%\.floter`. Camera captures default to Pictures/FLOTER; generated documents go to Desktop, or the home directory if Desktop is absent. The current UI has no Settings editor; edit the configuration file and restart.

Copy `.env.example` to `%USERPROFILE%\.floter\.env`, fill in your keys, and restart the app after changes. This one file is used by source runs and the built EXE. No keys are bundled in the source tree, wheel or installer, and the file is outside the Git repository. A secrets folder works only when `FLOTER_ENV_FILE` points to a dotenv file inside it; no folder scan or credential-store lookup occurs.

The first-defined value wins: process environment; the file selected by `FLOTER_ENV_FILE`, or `%USERPROFILE%/.floter/.env` when no override is set; then, only in source runs, source `.env` followed by parent `.env`. Setting `FLOTER_ENV_FILE` replaces the user dotenv path; it does not add another fallback. Blank-value behavior is field-specific: numeric settings and several paths/endpoints use defaults, while model/key fields can remain empty. `run-local.ps1` explicitly selects the checkout `.env` and runs the frozen EXE. Invalid numeric values fall back to defaults and are reported in the activity log at startup; startup failures are saved to `.floter/logs/startup-error.log`.

| Purpose | Variables |
| --- | --- |
| Mandatory Jev (native TypeSafe) | `Jev_API_Key`; `JEV_ENDPOINT=https://api.typesafe.ai/v1/systemone`; blank `JEV_MODEL` selects `jev-latest`. Old `ai-gateway.vercel.sh` endpoints are redirected to the native API. |
| Speech | `STT_ENGINE=auto` or `faster-whisper` selects Faster Whisper. `vosk` remains an optional legacy source mode with separately provisioned weights. |
| Local model | `WHISPER_MODEL_PATH` blank uses the bundled `models/faster-whisper-small.en`. Source users run `scripts/provision_whisper.py`. No model downloads during listening. |
| Device | `WHISPER_DEVICE=auto` probes CUDA, otherwise CPU. Explicit `cuda` errors when unavailable; `cpu` forces CPU. CUDA 12/cuDNN 9 runtime DLLs and an NVIDIA driver are required for GPU use. |
| End of speech | `SPEECH_SILENCE_SECONDS=0.7`, allowed range 0.35–2.0; invalid values reset to 0.7. |
| Rolling text | `SPEECH_PARTIAL_SECONDS=0.6`, allowed range 0.3–5.0; invalid values reset to 0.6; decoding time also affects update rate. |
| Wake | `WAKE_WORD=hey rex`. The old default `hey floter` migrates automatically. `VOICE_FOLLOWUP_SECONDS=20`, allowed range 0–60; invalid values reset to 20. |
| Hermes via OpenRouter | `OPENROUTER_API_KEY`, `HERMES_API_BASE=https://openrouter.ai/api/v1`, `HERMES_MODEL` set to an available model ID. Supports generated prose, advice and plans; Gemini can provide the same reasoning role as described below. |
| Other Hermes endpoint | `HERMES_API_KEY` takes precedence over OpenRouter key. Use an OpenAI-compatible `/v1` base; `/chat/completions` is appended. Loopback HTTP is allowed for a local server. |
| Gemini | `GEMINI_API_KEY` and `GEMINI_MODEL`. With no OpenRouter/Hermes key and no `HERMES_API_BASE`, Gemini also handles app navigation and questions through its OpenAI-compatible endpoint. `GEMINI_VISION_MODEL` optionally overrides the screen-analysis model. Check with `python scripts/check_gemini.py`. |
| Snippy | `SNIPPY_COMMAND` absolute MCP executable; `SNIPPY_ARGS` JSON array; optional `SNIPPY_CWD`. Alternatively `SNIPPY_URL` is a loopback SSE URL and takes precedence. |
| Windows backdrop | `MICA_ENABLED` is retained for compatibility; the borderless buddy view uses a solid navy background and does not apply Mica. |
| Camera selection | `CAMERA_DEVICE` blank selects the default camera; otherwise use an exact device description. Windows must allow desktop camera access. |
| Camera output | `CAMERA_SAVE_DIR` blank uses `%USERPROFILE%\Pictures\FLOTER`. JPEG photos and MP4 videos stay local. |
| Video duration | `CAMERA_VIDEO_SECONDS=60`, allowed range 1–300 seconds; invalid values reset to 60. Stop earlier by voice or the camera window's Stop / Close button. |
| Video audio | `CAMERA_RECORD_AUDIO=1` records the default microphone; `0` creates silent video. Microphone access must be allowed for audio. |
| Browser automation | `BROWSER_AUTOMATION=0`. `1` opens websites in FLOTER's own browser window and lets Rex act inside the page; see [GUI_NAVIGATION.md](GUI_NAVIGATION.md). Requires the `browser` extra (`pip install ".[browser]"`). |
| Browser | `BROWSER_CHANNEL=msedge`, `chrome` or `brave` drives that installed browser with FLOTER's own profile; invalid values reset to `msedge`. `BROWSER_PROFILE_DIR` blank uses `%USERPROFILE%\.floter\browser-profile`. |
| Browser input sites | `BROWSER_INPUT_SITES=youtube.com,google.com,wikipedia.org`: hosts (and subdomains) where Rex may click or type. Other sites can be opened and read but not changed. |

No extra API key is needed for LangChain schemas, local Notepad typing, or browser search. Those task requests still require Jev routing. Search opens Google results rather than fetching summaries. No LangSmith account is required; optional external tracing should be configured deliberately if desired.

FLOTER reads `%USERPROFILE%\.floter\applications.json` and accepts nine catalog identifiers: `notepad-plus-plus`, `antigravity-ide`, `whatsapp`, `instagram`, `microsoft-store`, `chatgpt`, `codex`, `gemini` and `claude`. A catalog identifier does not establish that the application is installed. Unknown identifiers are ignored. Existing built-in launch actions remain supported. Your selected application paths are listed in the local source-workspace report `acceptance-output/application-paths.md`; this machine-specific report is not bundled in the installer. Refresh registrations with `scripts/inventory_apps.ps1`, then run `scripts/configure_apps.py --install` to configure the selected apps. The first replacement preserves the previous catalog as `applications.before-selected-apps.json`. Personal paths and credentials are not bundled.

Closing an application is a local, Jev-routed `WM_CLOSE` request for one uniquely identified window. It allows the application to show its normal save prompt and never force-terminates a process. Closing an individual browser or Notepad tab is unsupported. Hermes is not required for this basic close action; A reasoning provider is used for generated answers, plans and experimental GUI navigation.

When Instagram is installed as an Edge-hosted app, it uses its Windows registered launch ID. It has no separate executable to identify for safe window closing, so closing it remains manual. Gemini uses a stable launcher and a versioned runtime; both paths are recorded during catalog refresh.

The installed app uses the Windows default input device. Allow desktop microphone access. Audio remains local; finalized text/session context goes to Jev. Explicit screen analysis uploads a screenshot. Transcripts and results remain in the session log; drafts, saved skills and screenshot cache are under `.floter`; camera media is in Pictures/FLOTER unless overridden.

Optional signing variables remain `FLOTER_SIGNTOOL`, `FLOTER_CERT_SHA1` and `FLOTER_TIMESTAMP_URL`; these are build-process variables, not app API keys. The installer builder does not read dotenv. `--sign` enables signing; current local builds are unsigned.

## Manual application registration example

The private catalog uses an `applications` object. For an installed Claude executable, substitute its actual absolute path:

```json
{
  "version": 1,
  "applications": {
    "claude": {
      "name": "Claude",
      "kind": "exe",
      "target": "C:\\Path\\To\\Claude.exe",
      "executable": "C:\\Path\\To\\Claude.exe"
    }
  }
}
```

Merge entries into an existing catalog instead of replacing unrelated registrations. `registered` entries use a Windows application ID such as a discovered `Package!App` value. Do not invent that ID; use the inventory workflow in [scripts/README.md](scripts/README.md). Restart FLOTER after editing. Absolute existing `CLAUDE_APP_PATH` and `GEMINI_APP_PATH` environment settings can also register those two EXEs; JSON is the more general catalog mechanism.
