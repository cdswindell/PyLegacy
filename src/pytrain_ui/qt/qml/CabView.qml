import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var cab
    required property var selection
    property bool effectsVisible: false
    property string selectedAnalogMode: "Horn"
    readonly property bool editorOpen: speedLimitDialog.visible || stateValueDialog.visible
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
        if (speedLimitDialog)
            speedLimitDialog.close()
        if (stateValueDialog)
            stateValueDialog.close()
    }

    function syncAnalogMode() {
        const modes = cab.analogModes
        const preferred = modes.indexOf(selectedAnalogMode)
        const horn = modes.indexOf("Horn")
        analogMode.currentIndex = preferred >= 0 ? preferred : horn >= 0 ? horn : modes.length ? 0 : -1
    }

    function editSpeedLimit() {
        if (cab.supportsSpeedLimit)
            speedLimitDialog.openFor(cab.speedLimit, cab.commandSpeedMax, cab.scope + " " + cab.tmccId)
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
    readonly property bool compact: height < 850
    readonly property int gap: compact ? 6 : 8
    readonly property int tileHeight: compact ? 72 : 112
    readonly property int sliderButtonHeight: compact ? 52 : 60

    function handleModelHold(action) {
        if (action.holdKind === "panel") {
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
            let_off: "steam_effects", water_injector: "steam_effects",
            freight_load: "freight_loading", freight_unload: "freight_loading",
            transformer_front_coupler: "transformer_couplers", transformer_rear_coupler: "transformer_couplers",
            momentum_low: "momentum", momentum_medium: "momentum", momentum_high: "momentum"
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
        return ["startup", "shutdown", "acela_startup", "acela_shutdown", "volume_down", "volume_up", "smoke_down", "smoke_up"].indexOf(key) >= 0
    }

    function driveActionRows() {
        const actions = cab.primaryActionModel.concat(cab.quickActionModel,
            cab.moreActionModel.filter(function(action) { return root.isDriveUtility(action.key) }))
        const byKey = {}
        const placed = {}
        for (const action of actions)
            byKey[action.key] = action
        const cells = [
            [byKey.startup || byKey.acela_startup, byKey.shutdown || byKey.acela_shutdown, byKey.volume_up],
            [byKey.bell, byKey.horn, byKey.volume_down],
            [byKey.smoke_down, byKey.smoke_up, byKey.boost],
            [byKey.rear_coupler, byKey.front_coupler, byKey.brake],
            [byKey.engineer_chatter, byKey.tower_chatter]
        ]
        const rows = cells.filter(function(row) {
            return row.some(function(action) { return action !== undefined })
        })
        for (const row of rows) {
            for (const action of row) {
                if (action)
                    placed[action.key] = true
            }
        }
        // Other equipment keeps its applicable controls after the standard rows.
        return rows.concat(root.pairedActionRows(actions.filter(function(action) { return !placed[action.key] })))
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
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0
        Layout.preferredHeight: root.tileHeight
        stacked: true
        wrapLabel: true
        padding: root.compact ? 4 : 6
        iconSize: root.compact ? 40 : 72
        text: action.label
        iconSource: action.iconSource
        font.pixelSize: root.compact ? 14 : 18
        deferForHold: action.hold
        holdThreshold: action.holdThreshold
        repeatWhileHeld: action.repeat
        repeatInterval: action.repeatInterval > 0 ? action.repeatInterval : 250
        onClicked: root.cab.triggerAction(action.key)
        onHeld: root.handleModelHold(action)
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
        anchors.fill: parent
        anchors.margins: root.compact ? 8 : 12
        anchors.bottomMargin: 4
        spacing: root.gap

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumHeight: titleControls.implicitHeight
            Layout.preferredHeight: Math.max(titleControls.implicitHeight, root.compact ? 76 : 96)
            spacing: 8
            CabButton {
                Layout.preferredWidth: root.compact ? 106 : 132
                Layout.preferredHeight: root.compact ? 72 : 88
                text: "Reset"
                font.pixelSize: root.compact ? 20 : 24
                font.bold: true
                onClicked: cab.reset()
            }
            ColumnLayout {
                id: titleControls
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Label {
                    Layout.fillWidth: true
                    text: (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : "")
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
                    text: cab.scope + " " + cab.tmccId
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
                width: (drivingArea.width - root.gap) * 3 / 5

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
                        model: ["Drive", "Speed"]
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
                            onClicked: root.effectsVisible = index === 1
                            contentItem: Text {
                                text: parent.text
                                color: parent.checked ? "#ffffff" : "#aeb7c2"
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
                                    color: pageTab.down ? "#4199cd" : pageTab.checked ? "#16376b" : "#0a204a"
                                    border.width: 1
                                    border.color: pageTab.checked ? "#88b5e1" : "#49668c"
                                    gradient: Gradient {
                                        GradientStop { position: 0; color: pageTab.down ? "#68bce9" : pageTab.checked ? "#315c94" : "#162e55" }
                                        GradientStop { position: 1; color: pageTab.down ? "#4199cd" : pageTab.checked ? "#16376b" : "#0a204a" }
                                    }
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    anchors.leftMargin: 1
                                    anchors.rightMargin: 1
                                    height: 8
                                    color: pageTab.down ? "#4199cd" : pageTab.checked ? "#16376b" : "#0a204a"
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
                    height: {
                        const base = root.compact ? 64 : 96
                        const rows = root.driveActionRows().length
                        const controls = rows * root.tileHeight + Math.max(0, rows - 1) * root.gap
                        const spare = parent.height - y - base - controls - auxGrid.height - root.gap * 2 - 4
                        return base + Math.min(root.compact ? 16 : 48, Math.max(0, spare))
                    }
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
                    DragHandler {
                        target: null
                        xAxis.enabled: true
                        yAxis.enabled: false
                        onActiveChanged: {
                            if (!active && Math.abs(translation.x) >= 48 && root.selection)
                                root.selection.selectRelative(translation.x < 0 ? 1 : -1)
                        }
                    }
                }

                ScrollView {
                    id: actionScroll
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
                            actions: cab.moreActionModel.filter(function(action) { return !root.isDriveUtility(action.key) })
                        }
                    }
                }

                GridLayout {
                    id: auxGrid
                    objectName: "auxiliaryGrid"
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: root.tileHeight
                    y: root.effectsVisible ? parent.height - height :
                        Math.min(parent.height - height, artwork.y + artwork.height + root.gap + actionContent.implicitHeight + root.gap)
                    columns: 3
                    columnSpacing: root.gap
                    Repeater {
                        model: cab.secondaryActionModel
                        FunctionButton {
                            required property var modelData
                            objectName: "auxControl_" + modelData.key
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: 0
                            Layout.minimumHeight: root.tileHeight
                            Layout.maximumHeight: root.tileHeight
                            Layout.preferredHeight: root.tileHeight
                            compact: true
                            text: modelData.label.replace(" · ", "\n")
                            holdHint: modelData.holdTarget === "lights" ? "Lighting panel" :
                                      modelData.holdTarget === "more" ? "More controls" :
                                      modelData.key === "sequence" ? "Repeat sequence" : ""
                            font.pixelSize: root.compact ? 14 : 18
                            deferForHold: modelData.hold
                            holdThreshold: modelData.holdThreshold
                            repeatWhileHeld: modelData.repeat
                            repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250
                            onClicked: cab.triggerAction(modelData.key)
                            onHeld: root.handleModelHold(modelData)
                        }
                    }
                }
            }

            Rectangle {
                objectName: "drivingSliders"
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: -16
                anchors.bottom: parent.bottom
                width: (drivingArea.width - root.gap) * 2 / 5
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
                                text: "CURRENT SPEED"
                                color: "#9aabba"
                                horizontalAlignment: Text.AlignHCenter
                                font.pixelSize: root.compact ? 10 : 15
                            }
                            Label {
                                objectName: "currentSpeedReadout"
                                Layout.fillWidth: true
                                text: ("000" + Math.max(0, Math.min(199, Math.round(cab.speed)))).slice(-3)
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
                            objectName: "reverseDirectionButton"
                            text: "◀ REV" + (root.requestedDirection === "REVERSE" ? " …" : "")
                            font.pixelSize: root.compact ? 17 : 22
                            selected: root.displayedDirection.indexOf("REVERSE") >= 0
                            onClicked: root.requestDirection("REVERSE")
                        }
                        CabButton {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.compact ? 52 : 64
                            Layout.preferredWidth: 0
                            Layout.minimumWidth: 0
                            id: forwardButton
                            objectName: "forwardDirectionButton"
                            text: "FWD ▶" + (root.requestedDirection === "FORWARD" ? " …" : "")
                            font.pixelSize: root.compact ? 17 : 22
                            selected: root.displayedDirection.indexOf("FORWARD") >= 0
                            onClicked: root.requestDirection("FORWARD")
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
                            ComboBox {
                                id: analogMode
                                objectName: "variableControlSelector"
                                visible: cab.analogModes.length > 0
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
                                ToolTip.text: currentText + (currentText === "Horn" ? " · 0–15" : " · 0–7")
                                contentItem: Text {
                                    leftPadding: 2
                                    rightPadding: 0
                                    text: analogMode.currentText === "Momentum" ? "Mom." : analogMode.displayText
                                    color: "#e9edf2"
                                    font: analogMode.font
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }
                                background: Rectangle {
                                    color: analogMode.down ? "#5597bf" : "#303945"
                                    radius: 6
                                    border.color: "#627384"
                                }
                            }
                            VerticalCabControl {
                                id: analogControl
                                objectName: "variableCabControl"
                                largeTouch: !root.compact
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 80
                                maximumValue: analogMode.currentText === "Horn" ? 15 : 7
                                springReturn: analogMode.currentText === "Horn"
                                value: analogMode.currentText === "Brake" ? cab.trainBrake : analogMode.currentText === "Momentum" ? cab.momentum : 0
                                onValueMoved: function(v) {
                                    if (analogMode.currentText === "Brake") cab.setTrainBrake(v)
                                    else if (analogMode.currentText === "Horn") cab.setQuillingHorn(v)
                                }
                                onValueCommitted: function(v) {
                                    if (analogMode.currentText === "Momentum") cab.setMomentum(v)
                                    else if (analogMode.currentText === "Brake") cab.setTrainBrake(v)
                                    else if (analogMode.currentText === "Horn") cab.setQuillingHorn(v)
                                }
                            }
                            Label {
                                objectName: "variableControlRange"
                                Layout.fillWidth: true
                                Layout.minimumHeight: 20
                                Layout.maximumHeight: 20
                                Layout.preferredHeight: 20
                                horizontalAlignment: Text.AlignHCenter
                                text: analogMode.currentText === "Horn" ? "0–15" : "0–7"
                                color: "#bdcfe5"
                                font.pixelSize: root.compact ? 12 : 15
                            }
                            Timer {
                                interval: 500
                                repeat: true
                                running: analogMode.currentText === "Horn" && analogControl.dragging && analogControl.pendingValue > 0
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
                                enabled: !cab.rampActive
                                repeatWhileHeld: true
                                onClicked: cab.stepSpeed(1)
                            }
                            VerticalThrottle {
                                id: throttle
                                objectName: "targetSpeedThrottle"
                                largeTouch: !root.compact
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 80
                                maximumValue: Math.max(1, cab.speedMax)
                                value: cab.targetSpeed
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
                                enabled: !cab.rampActive
                                repeatWhileHeld: true
                                onClicked: cab.stepSpeed(-1)
                            }
                        }
                    }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.topMargin: -4
            columns: 6
            columnSpacing: 4
            Repeater {
                model: cab.infoModel
                Rectangle {
                    id: stateTile
                    required property var modelData
                    readonly property bool editable: (modelData.label === "Speed Lim" && cab.supportsSpeedLimit) ||
                        (modelData.label === "Mom" && cab.supportsMomentum) ||
                        (modelData.label === "Brake" && cab.supportsTrainBrake) ||
                        (modelData.label === "Smoke" && cab.supportsSmoke)
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
                            color: "#f1f5f9"
                            font.pixelSize: root.compact ? 17 : 22
                            font.bold: true
                        }
                    }
                }
            }
        }
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
        }
    }

    SpeedLimitDialog {
        id: speedLimitDialog
        onLimitSubmitted: function(value) { cab.setSpeedLimit(value) }
        onLimitCleared: cab.clearSpeedLimit()
    }
}
