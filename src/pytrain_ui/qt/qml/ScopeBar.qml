import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string currentScope: ""
    implicitHeight: 84
    signal scopePressed(string scope, bool showKeypad)

    radius: 9
    color: "#20242a"
    border.width: 1
    border.color: "#3d444f"

    RowLayout {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 4

        Repeater {
            model: ["SWITCH", "ACCESSORY", "ROUTE", "TRAIN", "ENGINE"]

            Rectangle {
                id: scopeButton
                required property string modelData
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 0
                Layout.minimumWidth: 0
                Layout.minimumHeight: 76
                Layout.maximumHeight: 76
                Layout.preferredHeight: 76
                radius: 7
                readonly property bool activeScope: root.currentScope === modelData
                gradient: Gradient {
                    GradientStop {
                        position: 0
                        color: scopeTap.pressed ? "#101a25" : scopeButton.activeScope ? "#122c43" : "#405667"
                    }
                    GradientStop {
                        position: 0.22
                        color: scopeButton.activeScope ? "#1b4565" : "#2d4152"
                    }
                    GradientStop {
                        position: 0.65
                        color: scopeButton.activeScope ? "#245a80" : "#253748"
                    }
                    GradientStop {
                        position: 1
                        color: scopeTap.pressed ? "#5c8199" : scopeButton.activeScope ? "#397498" : "#263b50"
                    }
                }
                border.width: activeScope ? 2 : 1
                border.color: activeScope ? "#78bff0" : "#718a9c"

                Label {
                    anchors.centerIn: parent
                    width: parent.width - 6
                    text: scopeButton.modelData === "ACCESSORY" ? "Acc" : scopeButton.modelData.charAt(0) + scopeButton.modelData.slice(1).toLowerCase()
                    color: "#ffffff"
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    wrapMode: Text.NoWrap
                    font.pixelSize: 20
                    font.bold: true
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: 12
                }

                TapHandler {
                    id: scopeTap
                    property bool held: false
                    longPressThreshold: 0.45
                    onPressedChanged: if (pressed) held = false
                    onLongPressed: {
                        held = true
                        root.scopePressed(scopeButton.modelData, true)
                    }
                    onTapped: if (!held) root.scopePressed(scopeButton.modelData, false)
                }
            }
        }
    }
}
