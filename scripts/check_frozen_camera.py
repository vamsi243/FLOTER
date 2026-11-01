"""Launch the bundled camera worker without capturing media when no camera exists."""
import json
import multiprocessing as mp
from pathlib import Path
import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaDevices
from floter.tools.camera import CameraManager

if __name__ == '__main__':
    app = QGuiApplication([])
    root = Path(__file__).resolve().parents[1]
    report = {'camera_count':len(QMediaDevices.videoInputs()), 'hardware_capture_tested':False}
    if report['camera_count'] == 0:
        # Use the frozen launch protocol and the executable's bundled module,
        # not this interpreter, for multiprocessing's camera child.
        mp.set_executable(str(root / 'dist/FLOTER/FLOTER.exe'))
        sys.frozen = True
        # Keep the child's frozen import paths. Inheriting this source runner's
        # sys.path would mix installed Qt DLLs with the bundled Qt runtime.
        from multiprocessing import spawn
        original_preparation = spawn.get_preparation_data
        def frozen_preparation(name):
            data = original_preparation(name)
            for key in ('sys_path', 'init_main_from_path', 'init_main_from_name'):
                data.pop(key, None)
            return data
        spawn.get_preparation_data = frozen_preparation
        camera = CameraManager()
        try:
            camera.perform('photo')
            raise AssertionError('Expected missing-camera failure')
        except RuntimeError as exc:
            assert 'No camera was found' in str(exc), str(exc)
            report['packaged_no_device_error'] = str(exc)
            report['packaged_worker_passed'] = True
        finally:
            camera.shutdown()
    (root / 'acceptance-output/camera-frozen.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
