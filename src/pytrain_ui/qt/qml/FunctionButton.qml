import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root

    property url iconSource: ""
    property bool selected: false
    property bool compact: false
    property color normalColor: "#303640"
    property color selectedColor: "#176fa8"
    property color pressedColor: "#48515e"

    implicitHeight: compact ? 44 : 58
    font.pixelSize: compact ? 12 : 14

    contentItem: RowLayout {
        spacing: root.compact ? 5 : 8

        Rectangle {
            Layout.preferredWidth: root.compact ? 30 : 42
            Layout.preferredHeight: root.compact ? 30 : 42
            Layout.alignment: Qt.AlignVCenter
            visible: root.iconSource.toString().length > 0
            radius: root.compact ? 4 : 6
            color: "#e8ebef"
            border.width: 1
            border.color: "#c6cbd2"

            Image {
                anchors.fill: parent
                anchors.margins: root.compact ? 2 : 3
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
        radius: root.compact ? 7 : 9
        color: !root.enabled ? "#242930" : root.down ? root.pressedColor : root.selected ? root.selectedColor : root.normalColor
        border.width: 1
        border.color: root.selected ? "#78c9ff" : "#626b78"
    }
}
