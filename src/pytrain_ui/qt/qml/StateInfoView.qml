import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property string scope
    required property int tmccId
    signal closeRequested()
    signal allStopRequested()

    color: "#15191f"
    radius: 10

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            CabButton {
                Layout.preferredWidth: 96
                Layout.preferredHeight: 46
                text: "Back"
                onClicked: root.closeRequested()
            }
            Label {
                Layout.fillWidth: true
                text: "StateInfo"
                color: "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            CabButton {
                Layout.preferredWidth: 130
                Layout.preferredHeight: 46
                text: "ALL STOP"
                font.pixelSize: 17
                font.bold: true
                normalColor: "#8b2d32"
                pressedColor: "#b43b42"
                onClicked: root.allStopRequested()
            }
        }
        Label {
            Layout.fillWidth: true
            text: (root.scope === "TRAIN" ? "Train " : "Engine ") + root.tmccId
            color: "#f4f6f8"
            font.pixelSize: 28
            font.bold: true
        }
        Label {
            Layout.fillWidth: true
            text: "This " + (root.scope === "TRAIN" ? "train" : "engine") + " is not in the current roster."
            color: "#aeb7c2"
            wrapMode: Text.WordWrap
            font.pixelSize: 18
        }
        Label {
            Layout.fillWidth: true
            text: "StateInfo is not implemented yet."
            color: "#aeb7c2"
            wrapMode: Text.WordWrap
            font.pixelSize: 16
        }
        Item { Layout.fillHeight: true }
    }
}
