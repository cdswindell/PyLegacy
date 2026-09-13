import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window
    visible: true
    width: 800
    height: 1280
    minimumWidth: 520
    minimumHeight: 760
    color: "#0f1115"
    title: "PyTrain — " + cabController.scope + " " + cabController.tmccId

    CabView {
        anchors.fill: parent
        anchors.margins: 12
        cab: cabController
    }

    Shortcut { sequence: "Up"; onActivated: cabController.changeSpeed(1) }
    Shortcut { sequence: "Down"; onActivated: cabController.changeSpeed(-1) }
    Shortcut { sequence: "Shift+Up"; onActivated: cabController.changeSpeed(5) }
    Shortcut { sequence: "Shift+Down"; onActivated: cabController.changeSpeed(-5) }
    Shortcut { sequence: "F"; onActivated: cabController.setDirection("FORWARD") }
    Shortcut { sequence: "R"; onActivated: cabController.setDirection("REVERSE") }
    Shortcut { sequence: "B"; onActivated: cabController.bell() }
    Shortcut { sequence: "Space"; onActivated: cabController.stop() }
}
