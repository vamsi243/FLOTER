"""Verify actual Jev classification and exact literal spans without executing tools."""
import json
from pathlib import Path
from floter.tiers.jev_tier import JevReflexTier

def main():
    tier = JevReflexTier()
    results = []
    cases = [
        ('hey rex, can you try opening a note pad', 'launch_application', None),
        ('try write how are you doing on the notepad', 'type_notepad', 'literal words to append to Notepad'),
        ('look up the latest Python release on the internet', 'web_search', None),
        ('search for hiking trails near Sydney', 'web_search', None),
        ('write an essay about climate change in notepad', 'plan', None),
    ]
    for prompt, expected, purpose in cases:
        tier.context = {'last_action':'open','last_target':'notepad'}
        try:
            decision = tier.triage_and_route(prompt)
            item = {'prompt':prompt,'action':decision.action.value,'expected':expected,
                    'confidence':decision.confidence,'probability':decision.probability,'latency_ms':decision.latency_ms}
            if purpose:
                item['argument'] = tier.extract_argument(prompt,purpose)
            item['passed'] = decision.action.value == expected
        except Exception as exc:
            item = {'prompt':prompt,'passed':False,'error_type':type(exc).__name__, 'error':str(exc) if isinstance(exc, ValueError) else 'Provider failure'}
        results.append(item)
    path = Path(__file__).resolve().parents[1]/'acceptance-output'/'floter-jev-live.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))
    return int(not all(r['passed'] for r in results))

if __name__ == '__main__':
    raise SystemExit(main())
