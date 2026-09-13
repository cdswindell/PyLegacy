import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var cab
    spacing: 14

    Label {
        Layout.fillWidth: true
        text: (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : "")
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        font.pixelSize: 32
        font.bold: true
    }

    Label {
        Layout.fillWidth: true
        text: cab.scope + " " + cab.tmccId + "   " + (cab.direction || "—")
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: 18
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 12

        Label {
            text: "Speed\n" + cab.speed
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 26
        }

        Item { Layout.fillWidth: true }

        Label {
            text: "Target\n" + cab.targetSpeed
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 26
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10

        Button {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            text: "Reverse"
            font.pixelSize: 20
            font.bold: cab.direction.indexOf("REVERSE") >= 0
            onClicked: cab.setDirection("REVERSE")
        }

        Button {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            text: "Forward"
            font.pixelSize: 20
            font.bold: cab.direction.indexOf("FORWARD") >= 0
            onClicked: cab.setDirection("FORWARD")
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 370
        spacing: 18

        ColumnLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: 12

            Label {
                text: cab.speedMax
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: 54
                font.pixelSize: 18
            }
            Item { Layout.fillHeight: true }
            Label {
                text: Math.round(cab.speedMax / 2)
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: 54
                font.pixelSize: 18
            }
            Item { Layout.fillHeight: true }
            Label {
                text: "0"
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: 54
                font.pixelSize: 18
            }
        }

        Slider {
            id: throttle
            Layout.preferredWidth: 80
            Layout.fillHeight: true
            orientation: Qt.Vertical
            from: 0
            to: Math.max(1, cab.speedMax)
            stepSize: 1
            snapMode: Slider.SnapAlways
            value: cab.targetSpeed
            onPressedChanged: {
                if (!pressed)
                    cab.setSpeed(Math.round(value))
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 54
                    text: "-5"
                    font.pixelSize: 20
                    onClicked: cab.changeSpeed(-5)
                }
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 54
                    text: "+5"
                    font.pixelSize: 20
                    onClicked: cab.changeSpeed(5)
                }
            }

            Button {
                Layout.fillWidth: true
                Layout.preferredHeight: 58
                text: "Bell"
                font.pixelSize: 20
                onClicked: cab.bell()
            }

            Button {
                id: hornButton
                Layout.fillWidth: true
                Layout.preferredHeight: 62
                text: "Horn"
                font.pixelSize: 20
                onPressedChanged: cab.horn(pressed)
            }

            RowLayout {
                Layout.fillWidth: true
                Button {
                    id: brakeButton
                    Layout.fillWidth: true
                    Layout.preferredHeight: 62
                    text: "Brake"
                    font.pixelSize: 20
                    onPressedChanged: cab.brake(pressed)
                }
                Button {
                    id: boostButton
                    Layout.fillWidth: true
                    Layout.preferredHeight: 62
                    text: "Boost"
                    font.pixelSize: 20
                    onPressedChanged: cab.boost(pressed)
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 62
                    text: "STOP"
                    font.pixelSize: 21
                    font.bold: true
                    onClicked: cab.stop()
                }
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 62
                    text: "Reset"
                    font.pixelSize: 20
                    onClicked: cab.reset()
                }
            }
        }
    }

    Label {
        Layout.fillWidth: true
        text: "RPM " + cab.rpm + "   Labor " + cab.labor + "   Momentum " + cab.momentum + "   Smoke " + cab.smoke
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: 17
    }

    Timer {
        interval: 100
        repeat: true
        running: hornButton.pressed
        onTriggered: cab.horn(true)
    }

    Timer {
        interval: 250
        repeat: true
        running: boostButton.pressed
        onTriggered: cab.boost(true)
    }

    Timer {
        interval: 250
        repeat: true
        running: brakeButton.pressed
        onTriggered: cab.brake(true)
    }
}
