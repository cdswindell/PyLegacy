import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    required property var controller
    required property var accessory
    readonly property string kind: accessory.kind || ""
    property bool motorsSelected: true

    onKindChanged: motorsSelected = true

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

    ColumnLayout {
        anchors.fill: parent
        visible: root.kind === "AMC2"
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            CabButton {
                Layout.fillWidth: true
                text: "Motors"
                selected: root.motorsSelected
                onClicked: root.motorsSelected = true
            }
            CabButton {
                Layout.fillWidth: true
                text: "Lights"
                selected: !root.motorsSelected
                onClicked: root.motorsSelected = false
            }
        }

        ListView {
            id: outputs
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: root.kind === "AMC2" ? (root.motorsSelected ? 2 : 4) : 0
            ScrollBar.vertical: ListScrollBar { id: outputScroll }

            delegate: Rectangle {
                id: outputRow
                required property int index
                readonly property int output: index + 1
                readonly property var values: (root.motorsSelected ? root.accessory.motors : root.accessory.lights) || []
                readonly property var observed: values[index] || ({level: 0, on: false})
                width: outputs.width - outputScroll.gutterWidth
                height: 116
                color: "#23303d"
                radius: 8

                function send(level) {
                    root.controller.setAmc2Output(root.accessory.key, root.motorsSelected, output, level)
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    Label {
                        text: (root.motorsSelected ? "Motor " : "Light ") + outputRow.output
                        color: "white"
                        font.bold: true
                        font.pixelSize: 20
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        CabButton {
                            text: "On"
                            Layout.preferredWidth: 68
                            selected: outputRow.observed.on
                            activateOnRelease: true
                            onClicked: outputRow.send(outputRow.observed.level || 100)
                        }
                        CabButton {
                            text: "Off"
                            Layout.preferredWidth: 68
                            selected: !outputRow.observed.on
                            activateOnRelease: true
                            onClicked: outputRow.send(0)
                        }
                        Slider {
                            id: level
                            Layout.fillWidth: true
                            from: 0
                            to: 100
                            stepSize: 5
                            snapMode: Slider.SnapAlways
                            value: outputRow.observed.level
                            onMoved: if (!pressed) outputRow.send(Math.round(value))
                            onPressedChanged: if (!pressed && value !== outputRow.observed.level)
                                outputRow.send(Math.round(value))
                        }
                        Label {
                            Layout.preferredWidth: 46
                            text: Math.round(level.value) + "%"
                            color: "#b5c9e5"
                        }
                    }
                }
            }
        }
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
