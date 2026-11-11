import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    required property var cab
    required property real operatingButtonWidth
    required property int operatingButtonHeight
    property point artworkBottom: Qt.point(0, 0)
    property var actions: []
    readonly property int gap: 8
    readonly property real buttonWidth: (width - leftPadding - rightPadding - gap * 3) / 4

    function openBelow(item) {
        artworkBottom = item.mapToItem(parent, 0, item.height)
        actions = cab.panelModel("bell_horn")
        open()
    }

    padding: 12
    width: Math.min(parent.width - 24, 4 * Math.ceil(operatingButtonWidth) + gap * 3 + leftPadding + rightPadding)
    x: Math.max(12, Math.min(artworkBottom.x, parent.width - width - 12))
    y: Math.max(12, Math.min(artworkBottom.y + gap, parent.height - height - 12))
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle { color: "#102858"; radius: 12; border.color: "#626c79" }

    component OptionButton: Button {
        id: button
        property url artwork: ""
        Layout.preferredWidth: root.buttonWidth
        Layout.minimumWidth: root.buttonWidth
        Layout.maximumWidth: root.buttonWidth
        Layout.preferredHeight: root.operatingButtonHeight
        Layout.minimumHeight: root.operatingButtonHeight
        Layout.maximumHeight: root.operatingButtonHeight
        font.pixelSize: 19
        contentItem: Item {
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
        background: Rectangle {
            radius: 8
            color: button.down ? "#5c9fc6" : "#303640"
            border.color: "#626b78"
        }
    }

    contentItem: ColumnLayout {
        spacing: root.gap
        Label {
            Layout.fillWidth: true
            text: "Bell/Horn Options"
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
                spacing: 4
                Label {
                    text: section.modelData
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
                            font.pixelSize: command === "RING_BELL" || command === "BLOW_HORN_ONE" ? 26 : 19
                            artwork: modelData.iconSource || ""
                            Accessible.name: section.modelData + ": " + modelData.label
                            onClicked: root.cab.triggerPanelCommand(command)
                        }
                    }
                }
            }
        }
        OptionButton {
            Layout.alignment: Qt.AlignHCenter
            text: "Close"
            onClicked: root.close()
        }
    }
}
