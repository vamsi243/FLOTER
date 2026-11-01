# Qt Quick interface: code explainer

Reviewed against FLOTER 0.3.8 on 27 September 2026.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| `orb.qml` | Main layout, composer, window controls, mode switching, results, Activity and approval dialogs |
| `RobotFace.qml` | Procedural expressions and idle animations |
| `Camera.qml` | Camera preview and Stop/Close controls |
| `bridge.py` | `FloterBridge`: QML properties/slots, queued signals, voice queue and task callbacks |
| `backdrop.py` | Compatibility Windows backdrop helper; current main view uses a solid background |

`app.py` creates the Qt view and exposes the bridge to QML. Background callbacks emit queued Qt signals instead of updating widgets directly. `submitTextQuery` and `submitVoiceQuery` share the orchestrator but handle busy input differently: typed requests can be refused while finalized voice commands are queued.

`receiveApproval` formats plan and GUI review requests; `decideApproval` routes the user's decision to the corresponding gate. GUI navigation temporarily adjusts FLOTER's visibility so it does not obstruct the target application.

`complete_command` only emits clearing behavior for successful commands; QML compares submitted text with the current composer contents so newer typing survives. The history deque holds up to 500 entries and is not a durable conversation database.

State names are Idle, Listening, Thinking, Reasoning, Executing, Success and Blocked. Microphone state is tracked separately. Shutdown stops listening and coordinates orchestrator shutdown.

For changes, preserve Qt thread affinity, approval visibility, input accessibility and draft retention. Relevant tests include `test_ui_history.py`, `test_regressions.py` and `test_release_features.py`; actual window layout still needs visual review.

[Module overview](README.md) · [Repository code explainer](../codeexplainer.md)
