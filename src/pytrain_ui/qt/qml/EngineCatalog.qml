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

    function roadNumber(label) {
        var value = root.detail(label)
        var parts = value.trim().split(/\s+/)
        return parts.length ? parts[parts.length - 1] : ""
    }

    function roadName(label) {
        var value = root.detail(label)
        var number = root.roadNumber(label)
        if (!number.length)
            return value
        return value.slice(0, value.length - number.length).trim()
    }

    function compareRoadNumbers(a, b) {
        var an = Number(a)
        var bn = Number(b)
        var aNumeric = a.length > 0 && !isNaN(an)
        var bNumeric = b.length > 0 && !isNaN(bn)
        if (aNumeric && bNumeric)
            return an - bn
        return a.toLowerCase().localeCompare(b.toLowerCase())
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
            if (sortMode === "road") {
                var result = root.compareRoadNumbers(root.roadNumber(a.label), root.roadNumber(b.label))
                if (result !== 0)
                    return result
            }
            var av = root.roadName(a.label).toLowerCase()
            var bv = root.roadName(b.label).toLowerCase()
            return av.localeCompare(bv)
        })
        return rows
    }

    component SortButton: Button {
        id: control
        checkable: true
        Layout.preferredWidth: 104
        Layout.preferredHeight: 42
        font.pixelSize: 14
        font.bold: checked

        contentItem: Label {
            text: control.text
            color: "#f4f6f8"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font: control.font
        }

        background: Rectangle {
            radius: 6
            color: control.checked ? "#246aa0" : control.pressed ? "#3a424d" : "#303640"
            border.width: control.checked ? 2 : 1
            border.color: control.checked ? "#78bff0" : "#555e6b"
        }
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

            CabButton {
                Layout.preferredWidth: 130
                Layout.preferredHeight: 46
                text: "HALT"
                font.pixelSize: 17
                font.bold: true
                normalColor: "#8b2d32"
                pressedColor: "#b43b42"
                onClicked: cab.stop()
            }

            Button {
                Layout.preferredWidth: 100
                Layout.preferredHeight: 46
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

            ButtonGroup {
                id: sortGroup
                exclusive: true
            }

            SortButton {
                text: "Name"
                checked: root.sortMode === "name"
                ButtonGroup.group: sortGroup
                onClicked: root.sortMode = "name"
            }

            SortButton {
                text: "Road #"
                checked: root.sortMode === "road"
                ButtonGroup.group: sortGroup
                onClicked: root.sortMode = "road"
            }

            SortButton {
                text: "TMCC ID"
                checked: root.sortMode === "tmcc"
                ButtonGroup.group: sortGroup
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
