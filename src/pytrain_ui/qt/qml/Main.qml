import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    PanelMetrics { id: panelMetrics }
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

    property bool manageVisible: false
    property bool engineCatalogVisible: showCatalogAtStartup
    property string activeScope: "ENGINE"
    property string activeAccessoryKey: ""
    property int accessoryRevision: 0
    readonly property var activeAccessory: {
        accessoryRevision
        return activeAccessoryKey ? accessoryCatalogController.operatingView(activeAccessoryKey) : ({})
    }
    property bool accessoryOperatingVisible: false
    property bool stateInfoVisible: false
    property string stateInfoScope: "ENGINE"
    property int stateInfoId: 0
    property bool stateInfoFromRoster: false

    Connections {
        target: accessoryCatalogController
        function onChanged() { window.accessoryRevision++ }
    }

    function openStateInfo(scope, tmccId, fromRoster, deviceKind = "") {
        operatingCabView.closeDialogPanel()
        stateInfoScope = scope
        stateInfoId = tmccId
        stateInfoFromRoster = fromRoster
        stateInfoVisible = true
        stateInfoController.openFor(scope, tmccId, fromRoster, deviceKind)
    }

    function closeStateInfo() {
        stateInfoVisible = false
        stateInfoController.close()
        if (stateInfoScope === "ACC") accessoryCatalogController.reload()
    }

    function requestEditorExit(action) {
        if (discardChanges.pendingAction)
            return
        if (routeOpsView.hasUnsavedRouteChanges ||
            (stateInfoVisible && (stateInfoScope === "ACC" ? accessoryInfo.hasUnsavedChanges : operatingCabView.stateInfoHasUnsavedChanges))) {
            discardChanges.pendingAction = action
            discardChanges.open()
        } else {
            action()
        }
    }

    function changeScope(scope, showKeypad) {
        window.manageVisible = false
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
            if (showKeypad || (window.activeScope === scope && !window.engineCatalogVisible))
                window.engineCatalogVisible = true
            else
                window.engineCatalogVisible = !cabController.restoreScope(scope)
            window.activeScope = scope
        }

        if (showKeypad) {
            const roster = scope === "SWITCH" ? switchOpsView :
                           scope === "ROUTE" ? routeOpsView :
                           scope === "ACCESSORY" ? accessoryCatalog : engineCatalog
            Qt.callLater(roster.openTmccKeypad)
        }
    }

    Connections {
        target: stateInfoController
        function onRecordReady(scope, tmccId) {
            if (scope === "ACC") {
                window.closeStateInfo()
                return
            }
            if (!cabController.selectAddress(scope, tmccId))
                return
            if (scope === "ENGINE")
                selectedEngineController.selectEngine(tmccId)
            engineCatalogController.reload()
            window.engineCatalogVisible = false
            window.closeStateInfo()
        }
        function onRecordCleared(scope, tmccId) {
            if (scope === "ACC") {
                window.accessoryOperatingVisible = false
                window.closeStateInfo()
                return
            }
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
                currentIndex: window.manageVisible ? 4 : (window.stateInfoVisible && window.stateInfoScope !== "ACC") ? 0 :
                              window.activeScope === "SWITCH" ? 1 :
                              window.activeScope === "ROUTE" ? 2 :
                              window.activeScope === "ACCESSORY" ? 3 : 0

                Item {
                    EngineCatalog {
                        id: engineCatalog
                        anchors.fill: parent
                        visible: window.stateInfoVisible ? window.stateInfoFromRoster : window.engineCatalogVisible
                        enabled: !window.stateInfoVisible
                        opacity: enabled ? 1 : 0.42
                        scope: window.activeScope === "TRAIN" ? "TRAIN" : "ENGINE"
                        cab: cabController
                        catalog: engineCatalogController
                        infoController: stateInfoController
                        selection: selectedEngineController
                        onStateInfoRequested: function(scope, tmccId) {
                            window.engineCatalogVisible = true
                            window.openStateInfo(scope, tmccId, true)
                        }
                        onCabMenuRequested: cabMenu.open()
                        onEngineSelected: {
                            window.engineCatalogVisible = false
                        }
                        onVisibleChanged: if (visible && enabled) engineCatalogController.reload()
                        onCloseRequested: {
                            window.activeScope = cabController.scope
                            window.engineCatalogVisible = false
                        }
                    }

                    CabView {
                        id: operatingCabView
                        operatingEdgeInset: scopeBar.Layout.leftMargin + scopeBar.buttonInset
                        anchors.fill: parent
                        visible: window.stateInfoVisible || !window.engineCatalogVisible
                        cab: cabController
                        selection: selectedEngineController
                        infoController: stateInfoController
                        stateInfoVisible: window.stateInfoVisible
                        stateInfoFromRoster: window.stateInfoFromRoster
                        stateInfoIdentity: window.stateInfoScope + " " + window.stateInfoId
                        onStateInfoRequested: window.openStateInfo(cabController.scope, cabController.tmccId, false)
                        onStateInfoClosed: window.requestEditorExit(window.closeStateInfo)
                        onCabMenuRequested: cabMenu.open()
                    }
                }

                OpsView {
                    id: switchOpsView
                    controller: switchOpsController
                    onCabMenuRequested: cabMenu.open()
                    lcsController: lcsConfigController
                }

                OpsView {
                    id: routeOpsView
                    controller: routeOpsController
                    editorNavigationPending: !!discardChanges.pendingAction
                    onRouteCloseRequested: window.requestEditorExit(routeOpsView.discardRouteBuilder)
                    onCabMenuRequested: cabMenu.open()
                }

                Item {
                    AccessoryCatalog {
                        id: accessoryCatalog
                        anchors.fill: parent
                        visible: !window.accessoryOperatingVisible
                        enabled: !window.stateInfoVisible
                        controller: accessoryCatalogController
                        lcsConfig: accessoryLcsConfig
                        onCabMenuRequested: cabMenu.open()
                        onAccessoryRequested: function(key) {
                            window.activeAccessoryKey = key
                            window.accessoryOperatingVisible = true
                        }
                        onEditRequested: (tmccId, kind) => window.openStateInfo("ACC", tmccId, true, kind)
                        onAddRequested: window.openStateInfo("ACC", 0, true)
                        onLcsRequested: accessoryCatalog.openLcsConfiguration()
                    }

                    AccessoryOperatingView {
                        id: accessoryOperatingView
                        anchors.fill: parent
                        visible: window.accessoryOperatingVisible
                        enabled: !window.stateInfoVisible
                        controller: accessoryCatalogController
                        accessory: window.activeAccessory
                        configurationVisible: accessoryLcsConfig.visible
                        onConfigureRequested: tmccId => accessoryLcsConfig.openForModule("amc2", tmccId, "ACC")
                        onInfoRequested: tmccId => window.openStateInfo("ACC", tmccId, false, window.activeAccessory.kind || "")
                        onCabMenuRequested: cabMenu.open()
                        onCloseRequested: window.accessoryOperatingVisible = false
                    }

                    LcsConfig {
                        id: accessoryLcsConfig
                        controller: lcsConfigController
                        editorTop: window.accessoryOperatingVisible ? accessoryOperatingView.editorTop : accessoryCatalog.editorTop
                    }

                    Rectangle {
                        anchors.fill: parent
                        visible: window.stateInfoVisible && window.stateInfoScope === "ACC"
                        color: "#102858"
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Item { Layout.preferredWidth: accessoryInfoStop.width }
                                CabMenuTitle {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    compact: accessoryCatalog.compact
                                    title: {
                                        const name = (accessoryInfo.record.identity || []).find(field => field.key === "name")
                                        const roadName = name && name.value ? String(name.value) : ""
                                        const device = accessoryInfo.record.sensorTrack ? "Sensor Track" :
                                                       (accessoryInfo.record.lcsDeviceType || "")
                                        if (device)
                                            return roadName.toLowerCase().startsWith(device.toLowerCase()) ? roadName :
                                                roadName ? device + " " + roadName : device
                                        if (window.accessoryOperatingVisible && window.activeAccessory.tmccId === window.stateInfoId)
                                            return window.activeAccessory.title
                                        return roadName || "Accessory"
                                    }
                                    identity: window.stateInfoId ? "ACC " + window.stateInfoId : ""
                                    onActivated: cabMenu.open()
                                }
                                AllStopButton {
                                    id: accessoryInfoStop
                                    compact: accessoryCatalog.compact
                                    onClicked: accessoryCatalogController.halt()
                                }
                            }
                            StateInfoView {
                                id: accessoryInfo
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                controller: stateInfoController
                                onCloseRequested: window.requestEditorExit(window.closeStateInfo)
                                Timer {
                                    interval: 250
                                    repeat: true
                                    running: accessoryInfo.visible
                                    onTriggered: stateInfoController.refresh(accessoryInfo.editorOpen)
                                }
                            }
                        }
                    }
                }


                ManagePanel {
                    admin: managePyTrainController
                    cab: cabController
                    onCloseRequested: window.manageVisible = false
                    onAccessoriesRequested: accessoryCatalogController.reload()
                    onImagesRequested: {
                        cabController.refreshArtwork()
                        accessoryCatalogController.reload()
                    }
                }
            }

            SelectedEngineBar {
                Layout.topMargin: -4
                color: "#0d1f58"
                Layout.fillWidth: true
                Layout.leftMargin: -6
                Layout.rightMargin: -6
                Layout.preferredHeight: visible ? (operatingCabView.compact ? 74 : 86) : 0
                visible: !window.manageVisible && !operatingCabView.dialogPanelOpen && !window.stateInfoVisible && window.activeScope === "ENGINE" && !window.engineCatalogVisible && cabController.scope === "ENGINE"
                selection: selectedEngineController
            }

            ScopeBar {
                id: scopeBar
                color: window.engineScope ? "#102858" : "#20242a"
                Layout.fillWidth: true
                Layout.leftMargin: -6
                Layout.rightMargin: -6
                Layout.preferredHeight: 84
                Layout.minimumHeight: 84
                Layout.maximumHeight: 84
                currentScope: window.activeScope
                onScopePressed: (scope, showKeypad) =>
                    window.requestEditorExit(() => window.changeScope(scope, showKeypad))
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

    Popup {
        id: cabMenu
        objectName: "cabNavigationMenu"
        parent: previewViewport
        x: (parent.width - width) / 2
        y: 110
        width: Math.min(420, parent.width - 24)
        padding: 16
        modal: false
        focus: true
        background: Rectangle {
            color: "#102858"
            radius: 12
            border.color: "#6385af"
        }
        contentItem: ColumnLayout {
            spacing: 14
            Repeater {
                model: ["Roster", "Manage PyTrain", "Route Builder", "LCS Device Manager"]
                CabButton {
                    required property int index
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 70
                    font.pixelSize: 22
                    text: modelData
                    onClicked: {
                        cabMenu.close()
                        window.requestEditorExit(() => {
                            if (window.stateInfoVisible)
                                window.closeStateInfo()
                            if (index === 0) {
                                if (window.activeScope === "SWITCH")
                                    switchOpsView.showRoster()
                                else if (window.activeScope === "ROUTE")
                                    routeOpsView.showRoster()
                                else if (window.activeScope === "ACCESSORY") {
                                    window.accessoryOperatingVisible = false
                                    accessoryCatalog.showRoster()
                                } else
                                    window.engineCatalogVisible = true
                            } else if (index === 1) {
                                window.manageVisible = true
                            } else if (index === 2) {
                                window.activeScope = "ROUTE"
                                routeOpsController.reload()
                                Qt.callLater(routeOpsView.openAddRoute)
                            } else {
                                window.activeScope = "SWITCH"
                                switchOpsController.reload()
                                Qt.callLater(switchOpsView.openLcsConfiguration)
                            }
                        })
                    }
                }
            }
            CabButton {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 180
                Layout.preferredHeight: 70
                Layout.topMargin: panelMetrics.footerOffset(Layout.preferredHeight, parent.spacing)
                font.pixelSize: 22
                text: "Close"
                onClicked: cabMenu.close()
            }
        }
    }

    Popup {
        id: discardChanges
        objectName: "discardChangesConfirmation"
        property var pendingAction: null

        parent: Overlay.overlay
        width: Math.min(parent.width - 24, 520)
        x: (parent.width - width) / 2
        y: Math.max(0, (parent.height - height) / 2)
        padding: 16
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape
        onClosed: pendingAction = null
        background: Rectangle { color: "#102858"; radius: 12; border.color: "#7094c0" }

        contentItem: ColumnLayout {
            spacing: 12
            Label {
                Layout.fillWidth: true
                text: "Discard Changes?"
                color: "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            Label {
                Layout.fillWidth: true
                text: "You have unsaved edits."
                color: "#e2edf9"
                font.pixelSize: 18
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: panelMetrics.footerOffset(implicitHeight, parent.spacing)
                spacing: 12
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    text: "Keep Editing"
                    activateOnRelease: true
                    onClicked: discardChanges.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    text: "Discard"
                    normalColor: "#8d313d"
                    activateOnRelease: true
                    onClicked: {
                        const action = discardChanges.pendingAction
                        if (action)
                            action()
                        discardChanges.close()
                    }
                }
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        enabled: window.manageVisible
        onActivated: window.manageVisible = false
    }

    Shortcut {
        sequence: "Escape"
        enabled: window.stateInfoVisible && !(window.stateInfoScope === "ACC" ? accessoryInfo.editorOpen : operatingCabView.stateInfoEditorOpen) && !discardChanges.visible
        onActivated: window.requestEditorExit(window.closeStateInfo)
    }

    Shortcut {
        sequence: "Escape"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && window.engineCatalogVisible && cabController.tmccId > 0
        onActivated: {
            window.activeScope = cabController.scope
            window.engineCatalogVisible = false
        }
    }
    Shortcut {
        sequence: "Up"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(1)
    }
    Shortcut {
        sequence: "Down"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(-1)
    }
    Shortcut {
        sequence: "Shift+Up"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(5)
    }
    Shortcut {
        sequence: "Shift+Down"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(-5)
    }
    Shortcut {
        sequence: "F"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.setDirection("FORWARD")
    }
    Shortcut {
        sequence: "R"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.setDirection("REVERSE")
    }
    Shortcut {
        sequence: "B"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.bell()
    }
    Shortcut {
        sequence: "Space"
        enabled: !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.stop()
    }
}
