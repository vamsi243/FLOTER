"""Live camera intent checks only: never activate a camera."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from floter.tiers.jev_tier import JevReflexTier, JevActionEnum

CASES = [
    ('Can you take a picture?', 'photo'),
    ('Hey Rex, open the camera and take a photo', 'photo'),
    ('Take a selfie', 'photo'),
    ('Can you record a video?', 'record'),
    ('Open the camera and start recording a video', 'record'),
    ('Stop recording', 'stop'),
    ('Please stop the video and save it', 'stop'),
    ('Open the camera', 'open'),
    ('Close the camera', 'close'),
    ('Take a screenshot', 'screenshot'),
]


def check(item):
    query, expected = item
    tier = JevReflexTier()
    if expected == 'stop':
        tier.context = {'last_action':'camera:record', 'last_target':'camera'}
    try:
        result = tier.triage_and_route(query)
        matched = result.action == JevActionEnum.SNIPPY_CAPTURE if expected == 'screenshot' else result.action == JevActionEnum.CAMERA and result.target == expected
        return {'query':query, 'action':result.action.value,'target':result.target,
                'confidence':result.confidence,'probability':result.probability,
                'passed':matched and min(result.confidence,result.probability) >= .85}
    except Exception as exc:
        return {'query':query, 'passed':False, 'error':str(exc)}


if __name__ == '__main__':
    output = Path(__file__).resolve().parents[1] / 'acceptance-output/camera-routes.json'
    previous = json.loads(output.read_text()) if '--retry-failed' in sys.argv and output.exists() else []
    pending = {result['query'] for result in previous if not result['passed']}
    cases = [item for item in CASES if item[0] in pending] if previous else CASES
    with ThreadPoolExecutor(max_workers=2) as pool:
        checked = list(pool.map(check, cases))
    results = [result for result in previous if result['passed']] + checked
    output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))
    raise SystemExit(int(not all(result['passed'] for result in results)))
