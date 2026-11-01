# FLOTER code explainer

Reviewed against the cleaned source on 27 September 2026.

The distribution is `floter-desktop` (4.0.0), while imports and compatibility class names use `floter`. This directory is the package root, mapped by `pyproject.toml`; editable installation makes `python -m floter` available.

## Source map

| File / directory | Responsibility and useful symbols |
| --- | --- |
| `app.py`, `__main__.py`, `launcher.py` | Qt startup, multiprocessing bootstrap, source/frozen entry points and smoke-test modes |
| `config.py`, `.env.example` | `FloterConfig`, environment precedence, provider/audio/camera settings and built-in allowlists |
| `app_catalog.py` | `load_catalog`, selected private app entries and registered Windows launches |
| `ui/orb.qml` | Borderless buddy view: draggable header, resize grips, window controls, text/speech modes, composer, results, activity and approvals |
| `ui/RobotFace.qml` | Procedural face states and animations; replaces the retired shader orb |
| `ui/Camera.qml` | Camera preview, elapsed time and Stop / Close control |
| `ui/bridge.py` | `FloterBridge`: Qt properties/signals, voice queue, audio lifecycle, history, approvals, completion handling |
| `ui/backdrop.py` | Optional Windows Mica backdrop |
| `tiers/orchestrator.py` | `FloterOrchestrator`: single-flight routing, context, direct execution, plans and shutdown |
| `tiers/jev_tier.py` | `routing_choices`, `JevReflexTier`, remote response/score validation and literal argument extraction |
| `tiers/hermes_tier.py` | Hermes advice/JSON plan requests through a compatible endpoint; availability checks |
| `tiers/gemini_tier.py` | Gemini image/text analysis requests |
| `audio/listener.py` | `AudioListener`, isolated speech lifecycle, cancellation and optional Vosk path |
| `audio/whisper_stream.py` | CUDA setup, local model loading, bounded capture queue, decoding and `WakeSession` |
| `tools/desktop_actions.py` | LangChain schemas/tools, encoded browser search, `NotepadSession`, verified normal window close |
| `tools/camera.py` | `CameraManager`, isolated Qt capture process, recording stop/finalization and UI smoke test |
| `tools/mcp_tools.py` | Allowlisted launch/site operations, storage scanning and create-only document helpers |
| `tools/snippy_mcp.py` | MCP stdio/SSE transport, URL validation, calls and screenshot validation/persistence |
| `security/executables.py` | Trusted installation roots and executable resolution |
| `security/plans.py` | `PLAN_SCHEMA`, `ApprovalGate`, `SkillStore`: bounded actions, expiring single-use approval, validated JSON skills |
| `security/sandbox.py` | `SafeFileSystem` and path/create-only checks; application guardrails, not OS isolation |
| `workers.py` | Killable isolated workers, timeout/cancellation and JSON HTTP transport |
| `diagnostics.py` | Explicit provider, audio, Snippy and Notepad diagnostics |
| `tests/` | Routing, transport, security, voice, camera, selected apps, UI history and regression coverage |
| `floter.spec`, `packaging/floter.iss` | Frozen bundle resources and Windows installer |
| `.github/workflows/` | Windows test/build/package workflow; local presence does not establish a successful remote run |

`assets/branding/` contains the supplied PNG logo and multi-size Windows ICO. Setuptools and PyInstaller bundle these assets; the application sets its Qt icon and Windows AppUserModelID, while Inno Setup uses the icon for the installer and installed shortcut.

## A request through the code

1. QML calls `submitTextQuery`, or final speech reaches `submitVoiceQuery`. Provisional speech only updates display text.
2. The bridge hands accepted input to the orchestrator. Its lock prevents concurrent task execution.
3. `triage_and_route` sends capabilities and bounded context to Jev; actual finite scores are validated.
4. Most automatic actions require both route scores to reach 0.85; website/search routes use 0.60. GUI navigation also accepts a summed GUI-family probability of at least 0.85. Uncertain non-advice routes ask for clarification. Literal boundaries require an additional 0.70 check and are taken from the original words.
5. The selected executor checks arguments and resource identity. Plans instead pass through `validate_plan`, a UI approval ticket and revalidation before execution.
6. State/result signals update the UI and session history. Completion clears only matching successfully submitted input, preserving a newer draft.

## Maintenance scripts

| Group | Scripts |
| --- | --- |
| Provisioning | `provision_whisper.py`, optional `provision_voice.py` |
| App catalog | `inventory_apps.ps1`, `configure_apps.py`, `check_selected_apps.py`, `verify_selected_windows.py` |
| Live routing | `check_jev_connection.py`, `check_jev_live.py`, `check_floter_live.py`, `check_floter_sequence.py` |
| Desktop/voice integration | `check_notepad_live.py`, `check_close_window.py`, `check_voice_file.py`, `check_whisper_stream.py` |
| Camera | `check_camera_routes.py`, `check_camera_device.py`, `check_camera_encoder.py`, `check_frozen_camera.py` |
| UI inspection | `preview_check.py`, `preview_faces.py` |
| Distribution | `collect_notices.py`, `check_package.py`, `build_installer.py`, `acceptance_windows.ps1` |
| Snippy compatibility | `snippy_stdio.py` |

