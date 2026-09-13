import QtQuick
import QtQuick.Controls

Item {
    id: root

    property int minimumValue: 0
    property int maximumValue: 199
    property int value: 0
    signal valueCommitted(int value)

    implicitWidth: 150
    implicitHeight: 520

    function clamp(v) {
        return Math.max(minimumValue, Math.min(maximumValue, v))
    }

    function valueToY(v) {
        const span = Math.max(1, maximumValue - minimumValue)
        const frac = (clamp(v) - minimumValue) / span
        return track.y + (1.0 - frac) * (track.height - handle.height)
    }

    function yToValue(y) {
        const travel = Math.max(1, track.height - handle.height)
        const frac = 1.0 - Math.max(0, Math.min(1, (y - track.y) / travel))
        return Math.round(minimumValue + frac * (maximumValue - minimumValue))
    }

    Rectangle {
        id: track
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 34
        radius: 17
        color: "#2f343b"
        border.width: 1
        border.color: "#666c75"

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: Math.max(0, handle.y + handle.height / 2 - track.y)
            radius: 17
            color: "#3d78a8"
            opacity: 0.8
        }
    }

    Rectangle {
        id: handle
        width: 116
        height: 62
        radius: 16
        x: (root.width - width) / 2
        y: root.valueToY(root.value)
        color: dragHandler.active ? "#f2f4f7" : "#d8dce2"
        border.width: 2
        border.color: "#7d848d"

        Text {
            anchors.centerIn: parent
            text: root.value
            font.pixelSize: 24
            font.bold: true
            color: "#20242a"
        }

        DragHandler {
            id: dragHandler
            target: null
            xAxis.enabled: false
            yAxis.enabled: true
            property real startY: 0

            onActiveChanged: {
                if (active) {
                    startY = root.valueToY(root.value)
                } else {
                    root.valueCommitted(root.value)
                }
            }

            onTranslationChanged: {
                if (active)
                    root.value = root.yToValue(startY + translation.y)
            }
        }
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: function(eventPoint) {
            root.value = root.yToValue(eventPoint.position.y - handle.height / 2)
            root.valueCommitted(root.value)
        }
    }
}
