# FLOTER — Rex, your desktop buddy

FLOTER is a Windows desktop assistant for typed and voice requests. Rex can open apps and websites, append your words to a verified Notepad draft, search the web, capture camera media, and propose reviewed tasks. Experimental navigation operates visible application controls with your review.

This documentation describes source **4.0.0**, reviewed on **27 September 2026**. The Python distribution is `floter-desktop`; the import package and command are `floter`.

## Run the current Windows application

After building, start the application from the repository root:

```powershell
& ".\dist\FLOTER\FLOTER.exe"
```

Its Windows file/product metadata reports **4.0.0**. Keep the entire `dist/FLOTER` folder together, including `_internal`; copying the EXE alone is insufficient. Source edits and documentation edits do not update an existing bundle. Metadata matching the source version does not establish that every bundled module matches the checkout.

1. Create `%USERPROFILE%\.floter\.env` using [.env.example](.env.example). If it already exists, edit it rather than overwriting your settings.
2. Add `Jev_API_Key` (your TypeSafe API key) for Jev and restart FLOTER.
3. Choose **Text**, enter `Open Calculator`, and press Enter. Shift+Enter inserts a newline.
4. For local speech, choose **Speech + Text** and say `Hey Rex, open Notepad`. A provisioned local speech model and Windows microphone permission are required.
5. Try `Type Remember to water the plants in Notepad`. Save the draft manually in Notepad to retain the edited content.

All submitted commands go through remote Jev routing, even when their resulting action is local. Local speech recognition does not make the whole assistant offline. Follow-up speech can omit the wake phrase for 20 seconds by default.

## What you can do

| Use case | Example | What to expect |
| --- | --- | --- |
| Launch your workspace | `Open VS Code` | Launch a supported installed app |
| Capture a quick note | `Open Notepad`, then `Type Buy milk in Notepad` | Append literal words to FLOTER's verified draft |
| Open a web app | `Open Gmail in Brave` | Open the site in the selected installed browser |
| Research a topic | `Search for Sydney walking trails in Edge` | Open Google results; FLOTER does not read the results |
| Capture camera media | `Take a picture` or `Record a video` | Visible preview and local JPEG/MP4 output |
| Navigate an application | `Open WhatsApp and open Mom's contact profile` | Experimental, reviewed navigation; reasoning provider required |
| Hand a prompt to an AI app | `Open Claude and enter explain photosynthesis` | Reviewed exact prompt entry into an accessible composer |
| Create a document | `Write a short project proposal in proposal.md` | Reasoning provider proposes a create-only plan for approval |
| Understand your screen | `Explain what is on my screen` | Snippy capture and Gemini image analysis |

See [FEATURES.md](FEATURES.md) for the complete feature list, prerequisites, examples and limits, and [the manual](INSTRUCTION_MANUAL.md) for everyday use.

## Optional capabilities

- **Speech:** Faster Whisper with local weights; CUDA when available, CPU fallback in auto mode. Vosk is a legacy opt-in alternative.
- **Reasoning:** configure `GEMINI_API_KEY` and `GEMINI_MODEL`, or an OpenAI-compatible Hermes provider. With no separate Hermes/OpenRouter configuration, Gemini also backs reasoning and navigation.
- **Screen analysis:** Gemini plus a configured Snippy MCP capture service.
- **Visual navigation:** optional separate local OmniParser service; see [GUI_NAVIGATION.md](GUI_NAVIGATION.md). Accessibility-based navigation does not require that service.
- **Additional apps:** private registrations in `%USERPROFILE%\.floter\applications.json`; see [CONFIGURATION.md](CONFIGURATION.md).

Configuration is file-based; the current QML interface has no Settings editor. Restart after changes. `run-local.ps1` launches the existing EXE with this checkout's `.env`, overriding the normal user dotenv location; it does not launch edited Python source.

## Develop from source

Use Windows and Python **3.12** for the development/build workflow. Package metadata permits Python 3.10+, but build tooling uses `tomllib` and the documented baseline is 3.12. Run these commands from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,voice]"
.\.venv\Scripts\python.exe scripts/provision_whisper.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m floter
```

For typed-only development, install `.[dev]` and omit model provisioning. Provisioning downloads weights explicitly; listening never downloads them. GPU speech needs an NVIDIA driver and compatible CUDA 12/cuDNN 9 runtime libraries. The `voice-light` extra and `scripts/provision_voice.py` support legacy Vosk.

## Build

Install the development and voice dependencies above and Inno Setup 6. Provision weights before building a voice bundle.

```powershell
.\.venv\Scripts\python.exe scripts/collect_notices.py
.\.venv\Scripts\python.exe -m build --wheel --no-isolation
.\.venv\Scripts\python.exe -m PyInstaller --clean floter.spec --noconfirm
.\.venv\Scripts\python.exe scripts/check_package.py
.\.venv\Scripts\python.exe scripts/build_installer.py --compiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

PyInstaller includes local model weights and GPU DLLs only when present in the build environment. The installer output is `dist/installer/FLOTER-4.0.0-Setup.exe`; local builds are unsigned unless signing is explicitly configured. Read [packaging/README.md](packaging/README.md) and [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) before distribution. The new module-level Markdown guides are source documentation; the current spec explicitly bundles only its listed root documents.

## Documentation map

| Audience | Start here |
| --- | --- |
| Users | [Features and use cases](FEATURES.md), [manual](INSTRUCTION_MANUAL.md), [configuration](CONFIGURATION.md) |
| GUI navigation users | [Setup, reviews and limits](GUI_NAVIGATION.md) |
| Contributors | [Code explainer](codeexplainer.md), [architecture](ARCHITECTURE.md) |
| Module maintainers | [Audio](audio/README.md), [routing](tiers/README.md), [tools](tools/README.md), [security](security/README.md), [UI](ui/README.md) |
| Testing and releases | [Tests](tests/README.md), [scripts](scripts/README.md), [packaging](packaging/README.md) |
| Repository context | [Documentation index](docs/README.md), [cleanup history](CLEANUP.md) |

## Data and boundaries

Audio transcription stays local. Jev receives finalized requests and bounded context. Reasoning providers receive requests and, for GUI navigation, disclosed window titles/control labels. Explicit screen explanation uploads a screenshot to Gemini; navigation screenshots are sent to the local OmniParser service. Browser searches send queries to Google.

Settings, drafts, skills, cache and startup logs live under `%USERPROFILE%\.floter`; camera files default to `%USERPROFILE%\Pictures\FLOTER`. UI history clears on exit, but saved files and startup diagnostics persist. The application has bounded tools and review gates, not an OS sandbox. It has no arbitrary shell executor, messaging workflow, spoken responses, or automatic web-result summaries.

FLOTER source uses the [MIT license](LICENSE). Bundled dependencies and models retain their own terms; see [third-party notices](THIRD_PARTY_NOTICES/README.txt).
