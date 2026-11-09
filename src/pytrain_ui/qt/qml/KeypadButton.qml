import QtQuick
import QtQuick.Controls

CabButton {
    id: root
    implicitWidth: 52
    implicitHeight: 46
    Accessible.name: "Enter TMCC ID"
    hoverEnabled: true
    ToolTip.visible: hovered
    ToolTip.text: "Enter TMCC ID"

    contentItem: Item {
        Grid {
            anchors.centerIn: parent
            columns: 3
            spacing: 2
            Repeater {
                model: 12
                Rectangle {
                    width: Math.max(7, Math.min(root.width, root.height) / 8)
                    height: width
                    radius: 1
                    color: "#f4f6f8"
                }
            }
        }
    }
}
