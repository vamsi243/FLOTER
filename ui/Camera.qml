import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtMultimedia

Rectangle {
    width: 640; height: 480; color: "#172f64"
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 12; spacing: 10
        VideoOutput {
            objectName: "cameraVideo"
            Layout.fillWidth: true; Layout.fillHeight: true
            fillMode: VideoOutput.PreserveAspectFit
        }
        RowLayout {
            Layout.fillWidth: true
            Label {
                text: cameraControls.status; color: text.indexOf('●') === 0 ? "#f4f4f4" : "#f4f4f4"
                font.family: "Segoe UI"; font.pixelSize: 13
                wrapMode: Text.WordWrap; Layout.fillWidth: true
                Accessible.name: text
            }
            Button {
                text: "Stop / Close"; Accessible.name: "Stop capture and close camera"
                palette.buttonText: "#f4f4f4"
                background: Rectangle { color: "#172f64"; radius: 6; border.color: "#f4f4f4"; border.width: parent.activeFocus ? 2 : 1 }
                onClicked: cameraControls.stopCapture()
            }
        }
    }
}
