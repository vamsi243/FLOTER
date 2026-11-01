# Desktop tools and integrations

FLOTER 0.3.8 source guide, reviewed 27 September 2026.

This directory implements the actions that routing selects. It includes verified Notepad typing, application/site launch and close, bounded storage scans, camera capture, Snippy MCP, and experimental reviewed GUI navigation.

| Use case | Example | Dependency |
| --- | --- | --- |
| Draft a note | `Open Notepad`, then `Type Call the plumber in Notepad` | Installed trusted Notepad |
| Search online | `Search for train timetables in Edge` | Browser |
| Capture a photo | `Take a picture` | Camera and Windows permission |
| Read screen text | `Extract text from my screen` | Configured Snippy |
| Navigate controls | `Open Calculator and switch to Scientific mode` | Reasoning provider, accessible visible window, user review |

All commands still need Jev. GUI navigation is experimental and may ask for manual help. See [GUI_NAVIGATION.md](../GUI_NAVIGATION.md) for local OmniParser setup and limits.

See [codeexplainer.md](codeexplainer.md) for implementation details and the [main README](../README.md) for setup.
