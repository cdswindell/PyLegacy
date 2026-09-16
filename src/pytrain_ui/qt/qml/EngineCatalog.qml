import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var cab
    signal engineSelected()
    signal closeRequested()

    color: "#15191f"
    radius: 10

    property string sortMode: "name"
    property string searchText: ""

    function tmccId(label) {
        var match = label.match(/^Engine\s+(\d+)/)
        return match ? Number(match[1]) : 0
    }

    function detail(label) {
        var parts = label.split(" — ")
        return parts.length > 1 ? parts.slice(1).join(" — ") : label
    }

    function filteredTargets() {
        var rows = []
        var needle = searchText.trim().toLowerCase()
        for (var i = 0; i < cab.targetLabels.length; ++i) {
            var label = cab.targetLabels[i]
            if (!label.startsWith("Engine "))
                continue
            if (needle.length && label.toLowerCase().indexOf(needle) < 0)
                continue
            rows.push({ "sourceIndex": i, "label": label })
        }
        rows.sort(function(a, b) {
            if (sortMode === "tmcc")
                return root.tmccId(a.label) - root.tmccId(b.label)
            var av = root.detail(a.label).toLowerCase()
            var bv = root.detail(b.label).toLowerCase()
            return av.localeCompare(bv)
        })
        return rows
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: "ENGINES"
                color: "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            Button {
                text: "Cab"
                font.pixelSize: 15
                onClicked: root.closeRequested()
            }
        }

        TextField {
            id: searchField
            Layout.fillWidth: true
            Layout.preferredHeight: 54
            placeholderText: "Search name, road number, or TMCC ID"
            font.pixelSize: 17
            selectByMouse: true
            onTextChanged: root.searchText = text
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Label {
                text: "Sort"
                color: "#aeb7c2"
                font.pixelSize: 13
            }
            Button {
                text: "Name"
                checkable: true
                checked: root.sortMode === "name"
                onClicked: root.sortMode = "name"
            }
            Button {
                text: "TMCC ID"
                checkable: true
                checked: root.sortMode === "tmcc"
                onClicked: root.sortMode = "tmcc"
            }
            Item { Layout.fillWidth: true }
            Label {
                text: root.filteredTargets().length + " engines"
                color: "#9ea6b0"
                font.pixelSize: 12
            }
        }

        Label {
            Layout.fillWidth: true
            text: "Type filters will use PyTrain engine types in the next pass"
            color: "#87919d"
            font.pixelSize: 11
        }

        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            boundsBehavior: Flickable.StopAtBounds
            flickDeceleration: 1800
            model: root.filteredTargets()

            delegate: Rectangle {
                id: row
                required property var modelData
                width: ListView.view.width
                height: 72
                radius: 8
                color: tapHandler.pressed ? "#354150" : "#272d35"
                border.width: 1
                border.color: "#4b5664"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 14

                    Rectangle {
                        Layout.preferredWidth: 66
                        Layout.preferredHeight: 46
                        radius: 7
                        color: "#1c2229"
                        border.width: 1
                        border.color: "#596574"
                        Column {
                            anchors.centerIn: parent
                            Label {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "ENG"
                                color: "#9ea6b0"
                                font.pixelSize: 9
                                font.bold: true
                            }
                            Label {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: root.tmccId(row.modelData.label)
                                color: "white"
                                font.pixelSize: 18
                                font.bold: true
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            Layout.fillWidth: true
                            text: root.detail(row.modelData.label)
                            color: "#f3f5f7"
                            font.pixelSize: 16
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: row.modelData.label
                            color: "#a9b2bd"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                    }

                    Label {
                        text: "›"
                        color: "#8fc9ef"
                        font.pixelSize: 28
                    }
                }

                TapHandler {
                    id: tapHandler
                    gesturePolicy: TapHandler.DragThreshold
                    onTapped: {
                        root.cab.selectTarget(row.modelData.sourceIndex)
                        root.engineSelected()
                    }
                }
            }
        }
    }
}
