"""Check the Gemini key: list usable models, then test navigation and screen-analysis calls.

Run after adding GEMINI_API_KEY (and GEMINI_MODEL) to %USERPROFILE%\\.floter\\.env:
    python scripts/check_gemini.py
Never prints the key. Sends two tiny test prompts; no screenshot is uploaded.
"""
import json
import threading
import urllib.error
import urllib.request
from floter.config import config, ENV_FILE

def main():
    if not config.GEMINI_API_KEY:
        print(f'GEMINI_API_KEY is empty in {ENV_FILE}. Add it and run again.')
        return 1
    request = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=200',
                                     headers={'x-goog-api-key': config.GEMINI_API_KEY})
    with urllib.request.urlopen(request, timeout=20) as response:
        models = json.loads(response.read())['models']
    usable = sorted(m['name'].removeprefix('models/') for m in models
                    if 'generateContent' in m.get('supportedGenerationMethods', []))
    print('Models your key can use (put one in GEMINI_MODEL):')
    for name in usable:
        print('  ', name)
    if not config.GEMINI_MODEL:
        print(f'\nGEMINI_MODEL is empty in {ENV_FILE}. Pick one above and run again.')
        return 1
    if config.GEMINI_MODEL not in usable:
        print(f'\nGEMINI_MODEL={config.GEMINI_MODEL} is not in that list.')
        return 1
    # The list can include models retired for new accounts; ask Gemini directly and show its reason.
    for model in dict.fromkeys(filter(None, (config.GEMINI_MODEL, config.GEMINI_VISION_MODEL))):
        probe = urllib.request.Request(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            data=json.dumps({'contents': [{'parts': [{'text': 'Reply with the word ok'}]}]}).encode(),
            headers={'Content-Type': 'application/json', 'x-goog-api-key': config.GEMINI_API_KEY})
        try:
            urllib.request.urlopen(probe, timeout=40).close()
        except urllib.error.HTTPError as exc:
            reason = json.loads(exc.read() or b'{}')
            reason = (reason[0] if isinstance(reason, list) else reason).get('error', {}).get('message', exc.reason)
            print(f'\n{model} cannot be used: {reason}')
            return 1
    print(f'\nReasoning provider in use: {config.REASONING_PROVIDER} ({config.HERMES_MODEL})')
    from floter.tools.gui_agent import Reasoner
    reply = Reasoner(threading.Event()).call(
        'Return ONLY a JSON object {"action":"done","reason":"..."}.', {'goal': 'connection test'})
    print('Navigation call (OpenAI-compatible endpoint): OK ->', reply.get('action'))
    from floter.tiers.gemini_tier import GeminiMultimodalTier
    tier = GeminiMultimodalTier(); tier.cancel = threading.Event()
    result = tier.analyze_visual_and_logs('Return a JSON object with analysis set to "connection test successful".')
    print('Screen-analysis call (native endpoint): OK ->', str(result)[:120])
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
