"""Render the actual QML view, optionally exercising the Logs button."""
import sys
from pathlib import Path
from PySide6.QtCore import QObject, QMetaObject, Qt, QUrl, QTimer
from PySide6.QtGui import QGuiApplication, QColor, QFontDatabase, QFont
from PySide6.QtQuick import QQuickView
from floter.ui.bridge import FloterBridge

app = QGuiApplication([])
if sys.platform == 'win32':
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    app.setFont(QFont('Segoe UI', 10))
view = QQuickView()
view.setTitle('FLOTER')
view.setFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
view.setColor(QColor('#172f64'))
bridge = FloterBridge(view)
app.aboutToQuit.connect(bridge.shutdown)
view.rootContext().setContextProperty('floterBridge', bridge)
view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'ui/orb.qml')))
if view.status() == QQuickView.Error:
    raise SystemExit(1)
view.show()
logs = '--logs' in sys.argv
jev = '--jev' in sys.argv

def capture():
    image = view.grabWindow()
    assert not image.isNull()
    assert image.save('ui-jev-preview.png' if jev else ('ui-logs-preview.png' if logs else 'ui-preview.png'))
    if '--frame' in sys.argv:
        frame=view.frameGeometry()
        screenshot=view.screen().grabWindow(0,frame.x(),frame.y(),frame.width(),frame.height())
        assert screenshot.save('ui-frame-preview.png')
    app.quit()

def prepare():
    if logs or jev:
        button = view.rootObject().findChild(QObject, 'jevListButton' if jev else 'logsButton')
        assert button is not None
        assert QMetaObject.invokeMethod(button, 'clicked', Qt.DirectConnection)
        QTimer.singleShot(300, capture)
    else:
        capture()

QTimer.singleShot(1200, prepare)
app.exec()
view.setSource(QUrl())
