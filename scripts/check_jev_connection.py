"""Diagnose connectivity without displaying credentials or response bodies."""
from floter.tiers.jev_tier import JevReflexTier
import sys
import threading

def main():
    tier = JevReflexTier()
    tier.cancel = threading.Event()
    tier.context = {'last_target':'notepad'}
    print('Jev key configured:', bool(tier.api_key))
    try:
        decision = tier.triage_and_route(sys.argv[1] if len(sys.argv)>1 else 'open notepad')
        print('Route:', decision.action.value, 'confidence:', decision.confidence)
    except Exception as exc:
        while exc is not None:
            print(type(exc).__name__, str(exc)[:300])
            exc = exc.__cause__
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
