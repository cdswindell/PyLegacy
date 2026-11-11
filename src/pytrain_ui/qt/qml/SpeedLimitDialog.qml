import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    objectName: "speedLimitDialog"

    property int maximumSpeed: 199
    property bool hasExistingLimit: false
    property string targetText: ""
    property alias entryText: speedEntry.text
    readonly property bool acceptableInput: speedEntry.text.length > 0 && speedEntry.acceptableInput
    signal limitSubmitted(int value)
    signal limitCleared()

    function openFor(currentLimit, maximum, target) {
        maximumSpeed = Math.max(1, maximum)
        targetText = target
        hasExistingLimit = currentLimit > 0 && currentLimit !== 255
        speedEntry.text = hasExistingLimit ? String(Math.min(maximumSpeed, currentLimit)) : ""
        limitSlider.value = hasExistingLimit ? Number(speedEntry.text) : maximumSpeed
        open()
        speedEntry.forceActiveFocus()
        speedEntry.selectAll()
    }

    function syncEntry() {
        if (speedEntry.acceptableInput)
            limitSlider.value = Number(speedEntry.text)
    }

    function enterDigit(digit) {
        if (speedEntry.selectedText.length)
            speedEntry.remove(speedEntry.selectionStart, speedEntry.selectionEnd)
        speedEntry.insert(speedEntry.cursorPosition, digit)
        syncEntry()
    }

    function deleteDigit() {
        if (speedEntry.selectedText.length)
            speedEntry.remove(speedEntry.selectionStart, speedEntry.selectionEnd)
        else if (speedEntry.cursorPosition > 0)
            speedEntry.remove(speedEntry.cursorPosition - 1, speedEntry.cursorPosition)
        syncEntry()
    }

    function commit() {
        if (!acceptableInput)
            return
        limitSubmitted(Number(speedEntry.text))
        close()
    }

    parent: Overlay.overlay
    width: Math.min(parent.width - 24, 440)
    height: Math.min(parent.height - 24, implicitHeight)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 16
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    component EditorButton: Button {
        id: button
        focusPolicy: Qt.NoFocus
        font.pixelSize: 22
        contentItem: Item {
            Text {
                anchors.fill: parent
                visible: button.text !== "⌫"
                text: button.text
                font: button.font
                color: button.enabled ? "#ffffff" : "#7d8591"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            BackspaceIcon {
                anchors.fill: parent
                visible: button.text === "⌫"
                opacity: button.enabled ? 1 : 0.45
            }
        }
        background: Rectangle {
            radius: 9
            color: !button.enabled ? "#242930" : button.down ? "#4d5968" : button.highlighted ? "#246aa0" : "#343a44"
            border.width: button.highlighted ? 2 : 1
            border.color: button.highlighted ? "#78bff0" : "#626b78"
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
            Label {
                Layout.fillWidth: true
                text: "Set Speed Limit"
                color: "#f4f6f8"
                font.pixelSize: 26
                font.bold: true
            }
            EditorButton {
                Layout.preferredWidth: 64
                Layout.preferredHeight: 64
                text: "×"
                Accessible.name: "Close speed limit"
                onClicked: root.close()
            }
        }
        Label {
            Layout.fillWidth: true
            text: root.targetText
            color: "#b5bfcb"
            font.pixelSize: 18
            elide: Text.ElideRight
        }
        Label {
            objectName: "speedLimitRange"
            Layout.fillWidth: true
            text: (root.maximumSpeed === 31 ? "TMCC" : "Legacy") + " speed limit: 1–" + root.maximumSpeed
            color: "#b5bfcb"
            font.pixelSize: 18
        }
        TextField {
            id: speedEntry
            objectName: "speedLimitEntry"
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            placeholderText: !root.hasExistingLimit ? "No limit" : "1–" + root.maximumSpeed
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 30
            maximumLength: String(root.maximumSpeed).length
            inputMethodHints: Qt.ImhDigitsOnly
            validator: IntValidator { bottom: 1; top: root.maximumSpeed }
            selectByMouse: true
            onTextEdited: root.syncEntry()
            onAccepted: root.commit()
        }
        Slider {
            id: limitSlider
            objectName: "speedLimitSlider"
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            from: 1
            to: root.maximumSpeed
            stepSize: 1
            snapMode: Slider.SnapAlways
            onMoved: {
                speedEntry.text = String(Math.round(value))
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 8
            columnSpacing: 8
            Repeater {
                model: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "Set"]
                EditorButton {
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 58
                    text: modelData
                    font.pixelSize: 26
                    highlighted: modelData === "Set"
                    enabled: modelData !== "Set" || root.acceptableInput
                    Accessible.name: modelData === "⌫" ? "Backspace" : modelData === "Set" ? "Set speed limit" : modelData
                    onClicked: {
                        if (modelData === "⌫") root.deleteDigit()
                        else if (modelData === "Set") root.commit()
                        else root.enterDigit(modelData)
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            text: speedEntry.text.length && !speedEntry.acceptableInput ?
                  "Enter a speed from 1 to " + root.maximumSpeed : ""
            color: "#f0a35a"
            font.pixelSize: 16
            Layout.preferredHeight: 20
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 24
            EditorButton {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: 0
                Layout.preferredHeight: 54
                text: "Clear"
                font.pixelSize: 20
                enabled: root.hasExistingLimit
                onClicked: {
                    root.limitCleared()
                    root.close()
                }
            }
            EditorButton {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: 0
                Layout.preferredHeight: 54
                text: "Close"
                font.pixelSize: 20
                onClicked: root.close()
            }
        }
    }
}
