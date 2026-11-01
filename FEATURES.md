# FLOTER features

Implemented in source version 4.0.0; reviewed 27 September 2026. Examples express intended requests, not guaranteed keyword commands: Jev classifies them and can ask for clarification. All submitted commands require configured Jev routing, including actions performed locally. UI controls such as microphone mode and camera Stop do not require a model request.

| Feature | Example / behavior | Additional requirements and limits |
| --- | --- | --- |
| Typed commands | Enter submits; Shift+Enter adds a newline | Works without speech dependencies |
| Local speech | “Hey Rex, open Notepad” | `voice` dependencies, provisioned Whisper model, microphone permission; provisional text never executes |
| Follow-up listening | “Type hello in Notepad” after a wake command | Default 20-second window; configurable from 0–60 seconds |
| App launch | Open Notepad, Calculator, Chrome, Brave, Edge, Firefox, terminal, VS Code | App must be installed and resolve to a trusted executable |
| Selected app catalog | Notepad++, Antigravity, WhatsApp, Instagram, Microsoft Store, ChatGPT, Codex, Gemini, Claude | Private catalog configured per machine; entries do not imply installation |
| Experimental cross-application navigation | “Open Mom's profile in WhatsApp”; navigate a visible application's buttons, search fields and lists | Jev preserves the full goal; configured reasoning model, Windows UI Automation, optional local OmniParser visual fallback. Each input action is reviewed; see [GUI_NAVIGATION.md](GUI_NAVIGATION.md). |
| Keys and models | Recommended user file: `%USERPROFILE%\.floter\.env` (template: `.env.example`) | Jev key, Gemini key/model, optional OpenAI-compatible reasoning provider. One Gemini key can drive screen analysis, navigation and questions. User dotenv is outside Git and the installer; environment/source overrides are documented in CONFIGURATION.md. Restart after changes. |
| Gemini/Claude prompt handoff | “Open Claude and enter explain photosynthesis” | Jev extracts the exact prompt; registered desktop app or disclosed official-website fallback. Reviewed entry into an accessible composer, with separately reviewed submission only when explicitly requested. Login is manual; no universal app launch-argument API is assumed. |
| CUDA screen parsing | Microsoft OmniParser YOLOv9-E detector + Florence-2 captions, EasyOCR text | Separate local service; CUDA required by default, FP16 models, single-icon caption batches, CPU OCR to conserve VRAM. No guarantee of all-app coverage. |
| App closing | “Close WhatsApp” | One verified window, normal save prompts; no force kill or individual tab closing; browser-hosted app closing unsupported |
| Notepad dictation | Append literal supplied words to the assistant-created draft | Identity check and readback; changed tabs or Save As can invalidate the target; edits remain unsaved until saved in Notepad |
| Websites and web apps | “Open Gmail on Brave”, “Open YouTube”, “Go to bbc.com” | Built-in list: YouTube, Google, Gmail, Google Drive/Docs/Calendar/Maps, Outlook, GitHub, Wikipedia, LinkedIn, Reddit, Netflix, ChatGPT, Gemini, Claude. Other sites open by address, or via a search when only a name is given. Opens in the named browser (Brave, Chrome, Edge, Firefox) or your default browser. HTTPS only. |
| Internet lookup | “Look for cheap flights to Sydney in Chrome” | Jev picks out the search topic (falls back to the full request); opens Google results in the named or default browser. Does not read pages, summarize results or browse autonomously |
| Camera preview | “Open the camera” | Camera hardware and Windows permissions; visible separate preview |
| Camera photo | “Take a picture” | Saves a uniquely named JPEG under Pictures/FLOTER by default |
| Camera video | “Record a video”; “stop recording” | MP4, configurable 1–300-second limit, default 60; microphone audio optional; Stop button works without network |
| Storage inspection | Drive capacity/free space and bounded inventory | Read-only, time/entry budgets; not a complete disk index |
| Screenshot/OCR | Screenshot, text, table, colors, monitor layout | Separately configured Snippy MCP and supported server tools |
| Screen explanation | “Explain what is on my screen” | Snippy capture plus Gemini configuration; screenshot leaves the device |
| Advice and writing | Ask for explanations or original prose | Configured Hermes/OpenAI-compatible endpoint; generated documents use reviewed plans |
| Multi-step plans | Open supported apps/sites, create text documents, inspect storage, capture screen | Hermes; strict schema, maximum eight actions, approval before execution |
| Saved plans | `save skill morning`, `list skills`, `run skill morning` | Save the last successfully completed approved plan; every run needs fresh approval |
| UI feedback | Monochrome animated face with sleeping, upward eye roll and curiosity, wrapped results, Logs, command history | Session history capped at 500 entries; clears on exit; preserves newer input drafts |

