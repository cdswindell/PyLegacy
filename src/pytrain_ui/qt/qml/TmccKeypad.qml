import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root

    property string title: "TMCC ID"
    property int maximumId: 98
    property alias entryText: tmccIdEntry.text
    property alias errorText: tmccKeypadError.text
    readonly property bool acceptableInput: tmccIdEntry.acceptableInput
    signal submitted(int tmccId)

    function openFor(value) {
        tmccIdEntry.text = /^[0-9]+$/.test(value) && value.length <= String(maximumId).length ? value : ""
        tmccKeypadError.text = ""
        open()
        tmccIdEntry.forceActiveFocus()
        tmccIdEntry.selectAll()
    }

    function submitTmccId() {
        if (tmccIdEntry.acceptableInput)
            submitted(Number(tmccIdEntry.text))
    }

    function enterTmccDigit(digit) {
        if (tmccIdEntry.selectedText.length > 0)
            tmccIdEntry.remove(tmccIdEntry.selectionStart, tmccIdEntry.selectionEnd)
        tmccIdEntry.insert(tmccIdEntry.cursorPosition, digit)
        tmccKeypadError.text = ""
    }

    function deleteTmccDigit() {
        if (tmccIdEntry.selectedText.length > 0)
            tmccIdEntry.remove(tmccIdEntry.selectionStart, tmccIdEntry.selectionEnd)
        else if (tmccIdEntry.cursorPosition > 0)
            tmccIdEntry.remove(tmccIdEntry.cursorPosition - 1, tmccIdEntry.cursorPosition)
        tmccKeypadError.text = ""
    }

    parent: Overlay.overlay
    width: Math.min(parent.width - 24, 340)
    x: Math.max(0, (parent.width - width) / 2)
    y: Math.max(0, (parent.height - height) / 2)
    modal: true
    focus: true
    padding: 16
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle {
        color: "#171a1f"
        radius: 14
        border.width: 1
        border.color: "#59616c"
    }
    contentItem: ColumnLayout {
        spacing: 10
        Label {
            Layout.fillWidth: true
            text: root.title
            color: "#f4f6f8"
            font.pixelSize: 22
            font.bold: true
        }
        TextField {
            id: tmccIdEntry
            Layout.fillWidth: true
            Layout.preferredHeight: 54
            placeholderText: "1–" + root.maximumId
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 28
            maximumLength: String(root.maximumId).length
            inputMethodHints: Qt.ImhDigitsOnly
            validator: IntValidator { bottom: 1; top: root.maximumId }
            onAccepted: root.submitTmccId()
            onTextEdited: tmccKeypadError.text = ""
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 8
            columnSpacing: 8
            Repeater {
                model: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "Del", "0", "↵"]
                CabButton {
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 58
                    text: modelData === "Del" ? "⌫" : modelData
                    font.pixelSize: 24
                    Accessible.name: modelData === "↵" ? "Enter" :
                                     modelData === "Del" ? "Backspace" : modelData
                    selected: modelData === "↵"
                    enabled: modelData !== "↵" || tmccIdEntry.acceptableInput
                    onClicked: {
                        if (modelData === "Del")
                            root.deleteTmccDigit()
                        else if (modelData === "↵")
                            root.submitTmccId()
                        else
                            root.enterTmccDigit(modelData)
                    }
                }
            }
        }
        Label {
            id: tmccKeypadError
            Layout.fillWidth: true
            visible: text.length > 0
            color: "#f0a35a"
            wrapMode: Text.WordWrap
            font.pixelSize: 14
        }
    }
}
