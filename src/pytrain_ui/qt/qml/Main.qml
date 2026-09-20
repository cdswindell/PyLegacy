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
    title: "PyTrain — " + activeScope

    property bool engineCatalogVisible: showCatalogAtStartup
    property string activeScope: "ENGINE"
    property var activeAccessory: ({})
    property bool accessoryOperatingVisible: false

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: window.activeScope === "SWITCH" ? 2 :
                          window.activeScope === "ROUTE" ? 3 :
                          window.activeScope === "ACCESSORY" ? 4 :
                          window.engineCatalogVisible ? 1 : 0

            CabView {
                cab: cabController
                selection: selectedEngineController
            }

            EngineCatalog {
                cab: cabController
                catalog: engineCatalogController
                selection: selectedEngineController
                onEngineSelected: {
                    window.activeScope = "ENGINE"
                    window.engineCatalogVisible = false
                }
                onCloseRequested: window.engineCatalogVisible = false
            }

            OpsView {
                id: switchOpsView
                controller: switchOpsController
                lcsController: lcsConfigController
            }

            OpsView {
                id: routeOpsView
                controller: routeOpsController
            }

            AccessoryCatalog {
                id: accessoryCatalog
                controller: accessoryCatalogController
                lcsController: lcsConfigController
                onAccessoryRequested: function(key) {
                    window.activeAccessory = accessoryCatalogController.operatingView(key)
                    window.accessoryOperatingVisible = true
                }
                onAddRequested: {
                    // The add workflow is implemented with the accessory operating layer.
                }
                onLcsRequested: accessoryCatalog.openLcsConfiguration()
            }
        }

        SelectedEngineBar {
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 58 : 0
            visible: window.activeScope === "ENGINE" && !window.engineCatalogVisible && cabController.scope === "ENGINE"
            selection: selectedEngineController
        }

        ScopeBar {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            currentScope: window.activeScope
            onScopePressed: function(scope) {
                switchOpsView.cancelTransientPanels()
                routeOpsView.cancelTransientPanels()
                accessoryCatalog.cancelTransientPanels()
                if (scope === "SWITCH") {
                    switchOpsController.reload()
                    window.activeScope = "SWITCH"
                    window.engineCatalogVisible = false
                } else if (scope === "ROUTE") {
                    routeOpsController.reload()
                    window.activeScope = "ROUTE"
                    window.engineCatalogVisible = false
                } else if (scope === "ACCESSORY") {
                    accessoryCatalogController.reload()
                    window.activeScope = "ACCESSORY"
                    window.accessoryOperatingVisible = false
                    window.engineCatalogVisible = false
                } else if (scope === "ENGINE") {
                    if (window.activeScope === "ENGINE")
                        window.engineCatalogVisible = !window.engineCatalogVisible
                    else {
                        window.activeScope = "ENGINE"
                        window.engineCatalogVisible = false
                    }
                }
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        enabled: window.activeScope === "ENGINE" && window.engineCatalogVisible
        onActivated: window.engineCatalogVisible = false
    }
    Shortcut {
        sequence: "Up"
        enabled: window.activeScope === "ENGINE" && !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(1)
    }
    Shortcut {
        sequence: "Down"
        enabled: window.activeScope === "ENGINE" && !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(-1)
    }
    Shortcut {
        sequence: "Shift+Up"
        enabled: window.activeScope === "ENGINE" && !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(5)
    }
    Shortcut {
        sequence: "Shift+Down"
        enabled: window.activeScope === "ENGINE" && !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(-5)
    }
    Shortcut {
        sequence: "F"
        enabled: window.activeScope === "ENGINE" && !window.engineCatalogVisible
        onActivated: cabController.setDirection("FORWARD")
    }
    Shortcut {
        sequence: "R"
        enabled: window.activeScope === "ENGINE" && !window.engineCatalogVisible
        onActivated: cabController.setDirection("REVERSE")
    }
    Shortcut {
        sequence: "B"
        enabled: window.activeScope === "ENGINE" && !window.engineCatalogVisible
        onActivated: cabController.bell()
    }
    Shortcut {
        sequence: "Space"
        enabled: window.activeScope === "ENGINE" && !window.engineCatalogVisible
        onActivated: cabController.stop()
    }
}