## Practical use cases

### 1. Capture a quick note while working

**Requires:** Jev, trusted Notepad; local speech model and microphone only if speaking.

1. Say `Hey Rex, open Notepad`, or submit `Open Notepad` in Text mode.
2. Submit `Type Buy milk and call the plumber in Notepad`.
3. Submit `Type Book the car service in Notepad` to append another line.
4. Save in Notepad manually.

FLOTER binds its own uniquely named draft and verifies edits. It does not choose an arbitrary existing document. A tab change or Save As can invalidate the binding; reopen Notepad through FLOTER to establish a new draft. This workflow uses your supplied words; generating original prose is a separate reviewed-plan workflow.

### 2. Start research in your preferred browser

**Requires:** Jev and an installed supported browser; no additional search API key.

- `Open Gmail in Brave` opens the configured Gmail URL.
- `Search for walking trails near Sydney with train access in Edge` opens Google results for the extracted topic.
- `Go to bbc.com` opens an HTTPS address; an unrecognized site name can become a search so you can choose a result.

FLOTER opens pages but does not fetch, evaluate or summarize search results. Browser selection depends on the classifier identifying an available browser; an absent/uncertain selection uses the default browser.

### 3. Record a short webcam update

**Requires:** Jev, a camera and Windows permissions; microphone permission for audio recording.

1. Submit `Open the camera` to inspect the visible preview.
2. Submit `Take a picture` for a JPEG, or `Record a video` for an MP4.
3. Use the camera Stop control, or submit `Stop recording`, to finish early.

The default recording limit is 60 seconds, configurable up to 300. The camera Stop control works without a network request. Output defaults to `%USERPROFILE%/Pictures/FLOTER`. A start-success message means recording has started; wait for finalization before treating the file as complete.

### 4. Navigate a visible application's interface

**Requires:** Jev, a configured reasoning provider, a visible identifiable app and user review. OmniParser is optional unless visual fallback is needed.

Try `Open Calculator and switch to Scientific mode`, or `Open WhatsApp and open Mom's contact profile` after registering the installed app. Review disclosure of screen labels, the chosen window, each input action and completion evidence. Ambiguous contacts or inaccessible controls require manual help.

For AI handoff, try `Open Claude and enter explain photosynthesis`. The exact extracted prompt is staged in an accessible composer. An explicit ask/send/submit request can propose a separately reviewed Submit click. Login is manual. Generic message sending to people is not implemented. See [GUI_NAVIGATION.md](GUI_NAVIGATION.md).

### 5. Create writing or save a repeatable workspace plan

**Requires:** Jev plus a reasoning provider (Gemini or a configured Hermes-compatible endpoint).

- `Write a short project proposal in proposal.md` proposes a new file for review.
- `Open Calculator and then GitHub` proposes a bounded multi-action plan.
- After a plan completes, submit `save skill morning`, then `list skills`.
- Submit `run skill morning` and approve the saved plan again.

Plans contain at most eight supported actions. New documents default to the Desktop, falling back to the home directory when Desktop is absent. Existing files are not overwritten. Skill names start with a lowercase letter and contain up to 40 lowercase letters, digits, underscores or hyphens. Saving an existing skill name is refused. A saved plan that creates a fixed filename can fail on replay once that file exists. Earlier completed actions are not rolled back if a later action fails.

### 6. Understand a screen or inspect storage

**Requires:** Jev; Snippy for screen capture/OCR; Gemini additionally for image explanation.

- `Take a screenshot` saves validated Snippy image bytes locally.
- `Extract text from my screen` calls the configured Snippy OCR tool.
- `Explain what is on my screen` sends a captured screenshot and question to Gemini.
- `Show storage information for all drives` performs bounded read-only inspection without Snippy or Gemini.

Screen explanation uploads an image; GUI navigation instead sends textual element descriptions to its reasoning provider and uses the local parser for images. Storage inspection is budget-limited and is not a complete disk index.

## Deliberate limits

There is no arbitrary shell execution, unrestricted keyboard automation, message sending workflow, screen recording, spoken response generation, or automatic web-result summarization. GUI navigation can observe visible chat labels and text; the user reviews disclosure before those labels go to the configured reasoning provider. Dedicated browser DOM integration and individual tab-closing commands remain unsupported. Camera requests do not support spoken custom durations or device switching.

Legacy Vosk is optional and is not the default packaged voice path.

## Availability and acceptance

Jev/provider availability, installed apps, device permissions and local model provisioning affect behavior. Unit tests establish specific code behavior; live microphone accuracy, camera encoding, GPU availability and clean-machine installer lifecycle require target-machine checks. See [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) and [INSTRUCTION_MANUAL.md](INSTRUCTION_MANUAL.md).
