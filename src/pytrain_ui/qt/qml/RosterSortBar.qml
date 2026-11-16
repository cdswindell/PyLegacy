import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    required property string selectedKey
    required property bool compact
    property var keys: ["roadName", "roadNumber", "tmccId"]
    signal selected(string key)

    Layout.fillWidth: true
    spacing: 8

    Repeater {
        model: ["Name", "Road #", "TMCC ID"]
        delegate: CabButton {
            required property string modelData
            required property int index

            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredWidth: 1
            Layout.preferredHeight: root.compact ? 54 : 84
            text: modelData
            font.pixelSize: 26
            selected: root.selectedKey === root.keys[index]
            onClicked: root.selected(root.keys[index])
        }
    }
}
