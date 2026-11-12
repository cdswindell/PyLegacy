import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var cab
    required property var selection
    property var infoController: null
    property bool stateInfoVisible: false
    property bool stateInfoFromRoster: false
    property string stateInfoIdentity: ""
    readonly property bool stateInfoEditorOpen: stateInfo.editorOpen
    readonly property bool stateInfoHasUnsavedChanges: stateInfo.hasUnsavedChanges
    signal cabMenuRequested()
    signal stateInfoRequested()
    signal stateInfoClosed()
    property bool effectsVisible: false
    property string selectedAnalogMode: "Horn"
    readonly property bool dialogPanelOpen: dialogPanel.visible
    readonly property bool editorOpen: speedLimitDialog.visible || stateValueDialog.visible || bellHornPanel.visible || dialogPanelOpen
    property string requestedDirection: ""
    readonly property string reportedDirection: cab.direction
    readonly property string targetKey: cab.scope + ":" + cab.tmccId
    readonly property string displayedDirection: requestedDirection || reportedDirection

    // A button reflects the operator's request immediately. Delayed snapshots
    // with the old direction must not undo it; fresh direction feedback wins.
    onReportedDirectionChanged: requestedDirection = ""
    onTargetKeyChanged: {
        requestedDirection = ""
        selectedAnalogMode = "Horn"
        Qt.callLater(root.syncAnalogMode)
        if (actionScroll && actionScroll.contentItem) {
            actionScroll.contentItem.cancelFlick()
            actionScroll.contentItem.contentY = actionScroll.contentItem.originY
        }
        if (speedLimitDialog)
            speedLimitDialog.close()
        if (stateValueDialog)
            stateValueDialog.close()
        if (bellHornPanel)
            bellHornPanel.close()
        if (dialogPanel)
            dialogPanel.close()
    }

    function analogModeLabel(mode) {
        return mode === "Horn" && cab.isSteam ? "Whistle" : mode
    }

    function syncAnalogMode() {
        const modes = cab.analogModes
        const preferred = modes.indexOf(selectedAnalogMode)
        const horn = modes.indexOf("Horn")
        analogMode.currentIndex = preferred >= 0 ? preferred : horn >= 0 ? horn : modes.length ? 0 : -1
    }

    function editSpeedLimit() {
        if (cab.supportsSpeedLimit)
            speedLimitDialog.openFor(cab.speedLimit, cab.commandSpeedMax, cab.scope + " " + cab.tmccId,
                                     cab.speedLimitMax)
    }

    function editState(label) {
        if (label === "Speed Lim") {
            editSpeedLimit()
            return
        }
        stateValueDialog.openFor(label, cab.isLegacy, cab.stateEditValues[label], cab.scope + " " + cab.tmccId,
                                 label === "Mom" ? cab.mediumMomentum() : 3)
    }

    function requestDirection(direction) {
        cab.setDirection(direction)
        requestedDirection = reportedDirection.indexOf(direction) >= 0 ? "" : direction
    }

    Connections {
        target: root.cab
        function onStateChanged() {
            if (root.requestedDirection && root.reportedDirection.indexOf(root.requestedDirection) >= 0)
                root.requestedDirection = ""
        }
    }
    readonly property bool passengerCar: cab.isStandalonePassenger
    readonly property bool freightCar: cab.isStandaloneFreight
    readonly property bool standaloneCar: passengerCar || freightCar
    readonly property bool speedPresetsEnabled: cab.hasThrottle && !standaloneCar && !cab.isCrane && !cab.isCab1
    readonly property string analogControlMode: cab.analogModes.length === 1 ? cab.analogModes[0] : analogMode.currentText
    readonly property bool compact: height < 850
    readonly property int gap: compact ? 6 : 8
    readonly property int preferredTileHeight: compact ? 72 : 112
    readonly property int tileHeight: {
        const heightForSixRows = operatingColumns.height - artwork.y - artwork.height - 6 * gap
        return Math.max(compact ? 52 : 96, Math.min(preferredTileHeight, Math.floor(heightForSixRows / 6)))
    }
    readonly property int sliderButtonHeight: compact ? 52 : 60

    function handleModelHold(action) {
        if (action.holdKind === "panel") {
            if (action.holdTarget === "bell_horn")
                bellHornPanel.openOptions()
            else if (["crew", "tower", "lights", "conductor", "station", "steward"].includes(action.holdTarget))
                dialogPanel.openFor(action.holdTarget)
            else
                commandPanel.openFor(action.holdTarget)
        } else if (action.holdKind === "analog") {
            const index = analogMode.find(action.holdTarget)
            if (index >= 0) {
                selectedAnalogMode = action.holdTarget
                analogMode.currentIndex = index
            }
        } else {
            cab.triggerHoldAction(action.key)
        }
    }

    function pairedActionRows(actions) {
        const aliases = {
            bell: "signals", horn: "signals",
            brake: "brake_boost", boost: "brake_boost",
            rear_coupler: "couplers", front_coupler: "couplers",
            engineer_chatter: "crew_tower", tower_chatter: "crew_tower",
            conductor: "passenger_announcements", station: "passenger_announcements",
            startup: "power", shutdown: "power",
            acela_startup: "acela_power", acela_shutdown: "acela_power",
            freight_load: "freight_loading", freight_unload: "freight_loading",
            transformer_front_coupler: "transformer_couplers", transformer_rear_coupler: "transformer_couplers"
        }
        const rows = []
        for (const action of actions) {
            const paired = action.key.match(/^(.*)_(up|down|on|off)$/)
            const key = aliases[action.key] || (paired ? "pair:" + paired[1] : "single:" + action.key)
            let row = rows.find(function(item) { return item.key === key })
            if (!row) {
                row = {key: key, actions: []}
                rows.push(row)
            }
            row.actions.push(action)
        }
        return rows.map(function(row) { return row.actions })
    }

    function isDriveUtility(key) {
        return ["startup", "shutdown", "acela_startup", "acela_shutdown", "transformer_on", "transformer_off", "volume_down", "volume_up", "smoke_down", "smoke_up"].indexOf(key) >= 0
    }

    function isEngineSpecificControl(key) {
        return (cab.isDiesel && (key === "rpm_up" || key === "rpm_down"))
            || (cab.isSteam && (key === "let_off" || key === "water_injector"))
            || ["transformer_rear_coupler", "transformer_front_coupler", "freight_tower"].includes(key)
            || (cab.isElectric && ["pantograph_front_up", "pantograph_front_down",
                "pantograph_rear_up", "pantograph_rear_down", "electric_smoke_up", "electric_smoke_down"].includes(key))
    }

    function passengerAuxActions() {
        const actions = cab.secondaryActionModel
        return ["car_aux1", "car_aux2", "car_aux3"].map((key, index) => {
            const action = actions.find(item => item.key === key)
            return action ? Object.assign({}, action, {label: "Aux " + (index + 1), repeat: false}) : undefined
        }).filter(action => action !== undefined)
    }

    function carActionRows() {
        const actions = cab.primaryActionModel.concat(cab.actionModel)
        const byKey = {}
        for (const action of actions)
            byKey[action.key] = action
        const labels = {
            option_one_on: "Clack On", option_one_off: "Clack Off",
            option_two_on: "Grind On", option_two_off: "Grind Off"
        }
        const rows = root.freightCar ? [
            ["startup", "shutdown", "freight_load"],
            ["option_one_on", "option_one_off", "freight_unload"],
            ["option_two_on", "option_two_off", "flat_wheel"],
            ["freight_lights_on", "freight_lights_off", "bell"],
            ["front_coupler", "rear_coupler", "freight_special"]
        ] : [
            ["startup", "shutdown", "next_stop"],
            ["option_one_on", "option_one_off", "conductor"],
            ["option_two_on", "option_two_off", "steward"],
            ["car_lights_on", "car_lights_off", "station"],
            ["front_coupler", "rear_coupler"]
        ]
        return rows.map(row => row.map(key => {
            const action = byKey[key]
            if (action && labels[key])
                return Object.assign({}, action, {label: labels[key]})
            return action
        }))
    }

    function driveActionRows() {
        if (root.standaloneCar)
            return root.carActionRows()

        if (cab.isCrane) {
            const byKey = {}
            for (const action of cab.primaryActionModel.concat(cab.actionModel))
                byKey[action.key] = action
            return [
                [byKey.startup, byKey.shutdown, byKey.crane_outriggers],
                [byKey.crane_boom, byKey.crane_main_hook, byKey.crane_aux_hook],
                [byKey.bell, byKey.horn, byKey.crane_radio],
                [byKey.crane_rear_lamp, byKey.crane_front_lamp, byKey.boost],
                [byKey.rear_coupler, byKey.front_coupler, byKey.brake]
            ]
        }

        const actions = cab.primaryActionModel.concat(cab.quickActionModel,
            cab.moreActionModel.filter(action => root.isDriveUtility(action.key) || root.isEngineSpecificControl(action.key)))
        const byKey = {}
        const placed = {}
        for (const action of actions)
            byKey[action.key] = action
        if (cab.isElectric && !cab.isLegacy) {
            for (const action of cab.speedSoundActionModel)
                byKey[action.key] = action
        }
        const topControl = cab.isSteam ? byKey.let_off : cab.isDiesel ? byKey.rpm_up : byKey.volume_up
        const secondControl = cab.isSteam ? byKey.water_injector : cab.isDiesel ? byKey.rpm_down : byKey.volume_down
        const startup = byKey.startup || byKey.acela_startup || byKey.transformer_on
        const shutdown = byKey.shutdown || byKey.acela_shutdown || byKey.transformer_off
        const rows = cab.isElectric ? [
            [startup, shutdown, byKey.horn],
            [cab.isLegacy ? byKey.pantograph_front_up : byKey.volume_up,
             cab.isLegacy ? byKey.pantograph_rear_up : byKey.electric_rpm_up, byKey.bell]
        ] : [
            [startup, shutdown, topControl],
            [byKey.bell, byKey.horn, secondControl]
        ]
        rows.push(
            [byKey.engineer_chatter, byKey.tower_chatter || byKey.freight_tower],
            cab.isElectric
                ? [cab.isLegacy ? byKey.pantograph_front_down : byKey.volume_down,
                   cab.isLegacy ? byKey.pantograph_rear_down : byKey.electric_rpm_down, byKey.boost]
                : [byKey.smoke_down, byKey.smoke_up, byKey.boost],
            [byKey.rear_coupler || byKey.transformer_rear_coupler,
             byKey.front_coupler || byKey.transformer_front_coupler, byKey.brake]
        )
        for (const row of rows) {
            for (const action of row) {
                if (action)
                    placed[action.key] = true
            }
        }
        // Other equipment keeps its applicable controls after the standard rows.
        return rows.concat(root.pairedActionRows(actions.filter(function(action) { return !placed[action.key] && action.key !== "volume_up" && action.key !== "volume_down"
            && !["electric_smoke_down", "electric_smoke_up"].includes(action.key) })))
    }

    function speedActionRows() {
        const presets = ["Restricted", "Slow", "Medium", "Limited", "Normal", "Highball"].map((label, index) => ({
            key: label.toUpperCase(),
            label: label,
            speedPreset: true,
            hold: true,
            speedChevrons: index + 1
        }))
        const byKey = {}
        for (const action of cab.speedSoundActionModel.concat(cab.moreActionModel))
            byKey[action.key] = action
        const carControlKeys = root.freightCar
            ? [].concat(...root.carActionRows()).filter(action => action).map(action => action.key)
            : []
        const otherActions = root.passengerCar ? [] : cab.moreActionModel.filter(action =>
            !carControlKeys.includes(action.key) &&
            !root.isDriveUtility(action.key)
                && !root.isEngineSpecificControl(action.key)
                && !action.key.startsWith("momentum_")
                && action.key !== "labor_up" && action.key !== "labor_down")
        const stopAndRoll = [
            {key: "STOP_HOLD", label: "Normal", speedPreset: true, hold: true},
            {
                key: "ROLL",
                label: "Roll",
                speedPreset: true,
                iconSource: Qt.resolvedUrl("../../../pytrain/gui/images/engine_gui/roll-speed.jpg")
            },
            {key: "EMERGENCY_STOP", label: "Emergency", speedPreset: true}
        ]
        const canLoadWater = !cab.isCab1 && !cab.isCrane && cab.isLegacy && cab.isSteam
        const canRefuel = !cab.isCab1 && !cab.isCrane && cab.isLegacy && (cab.isDiesel || cab.isSteam)
        const gaugesAndSet = [
            cab.isElectric ? byKey.electric_smoke_down
                : {key: "fuel", label: cab.isSteam ? "Coal" : "Fuel", gauge: "FUEL", hold: canRefuel, disabled: !canRefuel},
            byKey.set_address,
            cab.isElectric ? byKey.electric_smoke_up
                : {key: "water", label: "Water", gauge: "WATER", hold: canLoadWater, disabled: !canLoadWater}
        ]
        if (cab.isCrane) {
            return [
                presets.slice(0, 3), presets.slice(3), stopAndRoll, gaugesAndSet,
                [byKey.volume_up, undefined, byKey.crane_sound_on],
                [byKey.volume_down, undefined, byKey.crane_sound_off]
            ]
        }
        const volumeUpThird = root.passengerCar && byKey.sound_on
            ? Object.assign({}, byKey.sound_on, {label: "Unmute"})
            : byKey.labor_up || byKey.electric_effort_up
        const volumeDownThird = root.passengerCar && byKey.sound_off
            ? Object.assign({}, byKey.sound_off, {label: "Mute"})
            : byKey.labor_down || byKey.electric_effort_down
        const rows = [
            presets.slice(0, 3), presets.slice(3), stopAndRoll, gaugesAndSet,
            [byKey.master_volume_up, byKey.blend_up, volumeUpThird],
            [byKey.master_volume_down, byKey.blend_down, volumeDownThird]
        ]
        return rows.concat(root.pairedActionRows(otherActions))
    }

    component PairedActions: ColumnLayout {
        property var actions: []
        property var rows: root.pairedActionRows(actions)
        Layout.fillWidth: true
        spacing: root.gap
        Repeater {
            model: rows
            RowLayout {
                id: pairedRow
                required property var modelData
                Layout.fillWidth: true
                spacing: root.gap
                Repeater {
                    model: 3
                    Loader {
                        id: actionCell
                        required property int index
                        readonly property var cellAction: pairedRow.modelData[index]
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.minimumHeight: root.tileHeight
                        Layout.maximumHeight: root.tileHeight
                        Layout.preferredHeight: root.tileHeight
                        active: cellAction !== undefined && cellAction !== null
                        sourceComponent: ActionTile { action: actionCell.cellAction }
                    }
                }
            }
        }
    }

    component ActionTile: FunctionButton {
        required property var action
        readonly property bool emergencyStop: action.key === "EMERGENCY_STOP"
        readonly property bool auxiliary: action.group === "secondary"
        objectName: auxiliary ? "auxControl_" + action.key : ""
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0
        Layout.preferredHeight: root.tileHeight
        stacked: true
        wrapLabel: !fitLabelWidth
        fitLabelWidth: action.key.endsWith("_coupler")
        padding: root.compact ? 4 : 6
        iconSize: (root.compact ? 40 : 72) - (root.preferredTileHeight - root.tileHeight)
        compact: auxiliary
        text: showGauge ? action.label + " " + (gaugeLevel >= 0 ? gaugeLevel + "%" : "—")
              : auxiliary ? action.label.replace(" · ", "\n") : action.label
        labelChevron: text === "< Smoke" ? -1 : text === "Smoke >" ? 1 : 0
        displayLabel: showGauge ? (gaugeLevel >= 0 ? gaugeLevel + "%" : "—") : labelChevron ? "Smoke" : text
        gaugeLabel: action.gauge ? action.label : ""
        gaugeLevel: action.disabled ? -1
                    : action.gauge === "FUEL" ? cab.fuelLevel : action.gauge === "WATER" ? cab.waterLevel : -1
        holdHint: auxiliary && action.holdTarget === "lights" ? "Lighting panel" :
                  auxiliary && action.key === "sequence" ? "Repeat sequence" : ""
        iconSource: action.iconSource || ""
        speedChevrons: action.speedChevrons || 0
        stopSign: emergencyStop || action.key === "STOP_HOLD"
        Accessible.name: stopSign ? text + " Stop" : text
        enabled: !action.disabled && (!action.speedPreset || root.speedPresetsEnabled)
        textColor: emergencyStop ? "#ff9499" : "#f5f7fa"
        font.bold: emergencyStop
        pressedColor: emergencyStop ? "#ab1c29" : "#5c9fc6"
        font.pixelSize: root.compact ? 14 : 18
        deferForHold: action.hold || false
        holdThreshold: action.holdThreshold || 1000
        repeatWhileHeld: action.repeat || false
        repeatInterval: action.repeatInterval > 0 ? action.repeatInterval : 250
        onClicked: {
            if (action.speedPreset)
                root.cab.setSpeedPreset(action.key, false)
            else if (showGauge)
                root.cab.playDialog("ENGINEER_" + action.gauge + "_LEVEL")
            else
                root.cab.triggerAction(action.key)
        }
        onHeld: {
            if (action.speedPreset)
                root.cab.setSpeedPreset(action.key, true)
            else if (showGauge)
                root.cab.playDialog("ENGINEER_" + action.gauge + "_REFILLED")
            else
                root.handleModelHold(action)
        }
    }

    FontLoader {
        id: speedFont
        source: "../../../pytrain/gui/fonts/digital-dream/DIGITALDREAM.ttf"
    }

    color: "#0d1f58"
    gradient: Gradient {
        GradientStop { position: 0; color: "#173775" }
        GradientStop { position: 0.5; color: "#0d1f58" }
        GradientStop { position: 1; color: "#09183f" }
    }
    radius: 14

    ColumnLayout {
        id: cabLayout
        readonly property int extraOperatingWidth: 12
        anchors.fill: parent
        anchors.margins: root.compact ? 8 : 12
        anchors.leftMargin: anchors.margins - extraOperatingWidth / 2
        anchors.rightMargin: anchors.leftMargin
        anchors.bottomMargin: 4
        spacing: root.gap

        RowLayout {
            id: cabHeader
            Layout.fillWidth: true
            Layout.minimumHeight: titleControls.implicitHeight
            Layout.preferredHeight: Math.max(titleControls.implicitHeight, root.compact ? 76 : 96)
            spacing: 8
            CabButton {
                Layout.preferredWidth: root.compact ? 106 : 132
                Layout.preferredHeight: root.compact ? 72 : 88
                text: "Reset"
                enabled: !bellHornPanel.visible && (!root.stateInfoVisible || !root.stateInfoFromRoster)
                font.pixelSize: root.compact ? 20 : 24
                font.bold: true
                onClicked: cab.reset()
            }
            ColumnLayout {
                id: titleControls
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                activeFocusOnTab: !root.stateInfoVisible
                Accessible.role: Accessible.Button
                Accessible.name: "Cab menu"
                Accessible.onPressAction: root.cabMenuRequested()
                Keys.onReturnPressed: root.cabMenuRequested()
                Keys.onSpacePressed: root.cabMenuRequested()
                TapHandler {
                    enabled: !root.stateInfoVisible
                    onTapped: root.cabMenuRequested()
                }
                Label {
                    Layout.fillWidth: true
                    text: root.stateInfoVisible && root.stateInfoFromRoster ? (root.stateInfoIdentity.startsWith("ENGINE") ? "Engine record" : "Train record") :
                          (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : "") + (root.stateInfoVisible ? "" : "  ▾")
                    color: "#f4f6f8"
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    font.pixelSize: root.compact ? 20 : 24
                    font.bold: true
                }
                Label {
                    objectName: "engineIdentity"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: root.stateInfoVisible ? root.stateInfoIdentity : cab.scope + " " + cab.tmccId
                    color: "#c7d1dd"
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: root.compact ? 16 : 20
                }
            }
            AllStopButton {
                compact: root.compact
                onClicked: cab.halt()
            }
        }

        Item {
            id: drivingArea
            objectName: "drivingArea"
            enabled: !bellHornPanel.visible && !root.dialogPanelOpen
            visible: !root.stateInfoVisible
            Layout.topMargin: 16
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0

            Item {
                id: operatingColumns
                objectName: "operatingColumns"
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: drivingArea.width - root.gap - drivingSliders.width

                Rectangle {
                    anchors.fill: parent
                    anchors.topMargin: pageTabs.height - 1
                    anchors.leftMargin: -2
                    anchors.rightMargin: -2
                    radius: 8
                    color: "#16376b"
                    border.color: "#5275a4"
                }

                TabBar {
                    id: pageTabs
                    objectName: "cabPageTabs"
                    implicitWidth: 0
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 56
                    currentIndex: root.effectsVisible ? 1 : 0
                    spacing: 6
                    padding: 0
                    background: Item {}
                    Repeater {
                        model: ["Controls", cab.isCrane ? "Sound" : cab.isElectric ? "Speed & Effects" : "Speed/Volume"]
                        TabButton {
                            id: pageTab
                            required property int index
                            required property string modelData
                            objectName: index === 0 ? "driveTab" : "speedTab"
                            implicitWidth: 100
                            width: (pageTabs.availableWidth - pageTabs.spacing) / 2
                            height: pageTabs.height
                            y: 0
                            padding: 0
                            topInset: 0
                            bottomInset: 0
                            text: modelData
                            onClicked: {
                                root.effectsVisible = index === 1
                                actionScroll.contentItem.contentY = 0
                            }
                            contentItem: Text {
                                text: parent.text
                                color: pageTab.checked ? "#ffffff" : "#aeb7c2"
                                font.pixelSize: 18
                                font.bold: parent.checked
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Item {
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.topMargin: pageTab.checked ? 0 : 5
                                    radius: 10
                                    color: pageTab.down ? Qt.darker("#4199cd", 1.45) : pageTab.checked ? "#16376b" : "#0a204a"
                                    border.width: 1
                                    border.color: pageTab.checked ? "#88b5e1" : "#49668c"
                                    gradient: Gradient {
                                        GradientStop { position: 0; color: pageTab.down ? Qt.darker("#68bce9", 1.45) : pageTab.checked ? "#315c94" : "#162e55" }
                                        GradientStop { position: 1; color: pageTab.down ? Qt.darker("#4199cd", 1.45) : pageTab.checked ? "#16376b" : "#0a204a" }
                                    }
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    anchors.leftMargin: 1
                                    anchors.rightMargin: 1
                                    height: 8
                                    color: pageTab.down ? Qt.darker("#4199cd", 1.45) : pageTab.checked ? "#16376b" : "#0a204a"
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: pageTab.checked ? "#16376b" : "#5275a4"
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: artwork
                    objectName: "locomotiveArtwork"
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: pageTabs.bottom
                    anchors.topMargin: -8
                    height: root.compact ? 64 : 120
                    radius: 8
                    color: "#e8ebef"
                    clip: true
                    Image {
                        anchors.fill: parent
                        anchors.margins: 2
                        source: cab.artworkSource
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: false
                    }
                    TapHandler {
                        enabled: !!root.infoController && cab.tmccId > 0
                        gesturePolicy: TapHandler.DragThreshold
                        onLongPressed: root.stateInfoRequested()
                    }
                    DragHandler {
                        id: artworkDrag
                        target: null
                        xAxis.enabled: true
                        yAxis.enabled: false
                        enabled: cab.scope === "ENGINE" && root.selection && root.selection.count > 0
                        onGrabChanged: function(transition, point) {
                            if (transition !== PointerDevice.UngrabExclusive)
                                return
                            const distance = point.scenePosition.x - point.scenePressPosition.x
                            const vertical = point.scenePosition.y - point.scenePressPosition.y
                            if (Math.abs(distance) >= 48 && Math.abs(distance) > Math.abs(vertical))
                                root.selection.selectRelative(distance < 0 ? 1 : -1)
                        }
                    }
                    WheelHandler {
                        id: artworkWheel
                        enabled: artworkDrag.enabled
                        target: null
                        orientation: Qt.Horizontal
                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                        blocking: false
                        property real distance: 0
                        property bool stepped: false

                        function resetSwipe() {
                            distance = 0
                            stepped = false
                        }

                        onWheel: function(event) {
                            if (event.phase === Qt.ScrollBegin || event.phase === Qt.ScrollEnd) {
                                swipeIdle.stop()
                                resetSwipe()
                            }
                            if (event.phase === Qt.ScrollMomentum || event.phase === Qt.ScrollEnd)
                                return

                            const pixels = event.pixelDelta
                            const angles = event.angleDelta
                            const hasPixels = pixels.x !== 0 || pixels.y !== 0
                            const dx = hasPixels ? pixels.x : angles.x / 3
                            const dy = hasPixels ? pixels.y : angles.y / 3
                            if (Math.abs(dx) <= Math.abs(dy))
                                return

                            if (event.phase === Qt.NoScrollPhase)
                                swipeIdle.restart()
                            if (stepped)
                                return
                            distance += dx
                            if (Math.abs(distance) >= 56) {
                                stepped = true
                                if (!swipeCooldown.running) {
                                    swipeCooldown.start()
                                    root.selection.selectRelative(distance < 0 ? 1 : -1)
                                }
                            }
                        }
                    }

                    Timer {
                        id: swipeIdle
                        interval: 350
                        onTriggered: artworkWheel.resetSwipe()
                    }

                    Timer {
                        // A physical swipe can arrive as several separate scroll sequences.
                        id: swipeCooldown
                        interval: 450
                    }
                }

                ScrollView {
                    id: actionScroll
                    objectName: "cabActionScroll"
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: artwork.bottom
                    anchors.topMargin: artwork.visible ? root.gap : 0
                    anchors.bottom: auxGrid.top
                    anchors.bottomMargin: root.gap
                    clip: true
                    contentWidth: availableWidth
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    ColumnLayout {
                        id: actionContent
                        width: actionScroll.availableWidth
                        spacing: root.gap
                        PairedActions {
                            visible: !root.effectsVisible
                            rows: root.driveActionRows()
                        }
                        PairedActions {
                            visible: root.effectsVisible
                            rows: root.speedActionRows()
                        }
                    }
                }

                GridLayout {
                    id: auxGrid
                    objectName: "auxiliaryGrid"
                    anchors.left: parent.left
                    anchors.right: parent.right
                    visible: !root.effectsVisible
                    height: root.tileHeight
                    y: visible
                        ? Math.min(parent.height - height, actionScroll.y + 5 * (height + root.gap))
                        : parent.height
                    columns: 3
                    columnSpacing: root.gap
                    Repeater {
                        model: root.passengerCar ? root.passengerAuxActions() : cab.secondaryActionModel
                        ActionTile {
                            required property var modelData
                            action: modelData
                            Layout.minimumHeight: root.tileHeight
                            Layout.maximumHeight: root.tileHeight
                        }
                    }
                }
            }

            Rectangle {
                id: drivingSliders
                objectName: "drivingSliders"
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: -16
                anchors.bottom: parent.bottom
                width: (drivingArea.width - root.gap - cabLayout.extraOperatingWidth) * 2 / 5
                radius: 10
                color: "#102858"
                border.color: "#496b9d"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: root.compact ? 6 : 10
                    Item {
                        id: speedReadoutRow
                        Layout.fillWidth: true
                        Layout.minimumHeight: root.compact ? 78 : 96
                        Layout.maximumHeight: root.compact ? 78 : 96
                        Layout.preferredHeight: root.compact ? 78 : 96
                        ColumnLayout {
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: parent.width
                            spacing: 0
                            Label {
                                Layout.fillWidth: true
                                text: "Current Speed"
                                color: "#9aabba"
                                horizontalAlignment: Text.AlignHCenter
                                font.pixelSize: root.compact ? 10 : 15
                            }
                            Label {
                                objectName: "currentSpeedReadout"
                                Layout.fillWidth: true
                                text: cab.isCab1
                                    ? (throttle.displayValue() > 0 ? "+" : "") + throttle.displayValue()
                                    : ("000" + Math.max(0, Math.min(199, Math.round(cab.speed)))).slice(-3)
                                font.family: speedFont.status === FontLoader.Ready ? speedFont.name : "monospace"
                                color: "#e4f6ff"
                                horizontalAlignment: Text.AlignHCenter
                                font.pixelSize: root.compact ? 36 : 46
                                font.bold: true
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        CabButton {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.compact ? 52 : 64
                            Layout.preferredWidth: 0
                            Layout.minimumWidth: 0
                            id: reverseButton
                            visible: !cab.isCab1
                            objectName: "reverseDirectionButton"
                            text: "◀ Rev" + (root.requestedDirection === "REVERSE" ? " …" : "")
                            font.pixelSize: root.compact ? 17 : 22
                            enabled: !root.standaloneCar
                            selected: root.displayedDirection.indexOf("REVERSE") >= 0
                            onClicked: root.requestDirection("REVERSE")
                        }
                        CabButton {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.compact ? 52 : 64
                            Layout.preferredWidth: 0
                            Layout.minimumWidth: 0
                            id: forwardButton
                            visible: !cab.isCab1
                            objectName: "forwardDirectionButton"
                            text: "Fwd ▶" + (root.requestedDirection === "FORWARD" ? " …" : "")
                            font.pixelSize: root.compact ? 17 : 22
                            enabled: !root.standaloneCar
                            selected: root.displayedDirection.indexOf("FORWARD") >= 0
                            onClicked: root.requestDirection("FORWARD")
                        }
                        CabButton {
                            objectName: "toggleDirectionButton"
                            visible: cab.isCab1
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.compact ? 52 : 64
                            text: "◀ Dir ▶"
                            Accessible.name: "Toggle Direction"
                            font.pixelSize: root.compact ? 17 : 22
                            onClicked: cab.toggleDirection()
                        }
                    }
                    Item {
                        id: sliderColumns
                        objectName: "sliderColumns"
                        readonly property real laneWidth: (width - 6) / 3
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 0
                        ColumnLayout {
                            visible: cab.analogModes.length > 0
                            objectName: "variableControlLane"
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: sliderColumns.laneWidth
                            spacing: 6
                            Label {
                                objectName: "variableControlLabel"
                                visible: cab.analogModes.length === 1
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.preferredHeight: root.sliderButtonHeight
                                text: cab.analogModes.length === 1 ? root.analogModeLabel(cab.analogModes[0]) : ""
                                color: "#e9edf2"
                                font.pixelSize: root.compact ? 11 : 18
                                minimumPixelSize: 10
                                fontSizeMode: Text.HorizontalFit
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            ComboBox {
                                id: analogMode
                                objectName: "variableControlSelector"
                                visible: cab.analogModes.length > 1
                                Layout.fillWidth: true
                                Layout.minimumHeight: root.sliderButtonHeight
                                Layout.maximumHeight: root.sliderButtonHeight
                                Layout.preferredHeight: root.sliderButtonHeight
                                model: cab.analogModes
                                Component.onCompleted: root.syncAnalogMode()
                                onModelChanged: Qt.callLater(root.syncAnalogMode)
                                onActivated: root.selectedAnalogMode = currentText
                                font.pixelSize: root.compact ? 11 : 18
                                leftPadding: 4
                                rightPadding: 14
                                topPadding: 0
                                bottomPadding: 0
                                indicator: Text {
                                    x: analogMode.width - width - 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "▾"
                                    color: "#c7d5e3"
                                    font.pixelSize: 12
                                }
                                popup.width: root.compact ? 150 : 220
                                popup.background: Rectangle { color: "#102858"; radius: 8; border.color: "#6385af" }
                                ToolTip.visible: hovered
                                delegate: ItemDelegate {
                                    required property int index
                                    required property string modelData
                                    width: analogMode.width
                                    text: root.analogModeLabel(modelData)
                                    font: analogMode.font
                                    highlighted: analogMode.highlightedIndex === index
                                }
                                ToolTip.text: root.analogModeLabel(currentText) + (currentText === "Horn" ? " · 0–15" : " · 0–7")
                                contentItem: Text {
                                    leftPadding: 2
                                    rightPadding: 0
                                    text: analogMode.currentText === "Momentum" ? "Mom." : root.analogModeLabel(analogMode.displayText)
                                    color: "#e9edf2"
                                    font: analogMode.font
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                    minimumPixelSize: 10
                                    fontSizeMode: Text.HorizontalFit
                                }
                                background: Rectangle {
                                    color: analogMode.down ? Qt.darker("#5597bf", 1.45) : "#303945"
                                    radius: 6
                                    border.color: "#627384"
                                }
                            }
                            VerticalCabControl {
                                id: analogControl
                                objectName: "variableCabControl"
                                enabled: !root.standaloneCar || cab.isLegacy
                                largeTouch: !root.compact
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 80
                                maximumValue: root.analogControlMode === "Horn" ? 15 : 7
                                springReturn: root.analogControlMode === "Horn"
                                value: root.analogControlMode === "Brake" ? cab.trainBrake : root.analogControlMode === "Momentum" ? cab.momentum : 0
                                onValueMoved: function(v) {
                                    if (root.analogControlMode === "Brake") cab.setTrainBrake(v)
                                    else if (root.analogControlMode === "Horn") cab.setQuillingHorn(v)
                                }
                                onValueCommitted: function(v) {
                                    if (root.analogControlMode === "Momentum") cab.setMomentum(v)
                                }
                            }
                            Label {
                                objectName: "variableControlRange"
                                Layout.fillWidth: true
                                Layout.minimumHeight: 20
                                Layout.maximumHeight: 20
                                Layout.preferredHeight: 20
                                horizontalAlignment: Text.AlignHCenter
                                text: root.analogControlMode === "Horn" ? "0–15" : "0–7"
                                color: "#bdcfe5"
                                font.pixelSize: root.compact ? 12 : 15
                            }
                            Timer {
                                interval: cab.isCab1 || cab.isCrane ? cab.hornRepeatInterval : 500
                                repeat: true
                                running: root.analogControlMode === "Horn" && analogControl.dragging && analogControl.pendingValue > 0
                                onTriggered: cab.setQuillingHorn(analogControl.pendingValue)
                            }
                        }
                        ColumnLayout {
                            objectName: "throttleLane"
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: cab.analogModes.length > 0 ? sliderColumns.laneWidth * 2 : sliderColumns.width
                            spacing: 6
                            CabButton {
                                Layout.fillWidth: true
                                Layout.minimumHeight: root.sliderButtonHeight
                                Layout.maximumHeight: root.sliderButtonHeight
                                Layout.preferredHeight: root.sliderButtonHeight
                                objectName: "speedStepUp"
                                text: "+"
                                font.pixelSize: root.compact ? 32 : 38
                                enabled: !root.standaloneCar && !cab.isCab1 && !cab.isCrane && !cab.rampActive
                                repeatWhileHeld: true
                                onClicked: cab.stepSpeed(1)
                            }
                            VerticalThrottle {
                                id: throttle
                                objectName: "targetSpeedThrottle"
                                enabled: cab.isCab1 || !root.standaloneCar
                                largeTouch: !root.compact
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 80
                                minimumValue: cab.isCab1 ? -5 : 0
                                maximumValue: cab.isCab1 ? 5 : Math.max(1, cab.speedMax)
                                value: cab.isCab1 ? 0 : cab.targetSpeed
                                springReturn: cab.isCab1
                                onGestureStarted: cab.beginRelativeThrottle()
                                onValueMoved: function(v) { if (springReturn) cab.moveRelativeThrottle(v) }
                                onGestureFinished: cab.endRelativeThrottle()
                                onValueCommitted: function(v) { cab.setSpeed(v) }
                            }
                            CabButton {
                                Layout.fillWidth: true
                                Layout.minimumHeight: root.sliderButtonHeight
                                Layout.maximumHeight: root.sliderButtonHeight
                                Layout.preferredHeight: root.sliderButtonHeight
                                objectName: "speedStepDown"
                                text: "−"
                                font.pixelSize: root.compact ? 32 : 38
                                enabled: !root.standaloneCar && !cab.isCab1 && !cab.isCrane && !cab.rampActive
                                repeatWhileHeld: true
                                onClicked: cab.stepSpeed(-1)
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            visible: root.stateInfoVisible
            Layout.fillWidth: true
            Layout.preferredHeight: root.compact ? 80 : 112
            Layout.maximumHeight: Layout.preferredHeight
            spacing: 8

            Rectangle {
                visible: !root.stateInfoFromRoster
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#e8ebef"
                radius: 8
                clip: true
                Image {
                    anchors.fill: parent
                    anchors.margins: 2
                    source: parent.visible ? cab.artworkSource : ""
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
            }

            ColumnLayout {
                Layout.fillWidth: root.stateInfoFromRoster
                Layout.preferredWidth: root.compact ? 145 : 185
                spacing: 0
                Label {
                    Layout.fillWidth: true
                    text: "Current Speed"
                    color: "#9aabba"
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: 15
                }
                Label {
                    objectName: "stateInfoSpeedReadout"
                    Layout.fillWidth: true
                    text: root.stateInfoFromRoster ? "—" : ("000" + Math.max(0, Math.min(199, Math.round(cab.speed)))).slice(-3)
                    font.family: speedFont.status === FontLoader.Ready ? speedFont.name : "monospace"
                    color: "#e4f6ff"
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: root.compact ? 36 : 46
                    font.bold: true
                }
            }
        }

        StateInfoView {
            id: stateInfo
            visible: root.stateInfoVisible
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            controller: root.infoController
            onCloseRequested: root.stateInfoClosed()
        }

        Connections {
            target: stateInfo.visible && root.infoController ? root.cab : null
            function onStateChanged() {
                root.infoController.refresh(stateInfo.editorOpen)
            }
        }

        GridLayout {
            enabled: !bellHornPanel.visible && !root.dialogPanelOpen
            visible: !root.stateInfoVisible
            Layout.fillWidth: true
            Layout.topMargin: -4
            columns: 6
            columnSpacing: 4
            Repeater {
                model: cab.infoModel
                Rectangle {
                    id: stateTile
                    required property var modelData
                    readonly property bool editable: !root.standaloneCar && !cab.isCrane && !cab.isCab1 && (
                        (modelData.label === "Speed Lim" && cab.supportsSpeedLimit) ||
                        (modelData.label === "Mom" && cab.supportsMomentum) ||
                        (modelData.label === "Brake" && cab.supportsTrainBrake) ||
                        (modelData.label === "Smoke" && cab.supportsSmoke) ||
                        (modelData.label === "Effort" && cab.supportsLabor) ||
                        (modelData.label === "RPM" && cab.supportsRpm))
                    objectName: modelData.label === "Speed Lim" ? "speedLimitStateTile" : ""
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: root.compact ? 38 : 54
                    radius: 6
                    color: editable ? "#263c50" : "#222a33"
                    border.width: editable ? 1 : 0
                    border.color: "#78bff0"
                    activeFocusOnTab: editable
                    Accessible.name: editable ? "Set " + modelData.label : modelData.label
                    Accessible.role: editable ? Accessible.Button : Accessible.StaticText
                    TapHandler {
                        enabled: stateTile.editable
                        onTapped: root.editState(modelData.label)
                    }
                    HoverHandler {
                        enabled: stateTile.editable
                        cursorShape: Qt.PointingHandCursor
                    }
                    Keys.onPressed: function(event) {
                        if (editable && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space)) {
                            root.editState(modelData.label)
                            event.accepted = true
                        }
                    }
                    Column {
                        anchors.centerIn: parent
                        spacing: 2
                        Label {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.label
                            color: "#9aabba"
                            font.pixelSize: root.compact ? 9 : 15
                        }
                        Label {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.label === "Speed Lim" && (cab.speedLimit <= 0 || cab.speedLimit === 255) ? "No limit" :
                                  modelData.value === "" ? "—" : modelData.value
                            color: stateTile.editable ? "#f1f5f9" : "#87919e"
                            font.pixelSize: root.compact ? 17 : 22
                            font.bold: true
                        }
                    }
                }
            }
        }
    }

    function closeBellHornOptions() {
        bellHornPanel.close()
    }

    MouseArea {
        anchors.left: parent.left
        anchors.right: parent.right
        y: cabLayout.y + cabHeader.y + cabHeader.height
        height: root.height - y
        z: 1
        visible: bellHornPanel.visible
        onClicked: root.closeBellHornOptions()
        onWheel: function(event) { event.accepted = true }
    }

    function closeDialogPanel() {
        dialogPanel.close()
    }

    CabDialogPanel {
        id: dialogPanel
        z: 2
        cab: root.cab
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: cabLayout.anchors.leftMargin
        anchors.rightMargin: cabLayout.anchors.rightMargin
        y: cabLayout.y + drivingArea.y + artwork.y + artwork.height + root.gap
        height: Math.max(0, root.height - y)
    }

    BellHornPopup {
        id: bellHornPanel
        parent: Overlay.overlay
        cab: root.cab
        operatingButtonWidth: (operatingColumns.width - 2 * root.gap) / 3
        operatingButtonHeight: root.tileHeight
    }

    CommandPanelPopup {
        id: commandPanel
        parent: Overlay.overlay
        cab: root.cab
        width: Math.min(Overlay.overlay.width - 24, 620)
        height: Math.min(Overlay.overlay.height - 24, 760)
        x: (Overlay.overlay.width - width) / 2
        y: (Overlay.overlay.height - height) / 2
    }

    StateValueDialog {
        id: stateValueDialog
        onValueSubmitted: function(kind, value) {
            if (kind === "Mom") cab.setMomentumPreset(value)
            else if (kind === "Brake") cab.setTrainBrake(value)
            else if (kind === "Smoke") cab.setSmoke(value)
            else if (kind === "Effort") cab.setLabor(value)
            else if (kind === "RPM") cab.setRpm(value)
        }
    }

    SpeedLimitDialog {
        id: speedLimitDialog
        onLimitSubmitted: function(value) { cab.setSpeedLimit(value) }
        onLimitCleared: cab.clearSpeedLimit()
    }
}
