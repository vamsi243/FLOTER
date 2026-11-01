# Test code explainer

Reviewed against FLOTER 0.3.8 on 27 September 2026.

Pytest discovers `tests/` through `pyproject.toml`. Tests patch configuration and integrations to exercise routes without relying on a live classifier. Fake desktop observations and reasoners exercise GUI action validation; fake camera workers cover process lifecycle and failure handling. Temporary directories isolate created documents and saved plans.

When changing a route, verify the observable action and its arguments, refusal when uncertainty is too high, and behavior when providers fail. When changing an executor, test identity validation and partial-failure handling, not only its successful return value. When changing configuration, test missing, blank and invalid values separately because defaults are field-specific.

Useful failure cases include stale Notepad identity, replayed/expired approvals, malformed provider JSON, unobserved GUI element IDs, changed prompt text, cancellation, worker exits and preservation of newly typed UI drafts.

Keep hardware/live-provider checks in explicit diagnostics rather than quietly introducing external effects into ordinary unit tests. Existing test coverage is evidence for those assertions, not a guarantee that all user examples work on every machine. See the [test index](README.md).
