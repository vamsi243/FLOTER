# Qt Quick interface

FLOTER 0.3.8 source guide, reviewed 27 September 2026.

The current interface is a borderless navy window with Rex's animated face, text input, speech mode, activity history and approval dialogs. `orb.qml` remains the main filename even though the old orb design has been replaced.

Use Text for keyboard entry, Speech + Text for wake listening, Enter to submit and Shift+Enter for a newline. Activity shows session requests/results. The camera has a separate preview window. Configuration is edited in the user dotenv file; there is no Settings editor in this QML view.

The UI describes progress, but success messages depend on executor reports. A camera recording can still be running after its start command succeeds.

See [codeexplainer.md](codeexplainer.md) for implementation details and the [main README](../README.md) for setup.
