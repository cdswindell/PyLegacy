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

    onVisibleChanged: if (!visible) {
        releaseHolds()
        operatingInfo.close()
    }
    onEnabledChanged: if (!enabled) releaseHolds()

    Popup {
        id: operatingInfo
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 32, 620)
        modal: true
        padding: 16
        background: Rectangle { color: "#102858"; radius: 10; border.color: "#4b5664" }

        contentItem: ColumnLayout {
            Label {
                text: root.accessory.title || "Accessory"
                color: "white"
                font.pixelSize: 26
                font.bold: true
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
            Repeater {
                model: root.accessory.operations || []
                delegate: Label {
                    required property var modelData
                    Layout.fillWidth: true
                    readonly property var mappings: modelData.lcsLabels || []
                    text: modelData.label + " · TMCC " + modelData.tmccId
                        + (mappings.length ? " · " + mappings.join(" · ") : "")
                    color: "white"
                    font.pixelSize: 20
                    wrapMode: Text.Wrap
                }
            }
            CabButton {
                Layout.fillWidth: true
                text: "Close"
                onClicked: operatingInfo.close()
            }
        }
    }

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
                identity: root.accessory.tmccId ? "ACC " + root.accessory.tmccId : ""
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
                    root.kind === "OPERATING" ? Math.min(root.height * 0.38, Math.max(0,
                        pageLayout.height - cabHeader.height - operationGrid.implicitHeight
                        - operatingInfoButton.implicitHeight - metrics.cabActionTileHeight(root.compact)
                        - 4 * pageLayout.spacing)) : root.height * 0.23,
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

        GridLayout {
            id: operationGrid
            visible: root.kind === "OPERATING"
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
                        readonly property bool canOperate: root.visible && root.enabled && !operatingInfo.opened && modelData.enabled === true
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
                                    Layout.preferredHeight: operationRow.vertical ? -1 : 52
                                    from: input ? input.minimum : 0
                                    to: input ? input.maximum : 1
                                    stepSize: 1
                                    snapMode: Slider.SnapAlways
                                    value: neutral

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

        CabButton {
            id: operatingInfoButton
            objectName: "operatingAccessoryInfoButton"
            visible: root.kind === "OPERATING"
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: metrics.cabActionTileHeight(root.compact)
            Layout.preferredWidth: root.compact ? 108 : 132
            Layout.preferredHeight: (root.compact ? 48 : 56) * 1.1
            text: "Info"
            font.pixelSize: root.compact ? 17 : 20
            onClicked: {
                root.releaseHolds()
                operatingInfo.open()
            }
        }

        Item {
            Layout.fillHeight: true
            Layout.preferredHeight: 0
            visible: root.kind === "OPERATING"
        }
    }
}
