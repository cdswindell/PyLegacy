import QtQuick
import QtQuick.Controls

CabButton {
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
                    width: 7
                    height: 7
                    radius: 1
                    color: "#f4f6f8"
                }
            }
        }
    }
}
