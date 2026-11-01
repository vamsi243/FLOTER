"""Turn Windows registration inventory into an explicit local launch catalog."""
import argparse
import json
import os
from pathlib import Path
import re
from floter.app_catalog import ENABLED_APPLICATIONS

ROOT = Path(__file__).resolve().parents[1]

def identifier(name):
    aliases = {'google chrome':'chrome', 'brave':'brave', 'visual studio code':'vscode',
               'code.exe':'vscode', 'notepad.exe':'notepad', 'notepad':'notepad',
               'calculator':'calculator', 'notepad++':'notepad-plus-plus', 'notepad++.exe':'notepad-plus-plus'}
    return aliases.get(name.lower(), re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:65])

def build_catalog(records):
    applications, outcomes, paths = {}, [], {}
    # Prefer friendly Start Menu names, then exact App Paths, then registered launch IDs.
    ordered = sorted(records, key=lambda r: {'Start Menu':0,'App Paths':1,'Registered Start application':2}.get(r['source'],3))
    for row in ordered:
        name = row['name']; alias = identifier(name)
        if alias not in ENABLED_APPLICATIONS:
            continue
        target = os.path.expandvars(row.get('path') or '').strip('"')
        status = 'Inventory only: no verified launch target'
        entry = None
        if re.search(r'\b(uninstall|install additional|release notes)\b', name, re.I):
            status = 'Inventory only: installer/uninstaller/document'
        elif row.get('arguments'):
            status = 'Inventory only: shortcut requires arguments; not reduced to a different command'
        elif target and Path(target).is_absolute() and Path(target).suffix.lower() == '.exe' and Path(target).is_file():
            entry = {'name':name, 'kind':'exe', 'target':str(Path(target).resolve()), 'executable':str(Path(target).resolve())}
            # Some installed apps use a stable launcher and a versioned runtime.
            runtimes = list(Path(target).parent.glob('app-*/' + Path(target).name))
            if runtimes:
                entry['close_executable'] = str(max(runtimes,key=lambda p:p.stat().st_mtime).resolve())
        elif row['source'] == 'Registered Start application' and (row.get('app_id') or '').startswith(('http:', 'https:')):
            status = 'Inventory only: website/documentation shortcut, not an application'
        elif row['source'] == 'Registered Start application' and row.get('app_id'):
            entry = {'name':name, 'kind':'registered', 'target':row['app_id'], 'executable':row.get('executable') or ''}
        if entry and alias:
            key = entry['target'].lower()
            if key in paths:
                status = 'Configured as ' + paths[key]
            elif alias in applications:
                # A package record can supply the actual executable behind a launcher.
                if entry.get('executable'):
                    applications[alias].setdefault('close_executable', entry['executable'])
                status = 'Configured as ' + alias
            else:
                applications[alias] = entry
                paths[key] = alias
                status = 'Configured as ' + alias
        outcomes.append({**row, 'status':status})
    return applications, outcomes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    records = json.loads((ROOT/'acceptance-output/application-discovery.json').read_text(encoding='utf-8-sig'))
    applications, outcomes = build_catalog(records)
    output = {'version':1, 'applications':applications}
    (ROOT/'acceptance-output/applications.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    lines = ['# Application paths on this computer', '',
             f'{len(applications)} selected application launch entries. Only the requested apps are configured. Duplicate registrations for those apps remain listed below.', '',
             'Sources: Start Menu shortcuts, App Paths, registered Start applications and installed-software registry. Portable applications without registrations are not discoverable through these sources. Store apps use a registered launch ID; executable paths can change after updates.', '',
             '| Application | Source | Executable / registered ID / installation folder | Configuration |',
             '| --- | --- | --- | --- |']
    for row in sorted(outcomes,key=lambda r:(r['name'].lower(),r['source'])):
        location = row.get('path') or row.get('executable') or row.get('install_location') or row.get('app_id') or '(not registered)'
        if row.get('app_id'): location += ' · ID: ' + row['app_id']
        entry = applications.get(identifier(row['name']), {})
        if entry.get('close_executable'):
            location += ' · Runtime: ' + entry['close_executable']
        values = [row['name'],row['source'],location,row['status']]
        lines.append('| ' + ' | '.join(str(v).replace('|','\\|').replace('\n',' ') for v in values) + ' |')
    (ROOT/'acceptance-output/application-paths.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if args.install:
        destination = Path.home()/'.floter/applications.json'
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():
            backup = destination.with_name('applications.before-selected-apps.json')
            if not backup.exists():
                with backup.open('xb') as stream:
                    stream.write(destination.read_bytes())
        destination.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(f'{len(applications)} selected launch entries configured; paths listed in application-paths.md')

if __name__ == '__main__': main()
