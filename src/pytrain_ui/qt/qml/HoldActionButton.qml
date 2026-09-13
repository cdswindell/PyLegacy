import QtQuick
import QtQuick.Controls

Button {
    id: root

    property int repeatInterval: 250
    property bool repeatWhileHeld: false
    signal heldAction()

    implicitHeight: 64
    font.pixelSize: 20

    onPressedChanged: {
        if (pressed) {
            heldAction()
        }
    }

    Timer {
        interval: root.repeatInterval
        repeat: true
        running: root.repeatWhileHeld && root.pressed
        onTriggered: root.heldAction()
    }
}
