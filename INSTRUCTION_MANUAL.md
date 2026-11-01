# FLOTER instruction manual

FLOTER is the application; Rex is its desktop buddy persona. This manual describes source 4.0.0, reviewed 27 September 2026. FLOTER runs on Windows 10/11 and accepts typed or spoken commands. Every task is classified by Jev. Speech recognition runs locally using Faster Whisper.

## 1. Install and configure

Run `FLOTER-4.0.0-Setup.exe`, or keep the whole `dist/FLOTER` folder and start `FLOTER.exe`. The EXE needs its `_internal` folder. Builds are unsigned. The build includes a voice model only if it was present when packaged; your API keys and personal application paths are not.

### Camera photos and videos

Connect a webcam (or use your built-in camera) and allow desktop camera access in Windows Settings. FLOTER opens its own visible camera window; it does not automate the separate Windows Camera app. No additional API key is needed beyond Jev routing.

| Request | Action |
| --- | --- |
| “Hey Rex, can you take a picture?” | Opens the camera preview, takes a JPEG photo, closes the preview, and shows the saved path in Logs/results. |
| “Open the camera” | Shows a live preview without saving media. |
| “Open the camera and record a video” | Starts an MP4 recording with microphone audio and a visible elapsed-time indicator. |
| “Hey Rex, stop recording” | Stops, finishes saving the MP4 and closes the camera window. The Stop / Close button does the same without requiring Jev/network access. |
| “Close the camera” | Closes the preview, or stops and saves the active recording before closing. |

Files default to `%USERPROFILE%\Pictures\FLOTER` with unique names. Recordings stop automatically after 60 seconds unless `CAMERA_VIDEO_SECONDS` changes that limit (1–300 seconds). Set `CAMERA_RECORD_AUDIO=0` for silent video; otherwise a working default microphone is required. `CAMERA_DEVICE` selects an exact Windows device description; blank uses the default. `CAMERA_SAVE_DIR` overrides the output folder. Restart after configuration changes. Spoken custom durations, camera switching and screen recording are not implemented. Taking a screenshot remains a separate Snippy action.

When a request requires unconfigured reasoning, FLOTER now says “I'm not configured to process this request yet” and suggests available actions. Provider configuration details remain in CONFIGURATION.md.

Create `%USERPROFILE%\.floter\.env` (copy `.env.example`) with:

```dotenv
Jev_API_Key=your-private-typesafe-api-key
JEV_ENDPOINT=https://api.typesafe.ai/v1/systemone
STT_ENGINE=faster-whisper
WHISPER_DEVICE=auto
WAKE_WORD=hey rex
SPEECH_SILENCE_SECONDS=0.7
SPEECH_PARTIAL_SECONDS=0.6
VOICE_FOLLOWUP_SECONDS=20
```

Restart after changing settings. Source runs also read the source `.env`. The old default `hey floter` migrates to `hey rex`. Do not share your actual `.env` file. See CONFIGURATION.md for other providers and configuration precedence.

CUDA is used when an NVIDIA GPU and compatible CUDA 12/cuDNN 9 runtime are available. Frozen builds include runtime libraries only when present in the build environment; an NVIDIA display driver is installed separately. `auto` falls back to CPU if model initialization fails; explicit `cuda` reports failure instead. The engine/device appears in Logs. CPU recognition can be slower.

## 2. Microphone and speech

Select your built-in or external microphone as the default Windows input device. Enable desktop microphone access in Windows Settings. You do not need an extra USB microphone if the built-in one works.

- **Text:** microphone off. Type in the command box and press Enter to run. Shift+Enter inserts a newline.
- **Speech + Text:** enables local wake listening while keeping keyboard entry available. Say Hey Rex; the face opens its eyes and the microphone indicator lights up when recognized. Speak your command; rolling text appears in the same the command box box.
- **Pause at the end:** roughly 0.7 seconds of silence marks the utterance complete; final decoding and Jev processing follow. No Enter click is needed.
- **Return to Text:** cancels unfinished speech, clears queued voice commands and switches the microphone off. It does not undo a task already executing.
- **Follow-ups:** say “Hey Rex, can you try opening a note pad?” The next command may omit the wake phrase for 20 seconds. Each accepted follow-up refreshes that window. After it expires, say Hey Rex again.
- **Hey Rex alone:** arms the follow-up window so you can say the command separately.

Partials may be revised. They never execute actions. Dispatch occurs once after a completed utterance, avoiding accidental execution while you are still correcting or extending a sentence. This is rolling transcription, not a guarantee of instantaneous decoding. Commands are limited to about 20 seconds. Excessively long/overflowed audio is discarded rather than submitted as a truncated command.

## 3. Features and examples

