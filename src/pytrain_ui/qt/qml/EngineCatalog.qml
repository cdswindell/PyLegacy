import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var cab
    required property var catalog
    required property var selection
    property var infoController: null
    signal cabMenuRequested()
    signal engineSelected()
    signal closeRequested()
    signal engineRequested(int tmccId)
    signal stateInfoRequested(string scope, int tmccId)

    function openTmccKeypad() {
        tmccKeypad.openFor(root.searchText)
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


    color: "#0d1f58"
    gradient: Gradient {
        GradientStop { position: 0; color: "#173775" }
        GradientStop { position: 0.5; color: "#0d1f58" }
        GradientStop { position: 1; color: "#09183f" }
    }
    radius: 10

    property string sortMode: "name"
    property string searchText: ""
    property int directTmccId: 0
    property string scope: "ENGINE"
    readonly property var targets: catalog ? (scope === "TRAIN" ? catalog.trains : catalog.engines) : []
    onScopeChanged: { searchText = ""; directTmccId = 0; typeFilter = "ALL"; tmccKeypad.close() }
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

    component ChoiceButton: CabButton {
        font.pixelSize: 26
        font.bold: selected
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                CabButton {
                    text: root.scope === "TRAIN" ? "Trains  ▾" : "Engines  ▾"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    font.pixelSize: 22
                    onClicked: root.cabMenuRequested()
                }
                Label { text: root.filteredTargets().length + (root.scope === "TRAIN" ? " trains" : " engines"); color: "#aeb7c2"; font.pixelSize: 18 }
            }
            Item { Layout.fillWidth: true }
            CabButton { Layout.preferredWidth: 144; Layout.preferredHeight: root.height < 850 ? 72 : 88; text: "Cab"; enabled: cab.tmccId > 0; font.pixelSize: 24; onClicked: root.closeRequested() }
            AllStopButton { compact: root.height < 850; onClicked: cab.halt() }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            TouchSearchField {
                id: searchField
                Layout.fillWidth: true
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
                entryText: searchField.text
                maximumId: 9999
                onClicked: root.requestAddress(Number(searchField.text))
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            ChoiceButton { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0; Layout.preferredHeight: 84; text: "Name"; selected: root.sortMode === "name"; onClicked: root.sortMode = "name" }
            ChoiceButton { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0; Layout.preferredHeight: 84; text: "Road #"; selected: root.sortMode === "road"; onClicked: root.sortMode = "road" }
            ChoiceButton { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0; Layout.preferredHeight: 84; text: "TMCC ID"; selected: root.sortMode === "tmcc"; onClicked: root.sortMode = "tmcc" }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            ListView {
                id: typeList
                Layout.fillWidth: true
                Layout.preferredHeight: 84
                orientation: ListView.Horizontal
                spacing: 7
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: [{ "key": "ALL", "label": "All" }].concat(root.catalog ? root.catalog.typeFilters : [])
                delegate: ChoiceButton {
                    required property var modelData
                    width: Math.max(164, implicitWidth + 40)
                    height: 84
                    text: modelData.label
                    selected: root.typeFilter === modelData.key
                    onClicked: root.typeFilter = modelData.key
                }
            }
        }

        ListView {
            id: listView
            objectName: "engineRoster"
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
                height: 108
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
                        Layout.preferredWidth: 132
                        Layout.preferredHeight: 92
                        radius: 7
                        color: "#1c2229"
                        border.width: 1
                        border.color: "#596574"
                        Column {
                            anchors.centerIn: parent
                            Label { anchors.horizontalCenter: parent.horizontalCenter; text: root.scope === "TRAIN" ? "TRN" : "ENG"; color: "#9ea6b0"; font.pixelSize: 14; font.bold: true }
                            Label { anchors.horizontalCenter: parent.horizontalCenter; text: row.modelData.tmccId; color: "white"; font.pixelSize: 36; font.bold: true }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            Layout.fillWidth: true
                            text: (row.modelData.roadName || (root.scope === "TRAIN" ? "Train" : "Engine")) + (row.modelData.roadNumber ? "  #" + row.modelData.roadNumber : "")
                            color: "#f3f5f7"
                            font.pixelSize: 28
                            font.bold: true
                            elide: Text.ElideRight
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
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
