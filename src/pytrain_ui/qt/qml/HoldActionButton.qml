import QtQuick
import QtQuick.Controls

Button {
    id: root

    property int repeatInterval: 250
    property bool repeatWhileHeld: false
    signal heldAction()

    implicitHeight: 64
    font.pixelSize: 20

    contentItem: Text {
        text: root.text
        font: root.font
        color: "#ffffff"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: 10
        color: root.pressed ? "#246aa0" : "#343a44"
        border.width: root.pressed ? 2 : 1
        border.color: root.pressed ? "#78bff0" : "#626b78"
    }

    onPressedChanged: {
        if (pressed)
            heldAction()
    }

    Timer {
        // ControllerView uses 300 ms for Boost/Brake. Keep explicit callers for
        // other controls (for example the 100 ms horn cadence) unchanged.
        interval: (root.text === "Brake" || root.text === "Boost") ? 300 : root.repeatInterval
        repeat: true
        running: root.repeatWhileHeld && root.pressed
        onTriggered: root.heldAction()
    }
}