| Feature | How to use it | What happens |
| --- | --- | --- |
| Open an application | “Hey Rex, can you try opening a note pad?” | Jev selects Notepad. FLOTER opens a new uniquely named draft and identifies its editor. Other supported apps include installed Chrome, Brave, Calculator, terminal and VS Code. |
| Open a configured installed app | “Can you open WhatsApp?”, “open WhatsApp”, or “let’s open WhatsApp” | Jev selects the named catalog entry and uses its verified executable or Windows registered app ID. The private catalog adds the selected apps, including Claude. |
| Close an application | “Close WhatsApp” | Jev requests a normal close for one uniquely identified window. Save prompts remain under the application’s control. Individual tabs are unsupported. Hermes is not required. |
| Type into that Notepad | “Try write how are you doing on the notepad.” | Jev extracts `how are you doing` and appends it to the identified draft. Existing text is retained. No global keyboard shortcuts or clipboard are used. |
| Additional text | “Type good morning in Notepad.” | Appends to the same draft, separated by a newline. Save manually in Notepad if you want to retain the edited content on disk. |
| Internet lookup | “Look up the latest Python release on the internet.” | Jev selects the search tool and picks out the exact topic words (the full request is used if it is unsure). Results open in Google in your default browser, or the browser you name. No additional search API key is required. |
| Context in a search | “Search for hiking trails near Sydney with train access on Edge.” | The topic and constraints are kept word for word; the browser name is not searched. FLOTER does not claim it has read or summarized the search results. |
| Websites | “Open Gmail on Brave.” “Open YouTube.” “Go to bbc.com.” | Opens built-in sites (Gmail, YouTube, Google Drive, Outlook and more), any address you say, or a search for a named site. Uses the browser you name (Brave, Chrome, Edge, Firefox) or your default browser. If Jev is unsure, FLOTER asks you to rephrase instead of guessing. |
| Drive information | “Show storage information for all drives.” | Shows drive capacity/free space and a bounded directory inventory in Logs. It is not an exhaustive file catalog. |
| Screenshot | “Take a screenshot.” | Requires separately configured Snippy MCP. Saves an image locally. |
| OCR/table/colors/monitors | “Extract the text from my screen.” | Routes to an available Snippy tool. |
| Explain the screen | “Explain what is on my screen.” | Requires Snippy and Gemini; uploads a screenshot and your question for analysis. |
| Generate new prose | “Write an essay about climate change.” | Requires a configured reasoning provider (Gemini or a Hermes-compatible endpoint). Generated documents and multi-step plans are reviewed before execution. Literal dictation requires only Jev. |
| Multi-step plan | “Open Calculator and then GitHub.” | Hermes proposes supported actions; review and approve the plan. |
| Saved plans | `save skill morning`, `list skills`, `run skill morning` | Save the last completed approved plan, list saved plans, or review/run a saved plan. Save/run names use the shown exact syntax. |
| Logs | Click Activity | See requests, routing confidence, errors and results for the latest 500 session entries. Cleared on exit. |

Notepad typing deliberately targets the FLOTER draft. If you change tabs, close it, or Save As another filename, FLOTER may stop rather than type into a different document. Ask it to open Notepad again to establish a new draft. Empty draft files are under `%USERPROFILE%\.floter\drafts`; typed edits are unsaved until you save them in Notepad.

## 4. Window controls

The borderless window has a draggable branded header and dedicated minimize, maximize/restore and close buttons. Drag any edge or corner to resize; double-click the header to maximize or restore. The shared input and result areas wrap and scroll. Activity sits at the far right of the mode row. Tab moves keyboard focus; Enter submits typed text. Successful actions clear their submitted text; an unfinished/newly typed draft is preserved. Failures retain the command for correction or retry. The app remains above ordinary windows.

