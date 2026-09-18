import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property var controller
    property string searchText: ""
    property string sortMode: "NAME"

    function visibleRows() {
        if (!controller)
            return []
        var needle = searchText.trim().toLowerCase()
        var rows = controller.rows.filter(function(row) {
            if (!needle)
                return true
            return row.roadName.toLowerCase().indexOf(needle) >= 0 ||
                   row.roadNumber.toLowerCase().indexOf(needle) >= 0 ||
                   String(row.primaryTmccId).indexOf(needle) >= 0 ||
                   row.lcsAssociations.toLowerCase().indexOf(needle) >= 0
        })
        rows.sort(function(a, b) {
            if (sortMode === "TMCC")
                return a.primaryTmccId - b.primaryTmccId
            if (sortMode === "ROAD")
                return a.roadNumber.localeCompare(b.roadNumber)
            return a.roadName.localeCompare(b.roadName)
        })
        return rows
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "Accessory Operations"
                color: "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            CabButton {
                Layout.preferredWidth: 120
                Layout.preferredHeight: 54
                text: "HALT"
                onClicked: cabController.halt()
            }
        }

        TextField {
            Layout.fillWidth: true
            placeholderText: "Search name, road number, TMCC ID, or LCS module"
            text: root.searchText
            onTextChanged: root.searchText = text
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Label {
                text: "Sort:"
                color: "#b8c0ca"
            }
            Button {
                text: "Name"
                checked: root.sortMode === "NAME"
                checkable: true
                onClicked: root.sortMode = "NAME"
            }
            Button {
                text: "Road #"
                checked: root.sortMode === "ROAD"
                checkable: true
                onClicked: root.sortMode = "ROAD"
            }
            Button {
                text: "TMCC ID"
                checked: root.sortMode === "TMCC"
                checkable: true
                onClicked: root.sortMode = "TMCC"
            }
            Item { Layout.fillWidth: true }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 5
            model: root.visibleRows()

            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width
                height: 82
                radius: 8
                color: "#20242a"
                border.width: 1
                border.color: "#3d444f"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 9
                    spacing: 10

                    Label {
                        Layout.preferredWidth: 54
                        text: modelData.primaryTmccId
                        color: "#78bff0"
                        font.pixelSize: 22
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            Layout.fillWidth: true
                            text: modelData.roadName
                            color: "#f4f6f8"
                            font.pixelSize: 17
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: {
                                var parts = []
                                if (modelData.roadNumber)
                                    parts.push("Road # " + modelData.roadNumber)
                                if (modelData.lcsAssociations)
                                    parts.push(modelData.lcsAssociations)
                                return parts.join(" · ")
                            }
                            color: "#b8c0ca"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.availableViews.join(" · ")
                            color: modelData.configured ? "#e9c46a" : "#8fa2b5"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                    }

                    Label {
                        text: modelData.preferredView
                        color: "#f4f6f8"
                        font.pixelSize: 13
                        font.bold: true
                    }
                }
            }
        }
    }
}
