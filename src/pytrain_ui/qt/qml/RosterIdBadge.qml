import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    required property string abbreviation
    required property int tmccId
    property int numberSize: 36

    radius: 7
    color: "#18232e"
    border.width: 1
    border.color: "#596574"

    Column {
        anchors.centerIn: parent
        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.abbreviation
            color: "#9ea6b0"
            font.pixelSize: 14
            font.bold: true
        }
        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.tmccId
            color: "white"
            font.pixelSize: root.numberSize
            font.bold: true
        }
    }
}
