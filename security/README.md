# Validation and approval boundaries

FLOTER 0.3.8 source guide, reviewed 27 September 2026.

This package validates executable targets, file creation and multi-step plans. It provides application guardrails, not process isolation or an OS sandbox.

A generated `proposal.md` must be new. A proposed workspace-opening plan must use implemented actions and receive approval. Saving that plan as a skill does not grant permanent execution permission; every run needs approval.

Normal direct actions such as opening Calculator do not receive a whole-plan approval dialog. GUI navigation has its own per-action review in [tools](../tools/codeexplainer.md).

See [codeexplainer.md](codeexplainer.md) for implementation details and the [main README](../README.md) for setup.
