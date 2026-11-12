import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property int minimumValue: 0
    property int maximumValue: 199
    property int value: 0
    property int pendingValue: value
    property bool awaitingConfirmation: false
    property bool largeTouch: false
    readonly property bool dragging: pointer.pressed
    readonly property real activeHeight: Math.max(1, height)
    signal valueCommitted(int value)

    implicitWidth: 112
    implicitHeight: 520

    function clamp(v) {
        return Math.max(minimumValue, Math.min(maximumValue, v))
    }

    function displayValue() {
        return (pointer.pressed || awaitingConfirmation) ? pendingValue : value
    }

    function commit(v) {
        pendingValue = clamp(v)
        awaitingConfirmation = true
        confirmationTimer.restart()
        valueCommitted(pendingValue)
    }

    function valueToY(v) {
        const span = Math.max(1, maximumValue - minimumValue)
        const frac = (clamp(v) - minimumValue) / span
        return rail.y + (1.0 - frac) * (rail.height - handle.height)
    }

    function yToValue(y) {
        const travel = Math.max(1, rail.height - handle.height)
        const frac = 1.0 - Math.max(0, Math.min(1, (y - rail.y) / travel))
        return Math.round(minimumValue + frac * (maximumValue - minimumValue))
    }

    onValueChanged: {
        if (pointer.pressed)
            return
        if (awaitingConfirmation) {
            if (value === pendingValue) {
                awaitingConfirmation = false
                confirmationTimer.stop()
            }
            return
        }
        pendingValue = value
    }

    Timer {
        id: confirmationTimer
        interval: 900
        repeat: false
        onTriggered: {
            root.awaitingConfirmation = false
            root.pendingValue = root.value
        }
    }

    Rectangle {
        anchors.horizontalCenter: rail.horizontalCenter
        anchors.top: rail.top
        height: rail.height
        width: 48
        radius: 12
        gradient: Gradient {
            GradientStop { position: 0; color: "#10151c" }
            GradientStop { position: 1; color: "#303a46" }
        }
        border.width: 1
        border.color: "#4e5662"
    }

    Repeater {
        model: 7
        Rectangle {
            required property int index
            width: index === 0 || index === 6 ? 24 : 16
            height: 2
            x: rail.x + rail.width + 8
            y: rail.y + index * (rail.height - height) / 6
            color: "#8b949f"
        }
    }

    Rectangle {
        id: rail
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        height: root.activeHeight
        width: 8
        radius: 4
        color: "#10151b"
        border.color: "#536170"
    }

    Rectangle {
        id: handle
        objectName: "throttleThumb"
        width: Math.min(root.largeTouch ? 144 : 96, root.width - 8)
        height: Math.round((root.largeTouch ? 96 : 62) * 0.8)
        radius: 9
        x: (root.width - width) / 2
        y: root.valueToY(root.displayValue())
        gradient: Gradient {
            GradientStop { position: 0; color: pointer.pressed ? "#f2f9ff" : "#d3dce5" }
            GradientStop { position: 0.45; color: "#aab8c6" }
            GradientStop { position: 0.5; color: "#7c8fa1" }
            GradientStop { position: 1; color: "#43576a" }
        }
        border.width: 2
        border.color: pointer.pressed ? "#5fb7f2" : "#9aa2ad"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 4
            radius: 5
            color: "transparent"
            border.color: "#e2eaf2"
            opacity: 0.5
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            y: root.largeTouch ? 6 : 3
            text: "TARGET"
            font.pixelSize: root.largeTouch ? 12 : 8
            font.bold: true
            color: "#263c50"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            y: root.largeTouch ? 22 : 13
            text: root.displayValue()
            font.pixelSize: root.largeTouch ? 30 : 19
            font.bold: true
            color: "#14212e"
        }
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: root.largeTouch ? 7 : 4
            spacing: 2
            Repeater {
                model: 3
                Rectangle {
                    width: Math.min(root.largeTouch ? 72 : 48, handle.width - 20)
                    height: 2
                    radius: 1
                    color: "#23394c"
                    Rectangle {
                        y: 2
                        width: parent.width
                        height: 1
                        color: "#c3d2df"
                        opacity: 0.6
                    }
                }
            }
        }

    }

    MouseArea {
        id: pointer
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        property real grabOffset: 0

        onPressed: function(event) {
            const thumbY = root.valueToY(root.awaitingConfirmation ? root.pendingValue : root.value)
            const onThumb = event.x >= handle.x && event.x <= handle.x + handle.width
                && event.y >= thumbY && event.y <= thumbY + handle.height
            grabOffset = onThumb ? event.y - thumbY : handle.height / 2
            confirmationTimer.stop()
            root.awaitingConfirmation = false
            root.pendingValue = root.yToValue(event.y - grabOffset)
        }
        onPositionChanged: function(event) {
            if (pressed)
                root.pendingValue = root.yToValue(event.y - grabOffset)
        }
        onReleased: function(event) {
            root.commit(root.yToValue(event.y - grabOffset))
        }
        onCanceled: root.pendingValue = root.value
    }
}
