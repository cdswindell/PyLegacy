import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GridLayout {
    id: root
    required property var controller
    required property string accessoryKey
    required property bool compact
    property int activeMask: 0
    PanelMetrics { id: metrics }
    columns: 3
    rowSpacing: 8
    columnSpacing: 8
    implicitWidth: 420

    Frame {
        objectName: "uncouplerInstructions"
        Layout.columnSpan: 3
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.bottomMargin: 4
        padding: 10
        background: Rectangle {
            color: "#173765"
            border.color: "#5275a4"
            radius: 8
        }
        contentItem: Label {
            text: "This panel operates uncoupling tracks. Tap a button to send a one-second pulse to the corresponding uncoupler track."
            color: "#c3d3e4"
            font.pixelSize: root.compact ? 16 : 18
            wrapMode: Text.WordWrap
        }
    }

    Repeater {
        model: 8
        CabButton {
            required property int index
            objectName: "uncouplerKey" + (index + 1)
            selected: !!(root.activeMask & (1 << index))
            text: String(index + 1)
            Accessible.name: "Uncouple track " + text
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredWidth: 1
            Layout.preferredHeight: metrics.cabActionTileHeight(root.compact)
            font.pixelSize: 32
            activateOnRelease: true
            onClicked: root.controller.pulseUncoupler(root.accessoryKey, index + 1)
        }
    }
}
