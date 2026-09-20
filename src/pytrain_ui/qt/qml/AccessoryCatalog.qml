import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var controller
    property var lcsController: null
    property string searchText: ""
    property string sortMode: "NAME"
    property string typeFilter: "ALL"

    signal accessoryRequested(string key)
    signal addRequested()
    signal lcsRequested()

    function openLcsConfiguration() {
        if (root.lcsController)
            lcsConfig.open()
    }

    function cancelTransientPanels() {
        lcsConfig.close()
    }

    color: "#15191f"
    radius: 10

    function compareRoadNumbers(a, b) {
        var an = Number(a)
        var bn = Number(b)
        var aNumeric = a.length > 0 && !isNaN(an)
        var bNumeric = b.length > 0 && !isNaN(bn)
        if (aNumeric && bNumeric)
            return an - bn
        return a.toLowerCase().localeCompare(b.toLowerCase())
    }

    function visibleRows() {
        if (!controller)
            return []
        var needle = searchText.trim().toLowerCase()
        var sourceRows = []
        controller.rows.forEach(function(row) {
            if (typeFilter === "ASC2" && row.componentRows.length > 0) {
                row.componentRows.forEach(function(component) {
                    var componentRow = Object.assign({}, row)
                    componentRow.primaryTmccId = component.tmccId
                    componentRow.roadName = component.label
                    componentRow.stateSummary = component.behavior.replace("_", " ").toUpperCase()
                    componentRow.quickActions = component.quickActions
                    componentRow.componentEnabled = component.enabled
                    sourceRows.push(componentRow)
                })
            } else {
                sourceRows.push(row)
            }
        })
        var rows = sourceRows.filter(function(row) {
            if (typeFilter !== "ALL" && typeFilter !== "OPERATING" && row.lcsTypes.indexOf(typeFilter) < 0)
                return false
            if (!needle)
                return true
            return row.roadName.toLowerCase().indexOf(needle) >= 0 ||
                   row.roadNumber.toLowerCase().indexOf(needle) >= 0 ||
                   String(row.primaryTmccId).indexOf(needle) >= 0 ||
                   row.lcsAssociations.toLowerCase().indexOf(needle) >= 0
        })
        rows.sort(function(a, b) {
            if (sortMode === "TMCC") {
                var idResult = a.primaryTmccId - b.primaryTmccId
                if (idResult !== 0)
                    return idResult
                return a.roadName.toLowerCase().localeCompare(b.roadName.toLowerCase())
            }
            if (sortMode === "ROAD") {
                var result = root.compareRoadNumbers(a.roadNumber, b.roadNumber)
                if (result !== 0)
                    return result
            }
            var result = a.roadName.toLowerCase().localeCompare(b.roadName.toLowerCase())
            return result !== 0 ? result : a.primaryTmccId - b.primaryTmccId
        })
        return rows
    }

    component ChoiceButton: CabButton {
        font.pixelSize: 14
        font.bold: selected
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "Operating Accessories"
                color: "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            CabButton {
                Layout.preferredWidth: 92
                Layout.preferredHeight: 46
                text: "ADD…"
                font.pixelSize: 14
                onClicked: root.addRequested()
            }
            CabButton {
                Layout.preferredWidth: 92
                Layout.preferredHeight: 46
                text: "LCS…"
                font.pixelSize: 14
                onClicked: root.lcsRequested()
            }
            Item { Layout.fillWidth: true }
            CabButton {
                Layout.preferredWidth: 120
                Layout.preferredHeight: 54
                text: "HALT"
                font.pixelSize: 17
                font.bold: true
                normalColor: "#8b2d32"
                pressedColor: "#b43b42"
                onClicked: root.controller.halt()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            TextField {
                id: searchField
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                placeholderText: "Search name, road number, TMCC ID, or LCS module"
                font.pixelSize: 17
                selectByMouse: true
                text: root.searchText
                onTextEdited: root.searchText = text
            }
            CabButton {
                Layout.preferredWidth: 72
                Layout.preferredHeight: 54
                text: "Clear"
                font.pixelSize: 14
                enabled: searchField.text.length > 0
                onClicked: {
                    root.searchText = ""
                    searchField.forceActiveFocus()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Label { text: "Sort"; color: "#aeb7c2"; font.pixelSize: 13 }
            ChoiceButton {
                Layout.preferredWidth: 104
                Layout.preferredHeight: 42
                text: "Name"
                selected: root.sortMode === "NAME"
                onClicked: root.sortMode = "NAME"
            }
            ChoiceButton {
                Layout.preferredWidth: 104
                Layout.preferredHeight: 42
                text: "Road #"
                selected: root.sortMode === "ROAD"
                onClicked: root.sortMode = "ROAD"
            }
            ChoiceButton {
                Layout.preferredWidth: 104
                Layout.preferredHeight: 42
                text: "TMCC ID"
                selected: root.sortMode === "TMCC"
                onClicked: root.sortMode = "TMCC"
            }
            Item { Layout.fillWidth: true }
            Label {
                text: root.visibleRows().length + " accessories"
                color: "#9ea6b0"
                font.pixelSize: 12
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Label { text: "Type"; color: "#aeb7c2"; font.pixelSize: 13 }
            ChoiceButton {
                Layout.preferredWidth: 70
                Layout.preferredHeight: 42
                text: "All"
                selected: root.typeFilter === "ALL"
                onClicked: root.typeFilter = "ALL"
            }
            ChoiceButton {
                Layout.preferredWidth: 100
                Layout.preferredHeight: 42
                text: "Operating"
                selected: root.typeFilter === "OPERATING"
                onClicked: root.typeFilter = "OPERATING"
            }
            ChoiceButton {
                Layout.preferredWidth: 82
                Layout.preferredHeight: 42
                text: "ASC2"
                selected: root.typeFilter === "ASC2"
                onClicked: root.typeFilter = "ASC2"
            }
            ChoiceButton {
                Layout.preferredWidth: 82
                Layout.preferredHeight: 42
                text: "AMC2"
                selected: root.typeFilter === "AMC2"
                onClicked: root.typeFilter = "AMC2"
            }
            ChoiceButton {
                Layout.preferredWidth: 82
                Layout.preferredHeight: 42
                text: "BPC2"
                selected: root.typeFilter === "BPC2"
                onClicked: root.typeFilter = "BPC2"
            }
            ChoiceButton {
                Layout.preferredWidth: 122
                Layout.preferredHeight: 42
                text: "Sensor Track"
                selected: root.typeFilter === "SENSOR_TRACK"
                onClicked: root.typeFilter = "SENSOR_TRACK"
            }
            Item { Layout.fillWidth: true }
        }

        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            boundsBehavior: Flickable.StopAtBounds
            flickDeceleration: 1800
            model: root.visibleRows()

            delegate: Rectangle {
                id: row
                required property var modelData
                width: ListView.view.width
                height: 82
                radius: 8
                color: tapHandler.pressed ? "#354150" : "#272d35"
                opacity: row.modelData.componentEnabled === false ? 0.62 : 1.0
                border.width: 1
                border.color: "#4b5664"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 9
                    spacing: 10

                    Label {
                        Layout.preferredWidth: 54
                        text: row.modelData.primaryTmccId
                        color: "#55bdf5"
                        font.pixelSize: 22
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            Layout.fillWidth: true
                            text: row.modelData.roadName
                            color: "#f4f6f8"
                            font.pixelSize: 17
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: {
                                var parts = []
                                if (row.modelData.roadNumber)
                                    parts.push("Road # " + row.modelData.roadNumber)
                                if (row.modelData.lcsAssociations)
                                    parts.push(row.modelData.lcsAssociations)
                                return parts.join(" · ")
                            }
                            color: "#b8c0ca"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: row.modelData.stateSummary || row.modelData.availableViews.join(" · ")
                            color: row.modelData.stateSummary ? "#8fc9ef" :
                                   (row.modelData.configured ? "#e9c46a" : "#8fa2b5")
                            font.pixelSize: 11
                            font.bold: row.modelData.stateSummary.length > 0
                            elide: Text.ElideRight
                        }
                    }

                    RowLayout {
                        visible: row.modelData.quickActions.length > 0
                        spacing: 5
                        Repeater {
                            model: row.modelData.quickActions
                            CabButton {
                                required property var modelData
                                Layout.preferredWidth: (modelData.key === "HOLD" || modelData.key === "PULSE") ? 104 : 58
                                Layout.preferredHeight: 38
                                text: modelData.label
                                font.pixelSize: 12
                                font.bold: modelData.selected
                                selected: modelData.selected
                                enabled: modelData.enabled === undefined || modelData.enabled
                                onClicked: {
                                    var id = row.modelData.primaryTmccId
                                    if (modelData.key === "HOLD" || modelData.key === "PULSE")
                                        root.controller.holdQuickAction(id, true)
                                    else
                                        root.controller.quickAction(modelData.key, id)
                                }
                                onReleased: {
                                    var id = row.modelData.primaryTmccId
                                    if (modelData.key === "HOLD" || modelData.key === "PULSE")
                                        root.controller.holdQuickAction(id, false)
                                }
                            }
                        }
                    }
                    Label {
                        visible: row.modelData.quickActions.length === 0
                        text: row.modelData.preferredView
                        color: "#f4f6f8"
                        font.pixelSize: 13
                        font.bold: true
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
                    longPressThreshold: 0.75

                    function hasAction(key) {
                        return row.modelData.quickActions.some(function(action) {
                            return action.key === key &&
                                   (action.enabled === undefined || action.enabled)
                        })
                    }

                    onTapped: root.accessoryRequested(row.modelData.key)
                    onDoubleTapped: {
                        if (hasAction("ON") && hasAction("OFF"))
                            root.controller.toggleQuickAction(row.modelData.primaryTmccId)
                    }
                }
            }
        }
    }
    LcsConfig {
        id: lcsConfig
        controller: root.lcsController
    }
}
