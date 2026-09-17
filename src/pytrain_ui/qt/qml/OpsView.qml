import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var controller
    property string sortKey: "roadName"
    signal closeRequested()

    color: "#171a1f"
    radius: 14

    function compareRows(a, b) {
        if (sortKey === "tmccId")
            return a.tmccId - b.tmccId

        let av = sortKey === "roadNumber" ? a.roadNumber : a.roadName
        let bv = sortKey === "roadNumber" ? b.roadNumber : b.roadName
        av = String(av || "").toLowerCase()
        bv = String(bv || "").toLowerCase()
        const result = av.localeCompare(bv, undefined, { numeric: true })
        return result !== 0 ? result : a.tmccId - b.tmccId
    }

    function visibleRows() {
        const query = searchField.text.trim().toLowerCase()
        const result = controller.rows.filter(function(row) {
            return !query ||
                   String(row.tmccId).toLowerCase().indexOf(query) >= 0 ||
                   row.roadName.toLowerCase().indexOf(query) >= 0 ||
                   row.roadNumber.toLowerCase().indexOf(query) >= 0
        })
        result.sort(compareRows)
        return result
    }

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

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Label {
                text: "Sort:"
                color: "#aeb5bf"
                font.pixelSize: 13
            }
            Repeater {
                model: [
                    { key: "roadName", label: "Name" },
                    { key: "roadNumber", label: "Road #" },
                    { key: "tmccId", label: "TMCC ID" }
                ]
                CabButton {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    text: modelData.label
                    selected: root.sortKey === modelData.key
                    onClicked: root.sortKey = modelData.key
                }
            }
        }

        ListView {
            id: roster
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 5
            model: root.visibleRows()

            delegate: Rectangle {
                id: row
                required property var modelData
                width: roster.width
                height: 68
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
                    Label {
                        Layout.preferredWidth: controller.scope === "ROUTE" ? 108 : 72
                        text: modelData.stateText
                        color: modelData.stateText === "ALIGNED" || modelData.stateText === "THRU" ? "#73d38a" :
                               modelData.stateText === "UNKNOWN" ? "#aeb5bf" : "#f0a35a"
                        font.pixelSize: 12
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    CabButton {
                        visible: controller.scope === "ROUTE"
                        Layout.preferredWidth: 96
                        Layout.preferredHeight: 46
                        text: "FIRE"
                        font.pixelSize: 16
                        font.bold: true
                        normalColor: "#a84418"
                        pressedColor: "#d65a20"
                        onClicked: controller.fireRoute(row.modelData.tmccId)
                    }
                }

                TapHandler {
                    enabled: controller.scope === "SWITCH"
                    onTapped: controller.select(row.modelData.tmccId)
                }
            }
        }

        Rectangle {
            visible: controller.scope === "SWITCH"
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
                              "Select a switch"
                    color: "#f4f6f8"
                    font.pixelSize: 17
                    font.bold: true
                    elide: Text.ElideRight
                }
                Label {
                    visible: controller.selectedId !== 0
                    Layout.fillWidth: true
                    text: controller.stateText
                    color: controller.stateText === "THRU" ? "#73d38a" :
                           controller.stateText === "UNKNOWN" ? "#b9c0c9" : "#f0a35a"
                    font.pixelSize: 14
                    font.bold: true
                }
                RowLayout {
                    visible: controller.selectedId !== 0
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 8
                    CabButton {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: "THRU"
                        selected: controller.isThru
                        onClicked: controller.operate("THRU")
                    }
                    CabButton {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: "OUT"
                        selected: controller.isOut
                        onClicked: controller.operate("OUT")
                    }
                }
            }
        }
    }
}
