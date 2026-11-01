# Test suite

Run from the repository root after installing `.[dev]` (plus voice dependencies for voice development):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

For a focused change:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_web_routing.py tests/test_user_settings.py
```

| Area | Test files |
| --- | --- |
| Routing/configuration | `test_web_routing.py`, `test_jev_model_routing.py`, `test_user_settings.py` |
| Core behavior and regressions | `test_floter_features.py`, `test_regressions.py`, `test_release_features.py` |
| Transport and Snippy | `test_http_transport.py`, `test_snippy.py` |
| Voice/UI | `test_streaming_voice.py`, `test_ui_history.py` |
| Desktop and registration | `test_selected_apps.py`, `test_omniparser_and_store_apps.py`, `test_gui_agent.py` |
| Camera lifecycle | `test_camera.py` |

The suite uses temporary paths, mocks and fake workers for many external effects. Passing it does not prove real microphone accuracy, installed-app accessibility, GPU inference, camera encoding or installer lifecycle. Those are covered by explicit scripts and target-machine acceptance; see [scripts](../scripts/README.md) and the [release checklist](../RELEASE_CHECKLIST.md).

See [codeexplainer.md](codeexplainer.md) for contributor guidance.
