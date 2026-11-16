import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    required property var controller
    required property var accessory
    readonly property string kind: accessory.kind || ""
    ListView {
        anchors.fill: parent
        visible: root.kind === "SENSOR"
        spacing: 8
        clip: true
        model: visible ? root.accessory.sequences || [] : []
        ScrollBar.vertical: ListScrollBar { id: sensorScroll }

        delegate: CabButton {
            required property var modelData
            width: ListView.view.width - sensorScroll.gutterWidth
            height: 60
            text: modelData.label
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
        spacing: 12
        property string heldKey: ""
        property int heldAddress: 0
        property int step: 0

        function command(name, data) {
            root.controller.tmccCommand(root.accessory.key, root.accessory.tmccId, name, data)
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

        VerticalThrottle {
            Layout.fillHeight: true
            Layout.preferredWidth: Math.min(176, tmcc.width * 0.30)
            minimumValue: -5
            maximumValue: 5
            scaleStep: 1
            springReturn: true
            value: tmcc.step
            onGestureStarted: {
                tmcc.heldKey = root.accessory.key
                tmcc.heldAddress = root.accessory.tmccId
            }
            onValueMoved: moved => {
                if (!tmcc.heldAddress)
                    return
                tmcc.step = moved
                root.controller.tmccCommand(tmcc.heldKey, tmcc.heldAddress, "RELATIVE_SPEED", moved)
            }
            onGestureFinished: tmcc.endThrottle()
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 3
            columnSpacing: 8
            rowSpacing: 8

            Repeater {
                model: [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
                CabButton {
                    required property int modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 1
                    Layout.column: modelData === 0 ? 1 : (modelData - 1) % 3
                    Layout.row: modelData === 0 ? 3 : Math.floor((modelData - 1) / 3)
                    text: String(modelData)
                    activateOnRelease: true
                    onClicked: tmcc.command("NUMERIC", modelData)
                }
            }

            Repeater {
                model: [
                    ["Boost", "BOOST"], ["Direction", "TOGGLE_DIRECTION"], ["Brake", "BRAKE"],
                    ["Aux 1", "AUX1_OPT_ONE"], ["Aux 2", "AUX2_OPT_ONE"],
                    ["Front Coupler", "FRONT_COUPLER"], ["Rear Coupler", "REAR_COUPLER"]
                ]
                CabButton {
                    required property int index
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 1
                    Layout.column: index < 5 ? index % 3 : index - 5
                    Layout.row: index < 5 ? 4 + Math.floor(index / 3) : 6
                    text: modelData[0]
                    font.pixelSize: 17
                    repeatWhileHeld: index === 0 || index === 2
                    onClicked: tmcc.command(modelData[1], 0)
                }
            }
        }
    }
}
