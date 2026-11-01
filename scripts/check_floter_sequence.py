"""End-to-end live Jev + tool check using a new draft; browser opening is mocked."""
import json
from pathlib import Path
from unittest.mock import patch
from floter.tiers.orchestrator import FloterOrchestrator
from floter.tools.desktop_actions import editor_text

def main():
    logs = []
    app = FloterOrchestrator(on_log_message=logs.append)
    reports = []
    root = Path(__file__).resolve().parents[1]
    speech = json.loads((root/'acceptance-output'/'floter-whisper-stream.json').read_text())['finals']
    for command in speech:
        result = app.process_query(command)
        reports.append({'command':command, 'result':result})
        if result['status'] != 'success':
            break
    if all(r['result']['status']=='success' for r in reports) and len(reports)==2:
        reports.append({'notepad_text':editor_text(app.notepad.editor_handle)})
        with patch('webbrowser.open', return_value=True) as browser:
            reports.append({'search_result':app.process_query('search for hiking trails near Sydney with train access'),
                            'browser_url':browser.call_args.args[0] if browser.called else None})
    output = {'reports':reports,'logs':logs,'browser_was_mocked':True}
    (root/'acceptance-output'/'floter-sequence.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))
    app.shutdown()
    return int(len(reports)!=4 or reports[2]['notepad_text'].strip().lower() != 'how are you doing')

if __name__ == '__main__':
    raise SystemExit(main())
