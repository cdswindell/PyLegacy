import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    PanelMetrics { id: metrics }

    property var controller
    property var accessory: ({})
    property bool configurationVisible: false
    property real controlBottomInset: 0
    readonly property bool compact: height < 850
    readonly property bool hasArtwork: (accessory.artworkSource || "").length > 0
    readonly property real editorTop: pageLayout.y + cabHeader.y + cabHeader.height + 8
    readonly property string kind: accessory.kind || ""
    readonly property bool hasAccessoryCab: kind === "OPERATING" && accessory.sharedCommandAddress === true
    readonly property int infoTabIndex: hasAccessoryCab ? 2 : 1
    readonly property bool accessoryCabSelected: hasAccessoryCab && operatingTabs.currentIndex === 1
    readonly property real accessoryCabArtworkLimit: Math.max(0,
        pageLayout.height - cabHeader.height - operatingTabs.height - 2 * pageLayout.spacing
        - metrics.accessoryTabContentGap - operationFrame.topPadding
        - operationFrame.bottomPadding - 340)
    signal infoRequested(int tmccId)
    signal configureRequested(int tmccId)
    signal closeRequested()
    signal cabMenuRequested()

    color: "#102858"
    radius: 10

    component OperationArtwork: Rectangle {
        id: artwork
        required property string source
        required property bool playback
        readonly property bool animated: source.toLowerCase().endsWith(".gif")
        color: "#11151a"
        radius: 6
        clip: true

        AnimatedImage {
            anchors.fill: parent
            source: artwork.visible && artwork.animated ? artwork.source : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            playing: artwork.visible && artwork.playback
            visible: artwork.animated
        }

        Image {
            anchors.fill: parent
            source: artwork.visible && !artwork.animated ? artwork.source : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            visible: !artwork.animated
        }
    }

    function releaseHolds() {
        if (kind === "OPERATING" && controller)
            controller.releaseConfiguredHolds(accessory.key)
    }

    readonly property string accessoryKey: accessory.key || ""
    onAccessoryKeyChanged: operatingTabs.currentIndex = 0
    onVisibleChanged: if (!visible) {
        releaseHolds()
        operatingTabs.currentIndex = 0
    }
    onEnabledChanged: if (!enabled) releaseHolds()

    ColumnLayout {
        id: pageLayout
        anchors.fill: parent
        anchors.margins: 12
        anchors.leftMargin: 6
        anchors.rightMargin: anchors.leftMargin
        spacing: 10

        RowLayout {
            id: cabHeader
            Layout.fillWidth: true
            Layout.minimumHeight: titleControls.implicitHeight
            Layout.preferredHeight: Math.max(titleControls.implicitHeight, root.compact ? 76 : 96)
            spacing: 8

            CabButton {
                Layout.preferredWidth: root.compact ? 106 : 132
                Layout.preferredHeight: root.compact ? 72 : 88
                text: "Back"
                enabled: !root.configurationVisible
                font.pixelSize: root.compact ? 20 : 24
                onClicked: root.closeRequested()
            }

            CabMenuTitle {
                id: titleControls
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                compact: root.compact
                menuEnabled: !root.configurationVisible
                title: root.accessory.title || "Accessory"
                identity: root.accessory.tmccId && !(root.hasAccessoryCab && operatingTabs.currentIndex === root.infoTabIndex)
                    ? "ACC " + root.accessory.tmccId : root.hasAccessoryCab ? " " : ""
                onActivated: root.cabMenuRequested()
            }

            AllStopButton {
                compact: root.compact
                onClicked: root.controller.halt()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            enabled: !root.configurationVisible
            visible: root.hasArtwork || !!root.accessory.tmccId
            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredHeight: root.hasArtwork ? Math.min(
                    root.hasAccessoryCab ? Math.min(root.height * 0.38, root.accessoryCabArtworkLimit)
                    : root.kind === "OPERATING" ? Math.min(root.height * 0.38, Math.max(0,
                        pageLayout.height - cabHeader.height - operatingTabs.height - operationFrame.implicitHeight
                        - metrics.accessoryTabContentGap - 2 * pageLayout.spacing)) : root.height * 0.23,
                    width / Math.max(1, Number(root.accessory.artworkAspectRatio || 3))
                        * (root.kind === "OPERATING" ? 1.5 : 1)) : 0

                Rectangle {
                    objectName: "accessoryArtwork"
                    anchors.fill: parent
                    visible: root.hasArtwork
                    color: root.kind === "AMC2" || root.kind === "SENSOR" ? "#e8ebef" : "#0f1216"
                    radius: 8
                    clip: true

                    Image {
                        anchors.fill: parent
                        source: root.accessory.artworkSource || ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }

                    ControlTapHandler {
                        enabled: root.kind === "AMC2" && !!root.accessory.tmccId
                        holdEnabled: true
                        onTappedTwice: root.infoRequested(root.accessory.tmccId)
                        onHeldGesture: root.infoRequested(root.accessory.tmccId)
                    }
                }
            }

            ColumnLayout {
                visible: root.kind !== "OPERATING"
                Layout.preferredWidth: root.compact ? 108 : 132
                Layout.minimumWidth: Layout.preferredWidth
                Layout.maximumWidth: Layout.preferredWidth
                Layout.alignment: Qt.AlignVCenter
                spacing: 14

                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: (root.compact ? 48 : 56) * 1.1
                    text: "Info"
                    font.pixelSize: root.compact ? 17 : 20
                    enabled: !!root.accessory.tmccId
                    onClicked: root.infoRequested(root.accessory.tmccId)
                }

                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: (root.compact ? 48 : 56) * 1.1
                    text: "Configure"
                    font.pixelSize: root.compact ? 17 : 20
                    visible: root.kind === "AMC2"
                    enabled: !!root.accessory.tmccId
                    onClicked: root.configureRequested(root.accessory.tmccId)
                }
            }
        }

        AccessoryDeviceControls {
            Layout.topMargin: root.kind === "AMC2" || root.kind === "SENSOR" ? metrics.sectionGap : 0
            Layout.bottomMargin: root.kind === "TMCC" || root.kind === "AMC2"
                ? Math.max(0, root.controlBottomInset - pageLayout.anchors.bottomMargin) : 0
            enabled: !root.configurationVisible
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.kind !== "" && root.kind !== "OPERATING"
            controller: root.controller
            accessory: root.accessory
            compact: root.compact
        }

        ColumnLayout {
            visible: root.kind === "OPERATING"
            Layout.fillWidth: true
            Layout.fillHeight: root.accessoryCabSelected
            Layout.topMargin: Math.max(0, metrics.accessoryTabInset - pageLayout.spacing)
            spacing: metrics.accessoryTabContentGap

            RowLayout {
                id: operatingTabs
                objectName: "operatingAccessoryTabs"
                Layout.preferredWidth: parent.width * 2 / 3
                Layout.maximumWidth: Layout.preferredWidth
                Layout.preferredHeight: 56
                Layout.maximumHeight: Layout.preferredHeight
                Layout.fillHeight: false
                spacing: 6
                property int currentIndex: 0
                onCurrentIndexChanged: if (currentIndex !== 0) root.releaseHolds()

                CabPageTab {
                    objectName: "operatingControlsTab"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 0
                    text: "Controls"
                    checked: operatingTabs.currentIndex === 0
                    onClicked: operatingTabs.currentIndex = 0
                }
                CabPageTab {
                    objectName: "operatingAccTab"
                    visible: root.hasAccessoryCab
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 0
                    text: "ACC"
                    checked: root.accessoryCabSelected
                    onClicked: operatingTabs.currentIndex = 1
                }
                CabPageTab {
                    objectName: "operatingInfoTab"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 0
                    text: "Info"
                    checked: operatingTabs.currentIndex === root.infoTabIndex
                    onClicked: operatingTabs.currentIndex = root.infoTabIndex
                }
            }

            Frame {
                id: operationFrame
                Layout.fillWidth: true
                Layout.fillHeight: root.accessoryCabSelected
                padding: 8
                background: Rectangle {
                    radius: 8
                    color: "#16376b"
                    border.color: "#5275a4"
                }

                contentItem: ColumnLayout {
                GridLayout {
                    id: operationGrid
                    visible: operatingTabs.currentIndex === 0
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: hasAnalog ? Infinity : columns * (targetButtonSize + 2 * cardInset)
                        + (columns - 1) * columnSpacing
                    columns: Math.max(1, Math.min(3, buttonCount))
                    rowSpacing: 8
                    columnSpacing: 8

                    readonly property var operations: root.accessory.operations || []
                    readonly property bool hasAnalog: operations.some(operation => operation.analogInput)
                    readonly property int buttonCount: operations.reduce(
                        (count, operation) => count + (operation.analogInput ? 0 : operation.control === "command_pair" ? 2 : 1), 0)
                    readonly property int cardInset: 9
                    readonly property int controlGap: 8
                    readonly property int targetButtonSize: 2 * metrics.cabActionTileHeight(root.compact)
                    readonly property real columnWidth: Math.max(0, (width - (columns - 1) * columnSpacing) / columns)

                    Repeater {
                        id: parentRepeater
                        // Keep delegates alive while device feedback refreshes their data.
                        readonly property var orderedOperations: operationGrid.operations.filter(operation => !operation.analogInput)
                            .concat(operationGrid.operations.filter(operation => operation.analogInput))
                        model: orderedOperations.length

                        delegate: Item {
                            id: operationSlot
                            required property int index
                            readonly property var operation: parentRepeater.orderedOperations[index] || ({})
                            readonly property int span: operation.analogInput ? operationGrid.columns
                                : operation.control === "command_pair" ? Math.min(2, operationGrid.columns) : 1

                            Layout.columnSpan: span
                            Layout.preferredWidth: operationGrid.columnWidth * span + (span - 1) * operationGrid.columnSpacing
                            Layout.preferredHeight: operationRow.height
                            Layout.alignment: Qt.AlignTop | Qt.AlignHCenter

                            Rectangle {
                                id: operationRow
                                readonly property var modelData: operationSlot.operation
                                readonly property var analog: modelData.analogInput || null
                                readonly property bool vertical: analog !== null && analog.orientation === "vertical"
                                readonly property string controlKind: modelData.control || ""
                                readonly property bool pulse: controlKind === "momentary_pulse"
                                readonly property bool operationActive: modelData.held === true || modelData.state === "ON"
                                readonly property bool canOperate: root.visible && root.enabled && operatingTabs.currentIndex === 0 && modelData.enabled === true
                                readonly property bool paired: controlKind === "command_pair"
                                readonly property bool toggles: controlKind === "latch" || controlKind === "command_toggle"
                                readonly property bool powerButton: paired || toggles
                                readonly property bool holding: controlKind === "momentary_hold"
                                property string heldAccessory: ""
                                property string heldOperation: ""
                                readonly property bool playbackRequested: modelData.animationRunning === true
                                readonly property int playbackDuration: modelData.animationDuration || 0
                                readonly property bool artworkActive: pulse || playbackDuration > 0 ? playbackTimer.running : operationActive
                                readonly property string stateArtwork: (artworkActive ? modelData.onImageSource : modelData.offImageSource) || ""
                                readonly property string artworkSource: {
                                    if (stateArtwork && !legacyPowerIcon(stateArtwork) && (!powerButton || stateArtwork.toLowerCase().endsWith(".gif")))
                                        return stateArtwork
                                    const sharedArtwork = modelData.imageSource || ""
                                    return legacyPowerIcon(sharedArtwork) ? "" : sharedArtwork
                                }
                                readonly property bool artworkOnButton: analog === null && !powerButton && artworkSource !== ""
                                readonly property bool playArtwork: root.visible && (pulse || playbackDuration > 0
                                    ? playbackTimer.running : playbackRequested)
                                readonly property real artworkWidth: Math.min(200, operationSlot.width * 0.28)
                                readonly property real artworkSpace: artworkSource && !artworkOnButton ? artworkWidth + 10 : 0
                                readonly property real controlsWidth: width - 2 * operationGrid.cardInset - artworkSpace
                                readonly property string artworkIdentity: (root.accessory.key || "") + "/" + (modelData.key || "")

                                function legacyPowerIcon(source) {
                                    const filename = (source || "").split("/").pop().toLowerCase()
                                    if (filename === "on_button.jpg")
                                        return "power-on"
                                    if (filename === "off_button.jpg")
                                        return "power-off"
                                    return ""
                                }

                                function activate(action) {
                                    if (!canOperate || !root.controller)
                                        return
                                    const accessoryKey = root.accessory.key
                                    const operationKey = modelData.key
                                    if (!root.controller.activateConfiguredOperation(accessoryKey, operationKey, action))
                                        return
                                    if (action === "press") {
                                        heldAccessory = accessoryKey
                                        heldOperation = operationKey
                                    }
                                    if (pulse || playbackDuration > 0)
                                        playbackTimer.restart()
                                }

                                function release() {
                                    if (!heldAccessory)
                                        return
                                    const accessoryKey = heldAccessory
                                    const operationKey = heldOperation
                                    heldAccessory = ""
                                    heldOperation = ""
                                    if (root.controller)
                                        root.controller.activateConfiguredOperation(accessoryKey, operationKey, "release")
                                }

                                onCanOperateChanged: if (!canOperate) release()
                                Component.onDestruction: release()

                                function startTimedPlayback() {
                                    if (playbackRequested && playbackDuration > 0 && root.visible)
                                        playbackTimer.restart()
                                }

                                Component.onCompleted: startTimedPlayback()
                                onPlaybackRequestedChanged: startTimedPlayback()
                                onArtworkIdentityChanged: {
                                    release()
                                    playbackTimer.stop()
                                    startTimedPlayback()
                                }

                                Timer {
                                    id: playbackTimer
                                    interval: Math.max(1, operationRow.playbackDuration || operationRow.modelData.pulseDuration || 0)
                                }
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: analog !== null ? operationSlot.width : Math.min(operationSlot.width,
                                    2 * operationGrid.cardInset + artworkSpace + operationGrid.targetButtonSize
                                    + (paired ? operationGrid.targetButtonSize + operationGrid.controlGap : 0))
                                height: Math.max(vertical ? 250 : 0, operationContent.implicitHeight + 2 * operationGrid.cardInset)
                                radius: 8
                                color: "#272d35"
                                border.width: 1
                                border.color: "#4b5664"

                                RowLayout {
                                    id: operationContent
                                    anchors.fill: parent
                                    anchors.margins: operationGrid.cardInset
                                    spacing: 10

                                    OperationArtwork {
                                        Layout.preferredWidth: operationRow.artworkWidth
                                        Layout.fillHeight: true
                                        visible: operationRow.artworkSource !== "" && !operationRow.artworkOnButton
                                        source: operationRow.artworkSource
                                        playback: operationRow.playArtwork
                                        opacity: operationRow.canOperate ? 1 : 0.42
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        spacing: 4

                                        Label {
                                            Layout.fillWidth: true
                                            text: operationRow.modelData.label || ""
                                            color: "#f4f6f8"
                                            font.pixelSize: 18
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        RowLayout {
                                            id: operationControls
                                            Layout.alignment: Qt.AlignHCenter
                                            spacing: operationGrid.controlGap
                                            visible: operationRow.analog === null && operationRow.controlKind !== ""
                                            readonly property real buttonSize: Math.max(0, Math.min(operationGrid.targetButtonSize,
                                                operationRow.paired ? (operationRow.controlsWidth - spacing) / 2 : operationRow.controlsWidth))

                                            Repeater {
                                                model: operationRow.paired ? ["on", "off"] : operationRow.toggles ? ["toggle"] : []

                                                FunctionButton {
                                                    required property string modelData
                                                    readonly property string action: modelData === "toggle"
                                                        ? (operationRow.operationActive ? "off" : "on") : modelData
                                                    objectName: "accessoryOperation-" + (operationRow.modelData.key || "") + "-" + modelData
                                                    Layout.preferredWidth: operationControls.buttonSize
                                                    Layout.preferredHeight: operationControls.buttonSize
                                                    enabled: operationRow.canOperate
                                                    text: (operationRow.toggles ? operationRow.modelData.actionLabel : "")
                                                        || (action === "on" ? "On" : "Off")
                                                    readonly property string stateIcon: (action === "on"
                                                        ? operationRow.modelData.onImageSource : operationRow.modelData.offImageSource) || ""
                                                    trialIcon: operationRow.legacyPowerIcon(stateIcon) || (stateIcon ? "" : "power-" + action)
                                                    iconSource: trialIcon ? "" : stateIcon
                                                    stacked: true
                                                    font.pixelSize: root.compact ? 17 : 21
                                                    iconSize: Math.round(operationControls.buttonSize * 0.64)
                                                    onClicked: operationRow.activate(action)
                                                }
                                            }

                                            CabButton {
                                                id: actionButton
                                                objectName: "accessoryOperation-" + (operationRow.modelData.key || "") + "-" +
                                                    (operationRow.holding ? "press" : "fire")
                                                visible: !operationRow.powerButton
                                                Layout.preferredWidth: operationControls.buttonSize
                                                Layout.preferredHeight: operationControls.buttonSize
                                                enabled: operationRow.canOperate
                                                Accessible.name: operationRow.modelData.label || ""
                                                text: operationRow.artworkOnButton ? "" : (operationRow.modelData.label || "")
                                                selected: operationRow.modelData.held === true || (operationRow.pulse && playbackTimer.running)
                                                opacity: operationRow.canOperate ? 1 : 0.6
                                                activateOnRelease: !operationRow.holding && !repeatWhileHeld
                                                holdWithinBounds: operationRow.holding
                                                repeatWhileHeld: operationRow.controlKind === "command"
                                                    && operationRow.analog === null && operationRow.modelData.repeat > 0
                                                repeatInterval: operationRow.modelData.repeat || 100
                                                onClicked: operationRow.activate(operationRow.holding ? "press" : "fire")
                                                onReleased: if (operationRow.holding) operationRow.release()
                                                onPressCanceled: if (operationRow.holding) operationRow.release()

                                                OperationArtwork {
                                                    anchors.fill: parent
                                                    anchors.margins: 12
                                                    visible: operationRow.artworkOnButton
                                                    source: operationRow.artworkSource
                                                    playback: operationRow.playArtwork
                                                    opacity: operationRow.canOperate ? 1 : 0.5
                                                }

                                                Rectangle {
                                                    visible: operationRow.holding || actionButton.repeatWhileHeld
                                                    anchors.top: parent.top
                                                    anchors.right: parent.right
                                                    anchors.margins: 8
                                                    width: 25
                                                    height: width
                                                    radius: width / 2
                                                    color: operationRow.artworkOnButton ? "#263b50" : "transparent"

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "↻"
                                                        color: "white"
                                                        font.pixelSize: 20
                                                    }
                                                }
                                            }
                                        }

                                        Slider {
                                            id: analogSlider
                                            objectName: "accessoryAnalogSlider-" + (operationRow.modelData.key || "")
                                            Accessible.name: operationRow.modelData.label || ""
                                            readonly property var input: operationRow.analog
                                            readonly property int neutral: input ? input.neutral : 0
                                            readonly property string operationIdentity: (root.accessory.key || "") + "/" +
                                                (operationRow.modelData.key || "")
                                            property string pressedIdentity: ""
                                            property int lastSent: neutral
                                            visible: input !== null
                                            enabled: visible && !root.configurationVisible && operationRow.canOperate
                                            orientation: operationRow.vertical ? Qt.Vertical : Qt.Horizontal
                                            Layout.fillWidth: !operationRow.vertical
                                            Layout.fillHeight: operationRow.vertical
                                            Layout.alignment: Qt.AlignHCenter
                                            Layout.preferredHeight: operationRow.vertical ? -1 : 80
                                            from: input ? input.minimum : 0
                                            to: input ? input.maximum : 1
                                            stepSize: 1
                                            snapMode: Slider.SnapAlways
                                            value: neutral

                                            background: Rectangle {
                                                x: operationRow.vertical ? (analogSlider.width - width) / 2
                                                    : analogSlider.leftPadding + analogSlider.handle.width / 2
                                                y: operationRow.vertical ? analogSlider.topPadding + analogSlider.handle.height / 2 : 12
                                                width: operationRow.vertical ? 8
                                                    : Math.max(0, analogSlider.availableWidth - analogSlider.handle.width)
                                                height: operationRow.vertical
                                                    ? Math.max(0, analogSlider.availableHeight - analogSlider.handle.height) : 8
                                                radius: 4
                                                color: "#141e29"
                                                border.color: "#536579"
                                            }

                                            handle: Item {
                                                id: boomThumb
                                                width: operationRow.vertical ? 34 : 96
                                                height: operationRow.vertical ? 34 : 62
                                                x: operationRow.vertical ? (analogSlider.width - width) / 2
                                                    : analogSlider.leftPadding + analogSlider.visualPosition *
                                                        (analogSlider.availableWidth - width)
                                                y: operationRow.vertical ? analogSlider.topPadding + analogSlider.visualPosition *
                                                    (analogSlider.availableHeight - height) : 12
                                                opacity: analogSlider.enabled ? 1 : 0.5

                                                Rectangle {
                                                    visible: !operationRow.vertical
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    width: 12
                                                    height: 24
                                                    radius: 4
                                                    color: "#46687f"
                                                    border.color: "#829eaf"
                                                }
                                                Rectangle {
                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    anchors.bottom: parent.bottom
                                                    visible: operationRow.vertical
                                                    height: parent.height
                                                    radius: 6
                                                    border.color: "#829eaf"
                                                    gradient: Gradient {
                                                        GradientStop {
                                                            position: 0
                                                            color: analogSlider.pressed ? "#457c99" : "#698ba0"
                                                        }
                                                        GradientStop { position: 1; color: "#203e52" }
                                                    }
                                                }
                                                ThrottleGrip {
                                                    visible: !operationRow.vertical
                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    anchors.bottom: parent.bottom
                                                    height: 43
                                                    caption: "RELATIVE"
                                                    valueText: Math.round(analogSlider.value).toString()
                                                    pressed: analogSlider.pressed
                                                }
                                            }

                                            function sendStep(repeated) {
                                                if (!pressed || pressedIdentity !== operationIdentity || !enabled || !visible)
                                                    return
                                                const step = Math.round(value)
                                                if (step !== neutral && (repeated || step !== lastSent) && root.controller)
                                                    root.controller.sendAnalogOperation(root.accessory.key, operationRow.modelData.key, step)
                                                lastSent = step
                                            }

                                            function resetGesture() {
                                                pressedIdentity = ""
                                                lastSent = neutral
                                                if (input && input.springReturn)
                                                    value = neutral
                                            }

                                            onPressedChanged: {
                                                if (!pressed) {
                                                    resetGesture()
                                                    return
                                                }
                                                pressedIdentity = operationIdentity
                                                sendStep(false)
                                            }
                                            onMoved: sendStep(false)
                                            onOperationIdentityChanged: resetGesture()
                                            onEnabledChanged: if (!enabled) resetGesture()
                                            onVisibleChanged: if (!visible) resetGesture()

                                            Timer {
                                                interval: analogSlider.input ? Math.max(1, analogSlider.input.repeat) : 1
                                                repeat: true
                                                running: analogSlider.input !== null && analogSlider.input.repeat > 0 &&
                                                    analogSlider.pressed && analogSlider.enabled && analogSlider.visible &&
                                                    analogSlider.pressedIdentity === analogSlider.operationIdentity &&
                                                    analogSlider.value !== analogSlider.neutral
                                                onTriggered: analogSlider.sendStep(true)
                                            }
                                        }
                                        Item { Layout.fillHeight: true }


                                    }
                                }
                            }
                        }
                    }
                }

                    AccessoryDeviceControls {
                        visible: root.accessoryCabSelected
                        enabled: !root.configurationVisible
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        controller: root.controller
                        accessory: ({ kind: "TMCC", key: root.accessoryKey, tmccId: root.accessory.tmccId })
                        compact: root.compact
                        showTmccTab: false
                        fillTmccKeypad: true
                    }

                    ColumnLayout {
                        id: infoMappings
                        visible: operatingTabs.currentIndex === root.infoTabIndex
                        Layout.fillWidth: true
                        spacing: 4
                        readonly property bool sharedCommandAddress: root.accessory.sharedCommandAddress === true
                        readonly property real operationWidth: width * 0.40

                        component MappingRow: Rectangle {
                            id: mappingRow
                            required property string operationText
                            required property string mappingText
                            property bool heading: false
                            Layout.fillWidth: true
                            implicitHeight: mappingLayout.implicitHeight + 16
                            radius: 5
                            color: heading ? "#23466a" : "#102858"

                            RowLayout {
                                id: mappingLayout
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 12

                                Label {
                                    Layout.preferredWidth: infoMappings.operationWidth
                                    text: mappingRow.operationText
                                    color: mappingRow.heading ? "#aeb7c2" : "white"
                                    font.pixelSize: root.compact ? 16 : 20
                                    font.bold: mappingRow.heading
                                    wrapMode: Text.Wrap
                                }
                                Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: mappingRow.mappingText
                                    color: mappingRow.heading ? "#aeb7c2" : "white"
                                    font.pixelSize: root.compact ? 16 : 20
                                    font.bold: mappingRow.heading
                                    wrapMode: Text.Wrap
                                }
                            }
                        }

                        Label {
                            visible: infoMappings.sharedCommandAddress
                            Layout.fillWidth: true
                            Layout.margins: 8
                            text: "TMCC ID " + root.accessory.tmccId
                            color: "white"
                            font.pixelSize: root.compact ? 16 : 20
                            font.bold: true
                        }

                        Label {
                            visible: infoMappings.sharedCommandAddress && text.length > 0
                            Layout.fillWidth: true
                            Layout.leftMargin: 8
                            Layout.rightMargin: 8
                            Layout.bottomMargin: 8
                            text: root.accessory.accessoryTypeName || ""
                            color: "#aeb7c2"
                            font.pixelSize: root.compact ? 16 : 20
                            wrapMode: Text.Wrap
                        }

                        MappingRow {
                            heading: true
                            operationText: "Operation"
                            mappingText: infoMappings.sharedCommandAddress ? "Accessory Panel Keys" : "Assignment"
                        }

                        Repeater {
                            model: root.accessory.operations || []
                            delegate: MappingRow {
                                required property var modelData
                                readonly property var assignments: modelData.lcsLabels || []
                                readonly property string keys: modelData.accessoryKeys || ""
                                operationText: modelData.label
                                mappingText: infoMappings.sharedCommandAddress ? keys
                                    : ["TMCC " + modelData.tmccId].concat(assignments).concat(keys ? [keys] : []).join(" · ")
                            }
                        }
                    }
                }
            }
        }

        Item {
            Layout.fillHeight: true
            Layout.preferredHeight: 0
            visible: root.kind === "OPERATING" && !root.accessoryCabSelected
        }
    }
}
