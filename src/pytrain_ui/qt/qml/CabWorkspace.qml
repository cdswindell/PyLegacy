import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: window
    PanelMetrics { id: panelMetrics }
    property bool inputActive: true
    property bool deckPane: false
    property var cabController
    property var managePyTrainController
    property var stateInfoController
    property var accessoryCatalogController
    property var engineCatalogController
    property var selectedEngineController
    property var switchOpsController
    property var routeOpsController
    property var lcsConfigController
    property bool showCatalogAtStartup: false
    signal windowSizeRequested(int displayWidth, int displayHeight)
    color: engineScope ? "#09183f" : "#0f1115"
    readonly property string activePanelTitle: {
        if (manageVisible)
            return "Manage PyTrain"
        if (accessoryLcsConfig.visible)
            return "LCS Device Manager"
        if (stateInfoVisible) {
            const model = stateInfoController.model
            if (model.addingAccessory)
                return "Add Accessory"
            if (model.creating)
                return "Create Engine"
            return (model.scopeTitle || stateInfoScope) + " Information"
        }
        if (activeScope === "SWITCH")
            return switchOpsView.activePanelTitle
        if (activeScope === "ROUTE")
            return routeOpsView.activePanelTitle
        if (activeScope === "ACCESSORY")
            return accessoryOperatingVisible ? (activeAccessory.title || "Accessory Controls") : "Accessories"
        if (engineCatalogVisible)
            return activeScope === "TRAIN" ? "Trains" : "Engines"
        return (activeScope === "TRAIN" ? "Train " : "Engine ")
            + (operatingCabView.effectsVisible ? operatingCabView.effectsPageTitle : "Controls")
    }

    property bool manageVisible: false
    property bool engineCatalogVisible: showCatalogAtStartup
    property string activeScope: "ENGINE"
    property string activeAccessoryKey: ""
    property string lastOperatedAccessoryKey: ""
    property bool lastAccessoryOperationFromRoster: false

    Connections {
        target: accessoryCatalogController
        function onOperated(key, fromRoster) {
            window.lastOperatedAccessoryKey = key
            window.lastAccessoryOperationFromRoster = fromRoster
        }
    }
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
    property bool stateInfoFromTab: false

    Connections {
        target: accessoryCatalogController
        function onChanged() { window.accessoryRevision++ }
    }

    readonly property var controllerRoster: activeScope === "SWITCH" ? switchOpsView :
        activeScope === "ROUTE" ? routeOpsView : activeScope === "ACCESSORY" ? accessoryCatalog : engineCatalog
    readonly property bool controllerCatalogVisible: !manageVisible && !stateInfoVisible &&
        (engineScope ? engineCatalogVisible : activeScope === "ACCESSORY" ? !accessoryOperatingVisible : true)
    readonly property var controllerRows: {
        const rows = engineScope ? engineCatalog.filteredTargets() :
            controllerRoster ? controllerRoster.rosterRows : []
        return Array.isArray(rows) ? rows : []
    }
    readonly property var controllerRow: {
        const list = controllerRoster ? controllerRoster.inputRoster : null
        const index = list ? list.currentIndex : -1
        return index >= 0 && index < controllerRows.length ? controllerRows[index] : ({})
    }
    readonly property var controllerInputState: ({
        scope: activeScope, catalog: controllerCatalogVisible, manage: manageVisible,
        blocked: manageVisible || stateInfoVisible || cabMenu.visible || discardChanges.visible || operatingCabView.editorOpen ||
            switchOpsView.activePanelTitle !== "Switches" || routeOpsView.activePanelTitle !== "Routes",
        accessory: accessoryOperatingVisible ? activeAccessory : controllerRow,
        row: controllerRow
    })

    function controllerNavigate(delta, edge = 0) {
        const list = controllerRoster ? controllerRoster.inputRoster : null
        if (!controllerCatalogVisible || !list || !list.count)
            return
        list.currentIndex = edge < 0 ? 0 : edge > 0 ? list.count - 1 :
            Math.max(0, Math.min(list.count - 1, list.currentIndex + delta))
        list.positionViewAtIndex(list.currentIndex, ListView.Contain)
    }

    function controllerSelect() {
        const row = controllerRow
        if (!controllerCatalogVisible || !row)
            return
        if (engineScope && row.tmccId)
            engineCatalog.requestAddress(row.tmccId)
        else if (activeScope === "ACCESSORY" && row.key)
            accessoryCatalog.accessoryRequested(row.key)
        else if (activeScope === "SWITCH" && row.tmccId)
            switchOpsController.select(row.tmccId)
        else if (activeScope === "ROUTE" && row.tmccId)
            routeOpsController.select(row.tmccId)
    }

    function controllerShowRoster() {
        requestEditorExit(function() {
            closeOpenPanels()
            if (engineScope)
                engineCatalogVisible = true
        })
    }

    function controllerHideRoster() {
        if (engineScope && cabController.restoreScope(activeScope))
            engineCatalogVisible = false
        else if (activeScope === "ACCESSORY" && activeAccessoryKey) {
            accessoryOperatingVisible = true
        }
    }

    function openStateInfo(scope, tmccId, fromRoster, deviceKind = "", fromTab = false) {
        operatingCabView.closeDialogPanel()
        stateInfoScope = scope
        stateInfoId = tmccId
        stateInfoFromRoster = fromRoster
        stateInfoFromTab = fromTab
        stateInfoVisible = true
        stateInfoController.openFor(scope, tmccId, fromRoster, deviceKind)
    }

    function closeStateInfo() {
        stateInfoVisible = false
        stateInfoFromTab = false
        stateInfoController.close()
        if (stateInfoScope === "ACC") accessoryCatalogController.reload()
    }

    function requestEditorExit(action) {
        if (discardChanges.pendingAction)
            return
        if (routeOpsView.hasUnsavedRouteChanges || switchOpsView.hasUnsavedSwitchChanges ||
            switchOpsView.hasUnsavedLcsChanges || accessoryLcsConfig.hasUnsavedChanges ||
            operatingCabView.hasUnsavedControlChanges || accessoryOperatingView.hasUnsavedRelayChanges ||
            (stateInfoVisible && (stateInfoScope === "ACC" ? (stateInfoFromTab ? accessoryOperatingView.infoHasUnsavedChanges : accessoryInfo.hasUnsavedChanges) : operatingCabView.stateInfoHasUnsavedChanges))) {
            discardChanges.pendingAction = action
            discardChanges.open()
        } else {
            action()
        }
    }

    function closeOpenPanels() {
        window.manageVisible = false
        operatingCabView.cancelTransientPanels()
        engineCatalog.cancelTransientPanels()
        if (window.stateInfoVisible)
            window.closeStateInfo()
        switchOpsView.cancelTransientPanels()
        routeOpsView.cancelTransientPanels()
        accessoryCatalog.cancelTransientPanels()
        window.accessoryOperatingVisible = false
    }

    function changeScope(scope, showKeypad) {
        const sameAccessoryScope = scope === "ACCESSORY" && window.activeScope === "ACCESSORY"
        const showAccessoryRoster = sameAccessoryScope && window.accessoryOperatingVisible
        const selectedAccessoryKey = sameAccessoryScope ? window.activeAccessoryKey : ""
        closeOpenPanels()
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
            window.engineCatalogVisible = false
            const key = selectedAccessoryKey || window.lastOperatedAccessoryKey
            if (!showKeypad && key) {
                if (!accessoryCatalogController.descriptor(key).key) {
                    if (window.activeAccessoryKey === key)
                        window.activeAccessoryKey = ""
                    if (window.lastOperatedAccessoryKey === key)
                        window.lastOperatedAccessoryKey = ""
                } else if (showAccessoryRoster ||
                           (!selectedAccessoryKey && window.lastAccessoryOperationFromRoster)) {
                    Qt.callLater(accessoryCatalog.restoreRosterPosition, key)
                } else {
                    window.activeAccessoryKey = key
                    window.accessoryOperatingVisible = true
                }
            }
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

    function navigateFromMenu(destination) {
        requestEditorExit(() => {
            closeOpenPanels()
            if (destination === "Roster") {
                if (activeScope === "SWITCH")
                    switchOpsView.showRoster()
                else if (activeScope === "ROUTE")
                    routeOpsView.showRoster()
                else if (activeScope === "ACCESSORY")
                    accessoryCatalog.showRoster()
                else
                    engineCatalogVisible = true
            } else if (destination === "Manage PyTrain") {
                manageVisible = true
            } else if (destination === "Route Builder") {
                activeScope = "ROUTE"
                routeOpsController.reload()
                Qt.callLater(routeOpsView.openAddRoute)
            } else if (destination === "LCS Device Manager") {
                activeScope = "SWITCH"
                switchOpsController.reload()
                Qt.callLater(switchOpsView.openLcsConfiguration)
            }
        })
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
            const editingRecord = window.stateInfoVisible && window.stateInfoScope === scope
                && window.stateInfoId === tmccId
            if (scope === "ACC") {
                const operatingRecord = window.accessoryOperatingVisible
                    && window.activeAccessory.tmccId === tmccId
                if (operatingRecord) {
                    window.accessoryOperatingVisible = false
                    window.activeAccessoryKey = ""
                }
                if (operatingRecord || editingRecord)
                    accessoryCatalog.showRoster()
                if (!editingRecord)
                    accessoryCatalogController.reload()
            } else if (scope === "SWITCH" || scope === "ROUTE") {
                const ops = scope === "SWITCH" ? switchOpsView : routeOpsView
                if (ops.handleRecordDeletion(tmccId))
                    discardChanges.close()
            } else if (scope === "ENGINE" || scope === "TRAIN") {
                const operatingRecord = window.activeScope === scope
                    && cabController.scope === scope && cabController.tmccId === tmccId
                if (operatingRecord || editingRecord) {
                    window.engineCatalogVisible = true
                    operatingCabView.cancelTransientPanels()
                    if (!window.stateInfoVisible)
                        discardChanges.close()
                }
                cabController.forgetClearedTarget(scope, tmccId)
                if (scope === "ENGINE")
                    selectedEngineController.pruneDeleted()
                engineCatalogController.reload()
                cabController.refreshRoster()
            }
            if (editingRecord) {
                discardChanges.close()
                window.closeStateInfo()
            }
        }
    }

    property string previewProfile: ""
    property int previewWidth: 720
    property int previewHeight: 1280
    property int normalWindowWidth: 720
    property int normalWindowHeight: 1280
    readonly property bool engineScope: activeScope === "ENGINE" || activeScope === "TRAIN"
    readonly property bool previewControlsAvailable: !deckPane && Qt.platform.os === "osx"
    readonly property bool devicePreviewActive: previewControlsAvailable && engineScope && previewProfile.length > 0
    readonly property int enginePreviewFooterHeight: previewControlsAvailable ? 44 : 0
    readonly property int previewFooterHeight: engineScope ? enginePreviewFooterHeight : 0
    readonly property real previewScale: devicePreviewActive ?
        Math.min(1, width / previewWidth, Math.max(1, height - previewFooterHeight) / previewHeight) : 1

    function resizePreviewWindow() {
        const availableWidth = Math.max(480, Screen.desktopAvailableWidth - 32)
        const availableHeight = Math.max(400, Screen.desktopAvailableHeight - 64)
        const fit = Math.min(1, availableWidth / previewWidth,
                             (availableHeight - previewFooterHeight) / previewHeight)
        windowSizeRequested(Math.max(480, Math.ceil(previewWidth * fit)),
                            Math.max(400, Math.ceil(previewHeight * fit) + previewFooterHeight))
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
            windowSizeRequested(normalWindowWidth, normalWindowHeight)
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
            id: viewportLayout
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
                            if (cabController.restoreScope(engineCatalog.scope))
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
                        stateInfoFromTab: window.stateInfoFromTab
                        stateInfoIdentity: window.stateInfoScope + " " + window.stateInfoId
                        onStateInfoRequested: window.requestEditorExit(() =>
                            window.openStateInfo(cabController.scope, cabController.tmccId, false))
                        onStateInfoTabRequested: window.requestEditorExit(() =>
                            window.openStateInfo(cabController.scope, cabController.tmccId, false, "", true))
                        onControlPageRequested: index => window.requestEditorExit(() => {
                            if (window.stateInfoVisible)
                                window.closeStateInfo()
                            operatingCabView.selectControlPage(index)
                        })
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
                    editorNavigationPending: cabMenu.visible || !!discardChanges.pendingAction
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
                        enabled: !window.stateInfoVisible || window.stateInfoFromTab
                        controller: accessoryCatalogController
                        infoController: stateInfoController
                        infoSelected: window.stateInfoVisible && window.stateInfoFromTab && window.stateInfoScope === "ACC"
                        accessory: window.activeAccessory
                        controlBottomInset: {
                            const barSpacing = selectedEngineBar.Layout.topMargin + viewportLayout.spacing
                            const cabHeight = height - window.enginePreviewFooterHeight
                            const compactCab = cabHeight - panelMetrics.selectedEngineBarHeight(true) - barSpacing < 850
                            return panelMetrics.cabStateTilesBottomInset + window.enginePreviewFooterHeight
                                 + panelMetrics.selectedEngineBarHeight(compactCab) + barSpacing
                        }
                        requestNavigation: action => window.requestEditorExit(action)
                        configurationVisible: accessoryLcsConfig.visible
                        onConfigureRequested: tmccId => window.requestEditorExit(() => {
                            if (window.stateInfoVisible) window.closeStateInfo()
                            accessoryLcsConfig.openForModule(window.activeAccessory.uncoupler ? "asc2" : "amc2", tmccId, "ACC")
                        })
                        onInfoRequested: tmccId => window.requestEditorExit(() =>
                            window.openStateInfo("ACC", tmccId, false, window.activeAccessory.kind || "", true))
                        onDeviceTabRequested: index => {
                            const info = index === accessoryOperatingView.deviceInfoTabIndex
                            if (info && accessoryOperatingView.infoSelected)
                                return
                            window.requestEditorExit(() => {
                                if (info) {
                                    window.openStateInfo("ACC", window.activeAccessory.tmccId, false, window.activeAccessory.kind || "", true)
                                } else {
                                    if (window.stateInfoVisible) window.closeStateInfo()
                                    accessoryOperatingView.deviceControlTabIndex = index
                                }
                            })
                        }
                        onCabMenuRequested: cabMenu.open()
                        onCloseRequested: window.requestEditorExit(() => {
                            if (window.stateInfoVisible) window.closeStateInfo()
                            window.accessoryOperatingVisible = false
                        })
                    }

                    LcsConfig {
                        id: accessoryLcsConfig
                        controller: lcsConfigController
                        editorTop: window.accessoryOperatingVisible ? accessoryOperatingView.editorTop : accessoryCatalog.editorTop
                    }

                    Rectangle {
                        anchors.fill: parent
                        visible: window.stateInfoVisible && window.stateInfoScope === "ACC" && !window.stateInfoFromTab
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
                id: selectedEngineBar
                Layout.topMargin: -4
                color: "#0d1f58"
                Layout.fillWidth: true
                Layout.leftMargin: -6
                Layout.rightMargin: -6
                Layout.preferredHeight: visible ? panelMetrics.selectedEngineBarHeight(operatingCabView.compact) : 0
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
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 70
                    font.pixelSize: 22
                    text: modelData
                    activateOnRelease: true
                    onClicked: {
                        window.navigateFromMenu(modelData)
                        cabMenu.close()
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
                        accessoryOperatingView.discardRelayChanges()
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
        enabled: window.inputActive && window.manageVisible
        onActivated: window.manageVisible = false
    }

    Shortcut {
        sequence: "Escape"
        enabled: window.inputActive && window.stateInfoVisible && !(window.stateInfoScope === "ACC" ? (stateInfoFromTab ? accessoryOperatingView.infoEditorOpen : accessoryInfo.editorOpen) : operatingCabView.stateInfoEditorOpen) && !discardChanges.visible
        onActivated: window.requestEditorExit(window.closeStateInfo)
    }

    Shortcut {
        sequence: "Escape"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && window.engineCatalogVisible && engineCatalog.canOpenCab
        onActivated: engineCatalog.closeRequested()
    }
    Shortcut {
        sequence: "Up"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(1)
    }
    Shortcut {
        sequence: "Down"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(-1)
    }
    Shortcut {
        sequence: "Shift+Up"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(5)
    }
    Shortcut {
        sequence: "Shift+Down"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.changeSpeed(-5)
    }
    Shortcut {
        sequence: "F"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.setDirection("FORWARD")
    }
    Shortcut {
        sequence: "R"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.setDirection("REVERSE")
    }
    Shortcut {
        sequence: "B"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.bell()
    }
    Shortcut {
        sequence: "Space"
        enabled: window.inputActive && !window.manageVisible && !cabMenu.visible && !window.stateInfoVisible && (window.activeScope === "ENGINE" || window.activeScope === "TRAIN") && !window.engineCatalogVisible && !operatingCabView.editorOpen
        onActivated: cabController.stop()
    }
}
