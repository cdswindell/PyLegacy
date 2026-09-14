import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    visible: true
    width: 720
    height: 1280
    minimumWidth: 480
    minimumHeight: 720
    color: "#0f1115"
    title: "PyTrain — " + cabController.scope + " " + cabController.tmccId

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        CabView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            cab: cabController

            // Mirror only CabView's top-level horizontal composition. CabView
            // explicitly restores left-to-right ordering for its internal rows.
            LayoutMirroring.enabled: true
            LayoutMirroring.childrenInherit: true
        }

        ScopeBar {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            currentScope: cabController.scope
        }
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
