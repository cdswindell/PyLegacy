import QtQuick

Item {
    id: root

    property int minimumValue: 0
    property int maximumValue: 7
    property int value: 0
    property int pendingValue: value
    property bool springReturn: false
    readonly property bool dragging: dragHandler.active

    signal valueMoved(int value)
    signal valueCommitted(int value)
    signal released()

    implicitWidth: 76
    implicitHeight: 420

    function clamp(v) {
        return Math.max(minimumValue, Math.min(maximumValue, v))
    }

    function displayValue() {
        return dragHandler.active ? pendingValue : (springReturn ? 0 : value)
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
        if (!dragHandler.active && !springReturn)
            pendingValue = clamp(value)
    }

    onMaximumValueChanged: {
        pendingValue = clamp(pendingValue)
    }

    Rectangle {
        anchors.horizontalCenter: rail.horizontalCenter
        anchors.top: rail.top
        anchors.bottom: rail.bottom
        width: Math.min(42, root.width - 8)
        radius: 12
        color: "#20242a"
        border.width: 1
        border.color: "#4e5662"
    }

    Repeater {
        model: root.maximumValue <= 7 ? root.maximumValue + 1 : 5

        Rectangle {
            required property int index
            width: index === 0 || index === parent.count - 1 ? 16 : 10
            height: 1
            x: rail.x + rail.width + 5
            y: rail.y + index * (rail.height - height) / Math.max(1, parent.count - 1)
            color: "#8b949f"
        }
    }

    Rectangle {
        id: rail
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 10
        radius: 5
        color: "#737b86"
    }

    Rectangle {
        id: handle
        width: Math.max(48, Math.min(68, root.width - 6))
        height: 46
        radius: 9
        x: (root.width - width) / 2
        y: root.valueToY(root.displayValue())
        color: dragHandler.active ? "#f7f9fb" : "#e1e5ea"
        border.width: 2
        border.color: dragHandler.active ? "#5fb7f2" : "#9aa2ad"

        Text {
            anchors.centerIn: parent
            text: root.displayValue()
            font.pixelSize: 17
            font.bold: true
            color: "#171a1f"
        }

        DragHandler {
            id: dragHandler
            target: null
            xAxis.enabled: false
            yAxis.enabled: true
            property real startY: 0

            onActiveChanged: {
                if (active) {
                    root.pendingValue = root.springReturn ? 0 : root.value
                    startY = root.valueToY(root.pendingValue)
                } else {
                    root.valueCommitted(root.pendingValue)
                    root.released()
                    if (root.springReturn)
                        root.pendingValue = 0
                }
            }

            onTranslationChanged: {
                if (!active)
                    return
                const nextValue = root.yToValue(startY + translation.y)
                if (nextValue !== root.pendingValue) {
                    root.pendingValue = nextValue
                    root.valueMoved(nextValue)
                }
            }
        }
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: function(eventPoint) {
            const nextValue = root.yToValue(eventPoint.position.y - handle.height / 2)
            root.pendingValue = nextValue
            root.valueMoved(nextValue)
            root.valueCommitted(nextValue)
            root.released()
            if (root.springReturn)
                root.pendingValue = 0
        }
    }
}
