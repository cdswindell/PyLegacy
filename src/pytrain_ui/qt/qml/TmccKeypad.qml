import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root

    property string title: "TMCC ID"
    property int minimumId: 1
    property int maximumId: 98
    property bool allowEmpty: false
    property alias entryText: tmccIdEntry.text
    property alias errorText: tmccKeypadError.text
    readonly property bool acceptableInput: tmccIdEntry.acceptableInput || (allowEmpty && !entryText.length)
    property bool showSetAddress: false
    signal submitted(int tmccId)
    signal setAddressRequested(int tmccId)

    function openFor(value) {
        tmccIdEntry.text = /^[0-9]+$/.test(value) && value.length <= String(maximumId).length ? value : ""
        tmccKeypadError.text = ""
        open()
        tmccIdEntry.forceActiveFocus()
        tmccIdEntry.selectAll()
    }

    function submitTmccId() {
        if (acceptableInput)
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
    width: Math.min(parent.width - 24, 560)
    x: Math.max(0, (parent.width - width) / 2)
    y: Math.max(0, (parent.height - height) / 2)
    modal: true
    focus: true
    padding: 16
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    component KeyButton: Button {
        id: keyControl
        focusPolicy: Qt.NoFocus
        font.pixelSize: 28

        contentItem: Item {
            Text {
                anchors.fill: parent
                visible: keyControl.text !== "⌫"
                text: keyControl.text
                font: keyControl.font
                color: keyControl.enabled ? "#ffffff" : "#7d8591"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
            BackspaceIcon {
                anchors.fill: parent
                visible: keyControl.text === "⌫"
                opacity: keyControl.enabled ? 1 : 0.45
            }
        }
        background: Rectangle {
            radius: 10
            color: keyControl.down ? (keyControl.text === "⌫" ? "#68a9d0" : "#355775") : (keyControl.highlighted ? "#246aa0" : "#343a44")
            border.width: keyControl.highlighted ? 2 : 1
            border.color: keyControl.highlighted ? "#78bff0" : "#626b78"
        }
    }

    background: Rectangle {
        color: "#102858"
        radius: 14
        border.width: 1
        border.color: "#59616c"
    }
    contentItem: ColumnLayout {
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Label {
                Layout.fillWidth: true
                text: root.title
                color: "#f4f6f8"
                font.pixelSize: 26
                font.bold: true
            }
            KeyButton {
                Layout.preferredWidth: 64
                Layout.preferredHeight: 64
                text: "×"
                Accessible.name: "Close keypad"
                onClicked: root.close()
            }
        }
        TextField {
            id: tmccIdEntry
            Layout.fillWidth: true
            Layout.preferredHeight: 76
            placeholderText: root.minimumId + "–" + root.maximumId
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 28
            maximumLength: String(root.maximumId).length
            inputMethodHints: Qt.ImhDigitsOnly
            validator: IntValidator { bottom: root.minimumId; top: root.maximumId }
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
                // Standard Button consumes the pointer gesture and clicks on release.
                // Closing a popup on press lets the remaining gesture hit its catalog.
                KeyButton {
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 74
                    text: modelData === "Del" ? "⌫" : modelData
                    font.pixelSize: 28
                    Accessible.name: modelData === "↵" ? "Enter" :
                                     modelData === "Del" ? "Backspace" : modelData
                    highlighted: modelData === "↵"
                    enabled: modelData !== "↵" || root.acceptableInput
                    onPressAndHold: {
                        if (modelData === "Del") {
                            tmccIdEntry.clear()
                            tmccKeypadError.text = ""
                        }
                    }
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
        RowLayout {
            Layout.fillWidth: true
            // Review this gap when standardizing keypad action-row spacing.
            Layout.topMargin: 12
            spacing: 18
            Item { Layout.fillWidth: true; visible: !root.showSetAddress }
            KeyButton {
                Layout.fillWidth: root.showSetAddress
                Layout.preferredWidth: root.showSetAddress ? 0 : 150
                Layout.preferredHeight: 58
                text: "Close"
                font.pixelSize: 22
                onClicked: root.close()
            }
            Item { Layout.fillWidth: true; visible: !root.showSetAddress }
            KeyButton {
                visible: root.showSetAddress
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 58
                text: "Set Address"
                font.pixelSize: 22
                highlighted: true
                enabled: root.acceptableInput && Number(root.entryText) !== 99
                onClicked: root.setAddressRequested(Number(root.entryText))
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
