import QtQuick
import QtQuick.Controls

Button {
    id: root

    property url iconSource: ""
    property bool selected: false
    property color normalColor: "#303640"
    property color selectedColor: "#176fa8"
    property color pressedColor: "#48515e"

    implicitHeight: 58
    font.pixelSize: 14

    contentItem: Row {
        spacing: 8
        anchors.centerIn: parent
        width: Math.min(implicitWidth, root.width - 14)

        Image {
            id: operationIcon
            anchors.verticalCenter: parent.verticalCenter
            width: 36
            height: 36
            source: root.iconSource
            visible: root.iconSource.toString().length > 0
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(0, parent.width - (operationIcon.visible ? operationIcon.width + parent.spacing : 0))
            text: root.text
            color: root.enabled ? "#f5f7fa" : "#858c96"
            font: root.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    background: Rectangle {
        radius: 9
        color: !root.enabled ? "#242930" : root.down ? root.pressedColor : root.selected ? root.selectedColor : root.normalColor
        border.width: 1
        border.color: root.selected ? "#78c9ff" : "#626b78"
    }
}
