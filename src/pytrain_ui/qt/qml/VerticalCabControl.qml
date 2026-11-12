import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property int minimumValue: 0
    property int maximumValue: 7
    property int value: 0
    property int pendingValue: value
    property bool awaitingConfirmation: false
    property bool springReturn: false
    property bool largeTouch: false
    readonly property bool dragging: pointer.pressed
    readonly property int tickCount: maximumValue <= 7 ? maximumValue + 1 : 5
    readonly property real activeHeight: Math.max(1, height)

    signal valueMoved(int value)
    signal valueCommitted(int value)
    signal released()

    implicitWidth: 76
    implicitHeight: 420

    function clamp(v) {
        return Math.max(minimumValue, Math.min(maximumValue, v))
    }

    function displayValue() {
        return pointer.pressed || awaitingConfirmation ? pendingValue : (springReturn ? 0 : value)
    }

    function valueToY(v) {
        const span = Math.max(1, maximumValue - minimumValue)
        const frac = (clamp(v) - minimumValue) / span
        return rail.y + frac * (rail.height - handle.height)
    }

    function yToValue(y) {
        const travel = Math.max(1, rail.height - handle.height)
        const position = Math.max(0, Math.min(1, (y - rail.y) / travel))
        return Math.round(minimumValue + position * (maximumValue - minimumValue))
    }

    onValueChanged: {
        if (awaitingConfirmation && value === pendingValue) {
            awaitingConfirmation = false
            confirmationTimer.stop()
        }
        if (!pointer.pressed && !springReturn && !awaitingConfirmation)
            pendingValue = clamp(value)
    }

    onMaximumValueChanged: {
        pendingValue = clamp(pendingValue)
    }

    onSpringReturnChanged: {
        awaitingConfirmation = false
        confirmationTimer.stop()
        pendingValue = springReturn ? 0 : clamp(value)
    }

    Timer {
        id: confirmationTimer
        interval: 900
        onTriggered: root.awaitingConfirmation = false
    }

    Rectangle {
        anchors.horizontalCenter: rail.horizontalCenter
        anchors.top: rail.top
        height: rail.height
        width: Math.min(root.largeTouch ? 64 : 42, root.width - 8)
        radius: 12
        color: "#20242a"
        border.width: 1
        border.color: "#4e5662"
    }

    Repeater {
        model: root.tickCount

        Rectangle {
            required property int index
            width: index === 0 || index === root.tickCount - 1 ? 16 : 10
            height: 1
            x: rail.x + rail.width + 5
            y: rail.y + index * (rail.height - height) / Math.max(1, root.tickCount - 1)
            color: "#8b949f"
        }
    }

    Rectangle {
        id: rail
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        height: root.activeHeight
        width: 10
        radius: 5
        color: "#737b86"
    }

    Rectangle {
        id: handle
        width: Math.max(24, Math.min(root.largeTouch ? 104 : 68, root.width - 6))
        height: root.largeTouch ? 72 : 46
        radius: 9
        x: (root.width - width) / 2
        y: root.valueToY(root.displayValue())
        color: pointer.pressed ? "#f7f9fb" : "#e1e5ea"
        border.width: 2
        border.color: pointer.pressed ? "#5fb7f2" : "#9aa2ad"

        Text {
            anchors.centerIn: parent
            text: root.displayValue()
            font.pixelSize: root.largeTouch ? 26 : 17
            font.bold: true
            color: "#171a1f"
        }

    }

    MouseArea {
        id: pointer
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        property real grabOffset: 0

        function moveTo(y) {
            const nextValue = root.yToValue(y - grabOffset)
            if (nextValue !== root.pendingValue) {
                root.pendingValue = nextValue
                root.valueMoved(nextValue)
            }
        }

        onPressed: function(event) {
            const currentValue = root.awaitingConfirmation ? root.pendingValue : (root.springReturn ? 0 : root.value)
            const thumbY = root.valueToY(currentValue)
            const onThumb = event.x >= handle.x && event.x <= handle.x + handle.width
                && event.y >= thumbY && event.y <= thumbY + handle.height
            grabOffset = onThumb ? event.y - thumbY : handle.height / 2
            confirmationTimer.stop()
            root.awaitingConfirmation = false
            root.pendingValue = currentValue
            moveTo(event.y)
        }
        onPositionChanged: function(event) {
            if (pressed)
                moveTo(event.y)
        }
        onReleased: {
            if (root.springReturn) {
                root.pendingValue = 0
            } else {
                root.awaitingConfirmation = root.pendingValue !== root.value
                if (root.awaitingConfirmation)
                    confirmationTimer.restart()
                root.valueCommitted(root.pendingValue)
            }
            root.released()
        }
        onCanceled: {
            root.pendingValue = root.springReturn ? 0 : root.value
            root.released()
        }
    }
}
