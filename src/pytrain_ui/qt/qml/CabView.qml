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
            Layout.minimumHeight: 390
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
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    CabButton {
                        Layout.fillWidth: true
                        text: "−5"
                        onClicked: cab.changeSpeed(-5)
                    }
                    CabButton {
                        Layout.fillWidth: true
                        text: "+5"
                        onClicked: cab.changeSpeed(5)
                    }
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
                    spacing: 10

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

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 68
                        text: "STOP"
                        font.pixelSize: 22
                        font.bold: true
                        normalColor: "#8b2d32"
                        pressedColor: "#b43b42"
                        onClicked: cab.stop()
                    }

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 68
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
}
