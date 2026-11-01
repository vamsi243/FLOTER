# Maintenance and diagnostic scripts

Run commands from the repository root with the development environment installed. These scripts are separate from normal application startup. Read a live-check script before using it: some contact providers, open/close applications, capture hardware input, or change installed software.

| Task | Entry points | Effects / prerequisites |
| --- | --- | --- |
| Provision speech | `provision_whisper.py`, legacy `provision_voice.py` | Downloads model weights |
| Discover selected apps | `inventory_apps.ps1`, `configure_apps.py` | Writes reports under `acceptance-output`; `--install` replaces the private catalog with a first-replacement backup |
| Verify selected apps | `check_selected_apps.py`, `verify_selected_windows.py` | Checks machine-specific registrations/windows |
| Check Jev | `check_jev_connection.py`, `check_jev_live.py` | Live provider calls; inspect each script's exact coverage |
| Exercise assistant | `check_floter_live.py`, `check_floter_sequence.py` | Can execute routed desktop tasks |
| Desktop checks | `check_notepad_live.py`, `check_close_window.py`, `check_gui_desktop.py` | Can manipulate app windows and drafts |
| Voice checks | `check_voice_file.py`, `check_whisper_stream.py` | Local model/audio prerequisites |
| Camera checks | `check_camera_routes.py`, `check_camera_device.py`, `check_camera_encoder.py`, `check_frozen_camera.py` | Different checks cover routing, hardware, encoding and packaged behavior |
| Gemini availability | `check_gemini.py` | Uses configured credentials and contacts the provider |
| OmniParser | `provision_omniparser.py`, `omniparser_service.py`, `start_omniparser.ps1` | Separate runtime; downloads, service startup and local inference |
| UI previews | `preview_check.py`, `preview_faces.py` | Visual inspection artifacts |
| Snippy adapter | `snippy_stdio.py` | Compatibility stdio service |
| Release | `collect_notices.py`, `check_package.py`, `build_installer.py` | Writes notices/build artifacts and validates bundle/wheel |
| Installer acceptance | `acceptance_windows.ps1` | Installs/reinstalls/uninstalls; use a disposable Windows VM |
| Secret scan | `check_secrets.py` | Scans Git-visible files; reports filenames without printing secret values |

Example app-catalog workflow:

```powershell
.\scripts\inventory_apps.ps1
.\.venv\Scripts\python.exe scripts/configure_apps.py
# Inspect acceptance-output/application-paths.md before installing the catalog.
.\.venv\Scripts\python.exe scripts/configure_apps.py --install
```

Historical files under `acceptance-output` do not establish current acceptance. See [codeexplainer.md](codeexplainer.md), [test guide](../tests/README.md) and [release checklist](../RELEASE_CHECKLIST.md).
