import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root
    property string entryText: ""
    property int maximumId: 9999
    objectName: "rosterSetButton"
    Layout.preferredWidth: 84
    Layout.minimumWidth: 84
    Layout.maximumWidth: 84
    Layout.preferredHeight: 84
    text: "Set"
    focusPolicy: Qt.NoFocus
    Accessible.name: "Select TMCC ID"
    enabled: /^[0-9]+$/.test(entryText) && Number(entryText) > 0 && Number(entryText) <= maximumId
    contentItem: Text {
        text: root.text
        color: root.enabled ? "white" : "#7d8591"
        font.pixelSize: 24
        font.bold: root.enabled
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: ButtonFace {
        depressed: root.down
        selected: false
        focused: root.activeFocus
    }
}
