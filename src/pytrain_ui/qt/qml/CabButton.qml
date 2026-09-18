import QtQuick
import QtQuick.Controls

Control {
    id: root

    property string text: ""
    property bool selected: false
    property bool repeatWhileHeld: false
    property int repeatInterval: 250
    property color normalColor: "#343a44"
    property color selectedColor: "#246aa0"
    property color pressedColor: "#4d5968"
    readonly property bool pressed: tapHandler.pressed

    signal clicked()
    signal doubleClicked()

    implicitHeight: 62
    font.pixelSize: 20
    font.bold: selected
    focusPolicy: Qt.StrongFocus

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

    TapHandler {
        id: tapHandler
        enabled: root.enabled
        acceptedButtons: Qt.LeftButton
        onPressedChanged: {
            if (pressed)
                root.clicked()
        }
        onDoubleTapped: root.doubleClicked()
    }

    Timer {
        interval: root.repeatInterval
        repeat: true
        running: root.enabled && root.repeatWhileHeld && root.pressed
        onTriggered: root.clicked()
    }

    Keys.onPressed: function(event) {
        if (!root.enabled || event.isAutoRepeat)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.clicked()
            event.accepted = true
        }
    }
}
