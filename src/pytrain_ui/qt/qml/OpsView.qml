import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RosterPanel {
    id: root

    PanelMetrics { id: metrics }
    readonly property real editorTop: pageLayout.y + pageAllStop.parent.y + pageAllStop.y + pageAllStop.height + 8

    required property var controller
    property var lcsController: null
    property bool editorNavigationPending: false
    readonly property bool hasUnsavedRouteChanges: routeBuilder.visible && controller.routeBuilderOpen &&
        (controller.routeBuilderDirty ||
         routeIdField.text.trim() !== (controller.routeBuilderId ? String(controller.routeBuilderId) : "") ||
         routeNameField.text.trim() !== controller.routeBuilderName ||
         routeNumberField.text.trim() !== controller.routeBuilderNumber)
    signal routeCloseRequested()

    property string sortKey: "roadName"
    property string routeStateFilter: "ALL"
    property int directTmccId: 0
    property var rightHandSwitches: ({})
    property int editingSwitchId: 0
    property string editingSwitchOriginalName: ""
    property string editingSwitchOriginalNumber: ""
    property int pendingOverwriteSwitchId: 0
    property bool addCommandControl: true
    readonly property var addSwitchIdentity: {
        root.rosterRows
        return controller && addSwitchId.acceptableInput ? controller.switchIdentity(Number(addSwitchId.text)) : ({})
    }
    readonly property bool addingAsc2Switch: !!addSwitchIdentity.asc2Switch
    property string populatedSwitchName: ""
    property string populatedSwitchNumber: ""
    property bool showInactiveSwitches: false
    property string routeCandidateScope: "SWITCH"
    property string routeCandidateSearch: ""
    property string routeCandidateSortKey: "roadName"
    property bool showUnnamedRouteSwitches: false
    signal closeRequested()
    signal cabMenuRequested()

    radius: 14

    component IdentityNumberField: TextField {
        id: numberField

        required property string keypadTitle
        property bool address: false
        signal keypadAccepted()

        maximumLength: address ? 2 : 4
        inputMethodHints: Qt.ImhDigitsOnly
        validator: RegularExpressionValidator {
            regularExpression: /[0-9]{0,4}/
        }

        TapHandler {
            enabled: Qt.platform.os === "linux"
            onTapped: keypad.openFor(numberField.text)
        }

        TmccKeypad {
            id: keypad
            title: numberField.keypadTitle
            minimumId: numberField.address ? 1 : 0
            maximumId: numberField.address ? 98 : 9999
            allowEmpty: !numberField.address
            onSubmitted: {
                numberField.text = entryText
                close()
                numberField.keypadAccepted()
            }
        }

        onVisibleChanged: if (!visible) keypad.close()
    }

    function toggleSwitchHandedness(tmccId) {
        rightHandSwitches = Object.assign({}, rightHandSwitches, {[tmccId]: !rightHandSwitches[tmccId]})
    }

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
        if (!controller)
            return []
        const query = searchField.text.trim().toLowerCase()
        const result = controller.rows.filter(function(row) {
            if (root.directTmccId > 0)
                return row.tmccId === root.directTmccId
            if (controller.scope === "SWITCH" && row.inactive && !root.showInactiveSwitches)
                return false
            if (controller.scope === "ROUTE" && root.routeStateFilter !== "ALL" && row.stateText !== root.routeStateFilter)
                return false
            return !query ||
                   String(row.tmccId).toLowerCase().indexOf(query) >= 0 ||
                   row.roadName.toLowerCase().indexOf(query) >= 0 ||
                   row.roadNumber.toLowerCase().indexOf(query) >= 0 ||
                   row.lcsAssociations.toLowerCase().indexOf(query) >= 0
        })
        result.sort(compareRows)
        return result
    }

    readonly property var rosterRows: visibleRows()
    onRosterRowsChanged: {
        if (rosterModel)
            syncRoster()
    }
    Component.onCompleted: syncRoster()

    ListModel {
        id: rosterModel
        dynamicRoles: true
    }

    function syncRoster() {
        // Update existing rows in place so feedback preserves delegates, focus, and scrolling.
        for (let index = 0; index < rosterRows.length; ++index) {
            const nextRow = rosterRows[index]
            let existing = index
            while (existing < rosterModel.count && rosterModel.get(existing).tmccId !== nextRow.tmccId)
                ++existing
            if (existing === rosterModel.count)
                rosterModel.insert(index, { tmccId: nextRow.tmccId, rowData: nextRow })
            else {
                if (existing !== index)
                    rosterModel.move(existing, index, 1)
                rosterModel.setProperty(index, "rowData", nextRow)
            }
        }
        if (rosterModel.count > rosterRows.length)
            rosterModel.remove(rosterRows.length, rosterModel.count - rosterRows.length)
    }

    function canSetSwitchAddress(text) {
        root.rosterRows
        return controller && /^[0-9]+$/.test(text) && controller.canProgramSwitchAddress(Number(text))
    }

    function openTmccKeypad() {
        tmccKeypad.openFor(searchField.text)
    }

    function submitTmccId(fromSearch) {
        if (!fromSearch && !tmccKeypad.acceptableInput)
            return
        const tmccId = Number(fromSearch ? searchField.text : tmccKeypad.entryText)
        if (!controller.rows.some(function(row) { return row.tmccId === tmccId })) {
            if (fromSearch) tmccKeypad.openFor(searchField.text)
            tmccKeypad.errorText = "No " + (controller.scope === "SWITCH" ? "switch" : "route") +
                                  " with TMCC ID " + tmccId + "."
            return
        }
        root.directTmccId = tmccId
        searchField.text = String(tmccId)
        controller.select(tmccId)
        tmccKeypad.close()
        roster.positionViewAtBeginning()
        roster.forceActiveFocus()
    }

    function editSwitch(tmccId) {
        editingSwitchId = tmccId
        switchEditorError.text = ""
        roadNameField.text = controller.switchRoadName(tmccId)
        roadNumberField.text = controller.switchRoadNumber(tmccId)
        editingSwitchOriginalName = roadNameField.text
        editingSwitchOriginalNumber = roadNumberField.text
        switchEditor.open()
        roadNameField.forceActiveFocus()
    }

    function openAddSwitch() {
        addSwitchId.text = ""
        addRoadName.text = ""
        addRoadNumber.text = ""
        addCommandControl = true
        addError.text = ""
        pendingOverwriteSwitchId = 0
        populatedSwitchName = ""
        populatedSwitchNumber = ""
        addSwitchPopup.open()
        addSwitchId.forceActiveFocus()
    }

    function completeExistingSwitchIdentity() {
        if (addRoadName.text === populatedSwitchName)
            addRoadName.text = ""
        if (addRoadNumber.text === populatedSwitchNumber)
            addRoadNumber.text = ""
        populatedSwitchName = ""
        populatedSwitchNumber = ""

        const tmccId = Number(addSwitchId.text)
        if (tmccId < 1 || tmccId > 98)
            return
        const identity = controller.switchIdentity(tmccId)
        if (!identity.exists && !identity.asc2Switch) {
            if (!addRoadNumber.text.trim() || addRoadNumber.text === populatedSwitchNumber) {
                addRoadNumber.text = String(tmccId).padStart(4, "0")
                populatedSwitchNumber = addRoadNumber.text
            }
            return
        }
        if (!addRoadName.text.trim()) {
            addRoadName.text = identity.roadName
            populatedSwitchName = identity.roadName
        }
        if (!addRoadNumber.text.trim()) {
            addRoadNumber.text = identity.roadNumber
            populatedSwitchNumber = identity.roadNumber
        }
    }

    function openAddRoute() {
        controller.openNewRouteBuilder()
        routeIdField.text = ""
        routeNameField.text = ""
        routeNumberField.text = ""
        routeBuilderError.text = ""
        routeBuilder.open()
        routeIdField.forceActiveFocus()
    }

    function loadRouteBuilder(tmccId) {
        const error = controller.openRouteBuilder(tmccId)
        if (error.length > 0) {
            routeBuilderError.text = error
            return false
        }
        routeIdField.text = String(controller.routeBuilderId)
        routeNameField.text = controller.routeBuilderName
        routeNumberField.text = controller.routeBuilderNumber
        routeBuilderError.text = ""
        return true
    }

    function editRoute(tmccId) {
        if (!root.loadRouteBuilder(tmccId))
            return
        routeBuilder.open()
    }

    function routeIdEditingFinished() {
        if (root.editorNavigationPending)
            return
        const text = routeIdField.text.trim()
        if (!text.length)
            return
        const tmccId = Number(text)
        if (tmccId < 1 || tmccId > 98) {
            routeBuilderError.text = "Route ID must be an integer from 1 to 98."
            return
        }
        if (tmccId !== controller.routeBuilderId)
            root.loadRouteBuilder(tmccId)
    }

    function routeCandidateRows() {
        if (!controller || !controller.routeBuilderOpen)
            return []
        const query = routeCandidateSearch.trim().toLowerCase()
        return controller.routeCandidates.filter(function(row) {
            if (row.scope !== routeCandidateScope)
                return false
            if (row.scope === "SWITCH" && !row.userDefined && !showUnnamedRouteSwitches)
                return false
            return !query ||
                   String(row.tmccId).indexOf(query) >= 0 ||
                   row.name.toLowerCase().indexOf(query) >= 0 ||
                   row.roadNumber.toLowerCase().indexOf(query) >= 0
        }).sort(function(a, b) {
            if (routeCandidateSortKey === "tmccId")
                return a.tmccId - b.tmccId
            let av = routeCandidateSortKey === "roadNumber" ? a.roadNumber : a.name
            let bv = routeCandidateSortKey === "roadNumber" ? b.roadNumber : b.name
            av = String(av || "").toLowerCase()
            bv = String(bv || "").toLowerCase()
            const result = av.localeCompare(bv, undefined, { numeric: true })
            return result !== 0 ? result : a.tmccId - b.tmccId
        })
    }

    function openRoutePicker() {
        routeCandidateScope = "SWITCH"
        routeCandidateSearch = ""
        routeCandidateSortKey = "roadName"
        showUnnamedRouteSwitches = false
        routeCandidateSearchField.text = ""
        routePickerError.text = ""
        routePicker.open()
    }

    function openLcsConfiguration() {
        if (root.lcsController)
            lcsConfig.open()
    }

    function showRoster() {
        cancelTransientPanels()
        directTmccId = 0
        searchField.clear()
        roster.positionViewAtBeginning()
    }

    function discardRouteBuilder() {
        routePicker.close()
        routeBuilder.close()
        if (controller && controller.scope === "ROUTE" && controller.routeBuilderOpen)
            controller.closeRouteBuilder()
    }

    function cancelTransientPanels() {
        tmccKeypad.close()
        discardRouteBuilder()
        addSwitchPopup.close()
        overwriteSwitchPopup.close()
        switchEditor.close()
        lcsConfig.close()
    }

    function submitAddSwitch(overwrite) {
        const tmccId = Number(addSwitchId.text)
        const identity = controller.switchIdentity(tmccId)
        if (identity.exists && !identity.asc2Switch && !overwrite) {
            completeExistingSwitchIdentity()
            pendingOverwriteSwitchId = tmccId
            overwriteSwitchPopup.open()
            return
        }
        const error = controller.addSwitch(tmccId,
                                           addRoadName.text,
                                           addRoadNumber.text,
                                           commandControlSwitch.checked,
                                           overwrite)
        if (error.length > 0)
            addError.text = error
        else {
            overwriteSwitchPopup.close()
            addSwitchPopup.close()
        }
    }

    component TouchButton: CabButton {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0
        Layout.preferredHeight: pageAllStop.height
        font.pixelSize: 20
    }

    component IconActionButton: CabButton {
        id: actionButton
        required property string symbol
        property bool rightHand: false
        property int iconSpacing: 8
        property int turnoutIconWidth: 23
        readonly property bool turnout: symbol === "thru" || symbol === "out"

        Accessible.role: Accessible.Button
        Accessible.name: text
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0

        contentItem: Item {
            RowLayout {
                anchors.centerIn: parent
                width: Math.min(implicitWidth, parent.width)
                spacing: actionButton.iconSpacing

                TurnoutDiagram {
                    visible: actionButton.turnout
                    compact: true
                    rightHand: actionButton.rightHand
                    diverging: actionButton.symbol === "out"
                    opacity: actionButton.enabled ? 1 : 0.55
                    Layout.preferredWidth: actionButton.turnoutIconWidth
                    Layout.preferredHeight: 34
                }

                Canvas {
                    visible: !actionButton.turnout
                    Accessible.ignored: true
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                    readonly property color ink: actionButton.enabled ? "#ffffff" : "#7d8591"
                    onInkChanged: requestPaint()
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = ink
                        ctx.lineWidth = 1.6
                        ctx.lineCap = "round"
                        ctx.lineJoin = "round"

                        const movesLeft = actionButton.symbol === "left"
                        const movesRight = actionButton.symbol === "right"
                        const moves = movesLeft || movesRight
                        ctx.strokeRect(movesLeft ? 13 : movesRight ? 2 : 5, moves ? 6 : 2,
                                       moves ? 8 : 14, moves ? 12 : 20)
                        ctx.beginPath()
                        if (moves) {
                            const tip = movesLeft ? 2 : 22
                            const head = movesLeft ? 6 : 18
                            ctx.moveTo(movesLeft ? 10 : 14, 12)
                            ctx.lineTo(tip, 12)
                            ctx.moveTo(head, 8)
                            ctx.lineTo(tip, 12)
                            ctx.lineTo(head, 16)
                        } else {
                            ctx.moveTo(8, 12)
                            ctx.lineTo(16, 12)
                            if (actionButton.symbol === "add") {
                                ctx.moveTo(12, 8)
                                ctx.lineTo(12, 16)
                            }
                        }
                        ctx.stroke()
                    }
                }

                Label {
                    Layout.minimumWidth: 0
                    Layout.fillWidth: true
                    text: actionButton.text
                    font: actionButton.font
                    color: actionButton.enabled ? "#ffffff" : "#7d8591"
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignHCenter
                    Accessible.ignored: true
                }
            }
        }
    }

    component RosterActionButton: CabButton {
        activateOnRelease: true
        Layout.preferredWidth: 88
        Layout.minimumHeight: 60
        Layout.maximumHeight: 60
        font.pixelSize: 22
    }

    component RosterTurnoutButton: IconActionButton {
        activateOnRelease: true
        Layout.fillWidth: false
        Layout.preferredWidth: 88
        Layout.minimumHeight: 60
        Layout.maximumHeight: 60
        leftPadding: 4
        rightPadding: 4
        iconSpacing: 4
        turnoutIconWidth: 20
        font.pixelSize: 20
    }

    ColumnLayout {
        id: pageLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            RowLayout {
                Layout.fillWidth: false
                Layout.preferredWidth: pageAllStop.width
                spacing: 6
                TouchButton {
                    text: "Add…"
                    font.pixelSize: switchLcsButton.visible ? 20 : 24
                    enabled: !!controller && !(lcsConfig.visible || routeBuilder.visible || routePicker.visible)
                    onClicked: {
                        if (controller.scope === "SWITCH")
                            root.openAddSwitch()
                        else
                            root.openAddRoute()
                    }
                }
                TouchButton {
                    id: switchLcsButton
                    visible: !!controller && controller.scope === "SWITCH" && !!root.lcsController
                    text: "LCS…"
                    enabled: !(lcsConfig.visible || routeBuilder.visible || routePicker.visible)
                    onClicked: lcsConfig.open()
                }
            }
            CabMenuTitle {
                rosterTitle: true
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                compact: root.height < 850
                title: controller && controller.scope === "SWITCH" ? "Switches" : "Routes"
                onActivated: root.cabMenuRequested()
            }
            AllStopButton { id: pageAllStop; compact: root.height < 850; onClicked: controller.halt() }
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
                onTextEdited: root.directTmccId = 0
                onAccepted: if (/^[0-9]+$/.test(text) && Number(text) > 0 && Number(text) <= 98) root.submitTmccId(true)
            }
            RosterBackspaceButton { field: searchField }
            KeypadButton {
                Layout.preferredWidth: 84
                Layout.preferredHeight: 84
                onClicked: root.openTmccKeypad()
            }
            RosterSetButton {
                visible: !!controller && controller.scope === "SWITCH"
                addressAllowed: root.canSetSwitchAddress(entryText)
                entryText: searchField.text
                maximumId: 98
                onClicked: root.submitTmccId(true)
            }
        }
        RosterSortBar {
            roster: roster
            compact: root.height < 850
            selectedKey: root.sortKey
            onSelected: key => root.sortKey = key
        }
        CheckBox {
            visible: controller && controller.scope === "SWITCH"
            Layout.preferredHeight: 54
            Layout.minimumHeight: 54
            text: "Show Unnamed"
            font.pixelSize: 22
            checked: root.showInactiveSwitches
            onToggled: root.showInactiveSwitches = checked
        }
        RosterFilterTabs {
            objectName: "routeFilterTabs"
            visible: !!controller && controller.scope === "ROUTE"
            selectedKey: root.routeStateFilter
            model: [{ key: "ALL", label: "All" }, { key: "Aligned", label: "Aligned" }, { key: "Unset", label: "Unset" }]
            onSelected: key => root.routeStateFilter = key
        }
        ListView {
            id: roster
            objectName: "operationsRoster"
            enabled: !(routeBuilder.visible || routePicker.visible || switchEditor.visible ||
                       addSwitchPopup.visible || overwriteSwitchPopup.visible || lcsConfig.visible)
            opacity: enabled ? 1 : 0.42
            Layout.leftMargin: -6
            Layout.rightMargin: Layout.leftMargin
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            clip: true
            spacing: 10
            model: rosterModel
            ScrollBar.vertical: ListScrollBar { id: rosterScrollBar }

            delegate: Rectangle {
                id: row
                required property var rowData
                readonly property bool isRoute: root.controller.scope === "ROUTE"
                width: roster.width - rosterScrollBar.gutterWidth
                height: 76
                radius: 8
                color: "#23303d"
                border.width: 1
                border.color: "#444c57"
                ControlTapHandler {
                    enabled: roster.enabled && !roster.moving
                    acceptsTap: position => !rowActions.contains(rowActions.mapFromItem(row, position))
                    onTappedTwice: {
                        if (row.isRoute)
                            root.controller.fireRoute(row.rowData.tmccId)
                        else
                            root.controller.toggleSwitch(row.rowData.tmccId)
                    }
                }
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: row.isRoute ? 5 : 8

                    Label {
                        Layout.preferredWidth: 42
                        text: rowData.tmccId
                        color: "#f4f6f8"
                        font.pixelSize: 26
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 2

                        MarqueeLabel {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: rowData.roadName || (row.isRoute ? "Route" : "Switch")
                            color: "#f4f6f8"
                            font.pixelSize: 22
                            font.bold: true
                        }
                        Label {
                            visible: !row.isRoute && !!rowData.lcsAssociations
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: rowData.lcsAssociations
                            color: "#aeb5bf"
                            font.pixelSize: 14
                            elide: Text.ElideRight
                        }
                    }
                    Label {
                        id: roadNumberLabel
                        visible: row.isRoute || !!rowData.roadNumber
                        Layout.preferredWidth: row.isRoute ? Math.ceil(roadNumberMetrics.advanceWidth) : implicitWidth
                        text: rowData.roadNumber ? "#" + rowData.roadNumber : ""
                        color: "#aeb5bf"
                        font.pixelSize: 17
                        font.features: row.isRoute ? ({ "tnum": 1 }) : ({})
                        horizontalAlignment: Text.AlignRight

                        TextMetrics {
                            id: roadNumberMetrics
                            font: roadNumberLabel.font
                            text: "#0000"
                        }
                    }
                    Label {
                        id: alignmentLabel
                        visible: row.isRoute
                        Layout.preferredWidth: Math.ceil(Math.max(alignedMetrics.advanceWidth, unsetMetrics.advanceWidth))
                                               + leftPadding + rightPadding
                        leftPadding: 6
                        rightPadding: leftPadding
                        TextMetrics {
                            id: alignedMetrics
                            font: alignmentLabel.font
                            text: "Aligned"
                        }
                        TextMetrics {
                            id: unsetMetrics
                            font: alignmentLabel.font
                            text: "Unset"
                        }
                        text: rowData.stateText === "UNKNOWN" ? "" : rowData.stateText
                        color: rowData.stateText === "Aligned" ? "#73d38a" :
                               "#ffffff"
                        font.pixelSize: 16
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    RowLayout {
                        id: rowActions
                        spacing: 6
                        RosterTurnoutButton {
                            visible: !row.isRoute
                            symbol: "thru"
                            rightHand: !!root.rightHandSwitches[row.rowData.tmccId]
                            text: "Thru"
                            selected: row.rowData.stateText === "THRU"
                            onClicked: controller.operateSwitch(row.rowData.tmccId, "THRU")
                        }
                        RosterTurnoutButton {
                            visible: !row.isRoute
                            symbol: "out"
                            rightHand: !!root.rightHandSwitches[row.rowData.tmccId]
                            text: "Out"
                            selected: row.rowData.stateText === "OUT"
                            distinguishDoubleClick: true
                            onDoubleClicked: root.toggleSwitchHandedness(row.rowData.tmccId)
                            onGestureHeld: root.toggleSwitchHandedness(row.rowData.tmccId)
                            onClicked: controller.operateSwitch(row.rowData.tmccId, "OUT")
                        }
                        RosterActionButton {
                            visible: row.isRoute
                            text: "Fire"
                            normalColor: "#a84418"
                            pressedColor: "#d65a20"
                            onClicked: controller.fireRoute(row.rowData.tmccId)
                        }
                        RosterActionButton {
                            text: "Edit…"
                            onClicked: {
                                if (row.isRoute) root.editRoute(row.rowData.tmccId)
                                else root.editSwitch(row.rowData.tmccId)
                            }
                        }
                    }
                }
            }
        }
    }

    TmccKeypad {
        id: tmccKeypad
        title: (controller && controller.scope === "SWITCH" ? "Switch" : "Route") + " TMCC ID"
        showSetAddress: !!controller && controller.scope === "SWITCH"
        setAddressAllowed: root.canSetSwitchAddress(entryText)
        onSetAddressRequested: function(tmccId) {
            const error = controller.programSwitchAddress(tmccId)
            if (error)
                errorText = error
            else
                close()
        }
        onSubmitted: root.submitTmccId()
    }

    Popup {
        id: routeBuilder
        objectName: "routeBuilder"
        readonly property bool compact: height < 920
        readonly property int minimumButtonHeight: compact ? 40 : 58
        readonly property int footerHeight: compact ? 52 : 72
        readonly property int fieldHeight: compact ? 42 : 58

        function toggleOutHandedness() {
            const index = controller.routeComponentIndex
            if (controller.routeComponents[index].position !== "OUT")
                controller.setRouteComponentPosition("OUT")
            controller.toggleRouteComponentDirection(index)
        }
        x: Math.max(0, (root.width - width) / 2)
        y: root.editorTop
        width: Math.min(root.width - 16, 720)
        height: Math.max(0, root.height - y - 8)
        padding: compact ? 12 : 18
        modal: false
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: "#102858"
            radius: 14
            border.width: 1
            border.color: "#59616c"
        }

        contentItem: ColumnLayout {
            spacing: routeBuilder.compact ? 5 : 9

            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: "Route Builder"
                    color: "#f4f6f8"
                    font.pixelSize: routeBuilder.compact ? 24 : 29
                    font.bold: true
                }
                Label {
                    text: (controller ? controller.routeComponents.length : 0) + " of 16 Elements"
                    color: "#aeb5bf"
                    font.pixelSize: 17
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: routeBuilder.compact ? 3 : 1
                columnSpacing: 12
                rowSpacing: routeBuilder.compact ? 6 : 9
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: 4
                    Label {
                        text: "TMCC ID (1-98)"
                        font.pixelSize: routeBuilder.compact ? 16 : 23
                        color: "#aeb5bf"
                    }
                    IdentityNumberField {
                        id: routeIdField
                        keypadTitle: "Route TMCC ID"
                        address: true
                        validator: IntValidator { bottom: 1; top: 98 }
                        Layout.fillWidth: true
                        Layout.preferredHeight: routeBuilder.fieldHeight
                        font.pixelSize: routeBuilder.compact ? 20 : 28
                        onEditingFinished: if (Qt.platform.os !== "linux") root.routeIdEditingFinished()
                        onKeypadAccepted: root.routeIdEditingFinished()
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 2
                    spacing: 4
                    Label {
                        text: "Route Name"
                        font.pixelSize: routeBuilder.compact ? 16 : 23
                        color: "#aeb5bf"
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        TouchSearchField {
                            id: routeNameField
                            titleCaseEnabled: true
                            Layout.minimumWidth: 0
                            keyboardTitle: "Route Name"
                            Layout.fillWidth: true
                            Layout.preferredHeight: routeBuilder.fieldHeight
                            maximumLength: 31
                            font.pixelSize: routeBuilder.compact ? 20 : 28
                        }
                        TitleCaseButton {
                            field: routeNameField
                            Layout.preferredHeight: routeNameField.Layout.preferredHeight
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: 4
                    Label {
                        text: "Route Number"
                        font.pixelSize: routeBuilder.compact ? 16 : 23
                        color: "#aeb5bf"
                    }
                    IdentityNumberField {
                        id: routeNumberField
                        keypadTitle: "Route Number"
                        Layout.fillWidth: true
                        Layout.preferredHeight: routeBuilder.fieldHeight
                        font.pixelSize: routeBuilder.compact ? 20 : 28
                    }
                }
            }

            Label {
                Layout.fillWidth: true
                text: controller && controller.routeComponents.length ?
                          "Select an element to edit or reorder. Double-tap or touch/hold Out to flip turnout left or right." :
                          "No elements yet. Add a switch or nested route."
                color: "#aeb5bf"
                font.pixelSize: routeBuilder.compact ? 14 : 18
                wrapMode: Text.WordWrap
            }

            ListView {
                id: routeComponentList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: routeBuilder.compact ? 140 : 172
                Layout.preferredHeight: routeBuilder.compact ? 146 : 182
                Layout.maximumHeight: 300
                orientation: ListView.Horizontal
                spacing: 8
                clip: true
                model: controller ? controller.routeComponents : []

                delegate: Rectangle {
                    id: routeElement
                    required property var modelData

                    function flipOutTurnout() {
                        if (modelData.scope === "SWITCH" && modelData.position === "OUT")
                            controller.toggleRouteComponentDirection(modelData.index)
                        else
                            controller.selectRouteComponent(modelData.index)
                    }

                    width: modelData.scope === "SWITCH" ? 132 : 180
                    height: routeComponentList.height - 4
                    radius: 8
                    color: controller && controller.routeComponentIndex === modelData.index ? "#164f70" : "#262b32"
                    border.width: controller && controller.routeComponentIndex === modelData.index ? 2 : 1
                    border.color: controller && controller.routeComponentIndex === modelData.index ? "#55c7ff" : "#444c57"

                    ControlTapHandler {
                        holdEnabled: !!point.device && point.device.type === PointerDevice.TouchScreen
                        onTappedOnce: controller.selectRouteComponent(modelData.index)
                        onTappedTwice: routeElement.flipOutTurnout()
                        onHeldGesture: routeElement.flipOutTurnout()
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: routeBuilder.compact ? 6 : 10
                        spacing: routeBuilder.compact ? 2 : 5
                        Label {
                            Layout.fillWidth: true
                            text: "Element " + (modelData.index + 1)
                            color: "#aeb5bf"
                            font.pixelSize: routeBuilder.compact ? 11 : 14
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.name
                            color: "#f4f6f8"
                            font.pixelSize: routeBuilder.compact ? 15 : 19
                            font.bold: true
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.scope === "ROUTE" ? "Route " + modelData.tmccId :
                                                               "Switch " + modelData.tmccId
                            color: "#aeb5bf"
                            font.pixelSize: routeBuilder.compact ? 13 : 16
                        }
                        TurnoutDiagram {
                            objectName: "routeSwitchDiagram"
                            visible: modelData.scope === "SWITCH"
                            diverging: modelData.position === "OUT"
                            rightHand: modelData.turnoutDirection === "RIGHT"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: visible ? 32 : 0
                            Layout.maximumHeight: 156
                        }
                        Item {
                            visible: modelData.scope !== "SWITCH"
                            Layout.fillHeight: true
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.turnoutDirection ? "OUT " + modelData.turnoutDirection : modelData.position
                            color: modelData.position === "THRU" ? "#73d38a" :
                                   modelData.position === "OUT" ? "#f0a35a" : "#55c7ff"
                            font.pixelSize: routeBuilder.compact ? 15 : 19
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                IconActionButton {
                    Layout.preferredHeight: routeBuilder.compact ? 42 : 62
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    symbol: "thru"
                    text: "Thru"
                    rightHand: enabled &&
                               controller.routeComponents[controller.routeComponentIndex].turnoutDirection === "RIGHT"
                    enabled: controller && controller.routeComponentIndex >= 0 &&
                             controller.routeComponents[controller.routeComponentIndex].scope === "SWITCH"
                    selected: enabled &&
                              controller.routeComponents[controller.routeComponentIndex].position === "THRU"
                    onClicked: controller.setRouteComponentPosition("THRU")
                }
                IconActionButton {
                    Layout.preferredHeight: routeBuilder.compact ? 42 : 62
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    symbol: "out"
                    text: "Out"
                    rightHand: enabled &&
                               controller.routeComponents[controller.routeComponentIndex].turnoutDirection === "RIGHT"
                    enabled: controller && controller.routeComponentIndex >= 0 &&
                             controller.routeComponents[controller.routeComponentIndex].scope === "SWITCH"
                    selected: enabled &&
                              controller.routeComponents[controller.routeComponentIndex].position === "OUT"
                    distinguishDoubleClick: true
                    holdWithinBounds: true
                    mouseHoldEnabled: Qt.platform.os === "osx"
                    onDoubleClicked: routeBuilder.toggleOutHandedness()
                    onGestureHeld: routeBuilder.toggleOutHandedness()
                    onClicked: controller.setRouteComponentPosition("OUT")
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                IconActionButton {
                    Layout.preferredHeight: routeBuilder.compact ? 42 : 62
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    symbol: "left"
                    text: "Move Left"
                    enabled: controller && controller.routeComponentIndex > 0
                    onClicked: controller.moveRouteComponent(-1)
                }
                IconActionButton {
                    Layout.preferredHeight: routeBuilder.compact ? 42 : 62
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    symbol: "right"
                    text: "Move Right"
                    enabled: controller && controller.routeComponentIndex >= 0 &&
                             controller.routeComponentIndex < controller.routeComponents.length - 1
                    onClicked: controller.moveRouteComponent(1)
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                IconActionButton {
                    Layout.preferredHeight: routeBuilder.compact ? 42 : 62
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    symbol: "add"
                    text: "Add…"
                    enabled: controller && controller.routeComponents.length < 16
                    onClicked: root.openRoutePicker()
                }
                IconActionButton {
                    Layout.preferredHeight: routeBuilder.compact ? 42 : 62
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    symbol: "remove"
                    text: "Remove"
                    enabled: controller && controller.routeComponentIndex >= 0
                    onClicked: controller.removeRouteComponent()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: routeBuilder.compact ? 42 : 62
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    text: "Clear All"
                    enabled: controller && controller.routeComponents.length > 0
                    onClicked: controller.clearRouteComponents()
                }
            }

            Label {
                id: routeBuilderError
                Layout.fillWidth: true
                visible: text.length > 0
                color: "#ff7777"
                font.pixelSize: routeBuilder.compact ? 13 : 16
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: metrics.footerOffset(implicitHeight, parent.spacing)
                spacing: 14
                ClearRecordButton {
                    Layout.preferredHeight: routeBuilder.footerHeight
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    enabled: {
                        root.rosterRows
                        const id = controller.routeBuilderId
                        return id === Number(routeIdField.text) && controller.canClearRecord(id)
                    }
                    onActivated: {
                        const error = controller.clearRecord(controller.routeBuilderId)
                        if (error)
                            routeBuilderError.text = error
                        else
                            routeBuilder.close()
                    }
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: routeBuilder.footerHeight
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    text: "Cancel"
                    font.pixelSize: metrics.editorButtonFontSize
                    onClicked: root.routeCloseRequested()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: routeBuilder.footerHeight
                    Layout.minimumHeight: routeBuilder.minimumButtonHeight
                    activateOnRelease: true
                    text: "Save"
                    font.pixelSize: metrics.editorButtonFontSize
                    font.bold: true
                    enabled: controller && controller.routeBuilderOpen &&
                             Number(routeIdField.text) >= 1 && Number(routeIdField.text) <= 98
                    onClicked: {
                        if (controller.routeBuilderId !== Number(routeIdField.text)) {
                            const idError = controller.assignRouteBuilderId(Number(routeIdField.text))
                            if (idError.length > 0) {
                                routeBuilderError.text = idError
                                return
                            }
                        }
                        const error = controller.saveRouteBuilder(routeNameField.text, routeNumberField.text)
                        if (error.length > 0)
                            routeBuilderError.text = error
                        else
                            routeBuilder.close()
                    }
                }
            }
        }
    }

    Popup {
        id: routePicker
        objectName: "routePicker"
        x: Math.max(0, (root.width - width) / 2)
        y: root.editorTop
        width: Math.min(root.width - 24, 640)
        height: Math.max(0, root.height - y - 8)
        modal: false
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: "#102858"
            radius: 14
            border.width: 1
            border.color: "#59616c"
        }

        contentItem: ColumnLayout {
            spacing: 10
            Label {
                Layout.fillWidth: true
                text: "Add to Route"
                color: "#f4f6f8"
                font.pixelSize: 22
                font.bold: true
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 42
                    text: "Switches"
                    selected: root.routeCandidateScope === "SWITCH"
                    onClicked: root.routeCandidateScope = "SWITCH"
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 42
                    text: "Routes"
                    selected: root.routeCandidateScope === "ROUTE"
                    onClicked: root.routeCandidateScope = "ROUTE"
                }
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
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: 38
                        text: modelData.label
                        selected: root.routeCandidateSortKey === modelData.key
                        onClicked: root.routeCandidateSortKey = modelData.key
                    }
                }
                CabButton {
                    visible: root.routeCandidateScope === "SWITCH"
                    Layout.preferredWidth: 180
                    Layout.preferredHeight: 38
                    text: root.showUnnamedRouteSwitches ? "Hide Unnamed" : "Show Unnamed"
                    selected: true
                    onClicked: root.showUnnamedRouteSwitches = !root.showUnnamedRouteSwitches
                }
            }
            TouchSearchField {
                id: routeCandidateSearchField
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                placeholderText: "Search name, road number, or TMCC ID"
                font.pixelSize: 14
                onTextChanged: root.routeCandidateSearch = text
            }
            ListView {
                id: routeCandidateList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 0
                Layout.preferredHeight: contentHeight
                Layout.maximumHeight: contentHeight
                clip: true
                spacing: 5
                model: root.routeCandidateRows()

                delegate: Rectangle {
                    required property var modelData
                    width: routeCandidateList.width
                    height: 62
                    radius: 8
                    color: "#262b32"
                    border.width: 1
                    border.color: "#444c57"

                    ControlTapHandler {
                        onTappedTwice: {
                            const error = controller.addRouteComponent(modelData.scope, modelData.tmccId)
                            if (error.length > 0)
                                routePickerError.text = error
                            else
                                routePicker.close()
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        Label {
                            Layout.preferredWidth: 42
                            text: modelData.tmccId
                            color: "#f4f6f8"
                            font.pixelSize: 18
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            MarqueeLabel {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                text: modelData.name
                                color: "#f4f6f8"
                                font.pixelSize: 15
                                font.bold: true
                            }
                            Label {
                                Layout.fillWidth: true
                                text: modelData.scope === "ROUTE" ? "Route" :
                                      (modelData.roadNumber ? "Switch · Road #" + modelData.roadNumber : "Switch")
                                color: "#aeb5bf"
                                font.pixelSize: 12
                            }
                        }
                        CabButton {
                            Layout.preferredWidth: 74
                            Layout.preferredHeight: 42
                            text: "Add"
                            onClicked: {
                                const error = controller.addRouteComponent(modelData.scope, modelData.tmccId)
                                if (error.length > 0)
                                    routePickerError.text = error
                                else
                                    routePicker.close()
                            }
                        }
                    }
                }
            }
            Label {
                id: routePickerError
                Layout.fillWidth: true
                visible: text.length > 0
                color: "#ff7777"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            CabButton {
                Layout.topMargin: metrics.footerOffset(Layout.preferredHeight, parent.spacing)
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                text: "Cancel"
                onClicked: routePicker.close()
            }
            Item {
                Layout.fillHeight: true
                Layout.preferredHeight: 0
            }
        }
    }

    Popup {
        id: addSwitchPopup
        x: Math.max(0, (Overlay.overlay.width - width) / 2)
        y: Math.max(76, (Overlay.overlay.height - height) / 2)
        width: Math.min(root.width - 40, 620)
        modal: false
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: "#102858"
            radius: 14
            border.width: 1
            border.color: "#59616c"
        }

        contentItem: ColumnLayout {
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: "Add Switch"
                color: "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                CheckBox {
                    id: commandControlSwitch
                    enabled: !root.addingAsc2Switch
                    checked: enabled && root.addCommandControl
                    Accessible.name: "Lionel Command Control Switch"
                    onToggled: root.addCommandControl = checked
                }
                Label {
                    Layout.fillWidth: true
                    text: "Lionel Command Control Switch"
                    color: "#f4f6f8"
                    font.pixelSize: 16
                    font.bold: true

                    opacity: commandControlSwitch.enabled ? 1 : 0.5
                    TapHandler {
                        enabled: commandControlSwitch.enabled
                        onTapped: root.addCommandControl = !root.addCommandControl
                    }
                }
            }
            Label {
                Layout.fillWidth: true
                visible: commandControlSwitch.checked
                text: "Put the Command Control switch into PROGRAM mode before pressing Add Switch."
                color: "#f0c36a"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            Label {
                text: "TMCC ID (1-98)"
                color: "#aeb5bf"
            }
            IdentityNumberField {
                id: addSwitchId
                keypadTitle: "Switch TMCC ID"
                address: true
                validator: IntValidator { bottom: 1; top: 98 }
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                font.pixelSize: 18
                onEditingFinished: if (Qt.platform.os !== "linux") root.completeExistingSwitchIdentity()
                onKeypadAccepted: root.completeExistingSwitchIdentity()
            }
            Label {
                text: "Road Name"
                color: "#aeb5bf"
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TouchSearchField {
                    id: addRoadName
                    titleCaseEnabled: true
                    Layout.minimumWidth: 0
                    keyboardTitle: "Road Name"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    maximumLength: 31
                    font.pixelSize: 18
                }
                TitleCaseButton {
                    field: addRoadName
                    Layout.preferredHeight: addRoadName.Layout.preferredHeight
                }
            }
            Label {
                text: "Road Number"
                color: "#aeb5bf"
            }
            IdentityNumberField {
                id: addRoadNumber
                keypadTitle: "Road Number"
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                font.pixelSize: 18
            }
            Label {
                id: addError
                Layout.fillWidth: true
                visible: text.length > 0
                color: "#ff7777"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.topMargin: metrics.footerOffset(implicitHeight, parent.spacing)
                Layout.fillWidth: true
                spacing: 10
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "Cancel"
                    font.pixelSize: metrics.editorButtonFontSize
                    onClicked: addSwitchPopup.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: root.addingAsc2Switch ? "Save" : "Add Switch"
                    font.pixelSize: metrics.editorButtonFontSize
                    font.bold: true
                    activateOnRelease: true
                    enabled: addSwitchId.acceptableInput && (root.addingAsc2Switch
                             ? (addRoadNumber.text.trim().length === 0 || addRoadNumber.acceptableInput) &&
                               (addRoadName.text.trim() !== root.addSwitchIdentity.roadName ||
                                addRoadNumber.text.trim() !== root.addSwitchIdentity.roadNumber)
                             : addRoadName.text.trim().length > 0 &&
                               addRoadNumber.acceptableInput && addRoadNumber.text.trim().length > 0)
                    onClicked: root.submitAddSwitch(false)
                }
            }
        }
    }

    Popup {
        id: overwriteSwitchPopup
        x: Math.max(0, (Overlay.overlay.width - width) / 2)
        y: Math.max(76, (Overlay.overlay.height - height) / 2)
        width: Math.min(root.width - 70, 560)
        modal: false
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: "#102858"
            radius: 14
            border.width: 1
            border.color: "#59616c"
        }

        contentItem: ColumnLayout {
            spacing: 14

            Label {
                Layout.fillWidth: true
                text: "Replace Switch " + root.pendingOverwriteSwitchId + "?"
                color: "#f4f6f8"
                font.pixelSize: 22
                font.bold: true
            }
            Label {
                Layout.fillWidth: true
                text: "A switch with this TMCC ID already exists. Continue and overwrite its configuration?"
                color: "#c8ced6"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.topMargin: metrics.footerOffset(implicitHeight, parent.spacing)
                Layout.fillWidth: true
                spacing: 10
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "Cancel"
                    font.pixelSize: metrics.editorButtonFontSize
                    onClicked: overwriteSwitchPopup.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "Replace Switch"
                    font.bold: true
                    onClicked: root.submitAddSwitch(true)
                }
            }
        }
    }

    Popup {
        id: switchEditor
        x: Math.max(0, (Overlay.overlay.width - width) / 2)
        y: Math.max(76, (Overlay.overlay.height - height) / 2)
        width: Math.min(root.width - 16, 540)
        modal: false
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: "#102858"
            radius: 14
            border.width: 1
            border.color: "#59616c"
        }

        contentItem: ColumnLayout {
            spacing: 14

            Label {
                Layout.fillWidth: true
                text: "Edit Switch " + root.editingSwitchId
                color: "#f4f6f8"
                font.pixelSize: 29
                font.bold: true
            }

            Label {
                text: "Road Name"
                color: "#aeb5bf"
                font.pixelSize: 17
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TouchSearchField {
                    id: roadNameField
                    titleCaseEnabled: true
                    Layout.minimumWidth: 0
                    keyboardTitle: "Road Name"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    font.pixelSize: 22
                    maximumLength: 31
                    selectByMouse: true
                }
                TitleCaseButton {
                    field: roadNameField
                    Layout.preferredHeight: roadNameField.Layout.preferredHeight
                }
            }

            Label {
                text: "Road Number"
                color: "#aeb5bf"
                font.pixelSize: 17
            }
            IdentityNumberField {
                id: roadNumberField
                keypadTitle: "Road Number"
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                font.pixelSize: 22
                selectByMouse: true
            }

            StateInfoGrid {
                Layout.fillWidth: true
                Layout.topMargin: metrics.sectionGap
                columns: 3
                rows: {
                    root.rosterRows
                    return switchEditor.visible ? controller.lcsBoardDetails(root.editingSwitchId) : []
                }
                visible: rows.length > 0
            }

            Label {
                id: switchEditorError
                Layout.fillWidth: true
                visible: text.length > 0
                color: "#ff7777"
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: metrics.footerOffset(implicitHeight, parent.spacing)
                spacing: 14

                ClearRecordButton {
                    Layout.preferredHeight: 63
                    enabled: {
                        root.rosterRows
                        return controller.canClearRecord(root.editingSwitchId)
                    }
                    onActivated: {
                        const error = controller.clearRecord(root.editingSwitchId)
                        if (error)
                            switchEditorError.text = error
                        else
                            switchEditor.close()
                    }
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 63
                    text: "Cancel"
                    font.pixelSize: metrics.editorButtonFontSize
                    onClicked: switchEditor.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 63
                    activateOnRelease: true
                    text: "Save"
                    font.pixelSize: metrics.editorButtonFontSize
                    font.bold: true
                    enabled: roadNameField.text !== root.editingSwitchOriginalName ||
                             roadNumberField.text !== root.editingSwitchOriginalNumber
                    onClicked: {
                        const error = controller.saveSwitchIdentity(root.editingSwitchId,
                                                                    roadNameField.text,
                                                                    roadNumberField.text)
                        if (error)
                            switchEditorError.text = error
                        else
                            switchEditor.close()
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

}
