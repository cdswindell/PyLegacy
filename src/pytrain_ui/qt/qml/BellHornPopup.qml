import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root

    PanelMetrics { id: metrics }
    required property var cab
    required property real operatingButtonWidth
    required property int operatingButtonHeight
    property var actions: []
    readonly property int gap: 14
    readonly property real buttonWidth: (width - leftPadding - rightPadding - gap * 3) / 4

    function openOptions() {
        actions = cab.panelModel("bell_horn")
        open()
    }

    padding: 12
    width: Math.min(parent.width - 24, 4 * Math.ceil(operatingButtonWidth) + gap * 3 + leftPadding + rightPadding)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    modal: false
    focus: true
    closePolicy: Popup.CloseOnEscape

    background: Rectangle { color: "#102858"; radius: 12; border.color: "#626c79" }

    component OptionButton: Button {
        id: button
        property url artwork: ""
        property int buttonHeight: root.operatingButtonHeight
        property real faceWidth: root.buttonWidth
        Layout.preferredWidth: faceWidth
        Layout.minimumWidth: faceWidth
        Layout.maximumWidth: faceWidth
        Layout.preferredHeight: buttonHeight
        Layout.minimumHeight: buttonHeight
        Layout.maximumHeight: buttonHeight
        font.pixelSize: 24
        contentItem: Item {
            transform: Translate { y: button.down ? 2 : -1 }
            Text {
                anchors.fill: parent
                visible: !crossing.visible
                text: button.text
                font: button.font
                color: "#f5f7fa"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            Image {
                id: crossing
                anchors.centerIn: parent
                width: Math.min(parent.width, parent.height)
                height: width
                source: button.artwork
                visible: source.toString().length > 0 && status === Image.Ready
                fillMode: Image.PreserveAspectFit
                mipmap: true
            }
        }
        background: Item {
            Rectangle {
                anchors.fill: parent
                radius: 10
                color: "#07162c"
                border.color: "#102239"
            }
            Rectangle {
                anchors.fill: parent
                anchors.topMargin: button.down ? 3 : 0
                anchors.bottomMargin: button.down ? 0 : 4
                radius: 10
                border.color: button.activeFocus ? "#a4d8ff" : button.down ? "#72a3c5" : "#7c8fa7"
                gradient: Gradient {
                    GradientStop { position: 0; color: button.down ? "#213953" : "#5c6f86" }
                    GradientStop { position: 0.18; color: button.down ? "#2e4d69" : "#485a70" }
                    GradientStop { position: 1; color: button.down ? "#426482" : "#28384e" }
                }
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 2
                    radius: 8
                    color: "transparent"
                    border.color: button.down ? "#456782" : "#51677e"
                }
            }
        }
    }

    contentItem: ColumnLayout {
        spacing: root.gap
        Label {
            Layout.fillWidth: true
            text: root.cab.isSteam ? "Bell/Whistle Options" : "Bell/Horn Options"
            color: "#f5f7fa"
            font.pixelSize: 21
            font.bold: true
        }

        Repeater {
            model: ["Bell", "Horn"]
            ColumnLayout {
                id: section
                required property string modelData
                readonly property var commands: root.actions.filter(action => action.section === modelData)
                visible: commands.length > 0
                Layout.fillWidth: true
                Layout.topMargin: modelData === "Horn" && root.actions.some(action => action.section === "Bell") ? metrics.sectionGap : 0
                spacing: 7
                readonly property string rowTitle: modelData === "Horn" && root.cab.isSteam ? "Whistle" : modelData
                Label {
                    text: section.rowTitle
                    color: "#b5c9e5"
                    font.pixelSize: 15
                    font.bold: true
                }
                RowLayout {
                    spacing: root.gap
                    Repeater {
                        model: section.commands
                        OptionButton {
                            required property var modelData
                            readonly property string command: modelData.command
                            text: {
                                if (command === "RING_BELL") return "▶ / Ⅱ"
                                if (command === "BLOW_HORN_ONE") return "▶"
                                if (command === "CYCLE_BELL_TONE" || command === "CYCLE_HORN_TONE") return "Cycle\nTone"
                                return modelData.label
                            }
                            font.pixelSize: command === "RING_BELL" || command === "BLOW_HORN_ONE" ? 32 : 24
                            artwork: modelData.iconSource || ""
                            Accessible.name: section.rowTitle + ": " + modelData.label
                            onClicked: root.cab.triggerPanelCommand(command)
                        }
                    }
                }
            }
        }
        OptionButton {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 36
            faceWidth: root.buttonWidth + 16
            buttonHeight: 56
            text: "Close"
            onClicked: root.close()
        }
    }
}
