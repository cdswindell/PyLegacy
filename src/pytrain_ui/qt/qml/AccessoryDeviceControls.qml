import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    PanelMetrics { id: metrics }
    required property var controller
    required property var accessory
    required property bool compact
    readonly property string kind: accessory.kind || ""
    TabBar {
        id: sensorTabs
        objectName: "sensorTabs"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.topMargin: metrics.accessoryTabInset
        visible: root.kind === "SENSOR"
        width: parent.width / 3
        height: 56
        padding: 0
        background: Item {}
        CabPageTab {
            id: actionTab
            text: "Action"
            height: sensorTabs.height
        }
    }

    ListView {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: sensorTabs.top
        // The tab style can offset the visible button inside the TabBar.
        anchors.topMargin: metrics.accessoryTabContentGap + (actionTab.parent
            ? actionTab.parent.mapToItem(sensorTabs, 0, actionTab.y + actionTab.height).y
            : sensorTabs.height)
        anchors.bottom: parent.bottom
        visible: root.kind === "SENSOR"
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
        visible: root.kind === "AMC2"
        controller: root.controller
        accessory: root.accessory
    }

    RowLayout {
        id: tmcc
        anchors.fill: parent
        visible: root.kind === "TMCC"
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
                anchors.fill: parent
                tmccId: root.accessory.tmccId || 0
                accScope: true
                compact: root.compact
                onCommandRequested: (name, data) => tmcc.command(name, data)
            }
        }

        Rectangle {
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
                    scaleStep: 1
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
