import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string currentScope: ""
    property var lastScopeTap: null
    readonly property int buttonInset: 4
    implicitHeight: 84
    signal scopePressed(string scope, bool showKeypad)

    radius: 9
    color: "#20242a"
    border.width: 1
    border.color: "#3d444f"

    RowLayout {
        anchors.fill: parent
        anchors.margins: root.buttonInset
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
                gradient: SelectionGradient {
                    selected: scopeButton.activeScope
                    depressed: scopeTap.pressed
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

                ControlTapHandler {
                    id: scopeTap
                    longPressThreshold: 0.45
                    holdEnabled: true
                    onPressedChanged: {
                        if (pressed && root.lastScopeTap !== scopeTap) {
                            if (root.lastScopeTap)
                                root.lastScopeTap.cancelPendingTap()
                            root.lastScopeTap = scopeTap
                        }
                    }
                    onTappedOnce: root.scopePressed(scopeButton.modelData, false)
                    onTappedTwice: root.scopePressed(scopeButton.modelData, true)
                    onHeldGesture: root.scopePressed(scopeButton.modelData, true)
                }
            }
        }
    }
}