The interface uses a navy (#172f64) background with off-white (#f4f4f4) text and a floating expressive face. There are no outer application borders. The supplied FLOTER logo appears in the header and Windows application/installer icons. Expressions use eye shape, gaze, brows, mouth and head tilt to show waiting, listening, thinking, working, success, errors and approval. While idle in Text mode, the face occasionally rolls its eyes upward or looks curious, then sleeps after 30 seconds with closed eyes and gentle breathing. A task or voice-mode change wakes it immediately. Idle animations pause while minimized. Task and approval expressions take priority over idle expressions; status text and logs remain available. Success means the executor reported success, not independent verification of every external action.

## 5. Routing and confidence

All submitted tasks go through Jev; there is no local intent-regex fallback. Most automatic actions require route confidence and chosen-option probability of at least 0.85; website/search routes use 0.60. Reviewed GUI navigation also accepts summed GUI-family probability of at least 0.85. Literal Notepad text uses a second Jev evaluation to select the start/end words from the original request; both boundary scores must reach 0.70. Text cannot be invented by that extraction step. Uncertain non-advice decisions ask for clarification without executing. Explicit advice requests use the configured reasoning provider.

Classifications can still be wrong. Notepad writes only to a verified draft, and search opens a fixed HTTPS search endpoint with encoded query text. There is no arbitrary shell tool. Normal closing requires a uniquely identified application window and preserves save prompts. Individual tabs, browser-hosted app closing (including Instagram), and unrestricted desktop automation remain unsupported. Experimental reviewed GUI navigation is described below. New capabilities require execution code; neither Jev nor a Hermes key adds them automatically.

## What connecting Hermes enables

This integration calls an OpenAI-compatible reasoning-model endpoint; it does not connect a separate autonomous desktop-control agent.

| Capability | Available after configuration | Example |
| --- | --- | --- |
| Answers and writing | Hermes returns generated text in results/logs. | “Explain this Python error.” |
| New text/Markdown documents | Hermes proposes a create-only file action, subject to your approval. | “Write a short project proposal in proposal.md.” |
| Open generated writing in Notepad | A reviewed plan creates a new file and opens it. | “Write a paragraph about renewable energy in Notepad.” |
| Multi-step tasks | Reviewed plans may contain up to eight implemented actions: app/site launches, new text documents, Notepad documents, bounded storage inspection, and Snippy capture when configured. | “Open WhatsApp and then Notepad++.” |
| Uncertain requests | Uncertain non-advice decisions ask for rephrasing. Explicit advice requests can use the reasoning provider; they do not execute arbitrary tools. | An ambiguous application or unsupported task. |
| Saved plans | A successfully approved plan can be saved, listed and reviewed before running again. | `save skill morning`, then `run skill morning`. |

Set `OPENROUTER_API_KEY`, `HERMES_API_BASE=https://openrouter.ai/api/v1`, and `HERMES_MODEL` to a model ID supported by your provider. Alternatively use `HERMES_API_KEY` with another compatible endpoint, or a configured local loopback server. Restart FLOTER after changing `.floter/.env`. Validate live generation against your configured provider before release.

Connecting a reasoning provider supports the implemented reviewed GUI navigation loop, which may observe visible chat labels after disclosure. It does not add a dedicated chat-reading/messaging API, tab controls, arbitrary shell commands or autonomous web browsing. Browser search currently opens results without reading/summarizing pages. Screen analysis separately requires Gemini and screenshot capture. These capabilities would need additional task-specific tools and integration work.

## 6. Troubleshooting

- **No command runs:** confirm your Jev API key/endpoint and internet connection. Speech decoding works offline, routing does not. Transient 429/502/503/504 classification failures have bounded retries; persistent failures perform no action.
- **Wrong words:** reduce background noise, position the mic closer, and try shorter complete phrases. Use the text field to correct a command. Live partials are provisional; the final decode uses a wider beam. Real microphone/accent accuracy is not guaranteed by synthetic tests.
- **Slow recognition:** check Logs for CPU versus CUDA. Set `WHISPER_DEVICE=cuda` to get an explicit runtime error rather than silently using CPU. `WHISPER_MODEL_PATH` must point to an extracted CTranslate2 Whisper model; changing it may change accuracy, speed and memory needs.
- **Splits a long pause:** increase `SPEECH_SILENCE_SECONDS` up to 2.0. Larger values delay submission.
- **Wake follow-up not accepted:** the follow-up window may have expired. Say Hey Rex again. Set `VOICE_FOLLOWUP_SECONDS=0` to require the phrase for every wake-mode command.
- **Notepad target changed:** reopen it through FLOTER. Existing documents are not automatically selected for editing.
- **Long results:** scroll the result region or open Logs. The UI does not trim the visible result to two lines.

## 7. Privacy and optional credentials

Audio stays local. Finalized commands and bounded session context go to Jev. A search sends its query to Google through your browser. Explicit screen analysis uploads an image to Gemini. The reasoning provider receives escalated text and, during reviewed GUI navigation, window titles and textual screen elements. Navigation screenshots go only to the local parser. No API key is needed for local transcription or LangChain tool schemas, and no LangSmith account is required.

Optional provider settings: `OPENROUTER_API_KEY` or `HERMES_API_KEY` plus Hermes base/model; `GEMINI_API_KEY` and model IDs; Snippy executable or loopback URL. See CONFIGURATION.md. The MIT license covers FLOTER source; bundled dependencies retain their own notices.
# Experimental Rex application navigation

In FLOTER 4.0.0, add your Jev key and `GEMINI_API_KEY` / `GEMINI_MODEL` (or another reasoning provider) to `%USERPROFILE%\.floter\.env` and restart. Follow [GUI_NAVIGATION.md](GUI_NAVIGATION.md) for optional local CUDA visual parsing. Ask for a complete goal such as “Open WhatsApp and open Mom's contact profile” or “Open Claude and enter explain photosynthesis.” Review the chosen window and each proposed action. Use Cancel on a review or Stop in FLOTER to halt navigation.
