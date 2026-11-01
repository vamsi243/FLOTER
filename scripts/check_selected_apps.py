"""Live Jev phrasing checks; optionally launch each correctly routed app once."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from floter.app_catalog import ENABLED_APPLICATIONS
from floter.config import config
from floter.tiers.jev_tier import JevReflexTier, JevActionEnum
from floter.tools.mcp_tools import FastMCPToolRegistry
from floter.tools.desktop_actions import application_windows

ROOT = Path(__file__).resolve().parents[1]

def classify(item):
    name, label, template = item
    query = template.format(label)
    try:
        decision = JevReflexTier().triage_and_route(query)
        passed = (decision.action == JevActionEnum.LAUNCH_APP and decision.target == name
                  and decision.confidence >= .85 and decision.probability >= .85)
        return {'app':name,'query':query,'action':decision.action.value,'target':decision.target,
                'confidence':decision.confidence,'probability':decision.probability,
                'latency_ms':round(decision.latency_ms),'passed':passed}
    except Exception as exc:
        return {'app':name,'query':query,'passed':False,'error':str(exc)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--launch',action='store_true')
    parser.add_argument('--only',nargs='*')
    args = parser.parse_args()
    assert set(config.APP_CATALOG) == ENABLED_APPLICATIONS, 'Selected catalog is incomplete'
    selected = set(args.only) if args.only else ENABLED_APPLICATIONS
    assert selected <= ENABLED_APPLICATIONS
    cases = [(name, config.APP_CATALOG[name]['name'], template)
             for name in sorted(selected)
             for template in ('open {}','can you open {}','let\'s open {}')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        routes = list(pool.map(classify,cases))
    launched = []
    if args.launch:
        for name in sorted(selected):
            entry = config.APP_CATALOG[name]
            if not all(row['passed'] for row in routes if row['app']==name):
                launched.append({'app':name,'launched':False,'reason':'A phrasing check failed'})
                continue
            try:
                result = FastMCPToolRegistry.launch_application(name)
                executables = [entry.get('executable'),entry.get('close_executable')]
                handles=[]
                deadline=time.monotonic()+12
                while any(executables) and time.monotonic()<deadline:
                    handles=application_windows(executables)
                    if handles: break
                    time.sleep(.3)
                launched.append({'app':name,'launched':True,'result':result,
                                 'window_verified':bool(handles),
                                 'verification':'exact executable window' if handles else 'launch request accepted; window needs manual verification'})
            except Exception as exc:
                launched.append({'app':name,'launched':False,'error':str(exc)})
    report={'routes':routes,'launches':launched}
    destination = ROOT/'acceptance-output/selected-app-checks.json'
    if not args.launch and destination.exists():
        report['launches'] = json.loads(destination.read_text())['launches']
    if args.only and destination.exists():
        previous=json.loads(destination.read_text())
        report['routes'] = [r for r in previous['routes'] if r['app'] not in selected] + routes
        report['launches'] = [r for r in previous['launches'] if r['app'] not in selected] + launched
    destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return int(not all(row['passed'] for row in routes) or any(not row['launched'] for row in launched))

if __name__=='__main__': raise SystemExit(main())
