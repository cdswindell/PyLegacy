import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

DelayButton {
    id: clearButton
    Layout.fillWidth: true
    Layout.preferredWidth: 0
    Layout.minimumWidth: 0
    Layout.preferredHeight: 56
    text: "Clear"
    Accessible.name: "Hold for 3 seconds to clear this Base 3 record"
    delay: 3000
    onVisibleChanged: if (visible) checked = false
    font.bold: true
    font.pixelSize: 20
    contentItem: Text {
        text: clearButton.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font: clearButton.font
        color: clearButton.enabled ? "#ff6666" : "#858c96"
    }
    background: ButtonFace {
        depressed: clearButton.down
        focused: clearButton.activeFocus
        Rectangle {
            visible: clearButton.down && clearButton.progress > 0
            anchors.left: parent.left
            anchors.leftMargin: 3
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            width: Math.max(0, parent.width - 6) * clearButton.progress
            height: 5
            radius: 2
            color: clearButton.contentItem.color
        }
    }
}
