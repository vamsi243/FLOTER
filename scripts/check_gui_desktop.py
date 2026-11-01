"""Exercise real UIA input only against an isolated FLOTER test window."""
import sys
import time
import subprocess

if '--fixture' in sys.argv:
    from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel
    from PySide6.QtCore import QTimer
    app=QApplication([])
    window=QWidget(); window.setWindowTitle('FLOTER GUI navigation fixture')
    layout=QVBoxLayout(window)
    field=QLineEdit(); field.setAccessibleName('Search')
    button=QPushButton('Open profile'); label=QLabel('Waiting')
    button.clicked.connect(lambda: label.setText('Profile: '+field.text()))
    for item in (field,button,label): layout.addWidget(item)
    window.resize(420,220); window.show()
    QTimer.singleShot(60000,app.quit)
    sys.exit(app.exec())

if __name__=='__main__':
    import threading
    from floter.tools.gui_worker import DesktopWorker
    process=subprocess.Popen([sys.executable,__file__,'--fixture'])
    session=None
    try:
        session=DesktopWorker(threading.Event())
        for _ in range(40):
            targets=[w for w in session.windows() if w['title']=='FLOTER GUI navigation fixture']
            if targets: break
            time.sleep(.25)
        assert len(targets)==1
        session.bind(targets[0]['handle'])
        observation=session.observe()
        field=next(e for e in observation['elements'] if e['role']=='Edit')
        session.execute(observation,{'action':'type','element':field['id'],'text':'Mom'})
        observation=session.observe()
        button=next(e for e in observation['elements'] if e['label']=='Open profile')
        session.execute(observation,{'action':'click','element':button['id']})
        time.sleep(.2)
        result=session.observe()
        assert any(e['label']=='Profile: Mom' for e in result['elements'])
        print('Real UIA typing, button invocation, and result re-observation passed.')
    finally:
        if session: session.close()
        process.terminate(); process.wait(timeout=5)
