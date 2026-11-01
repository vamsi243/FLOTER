"""Visible, local camera capture in an isolated Qt process."""
import multiprocessing as mp
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4
from datetime import datetime


@dataclass
class CaptureJob:
    process: object
    stop: object
    connection: object
    action: str
    ready: threading.Event = field(default_factory=threading.Event)
    finished: threading.Event = field(default_factory=threading.Event)
    startup: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)


class CameraManager:
    def __init__(self, on_message=None):
        self.on_message = on_message or (lambda message: None)
        self.job = None
        self._lock = threading.Lock()
        self._closed = False

    def perform(self, action):
        if action not in {'open', 'photo', 'record', 'stop', 'close'}:
            raise ValueError('Unsupported camera action')
        with self._lock:
            if self._closed:
                raise RuntimeError('Camera is shutting down.')
            if action in {'stop', 'close'}:
                return self._stop()
            if self.job and not self.job.finished.is_set():
                # Preview can be replaced with a requested capture, but an active
                # recording must be explicitly stopped before starting another.
                if self.job.action == 'open':
                    self._stop()
                else:
                    raise RuntimeError('The camera is already capturing. Say “stop recording” or use the camera Stop button first.')
            from floter.config import config
            directory = Path(config.CAMERA_SAVE_DIR).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:8] + ('.jpg' if action == 'photo' else '.mp4'))
            ctx = mp.get_context('spawn')
            receive, send = ctx.Pipe(duplex=False)
            stop = ctx.Event()
            process = ctx.Process(target=camera_worker, args=(action, config.CAMERA_DEVICE,
                str(path), max(1, min(300, config.CAMERA_VIDEO_SECONDS)), config.CAMERA_RECORD_AUDIO, stop, send))
            job = CaptureJob(process, stop, receive, action)
            try:
                process.start()
            except Exception:
                receive.close()
                raise
            finally:
                send.close()
            self.job = job
            threading.Thread(target=self._monitor, args=(job,), daemon=True).start()
            event = job.finished if action == 'photo' else job.ready
            if not event.wait(25):
                stop.set()
                raise RuntimeError('The camera did not become ready. Check Windows camera access and whether another app is using it.')
            result = job.result if job.finished.is_set() else job.startup
            if result.get('status') != 'success':
                raise RuntimeError(result.get('message', 'Camera capture could not start.'))
            return result

    def _monitor(self, job):
        stop_requested_at = None
        try:
            while True:
                if job.stop.is_set():
                    stop_requested_at = stop_requested_at or time.monotonic()
                    if time.monotonic() - stop_requested_at > 12:
                        break
                if job.connection.poll(.1):
                    try:
                        event, result = job.connection.recv()
                    except EOFError:
                        break
                    if event == 'ready':
                        job.startup = result
                        job.ready.set()
                    elif event == 'done':
                        job.result = result
                        break
                elif not job.process.is_alive():
                    break
        finally:
            job.process.join(3)
            if job.process.is_alive():
                job.process.terminate()  # Only this manager's unresponsive child.
                job.process.join(2)
            if not job.result:
                job.result = {'status':'error', 'message':'Camera stopped unexpectedly; no completed capture was confirmed.'}
            job.connection.close()
            job.ready.set()
            job.finished.set()
            if job.action != 'photo':
                self.on_message(job.result['message'])

    def _stop(self):
        job = self.job
        if not job or job.finished.is_set():
            return {'status':'success', 'message':'The camera is not recording or previewing.'}
        job.stop.set()
        if not job.finished.wait(15):
            raise RuntimeError('The camera is still finalizing the recording. Please wait before starting another capture.')
        if job.result.get('status') != 'success':
            raise RuntimeError(job.result['message'])
        return job.result

    def shutdown(self):
        self._closed = True
        job = self.job
        if job and not job.finished.is_set():
            job.stop.set()
            if not job.finished.wait(12):
                if job.process.is_alive():
                    job.process.terminate()
                job.finished.wait(3)


