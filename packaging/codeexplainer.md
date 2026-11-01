# Packaging code explainer

Reviewed against FLOTER 0.3.8 on 27 September 2026.

`pyproject.toml` maps the repository root to package `floter`, explicitly enumerates its runtime subpackages and includes QML/branding package data. Its console script calls `floter.app:main`.

`floter.spec` uses `launcher.py`, obtains the version from project metadata, adds Windows version information/icon assets, explicitly lists root documentation and QML resources, and collects runtime dependencies. Whisper weights and NVIDIA libraries are added only when found. It excludes PyQt variants and filters incompatible host ICU DLLs. It builds a directory bundle, not a standalone one-file EXE.

`packaging/floter.iss` defines per-user versioned installation, Start Menu shortcuts, version registration, optional signing and downgrade prevention. `scripts/build_installer.py` supplies build parameters and invokes the compiler.

The current spec's documentation list is explicit: the new module README/codeexplainer files and docs index are source guides and are not automatically copied into a bundle. A Markdown edit also leaves existing `dist` files untouched. If shipping the whole source documentation tree becomes a requirement, update packaging and verification together.

`check_package.py` checks selected bundled modules/resources and smoke-test modes. It is not a byte-for-byte audit of all modules and is not clean-machine acceptance. Hardware capture, provider availability and installation lifecycle need the separate checks in the [release checklist](../RELEASE_CHECKLIST.md).

[Packaging overview](README.md)
