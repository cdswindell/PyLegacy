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

    contentItem: Item {
        readonly property int titleGap: 8

        Text {
            id: titleLabel
            width: Math.max(0, parent.width - chevron.width - parent.titleGap)
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            font: root.font
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 20
            color: "#f4f6f8"
            elide: Text.ElideRight
        }
        Text {
            id: chevron
            x: Math.min(titleLabel.paintedWidth, titleLabel.width) + parent.titleGap
            anchors.verticalCenter: titleLabel.verticalCenter
            text: "▾"
            font.pixelSize: root.font.pixelSize
            color: "#f4f6f8"
        }
    }

    background: Rectangle {
        radius: 8
        color: root.down ? "#246aa0" : "transparent"
        border.color: root.activeFocus ? "#78bff0" : "transparent"
    }
}