Integration scripts may call paid providers, open apps, write drafts, use hardware or install/uninstall software. Read the relevant script before running it. Existing reports in `acceptance-output/` are historical evidence, not automatically current test results. `run-local.ps1` launches the existing frozen bundle using the checkout's private dotenv; it does not run edited source.

## Extending the app

Implement a bounded executor with parameter/resource validation; add a semantic capability in `routing_choices`; dispatch it in the orchestrator; expose useful UI feedback; and add behavior-focused regression coverage. Do not add a phrase matcher that bypasses Jev. New plan actions require schema, execution and approval-display support. Keep [FEATURES.md](FEATURES.md), [ARCHITECTURE.md](ARCHITECTURE.md), configuration and the user manual aligned.

Compatibility names (`floter`, `orb.qml`, Vosk support) remain intentional. An old name alone does not make a file obsolete.
## GUI navigation implementation

`tools/gui_agent.py` preserves the goal, validates JSON actions, calls the reasoning endpoint and the loopback parser, and drives a bounded observation loop. `tools/gui_worker.py` isolates blocking UI Automation calls; `tools/gui_desktop.py` pins window/control identity and rechecks target pixels before input. `tools/gui_review.py` provides expiring single-use action review. Jev exposes named-app and already-open-app navigation routes. `scripts/omniparser_service.py` loads the Microsoft detector/caption models separately from the app, using CUDA; `scripts/provision_omniparser.py` downloads pinned model revisions. See [GUI_NAVIGATION.md](GUI_NAVIGATION.md) for configuration and limits.

## Detailed module guides

| Area | Overview | Implementation |
| --- | --- | --- |
| Local speech | [audio/README.md](audio/README.md) | [audio/codeexplainer.md](audio/codeexplainer.md) |
| Routing/providers | [tiers/README.md](tiers/README.md) | [tiers/codeexplainer.md](tiers/codeexplainer.md) |
| Desktop integrations | [tools/README.md](tools/README.md) | [tools/codeexplainer.md](tools/codeexplainer.md) |
| Validation/approval | [security/README.md](security/README.md) | [security/codeexplainer.md](security/codeexplainer.md) |
| Qt interface | [ui/README.md](ui/README.md) | [ui/codeexplainer.md](ui/codeexplainer.md) |
| Operational scripts | [scripts/README.md](scripts/README.md) | [scripts/codeexplainer.md](scripts/codeexplainer.md) |
| Tests | [tests/README.md](tests/README.md) | [tests/codeexplainer.md](tests/codeexplainer.md) |
| Distribution | [packaging/README.md](packaging/README.md) | [packaging/codeexplainer.md](packaging/codeexplainer.md) |

## Walkthrough: open a site in a named browser

For `Open Gmail in Brave`, QML calls `FloterBridge.submitTextQuery`. The orchestrator passes the request and session context to `JevReflexTier`. `routing_choices` describes Gmail separately from launching Brave. The validated web decision includes the site target and optional browser. `_open_web` dispatches through `FastMCPToolRegistry.open_website`; the URL comes from the configured site map. The browser executor resolves an installed executable and launches it with an argument list. Result/state callbacks update QML through queued signals.

For a search, `_extract_or_full` tries to retain the exact topic words; extraction failure falls back to the complete query. The executor URL-encodes it into a Google search. No page-reading stage follows.

## Walkthrough: create a reviewed document

For `Write a short proposal in proposal.md`, the plan route calls `HermesAgentOrchestrator` in plan mode. Its name remains Hermes even when configuration selects Gemini's compatible endpoint. The returned JSON must fit `PLAN_SCHEMA`. `_propose` creates an approval ticket and the bridge renders its actions. Consuming an approved ticket revalidates the immutable plan; `generate_notepad_document` creates a new file, or `write_notepad` creates and opens it. File creation refuses an existing destination. Only a completely executed plan becomes eligible for `save skill <name>`.

## Configuration and shared infrastructure

`config.py` loads process/user/source settings without overriding previously defined environment values. Frozen runs skip source dotenv fallback. `app_catalog.py` accepts only its explicit enabled identifiers and supported registration shapes; adding an arbitrary JSON key does not automatically add a capability.

`workers.py` uses spawned processes and pipes for cancellable blocking work, transports progress/results, and terminates workers after completion or timeout. `request_json` rejects redirects and bounds response size. Only classification endpoints receive bounded retries for selected transient HTTP errors. Cancellation stops waiting/ongoing work where possible; it cannot reverse completed external effects.

`app.py` calls multiprocessing freeze support before normal Qt startup and also dispatches explicit diagnostic/smoke modes. Startup exceptions are persisted to the user profile because the windowed EXE has no console. The source and EXE entry paths converge on this startup logic.

## Repository boundaries

`assets/branding` is runtime input. `models`, `.tools`, `.venv`, `build`, `dist` and `acceptance-output` are machine/build resources rather than core modules. `videos` holds local media projects and is not tracked. The Python package list in `pyproject.toml` defines what ships in a wheel; the explicit data list in `floter.spec` defines bundled root documentation. New module guides do not automatically ship in existing or rebuilt binaries.
