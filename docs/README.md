# Documentation index

Reviewed against FLOTER 0.3.8 source on 27 September 2026.

- [Main README](../README.md): run the EXE, source setup and builds.
- [Feature catalog](../FEATURES.md): use cases, examples and prerequisites.
- [User manual](../INSTRUCTION_MANUAL.md): everyday operation and troubleshooting.
- [Configuration](../CONFIGURATION.md): dotenv precedence, providers, devices and app registrations.
- [GUI navigation](../GUI_NAVIGATION.md): experimental reviewed desktop navigation and local parser setup.
- [Architecture](../ARCHITECTURE.md): component flow and trust boundaries.
- [Root code explainer](../codeexplainer.md): source map and contributor walkthrough.
- [Release checklist](../RELEASE_CHECKLIST.md): packaging and target-machine acceptance.
- [Cleanup record](../CLEANUP.md): historical cleanup, not the current configuration contract.

Each runtime directory has a README and a codeexplainer.md: [audio](../audio/README.md), [tiers](../tiers/README.md), [tools](../tools/README.md), [security](../security/README.md), [ui](../ui/README.md). Supporting guides cover [tests](../tests/README.md), [scripts](../scripts/README.md) and [packaging](../packaging/README.md).

Historical acceptance reports are not authoritative evidence for the current release. Third-party README files describe their own dependencies and are not FLOTER guides.

When behavior changes, update the feature catalog and the affected module guide, then reconcile configuration, architecture and the manual. Existing binaries and exported collateral require separate rebuilds.
