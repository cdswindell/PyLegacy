import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RosterPanel {
    id: root

    required property var cab
    required property var catalog
    required property var selection
    readonly property bool canOpenCab: cab.rememberedCabScopes.includes(scope)
    property var infoController: null
    signal cabMenuRequested()
    signal engineSelected()
    signal closeRequested()
    signal engineRequested(int tmccId)
    signal stateInfoRequested(string scope, int tmccId)

    function openTmccKeypad() {
        tmccKeypad.openFor(root.searchText)
    }

    function cancelTransientPanels() {
        tmccKeypad.close()
        searchField.closeTouchKeyboard()
    }

    function requestAddress(tmccId) {
        if (scope === "ENGINE" && infoController && infoController.needsEngineRecord(tmccId))
            stateInfoRequested(scope, tmccId)
        else
            engineRequested(tmccId)
    }

    onEngineRequested: function(tmccId) {
        if (!cab.selectAddress(scope, tmccId)) {
            stateInfoRequested(scope, tmccId)
            return
        }
        if (scope === "ENGINE")
            selection.selectEngine(tmccId)
        directTmccId = 0
        searchText = ""
        engineSelected()
    }


    radius: 10

    property string sortMode: "tmcc"
    property string searchText: ""
    property int directTmccId: 0
    property string scope: "ENGINE"
    readonly property var targets: catalog ? (scope === "TRAIN" ? catalog.trains : catalog.engines) : []
    onScopeChanged: { searchText = ""; directTmccId = 0; tmccKeypad.close() }
    property string engineTypeFilter: "ALL"
    property string trainTypeFilter: "ALL"
    readonly property var typeFilters: {
        const availableTypes = new Set(targets.map(target => target.engineType))
        return [{ key: "ALL", label: "All" }].concat(catalog
            ? catalog.typeFilters.filter(filter => availableTypes.has(filter.key)) : [])
    }
    readonly property string typeFilter: {
        const selected = scope === "TRAIN" ? trainTypeFilter : engineTypeFilter
        return typeFilters.some(filter => filter.key === selected) ? selected : "ALL"
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
        if (!catalog)
            return rows
        var needle = searchText.trim().toLowerCase()
        for (var i = 0; i < root.targets.length; ++i) {
            var engine = root.targets[i]
            if (directTmccId > 0 && engine.tmccId !== directTmccId)
                continue
            if (directTmccId === 0 && typeFilter !== "ALL" && engine.engineType !== typeFilter)
                continue
            var searchable = (engine.roadName + " " + engine.roadNumber + " " + engine.tmccId + " " +
                              engine.engineType + " " + engine.engineTypeLabel).toLowerCase()
            if (directTmccId === 0 && needle.length && searchable.indexOf(needle) < 0)
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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            CabButton {
                Layout.preferredWidth: pageAllStop.width
                Layout.preferredHeight: pageAllStop.height
                text: "Cab"
                enabled: root.canOpenCab
                font.pixelSize: 24
                onClicked: root.closeRequested()
            }
            CabMenuTitle {
                rosterTitle: true
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                compact: pageAllStop.compact
                title: root.scope === "TRAIN" ? "Trains" : "Engines"
                identity: root.filteredTargets().length + (root.scope === "TRAIN" ? " trains" : " engines")
                onActivated: root.cabMenuRequested()
            }
            AllStopButton { id: pageAllStop; compact: root.height < 850; onClicked: cab.halt() }
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
                onAccepted: {
                    if (/^[0-9]{1,4}$/.test(text) && Number(text) > 0)
                        root.requestAddress(Number(text))
                }
            }
            RosterBackspaceButton { field: searchField }
            KeypadButton {
                Layout.preferredWidth: 84
                Layout.preferredHeight: 84
                onClicked: root.openTmccKeypad()
            }
            RosterSetButton {
                showButton: root.scope === "ENGINE"
                entryText: searchField.text
                maximumId: 9999
                onClicked: root.requestAddress(Number(searchField.text))
            }
        }

        RosterSortBar {
            roster: listView
            compact: root.height < 850
            keys: ["tmcc", "name", "road"]
            selectedKey: root.sortMode
            onSelected: key => root.sortMode = key
        }

        RosterFilterTabs {
            objectName: "engineFilterTabs"
            selectedKey: root.typeFilter
            model: root.typeFilters
            onSelected: key => {
                if (root.scope === "TRAIN")
                    root.trainTypeFilter = key
                else
                    root.engineTypeFilter = key
            }
        }

        ListView {
            id: listView
            objectName: "engineRoster"
            Layout.leftMargin: -6
            Layout.rightMargin: Layout.leftMargin
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            boundsBehavior: Flickable.StopAtBounds
            flickDeceleration: 1800
            model: root.filteredTargets()

            ScrollBar.vertical: ListScrollBar { id: rosterScrollBar }

            delegate: Rectangle {
                id: row
                required property var modelData
                width: listView.width - rosterScrollBar.gutterWidth
                height: 108
                radius: 8
                color: tapHandler.pressed ? "#354150" : "#23303d"
                border.width: 1
                border.color: "#4b5664"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 14
                    RosterIdBadge {
                        Layout.preferredWidth: 132
                        Layout.preferredHeight: 92
                        abbreviation: root.scope === "TRAIN" ? "TRN" : "ENG"
                        tmccId: row.modelData.tmccId
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        MarqueeLabel {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: (row.modelData.roadName || (root.scope === "TRAIN" ? "Train" : "Engine")) + (row.modelData.roadNumber ? "  #" + row.modelData.roadNumber : "")
                            color: "#f3f5f7"
                            font.pixelSize: 28
                            font.bold: true
                        }
                        Label {
                            Layout.fillWidth: true
                            text: row.modelData.engineTypeLabel +
                                  (row.modelData.controlTypeLabel ? " · " + row.modelData.controlTypeLabel : "")
                            color: "#a9b2bd"
                            font.pixelSize: 20
                            elide: Text.ElideRight
                        }
                    }
                    Label { text: "›"; color: "#8fc9ef"; font.pixelSize: 28 }
                }

                TapHandler {
                    id: tapHandler
                    gesturePolicy: TapHandler.DragThreshold
                    onTapped: root.engineRequested(row.modelData.tmccId)
                }
            }
        }
    }

    TmccKeypad {
        id: tmccKeypad
        title: (root.scope === "TRAIN" ? "Train" : "Engine") + " TMCC ID"
        maximumId: 9999
        showSetAddress: root.scope === "ENGINE" && !!root.infoController
        onSetAddressRequested: function(tmccId) {
            const error = root.infoController.programEngineAddress(tmccId)
            if (error) {
                errorText = error
                return
            }
            close()
            root.requestAddress(tmccId)
        }
        onSubmitted: function(tmccId) {
            close()
            root.requestAddress(tmccId)
        }
    }

}
