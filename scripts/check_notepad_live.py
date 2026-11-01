"""Exercise only a new FLOTER-owned draft; leave it visible for inspection."""
import json
from pathlib import Path
from floter.tools.desktop_actions import NotepadSession, editor_text

if __name__ == '__main__':
    session = NotepadSession()
    opened = session.open()
    written = session.append('how are you doing')
    actual = editor_text(session.editor_handle)
    report = {'opened':opened, 'written':written, 'text':actual, 'matches':actual == 'how are you doing'}
    (Path(__file__).resolve().parents[1]/'acceptance-output'/'floter-notepad.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['matches'] else 1)
