import QtQuick
import QtQuick.Controls

TabButton {
    id: root
    implicitWidth: 100
    padding: 0
    topInset: 0
    bottomInset: 0

    contentItem: Text {
        text: root.text
        color: root.checked ? "#ffffff" : "#aeb7c2"
        font.pixelSize: 18
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Item {
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: root.checked ? 0 : 5
            radius: 10
            color: root.down ? "#263b50" : root.checked ? "#397498" : "#20313e"
            border.width: 1
            border.color: root.checked ? "#9ab2c3" : "#718a9c"
            gradient: root.checked ? selectedTabGradient : inactiveTabGradient
            SelectionGradient {
                id: selectedTabGradient
                selected: true
                depressed: root.down
            }
            Gradient {
                id: inactiveTabGradient
                GradientStop { position: 0; color: root.down ? "#101a25" : "#324553" }
                GradientStop { position: 1; color: root.down ? "#263b50" : "#20313e" }
            }
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 1
            anchors.rightMargin: 1
            height: 8
            color: root.down ? "#263b50" : root.checked ? "#397498" : "#20313e"
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: root.checked ? "#397498" : "#5275a4"
        }
    }
}
