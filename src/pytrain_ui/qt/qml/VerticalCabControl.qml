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
    property bool momentumMode: false
    property bool presetMomentum: false
    readonly property int scaleFontSize: largeTouch ? 14 : 11
    readonly property int labelStep: maximumValue === 15 && (height - handle.height) / 15 < scaleFontSize + 5 ? 3 : 1
    readonly property bool dragging: pointer.pressed && !interactionCanceled
    readonly property real activeHeight: Math.max(1, height)

    signal valueMoved(int value)
    signal valueCommitted(int value)
    signal released()

    onVisibleChanged: if (!visible) cancelInteraction()
    onEnabledChanged: if (!enabled) cancelInteraction()
    property bool interactionCanceled: false
    function cancelInteraction() {
        interactionCanceled = true
        awaitingConfirmation = false
        confirmationTimer.stop()
        pendingValue = springReturn ? 0 : value
        released()
    }

    implicitWidth: 76
    implicitHeight: 420

    function scaleLabel(v) {
        if (!momentumMode)
            return String(v)
        if (v === minimumValue)
            return "Low"
        if (v === maximumValue)
            return "High"
        return presetMomentum ? "Med" : String(v)
    }

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
        width: Math.min(46, Math.round(root.width * 0.44))
        radius: 12
        gradient: Gradient {
            GradientStop { position: 0; color: "#10151c" }
            GradientStop { position: 1; color: "#303a46" }
        }
        border.width: 1
        border.color: "#4e5662"
    }

    Repeater {
        model: root.maximumValue - root.minimumValue + 1

        Item {
            required property int index
            readonly property int stepValue: root.minimumValue + index
            readonly property bool active: stepValue === root.displayValue()

            x: 0
            y: root.valueToY(stepValue) + handle.height / 2
            width: rail.x + rail.width / 2
            height: 0

            Rectangle {
                id: tick
                anchors.right: parent.right
                anchors.rightMargin: Math.min(22, root.width * 0.18)
                anchors.verticalCenter: parent.verticalCenter
                width: active || index % root.labelStep === 0 ? 6 : 3
                height: active ? 2 : 1
                color: active ? "#d6efff" : "#8198ae"
            }
            Text {
                anchors.left: parent.left
                anchors.leftMargin: 3
                anchors.verticalCenter: parent.verticalCenter
                visible: index % root.labelStep === 0
                text: root.scaleLabel(stepValue)
                font.pixelSize: root.scaleFontSize
                font.bold: active
                color: active ? "#ffffff" : "#b9cee4"
            }
        }
    }

    Rectangle {
        id: rail
        x: Math.round(root.width * 0.78 - width / 2) + 3
        anchors.top: parent.top
        height: root.activeHeight
        width: 8
        radius: 4
        color: "#10151b"
        border.color: "#536170"
    }

    ButtonFace {
        id: handle
        width: Math.round(Math.min(root.largeTouch ? 68 : 53, root.width * 0.60))
        height: Math.round(0.8 * (root.largeTouch ? 72 : 46))
        anchors.right: parent.right
        y: root.valueToY(root.displayValue())
        depressed: pointer.pressed
        selected: pointer.pressed

        Text {
            anchors.centerIn: parent
            text: root.scaleLabel(root.displayValue())
            font.pixelSize: text.length > 2 ? root.scaleFontSize : root.largeTouch ? 26 : 17
            font.bold: true
            color: "#ffffff"
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
            root.interactionCanceled = false
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
            if (pressed && !root.interactionCanceled)
                moveTo(event.y)
        }
        onReleased: {
            if (root.interactionCanceled)
                return
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
