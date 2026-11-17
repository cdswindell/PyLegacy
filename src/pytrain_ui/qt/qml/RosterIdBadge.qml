import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    required property string abbreviation
    required property int tmccId
    property string displayValue: String(tmccId)
    property int numberSize: 36
    property url imageSource

    radius: 7
    color: "#18232e"
    border.width: 1
    border.color: "#596574"

    Image {
        id: badgeArtwork
        anchors.fill: parent
        anchors.margins: 4
        source: root.imageSource
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        visible: status === Image.Ready
    }

    Column {
        anchors.centerIn: parent
        visible: !badgeArtwork.visible
        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.abbreviation.length > 0
            text: root.abbreviation
            color: "#9ea6b0"
            font.pixelSize: 14
            font.bold: true
        }
        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.displayValue
            color: "white"
            font.pixelSize: root.numberSize
            font.bold: true
        }
    }
}
