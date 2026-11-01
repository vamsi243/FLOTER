"""Verify normal close and close refusal using only newly created test windows."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--helper',type=Path)
    parser.add_argument('--keep-open',action='store_true')
    args=parser.parse_args()
    if args.helper:
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QGuiApplication,QWindow
        class Window(QWindow):
            def event(self,event):
                if args.keep_open and event.type()==QEvent.Close:
                    event.ignore(); return True
                return super().event(event)
        app=QGuiApplication([]); window=Window()
        window.setTitle('FLOTER owned close-test window'); window.resize(280,100); window.show()
        import psutil
        args.helper.write_text(json.dumps({'handle':int(window.winId()),'executable':psutil.Process().exe()}))
        return app.exec()
    from floter.config import config
    from floter.tools.desktop_actions import close_application
    reports=[]
    config.WHITELISTED_APPS['test-close-helper']=[sys.executable]
    config.APP_CATALOG['test-close-helper']={'executable':sys.executable}
    with tempfile.TemporaryDirectory() as directory:
        for keep_open in (False,True):
            receipt=Path(directory)/('kept.txt' if keep_open else 'closed.txt')
            command=[sys.executable,__file__,'--helper',str(receipt)]
            if keep_open: command.append('--keep-open')
            process=subprocess.Popen(command)
            try:
                deadline=time.monotonic()+15
                while not receipt.exists() and time.monotonic()<deadline: time.sleep(.1)
                details=json.loads(receipt.read_text())
                handle=details['handle']
                config.APP_CATALOG['test-close-helper']['executable']=details['executable']
                result=close_application('test-close-helper',preferred_handle=handle)
                assert result['closed'] is (not keep_open)
                if keep_open: assert process.poll() is None, 'Close refusal must not terminate the app'
                reports.append(result)
            finally:
                # Only the disposable child created above is cleaned up.
                if process.poll() is None: process.terminate()
                process.wait(5)
    target=Path(__file__).resolve().parents[1]/'acceptance-output/close-window-check.json'
    target.write_text(json.dumps(reports,indent=2))
    print(json.dumps(reports,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
