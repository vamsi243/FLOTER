# Windows packaging

FLOTER has three distinct deliverables: a Python wheel, a PyInstaller folder bundle and an Inno Setup installer. Source version comes from `pyproject.toml` (currently 4.0.0).

Use the build commands in the [main README](../README.md). The build baseline is Windows with Python 3.12, development/voice dependencies, provisioned speech weights and Inno Setup 6. The spec imports sounddevice, so a typed-only development installation is insufficient for that build recipe.

| Output | Purpose |
| --- | --- |
| `dist/*.whl` | Python installation; provision voice weights separately |
| `dist/FLOTER/FLOTER.exe` plus `_internal` | Folder-distributed application; keep the whole directory |
| `dist/installer/FLOTER-4.0.0-Setup.exe` | Per-user Windows installer |

The installer targets x64-compatible Windows 10 build 19041 or later and requests no administrator privileges. Its default installation root is `%LOCALAPPDATA%\Programs\FLOTER`, with files under `versions/<version>`.

Keys and app registrations belong in the user's profile and are not installer assets. Heavy OmniParser runtime/models are separately provisioned; the bundle includes client code and setup helpers. Signing requires explicit configuration; do not present an unsigned local installer as signed.

Read [codeexplainer.md](codeexplainer.md) and [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md). Rebuilding the application is a separate operation from editing documentation.
