"""Verify the no-device path without photographing or recording anyone."""
import json
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaDevices
from floter.tools.camera import CameraManager

if __name__ == '__main__':
    app = QGuiApplication([])
    devices = [device.description() for device in QMediaDevices.videoInputs()]
    report = {'devices':devices, 'hardware_capture_tested':False}
    if not devices:
        camera = CameraManager()
        try:
            camera.perform('photo')
            raise AssertionError('Missing camera unexpectedly reported success')
        except RuntimeError as exc:
            assert 'No camera was found' in str(exc), str(exc)
            report['no_device_error'] = str(exc)
            report['no_device_check_passed'] = True
        finally:
            camera.shutdown()
    path = Path(__file__).resolve().parents[1] / 'acceptance-output/camera-device.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
