import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var cab

    color: "#171a1f"
    radius: 18

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            ComboBox {
                id: targetPicker
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                model: cab.targetLabels
                currentIndex: cab.targetIndex
                font.pixelSize: 17
                onActivated: cab.selectTarget(currentIndex)

                contentItem: Text {
                    leftPadding: 14
                    rightPadding: 34
                    text: targetPicker.displayText
                    font: targetPicker.font
                    color: "#ffffff"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                background: Rectangle {
                    radius: 9
                    color: "#292e36"
                    border.width: 1
                    border.color: targetPicker.activeFocus ? "#78bff0" : "#626b78"
                }

                delegate: ItemDelegate {
                    required property int index
                    required property var modelData
                    width: targetPicker.width
                    height: 46
                    text: modelData
                    font.pixelSize: 16
                    highlighted: targetPicker.highlightedIndex === index
                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: "#ffffff"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle {
                        color: parent.highlighted ? "#246aa0" : "#292e36"
                    }
                }

                popup: Popup {
                    y: targetPicker.height
                    width: targetPicker.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 420)
                    padding: 1
                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: targetPicker.popup.visible ? targetPicker.delegateModel : null
                        currentIndex: targetPicker.highlightedIndex
                        ScrollIndicator.vertical: ScrollIndicator { }
                    }
                    background: Rectangle {
                        color: "#20242a"
                        border.color: "#626b78"
                        radius: 8
                    }
                }
            }

            CabButton {
                Layout.preferredWidth: 108
                Layout.preferredHeight: 54
                text: "Refresh"
                font.pixelSize: 16
                onClicked: cab.refreshRoster()
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            Label {
                Layout.fillWidth: true
                text: (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : "")
                color: "#f4f6f8"
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                font.pixelSize: 29
                font.bold: true
            }

            Label {
                Layout.fillWidth: true
                text: cab.scope + " " + cab.tmccId + "   " + (cab.direction || "—")
                color: "#aeb5bf"
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 16
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                radius: 12
                color: "#23272e"
                Column {
                    anchors.centerIn: parent
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: "SPEED"; color: "#9ea6b0"; font.pixelSize: 13 }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.speed; color: "white"; font.pixelSize: 30; font.bold: true }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                radius: 12
                color: "#23272e"
                Column {
                    anchors.centerIn: parent
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: "TARGET"; color: "#9ea6b0"; font.pixelSize: 13 }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.targetSpeed; color: "white"; font.pixelSize: 30; font.bold: true }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            CabButton {
                Layout.fillWidth: true
                text: "Reverse"
                selected: cab.direction.indexOf("REVERSE") >= 0
                onClicked: cab.setDirection("REVERSE")
            }

            CabButton {
                Layout.fillWidth: true
                text: "Forward"
                selected: cab.direction.indexOf("FORWARD") >= 0
                onClicked: cab.setDirection("FORWARD")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 500
            spacing: 18

            ColumnLayout {
                Layout.preferredWidth: 190
                Layout.fillHeight: true
                spacing: 4

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "THROTTLE   " + cab.speedMax
                    color: "#b9c0c9"
                    font.pixelSize: 15
                }

                VerticalThrottle {
                    id: throttle
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillHeight: true
                    Layout.preferredWidth: 170
                    minimumValue: 0
                    maximumValue: Math.max(1, cab.speedMax)
                    value: cab.targetSpeed
                    onValueCommitted: function(v) { cab.setSpeed(v) }
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "0"
                    color: "#b9c0c9"
                    font.pixelSize: 15
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    CabButton { Layout.fillWidth: true; text: "−5"; onClicked: cab.changeSpeed(-5) }
                    CabButton { Layout.fillWidth: true; text: "+5"; onClicked: cab.changeSpeed(5) }
                }

                CabButton {
                    Layout.fillWidth: true
                    text: "Bell"
                    onClicked: cab.bell()
                }

                HoldActionButton {
                    Layout.fillWidth: true
                    text: "Horn"
                    repeatWhileHeld: true
                    repeatInterval: 100
                    onHeldAction: cab.horn(true)
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    HoldActionButton {
                        Layout.fillWidth: true
                        text: "Brake"
                        repeatWhileHeld: true
                        repeatInterval: 250
                        onHeldAction: cab.brake(true)
                    }
                    HoldActionButton {
                        Layout.fillWidth: true
                        text: "Boost"
                        repeatWhileHeld: true
                        repeatInterval: 250
                        onHeldAction: cab.boost(true)
                    }
                }

                Label {
                    Layout.fillWidth: true
                    text: "OPERATIONS"
                    color: "#9ea6b0"
                    font.pixelSize: 13
                    font.bold: true
                    leftPadding: 2
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 8
                    rowSpacing: 7

                    Repeater {
                        model: cab.actionModel
                        FunctionButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 58
                            text: modelData.label
                            iconSource: modelData.iconSource
                            onClicked: cab.triggerAction(modelData.key)
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: 6
                    rowSpacing: 6
                    visible: cab.secondaryActionModel.length > 0

                    Repeater {
                        model: cab.secondaryActionModel
                        CabButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            text: modelData.label
                            font.pixelSize: 13
                            onClicked: cab.triggerAction(modelData.key)
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 4
                    columnSpacing: 6
                    rowSpacing: 6
                    visible: cab.tuningActionModel.length > 0

                    Repeater {
                        model: cab.tuningActionModel
                        CabButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 46
                            text: modelData.label
                            font.pixelSize: 12
                            onClicked: cab.triggerAction(modelData.key)
                        }
                    }

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        text: cab.speedLimit > 0 ? "Limit " + cab.speedLimit : "Speed Limit"
                        font.pixelSize: 12
                        onClicked: speedLimitPopup.open()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 135
                    radius: 12
                    color: "#e8ebef"
                    border.width: 1
                    border.color: cab.hasCustomArtwork ? "#3c8dbc" : "#aeb5bf"
                    clip: true

                    Image {
                        anchors.fill: parent
                        anchors.margins: 8
                        source: cab.artworkSource
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: false
                    }

                    Label {
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.margins: 8
                        visible: cab.hasCustomArtwork
                        text: "CUSTOM"
                        color: "#176fa8"
                        font.pixelSize: 11
                        font.bold: true
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 66
                        text: "STOP"
                        font.pixelSize: 22
                        font.bold: true
                        normalColor: "#8b2d32"
                        pressedColor: "#b43b42"
                        onClicked: cab.stop()
                    }

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 66
                        text: "Reset"
                        onClicked: cab.reset()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 54
            radius: 10
            color: "#23272e"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14

                Label { text: "RPM  " + cab.rpm; color: "#d9dde3"; font.pixelSize: 15 }
                Item { Layout.fillWidth: true }
                Label { text: "Labor  " + cab.labor; color: "#d9dde3"; font.pixelSize: 15 }
                Item { Layout.fillWidth: true }
                Label { text: "Momentum  " + cab.momentum; color: "#d9dde3"; font.pixelSize: 15 }
                Item { Layout.fillWidth: true }
                Label { text: "Smoke  " + cab.smoke; color: "#d9dde3"; font.pixelSize: 15 }
            }
        }
    }

    Popup {
        id: speedLimitPopup
        x: Math.round((root.width - width) / 2)
        y: Math.round((root.height - height) / 2)
        width: Math.min(440, root.width - 48)
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: 18
        onOpened: limitSpin.value = cab.speedLimit > 0 ? cab.speedLimit : Math.max(1, cab.targetSpeed)

        background: Rectangle {
            radius: 12
            color: "#252a31"
            border.width: 1
            border.color: "#697382"
        }

        contentItem: ColumnLayout {
            spacing: 14

            Label {
                Layout.fillWidth: true
                text: "Speed Limit"
                color: "white"
                font.pixelSize: 22
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
            }

            Label {
                Layout.fillWidth: true
                text: cab.speedLimit > 0 ? "Current limit: " + cab.speedLimit : "No speed limit set"
                color: "#c8ced6"
                font.pixelSize: 15
                horizontalAlignment: Text.AlignHCenter
            }

            SpinBox {
                id: limitSpin
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 180
                from: 1
                to: cab.commandSpeedMax
                editable: true
                font.pixelSize: 20
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                CabButton {
                    Layout.fillWidth: true
                    text: "Clear"
                    enabled: cab.speedLimit > 0
                    onClicked: {
                        cab.clearSpeedLimit()
                        speedLimitPopup.close()
                    }
                }

                CabButton {
                    Layout.fillWidth: true
                    text: "Set"
                    selected: true
                    onClicked: {
                        cab.setSpeedLimit(limitSpin.value)
                        speedLimitPopup.close()
                    }
                }
            }
        }
    }
}
