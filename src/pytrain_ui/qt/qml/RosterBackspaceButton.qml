import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root
    required property var field
    objectName: "rosterBackspaceButton"
    Layout.preferredWidth: 60
    Layout.minimumWidth: 60
    Layout.maximumWidth: 60
    Layout.preferredHeight: 54
    focusPolicy: Qt.NoFocus
    text: "⌫"
    Accessible.name: "Backspace search text"
    enabled: field && field.text.length > 0
    onClicked: {
        let start = field.selectedText.length ? field.selectionStart : field.cursorPosition
        const end = field.selectedText.length ? field.selectionEnd : field.cursorPosition
        if (start === end) start = Math.max(0, start - 1)
        field.text = field.text.slice(0, start) + field.text.slice(end)
        field.cursorPosition = start
        field.textEdited()
        field.forceActiveFocus()
    }
    contentItem: Text {
        text: root.text
        color: root.enabled ? "white" : "#7d8591"
        font.pixelSize: 28
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 8
        color: root.down ? "#68a9d0" : "#343a44"
        border.color: "#626b78"
    }
}
