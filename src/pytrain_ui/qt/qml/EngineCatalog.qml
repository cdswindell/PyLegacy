import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var cab
    required property var catalog
    required property var selection
    signal engineSelected()
    signal closeRequested()

    color: "#15191f"
    radius: 10

    property string sortMode: "name"
    property string searchText: ""
    property string typeFilter: "ALL"

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
        if (!catalog)
            return rows
        var needle = searchText.trim().toLowerCase()
        for (var i = 0; i < catalog.engines.length; ++i) {
            var engine = catalog.engines[i]
            if (typeFilter !== "ALL" && engine.engineType !== typeFilter)
                continue
            var searchable = (engine.roadName + " " + engine.roadNumber + " " + engine.tmccId + " " +
                              engine.engineType + " " + engine.engineTypeLabel).toLowerCase()
            if (needle.length && searchable.indexOf(needle) < 0)
                continue
            rows.push(engine)
        }
        rows.sort(function(a, b) {
            if (sortMode === "tmcc")
                return a.tmccId - b.tmccId
            if (sortMode === "road") {
                var result = root.compareRoadNumbers(a.roadNumber, b.roadNumber)
                if (result !== 0)
                    return result
            }
            var result = a.roadName.toLowerCase().localeCompare(b.roadName.toLowerCase())
            return result !== 0 ? result : a.tmccId - b.tmccId
        })
        return rows
    }

    component ChoiceButton: Button {
        id: control
        checkable: true
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
            placeholderText: "Search name, road number, TMCC ID, or type"
            font.pixelSize: 17
            selectByMouse: true
            onTextChanged: root.searchText = text
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Label { text: "Sort"; color: "#aeb7c2"; font.pixelSize: 13 }
            ButtonGroup { id: sortGroup; exclusive: true }
            ChoiceButton {
                Layout.preferredWidth: 104; Layout.preferredHeight: 42
                text: "Name"; checked: root.sortMode === "name"; ButtonGroup.group: sortGroup
                onClicked: root.sortMode = "name"
            }
            ChoiceButton {
                Layout.preferredWidth: 104; Layout.preferredHeight: 42
                text: "Road #"; checked: root.sortMode === "road"; ButtonGroup.group: sortGroup
                onClicked: root.sortMode = "road"
            }
            ChoiceButton {
                Layout.preferredWidth: 104; Layout.preferredHeight: 42
                text: "TMCC ID"; checked: root.sortMode === "tmcc"; ButtonGroup.group: sortGroup
                onClicked: root.sortMode = "tmcc"
            }
            Item { Layout.fillWidth: true }
            Label { text: root.filteredTargets().length + " engines"; color: "#9ea6b0"; font.pixelSize: 12 }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Label { text: "Type"; color: "#aeb7c2"; font.pixelSize: 13 }
            ListView {
                id: typeList
                Layout.fillWidth: true
                Layout.preferredHeight: 42
                orientation: ListView.Horizontal
                spacing: 7
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: [{ "key": "ALL", "label": "All" }].concat(root.catalog ? root.catalog.typeFilters : [])
                delegate: ChoiceButton {
                    required property var modelData
                    width: Math.max(82, implicitContentWidth + 26)
                    height: 42
                    text: modelData.label
                    checked: root.typeFilter === modelData.key
                    onClicked: root.typeFilter = modelData.key
                }
            }
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
                            Label { anchors.horizontalCenter: parent.horizontalCenter; text: "ENG"; color: "#9ea6b0"; font.pixelSize: 9; font.bold: true }
                            Label { anchors.horizontalCenter: parent.horizontalCenter; text: row.modelData.tmccId; color: "white"; font.pixelSize: 18; font.bold: true }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            Layout.fillWidth: true
                            text: (row.modelData.roadName || "Engine") + (row.modelData.roadNumber ? "  " + row.modelData.roadNumber : "")
                            color: "#f3f5f7"
                            font.pixelSize: 16
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: row.modelData.engineTypeLabel
                            color: "#a9b2bd"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                    }
                    Label { text: "›"; color: "#8fc9ef"; font.pixelSize: 28 }
                }

                TapHandler {
                    id: tapHandler
                    gesturePolicy: TapHandler.DragThreshold
                    onTapped: {
                        root.selection.selectEngine(row.modelData.tmccId)
                        searchField.clear()
                        root.engineSelected()
                    }
                }
            }
        }
    }
}
