# Validation and approval boundaries: code explainer

Reviewed against FLOTER 0.3.8 on 27 September 2026.

## Files

- `executables.py`: approved installation roots and explicit executable resolution.
- `sandbox.py`: `GuardrailViolationError`, bounded reads and exclusive create-only writes.
- `plans.py`: strict JSON schema, `validate_plan`, `ApprovalGate` and `SkillStore`.

## Plan contract

A plan has `version: 1`, a nonempty summary and 1–8 actions. Unknown fields and unsupported tools are rejected. Supported tools are `launch_application`, `snippy_capture`, `generate_notepad_document`, `write_notepad` and `inspect_storage`. Launch targets must be in configured app/site allowlists.

`propose` validates and serializes a snapshot. `consume` matches its random token, removes the pending ticket, checks its 300-second lifetime, then revalidates the snapshot. Mutating a caller's original dictionary does not mutate the approved plan. Approval authorizes that plan only.

Skills live in `%USERPROFILE%/.floter/skills` by default. Names match `[a-z][a-z0-9_-]{0,39}`. Saves use exclusive file creation; loading validates size, rejects symlinks and validates the schema again. Listing returns at most 100 names.

## Boundaries to preserve

File helpers resolve paths and refuse existing destinations using exclusive open modes. They are not a filesystem jail restricting all writes to one root; callers must constrain their output directories and names. These helpers do not govern every write in the app: camera media, logs and UI editor operations have their own implementations.

Add schema coverage for each new plan action, including invalid parameters and replay/expiry cases. Relevant tests are `test_floter_features.py`, `test_regressions.py` and `test_release_features.py`.

[Module overview](README.md) · [Repository code explainer](../codeexplainer.md)
