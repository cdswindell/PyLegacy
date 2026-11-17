import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    required property string selectedKey
    required property bool compact
    required property ListView roster
    property var keys: ["tmccId", "roadName", "roadNumber"]
    signal selected(string key)

    function selectAndScrollToTop(key) {
        selected(key)
        Qt.callLater(() => {
            roster.cancelFlick()
            roster.forceLayout()
            roster.positionViewAtBeginning()
        })
    }

    Layout.fillWidth: true
    spacing: 8

    Repeater {
        model: ["TMCC ID", "Name", "Road #"]
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
            distinguishDoubleClick: true
            activateOnHold: true
            onClicked: root.selected(root.keys[index])
            onDoubleClicked: root.selectAndScrollToTop(root.keys[index])
            onGestureHeld: root.selectAndScrollToTop(root.keys[index])
        }
    }
}
