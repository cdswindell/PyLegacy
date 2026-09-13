import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    required property var cab
    spacing: 16

    Label {
        Layout.fillWidth: true
        text: (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : "")
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: 34
        font.bold: true
    }

    Label {
        Layout.fillWidth: true
        text: cab.scope + " " + cab.tmccId + "   " + (cab.direction || "—")
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: 20
    }

    RowLayout {
        Layout.fillWidth: true
        Label { text: "Speed " + cab.speed; font.pixelSize: 30 }
        Item { Layout.fillWidth: true }
        Label { text: "Target " + cab.targetSpeed; font.pixelSize: 30 }
    }

    RowLayout {
        Layout.fillWidth: true
        Button { Layout.fillWidth: true; text: "Reverse"; onClicked: cab.setDirection("REVERSE") }
        Button { Layout.fillWidth: true; text: "Forward"; onClicked: cab.setDirection("FORWARD") }
    }

    Slider {
        id: throttle
        Layout.fillWidth: true
        from: 0
        to: 199
        stepSize: 1
        value: cab.targetSpeed
        onPressedChanged: if (!pressed) cab.setSpeed(Math.round(value))
    }

    RowLayout {
        Layout.fillWidth: true
        Button { text: "-5"; onClicked: cab.changeSpeed(-5) }
        Item { Layout.fillWidth: true }
        Button { text: "+5"; onClicked: cab.changeSpeed(5) }
    }

    Label {
        Layout.fillWidth: true
        text: "RPM " + cab.rpm + "   Labor " + cab.labor + "   Momentum " + cab.momentum
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: 18
    }
}
