import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RosterPanel {
    id: root
    readonly property Item inputRoster: listView

    readonly property real editorTop: pageLayout.y + pageAllStop.parent.y + pageAllStop.y + pageAllStop.height + 8

    property var controller
    property var lcsConfig: null
    property string searchText: ""
    property int directTmccId: 0
    property string sortMode: "TMCC"
    property string typeFilter: "ALL"
    readonly property var lcsFilterKinds: ["SENSOR", "BPC2", "ASC2", "AMC2"]
    readonly property string detectedFilterKinds: {
        const kinds = new Set(controller ? controller.rows.map(row => row.kind) : [])
        return lcsFilterKinds.concat("OPERATING").filter(kind => kinds.has(kind)).join(",")
    }
    readonly property var typeFilters: {
        const kinds = new Set(detectedFilterKinds.split(","))
        return [
            {key: "ALL", label: "All"},
            {key: "OPERATING", label: "Operating"},
            {key: "LCS", label: "LCS"},
            {key: "TMCC", label: "TMCC"},
            {key: "SENSOR", label: "Sensor"},
            {key: "BPC2", label: "BPC2"},
            {key: "ASC2", label: "ASC2"},
            {key: "AMC2", label: "AMC2"}
        ].filter(filter => filter.key === "ALL" || filter.key === "TMCC" ||
            (filter.key === "LCS" ? lcsFilterKinds.some(kind => kinds.has(kind)) : kinds.has(filter.key)))
    }
    onTypeFiltersChanged: {
        if (!typeFilters.some(filter => filter.key === typeFilter))
            typeFilter = "ALL"
    }
    property bool showUnnamedAccessories: false
    readonly property bool compact: height < 850
    property int activeQuickActions: 0
    readonly property var rosterRows: visibleRows()
    onRosterRowsChanged: {
        if (listView && activeQuickActions === 0)
            listView.refreshRows()
    }
    onActiveQuickActionsChanged: {
        if (listView && activeQuickActions === 0)
            listView.refreshRows()
    }

    signal accessoryRequested(string key)
    signal editRequested(int tmccId, string kind)
    signal addRequested()
    signal lcsRequested()
    signal cabMenuRequested()

    function openTmccKeypad() {
        tmccKeypad.openFor(root.searchText)
    }

    function openLcsConfiguration() {
        if (root.lcsConfig)
            lcsConfig.open()
    }

    function openDirectControl(tmccId, fromKeypad) {
        const rows = root.controller ? root.controller.rows : []
        const control = rows.find(row => row.primaryTmccId === tmccId &&
            (row.kind === "AMC2" || row.kind === "SENSOR"))
            ?? (fromKeypad ? rows.find(row => row.primaryTmccId === tmccId && row.kind === "TMCC") : undefined)
        if (!control)
            return false

        root.directTmccId = 0
        root.searchText = ""
        searchField.clear()
        tmccKeypad.close()
        root.accessoryRequested(control.key)
        return true
    }

    function selectTmccId(tmccId, fromSearch, reportMissing = true) {
        if (root.openDirectControl(tmccId, !fromSearch))
            return

        const rows = root.controller ? root.controller.rows : []
        if (!rows.some(row => row.primaryTmccId === tmccId || row.tmccIds.includes(tmccId))) {
            if (!reportMissing)
                return
            if (fromSearch) tmccKeypad.openFor(searchField.text)
            tmccKeypad.errorText = "No accessory with TMCC ID " + tmccId + "."
            return
        }
        root.typeFilter = "ALL"
        root.directTmccId = tmccId
        root.searchText = String(tmccId)
        tmccKeypad.close()
    }

    function rosterRowHeight(row) {
        return row.kind === "ASC2" || row.kind === "BPC2" ? 146 : 112
    }

    function restoreRosterPosition(key) {
        const target = controller.rows.find(row => row.key === key)
        if (!target || !visible)
            return
        if (!rosterRows.some(row => row.key === key)) {
            directTmccId = 0
            searchText = ""
            searchField.clear()
            typeFilter = "ALL"
            if (!target.userDefined)
                showUnnamedAccessories = true
        }

        listView.refreshRows()
        const index = listView.model.findIndex(row => row.key === key)
        if (index < 0)
            return

        // Reserve only the extra space needed to top-align a row near the end.
        const tail = listView.model.slice(index)
        const tailHeight = tail.reduce((height, row) => height + rosterRowHeight(row), 0)
            + (tail.length - 1) * listView.spacing
        listView.returnSpace = Math.max(0, listView.height - tailHeight)
        listView.forceLayout()
        listView.positionViewAtIndex(index, ListView.Beginning)
    }

    function showRoster() {
        cancelTransientPanels()
        listView.returnSpace = 0
        directTmccId = 0
        searchText = ""
        searchField.clear()
        typeFilter = "ALL"
        listView.positionViewAtBeginning()
    }

    function cancelTransientPanels() {
        tmccKeypad.close()
        searchField.closeTouchKeyboard()
        if (lcsConfig) lcsConfig.close()
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
        var rows = controller.rows.filter(function(row) {
            if (root.directTmccId > 0)
                return row.tmccIds.indexOf(root.directTmccId) >= 0
            if (root.typeFilter === "LCS") {
                if (!root.lcsFilterKinds.includes(row.kind))
                    return false
            } else if (root.typeFilter !== "ALL" && root.typeFilter !== row.kind) {
                return false
            }
            if (!root.showUnnamedAccessories && !row.userDefined)
                return false
            if (!needle)
                return true
            return row.roadName.toLowerCase().indexOf(needle) >= 0 ||
                   row.roadNumber.toLowerCase().indexOf(needle) >= 0 ||
                   row.tmccIds.some(id => String(id).indexOf(needle) >= 0) ||
                   row.lcsAssociations.toLowerCase().indexOf(needle) >= 0 ||
                   (row.componentNames || "").toLowerCase().indexOf(needle) >= 0
        })
        rows.sort(function(a, b) {
            if (root.typeFilter === "ALL") {
                const aOperating = a.kind === "OPERATING"
                const bOperating = b.kind === "OPERATING"
                if (aOperating !== bOperating)
                    return aOperating ? -1 : 1
                if (aOperating) {
                    const nameOrder = a.roadName.toLowerCase().localeCompare(b.roadName.toLowerCase())
                    return nameOrder || a.primaryTmccId - b.primaryTmccId
                }
            }
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
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0
        Layout.preferredHeight: pageAllStop.height
        font.pixelSize: pageAllStop.font.pixelSize
    }

    ColumnLayout {
        id: pageLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        RowLayout {
            id: rosterHeader
            Layout.fillWidth: true
            spacing: 10
            RosterHeaderActions {
                id: headerActions
                headerWidth: pageLayout.width
                headerSpacing: rosterHeader.spacing
                stopWidth: pageAllStop.Layout.preferredWidth
                titleFont: rosterTitle.titleFont
                ChoiceButton {
                    text: "Add…"
                    enabled: !lcsConfig || !lcsConfig.visible
                    onClicked: root.addRequested()
                }
                ChoiceButton {
                    text: "LCS…"
                    enabled: !lcsConfig || !lcsConfig.visible
                    onClicked: root.lcsRequested()
                }
            }
            CabMenuTitle {
                id: rosterTitle
                rosterTitle: true
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.rightMargin: headerActions.titleRightMargin
                compact: root.compact
                title: "Accessories"
                onActivated: root.cabMenuRequested()
            }
            AllStopButton { id: pageAllStop; compact: root.compact; onClicked: root.controller.halt() }
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
                onTouchKeyboardFinished: if (/^[0-9]+$/.test(text)) root.selectTmccId(Number(text), true, false)
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
        RosterSortBar {
            roster: listView
            compact: root.compact
            keys: ["TMCC", "NAME", "ROAD"]
            selectedKey: root.sortMode
            onSelected: key => root.sortMode = key
        }
        CheckBox {
            Layout.preferredHeight: 54
            Layout.minimumHeight: 54
            text: "Show Unnamed"
            font.pixelSize: 22
            checked: root.showUnnamedAccessories
            onToggled: root.showUnnamedAccessories = checked
        }
        RosterFilterTabs {
            objectName: "accessoryFilterTabs"
            selectedKey: root.typeFilter
            model: root.typeFilters
            onSelected: key => root.typeFilter = key
        }
        ListView {
            id: listView
            enabled: !lcsConfig || !lcsConfig.visible
            objectName: "accessoryRoster"
            property real returnSpace: 0
            footer: Item { height: listView.returnSpace }
            Layout.leftMargin: -6
            Layout.rightMargin: Layout.leftMargin
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            clip: true
            spacing: 10
            boundsBehavior: Flickable.StopAtBounds
            flickDeceleration: 1800
            // Refresh after the release click so command feedback cannot replace its delegate mid-gesture.
            function refreshRows() {
                const rows = root.rosterRows
                if (model === rows)
                    return

                // The top of the viewport may fall in the gap between delegates.
                let index = indexAt(width / 2, contentY)
                if (index < 0)
                    index = indexAt(width / 2, contentY + spacing)
                const item = itemAtIndex(index)
                const offset = item ? contentY - item.y : 0
                const anchorIndex = item ? rows.findIndex(entry => entry.key === item.modelData.key) : -1

                model = rows
                if (anchorIndex >= 0) {
                    positionViewAtIndex(anchorIndex, ListView.Beginning)
                    forceLayout()
                    const anchor = itemAtIndex(anchorIndex)
                    if (anchor) {
                        const bottom = originY + Math.max(0, contentHeight - height)
                        contentY = Math.min(bottom, Math.max(originY, anchor.y + offset))
                    }
                }
            }
            Component.onCompleted: refreshRows()

            ScrollBar.vertical: ListScrollBar { id: rosterScrollBar }

            delegate: Rectangle {
                id: row
                required property var modelData
                objectName: "accessoryRosterRow-" + modelData.key
                width: listView.width - rosterScrollBar.gutterWidth
                height: root.rosterRowHeight(modelData)
                radius: 8
                color: tapHandler.pressed || quickActionTap.pressed ? "#354150" : "#23303d"
                border.width: 1
                border.color: "#4b5664"
                property int heldAddress: 0
                readonly property bool canHold: modelData.kind === "ASC2" &&
                    modelData.quickActions.some(action => action.key === "HOLD" && action.enabled !== false)

                function beginHold() {
                    if (!canHold || heldAddress ||
                        !quickActionTap.acceptsTap(quickActionTap.point.position))
                        return
                    heldAddress = modelData.primaryTmccId
                    ++root.activeQuickActions
                    root.controller.holdQuickAction(heldAddress, true)
                }

                function releaseHold() {
                    if (!heldAddress)
                        return
                    const address = heldAddress
                    heldAddress = 0
                    root.controller.holdQuickAction(address, false)
                    Qt.callLater(() => --root.activeQuickActions)
                }

                onEnabledChanged: if (!enabled) releaseHold()
                onVisibleChanged: if (!visible) releaseHold()
                Component.onDestruction: releaseHold()

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        RosterIdBadge {
                            readonly property string kind: row.modelData.kind
                            Layout.preferredWidth: 70
                            Layout.preferredHeight: 54
                            abbreviation: kind === "OPERATING" ? "" : kind === "TMCC" ? "ACC" :
                                          kind === "SENSOR" ? "IRDA" : kind
                            tmccId: row.modelData.primaryTmccId
                            displayValue: kind === "OPERATING" ? "OP" : String(tmccId)
                            imageSource: kind === "OPERATING" ? row.modelData.imageSource : ""
                            numberSize: 26
                        }
                        Image {
                            visible: row.modelData.kind !== "OPERATING" && row.modelData.imageSource.length > 0
                            source: visible ? row.modelData.imageSource : ""
                            Layout.preferredWidth: visible ? 68 : 0
                            Layout.preferredHeight: 54
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 2
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                MarqueeLabel {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: row.modelData.roadName
                                    color: "#f4f6f8"
                                    font.pixelSize: 28
                                    font.bold: true
                                }
                                Label {
                                    visible: !!row.modelData.roadNumber
                                    text: "#" + row.modelData.roadNumber
                                    color: "#b8c0ca"
                                    font.pixelSize: 20
                                }
                            }
                            Label {
                                Layout.fillWidth: true
                                visible: !!row.modelData.lcsAssociations
                                text: row.modelData.lcsAssociations
                                color: "#b8c0ca"
                                font.pixelSize: 20
                                elide: Text.ElideRight
                            }
                        }
                        Label { visible: !quickActions.visible && row.modelData.kind !== "ASC2" && row.modelData.kind !== "BPC2"; text: "›"; color: "#8fc9ef"; font.pixelSize: 42 }
                    }
                    RowLayout {
                        id: quickActions
                        Layout.fillWidth: true
                        visible: row.modelData.kind === "ASC2" || row.modelData.kind === "BPC2"
                        spacing: 8
                        Repeater {
                            model: row.modelData.quickActions
                            AccessoryActionButton {
                                required property var modelData
                                controller: root.controller
                                tmccId: row.modelData.primaryTmccId
                                deviceKind: row.modelData.kind
                                action: modelData.key
                                onAccessoryPressChanged: active => {
                                    if (active)
                                        ++root.activeQuickActions
                                    else
                                        Qt.callLater(() => --root.activeQuickActions)
                                }
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.preferredWidth: 102
                                Layout.preferredHeight: 57
                                text: modelData.label
                                Accessible.name: modelData.label
                                font.pixelSize: 23
                                font.bold: true
                                selected: modelData.selected || heldAddress !== 0
                                enabled: modelData.enabled === undefined || modelData.enabled
                            }
                        }
                        CabButton {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 102
                            Layout.preferredHeight: 57
                            text: "Edit"
                            activateOnRelease: true
                            onClicked: root.editRequested(row.modelData.primaryTmccId, row.modelData.kind)
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: !quickActions.visible && !!row.modelData.stateSummary
                        text: row.modelData.stateSummary
                        color: "#8fc9ef"
                        font.pixelSize: 22
                        elide: Text.ElideRight
                    }
                }
                TapHandler {
                    id: tapHandler
                    enabled: !quickActions.visible
                    gesturePolicy: TapHandler.DragThreshold
                    onTapped: root.accessoryRequested(row.modelData.key)
                }
                ControlTapHandler {
                    id: quickActionTap
                    enabled: quickActions.visible && !listView.moving
                    acceptsTap: position => !quickActions.contains(quickActions.mapFromItem(row, position))
                    holdEnabled: row.canHold
                    longPressThreshold: 0.55
                    onHeldGesture: row.beginHold()
                    onPressedChanged: if (!pressed) row.releaseHold()
                    onCanceled: row.releaseHold()
                    onEnabledChanged: if (!enabled) row.releaseHold()
                    onTappedTwice: {
                        const actions = row.modelData.quickActions
                        const supports = key => actions.some(action => action.key === key && action.enabled !== false)
                        if (supports("ON") && supports("OFF"))
                            root.controller.toggleQuickAction(row.modelData.primaryTmccId, row.modelData.kind)
                    }
                }
            }
        }
    }
    TmccKeypad {
        id: tmccKeypad
        title: "Accessory TMCC ID"
        onSubmitted: function(tmccId) { root.selectTmccId(tmccId, false) }
    }

}
