"""Installed and frozen application entry point."""
import sys
from pathlib import Path


def browser_smoke_test():
    """Frozen-build check that FLOTER's browser starts in its worker process; uses a throwaway profile."""
    import tempfile
    from floter.config import config
    from floter.tools.browser_worker import BrowserWorker
    worker = BrowserWorker(channel=config.BROWSER_CHANNEL, profile_dir=tempfile.mkdtemp(prefix='floter-browser-smoke-'), input_sites=[])
    try:
        return 0 if worker.call(None, 'alive') is True and isinstance(worker.call(None, 'observe')['elements'], list) else 1
    finally:
        worker.close()


def main():
    import multiprocessing
    multiprocessing.freeze_support()
    if '--browser-worker-smoke-test' in sys.argv:
        return browser_smoke_test()
    if '--gui-worker-smoke-test' in sys.argv:
        import threading
        from floter.tools.gui_worker import DesktopWorker
        worker=DesktopWorker(threading.Event())
        try:
            assert isinstance(worker.windows(),list)
        finally:
            worker.close()
        return 0
    if '--camera-smoke-test' in sys.argv:
        from floter.tools.camera import camera_ui_smoke_test
        return camera_ui_smoke_test()
    if "--worker-smoke-test" in sys.argv:
        import threading
        from floter.workers import run_isolated
        if run_isolated(str, ("worker-ok",), threading.Event(), timeout=15) != "worker-ok":
            return 1
        return 0
    if "--test-voice-worker" in sys.argv:
        import threading
        from floter.audio.listener import _voice_worker
        from floter.workers import run_isolated, CancelledError
        from floter.config import config
        stop = threading.Event()
        log_path = Path("voice_test_result.txt")
        def on_prog(evt, val):
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"WORKER PROG: {evt} -> {val}\n")
            except Exception:
                pass
            if evt == 'state' and val == 'Listening':
                stop.set()
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("Starting isolated voice worker test...\n")
            run_isolated(_voice_worker, (0.5, ''), stop, timeout=20, on_progress=on_prog)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("VOICE WORKER FINISHED CLEANLY\n")
            return 0
        except CancelledError:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("VOICE WORKER REACHED LISTENING AND CANCELLED CLEANLY (SUCCESS)\n")
            return 0
        except Exception as exc:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"VOICE WORKER FAILED: {type(exc).__name__}: {exc}\n")
            return 1
    if "--diagnostics" in sys.argv:
        from floter.diagnostics import main as diagnose
        return diagnose(sys.argv[sys.argv.index("--diagnostics")+1:])
    try:
        return _run_gui()
    except Exception:
        import traceback
        report_startup_failure(traceback.format_exc())
        return 1


def report_startup_failure(detail):
    """The windowed EXE has no console: keep a log and tell the user where it is."""
    log = Path.home() / '.floter' / 'logs' / 'startup-error.log'
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(detail, encoding='utf-8')
    except OSError:
        log = None
    if sys.platform == 'win32' and '--smoke-test' not in sys.argv:
        import ctypes
        message = 'FLOTER could not start.\n\n' + detail.strip().splitlines()[-1][:500]
        if log:
            message += '\n\nDetails were saved to:\n' + str(log)
        ctypes.windll.user32.MessageBoxW(None, message, 'FLOTER', 0x10)


def _run_gui():
    from PySide6.QtCore import Qt, QUrl, QTimer
    from PySide6.QtGui import QGuiApplication, QColor, QSurfaceFormat, QIcon
    from PySide6.QtQuick import QQuickView
    from floter.ui.bridge import FloterBridge

    surface = QSurfaceFormat()
    surface.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(surface)
    app = QGuiApplication(sys.argv)
    app.setApplicationName("FLOTER")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets/branding/floter.ico')))
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('FLOTER.Desktop')
    view = QQuickView()
    view.setColor(QColor("#172f64"))
    view.setTitle('FLOTER')
    view.setFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    from PySide6.QtCore import QSize
    view.setMinimumSize(QSize(340, 400))
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    bridge = FloterBridge(view)
    app.aboutToQuit.connect(bridge.shutdown)
    view.rootContext().setContextProperty("floterBridge", bridge)
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / "ui" / "orb.qml")))
    if view.status() == QQuickView.Error:
        raise RuntimeError('The FLOTER window could not load: ' + '; '.join(e.toString() for e in view.errors()))
    view.show()
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(1200, app.quit)
    result = app.exec()
    view.setSource(QUrl())
    return result
