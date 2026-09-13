import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root

    required property var cab
    property string panelKey: ""
    property string panelTitle: ""
    property var actionModel: []

    function openFor(key) {
        panelKey = key
        panelTitle = cab.panelTitle(key)
        actionModel = cab.panelModel(key)
        open()
    }

    width: Math.min(560, (parent ? parent.width : 620) - 40)
    height: Math.min(620, Math.max(220, contentColumn.implicitHeight + 36))
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    padding: 16

    background: Rectangle {
        radius: 12
        color: "#252a31"
        border.width: 1
        border.color: "#697382"
    }

    contentItem: ColumnLayout {
        id: contentColumn
        spacing: 10

        Label {
            Layout.fillWidth: true
            text: root.panelTitle
            color: "white"
            font.pixelSize: 20
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            GridLayout {
                width: parent.width
                columns: width >= 430 ? 3 : 2
                columnSpacing: 6
                rowSpacing: 6

                Repeater {
                    model: root.actionModel
                    FunctionButton {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 42
                        compact: true
                        text: (modelData.section ? modelData.section + " · " : "") + modelData.label
                        onClicked: root.cab.triggerPanelCommand(modelData.command)
                    }
                }
            }
        }

        CabButton {
            Layout.fillWidth: true
            Layout.preferredHeight: 42
            text: "Close"
            onClicked: root.close()
        }
    }
}
