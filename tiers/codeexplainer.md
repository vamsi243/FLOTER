# Routing and model providers: code explainer

Reviewed against FLOTER 0.3.8 on 27 September 2026.

## Source map

| File | Main responsibility |
| --- | --- |
| `jev_tier.py` | `routing_choices`, `JevActionEnum`, `JevDecision`, response validation and literal argument extraction |
| `orchestrator.py` | `FloterOrchestrator`, single-task admission, dispatch, cancellation, session context and approvals |
| `hermes_tier.py` | OpenAI-compatible advice and JSON-plan generation |
| `gemini_tier.py` | Explicit image/text analysis through Gemini |

## Dispatch walkthrough

`process_query_async` acquires a nonblocking lock and starts a background thread. `_route_query` supplies context to Jev, validates the decision and selects an executor. A busy task is not silently run concurrently. Completion reaches the bridge through callbacks.

Most automatic actions require confidence and chosen-option probability of at least 0.85. Website/search routes use 0.60. GUI navigation additionally accepts summed probability of at least 0.85 across GUI destinations, even when the individual route scores do not meet the usual threshold. Uncertain non-advice routes return `needs_input` through `_clarify`; they do not execute a guessed action. Invalid or unavailable classification fails without local intent fallback.

Literal extraction is a separate Jev evaluation of boundaries in the original request, with a 0.70 threshold. Search/site extraction can fall back to the full request. Notepad and assistant prompt extraction must succeed.

Plans pass through `ApprovalGate`; `_execute_plan` runs validated actions in order and saves `last_approved_plan` only after all actions complete. Failure stops remaining actions but does not roll back prior effects. `run skill <name>` proposes a fresh approval, never immediate replay.

## Extension points

Add an implemented capability to `routing_choices`, dispatch it in the orchestrator, and validate at the executor boundary. Plan actions also need schema and approval-display updates. Keep provider HTTP calls cancellable through `workers.py`. Relevant tests include web routing, Jev model routing, HTTP transport and GUI-agent tests.

[Module overview](README.md) · [Repository code explainer](../codeexplainer.md)
