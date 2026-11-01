# Run: python -m PyInstaller floter.spec --noconfirm
import sounddevice
import _sounddevice
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct
import tomllib

root = Path(SPECPATH)
release = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
version_tuple = tuple(map(int, release.split('.'))) + (0,)
windows_version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple, fileType=1),
    kids=[StringFileInfo([StringTable('040904B0', [
        StringStruct('CompanyName', 'FLOTER'),
        StringStruct('FileDescription', 'FLOTER desktop assistant'),
        StringStruct('FileVersion', release),
        StringStruct('InternalName', 'FLOTER'),
        StringStruct('OriginalFilename', 'FLOTER.exe'),
        StringStruct('ProductName', 'FLOTER'),
        StringStruct('ProductVersion', release),
    ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])],
)

datas = [
    (str(root / 'assets' / 'branding'), 'floter/assets/branding'),
    (str(root / 'THIRD_PARTY_NOTICES'), 'THIRD_PARTY_NOTICES'),
    (str(root / 'LICENSE'), '.'),
    (str(root / 'README.md'), '.'),
    (str(root / 'CONFIGURATION.md'), '.'),
    (str(root / 'codeexplainer.md'), '.'),
    (str(root / 'ARCHITECTURE.md'), '.'),
    (str(root / 'FEATURES.md'), '.'),
    (str(root / 'GUI_NAVIGATION.md'), '.'),
    (str(root / 'RELEASE_CHECKLIST.md'), '.'),
    (str(root / 'CLEANUP.md'), '.'),
    (str(root / 'INSTRUCTION_MANUAL.md'), '.'),
    (str(root / '.env.example'), '.'),
    (str(root / 'ui' / 'orb.qml'), 'floter/ui'),
    (str(root / 'ui' / 'RobotFace.qml'), 'floter/ui'),
    (str(root / 'ui' / 'Camera.qml'), 'floter/ui'),
    (sounddevice.__file__, '.'),
    (_sounddevice.__file__, '.'),
]
binaries = []
for helper in ('omniparser_service.py','provision_omniparser.py','omniparser_requirements.txt','start_omniparser.ps1'):
    datas.append((str(root / 'scripts' / helper), 'gui-setup'))
voice_model = root / 'models' / 'faster-whisper-small.en'
if voice_model.is_dir():
    for model_file in voice_model.glob('*'):
        if model_file.is_file():
            datas.append((str(model_file), 'models/faster-whisper-small.en'))
import sys
for library in ('cublas', 'cudnn', 'cuda_nvrtc'):
    directory = Path(sys.prefix) / 'Lib/site-packages/nvidia' / library / 'bin'
    if directory.is_dir():
        for dll in directory.glob('*.dll'):
            binaries.append((str(dll), 'nvidia/' + library + '/bin'))
hiddenimports = [
    'PySide6.QtQuick',
    'PySide6.QtQml',
    'PySide6.QtMultimedia',
    'PySide6.QtQuickControls2',
    '_cffi_backend',
    '_sounddevice',
    'sounddevice',
    '_sounddevice_data',
    'faster_whisper',
    'ctranslate2',
    'tokenizers',
    'huggingface_hub',
    'av',
    'tqdm',
    'cffi',
    'numpy',
    # Loaded by name inside the browser worker process, so static analysis cannot see it.
    'floter.tools.browser_session',
]

for pkg in ['langchain_core', 'pywinauto', 'comtypes', 'sounddevice', '_sounddevice_data', 'faster_whisper', 'ctranslate2', 'tokenizers', 'huggingface_hub', 'av', 'tqdm', 'cffi', 'playwright']:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

a = Analysis(
    [str(root / 'launcher.py')],
    pathex=[str(root.parent)],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=['PyQt6', 'PyQt5'],
    noarchive=False,
)

# Qt uses Windows ICU; an unrelated ICU on the build host PATH can be
# collected by PyInstaller and shadow the compatible Windows system DLL.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {'icuuc.dll', 'icuin.dll'}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FLOTER', console=False, icon=str(root / 'assets/branding/floter.ico'), version=windows_version)
coll = COLLECT(exe, a.binaries, a.datas, name='FLOTER')
