import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property int minimumValue: 0
    property int maximumValue: 199
    property int value: 0
    property int currentSpeed: value
    property int pendingValue: value
    property bool awaitingConfirmation: false
    property bool largeTouch: false
    property real thumbScale: 1
    property bool springReturn: false
    property int scaleStep: 20
    property int valueStep: 1
    property string handleCaption: springReturn ? "RELATIVE" : "TARGET"
    property string valueSuffix: ""
    property bool muted: false
    readonly property int scaleCount: Math.floor((maximumValue - minimumValue) / scaleStep) + 1
    readonly property bool dragging: pointer.pressed && !interactionCanceled
    readonly property real activeHeight: Math.max(1, height)
    signal valueCommitted(int value)
    signal gestureStarted()
    signal valueMoved(int value)
    signal gestureFinished()

    onVisibleChanged: if (!visible) cancelInteraction()
    onEnabledChanged: if (!enabled) cancelInteraction()
    onSpringReturnChanged: gestureFinished()

    property bool interactionCanceled: false
    function cancelInteraction() {
        interactionCanceled = true
        awaitingConfirmation = false
        confirmationTimer.stop()
        pendingValue = springReturn ? 0 : value
        if (springReturn)
            gestureFinished()
    }

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
        return clamp(minimumValue + valueStep * Math.round(frac * (maximumValue - minimumValue) / valueStep))
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
        id: trough

        anchors.horizontalCenter: rail.horizontalCenter
        anchors.top: rail.top
        height: rail.height
        width: Math.max(0, Math.min(46, root.width - 8))
        radius: 12
        gradient: Gradient {
            GradientStop { position: 0; color: "#10151c" }
            GradientStop { position: 1; color: "#303a46" }
        }
        border.width: 1
        border.color: "#4e5662"
    }

    Repeater {
        model: root.scaleCount
        Text {
            required property int index
            readonly property int stepValue: root.minimumValue + index * root.scaleStep
            anchors.right: parent.right
            anchors.rightMargin: 3
            y: root.valueToY(stepValue) + handle.height / 2 - height / 2
            text: stepValue
            font.pixelSize: root.largeTouch ? 14 : 11
            color: "#c1d8eb"
        }
    }

    Rectangle {
        id: rail
        x: Math.round(handle.x + handle.width * 0.35 - width / 2)
        anchors.top: parent.top
        height: root.activeHeight
        width: 8
        radius: 4
        color: "#10151b"
        border.color: "#536170"
    }

    Rectangle {
        id: rampBand
        objectName: "throttleRampBand"

        readonly property real currentY: root.valueToY(root.currentSpeed) + handle.height / 2
        readonly property real targetY: root.valueToY(root.value) + handle.height / 2

        anchors.horizontalCenter: rail.horizontalCenter
        y: Math.min(currentY, targetY)
        width: Math.max(0, trough.width - 2)
        height: Math.abs(targetY - currentY)
        visible: root.enabled && !root.springReturn && height > 0
        color: "#65451f"

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: rail.width
            height: parent.height
            color: "#402d18"
            border.color: "#d4a151"
        }
    }

    Repeater {
        model: root.scaleCount

        Rectangle {
            required property int index
            readonly property int stepValue: root.minimumValue + index * root.scaleStep
            width: root.largeTouch ? 10 : 7
            height: 2
            x: trough.x + trough.width - width / 2
            y: Math.round(root.valueToY(stepValue) + (handle.height - height) / 2)
            color: "#a9bfd3"
        }
    }

    Rectangle {
        anchors.horizontalCenter: rail.horizontalCenter
        width: 18
        height: Math.min(root.height, handle.height + 22)
        y: Math.max(0, Math.min(root.height - height, handle.y - 11))
        radius: 8
        color: "#111e28"
        border.color: "#698492"
    }

    ThrottleGrip {
        id: handle
        objectName: "throttleThumb"
        width: Math.max(0, Math.min((root.largeTouch ? 144 : 96) * root.thumbScale, root.width - (root.largeTouch ? 31 : 24)))
        height: Math.round((root.largeTouch ? 74 : 54) * 0.8) * root.thumbScale
        x: 2
        y: root.valueToY(root.displayValue())
        valueText: root.displayValue() + root.valueSuffix
        caption: root.handleCaption
        largeTouch: root.largeTouch
        muted: root.muted
        pressed: pointer.pressed
    }

    MouseArea {
        id: pointer
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        property real grabOffset: 0

        function moveTo(y) {
            const nextValue = root.yToValue(y - grabOffset)
            if (root.pendingValue !== nextValue) {
                root.pendingValue = nextValue
                root.valueMoved(nextValue)
            }
        }

        onPressed: function(event) {
            root.interactionCanceled = false
            const thumbY = root.valueToY(root.awaitingConfirmation ? root.pendingValue : root.value)
            const onThumb = event.x >= handle.x && event.x <= handle.x + handle.width
                && event.y >= thumbY && event.y <= thumbY + handle.height
            grabOffset = onThumb ? event.y - thumbY : handle.height / 2
            confirmationTimer.stop()
            root.awaitingConfirmation = false
            root.pendingValue = root.value
            if (root.springReturn)
                root.gestureStarted()
            moveTo(event.y)
        }
        onPositionChanged: function(event) {
            if (pressed && !root.interactionCanceled)
                moveTo(event.y)
        }
        onReleased: function(event) {
            if (root.interactionCanceled)
                return
            if (root.springReturn) {
                root.pendingValue = 0
                root.gestureFinished()
            } else {
                root.commit(root.yToValue(event.y - grabOffset))
            }
        }
        onCanceled: {
            root.pendingValue = root.value
            if (root.springReturn)
                root.gestureFinished()
        }
    }
}
