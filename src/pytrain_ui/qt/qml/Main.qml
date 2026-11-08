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
    onClosing: Qt.quit()

    property bool engineCatalogVisible: showCatalogAtStartup
    property string activeScope: "ENGINE"
    property var activeAccessory: ({})
    property bool accessoryOperatingVisible: false
    property bool stateInfoVisible: false
    property string stateInfoScope: "ENGINE"
    property int stateInfoId: 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: window.stateInfoVisible ? 5 :
                          window.activeScope === "SWITCH" ? 2 :
                          window.activeScope === "ROUTE" ? 3 :
                          window.activeScope === "ACCESSORY" ? 4 :
                          window.engineCatalogVisible ? 1 : 0

            CabView {
                cab: cabController
                selection: selectedEngineController
            }

            EngineCatalog {
                scope: window.activeScope === "TRAIN" ? "TRAIN" : "ENGINE"
                cab: cabController
                catalog: engineCatalogController
                selection: selectedEngineController
                onStateInfoRequested: function(scope, tmccId) {
                    window.stateInfoScope = scope
                    window.stateInfoId = tmccId
                    window.stateInfoVisible = true
                    window.engineCatalogVisible = true
                }
                onEngineSelected: {
                    window.stateInfoVisible = false
                    window.engineCatalogVisible = false
                }
                onCloseRequested: {
                    window.activeScope = cabController.scope
                    window.engineCatalogVisible = false
                }
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

            Item {
                AccessoryCatalog {
                    id: accessoryCatalog
                    anchors.fill: parent
                    visible: !window.accessoryOperatingVisible
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

                AccessoryOperatingView {
                    anchors.fill: parent
                    visible: window.accessoryOperatingVisible
                    controller: accessoryCatalogController
                    accessory: window.activeAccessory
                    onCloseRequested: window.accessoryOperatingVisible = false
                }
            }

            StateInfoView {
                scope: window.stateInfoScope
                tmccId: window.stateInfoId
                onCloseRequested: window.stateInfoVisible = false
                onAllStopRequested: cabController.halt()
            }
        }

        SelectedEngineBar {
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 58 : 0
            visible: !window.stateInfoVisible && window.activeScope === "ENGINE" && !window.engineCatalogVisible && cabController.scope === "ENGINE"
            selection: selectedEngineController
        }

        ScopeBar {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            currentScope: window.activeScope
            onScopePressed: function(scope) {
                window.stateInfoVisible = false
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
                } else if (scope === "ENGINE" || scope === "TRAIN") {
                    if (window.activeScope === scope && cabController.scope === scope)
                        window.engineCatalogVisible = !window.engineCatalogVisible
                    else
                        window.engineCatalogVisible = cabController.scope !== scope
                    window.activeScope = scope
                }
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        enabled: window.stateInfoVisible
        onActivated: window.stateInfoVisible = false
    }

    Shortcut {
        sequence: "Escape"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && window.engineCatalogVisible
        onActivated: {
            window.activeScope = cabController.scope
            window.engineCatalogVisible = false
        }
    }
    Shortcut {
        sequence: "Up"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(1)
    }
    Shortcut {
        sequence: "Down"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(-1)
    }
    Shortcut {
        sequence: "Shift+Up"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(5)
    }
    Shortcut {
        sequence: "Shift+Down"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible
        onActivated: cabController.changeSpeed(-5)
    }
    Shortcut {
        sequence: "F"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible
        onActivated: cabController.setDirection("FORWARD")
    }
    Shortcut {
        sequence: "R"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible
        onActivated: cabController.setDirection("REVERSE")
    }
    Shortcut {
        sequence: "B"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible
        onActivated: cabController.bell()
    }
    Shortcut {
        sequence: "Space"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible
        onActivated: cabController.stop()
    }
}
