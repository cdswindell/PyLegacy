import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: root
    property string profile: ""
    property string resolutionText: "Current size"
    signal profileSelected(string key, int displayWidth, int displayHeight)
    spacing: 6

    Label {
        text: "Preview"
        visible: root.width >= 600
        color: "#aeb7c2"
        font.pixelSize: 12
    }
    Repeater {
        model: [
            {key: "pi", label: "Raspberry Pi", width: 720, height: 1280},
            {key: "pycab", label: "PyCab", width: 800, height: 1280},
            {key: "deck", label: "Steam Deck", width: 639, height: 800}
        ]
        Button {
            id: choice
            required property var modelData
            Layout.fillWidth: true
            Layout.preferredWidth: 0
            Layout.minimumWidth: 0
            Layout.fillHeight: true
            text: modelData.label
            checkable: true
            checked: root.profile === modelData.key
            font.pixelSize: root.width < 600 ? 11 : 12
            onClicked: root.profileSelected(modelData.key, modelData.width, modelData.height)
            contentItem: Text {
                text: choice.text
                font: choice.font
                color: "#f4f6f8"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
            background: Rectangle {
                radius: 6
                color: choice.down ? "#4d5968" : choice.checked ? "#246aa0" : "#303640"
                border.width: choice.checked ? 2 : 1
                border.color: choice.checked ? "#78bff0" : "#626b78"
            }
        }
    }
    Label {
        text: root.resolutionText
        color: "#aeb7c2"
        font.pixelSize: root.width < 600 ? 10 : 11
    }
}
