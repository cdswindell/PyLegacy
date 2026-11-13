import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root

    PanelMetrics { id: metrics }
    objectName: "stateValueDialog"
    property string kind: "Mom"
    property bool legacy: true
    property int draftValue: -1
    property string targetText: ""
    property string currentText: ""
    readonly property var titles: ({Mom: "Momentum", Brake: "Train Brake", Smoke: "Smoke",
                                    Effort: "Effort (Labor)", RPM: "RPM"})
    readonly property string titleText: titles[kind]
    readonly property bool hasSetButton: kind === "Brake" || kind === "Effort" || kind === "RPM"
    readonly property bool sliderAvailable: hasSetButton || (kind === "Mom" && legacy)
    readonly property var choices: {
        if (kind === "Mom") return ["Low", "Medium", "High"]
        if (kind === "Smoke") return legacy ? ["Off", "Low", "Medium", "High"] : ["Off", "On"]
        return []
    }
    signal valueSubmitted(string kind, int value)

    function description(value) {
        if (value === null || value === undefined || value < 0)
            return "Not reported"
        if (kind === "Mom")
            return value === 0 ? "Low (0)" : value === 7 ? "High (7)" : "Med (" + value + ")"
        if (hasSetButton)
            return String(value)
        return choices[value]
    }
    function openFor(field, isLegacy, current, target, medium) {
        kind = field
        legacy = isLegacy
        targetText = target
        draftValue = current === null || current === undefined ? -1 : current
        currentText = description(draftValue)
        valueSlider.value = kind === "Mom" ? (medium ?? 3) : Math.max(0, draftValue)
        open()
    }
    function choiceValue(index) {
        return kind === "Mom" ? [0, legacy ? Math.round(valueSlider.value) : 3, 7][index] : index
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
        font.bold: true
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
        background: ButtonFace {
            depressed: button.down
            selected: button.highlighted
            focused: button.activeFocus
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
                Accessible.name: "Close " + root.titleText
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
            visible: root.choices.length > 0
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
                        root.commit()
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: root.sliderAvailable
            Label {
                Layout.alignment: Qt.AlignHCenter
                text: root.kind === "Mom" ? "Medium level: " + valueSlider.value + "  (1–6)" :
                      (root.draftValue < 0 ? "Choose a value" : String(root.draftValue)) + "  (0–" + valueSlider.to + ")"
                color: "white"
                font.pixelSize: 26
            }
            Slider {
                id: valueSlider
                objectName: "stateValueSlider"
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                from: root.kind === "Mom" ? 1 : 0
                to: root.kind === "Effort" ? 31 : root.kind === "Mom" ? 6 : 7
                stepSize: 1
                snapMode: Slider.SnapAlways
                onMoved: if (root.hasSetButton) root.draftValue = Math.round(value)
                onPressedChanged: if (pressed && root.hasSetButton) root.draftValue = Math.round(value)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: metrics.footerGap
            spacing: 24
            EditorButton {
                visible: root.hasSetButton
                text: root.kind === "Brake" ? "Off" : "Default"
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                onClicked: {
                    root.draftValue = root.kind === "Effort" ? 12 : 0
                    root.commit()
                }
            }
            Item { visible: !root.hasSetButton; Layout.fillWidth: true }
            EditorButton {
                text: "Close"
                Layout.fillWidth: root.hasSetButton
                Layout.preferredWidth: root.hasSetButton ? 0 : 150
                onClicked: root.close()
            }
            Item { visible: !root.hasSetButton; Layout.fillWidth: true }
            EditorButton {
                visible: root.hasSetButton
                objectName: "stateValueSet"
                text: "Set"
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                highlighted: true
                enabled: root.draftValue >= 0
                onClicked: root.commit()
            }
        }
    }
}
