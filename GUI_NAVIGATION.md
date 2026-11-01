# Rex application navigation (experimental, FLOTER 4.0.0)

Jev routes the complete request to one GUI agent. Named configured apps can be launched first; other apps must already have a visible identifiable window. The same observe/reason/review/act loop works across applications, without claiming universal coverage. It prefers Windows UI Automation and can ask the local OmniParser service for visual regions and icon captions. Browser windows use accessibility/vision, not a separate DOM integration.

The user reviews the task disclosure, chosen application, each click/type/scroll, and the completion evidence. Text labels may include private screen content and go to the configured reasoning endpoint. Images go only to the authenticated loopback OmniParser service. Visible content is treated as untrusted data in the model prompt. Review is essential: prompt instructions and model confidence are not security boundaries. No message sending, purchases, deletion, passwords or security-change workflows are supported.

The agent permits 16 reasoning iterations and checks a five-minute loop deadline between steps; this is not a hard five-minute wall-clock timeout for a step already in progress. Each review expires after two minutes. Stop in FLOTER cancels pending reviews/network requests; Escape is checked before desktop input. Completed side effects cannot be undone. Changed focus, window bounds, control identity, or target appearance stop execution. Typing uses UI Automation ValuePattern on an accessible non-password field; visual-only typing is not supported. Popups in separate windows and inaccessible/elevated controls may require manual interaction. Native accessibility calls run in a disposable worker with a 20-second call timeout; this is not an OS sandbox.

## Browser automation (experimental)

With `BROWSER_AUTOMATION=1`, websites open in FLOTER's own browser window: the installed Microsoft Edge by default, or Chrome or Brave through `BROWSER_CHANNEL`. Brave runs as a separate window with FLOTER's profile, alongside your normal Brave; your everyday Brave profile, logins and extensions are not used. Brave is not in Playwright's official support matrix; if a Brave update breaks automation, switch to `msedge`. The window uses a separate profile in `%USERPROFILE%\.floter\browser-profile`, not your everyday browser, and FLOTER opens no remote-debugging port. You start signed out; sign in manually in that window if a site needs it. Naming a browser ("open Gmail in Brave") still uses that browser.

Follow-ups such as "search for Shape of You", "play the second video" or "open Shorts" act inside the open page. Rex reads the page's interactive elements as text (roles, labels, positions; never field values or screenshots) and sends them to your configured reasoning provider. You review every click, text entry, Enter key, scroll and back action. Actions target page elements, not screen coordinates, so FLOTER stays visible.

Rex never fills password fields or uses controls labelled send, post, publish, buy, pay, checkout, place order, delete, remove, unsubscribe, sign out or log out. Clicking and typing are limited to `BROWSER_INPUT_SITES` (default `youtube.com,google.com,wikipedia.org`); other sites can be opened but not changed. Rex acts on the most recently opened tab. Content inside cross-site frames is not visible to it. The browser window closes when FLOTER exits; if you close it, the next request reopens it.

Install for source runs with `.\.venv\Scripts\python.exe -m pip install ".[browser]"`. No separate browser download is needed.

## Local CUDA setup

Keep the heavy runtime separate from FLOTER's Qt/Whisper environment. From the project root:

```powershell
git clone https://github.com/microsoft/OmniParser.git .tools/OmniParser
git -C .tools/OmniParser checkout 354021201345a96178360b28733573e27269f2de
.\.venv\Scripts\python.exe -m venv .tools/omniparser-env
.\.tools\omniparser-env\Scripts\python.exe -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
.\.tools\omniparser-env\Scripts\python.exe -m pip install -r scripts/omniparser_requirements.txt
.\.tools\omniparser-env\Scripts\python.exe scripts/provision_omniparser.py
.\scripts\start_omniparser.ps1
.\.venv\Scripts\python.exe -m floter
```

The service defaults to CUDA and fails explicitly if unavailable. CPU requires `-Device cpu`. YOLO uses FP16 with CUDA autocast through Microsoft's adapter and 640-pixel detector inputs; Florence uses FP16 and single-icon batches. The reduced detector resolution conserves memory but may miss small controls. EasyOCR stays on CPU, leaving more GPU memory for detector/caption models and Whisper. A 4 GB GPU may still run out of memory with other workloads; stop competing GPU tasks or use CPU explicitly. Model downloads happen only during provisioning. The service keeps models warm between requests.

FLOTER starts the service automatically the first time navigation needs visual parsing (set `OMNIPARSER_HOME` to this source folder for the built EXE), waits for it to load, and stops it when FLOTER exits. `scripts/start_omniparser.ps1` still starts it manually. The service binds 127.0.0.1:8766 and writes a new token to `%USERPROFILE%/.floter/omniparser.token`; logs go to `%USERPROFILE%/.floter/logs`.

## Configuration

`GUI_MODEL_API_BASE`, `GUI_MODEL`, and `GUI_MODEL_API_KEY` default to the existing Hermes endpoint/model/key. The model selects JSON actions from textual accessibility/OmniParser descriptions; it does not receive screenshots, so a text model is supported. A loopback OpenAI-compatible model endpoint is supported without a key. Remote endpoints require HTTPS and credentials. No new model provider is silently enabled.

`OMNIPARSER_URL` defaults to `http://127.0.0.1:8766`; only loopback HTTP is accepted. `OMNIPARSER_TOKEN_FILE` can override the token path. Models, source checkout, and runtime are local optional dependencies, not embedded in the Windows installer. Accessibility-based navigation works without the parser; visual fallback needs the service. Installer 4.0.0 includes the client and helper scripts under `_internal/gui-setup`. For an installed copy, use Python 3.12 to create the separate runtime under `_internal/.tools`, substitute `gui-setup` for `scripts` in the commands above, and launch FLOTER.exe normally. Git is required for the pinned upstream checkout.

## Keys and AI assistant handoff

Put the Jev gateway key and `GEMINI_API_KEY` / `GEMINI_MODEL` in `%USERPROFILE%\.floter\.env`. With only Gemini configured, navigation and advice use Gemini's OpenAI-compatible endpoint; set `GUI_MODEL_*` or `HERMES_*` to use a different OpenAI-compatible provider. The file is plain text in your Windows profile, outside the repository and installer; keep it private. Uninstall does not delete it.

For “Open Gemini/Claude and enter …”, Jev extracts the supplied prompt, then the navigation model locates the composer. Typed text must exactly equal the extracted prompt. It is staged by default; explicit ask/send/submit requests can propose a separately reviewed Submit click. This is UI automation, not an undocumented EXE command-line argument. Register an installed app's absolute EXE path in `%USERPROFILE%/.floter/applications.json` (see [configuration](CONFIGURATION.md)); otherwise the official website is offered with a disclosure. Login and ambiguous targets remain manual. Visual-only or inaccessible composers are unsupported. The current typing limit is 1,000 single-line characters.

## Model provenance

The adapter uses the official OmniParser YOLOv9-E `icon_detect_v3` and Florence-2 `icon_caption` weights, with EasyOCR, rather than importing the upstream demo's entire dependency stack. It uses a custom OCR/region merge. The provisioner pins Microsoft model revision `d10c4687d4af8245d67780ae59900f09660aad3a` and Florence-2-base processor/code revision `5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac`. Inspect the upstream per-component licenses before distributing models. The source checkout revision is pinned in the setup commands above.

Validate with automated tests, then a disposable app containing harmless buttons/search fields before trying personal applications. GPU inference checks prove parsing works, not that every application can be controlled reliably.
