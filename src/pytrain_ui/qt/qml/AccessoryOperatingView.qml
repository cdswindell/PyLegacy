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
            visible: root.hasArtwork || (root.kind !== "OPERATING" && !!root.accessory.tmccId)
            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredHeight: root.hasArtwork ? Math.min(root.height * 0.23,
                    width / Math.max(1, Number(root.accessory.artworkAspectRatio || 3))) : 0

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

        RowLayout {
            Layout.fillWidth: true
            visible: root.kind === "OPERATING"

            Label {
                text: "Power"
                color: "#aeb7c2"
                font.pixelSize: 14
            }
            Label {
                text: root.accessory.powerState || "UNKNOWN"
                color: root.accessory.powerState === "ON" ? "#62d98b" :
                       root.accessory.powerState === "OFF" ? "#8fc9ef" : "#e9c46a"
                font.pixelSize: 16
                font.bold: true
            }
            Label {
                visible: root.accessory.powerStateAuthoritative === true
                text: "LCS"
                color: "#8fa2b5"
                font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
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

        ListView {
            id: operationList
            visible: root.kind === "OPERATING"
            ScrollBar.vertical: ListScrollBar {}
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            // Keep delegates alive during command feedback refreshes.
            readonly property var operations: root.accessory.operations || []
            model: operations.length

            delegate: Rectangle {
                id: operationRow
                required property int index
                readonly property var modelData: operationList.operations[index] || ({})
                readonly property var analog: modelData.analogInput || null
                readonly property bool vertical: analog !== null && analog.orientation === "vertical"
                readonly property bool operationActive: modelData.state === "ON"
                readonly property bool playbackRequested: modelData.animationRunning === true
                readonly property int playbackDuration: modelData.animationDuration || 0
                readonly property bool artworkActive: playbackDuration > 0 ? playbackTimer.running : operationActive
                readonly property string artworkSource: (artworkActive ? modelData.onImageSource : modelData.offImageSource)
                    || modelData.imageSource || ""
                readonly property bool gifArtwork: artworkSource.toLowerCase().endsWith(".gif")
                readonly property string artworkIdentity: (root.accessory.key || "") + "/" + (modelData.key || "")

                function startTimedPlayback() {
                    if (playbackRequested && playbackDuration > 0 && root.visible)
                        playbackTimer.restart()
                }

                Component.onCompleted: startTimedPlayback()
                onPlaybackRequestedChanged: startTimedPlayback()
                onArtworkIdentityChanged: {
                    playbackTimer.stop()
                    startTimedPlayback()
                }

                Timer {
                    id: playbackTimer
                    interval: Math.max(1, operationRow.playbackDuration)
                }
                width: ListView.view.width
                height: vertical ? 250 : Math.max(104, Math.min(190, Number(modelData.height || 120)))
                radius: 8
                color: "#272d35"
                border.width: 1
                border.color: "#4b5664"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 9
                    spacing: 10

                    Rectangle {
                        Layout.preferredWidth: Math.min(230, operationRow.width * 0.34)
                        Layout.fillHeight: true
                        visible: operationRow.artworkSource.length > 0
                        color: "#11151a"
                        radius: 6
                        clip: true

                        AnimatedImage {
                            anchors.fill: parent
                            source: operationRow.gifArtwork ? operationRow.artworkSource : ""
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            playing: root.visible &&
                                (operationRow.playbackDuration > 0 ? playbackTimer.running : operationRow.playbackRequested)
                            visible: operationRow.gifArtwork
                        }

                        Image {
                            anchors.fill: parent
                            source: operationRow.gifArtwork ? "" : operationRow.artworkSource
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            visible: !operationRow.gifArtwork
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 4

                        Label {
                            Layout.fillWidth: true
                            text: operationRow.modelData.label
                            color: "#f4f6f8"
                            font.pixelSize: 18
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: operationRow.analog === null
                            text: "TMCC " + operationRow.modelData.tmccId + " · " +
                                  (operationRow.modelData.behavior || "").replace("_", " ")
                            color: "#aeb7c2"
                            font.pixelSize: 12
                        }
                        Label {
                            visible: operationRow.analog === null
                            text: operationRow.modelData.state || ""
                            color: operationRow.modelData.state === "ON" ? "#62d98b" :
                                   operationRow.modelData.state === "OFF" ? "#8fc9ef" : "#e9c46a"
                            font.pixelSize: 13
                            font.bold: true
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
                            enabled: visible && !root.configurationVisible
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
