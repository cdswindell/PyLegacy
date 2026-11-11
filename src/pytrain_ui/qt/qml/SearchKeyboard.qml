import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    objectName: "searchKeyboard"
    property string title: "Search"
    property var targetField: null
    property bool upperCase: false

    function openFor(field) {
        targetField = field
        entry.text = field.text
        open()
        entry.forceActiveFocus()
        entry.selectAll()
    }
    function publish() {
        if (targetField) {
            targetField.text = entry.text
            targetField.textEdited()
        }
    }
    function clearEntry() {
        entry.clear()
        publish()
    }
    function typeKey(key) {
        if (key === "⇧") {
            upperCase = !upperCase
            return
        }
        let start = entry.selectedText.length ? entry.selectionStart : entry.cursorPosition
        const end = entry.selectedText.length ? entry.selectionEnd : entry.cursorPosition
        if (key === "⌫" && start === end)
            start = Math.max(0, start - 1)
        const inserted = key === "⌫" ? "" : upperCase ? key.toUpperCase() : key
        entry.text = entry.text.slice(0, start) + inserted + entry.text.slice(end)
        entry.cursorPosition = start + inserted.length
        publish()
    }

    parent: Overlay.overlay
    width: Math.min(parent.width - 16, 760)
    x: (parent.width - width) / 2
    y: parent.height - height - 8
    modal: true
    focus: true
    padding: 12
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: "#102858"; radius: 12; border.color: "#7094c0" }

    component KeyboardKey: Button {
        id: key
        property bool holdActivated: false
        onPressedChanged: if (!pressed) holdActivated = false
        focusPolicy: Qt.NoFocus
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0
        Layout.preferredHeight: 56
        font.pixelSize: 22
        contentItem: Item {
            Text {
                anchors.fill: parent
                visible: key.text !== "⌫"
                text: key.text
                font: key.font
                color: "#ffffff"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            BackspaceIcon {
                anchors.fill: parent
                visible: key.text === "⌫"
                opacity: key.enabled ? 1 : 0.45
            }
        }
        background: Rectangle {
            radius: 7
            color: key.holdActivated ? Qt.darker("#69b7df", 1.45) : key.down ? "#69b7df" : key.highlighted ? "#246aa0" : "#334a6a"
            border.color: key.down ? "#d2f1ff" : "#718baa"
            border.width: key.down ? 2 : 1
        }
    }
    contentItem: ColumnLayout {
        spacing: 8
        RowLayout {
            Label { Layout.fillWidth: true; text: root.title; color: "white"; font.pixelSize: 24; font.bold: true }
            KeyboardKey { Layout.fillWidth: false; Layout.preferredWidth: 64; Layout.preferredHeight: 64; text: "×"; Accessible.name: "Close keyboard"; onClicked: root.close() }
        }
        TextField {
            id: entry
            objectName: "searchKeyboardEntry"
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            font.pixelSize: 24
            selectByMouse: true
            maximumLength: root.targetField ? root.targetField.maximumLength : 32767
            placeholderText: root.targetField ? root.targetField.placeholderText : ""
            onTextEdited: root.publish()
            onAccepted: root.close()
        }
        Repeater {
            model: ["1234567890", "qwertyuiop", "asdfghjkl", "⇧zxcvbnm⌫"]
            RowLayout {
                required property string modelData
                Layout.fillWidth: true
                spacing: 5
                Repeater {
                    model: modelData.split("")
                    KeyboardKey {
                        required property string modelData
                        text: root.upperCase ? modelData.toUpperCase() : modelData
                        Accessible.name: modelData === "⌫" ? "Backspace" : modelData === "⇧" ? "Shift" : text
                        onPressAndHold: {
                            if (modelData === "⌫") {
                                holdActivated = true
                                root.clearEntry()
                            }
                        }
                        onClicked: root.typeKey(modelData)
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            KeyboardKey { text: "Clear"; onClicked: root.clearEntry() }
            KeyboardKey { text: "Space"; onClicked: root.typeKey(" ") }
            KeyboardKey { text: "−"; onClicked: root.typeKey("-") }
            KeyboardKey { text: "Done"; highlighted: true; onClicked: root.close() }
        }
    }
}
