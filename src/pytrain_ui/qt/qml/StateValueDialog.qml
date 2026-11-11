import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    objectName: "stateValueDialog"
    property string kind: "Mom"
    property bool legacy: true
    property int draftValue: -1
    property string targetText: ""
    property string currentText: ""
    readonly property string titleText: kind === "Mom" ? "Momentum" : kind === "Brake" ? "Train Brake" : "Smoke"
    readonly property bool sliderAvailable: kind === "Brake" || (kind === "Mom" && legacy)
    readonly property var choices: kind === "Mom" ? ["Low", "Med", "High"] : legacy ? ["Off", "Low", "Medium", "High"] : ["Off", "On"]
    signal valueSubmitted(string kind, int value)

    function description(value) {
        if (value === null || value === undefined || value < 0)
            return "Not reported"
        if (kind === "Mom")
            return value === 0 ? "Low (0)" : value === 7 ? "High (7)" : "Med (" + value + ")"
        if (kind === "Brake")
            return String(value)
        return choices[value]
    }
    function openFor(field, isLegacy, current, target) {
        kind = field
        legacy = isLegacy
        targetText = target
        draftValue = current === null || current === undefined ? -1 : current
        currentText = description(draftValue)
        valueSlider.value = Math.max(0, draftValue)
        open()
    }
    function choiceValue(index) {
        return kind === "Mom" ? [0, 3, 7][index] : index
    }
    function selected(index) {
        if (kind === "Mom" && index === 1)
            return draftValue > 0 && draftValue < 7
        return draftValue === choiceValue(index)
    }
    function commit() {
        if (draftValue < 0)
            return
        valueSubmitted(kind, draftValue)
        close()
    }

    parent: Overlay.overlay
    width: Math.min(parent.width - 24, 560)
    height: Math.min(parent.height - 24, implicitHeight)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 20
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle {
        color: "#102858"
        radius: 14
        border.color: "#78bff0"
    }
    component EditorButton: Button {
        id: button
        font.pixelSize: 24
        focusPolicy: Qt.NoFocus
        implicitHeight: 72
        Layout.minimumWidth: 0
        contentItem: Text {
            text: button.text
            font: button.font
            color: button.enabled ? "white" : "#7d8591"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 9
            color: button.down ? "#397bad" : button.highlighted ? "#006fa5" : "#303e58"
            border.color: button.highlighted ? "#78d5ff" : "#667b9c"
            border.width: button.highlighted ? 2 : 1
            opacity: button.enabled ? 1 : 0.5
        }
    }
    contentItem: ColumnLayout {
        spacing: 20
        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: root.titleText
                font.pixelSize: 28
                font.bold: true
                color: "white"
            }
            EditorButton {
                text: "×"
                Layout.preferredWidth: 64
                Accessible.name: "Cancel " + root.titleText
                onClicked: root.close()
            }
        }
        Label {
            Layout.fillWidth: true
            text: root.targetText
            color: "#b5c9e5"
            font.pixelSize: 20
        }
        Label {
            objectName: "currentStateValue"
            text: "Current: " + root.currentText
            color: "white"
            font.pixelSize: 24
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.kind !== "Brake"
            spacing: 10
            Repeater {
                model: root.choices
                EditorButton {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    text: modelData
                    highlighted: root.selected(index)
                    onClicked: {
                        root.draftValue = root.choiceValue(index)
                        if (root.kind === "Smoke")
                            root.commit()
                        else
                            valueSlider.value = root.draftValue
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: root.sliderAvailable
            Label {
                Layout.alignment: Qt.AlignHCenter
                text: root.draftValue < 0 ? "Choose a value: 0–7" : String(root.draftValue) + "  (0–7)"
                color: "white"
                font.pixelSize: 26
            }
            Slider {
                id: valueSlider
                objectName: "stateValueSlider"
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                from: 0
                to: 7
                stepSize: 1
                snapMode: Slider.SnapAlways
                onMoved: root.draftValue = Math.round(value)
                onPressedChanged: if (pressed) root.draftValue = Math.round(value)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 12
            spacing: 8
            EditorButton {
                visible: root.kind === "Brake"
                text: "Off"
                Layout.preferredWidth: 112
                onClicked: {
                    root.draftValue = 0
                    root.commit()
                }
            }
            EditorButton {
                text: "Cancel"
                Layout.preferredWidth: 150
                onClicked: root.close()
            }
            Item { Layout.fillWidth: true; Layout.minimumWidth: 32 }
            EditorButton {
                visible: root.kind !== "Smoke"
                objectName: "stateValueSet"
                text: "Set"
                Layout.preferredWidth: 150
                highlighted: true
                enabled: root.draftValue >= 0
                onClicked: root.commit()
            }
        }
    }
}
