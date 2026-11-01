# Routing and model providers

FLOTER 0.3.8 source guide, reviewed 27 September 2026.

Every submitted request first goes to Jev. The orchestrator then invokes a bounded tool, asks for clarification, proposes a plan, or calls an optional reasoning/vision provider.

For example, `Open Gmail in Brave` becomes a website request with browser selection. `Write a short proposal in proposal.md` requests a reviewed document plan. `Explain what is on my screen` uses Snippy capture and Gemini.

Jev is required. Gemini or an OpenAI-compatible reasoning endpoint is optional; configuring Gemini alone can also back the Hermes-named reasoning class. These class names describe integration roles rather than requiring a particular model vendor. See [configuration](../CONFIGURATION.md).

See [codeexplainer.md](codeexplainer.md) for implementation details and the [main README](../README.md) for setup.
