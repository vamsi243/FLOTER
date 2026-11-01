"""OpenAI-compatible Hermes reasoning. Model text never executes tools."""
import json
import urllib.request
from urllib.parse import urlparse
from floter.config import config, model_chain
from floter.workers import request_json, CancelledError

REQUEST_NOT_CONFIGURED = "I'm not configured to process this request yet. Try an available action, such as opening an app, searching the web, or taking a photo."

class HermesAgentOrchestrator:
    def __init__(self):
        self.cancel = None

    def ensure_configured(self):
        parsed = urlparse(config.HERMES_API_BASE.rstrip('/'))
        local = parsed.hostname in {'localhost', '127.0.0.1', '::1'}
        if parsed.scheme != 'https' and not (local and parsed.scheme == 'http'):
            raise ValueError('Hermes requires HTTPS except for loopback endpoints')
        if not config.HERMES_MODEL or (not local and not (config.HERMES_API_KEY or config.OPENROUTER_API_KEY)):
            raise RuntimeError(REQUEST_NOT_CONFIGURED)

    def execute_complex_plan(self, goal, state_callback=None, plan_mode=False):
        self.ensure_configured()
        base = config.HERMES_API_BASE.rstrip("/")
        parsed = urlparse(base)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
            raise ValueError("Hermes requires HTTPS except for loopback endpoints")
        key = config.HERMES_API_KEY or config.OPENROUTER_API_KEY
        if not key and not local:
            raise RuntimeError(REQUEST_NOT_CONFIGURED)
        if not config.HERMES_MODEL:
            raise RuntimeError(REQUEST_NOT_CONFIGURED)
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {"messages": [
            {"role": "system", "content": "You are FLOTER. Provide helpful answers or a proposed plan. You have no tool execution or screen access. Never claim actions were performed."},
            {"role": "user", "content": goal}], "max_tokens": 2048}
        if plan_mode:
            from floter.security.plans import PLAN_SCHEMA
            payload['messages'][0]['content'] = ('Return only JSON matching this schema. Propose at most 8 actions; never execute them. '
                                                'Use exact allowlisted targets. Schema: ' + json.dumps(PLAN_SCHEMA)
                                                + ' Apps: ' + ', '.join(config.WHITELISTED_APPS)
                                                + ' Websites: ' + ', '.join(config.WHITELISTED_URL_MAP))
        failure = None
        # With Gemini as the provider, a busy or failing model hands over to the next fallback.
        for model in model_chain(config.HERMES_MODEL, config.REASONING_FALLBACK_MODELS):
            request = urllib.request.Request(base + "/chat/completions", data=json.dumps({"model": model, **payload}).encode(), headers=headers)
            try:
                data = request_json(request, 30, self.cancel)
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Empty response")
                if plan_mode:
                    from floter.security.plans import validate_plan
                    from floter.tools.gui_agent import parse_json_reply
                    return {"plan": validate_plan(parse_json_reply(content))}
                return {"analysis": content, "mode": "advisory"}
            except CancelledError:
                raise
            except Exception as exc:
                failure = exc
        raise RuntimeError("Hermes request failed; check endpoint, model, credentials and connection") from failure
