"""Opt-in live routing check. Never executes returned actions or prints keys."""
import json
from dataclasses import asdict
from pathlib import Path
from floter.tiers.jev_tier import JevReflexTier

def main():
    tier = JevReflexTier()
    results = []
    for prompt in ('Can you please open the notepad?', 'Bring up my code editor',
                   'Take a screenshot please', 'Show storage information from all drives',
                   'Close Notepad', 'Explain what is on my screen'):
        try:
            decision = tier.triage_and_route(prompt)
            results.append({'prompt': prompt, **asdict(decision)})
        except Exception as exc:
            # Types only: provider messages can contain sensitive material.
            cause = exc.__cause__
            results.append({'prompt': prompt, 'error': type(exc).__name__,
                            'cause': type(cause).__name__ if cause else None,
                            'http_status': getattr(cause, 'code', None)})
            break
    report = Path(__file__).resolve().parents[1] / 'acceptance-output' / 'jev-live-routing.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))
    return int(any('error' in result for result in results))

if __name__ == '__main__':
    raise SystemExit(main())
