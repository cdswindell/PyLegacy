import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root
    objectName: "rosterMenuButton"
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    Layout.minimumHeight: 54
    leftPadding: 0
    rightPadding: 4
    font.pixelSize: 30
    font.bold: true
    Accessible.name: root.text + " menu"

    contentItem: RowLayout {
        spacing: 8
        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.maximumWidth: implicitWidth
            text: root.text
            font: root.font
            color: "#f4f6f8"
            elide: Text.ElideRight
        }
        Label {
            text: "▾"
            font.pixelSize: root.font.pixelSize
            color: "#f4f6f8"
        }
        Item { Layout.fillWidth: true }
    }

    background: Rectangle {
        radius: 8
        color: root.down ? "#246aa0" : "transparent"
        border.color: root.activeFocus ? "#78bff0" : "transparent"
    }
}
