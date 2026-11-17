import QtQuick

Rectangle {
    id: thumb

    required property string valueText
    property string caption: ""
    property bool largeTouch: false
    property bool muted: false
    property bool pressed: false

    radius: 14
    gradient: Gradient {
        GradientStop { position: 0; color: thumb.muted ? "#686c72" : thumb.pressed ? "#306881" : "#698ba0" }
        GradientStop { position: 0.45; color: thumb.muted ? "#45494f" : "#365a72" }
        GradientStop { position: 1; color: thumb.muted ? "#30343a" : "#203e52" }
    }
    border.color: thumb.muted ? "#969da5" : thumb.pressed ? "#5fb7f2" : "#8ba9bb"

    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.57
        height: parent.height - 10
        radius: 6
        color: thumb.muted ? "#272b31" : "#142838"
        border.color: "#698492"

        Column {
            anchors.centerIn: parent

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: text.length > 0
                text: thumb.caption
                font.pixelSize: thumb.largeTouch ? 10 : 8
                font.bold: true
                color: "#d9edf9"
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: thumb.valueText
                font.pixelSize: thumb.largeTouch ? 23 : 17
                font.bold: true
                color: "#ffffff"
            }
        }
    }

    Repeater {
        model: 6
        Rectangle {
            required property int index
            width: 2
            height: parent.height * 0.58
            anchors.verticalCenter: parent.verticalCenter
            x: index < 3 ? parent.width * 0.07 + index * 4
                         : parent.width * 0.81 + (index - 3) * 4
            radius: 1
            color: "#152a3a"
            border.color: "#587d93"
        }
    }
}
