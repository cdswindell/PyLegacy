import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    objectName: "networkCard"
    required property var reading
    implicitHeight: content.implicitHeight + 20
    color: "#16376b"
    border.color: "#5275a4"
    radius: 8
    Accessible.role: Accessible.StaticText
    Accessible.name: reading.connection + ". " + reading.ssid + ". " + reading.signal + ". Local IP " + reading.address

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 10
        spacing: 5

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "Network"
                color: "#bad4ea"
                font.pixelSize: 17
                font.bold: true
            }
            Label {
                Layout.fillWidth: true
                text: root.reading.connection
                color: "#f4f6f8"
                horizontalAlignment: Text.AlignRight
                font.pixelSize: 16
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label {
                objectName: "networkSsid"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.reading.ssid
                color: "#f4f6f8"
                font.pixelSize: 17
                elide: Text.ElideRight
            }
            Row {
                visible: root.reading.wireless
                spacing: 3
                Accessible.ignored: true
                Repeater {
                    model: 4
                    Rectangle {
                        required property int index
                        width: 6
                        height: 7 + index * 5
                        y: 22 - height
                        radius: 1
                        color: index < root.reading.bars ? root.reading.color : "#425b77"
                    }
                }
            }
            Label {
                objectName: "networkSignal"
                text: root.reading.signal
                color: root.reading.color
                font.pixelSize: 16
            }
        }
        Label {
            objectName: "networkAddress"
            Layout.fillWidth: true
            text: "Local IP  " + root.reading.address
            color: "#f4f6f8"
            font.pixelSize: 16
            wrapMode: Text.WordWrap
        }
    }
}
