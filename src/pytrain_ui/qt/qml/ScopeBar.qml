import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string currentScope: ""
    signal scopePressed(string scope)

    radius: 9
    color: "#20242a"
    border.width: 1
    border.color: "#3d444f"

    RowLayout {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 4

        Repeater {
            model: ["ENGINE", "TRAIN", "SWITCH", "ACCESSORY", "ROUTE"]

            Rectangle {
                id: scopeButton
                required property string modelData
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 7
                color: scopeTap.pressed ? "#3c5265" : (root.currentScope === modelData ? "#246aa0" : "#303640")
                border.width: root.currentScope === modelData ? 2 : 1
                border.color: root.currentScope === modelData ? "#78bff0" : "#555e6b"

                Label {
                    anchors.centerIn: parent
                    width: parent.width - 6
                    text: scopeButton.modelData === "ACCESSORY" ? "Accessory" : scopeButton.modelData.charAt(0) + scopeButton.modelData.slice(1).toLowerCase()
                    color: "#f4f6f8"
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    font.pixelSize: 12
                    font.bold: root.currentScope === scopeButton.modelData
                }

                TapHandler {
                    id: scopeTap
                    onTapped: root.scopePressed(scopeButton.modelData)
                }
            }
        }
    }
}
