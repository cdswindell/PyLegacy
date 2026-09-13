import QtQuick
import QtQuick.Controls

Item {
    id: root

    property int minimumValue: 0
    property int maximumValue: 199
    property int value: 0
    property int pendingValue: value
    signal valueCommitted(int value)

    implicitWidth: 170
    implicitHeight: 520

    function clamp(v) {
        return Math.max(minimumValue, Math.min(maximumValue, v))
    }

    function displayValue() {
        return dragHandler.active ? pendingValue : value
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
        if (!dragHandler.active)
            pendingValue = value
    }

    Rectangle {
        anchors.horizontalCenter: rail.horizontalCenter
        anchors.top: rail.top
        anchors.bottom: rail.bottom
        width: 72
        radius: 18
        color: "#20242a"
        border.width: 1
        border.color: "#4e5662"
    }

    Repeater {
        model: 7
        Rectangle {
            required property int index
            width: index === 0 || index === 6 ? 28 : 18
            height: 2
            x: rail.x + rail.width + 10
            y: rail.y + index * (rail.height - height) / 6
            color: "#8b949f"
        }
    }

    Rectangle {
        id: rail
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 14
        radius: 7
        color: "#737b86"
    }

    Rectangle {
        id: handle
        width: 126
        height: 66
        radius: 13
        x: (root.width - width) / 2
        y: root.valueToY(root.displayValue())
        color: dragHandler.active ? "#f7f9fb" : "#e1e5ea"
        border.width: 3
        border.color: dragHandler.active ? "#5fb7f2" : "#9aa2ad"

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: 52
            height: 5
            radius: 2
            color: "#6b737e"
        }

        Text {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -18
            text: root.displayValue()
            font.pixelSize: 22
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
                    pendingValue = root.value
                    startY = root.valueToY(root.value)
                } else {
                    root.valueCommitted(root.pendingValue)
                }
            }

            onTranslationChanged: {
                if (active)
                    root.pendingValue = root.yToValue(startY + translation.y)
            }
        }
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: function(eventPoint) {
            const tappedValue = root.yToValue(eventPoint.position.y - handle.height / 2)
            root.pendingValue = tappedValue
            root.valueCommitted(tappedValue)
        }
    }
}
