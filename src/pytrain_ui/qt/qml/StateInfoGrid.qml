import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GridLayout {
    id: section
    required property var rows
    property int tileHeight: 0
    columns: width >= 520 ? 4 : 2
    columnSpacing: 8
    rowSpacing: 8
    Repeater {
        model: section.rows
        delegate: Rectangle {
            required property var modelData
            Layout.fillWidth: true
            Layout.preferredWidth: 0
            Layout.minimumWidth: 0
            Layout.preferredHeight: section.tileHeight || detailLabels.implicitHeight + 16
            color: "#173765"
            radius: 6
            ColumnLayout {
                id: detailLabels
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: 8
                spacing: 2
                Label {
                    Layout.fillWidth: true
                    text: modelData.label
                    color: "#b5c9e5"
                    font.pixelSize: 17
                    wrapMode: Text.WordWrap
                }
                Label {
                    Layout.fillWidth: true
                    text: modelData.value
                    color: "white"
                    font.pixelSize: 20
                    wrapMode: Text.WrapAnywhere
                }
            }
        }
    }
}
