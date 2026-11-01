# Desktop tools and integrations: code explainer

Reviewed against FLOTER 0.3.8 on 27 September 2026.

## Executors

| File | What to trace |
| --- | --- |
| `desktop_actions.py` | `NotepadSession`, StructuredTool input schemas, browser URL encoding and verified `WM_CLOSE` |
| `mcp_tools.py` | `FastMCPToolRegistry`: launch/site operations, bounded storage inventory and create-only document output |
| `camera.py` | `CameraManager` and a separate Qt capture process with stop/finalization messages |
| `snippy_mcp.py` | stdio/SSE calls, server validation, image response validation and persistence |
| `gui_agent.py` | Reasoning requests, action schema checks, window selection and bounded observation loop |
| `gui_worker.py` | Persistent isolated Windows UI Automation worker and request/response transport |
| `gui_desktop.py` | `DesktopSession`: window binding, observations and target revalidation before input |
| `gui_review.py` | Expiring single-use review decisions, separate from whole-plan tickets |
| `omniparser_launcher.py` | On-demand local service startup and owned-process shutdown |

## Important flows

**Notepad:** open a uniquely named draft, bind its editor identity, append literal supplied text, then read back the edit. A changed tab/title or Save As can invalidate the binding. Edited content is not saved automatically.

**Documents:** `generate_notepad_document` creates a new `.txt`/`.md` on the Desktop, or home directory if Desktop is absent. `write_notepad` creates and opens the document. Existing files are refused by `SafeFileSystem`.

**Camera:** a command can return after recording starts; worker lifecycle messages report finalization. The camera window's Stop control can finish a recording without a routing request. Photos/videos default to Pictures/FLOTER.

**GUI:** review data disclosure, choose and review an observed window, bind it, observe elements, request one JSON action, validate and review input, execute against fresh target checks, then observe again. The loop has a 16-step limit and a five-minute deadline checked between steps. Completion requires observed evidence plus user confirmation. Review tickets expire after 120 seconds. OmniParser runs locally when visual inspection is requested; extracted labels can go to the reasoning endpoint.

Assistant prompt handoff rejects altered prompt text before typing. Accessible Edit/Document fields are required; typing is limited to 1,000 single-line characters. Submission intent is described in planner instructions and the proposed click is separately reviewed. This is not a general messaging API.

## Testing and changes

Use fake desktops/reasoners to test stale targets, invalid IDs, altered prompts, refusal and cancellation before live app tests. Do not equate a successful input call with achievement of a goal. The `FastMCPToolRegistry` name is historical: these static methods are called inside FLOTER; Snippy is the separate MCP integration.

[Module overview](README.md) · [Repository code explainer](../codeexplainer.md)
