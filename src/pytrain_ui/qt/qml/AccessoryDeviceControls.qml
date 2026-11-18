import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    PanelMetrics { id: metrics }
    required property var controller
    required property var accessory
    required property bool compact
    property bool showTmccTab: true
    property bool fillTmccKeypad: false
    property var infoController
    property bool infoSelected: false
    property int controlTabIndex: 0
    readonly property string kind: accessory.kind || ""
    readonly property int infoTabIndex: kind === "AMC2" ? 2 : 1
    readonly property bool infoHasUnsavedChanges: deviceInfo.hasUnsavedChanges
    readonly property bool infoEditorOpen: deviceInfo.editorOpen
    signal tabRequested(int index)

    TabBar {
        id: deviceTabs
        objectName: root.kind === "AMC2" ? "amc2Tabs" : root.kind === "SENSOR" ? "sensorTabs" : "tmccAccessoryTabs"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.topMargin: metrics.accessoryTabInset
        visible: root.kind === "AMC2" || root.kind === "SENSOR" || (root.kind === "TMCC" && root.showTmccTab)
        width: parent.width * 2 / 3
        height: 56
        spacing: 6
        padding: 0
        currentIndex: root.infoSelected ? root.infoTabIndex : root.controlTabIndex
        background: Item {}
        Repeater {
            id: deviceTabRepeater
            model: root.kind === "AMC2" ? ["Motors", "Lights", "Info"]
                : root.kind === "SENSOR" ? ["Action", "Info"] : ["Controls", "Info"]
            CabPageTab {
                id: deviceTab
                required property int index
                required property string modelData
                objectName: modelData === "Info" ? "accessoryDeviceInfoTab" : "accessoryDeviceControlTab" + index
                width: (deviceTabs.availableWidth - deviceTabs.spacing * (deviceTabs.count - 1)) / deviceTabs.count
                height: deviceTabs.height
                y: 0
                text: modelData
                onClicked: {
                    // Navigation owns selection so canceled edits retain their tab and draft.
                    deviceTabs.currentIndex = Qt.binding(() => root.infoSelected ? root.infoTabIndex : root.controlTabIndex)
                    root.tabRequested(index)
                }
            }
        }
    }

    readonly property real contentTop: {
        if (!deviceTabs.visible)
            return 0
        const tab = deviceTabRepeater.itemAt(root.infoSelected ? root.infoTabIndex : root.controlTabIndex)
        return metrics.accessoryTabContentGap + (tab && tab.parent
            ? tab.parent.mapToItem(root, 0, tab.y + tab.height).y
            : deviceTabs.y + deviceTabs.height)
    }

    StateInfoView {
        id: deviceInfo
        objectName: "accessoryDeviceStateInfo"
        anchors.fill: parent
        anchors.topMargin: root.contentTop
        visible: root.infoSelected
        controller: root.infoController
        showCloseButton: false
        scrollable: root.kind !== "AMC2"
    }

    ListView {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.contentTop
        anchors.bottom: parent.bottom
        visible: root.kind === "SENSOR" && !root.infoSelected
        spacing: 14
        clip: true
        model: visible ? root.accessory.sequences || [] : []
        ScrollBar.vertical: ListScrollBar { id: sensorScroll }

        delegate: CabButton {
            id: actionButton
            required property var modelData
            width: ListView.view.width - sensorScroll.gutterWidth
            height: 60
            leftPadding: 10
            rightPadding: 10
            readonly property var directions: /^(.*) R➟L[/](.*) L➟R$/.exec(modelData.label)
            readonly property var actionLabels: directions
                ? ["Right ➟ Left: " + directions[1], "Left ➟ Right: " + directions[2]]
                : [modelData.label]
            text: actionLabels.join(". ")
            Accessible.role: Accessible.Button
            Accessible.name: text
            contentItem: Item {
                RowLayout {
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(parent.width, 580)
                    spacing: 12
                    Repeater {
                        model: actionButton.actionLabels
                        Text {
                            required property string modelData
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: 1
                            Layout.fillHeight: true
                            text: modelData
                            font: actionButton.font
                            color: actionButton.enabled ? "#ffffff" : "#7d8591"
                            horizontalAlignment: actionButton.directions ? Text.AlignLeft : Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }
                    }
                }
            }
            selected: root.accessory.sequence === modelData.value
            activateOnRelease: true
            onClicked: root.controller.setSensorSequence(root.accessory.key, modelData.value)
        }
    }

    Amc2Controls {
        anchors.fill: parent
        anchors.topMargin: root.contentTop
        visible: root.kind === "AMC2" && !root.infoSelected
        controller: root.controller
        accessory: root.accessory
        motorsSelected: root.controlTabIndex === 0
    }

    RowLayout {
        id: tmcc
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.contentTop
        anchors.bottom: parent.bottom
        visible: root.kind === "TMCC" && !root.infoSelected
        spacing: 8
        property string heldKey: ""
        property int heldAddress: 0
        property int step: 0

        function command(name, data) {
            root.controller.tmccCommand(root.accessory.key, root.accessory.tmccId, name, data)
        }

        function beginThrottle() {
            heldKey = root.accessory.key
            heldAddress = root.accessory.tmccId
        }

        function moveThrottle(value) {
            if (!heldAddress)
                return
            step = value
            root.controller.tmccCommand(heldKey, heldAddress, "RELATIVE_SPEED", value)
        }

        function endThrottle() {
            const key = heldKey
            const address = heldAddress
            heldAddress = 0
            heldKey = ""
            step = 0
            if (address)
                root.controller.tmccCommand(key, address, "RELATIVE_SPEED", 0)
        }

        onVisibleChanged: if (!visible) endThrottle()
        onEnabledChanged: if (!enabled) endThrottle()

        Timer {
            interval: 200
            repeat: true
            running: tmcc.heldAddress > 0 && tmcc.step !== 0
            onTriggered: root.controller.tmccCommand(tmcc.heldKey, tmcc.heldAddress, "RELATIVE_SPEED", tmcc.step)
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0

            AccessoryCabKeys {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: root.fillTmccKeypad ? parent.height
                    : Math.min(parent.height, rows * metrics.cabActionTileHeight(root.compact) + (rows - 1) * rowSpacing)
                tmccId: root.accessory.tmccId || 0
                accScope: true
                keyLabels: root.accessory.cabKeyLabels || ({})
                compact: root.compact
                onCommandRequested: (name, data) => tmcc.command(name, data)
            }
        }

        Rectangle {
            objectName: "tmccAccessoryThrottle"
            Layout.preferredWidth: Math.max(108, Math.min(164, tmcc.width * 0.22))
            Layout.fillHeight: true
            border.color: "#496b9d"
            color: "#102858"
            radius: 10

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6

                Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    color: "#c3d3e4"
                    text: "Current Speed"
                }

                Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    color: "#e4f6ff"
                    text: (tmcc.step > 0 ? "+" : "") + tmcc.step
                    font.pixelSize: 36
                    font.bold: true
                }

                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    text: "◀ Dir ▶"
                    Accessible.name: "Toggle Direction"
                    onClicked: tmcc.command("TOGGLE_DIRECTION", 0)
                }

                RelativeStepButton { delta: 1 }

                VerticalThrottle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    minimumValue: -5
                    maximumValue: 5
                    scaleStep: !root.showTmccTab && height < 170 ? 5 : 1
                    springReturn: true
                    value: tmcc.step
                    onGestureStarted: tmcc.beginThrottle()
                    onValueMoved: moved => tmcc.moveThrottle(moved)
                    onGestureFinished: tmcc.endThrottle()
                }

                RelativeStepButton { delta: -1 }
            }
        }
    }

    component RelativeStepButton: CabButton {
        id: stepButton
        required property int delta
        Layout.fillWidth: true
        Layout.preferredHeight: 52
        text: delta > 0 ? "+" : "−"
        font.pixelSize: 32
        onClicked: {
            tmcc.beginThrottle()
            tmcc.moveThrottle(delta)
            if (!isPointerPressed())
                tmcc.endThrottle()
        }
        onReleased: if (tmcc.step === delta) tmcc.endThrottle()
        onPressCanceled: if (tmcc.step === delta) tmcc.endThrottle()
    }
}
