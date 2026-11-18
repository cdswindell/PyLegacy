import QtQuick
import QtQuick.Layouts

GridLayout {
    id: root
    required property var controller
    required property string accessoryKey
    required property bool compact
    PanelMetrics { id: metrics }
    columns: 3
    rowSpacing: 8
    columnSpacing: 8
    implicitWidth: 420

    Repeater {
        model: 8
        CabButton {
            required property int index
            objectName: "uncouplerKey" + (index + 1)
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
