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
    property bool springReturn: false
    property int scaleStep: 20
    property int valueStep: 1
    property string handleCaption: springReturn ? "RELATIVE" : "TARGET"
    property string valueSuffix: ""
    property bool muted: false
    readonly property int scaleCount: Math.floor((maximumValue - minimumValue) / scaleStep) + 1
    readonly property bool dragging: pointer.pressed
    readonly property real activeHeight: Math.max(1, height)
    signal valueCommitted(int value)
    signal gestureStarted()
    signal valueMoved(int value)
    signal gestureFinished()

    onVisibleChanged: if (!visible && springReturn) gestureFinished()
    onEnabledChanged: if (!enabled && springReturn) gestureFinished()
    onSpringReturnChanged: gestureFinished()

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

    Rectangle {
        id: handle
        objectName: "throttleThumb"
        width: Math.max(0, Math.min(root.largeTouch ? 144 : 96, root.width - (root.largeTouch ? 31 : 24)))
        height: Math.round((root.largeTouch ? 74 : 54) * 0.8)
        radius: 14
        x: 2
        y: root.valueToY(root.displayValue())
        gradient: Gradient {
            GradientStop { position: 0; color: root.muted ? "#686c72" : pointer.pressed ? "#306881" : "#698ba0" }
            GradientStop { position: 0.45; color: root.muted ? "#45494f" : "#365a72" }
            GradientStop { position: 1; color: root.muted ? "#30343a" : "#203e52" }
        }
        border.color: root.muted ? "#969da5" : pointer.pressed ? "#5fb7f2" : "#8ba9bb"

        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 0.57
            height: parent.height - 10
            radius: 6
            color: root.muted ? "#272b31" : "#142838"
            border.color: "#698492"

            Column {
                anchors.centerIn: parent

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: text.length > 0
                    text: root.handleCaption
                    font.pixelSize: root.largeTouch ? 10 : 8
                    font.bold: true
                    color: "#d9edf9"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.displayValue() + root.valueSuffix
                    font.pixelSize: root.largeTouch ? 23 : 17
                    font.bold: true
                    color: "#ffffff"
                }
            }
        }

        Repeater {
            model: 6
            Rectangle {
                required property int index
                width: 2
                height: parent.height * 0.58
                anchors.verticalCenter: parent.verticalCenter
                x: index < 3 ? parent.width * 0.07 + index * 4
                             : parent.width * 0.81 + (index - 3) * 4
                radius: 1
                color: "#152a3a"
                border.color: "#587d93"
            }
        }
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
            if (pressed)
                moveTo(event.y)
        }
        onReleased: function(event) {
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
