import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root

    property url iconSource: ""
    property bool selected: false
    property color normalColor: "#303640"
    property color selectedColor: "#176fa8"
    property color pressedColor: "#48515e"

    implicitHeight: 58
    font.pixelSize: 14

    contentItem: RowLayout {
        spacing: 8

        Rectangle {
            Layout.preferredWidth: 42
            Layout.preferredHeight: 42
            Layout.alignment: Qt.AlignVCenter
            visible: root.iconSource.toString().length > 0
            radius: 6
            color: "#e8ebef"
            border.width: 1
            border.color: "#c6cbd2"

            Image {
                anchors.fill: parent
                anchors.margins: 3
                source: root.iconSource
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
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
