# Cleanup record — 2026-09-27

## Scope

Fixed four release bugs, removed unused code, archived previous build outputs and completed the rename to FLOTER.

## Fixes

- Voice commands keep the dictated capitalisation and punctuation after the wake phrase; spoken skill names are normalised.
- Invalid numeric settings and an unreadable application catalog no longer stop startup. Values fall back to defaults and are reported in the activity log. Startup failures show a message and are saved to `%USERPROFILE%\.floter\logs\startup-error.log`.
- Settings can configure the Jev endpoint, model and TypeSafe key, and Gemini model IDs. Screen analysis uses `GEMINI_MODEL` when no vision model is set.
- A field cleared in Settings falls back to its default instead of storing an empty value; clearing the reasoning endpoint no longer breaks Hermes.

## Removed

- Unused Excel report and log-scan helpers (and the `openpyxl` dependency), the no-op sandbox decorator, unused shell-token checks, unrouted action names and the unused `WHISPER_MODEL_SIZE` setting.
- All old-name paths and aliases: the old config folder and env-file variable, the old command alias, the old Pictures folder default and the installer's old shortcut cleanup.

## Archived

Previous versions and leftovers moved out of the repository: older installers and wheels, old-name/compact/jev-voice/ui-update bundles, `.publish` (0.2.0), the 2026-09-25 cleanup archive, stale egg-info, old acceptance reports, old-brand video renders, UI previews and the stale parent-folder `main.py`, `requirements.txt` and `.env.example`.

User data on the development machine moved from the old-name folders to `%USERPROFILE%\.floter` and `Pictures\FLOTER`.
