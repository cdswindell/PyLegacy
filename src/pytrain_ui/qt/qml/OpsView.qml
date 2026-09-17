import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var controller
    signal closeRequested()

    color: "#171a1f"
    radius: 14

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: controller.scope === "SWITCH" ? "Switch Operations" : "Route Operations"
                color: "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            CabButton {
                Layout.preferredWidth: 100
                Layout.preferredHeight: 46
                text: "HALT"
                font.bold: true
                normalColor: "#9d2020"
                pressedColor: "#c62d2d"
                onClicked: controller.halt()
            }
        }

        TextField {
            id: searchField
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            placeholderText: "Search road name, road number, or TMCC ID"
            font.pixelSize: 15
        }

        ListView {
            id: roster
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 5
            model: controller.rows

            delegate: Rectangle {
                id: row
                required property var modelData
                width: roster.width
                height: visible ? 62 : 0
                visible: {
                    const query = searchField.text.trim().toLowerCase()
                    if (!query)
                        return true
                    return String(modelData.tmccId).toLowerCase().indexOf(query) >= 0 ||
                           modelData.roadName.toLowerCase().indexOf(query) >= 0 ||
                           modelData.roadNumber.toLowerCase().indexOf(query) >= 0
                }
                radius: 8
                color: controller.selectedId === modelData.tmccId ? "#244f70" : "#262b32"
                border.width: 1
                border.color: controller.selectedId === modelData.tmccId ? "#78bff0" : "#444c57"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10
                    Label {
                        Layout.preferredWidth: 72
                        text: modelData.tmccId
                        color: "#f4f6f8"
                        font.pixelSize: 20
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Label {
                            Layout.fillWidth: true
                            text: modelData.roadName || (controller.scope === "SWITCH" ? "Switch" : "Route")
                            color: "#f4f6f8"
                            font.pixelSize: 16
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.roadNumber ? "Road # " + modelData.roadNumber : "TMCC ID " + modelData.tmccId
                            color: "#aeb5bf"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                }

                TapHandler {
                    onTapped: controller.select(row.modelData.tmccId)
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: controller.selectedId ? 150 : 82
            radius: 9
            color: "#20242a"
            border.width: 1
            border.color: "#3d444f"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 6
                Label {
                    Layout.fillWidth: true
                    text: controller.selectedId ?
                              ((controller.roadName || controller.scope) +
                               (controller.roadNumber ? "  #" + controller.roadNumber : "") +
                               "   TMCC " + controller.selectedId) :
                              "Select a " + (controller.scope === "SWITCH" ? "switch" : "route")
                    color: "#f4f6f8"
                    font.pixelSize: 17
                    font.bold: true
                    elide: Text.ElideRight
                }
                Label {
                    visible: controller.selectedId !== 0
                    Layout.fillWidth: true
                    text: controller.stateText
                    color: "#b9c0c9"
                    font.pixelSize: 14
                }
                RowLayout {
                    visible: controller.selectedId !== 0
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 8
                    CabButton {
                        visible: controller.scope === "SWITCH"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: "THRU"
                        selected: controller.isThru
                        onClicked: controller.operate("THRU")
                    }
                    CabButton {
                        visible: controller.scope === "SWITCH"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: "OUT"
                        selected: controller.isOut
                        onClicked: controller.operate("OUT")
                    }
                    CabButton {
                        visible: controller.scope === "ROUTE"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: "FIRE ROUTE"
                        normalColor: "#246aa0"
                        onClicked: controller.operate("FIRE")
                    }
                }
            }
        }
    }
}