def camera_worker(action, device_name, output, duration, with_audio, stop, connection):
    """The child owns all Qt media objects and their event loop."""
    try:
        from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer, QUrl, QSize
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQuick import QQuickView
        from PySide6.QtMultimedia import (QMediaDevices, QCamera, QMediaCaptureSession,
            QImageCapture, QMediaRecorder, QMediaFormat, QAudioInput)

        app = QGuiApplication([])
        app.setQuitOnLastWindowClosed(False)
        devices = QMediaDevices.videoInputs()
        if not devices:
            raise RuntimeError('No camera was found. Connect a camera and allow desktop camera access in Windows Settings.')
        selected = next((device for device in devices if device.description().casefold() == device_name.casefold()), None) if device_name else QMediaDevices.defaultVideoInput()
        if selected is None or selected.isNull():
            raise RuntimeError('The configured camera was not found. Check CAMERA_DEVICE or leave it blank for the default camera.')

        class Controls(QObject):
            changed = Signal()
            stopRequested = Signal()
            _status = 'Starting camera…'
            @Property(str, notify=changed)
            def status(self):
                return self._status
            def update(self, text):
                self._status = text
                self.changed.emit()
            @Slot()
            def stopCapture(self):
                self.stopRequested.emit()

        controls = Controls()
        view = QQuickView()
        view.setTitle('FLOTER · Camera')
        view.setMinimumSize(QSize(360, 300))
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.rootContext().setContextProperty('cameraControls', controls)
        view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'ui/Camera.qml')))
        if view.status() == QQuickView.Error:
            raise RuntimeError('The camera preview could not load.')
        sink = view.rootObject().findChild(QObject, 'cameraVideo').property('videoSink')
        camera = QCamera(selected)
        session = QMediaCaptureSession()
        session.setCamera(camera)
        session.setVideoSink(sink)
        capture = QImageCapture()
        session.setImageCapture(capture)
        recorder = QMediaRecorder()
        session.setRecorder(recorder)
        audio = None
        if action == 'record' and with_audio:
            audio_device = QMediaDevices.defaultAudioInput()
            if audio_device.isNull():
                raise RuntimeError('No microphone was found for video audio. Connect one or set CAMERA_RECORD_AUDIO=0 for silent video.')
            audio = QAudioInput(audio_device)
            session.setAudioInput(audio)
        fmt = QMediaFormat(QMediaFormat.MPEG4)
        recorder.setMediaFormat(fmt)
        recorder.setQuality(QMediaRecorder.NormalQuality)
        recorder.setVideoResolution(QSize(1280, 720))
        recorder.setOutputLocation(QUrl.fromLocalFile(output))
        state = {'done':False, 'started':False, 'recording':False, 'stopping':False, 'frame':False, 'start_time':0.0}
        deadline = QTimer(); deadline.setSingleShot(True)
        finalize = QTimer(); finalize.setSingleShot(True)
        limit = QTimer(); limit.setSingleShot(True)

        def send(event, message, **extra):
            connection.send((event, {'status':'success', 'message':message, **extra}))

        def finish(message, path=None, error=False):
            if state['done']:
                return
            state['done'] = True
            deadline.stop(); finalize.stop(); limit.stop()
            camera.stop()
            connection.send(('done', {'status':'error' if error else 'success', 'message':message, **({'path':path} if path else {})}))
            app.quit()

        def fail(message):
            if state['done']:
                return
            finish(message, error=True)
            if recorder.recorderState() != QMediaRecorder.StoppedState:
                recorder.stop()

        def saved_photo(capture_id, filename):
            if Path(filename).is_file() and Path(filename).stat().st_size:
                finish('Photo saved: ' + filename, filename)
            else:
                fail('The camera did not save the photo. Check the output folder.')

        def recorder_state(value):
            if state['done']:
                return
            if value == QMediaRecorder.RecordingState:
                state['recording'] = True
                state['start_time'] = time.monotonic()
                deadline.stop()
                limit.start(duration * 1000)
                controls.update(f'● Recording · 0s / {duration}s · ' + ('with audio' if with_audio else 'silent'))
                send('ready', f'Recording started. Say “Hey Rex, stop recording” or click Stop. It stops automatically after {duration} seconds.', recording=True)
            elif value == QMediaRecorder.StoppedState and state['recording']:
                filename = recorder.actualLocation().toLocalFile() or output
                if Path(filename).is_file() and Path(filename).stat().st_size:
                    finish('Video saved: ' + filename, filename)
                else:
                    fail('Recording ended but no completed video was saved.')

        def end_capture():
            if state['done'] or state['stopping']:
                return
            state['stopping'] = True
            deadline.stop(); limit.stop()
            if state['recording']:
                controls.update('Saving video…')
                finalize.start(10000)
                recorder.stop()
            elif action == 'open':
                finish('Camera preview closed.')
            else:
                finish('Camera capture cancelled before completion.', error=True)

        def begin_capture():
            if state['started'] or state['done'] or state['stopping'] or not state['frame']:
                return
            if action == 'photo' and not capture.isReadyForCapture():
                return
            state['started'] = True
            if action == 'photo':
                controls.update('Taking photo…')
                if capture.captureToFile(output) < 0:
                    fail('The camera could not take the photo. Please try again.')
            elif action == 'record':
                recorder.record()
            else:
                deadline.stop()
                controls.update('Camera preview · not recording')
                send('ready', 'Camera preview opened. Ask to take a picture or record a video.', preview=True)

        def first_frame(frame):
            if frame.isValid() and not state['frame']:
                state['frame'] = True
                QTimer.singleShot(600, begin_capture)

        def tick():
            if stop.is_set():
                end_capture()
            elif state['recording'] and not state['stopping']:
                elapsed = int(time.monotonic() - state['start_time'])
                controls.update(f'● Recording · {elapsed}s / {duration}s · ' + ('with audio' if with_audio else 'silent'))

        capture.imageSaved.connect(saved_photo)
        capture.readyForCaptureChanged.connect(lambda ready: begin_capture() if ready and state['frame'] else None)
        capture.errorOccurred.connect(lambda *_: fail('Photo capture failed. Check camera access and the save folder.'))
        camera.errorOccurred.connect(lambda *_: fail('Camera access failed. Allow desktop camera access in Windows Settings and close other apps using the camera.'))
        recorder.errorOccurred.connect(lambda *_: fail('Video recording failed. Check camera/microphone permissions, available disk space and media encoder support.'))
        recorder.recorderStateChanged.connect(recorder_state)
        sink.videoFrameChanged.connect(first_frame)
        controls.stopRequested.connect(end_capture)
        view.closing.connect(lambda *_: end_capture())
        deadline.timeout.connect(lambda: fail('The camera did not supply usable frames. Check device access and try again.'))
        finalize.timeout.connect(lambda: fail('Video finalization timed out; the recording may be incomplete.'))
        limit.timeout.connect(end_capture)
        poll = QTimer(); poll.setInterval(100); poll.timeout.connect(tick); poll.start()
        view.show()
        deadline.start(15000)
        # Start only after the event loop begins, so immediate device errors
        # can reliably finish the worker via app.quit().
        QTimer.singleShot(0, camera.start)
        app.exec()
        camera.stop()
        session.setVideoSink(None)
        view.setSource(QUrl())
    except Exception as exc:
        connection.send(('done', {'status':'error', 'message':str(exc)}))
    finally:
        connection.close()


def camera_ui_smoke_test():
    """Load the real preview/backend without turning on any device."""
    from PySide6.QtCore import QUrl, QObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlPropertyMap
    from PySide6.QtQuick import QQuickView
    from PySide6.QtMultimedia import QMediaFormat, QMediaDevices
    app = QGuiApplication([])
    controls = QQmlPropertyMap()
    controls.insert('status', 'Camera preview check · camera off')
    view = QQuickView()
    view.rootContext().setContextProperty('cameraControls', controls)
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'ui/Camera.qml')))
    if view.status() == QQuickView.Error:
        return 1
    assert view.rootObject().findChild(QObject, 'cameraVideo').property('videoSink') is not None
    assert QMediaFormat.MPEG4 in QMediaFormat().supportedFileFormats(QMediaFormat.Encode)
    print('Camera preview and MP4 encoding backend loaded; available cameras:', len(QMediaDevices.videoInputs()))
    view.setSource(QUrl())
    return 0
