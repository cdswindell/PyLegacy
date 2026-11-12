import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RosterPanel {
    id: root
    readonly property real editorTop: pageLayout.y + pageAllStop.parent.y + pageAllStop.y + pageAllStop.height + 8

    property var controller
    property var lcsController: null
    property string searchText: ""
    property int directTmccId: 0
    property string sortMode: "NAME"
    property string typeFilter: "ALL"
    property bool showUnnamedAccessories: false

    signal accessoryRequested(string key)
    signal addRequested()
    signal lcsRequested()
    signal cabMenuRequested()

    function openTmccKeypad() {
        tmccKeypad.openFor(root.searchText)
    }

    function openLcsConfiguration() {
        if (root.lcsController)
            lcsConfig.open()
    }

    function selectTmccId(tmccId, fromSearch) {
        const exists = root.controller && root.controller.rows.some(function(row) {
            return row.primaryTmccId === tmccId || row.tmccIds.indexOf(tmccId) >= 0
        })
        if (!exists) {
            if (fromSearch) tmccKeypad.openFor(searchField.text)
            tmccKeypad.errorText = "No accessory with TMCC ID " + tmccId + "."
            return
        }
        root.typeFilter = "ALL"
        root.directTmccId = tmccId
        root.searchText = String(tmccId)
        tmccKeypad.close()
    }

    function showRoster() {
        cancelTransientPanels()
        directTmccId = 0
        searchText = ""
        searchField.clear()
        typeFilter = "ALL"
        listView.positionViewAtBeginning()
    }

    function cancelTransientPanels() {
        tmccKeypad.close()
        lcsConfig.close()
    }

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
            if (root.directTmccId > 0)
                return row.primaryTmccId === root.directTmccId || row.tmccIds.indexOf(root.directTmccId) >= 0
            if (!root.showUnnamedAccessories && !row.userDefined)
                return false
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
        font.pixelSize: 26
        font.bold: selected
    }

    ColumnLayout {
        id: pageLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            RosterMenuButton {
                text: "Operating Accessories"
                onClicked: root.cabMenuRequested()
            }
            AllStopButton { id: pageAllStop; compact: root.height < 850; onClicked: root.controller.halt() }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            ChoiceButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 92
                text: "ADD…"
                enabled: !lcsConfig.visible
                onClicked: root.addRequested()
            }
            ChoiceButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 92
                text: "LCS…"
                enabled: !lcsConfig.visible
                onClicked: root.lcsRequested()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            TouchSearchField {
                id: searchField
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.minimumHeight: 54
                Layout.maximumHeight: 54
                Layout.preferredHeight: 54
                Layout.alignment: Qt.AlignVCenter
                placeholderText: "Name, road #, or TMCC ID"
                font.pixelSize: 26
                selectByMouse: true
                text: root.searchText
                onTextEdited: { root.directTmccId = 0; root.searchText = text }
                onAccepted: if (/^[0-9]+$/.test(text) && Number(text) > 0 && Number(text) <= 98) root.selectTmccId(Number(text), true)
            }
            RosterBackspaceButton { field: searchField }
            KeypadButton {
                Layout.preferredWidth: 84
                Layout.preferredHeight: 84
                onClicked: root.openTmccKeypad()
            }
            RosterSetButton {
                entryText: searchField.text
                maximumId: 98
                onClicked: root.selectTmccId(Number(searchField.text), true)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: [{key:"NAME",label:"Name"},{key:"ROAD",label:"Road #"},{key:"TMCC",label:"TMCC ID"}]
                ChoiceButton {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 84
                    text: modelData.label
                    selected: root.sortMode === modelData.key
                    onClicked: root.sortMode = modelData.key
                }
            }
        }
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: 84
            orientation: ListView.Horizontal
            spacing: 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: [
                {key:"ALL",label:"All"}, {key:"OPERATING",label:"Operating"},
                {key:"ASC2",label:"ASC2"}, {key:"AMC2",label:"AMC2"},
                {key:"BPC2",label:"BPC2"}, {key:"SENSOR_TRACK",label:"Sensor Track"}
            ]
            delegate: ChoiceButton {
                required property var modelData
                width: modelData.label.length > 8 ? 240 : modelData.label.length > 5 ? 220 : 164
                height: 84
                text: modelData.label
                selected: root.typeFilter === modelData.key
                onClicked: root.typeFilter = modelData.key
            }
        }
        CheckBox {
            Layout.preferredHeight: 76
            Layout.minimumHeight: 76
            text: "Show Unnamed"
            font.pixelSize: 22
            checked: root.showUnnamedAccessories
            onToggled: root.showUnnamedAccessories = checked
        }
        ListView {
            id: listView
            enabled: !lcsConfig.visible
            objectName: "accessoryRoster"
            Layout.leftMargin: -6
            Layout.rightMargin: Layout.leftMargin
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            clip: true
            spacing: 10
            boundsBehavior: Flickable.StopAtBounds
            flickDeceleration: 1800
            model: root.visibleRows()
            delegate: Rectangle {
                id: row
                required property var modelData
                width: ListView.view.width
                height: 156
                radius: 8
                color: tapHandler.pressed ? "#354150" : "#272d35"
                opacity: row.modelData.componentEnabled === false ? 0.62 : 1.0
                border.width: 1
                border.color: "#4b5664"
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Label {
                            Layout.preferredWidth: 70
                            text: row.modelData.primaryTmccId
                            color: "#55bdf5"
                            font.pixelSize: 36
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 2
                            Label {
                                Layout.fillWidth: true
                                text: row.modelData.roadName
                                color: "#f4f6f8"
                                font.pixelSize: 28
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Label {
                                Layout.fillWidth: true
                                text: (row.modelData.roadNumber ? "Road #" + row.modelData.roadNumber : "") +
                                      (row.modelData.lcsAssociations ? " · " + row.modelData.lcsAssociations : "")
                                color: "#b8c0ca"
                                font.pixelSize: 20
                                elide: Text.ElideRight
                            }
                            Label {
                                Layout.fillWidth: true
                                visible: row.modelData.quickActions.length > 0 && row.modelData.stateSummary.length > 0
                                text: row.modelData.stateSummary
                                color: "#8fc9ef"
                                font.pixelSize: 18
                                font.bold: true
                                elide: Text.ElideRight
                            }
                        }
                        Label { text: "›"; color: "#8fc9ef"; font.pixelSize: 42 }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        visible: row.modelData.quickActions.length > 0
                        spacing: 8
                        Repeater {
                            model: row.modelData.quickActions
                            ChoiceButton {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.preferredWidth: (modelData.key === "HOLD" || modelData.key === "PULSE") ? 208 : 116
                                Layout.preferredHeight: 57
                                text: modelData.label
                                font.bold: modelData.selected
                                selected: modelData.selected
                                enabled: modelData.enabled === undefined || modelData.enabled
                                onClicked: {
                                    var id = row.modelData.primaryTmccId
                                    if (modelData.key === "HOLD" || modelData.key === "PULSE") root.controller.holdQuickAction(id, true)
                                    else root.controller.quickAction(modelData.key, id)
                                }
                                onReleased: {
                                    var id = row.modelData.primaryTmccId
                                    if (modelData.key === "HOLD" || modelData.key === "PULSE") root.controller.holdQuickAction(id, false)
                                }
                            }
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: row.modelData.quickActions.length === 0
                        text: row.modelData.stateSummary || row.modelData.availableViews.join(" · ")
                        color: "#8fc9ef"
                        font.pixelSize: 22
                        elide: Text.ElideRight
                    }
                }
                TapHandler {
                    id: tapHandler
                    gesturePolicy: TapHandler.DragThreshold
                    longPressThreshold: 0.75
                    function hasAction(key) {
                        return row.modelData.quickActions.some(function(action) { return action.key === key && (action.enabled === undefined || action.enabled) })
                    }
                    onTapped: root.accessoryRequested(row.modelData.key)
                    onDoubleTapped: {
                        if (hasAction("ON") && hasAction("OFF")) root.controller.toggleQuickAction(row.modelData.primaryTmccId)
                    }
                }
            }
        }
    }
    LcsConfig {
        id: lcsConfig
        controller: root.lcsController
        editorTop: root.editorTop
    }

    TmccKeypad {
        id: tmccKeypad
        title: "Accessory TMCC ID"
        onSubmitted: function(tmccId) { root.selectTmccId(tmccId, false) }
    }

}
