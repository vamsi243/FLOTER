"""Encode synthetic frames through Qt and decode the finalized MP4; no camera/mic access."""
from pathlib import Path
from uuid import uuid4
import json
import av
from PySide6.QtCore import QTimer, QUrl, QSize
from PySide6.QtGui import QGuiApplication, QImage, QColor
from PySide6.QtMultimedia import QMediaCaptureSession, QMediaRecorder, QMediaFormat, QVideoFrameInput, QVideoFrame

app = QGuiApplication([])
root = Path(__file__).resolve().parents[1] / 'acceptance-output'
path = root / ('camera-encoder-' + uuid4().hex[:8] + '.mp4')
session = QMediaCaptureSession()
source = QVideoFrameInput()
session.setVideoFrameInput(source)
recorder = QMediaRecorder()
session.setRecorder(recorder)
recorder.setMediaFormat(QMediaFormat(QMediaFormat.MPEG4))
recorder.setVideoResolution(QSize(160, 120))
recorder.setVideoFrameRate(10)
recorder.setOutputLocation(QUrl.fromLocalFile(str(path)))
state = {'frames':0, 'started':False, 'errors':[], 'finalized':False}

def changed(value):
    if value == QMediaRecorder.RecordingState:
        state['started'] = True
    elif value == QMediaRecorder.StoppedState and state['started']:
        state['finalized'] = True
        app.quit()

def frame():
    if not state['started']:
        return
    if state['frames'] >= 12:
        timer.stop()
        recorder.stop()
        return
    picture = QImage(160, 120, QImage.Format_RGBA8888)
    picture.fill(QColor.fromHsv(state['frames'] * 25, 180, 220))
    sample = QVideoFrame(picture)
    sample.setStartTime(state['frames'] * 100000)
    sample.setEndTime((state['frames'] + 1) * 100000)
    if source.sendVideoFrame(sample):
        state['frames'] += 1

def error(*args):
    state['errors'].append(recorder.errorString())
    app.quit()

recorder.recorderStateChanged.connect(changed)
recorder.errorOccurred.connect(error)
timer = QTimer(); timer.setInterval(100); timer.timeout.connect(frame); timer.start()
QTimer.singleShot(12000, app.quit)
recorder.record()
app.exec()
assert state['finalized'] and not state['errors'], state
assert path.is_file() and path.stat().st_size > 0
with av.open(str(path)) as video:
    decoded = sum(1 for _ in video.decode(video=0))
assert decoded == 12, decoded
report = {'qt_frames_encoded':state['frames'], 'frames_decoded':decoded, 'finalized':True, 'path':str(path)}
(root / 'camera-encoder.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
