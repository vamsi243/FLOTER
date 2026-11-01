"""Render all procedural expressions from the actual QML component."""
from pathlib import Path
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PIL import Image, ImageDraw
from floter.ui.bridge import FloterBridge

root = Path(__file__).resolve().parents[1]
out = root / 'acceptance-output'
out.mkdir(exist_ok=True)
app = QGuiApplication([])
view = QQuickView()
view.setColor(QColor("#172f64"))
bridge = FloterBridge(view)
view.rootContext().setContextProperty('floterBridge', bridge)
view.setSource(QUrl.fromLocalFile(str(root / 'ui/RobotFace.qml')))
assert view.status() != QQuickView.Error
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.resize(180, 150)
view.show()
face = view.rootObject()
sheet = Image.new('RGB', (720, 600), '#172f64')
draw = ImageDraw.Draw(sheet)
for index, mood in enumerate(('idle', 'waiting', 'listening', 'thinking', 'working', 'success', 'alert', 'approval', 'sleeping', 'eye-roll', 'curious')):
    face.setProperty('mood', mood)
    QTest.qWait(500)
    assert face.property('state') == mood
    path = out / f'face-{mood}.png'
    assert view.grabWindow().save(str(path))
    with Image.open(path) as frame:
        tile = frame.resize((180, 150))
        x, y = (index % 4) * 180, (index // 4) * 200
        sheet.paste(tile, (x, y))
        draw.text((x + 58, y + 162), mood.capitalize(), fill='#f4f4f4')
sheet.save(out / 'face-expressions.png')
bridge.shutdown()
view.setSource(QUrl())
print(out / 'face-expressions.png')
