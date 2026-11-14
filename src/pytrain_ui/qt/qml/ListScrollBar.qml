import QtQuick
import QtQuick.Controls

ScrollBar {
    id: root

    readonly property int gutterWidth: visible ? width + 6 : 0
    policy: size < 1 ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
    width: 10
    padding: 1
    minimumSize: 0.08

    background: Rectangle {
        radius: width / 2
        color: "#18232e"
    }

    contentItem: Rectangle {
        implicitWidth: 8
        radius: width / 2
        color: root.pressed ? "#78c9ff" : "#87a9c2"
    }
}
