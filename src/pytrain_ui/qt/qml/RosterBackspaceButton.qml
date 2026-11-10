import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root
    required property var field
    objectName: "rosterBackspaceButton"
    Layout.preferredWidth: 84
    Layout.minimumWidth: 84
    Layout.maximumWidth: 84
    Layout.preferredHeight: 84
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
    contentItem: BackspaceIcon { opacity: root.enabled ? 1 : 0.45 }
    background: Rectangle {
        radius: 8
        color: root.down ? "#68a9d0" : "#343a44"
        border.color: "#626b78"
    }
}
