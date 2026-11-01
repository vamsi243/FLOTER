import QtQuick 2.15
import QtQuick.Controls.Basic
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    width: 420; height: 620
    color: "#172f64"
    readonly property bool compact: height < 520
    property int currentState: floterBridge.stateIndex
    property real audioLevel: floterBridge.audioLevel
    readonly property string faceMood: floterBridge.approvalText.length > 0 ? "approval"
        : currentState === 6 ? "alert" : currentState === 5 ? "success"
        : currentState === 4 ? "working" : currentState === 2 || currentState === 3 ? "thinking"
        : floterBridge.listeningActive ? "listening" : floterBridge.wakeEnabled ? "waiting" : "idle"
    readonly property string greeting: faceMood === "approval" ? "A little check before I go."
        : faceMood === "alert" ? "Let's try that together."
        : faceMood === "success" ? "All done. What's next?"
        : faceMood === "thinking" ? "Let me think about that."
        : faceMood === "working" ? "I'm on it."
        : faceMood === "listening" ? "I'm listening."
        : faceMood === "waiting" ? "Just say, “Hey Rex”." : "Hey, I'm Rex."

    component BuddyButton: Button {
        id: control
        implicitHeight: 34; implicitWidth: Math.max(34, contentItem.implicitWidth + 24)
        hoverEnabled: true
        font.family: "Segoe UI"; font.pixelSize: 12
        Accessible.name: text
        background: Rectangle {
            radius: height / 2
            color: control.down ? "#30f4f4f4" : control.checked || control.hovered ? "#1cf4f4f4" : "transparent"
            border.width: control.activeFocus ? 1 : 0; border.color: "#f4f4f4"
            Behavior on color { ColorAnimation { duration: 140 } }
        }
        contentItem: Text {
            text: control.text; font: control.font; color: "#f4f4f4"
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
    }
    component ReadPanel: ScrollView {
        property alias text: area.text
        property alias areaName: area.objectName
        clip: true; contentWidth: availableWidth
        TextArea {
            id: area; width: parent.availableWidth
            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
            textFormat: TextEdit.PlainText
            font.family: "Segoe UI"; font.pixelSize: 13
            color: "#f4f4f4"; selectionColor: "#446095"; selectedTextColor: "#f4f4f4"
            background: null
        }
    }
    component SurfaceDialog: Dialog {
        anchors.centerIn: parent
        width: parent.width - 32; height: parent.height - 32
        modal: true
        palette.windowText: "#f4f4f4"; palette.text: "#f4f4f4"; palette.buttonText: "#f4f4f4"
        palette.button: "#172f64"; palette.window: "#172f64"
        palette.highlight: "#446095"; palette.highlightedText: "#f4f4f4"
        background: Rectangle { color: "#172f64"; radius: 18 }
    }
    SurfaceDialog {
        id: approvalDialog; title: "A moment for your approval"
        visible: floterBridge.approvalText.length > 0
        closePolicy: Popup.NoAutoClose
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: floterBridge.decideApproval(true)
        onRejected: floterBridge.decideApproval(false)
        contentItem: ReadPanel { text: floterBridge.approvalText }
    }
    SurfaceDialog {
        id: logsDialog; objectName: "logsDialog"; title: "Our activity · this session"
        standardButtons: Dialog.Close
        contentItem: ReadPanel { areaName: "historyText"; text: floterBridge.commandHistory || "Our next adventure starts with your first request." }
    }
    Connections {
        target: floterBridge
        function onLiveTranscriptChanged() {
            inputField.text = floterBridge.liveTranscript
            inputField.cursorPosition = inputField.length
        }
        function onCommandCompleted(query) {
            if (inputField.text.trim() === query.trim()) inputField.clear()
        }
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: root.compact ? 18 : 24
        spacing: root.compact ? 8 : 14
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: 38
            MouseArea {
                anchors.fill: parent
                onPressed: floterBridge.startWindowMove()
                onDoubleClicked: floterBridge.maximizeWindow()
            }
            Row {
                spacing: 9; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                Rectangle {
                    width: 34; height: 34; radius: 10; color: "#f4f4f4"
                    Image { anchors.fill: parent; anchors.margins: 5; source: "../assets/branding/floter-logo.png"; fillMode: Image.PreserveAspectFit; smooth: true }
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter; spacing: 1
                    Text { text: "FLOTER"; color: "#f4f4f4"; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                    Text { text: "YOUR AI BUDDY"; color: "#f4f4f4"; opacity: .65; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1.5 }
                }
            }
            Row {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                BuddyButton { objectName: "minimizeButton"; text: "−"; implicitWidth: 30; Accessible.name: "Minimize"; onClicked: floterBridge.minimizeWindow() }
                BuddyButton { objectName: "maximizeButton"; text: "□"; implicitWidth: 30; Accessible.name: "Maximize or restore"; onClicked: floterBridge.maximizeWindow() }
                BuddyButton { objectName: "closeButton"; text: "×"; implicitWidth: 30; Accessible.name: "Close FLOTER"; onClicked: floterBridge.closeApplication() }
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: root.compact ? 84 : Math.min(190, root.height * .3)
            Layout.minimumHeight: 64
            RobotFace { id: buddy; anchors.fill: parent; mood: root.faceMood; audioLevel: root.audioLevel }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 6
            Label {
                Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
                text: root.greeting; color: "#f4f4f4"; font.family: "Segoe UI"
                font.pixelSize: root.compact ? 20 : 25; font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
                text: floterBridge.wakeEnabled ? floterBridge.microphoneStatus : "A little help. A little company."
                color: "#f4f4f4"; opacity: .72; font.family: "Segoe UI"; font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: root.compact ? 40 : 65
            radius: 16; color: "#0bf4f4f4"
            ScrollView {
                id: body; objectName: "bodyScroll"
                anchors.fill: parent; anchors.margins: 13
                ScrollBar.vertical.policy: ScrollBar.AsNeeded
                clip: true; contentWidth: availableWidth
                TextArea {
                    objectName: "resultText"; width: body.availableWidth
                    text: root.currentState === 2 ? "Thinking about your request…" : root.currentState === 4 ? "Taking care of that for you…"
                        : floterBridge.latestMessage === "Ready. Type a command, or choose Speech + Text." ? "Open an app, jot something down, or ask me to lend a hand." : floterBridge.latestMessage
                    readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                    color: "#f4f4f4"; font.family: "Segoe UI"; font.pixelSize: 12
                    selectionColor: "#446095"; selectedTextColor: "#f4f4f4"
                    background: null; padding: 0
                    Accessible.name: "Latest command result"
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 3
            Rectangle {
                implicitWidth: modeRow.implicitWidth + 8; implicitHeight: 38; radius: 19; color: "#0bf4f4f4"
                Row {
                    id: modeRow; anchors.centerIn: parent; spacing: 2
                    BuddyButton { objectName: "textModeButton"; text: "Text"; checkable: true; checked: !floterBridge.wakeEnabled; onClicked: floterBridge.setWakeEnabled(false) }
                    BuddyButton { objectName: "speechModeButton"; text: "Speech + Text"; checkable: true; checked: floterBridge.wakeEnabled; onClicked: { if (!floterBridge.wakeEnabled) floterBridge.setWakeEnabled(true) } }
                }
            }
            Item { Layout.fillWidth: true }
            BuddyButton { objectName: "stopTaskButton"; text: "Stop"; visible: root.currentState !== 0; onClicked: floterBridge.stopTask() }
            BuddyButton { objectName: "logsButton"; text: "Activity"; onClicked: logsDialog.open() }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: root.compact ? 67 : 90
            radius: 18; color: "#12f4f4f4"
            border.width: inputField.activeFocus ? 1 : 0; border.color: "#60f4f4f4"
            ScrollView {
                id: inputScroll; anchors.fill: parent; anchors.rightMargin: 53
                anchors.margins: 10; clip: true; contentWidth: availableWidth
                TextArea {
                    id: inputField; objectName: "commandInput"; width: inputScroll.availableWidth
                    placeholderText: "What's on your mind?"; placeholderTextColor: "#b8c3d8"
                    color: "#f4f4f4"; font.family: "Segoe UI"; font.pixelSize: 13
                    selectionColor: "#446095"; selectedTextColor: "#f4f4f4"
                    wrapMode: TextEdit.Wrap; selectByMouse: true; textFormat: TextEdit.PlainText
                    background: null
                    Accessible.name: "Type a command or see live speech here; Enter to send"
                    function submit() { if (text.trim()) floterBridge.submitTextQuery(text) }
                    Keys.onReturnPressed: function(event) { if (!(event.modifiers & Qt.ShiftModifier)) { submit(); event.accepted = true } else event.accepted = false }
                    Keys.onEnterPressed: function(event) { if (!(event.modifiers & Qt.ShiftModifier)) { submit(); event.accepted = true } else event.accepted = false }
                }
            }
            BuddyButton {
                objectName: "sendButton"; anchors.right: parent.right; anchors.rightMargin: 10; anchors.bottom: parent.bottom; anchors.bottomMargin: 10
                text: "↑"; font.pixelSize: 23; implicitWidth: 34; checked: true
                Accessible.name: "Send command"; enabled: inputField.text.trim().length > 0
                opacity: enabled ? 1 : .45; onClicked: inputField.submit()
            }
        }
        Label {
            visible: !root.compact; Layout.alignment: Qt.AlignHCenter
            text: floterBridge.wakeEnabled ? "Say Hey Rex · I'm here when you need me" : "Microphone off · Enter to send"
            color: "#f4f4f4"; opacity: .55; font.family: "Segoe UI"; font.pixelSize: 10
        }
    }
    // Invisible native resize grips keep the frameless window usable.
    Repeater {
        model: [Qt.LeftEdge, Qt.RightEdge, Qt.TopEdge, Qt.BottomEdge,
                Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.TopEdge,
                Qt.LeftEdge | Qt.BottomEdge, Qt.RightEdge | Qt.BottomEdge]
        delegate: MouseArea {
            required property int modelData
            readonly property bool horizontalEdge: (modelData & Qt.LeftEdge) || (modelData & Qt.RightEdge)
            readonly property bool verticalEdge: (modelData & Qt.TopEdge) || (modelData & Qt.BottomEdge)
            width: horizontalEdge ? 6 : root.width - 12
            height: verticalEdge ? 6 : root.height - 12
            x: modelData & Qt.RightEdge ? root.width - width : horizontalEdge ? 0 : 6
            y: modelData & Qt.BottomEdge ? root.height - height : verticalEdge ? 0 : 6
            cursorShape: horizontalEdge && verticalEdge ? ((modelData === (Qt.LeftEdge | Qt.TopEdge) || modelData === (Qt.RightEdge | Qt.BottomEdge)) ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor) : horizontalEdge ? Qt.SizeHorCursor : Qt.SizeVerCursor
            onPressed: floterBridge.resizeWindow(modelData)
        }
    }
}
