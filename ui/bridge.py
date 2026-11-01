import sys
import json
from datetime import datetime
from collections import deque
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, Property, QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

from floter.tiers.orchestrator import FloterOrchestrator
from floter.audio.listener import AudioListener
from floter.config import config

STATE_MAP = {
    "Idle": 0,
    "Listening": 1,
    "Thinking": 2,
    "Reasoning": 3,
    "Executing": 4,
    "Success": 5,
    "Blocked": 6
}

REVERSE_STATE_MAP = {v: k for k, v in STATE_MAP.items()}

class FloterBridge(QObject):
    """
    QObject Bridge exposing properties and slots to Qt6 QML.
    Connects AudioListener, FloterOrchestrator, and QML application interface.
    """

    approvalRequested = Signal(object)
    approvalChanged = Signal()
    wakeChanged = Signal()
    stateRequested = Signal(str)
    audioRequested = Signal(float)
    logRequested = Signal(str)
    transcriptReady = Signal(str)
    partialTranscriptReady = Signal(str)
    stateChanged = Signal()
    audioLevelChanged = Signal()
    logTraceChanged = Signal()
    historyChanged = Signal()
    liveTranscriptChanged = Signal()
    audioStateRequested = Signal(str)
    listeningRequested = Signal(bool)
    listeningChanged = Signal()
    completionRequested = Signal(str, object)
    commandCompleted = Signal(str)

    def __init__(self, view: Optional[QQuickView] = None):
        super().__init__()
        self.view = view
        self._gui_running = False
        self._history = deque(maxlen=500)
        self._voice_queue = deque()
        self._voice_timer = QTimer(self)
        self._voice_timer.setInterval(150)
        self._voice_timer.timeout.connect(self._drain_voice_queue)
        self._approval_token = ""
        self._approval_hide = True
        self._approval_text = ""
        self._wake = False
        self._listening = False
        self._audio_status = 'Off'
        self._closing = False
        self.approvalRequested.connect(self.receiveApproval, Qt.QueuedConnection)
        self._state_index: int = 0
        self._state_name: str = "Idle"
        self._audio_level: float = 0.0
        self._log_trace: str = "Ready. Type a command, or choose Speech + Text.\n"
        self._latest_message: str = "Ready. Type a command, or choose Speech + Text."
        self._live_transcript: str = ""

        self.stateRequested.connect(self.set_state_by_name, Qt.QueuedConnection)
        self.audioRequested.connect(self.set_audio_level, Qt.QueuedConnection)
        self.logRequested.connect(self.append_log, Qt.QueuedConnection)
        self.transcriptReady.connect(self.submitVoiceQuery, Qt.QueuedConnection)
        self.partialTranscriptReady.connect(self.set_live_transcript, Qt.QueuedConnection)
        self.audioStateRequested.connect(self.set_audio_status, Qt.QueuedConnection)
        self.listeningRequested.connect(self.set_listening, Qt.QueuedConnection)
        self.completionRequested.connect(self.complete_command, Qt.QueuedConnection)

        # Initialize Orchestrator and Audio Listener
        self.orchestrator = FloterOrchestrator(
            on_state_change=self.stateRequested.emit,
            on_log_message=self.logRequested.emit,
            on_approval=self.approvalRequested.emit,
            on_completed=self.completionRequested.emit
        )
        self.audio_listener = AudioListener(
            on_audio_level=self.audioRequested.emit,
            on_transcription=self.transcriptReady.emit,
            on_error=self.logRequested.emit,
            on_state_change=self.audioStateRequested.emit,
            on_partial_transcription=self.partialTranscriptReady.emit,
            on_wake_active=self.listeningRequested.emit
        )
        from floter.config import CONFIG_WARNINGS
        for warning in CONFIG_WARNINGS:
            self.append_log('Configuration: ' + warning)
        CONFIG_WARNINGS.clear()
        if not self.orchestrator.jev.api_key:
            from floter.config import ENV_FILE
            self.append_log(f'Jev key missing. Add Jev_API_Key to {ENV_FILE} and restart FLOTER.')

    @Slot(str, object)
    def complete_command(self, query, result):
        if self._gui_running and not self._closing:
            self._gui_running = False
            if self.view:
                self.view.showNormal()
                self.view.requestActivate()
        if self._closing or result.get('status') != 'success':
            return
        if self._live_transcript == query:
            self._live_transcript = ''
        # QML compares the submitted text with the current draft before clearing.
        # Do not send a transcript update that could overwrite newly typed text.
        self.commandCompleted.emit(query)

    @Property(bool, notify=listeningChanged)
    def listeningActive(self):
        return self._listening

    @Property(str, notify=listeningChanged)
    def microphoneStatus(self):
        return self._audio_status

    @Slot(bool)
    def set_listening(self, active):
        self._listening = bool(active and self._wake)
        self.listeningChanged.emit()

    @Slot(str)
    def set_audio_status(self, state):
        self._audio_status = {'Thinking':'Preparing speech…', 'Waiting':'Say “Hey Rex”',
                              'Listening':'Listening…', 'Idle':'Off'}.get(state, state)
        if state == 'Idle' and not self.audio_listener.wake_enabled:
            self._wake = False
            self._listening = False
            self.wakeChanged.emit()
        self.listeningChanged.emit()

    @Slot()
    def maximizeWindow(self):
        if self.view:
            if self.view.windowState() == Qt.WindowMaximized:
                self.view.showNormal()
            else:
                self.view.showMaximized()

    @Slot()
    def startWindowMove(self):
        if self.view:
            self.view.startSystemMove()

    @Slot(int)
    def resizeWindow(self, edges):
        if self.view:
            self.view.startSystemResize(Qt.Edge(edges))

    @Slot()
    def shutdown(self):
        self._closing = True
        self._voice_timer.stop()
        self._voice_queue.clear()
        self.audio_listener.stop_stream()
        self.orchestrator.shutdown()

    @Slot(object)
    def receiveApproval(self, ticket):
        if self._closing:
            return
        if ticket.get('gui'):
            if ticket.get('clear'):
                if self._approval_token == ticket['token']:
                    self._approval_token = ''
                    self._approval_text = ''
                    self.approvalChanged.emit()
                return
            self._gui_running = True
            if self.view:
                self.view.showNormal()
                self.view.requestActivate()
            self._approval_token = ticket['token']
            self._approval_hide = ticket.get('hide', True)
            self._approval_text = ticket['title'] + '\n\n' + ticket['detail']
            self.approvalChanged.emit()
            return
        self._approval_token = ticket['token']
        plan = ticket['plan']
        lines = [plan['summary'], '']
        for index, action in enumerate(plan['actions'], 1):
            args = action['arguments']
            if action['tool'] == 'launch_application':
                lines.append(f"{index}. Open {args['target']}")
            elif action['tool'] == 'snippy_capture':
                lines.append(f'{index}. Capture the full screen with Snippy and save the image locally.')
            elif action['tool'] == 'inspect_storage':
                lines.append(f"{index}. Read drive storage and paths (up to {args['time_budget']} seconds and "
                             f"{args['max_entries_per_drive']} entries per drive).")
            else:
                lines.append(f"{index}. Create new document: {args['file_name']}")
                if action['tool'] == 'write_notepad':
                    lines.append('Open this document in Notepad.')
                lines.extend(['Content:', args['content']])
            lines.append('')
        self._approval_text = '\n'.join(lines)
        self._record_history("Awaiting approval", self._approval_text)
        self.approvalChanged.emit()

    @Property(str, notify=approvalChanged)
    def approvalText(self):
        return self._approval_text

    @Slot(bool)
    def decideApproval(self, approved):
        try:
            if approved:
                if self._approval_token.startswith('gui:') and self._approval_hide and self.view:
                    self.view.showMinimized()
                if not self.orchestrator.approve_plan(self._approval_token):
                    if self.view: self.view.showNormal()
                    self.append_log('Finish the current request before approving.')
                    return
                self._record_history('Approval', 'Approved proposed actions.')
            else:
                if self._approval_token.startswith('gui:'):
                    self.orchestrator.gui_review.decide(self._approval_token, False)
                else:
                    self.orchestrator.reject_plan()
                self._record_history('Approval', 'Rejected the pending action; earlier completed actions remain.' if self._approval_token.startswith('gui:') else 'Rejected proposed actions; nothing executed.')
        except Exception as exc:
            self.append_log(str(exc))
        self._approval_token = ''
        self._approval_text = ''
        self.approvalChanged.emit()

    @Property(bool, notify=wakeChanged)
    def wakeEnabled(self):
        return self._wake

    @Slot(bool)
    def setWakeEnabled(self, enabled):
        if self._closing:
            return
        self._wake = bool(enabled and self.audio_listener.set_wake_enabled(True)) if enabled else False
        if not enabled:
            self.audio_listener.set_wake_enabled(False)
            self._listening = False
            self._audio_status = 'Off'
            self._voice_queue.clear()
            self.listeningChanged.emit()
        self.wakeChanged.emit()
        self.append_log('Speech + Text enabled. Say Hey Rex, then your command.' if self._wake else 'Text mode. Microphone off.')

    # Properties exposed to QML
    @Property(int, notify=stateChanged)
    def stateIndex(self) -> int:
        return self._state_index

    @Property(str, notify=stateChanged)
    def stateName(self) -> str:
        return self._state_name

    @Property(float, notify=audioLevelChanged)
    def audioLevel(self) -> float:
        return self._audio_level

    @Property(str, notify=logTraceChanged)
    def logTrace(self) -> str:
        return self._log_trace

    @Property(str, notify=liveTranscriptChanged)
    def liveTranscript(self) -> str:
        return self._live_transcript

    @Property(str, notify=logTraceChanged)
    def latestMessage(self):
        return self._latest_message

    @Property(str, constant=True)
    def jevCommands(self):
        apps = "\n".join(f"• open {name}" for name in config.WHITELISTED_APPS)
        sites = "\n".join(f"• open {name}" for name in config.WHITELISTED_URL_MAP)
        return (
            "APP EXAMPLES (routed by Jev)\n" + apps +
            "\n\nWEBSITES\n" + sites +
            "\n\nUse natural language, for example: Can you please open Notepad? "
            "Apps must be installed. Close an app by name; individual tab control is not supported."
            "\n\nSCREENSHOTS (requires Snippy)\n"
            "• take a screenshot\n• take a quick screen shot\n• capture screen"
            "\n\nSCREEN ANALYSIS (requires Gemini)\n"
            "• what is on my screen\n• look at this screen\n• analyze the display"
            "\n\nEvery command is classified by Jev through the configured API. "
            "An API key is required; no local phrase matching or offline fallback. "
            "High-confidence simple actions run automatically. Uncertain requests go to Hermes "
            "when a reasoning provider is configured; otherwise FLOTER asks you to rephrase."
            "\n\nFOLLOW-UP TYPING\nHey Rex, can you try opening a note pad?\n"
            "Try write how are you doing on the notepad.\n"
            "\nWEB SEARCH\nLook up hiking trails near Sydney.\nSearch for the weather on Edge.\n"
            "\nWEBSITES IN A BROWSER\nOpen Gmail on Brave.\nOpen YouTube in Chrome.\nGo to bbc.com.\n"
            "Without a browser name, your default browser is used."
        )

    @Property(str, notify=historyChanged)
    def commandHistory(self):
        return "\n\n".join(self._history)

    def _record_history(self, kind, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        self._history.append(f"[{stamp}] {kind}\n{str(text)[:20000]}")
        self.historyChanged.emit()

    @Slot()
    def minimizeWindow(self):
        if self.view:
            self.view.showMinimized()

    # Slots callable from QML
    @Slot(str)
    def submitVoiceQuery(self, query):
        if self._closing or not query.strip():
            return
        if len(self._voice_queue) >= 5:
            self.append_log('Voice queue is full; this command was not accepted.')
            return
        self._voice_queue.append(query.strip())
        self._voice_timer.start()
        self._drain_voice_queue()

    @Slot()
    def _drain_voice_queue(self):
        if self._closing:
            return
        if not self._voice_queue:
            self._voice_timer.stop()
        elif not self.orchestrator._lock.locked() and not self._approval_token:
            self.submitTextQuery(self._voice_queue.popleft())

    @Slot(str)
    def submitTextQuery(self, query: str) -> None:
        if not self._closing and query.strip():
            cleaned = query.strip()
            self._live_transcript = cleaned
            self.liveTranscriptChanged.emit()
            self._record_history("You", cleaned)
            if not self.orchestrator.process_query_async(cleaned):
                self._record_history("Not started", "FLOTER is busy. Submit the command again when idle.")

    @Slot()
    def triggerMicListening(self) -> None:
        if self.audio_listener._lock.locked():
            self.audio_listener.finish_utterance()
            self.append_log('Finishing this utterance…')
            return
        self.append_log("Triggered microphone listening...")
        self.audio_listener.trigger_push_to_talk(duration_sec=3.5)

    @Slot()
    def cancelVoice(self):
        self._voice_queue.clear()
        self.audio_listener.stop_stream()
        self._wake = False
        self.wakeChanged.emit()
        self.append_log('Microphone stopped; unfinished speech discarded.')

    @Slot()
    def stopTask(self):
        self._voice_queue.clear()
        self.orchestrator.cancel_task()
        self.append_log('Stop requested. Completed actions cannot be undone.')

    @Slot(int, int)
    def moveWindow(self, dx: int, dy: int) -> None:
        if self.view:
            current_pos = self.view.position()
            self.view.setPosition(current_pos + QPoint(dx, dy))

    @Slot()
    def closeApplication(self) -> None:
        if self.view:
            self.view.close()
        app = QGuiApplication.instance()
        if app:
            app.quit()

    # Internal update methods
    @Slot(str)
    def set_live_transcript(self, text: str) -> None:
        if self._closing:
            return
        self._live_transcript = text
        self.liveTranscriptChanged.emit()

    @Slot(str)
    def set_state_by_name(self, name: str) -> None:
        if self._closing:
            return
        if self._wake and not self.audio_listener.wake_enabled:
            self._wake = False
            self.wakeChanged.emit()

        # If returning to Idle after Success or Blocked, delay slightly so the user clearly sees the state
        if name == "Idle" and self._state_name in ("Success", "Blocked"):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1600, self._delayed_return_to_idle)
            return

        self._state_name = name
        self._state_index = STATE_MAP.get(name, 0)
        self.stateChanged.emit()

    def _delayed_return_to_idle(self) -> None:
        if self._closing or self._state_name not in ("Success", "Blocked"):
            return
        self._state_name = "Idle"
        self._state_index = STATE_MAP.get("Idle", 0)
        self.stateChanged.emit()

    @Slot(float)
    def set_audio_level(self, level: float) -> None:
        self._audio_level = level
        self.audioLevelChanged.emit()

    @Slot(str)
    def append_log(self, text: str) -> None:
        self._record_history("FLOTER", text)
        if text.strip():
            self._latest_message = text.lstrip("• ")
        self._log_trace += f"• {text}\n"
        # Keep trace bounded
        lines = self._log_trace.splitlines()
        if len(lines) > 20:
            self._log_trace = "\n".join(lines[-20:]) + "\n"
        self.logTraceChanged.emit()
