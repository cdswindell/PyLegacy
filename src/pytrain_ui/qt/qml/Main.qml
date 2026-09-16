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

    property bool engineCatalogVisible: false

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: window.engineCatalogVisible ? 1 : 0

            CabView {
                cab: cabController
                selection: selectedEngineController
            }

            EngineCatalog {
                cab: cabController
                catalog: engineCatalogController
                selection: selectedEngineController
                onEngineSelected: window.engineCatalogVisible = false
                onCloseRequested: window.engineCatalogVisible = false
            }
        }

        SelectedEngineBar {
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 58 : 0
            visible: !window.engineCatalogVisible && cabController.scope === "ENGINE"
            selection: selectedEngineController
        }

        ScopeBar {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            currentScope: cabController.scope
            onScopePressed: function(scope) {
                if (scope === "ENGINE" && cabController.scope === "ENGINE")
                    window.engineCatalogVisible = !window.engineCatalogVisible
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        enabled: window.engineCatalogVisible
        onActivated: window.engineCatalogVisible = false
    }
    Shortcut {
        sequence: "Up"
        enabled: !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(1)
    }
    Shortcut {
        sequence: "Down"
        enabled: !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(-1)
    }
    Shortcut {
        sequence: "Shift+Up"
        enabled: !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(5)
    }
    Shortcut {
        sequence: "Shift+Down"
        enabled: !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(-5)
    }
    Shortcut {
        sequence: "F"
        enabled: !window.engineCatalogVisible
        onActivated: cabController.setDirection("FORWARD")
    }
    Shortcut {
        sequence: "R"
        enabled: !window.engineCatalogVisible
        onActivated: cabController.setDirection("REVERSE")
    }
    Shortcut {
        sequence: "B"
        enabled: !window.engineCatalogVisible
        onActivated: cabController.bell()
    }
    Shortcut {
        sequence: "Space"
        enabled: !window.engineCatalogVisible
        onActivated: cabController.stop()
    }
}
