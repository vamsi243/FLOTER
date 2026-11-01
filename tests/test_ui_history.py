"""Regression coverage for command history and native window controls."""
import os
import subprocess
import sys


def test_history_and_minimize():
    script = '''
from unittest.mock import Mock
from PySide6.QtGui import QGuiApplication
from floter.ui.bridge import FloterBridge
app = QGuiApplication([])
view = Mock()
bridge = FloterBridge(view)
bridge.orchestrator.process_query_async = Mock(return_value=True)
bridge.submitTextQuery('open notepad')
bridge.append_log('Successfully launched application: notepad')
assert 'You\\nopen notepad' in bridge.commandHistory
assert 'FLOTER\\nSuccessfully launched application: notepad' in bridge.commandHistory
bridge.orchestrator.process_query_async.return_value = False
bridge.submitTextQuery('open calculator')
assert 'Not started' in bridge.commandHistory
before = bridge.commandHistory
bridge.submitTextQuery('   ')
assert bridge.commandHistory == before
bridge.receiveApproval({'token': 'test', 'plan': {'summary': 'Test plan', 'actions': []}})
bridge.decideApproval(False)
assert 'Awaiting approval' in bridge.commandHistory
assert 'Rejected proposed actions; nothing executed.' in bridge.commandHistory
bridge.receiveApproval({'token':'storage', 'plan':{'summary':'Inspect storage','actions':[
    {'tool':'inspect_storage','arguments':{'time_budget':5,'max_entries_per_drive':100}}]}})
assert '5 seconds' in bridge.approvalText and '100 entries per drive' in bridge.approvalText
bridge.decideApproval(False)
bridge.minimizeWindow()
view.showMinimized.assert_called_once()
for i in range(510): bridge.append_log(f'entry {i}')
assert len(bridge._history) == 500
assert 'entry 509' in bridge.commandHistory
assert 'You\\nopen notepad' not in bridge.commandHistory
bridge.shutdown()
'''
    result = subprocess.run([sys.executable, '-c', script], env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_latest_message_keeps_every_line_of_a_multiline_result():
    script = '''
from unittest.mock import Mock
from PySide6.QtGui import QGuiApplication
from floter.ui.bridge import FloterBridge
app = QGuiApplication([])
bridge = FloterBridge(Mock())
bridge.append_log('first drive\\nsecond drive')
assert bridge.latestMessage == 'first drive\\nsecond drive'
bridge.append_log('next result')
assert bridge.latestMessage == 'next result'
bridge.shutdown()
'''
    result = subprocess.run([sys.executable, '-c', script], env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_navigation_approval_minimizes_only_before_screen_work():
    script = '''
from unittest.mock import Mock
from PySide6.QtGui import QGuiApplication
from floter.ui.bridge import FloterBridge
app = QGuiApplication([])
view = Mock()
bridge = FloterBridge(view)
bridge.orchestrator.approve_plan = Mock(return_value=True)
bridge.receiveApproval({'token':'gui:a','gui':True,'title':'Navigate an application','detail':'goal','hide':False})
bridge.decideApproval(True)
view.showMinimized.assert_not_called()
bridge.receiveApproval({'token':'gui:b','gui':True,'title':'Select application','detail':'Gemini','hide':True})
bridge.decideApproval(True)
view.showMinimized.assert_called_once()
bridge.shutdown()
'''
    result = subprocess.run([sys.executable, '-c', script], env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_compact_face_tracks_real_activity_and_task_priority():
    script = '''
from pathlib import Path
from PySide6.QtCore import QUrl, QObject, QMetaObject, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from unittest.mock import Mock
from floter.ui.bridge import FloterBridge
import floter
app = QGuiApplication([])
view = QQuickView()
bridge = FloterBridge(view)
view.rootContext().setContextProperty('floterBridge', bridge)
view.setSource(QUrl.fromLocalFile(str(Path(floter.__file__).parent / 'ui/orb.qml')))
assert view.status() != QQuickView.Error
view.show()
root = view.rootObject()
assert root.width() == 420 and root.height() == 620
# Keys come from %USERPROFILE%/.floter/.env; the window has no settings screen.
assert root.findChild(QObject, 'settingsButton') is None and root.findChild(QObject, 'settingsDialog') is None
assert root.property('greeting') == "Hey, I'm Rex."
face = root.findChild(QObject, 'robotFace')
assert face is not None and face.property('mood') == 'idle'
face.setProperty('idleExpression', 'sleeping')
assert face.property('expression') == 'sleeping'
assert root.property('color').name() == '#172f64'
for name in ['minimizeButton', 'maximizeButton', 'closeButton', 'sendButton']:
    assert root.findChild(QObject, name) is not None
bridge.set_state_by_name('Thinking')
assert face.property('mood') == 'thinking'
assert face.property('expression') == 'thinking'
bridge.set_state_by_name('Idle')
assert face.property('mood') == 'idle'
bridge.set_state_by_name('Listening')
bridge.set_audio_level(0)
bridge.set_audio_level(.2)
assert face.property('mood') == 'idle' # audio alone must not imply wake recognition
bridge._wake = True
bridge.audio_listener = Mock(wake_enabled=True)
bridge.wakeChanged.emit()
assert face.property('mood') == 'waiting'
bridge.set_listening(True)
assert face.property('mood') == 'listening'
for state, mood in [('Thinking','thinking'),('Reasoning','thinking'),('Executing','working'),('Success','success'),('Blocked','alert')]:
    bridge.set_state_by_name(state)
    assert face.property('mood') == mood
    QTest.qWait(250)
    assert face.property('state') == mood
bridge.receiveApproval({'token':'face-test','plan':{'summary':'Review','actions':[]}})
assert face.property('mood') == 'approval'
bridge.decideApproval(False)
bridge.set_state_by_name('Thinking')
bridge.set_state_by_name('Idle')
assert face.property('mood') == 'listening'
bridge.set_listening(False)
assert face.property('mood') == 'waiting'
view.showMinimized()
QTest.qWait(50)
assert not face.property('motionEnabled')
view.showNormal()
assert root.findChild(QObject, 'jevListButton') is None
assert root.findChild(QObject, 'liveTranscriptText') is None
for name in ['textModeButton','speechModeButton']:
    assert root.findChild(QObject, name) is not None
button = root.findChild(QObject, 'logsButton')
assert QMetaObject.invokeMethod(button, 'clicked', Qt.DirectConnection)
app.processEvents()
assert root.findChild(QObject, 'logsDialog').property('visible')
root.findChild(QObject, 'logsDialog').setProperty('visible', False)
bridge.orchestrator.process_query_async = Mock(return_value=True)
field = root.findChild(QObject, 'commandInput')
field.setProperty('text', 'open notepad')
field.forceActiveFocus()
QTest.keyClick(view, Qt.Key_Return)
QTest.qWait(50)
bridge.orchestrator.process_query_async.assert_called_once_with('open notepad')
assert field.property('text') == 'open notepad'
bridge.complete_command('open notepad', {'status':'error'})
assert field.property('text') == 'open notepad'
bridge.complete_command('open notepad', {'status':'success'})
assert field.property('text') == ''
field.setProperty('text', 'my next command')
bridge.complete_command('open notepad', {'status':'success'})
assert field.property('text') == 'my next command'
bridge.orchestrator.process_query_async.reset_mock()
field.setProperty('text', 'open calculator')
assert QMetaObject.invokeMethod(root.findChild(QObject, 'sendButton'), 'clicked', Qt.DirectConnection)
bridge.orchestrator.process_query_async.assert_called_once_with('open calculator')
assert QMetaObject.invokeMethod(root.findChild(QObject, 'minimizeButton'), 'clicked', Qt.DirectConnection)
assert view.windowState() == Qt.WindowMinimized
view.showNormal()
assert QMetaObject.invokeMethod(root.findChild(QObject, 'maximizeButton'), 'clicked', Qt.DirectConnection)
assert view.windowState() == Qt.WindowMaximized
assert QMetaObject.invokeMethod(root.findChild(QObject, 'maximizeButton'), 'clicked', Qt.DirectConnection)
assert view.windowState() == Qt.WindowNoState
bridge.set_audio_status('Waiting')
bridge.set_state_by_name('Executing')
bridge.set_audio_status('Listening')
assert bridge.stateName == 'Executing'
bridge.set_state_by_name('Idle')
view.setResizeMode(QQuickView.SizeRootObjectToView)
bridge.set_live_transcript('A long transcript with enough words to wrap. ' * 30)
bridge.append_log('A lengthy result should remain accessible by scrolling. ' * 40)
for width,height in [(340,400),(700,800)]:
    view.resize(width,height)
    QTest.qWait(100)
    assert root.width()==width and root.height()==height
    field=root.findChild(QObject,'commandInput')
    assert field.property('width') > 80
    assert field.property('text') == bridge.liveTranscript
    result=root.findChild(QObject,'resultText')
    assert result.property('implicitHeight') > 64
    assert root.findChild(QObject,'bodyScroll').property('contentHeight') > 0
bridge.shutdown()
view.setSource(QUrl())
'''
    result = subprocess.run([sys.executable, '-c', script], env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
