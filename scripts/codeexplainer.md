# Script code explainer

Reviewed against FLOTER 0.3.8 on 27 September 2026.

The scripts are operational entry points rather than an imported application layer. Most derive the repository root from their own path. Their dependencies and side effects differ, so there is no single safe command that runs all of them.

`inventory_apps.ps1` discovers Windows registrations. `configure_apps.py` consumes `acceptance-output/application-discovery.json`, builds selected entries, and writes JSON and a Markdown report. Without `--install`, it only creates reports; with that flag, it writes `%USERPROFILE%/.floter/applications.json` and preserves an existing catalog once as `applications.before-selected-apps.json`.

`provision_whisper.py` and `provision_voice.py` explicitly prepare local speech weights. `provision_omniparser.py` prepares the separate parser models; `omniparser_service.py` exposes authenticated local inference. FLOTER's client and launcher live in `tools/`, so service changes must preserve that request/response contract. See [GUI_NAVIGATION.md](../GUI_NAVIGATION.md).

`check_package.py` is more than a file listing: it inspects selected frozen code objects, wheel resources, QML/branding and excluded private files, then launches smoke-test modes outside the checkout. It may also run packaged voice validation when a synthetic sample exists. It expects both a bundle and a wheel.

`build_installer.py` reads release metadata and invokes Inno Setup; signing is optional. `collect_notices.py` assembles redistribution notices. `acceptance_windows.ps1` exercises install/startup/reinstall/uninstall in a disposable environment.

When adding a diagnostic, make its effects explicit, bound network/hardware waits, keep credentials out of output, and distinguish mocked checks from live evidence. See the [script index](README.md).
