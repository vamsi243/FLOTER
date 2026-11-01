# Release checklist

Source version: 4.0.0. Documentation review: 2026-09-25. This is a completion checklist, not a claim that all release acceptance has passed.

- Run the regression suite in the intended Python environment.
- Run source UI, worker and camera UI smoke tests; exercise resize, input preservation, history and approval flows.
- Confirm Jev routing with intended credentials, including failures and low-confidence requests. Test optional providers only when distributing those capabilities.
- Test real microphone/wake/follow-up behavior and local CPU/CUDA transcription on target hardware.
- Test Notepad identity/readback, app launches and graceful close/save prompts against test-owned windows.
- Test physical camera permissions, photos, audio/video encoding, automatic duration and stop/finalization.
- Regenerate third-party notices from the release environment; review model/runtime redistribution terms.
- Build a fresh wheel and PyInstaller bundle using the current source; run `scripts/check_package.py`. Existing `dist/` artifacts predate this cleanup.
- Build the installer and verify install, upgrade, launch, uninstall and retained user data on a disposable Windows machine using the acceptance script as appropriate.
- Decide whether to sign the release. Unsigned artifacts must be described accurately.
- Verify no private dotenv, application inventories, signing material or local acceptance reports are distributed.
- Recreate checksums for the final artifacts and confirm version consistency with `pyproject.toml`.
- Publish only artifacts that passed the release checks. Repository hosting/publication status must be verified separately; this workspace currently has no Git metadata.

Build commands are in [README.md](README.md). Cleanup verification is recorded in [CLEANUP.md](CLEANUP.md). Historical reports were moved to the ignored local archive and are not release documentation.
