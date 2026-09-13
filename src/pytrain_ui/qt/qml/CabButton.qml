import QtQuick
import QtQuick.Controls

Button {
    id: root

    property bool selected: false
    property color normalColor: "#343a44"
    property color selectedColor: "#246aa0"
    property color pressedColor: "#4d5968"

    implicitHeight: 62
    font.pixelSize: 20
    font.bold: selected

    contentItem: Text {
        text: root.text
        font: root.font
        color: root.enabled ? "#ffffff" : "#7d8591"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 10
        color: root.pressed ? root.pressedColor : (root.selected ? root.selectedColor : root.normalColor)
        border.width: root.selected ? 2 : 1
        border.color: root.selected ? "#78bff0" : "#626b78"
    }
}
