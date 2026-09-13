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
        anchors.margins: 22
        spacing: 14

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Label {
                Layout.fillWidth: true
                text: (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : "")
                color: "#f4f6f8"
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                font.pixelSize: 31
                font.bold: true
            }

            Label {
                Layout.fillWidth: true
                text: cab.scope + " " + cab.tmccId + "   " + (cab.direction || "—")
                color: "#aeb5bf"
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 17
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 78
                radius: 12
                color: "#23272e"

                Column {
                    anchors.centerIn: parent
                    spacing: 0
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: "SPEED"; color: "#9ea6b0"; font.pixelSize: 13 }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.speed; color: "white"; font.pixelSize: 31; font.bold: true }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 78
                radius: 12
                color: "#23272e"

                Column {
                    anchors.centerIn: parent
                    spacing: 0
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: "TARGET"; color: "#9ea6b0"; font.pixelSize: 13 }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.targetSpeed; color: "white"; font.pixelSize: 31; font.bold: true }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Button {
                Layout.fillWidth: true
                Layout.preferredHeight: 62
                text: "Reverse"
                font.pixelSize: 20
                font.bold: cab.direction.indexOf("REVERSE") >= 0
                onClicked: cab.setDirection("REVERSE")
            }

            Button {
                Layout.fillWidth: true
                Layout.preferredHeight: 62
                text: "Forward"
                font.pixelSize: 20
                font.bold: cab.direction.indexOf("FORWARD") >= 0
                onClicked: cab.setDirection("FORWARD")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 410
            spacing: 22

            ColumnLayout {
                Layout.preferredWidth: 180
                Layout.fillHeight: true
                spacing: 4

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: cab.speedMax
                    color: "#b9c0c9"
                    font.pixelSize: 16
                }

                VerticalThrottle {
                    id: throttle
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillHeight: true
                    Layout.preferredWidth: 160
                    minimumValue: 0
                    maximumValue: Math.max(1, cab.speedMax)
                    value: cab.targetSpeed
                    onValueCommitted: function(v) { cab.setSpeed(v) }
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "0"
                    color: "#b9c0c9"
                    font.pixelSize: 16
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 58
                        text: "−5"
                        font.pixelSize: 21
                        onClicked: cab.changeSpeed(-5)
                    }
                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 58
                        text: "+5"
                        font.pixelSize: 21
                        onClicked: cab.changeSpeed(5)
                    }
                }

                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 62
                    text: "Bell"
                    font.pixelSize: 20
                    onClicked: cab.bell()
                }

                HoldActionButton {
                    Layout.fillWidth: true
                    text: "Horn"
                    repeatWhileHeld: true
                    repeatInterval: 100
                    font.bold: pressed
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
                        font.bold: pressed
                        onHeldAction: cab.brake(true)
                    }

                    HoldActionButton {
                        Layout.fillWidth: true
                        text: "Boost"
                        repeatWhileHeld: true
                        repeatInterval: 250
                        font.bold: pressed
                        onHeldAction: cab.boost(true)
                    }
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 68
                        text: "STOP"
                        font.pixelSize: 22
                        font.bold: true
                        onClicked: cab.stop()
                    }

                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 68
                        text: "Reset"
                        font.pixelSize: 20
                        onClicked: cab.reset()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            radius: 10
            color: "#23272e"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16

                Label { text: "RPM  " + cab.rpm; color: "#d9dde3"; font.pixelSize: 16 }
                Item { Layout.fillWidth: true }
                Label { text: "Labor  " + cab.labor; color: "#d9dde3"; font.pixelSize: 16 }
                Item { Layout.fillWidth: true }
                Label { text: "Momentum  " + cab.momentum; color: "#d9dde3"; font.pixelSize: 16 }
                Item { Layout.fillWidth: true }
                Label { text: "Smoke  " + cab.smoke; color: "#d9dde3"; font.pixelSize: 16 }
            }
        }
    }
}
