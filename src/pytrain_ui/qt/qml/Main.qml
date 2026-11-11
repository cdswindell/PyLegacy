import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    visibility: startFullscreen ? Window.FullScreen : Window.Windowed
    width: 720
    height: 1280
    minimumWidth: 480
    minimumHeight: devicePreviewActive ? 400 : 720
    color: engineScope ? "#09183f" : "#0f1115"
    palette.window: "#102858"
    palette.windowText: "#f4f6f8"
    palette.base: "#0a2045"
    palette.text: "#f4f6f8"
    palette.placeholderText: "#acbfd8"
    palette.button: "#344862"
    palette.buttonText: "#ffffff"
    palette.highlight: "#246aa0"
    palette.highlightedText: "#ffffff"
    title: "PyTrain — " + activeScope
    onClosing: Qt.quit()

    property bool engineCatalogVisible: showCatalogAtStartup
    property string activeScope: "ENGINE"
    property var activeAccessory: ({})
    property bool accessoryOperatingVisible: false
    property bool stateInfoVisible: false
    property string stateInfoScope: "ENGINE"
    property int stateInfoId: 0
    property bool stateInfoFromRoster: false

    function openStateInfo(scope, tmccId, fromRoster) {
        operatingCabView.closeDialogPanel()
        stateInfoScope = scope
        stateInfoId = tmccId
        stateInfoFromRoster = fromRoster
        stateInfoVisible = true
        stateInfoController.openFor(scope, tmccId, fromRoster)
    }

    function closeStateInfo() {
        stateInfoVisible = false
        stateInfoController.close()
    }

    Connections {
        target: stateInfoController
        function onRecordReady(scope, tmccId) {
            if (!cabController.selectAddress(scope, tmccId))
                return
            if (scope === "ENGINE")
                selectedEngineController.selectEngine(tmccId)
            engineCatalogController.reload()
            window.engineCatalogVisible = false
            window.closeStateInfo()
        }
        function onRecordCleared(scope, tmccId) {
            window.engineCatalogVisible = true
            window.closeStateInfo()
            cabController.forgetClearedTarget(scope, tmccId)
            selectedEngineController.pruneDeleted()
            engineCatalogController.reload()
            cabController.refreshRoster()
        }
    }

    property string previewProfile: ""
    property int previewWidth: 720
    property int previewHeight: 1280
    property int normalWindowWidth: 720
    property int normalWindowHeight: 1280
    readonly property bool engineScope: activeScope === "ENGINE" || activeScope === "TRAIN"
    readonly property bool previewControlsAvailable: Qt.platform.os === "osx"
    readonly property bool devicePreviewActive: previewControlsAvailable && engineScope && previewProfile.length > 0
    readonly property int previewFooterHeight: previewControlsAvailable && engineScope ? 44 : 0
    readonly property real previewScale: devicePreviewActive ?
        Math.min(1, width / previewWidth, Math.max(1, height - previewFooterHeight) / previewHeight) : 1

    function resizePreviewWindow() {
        const availableWidth = Math.max(480, Screen.desktopAvailableWidth - 32)
        const availableHeight = Math.max(400, Screen.desktopAvailableHeight - 64)
        const fit = Math.min(1, availableWidth / previewWidth,
                             (availableHeight - previewFooterHeight) / previewHeight)
        window.width = Math.max(window.minimumWidth, Math.ceil(previewWidth * fit))
        window.height = Math.max(window.minimumHeight, Math.ceil(previewHeight * fit) + previewFooterHeight)
    }

    function selectDevicePreview(key, displayWidth, displayHeight) {
        if (previewProfile.length === 0) {
            normalWindowWidth = window.width
            normalWindowHeight = window.height
        }
        previewWidth = displayWidth
        previewHeight = displayHeight
        previewProfile = key
        resizePreviewWindow()
    }

    onEngineScopeChanged: {
        if (previewProfile.length === 0)
            return
        if (engineScope)
            resizePreviewWindow()
        else {
            window.width = normalWindowWidth
            window.height = normalWindowHeight
        }
    }

    Item {
        id: previewViewport
        anchors.top: parent.top
        x: Math.max(0, (window.width - width * scale) / 2)
        width: window.devicePreviewActive ? window.previewWidth : window.width
        height: window.devicePreviewActive ? window.previewHeight : window.height - window.previewFooterHeight
        scale: window.previewScale
        transformOrigin: Item.TopLeft
        clip: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: window.stateInfoVisible ? 0 :
                              window.activeScope === "SWITCH" ? 2 :
                              window.activeScope === "ROUTE" ? 3 :
                              window.activeScope === "ACCESSORY" ? 4 :
                              window.engineCatalogVisible ? 1 : 0

                CabView {
                    id: operatingCabView
                    cab: cabController
                    selection: selectedEngineController
                    infoController: stateInfoController
                    stateInfoVisible: window.stateInfoVisible
                    stateInfoFromRoster: window.stateInfoFromRoster
                    stateInfoIdentity: window.stateInfoScope + " " + window.stateInfoId
                    onStateInfoRequested: window.openStateInfo(cabController.scope, cabController.tmccId, false)
                    onStateInfoClosed: window.closeStateInfo()
                }

                EngineCatalog {
                    scope: window.activeScope === "TRAIN" ? "TRAIN" : "ENGINE"
                    cab: cabController
                    catalog: engineCatalogController
                    infoController: stateInfoController
                    selection: selectedEngineController
                    onStateInfoRequested: function(scope, tmccId) {
                        window.engineCatalogVisible = true
                        window.openStateInfo(scope, tmccId, true)
                    }
                    onEngineSelected: {
                        window.engineCatalogVisible = false
                    }
                    onVisibleChanged: if (visible) engineCatalogController.reload()
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


            }

            SelectedEngineBar {
                Layout.topMargin: -4
                color: "#0d1f58"
                Layout.fillWidth: true
                Layout.preferredHeight: visible ? (operatingCabView.compact ? 74 : 86) : 0
                visible: !operatingCabView.dialogPanelOpen && !window.stateInfoVisible && window.activeScope === "ENGINE" && !window.engineCatalogVisible && cabController.scope === "ENGINE"
                selection: selectedEngineController
            }

            ScopeBar {
                color: window.engineScope ? "#102858" : "#20242a"
                Layout.fillWidth: true
                Layout.preferredHeight: 84
                Layout.minimumHeight: 84
                Layout.maximumHeight: 84
                currentScope: window.activeScope
                onScopePressed: function(scope) {
                    operatingCabView.closeBellHornOptions()
                    operatingCabView.closeDialogPanel()
                    if (window.stateInfoVisible)
                        window.closeStateInfo()
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
                            window.engineCatalogVisible = cabController.tmccId <= 0 || !window.engineCatalogVisible
                        else
                            window.engineCatalogVisible = cabController.tmccId <= 0 || cabController.scope !== scope
                        window.activeScope = scope
                    }
                }
            }
        }
    }

    DevicePreviewBar {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        anchors.bottomMargin: 6
        height: 32
        visible: window.previewControlsAvailable && window.engineScope
        profile: window.previewProfile
        resolutionText: window.devicePreviewActive ?
            window.previewWidth + " × " + window.previewHeight +
            (window.previewScale < 0.995 ? " · " + Math.round(window.previewScale * 100) + "%" : "") : "Current size"
        onProfileSelected: function(key, displayWidth, displayHeight) {
            window.selectDevicePreview(key, displayWidth, displayHeight)
        }
    }

    Shortcut {
        sequence: "Escape"
        enabled: window.stateInfoVisible && !operatingCabView.stateInfoEditorOpen
        onActivated: window.closeStateInfo()
    }

    Shortcut {
        sequence: "Escape"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && window.engineCatalogVisible && cabController.tmccId > 0
        onActivated: {
            window.activeScope = cabController.scope
            window.engineCatalogVisible = false
        }
    }
    Shortcut {
        sequence: "Up"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(1)
    }
    Shortcut {
        sequence: "Down"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(-1)
    }
    Shortcut {
        sequence: "Shift+Up"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(5)
    }
    Shortcut {
        sequence: "Shift+Down"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(-5)
    }
    Shortcut {
        sequence: "F"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.setDirection("FORWARD")
    }
    Shortcut {
        sequence: "R"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.setDirection("REVERSE")
    }
    Shortcut {
        sequence: "B"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.bell()
    }
    Shortcut {
        sequence: "Space"
        enabled: !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.stop()
    }
}
