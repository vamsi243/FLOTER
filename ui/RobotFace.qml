import QtQuick 2.15

Item {
    id: face
    objectName: "robotFace"
    property string mood: "idle"
    property real audioLevel: 0
    property bool motionEnabled: visible && (!Window.window || Window.window.visibility !== Window.Minimized)
    property real eyeHeight: 28
    property real eyeWidth: 19
    property real gaze: 0
    property real gazeY: 0
    property int idleBeat: 0
    property string idleExpression: "idle"
    readonly property string expression: mood === "idle" ? idleExpression : mood
    property real breathing: 0
    property real smile: 7
    property real browAngle: 0
    property real headTilt: 0
    property color light: "#f4f4f4"
    property real blink: 1
    state: expression
    Accessible.role: Accessible.StaticText
    Accessible.name: "FLOTER expression: " + expression

    states: [
        State { name: "idle" },
        State { name: "sleeping"; PropertyChanges { target: face; eyeHeight: 3; eyeWidth: 25; smile: 3; headTilt: -7; gazeY: 4 } },
        State { name: "eye-roll"; PropertyChanges { target: face; eyeHeight: 15; gazeY: -12; smile: -2; browAngle: -6 } },
        State { name: "curious"; PropertyChanges { target: face; gaze: 9; gazeY: -3; eyeHeight: 30; smile: 5; headTilt: 8; browAngle: -12 } },
        State { name: "waiting"; PropertyChanges { target: face; eyeHeight: 20; smile: 4 } },
        State { name: "listening"; PropertyChanges { target: face; eyeHeight: 34; eyeWidth: 23; smile: 3 } },
        State { name: "thinking"; PropertyChanges { target: face; gaze: 7; eyeHeight: 23; smile: 0; headTilt: -5; browAngle: -10 } },
        State { name: "working"; PropertyChanges { target: face; eyeHeight: 19; smile: 2; browAngle: 9 } },
        State { name: "success"; PropertyChanges { target: face; eyeHeight: 13; eyeWidth: 24; smile: 14; headTilt: 4 } },
        State { name: "alert"; PropertyChanges { target: face; eyeHeight: 24; smile: -7; browAngle: -15 } },
        State { name: "approval"; PropertyChanges { target: face; gaze: -5; eyeHeight: 26; smile: 0; headTilt: 5; browAngle: -12 } }
    ]
    transitions: Transition {
        enabled: face.motionEnabled
        NumberAnimation { properties: "eyeHeight,eyeWidth,gaze,gazeY,smile,browAngle,headTilt"; duration: 220; easing.type: Easing.InOutQuad }
        ColorAnimation { properties: "light"; duration: 220 }
    }
    Timer {
        interval: 4800; repeat: true
        running: face.motionEnabled && (face.expression === "idle" || face.expression === "waiting")
        onTriggered: blinkAnimation.start()
    }
    SequentialAnimation {
        id: blinkAnimation
        NumberAnimation { target: face; property: "blink"; to: .1; duration: 85 }
        NumberAnimation { target: face; property: "blink"; to: 1; duration: 120 }
    }
    onMoodChanged: { blinkAnimation.stop(); blink = 1; idleBeat = 0; idleExpression = "idle" }
    Timer {
        interval: 6000; repeat: true
        running: face.motionEnabled && face.mood === "idle"
        onTriggered: {
            face.idleBeat += 1
            face.idleExpression = face.idleBeat >= 5 ? "sleeping"
                : face.idleBeat === 2 ? "eye-roll" : face.idleBeat === 4 ? "curious" : "idle"
        }
    }
    Timer {
        interval: 1600
        running: face.mood === "idle" && face.motionEnabled && (face.idleExpression === "eye-roll" || face.idleExpression === "curious")
        onTriggered: face.idleExpression = "idle"
    }
    SequentialAnimation on breathing {
        running: face.motionEnabled && face.expression === "sleeping"
        loops: Animation.Infinite
        NumberAnimation { to: 3; duration: 1800; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0; duration: 1800; easing.type: Easing.InOutSine }
    }
    onMotionEnabledChanged: { if (!motionEnabled) { blinkAnimation.stop(); blink = 1 } }

    Text {
        anchors.right: parent.right; anchors.rightMargin: 24
        anchors.top: parent.top; anchors.topMargin: 4
        text: "z Z"; color: "#f4f4f4"; font.family: "Segoe UI"; font.pixelSize: 14
        visible: face.expression === "sleeping"
        Accessible.ignored: true
    }
    Rectangle {
        id: shell
        width: Math.min(parent.width, parent.height * 1.3, 230)
        height: width / 1.3
        anchors.centerIn: parent
        radius: width * .27
        rotation: face.headTilt
        transform: Translate { y: face.expression === "sleeping" ? face.breathing : 0 }
        color: "transparent"
        Rectangle {
            anchors.fill: parent; anchors.margins: 7
            radius: shell.radius - 5
            color: "transparent"
            Item {
                width: 140; height: 100; anchors.centerIn: parent
                scale: shell.width / 172
                Repeater {
                    model: 2
                    delegate: Item {
                        required property int index
                        x: (index === 0 ? 37 : 102) + face.gaze; y: 40 + face.gazeY
                        Rectangle {
                            anchors.centerIn: parent
                            width: face.eyeWidth; height: Math.max(3, face.eyeHeight * face.blink)
                            radius: width / 2; color: face.light
                        }
                        Rectangle {
                            x: -14; y: -27; width: 28; height: 3; radius: 2
                            color: face.light; opacity: face.browAngle === 0 ? 0 : 1
                            rotation: index === 0 ? face.browAngle : -face.browAngle
                            Behavior on opacity { NumberAnimation { duration: 160 } }
                        }
                    }
                }
                Canvas {
                    id: mouth
                    x: 49; y: 64; width: 42; height: 26
                    onPaint: {
                        var ctx = getContext("2d"); ctx.reset()
                        ctx.strokeStyle = face.light; ctx.lineWidth = 3.5; ctx.lineCap = "round"
                        ctx.beginPath(); ctx.moveTo(6, 9)
                        ctx.quadraticCurveTo(21, 9 + face.smile, 36, 9); ctx.stroke()
                    }
                    Connections {
                        target: face
                        function onSmileChanged() { mouth.requestPaint() }
                        function onLightChanged() { mouth.requestPaint() }
                    }
                }
            }
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom; anchors.bottomMargin: 2
            width: face.mood === "listening" ? 12 + Math.min(1, Math.max(0, face.audioLevel)) * 35 : 12
            visible: face.mood === "listening"
            height: 3; radius: 1; color: face.light
            Behavior on width { NumberAnimation { duration: 90 } }
        }
    }
}
