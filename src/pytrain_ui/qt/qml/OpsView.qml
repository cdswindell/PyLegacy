import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var controller
    property var lcsController: null
    property string sortKey: "roadName"
    property int editingSwitchId: 0
    property string editingSwitchOriginalName: ""
    property string editingSwitchOriginalNumber: ""
    property int pendingOverwriteSwitchId: 0
    property string populatedSwitchName: ""
    property string populatedSwitchNumber: ""
    property bool showInactiveSwitches: false
    property string routeCandidateScope: "SWITCH"
    property string routeCandidateSearch: ""
    property string routeCandidateSortKey: "roadName"
    property bool showUnnamedRouteSwitches: false
    signal closeRequested()

    color: "#171a1f"
    radius: 14

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
            if (controller.scope === "SWITCH" && row.inactive && !root.showInactiveSwitches)
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

    function editSwitch(tmccId) {
        editingSwitchId = tmccId
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
        commandControlSwitch.checked = true
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
        if (!identity.exists) {
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
        controller.closeRouteBuilder()
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
        const text = routeIdField.text.trim()
        if (!text.length) {
            controller.closeRouteBuilder()
            routeNameField.text = ""
            routeNumberField.text = ""
            return
        }
        const tmccId = Number(text)
        if (tmccId < 1 || tmccId > 98) {
            routeBuilderError.text = "Route ID must be an integer from 1 to 98."
            return
        }
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

    function cancelTransientPanels() {
        routePicker.close()
        routeBuilder.close()
        addSwitchPopup.close()
        overwriteSwitchPopup.close()
        switchEditor.close()
        lcsConfig.close()
        if (controller && controller.scope === "ROUTE")
            controller.closeRouteBuilder()
    }

    function submitAddSwitch(overwrite) {
        const tmccId = Number(addSwitchId.text)
        const identity = controller.switchIdentity(tmccId)
        if (identity.exists && !overwrite) {
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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
                    Layout.preferredWidth: 0
            Label {
                text: controller && controller.scope === "SWITCH" ? "Switch Operations" : "Route Operations"
                color: (lcsConfig.visible || routeBuilder.visible || routePicker.visible) ? "#777d86" : "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            CabButton {
                visible: controller
                Layout.leftMargin: 16
                Layout.preferredWidth: 90
                Layout.preferredHeight: 46
                text: "ADD…"
                enabled: !(lcsConfig.visible || routeBuilder.visible || routePicker.visible)
                font.bold: true
                onClicked: {
                    if (controller.scope === "SWITCH")
                        root.openAddSwitch()
                    else
                        root.openAddRoute()
                }
            }
            CabButton {
                visible: controller && controller.scope === "SWITCH" && root.lcsController
                Layout.preferredWidth: 90
                Layout.preferredHeight: 46
                text: "LCS…"
                enabled: !(lcsConfig.visible || routeBuilder.visible || routePicker.visible)
                font.bold: true
                onClicked: lcsConfig.open()
            }
            Item {
                Layout.fillWidth: true
            }
            CabButton {
                Layout.preferredWidth: 120
                Layout.preferredHeight: 54
                text: "HALT"
                font.bold: true
                normalColor: "#9d2020"
                pressedColor: "#c62d2d"
                onClicked: controller.halt()
            }
        }

        TextField {
            id: searchField
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            placeholderText: "Search road name, road number, or TMCC ID"
            font.pixelSize: 15
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
                    Layout.preferredWidth: 145
                    Layout.preferredHeight: 38
                    text: modelData.label
                    selected: root.sortKey === modelData.key
                    onClicked: root.sortKey = modelData.key
                }
            }
            Item {
                visible: controller && controller.scope === "SWITCH"
                Layout.preferredWidth: 8
            }
            CabButton {
                visible: controller && controller.scope === "SWITCH"
                Layout.fillWidth: true
                Layout.minimumWidth: 170
                Layout.preferredHeight: 38
                text: root.showInactiveSwitches ? "HIDE UNNAMED" : "SHOW UNNAMED"
                selected: true
                onClicked: root.showInactiveSwitches = !root.showInactiveSwitches
            }
        }

        ListView {
            id: roster
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 5
            model: root.visibleRows()

            delegate: Rectangle {
                id: row
                required property var modelData
                width: roster.width
                height: 68
                radius: 8
                color: "#262b32"
                border.width: 1
                border.color: "#444c57"

                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    onDoubleTapped: {
                        if (root.controller.scope === "ROUTE")
                            root.controller.fireRoute(row.modelData.tmccId)
                        else
                            root.controller.toggleSwitch(row.modelData.tmccId)
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 6
                    Label {
                        Layout.preferredWidth: 50
                        text: modelData.tmccId
                        color: "#f4f6f8"
                        font.pixelSize: 20
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Label {
                            Layout.fillWidth: true
                            text: modelData.roadName || (controller && controller.scope === "SWITCH" ? "Switch" : "Route")
                            color: "#f4f6f8"
                            font.pixelSize: 16
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: {
                                let detail = modelData.roadNumber ? "Road # " + modelData.roadNumber :
                                                                  "TMCC ID " + modelData.tmccId
                                if (modelData.lcsAssociations)
                                    detail += " · " + modelData.lcsAssociations
                                return detail
                            }
                            color: "#aeb5bf"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                    Label {
                        Layout.preferredWidth: controller && controller.scope === "ROUTE" ? 108 : 58
                        text: modelData.stateText
                        color: modelData.stateText === "ALIGNED" || modelData.stateText === "THRU" ? "#73d38a" :
                               modelData.stateText === "UNKNOWN" ? "#aeb5bf" : "#f0a35a"
                        font.pixelSize: 12
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    CabButton {
                        visible: controller && controller.scope === "SWITCH"
                        Layout.preferredWidth: 68
                        Layout.preferredHeight: 46
                        text: "THRU"
                        selected: row.modelData.stateText === "THRU"
                        onClicked: controller.operateSwitch(row.modelData.tmccId, "THRU")
                    }
                    CabButton {
                        visible: controller && controller.scope === "SWITCH"
                        Layout.preferredWidth: 68
                        Layout.preferredHeight: 46
                        text: "OUT"
                        selected: row.modelData.stateText === "OUT"
                        onClicked: controller.operateSwitch(row.modelData.tmccId, "OUT")
                    }
                    CabButton {
                        visible: controller && controller.scope === "ROUTE"
                        Layout.preferredWidth: 96
                        Layout.preferredHeight: 46
                        text: "FIRE"
                        normalColor: "#a84418"
                        pressedColor: "#d65a20"
                        onClicked: controller.fireRoute(row.modelData.tmccId)
                    }
                    CabButton {
                        visible: controller && controller.scope === "ROUTE"
                        Layout.preferredWidth: 68
                        Layout.preferredHeight: 46
                        text: "EDIT…"
                        onClicked: root.editRoute(row.modelData.tmccId)
                    }
                    CabButton {
                        visible: controller && controller.scope === "SWITCH"
                        Layout.preferredWidth: 58
                        Layout.preferredHeight: 46
                        text: "EDIT…"
                        onClicked: root.editSwitch(row.modelData.tmccId)
                    }
                }
            }
        }
    }

    Popup {
        id: routeBuilder
        x: Math.max(0, (Overlay.overlay.width - width) / 2)
        y: Math.max(76, (Overlay.overlay.height - height) / 2)
        width: Math.min(root.width - 24, 690)
        height: Math.min(root.height - 64, 1160)
        modal: false
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: "#171a1f"
            radius: 14
            border.width: 1
            border.color: "#59616c"
        }

        contentItem: ColumnLayout {
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: "Route Builder"
                    color: "#f4f6f8"
                    font.pixelSize: 24
                    font.bold: true
                }
                Label {
                    text: (controller ? controller.routeComponents.length : 0) + " of 16"
                    color: "#aeb5bf"
                    font.pixelSize: 14
                }
            }

            Label {
                text: "TMCC ID (1-98)"
                color: "#aeb5bf"
            }
            TextField {
                id: routeIdField
                Layout.fillWidth: true
                Layout.preferredHeight: 46
                maximumLength: 2
                inputMethodHints: Qt.ImhDigitsOnly
                validator: IntValidator { bottom: 1; top: 98 }
                font.pixelSize: 17
                onEditingFinished: root.routeIdEditingFinished()
            }

            Label {
                text: "Route Name"
                color: "#aeb5bf"
            }
            TextField {
                id: routeNameField
                Layout.fillWidth: true
                Layout.preferredHeight: 46
                maximumLength: 31
                font.pixelSize: 17
            }

            Label {
                text: "Route Number"
                color: "#aeb5bf"
            }
            TextField {
                id: routeNumberField
                Layout.fillWidth: true
                Layout.preferredHeight: 46
                maximumLength: 4
                inputMethodHints: Qt.ImhDigitsOnly
                validator: RegularExpressionValidator {
                    regularExpression: /[0-9]{0,4}/
                }
                font.pixelSize: 17
            }

            Label {
                Layout.fillWidth: true
                text: controller && controller.routeComponents.length ?
                          "Select a card to change its position, order, or remove it." :
                          "No components yet. Add a switch or nested route."
                color: "#aeb5bf"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }

            ListView {
                id: routeComponentList
                Layout.fillWidth: true
                Layout.preferredHeight: 300
                orientation: ListView.Horizontal
                spacing: 8
                clip: true
                model: controller ? controller.routeComponents : []

                delegate: Rectangle {
                    required property var modelData
                    width: 180
                    height: routeComponentList.height - 4
                    radius: 8
                    color: controller && controller.routeComponentIndex === modelData.index ? "#164f70" : "#262b32"
                    border.width: controller && controller.routeComponentIndex === modelData.index ? 2 : 1
                    border.color: controller && controller.routeComponentIndex === modelData.index ? "#55c7ff" : "#444c57"

                    TapHandler {
                        onTapped: controller.selectRouteComponent(modelData.index)
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 5
                        Label {
                            Layout.fillWidth: true
                            text: "Card " + (modelData.index + 1)
                            color: "#aeb5bf"
                            font.pixelSize: 12
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.name
                            color: "#f4f6f8"
                            font.pixelSize: 16
                            font.bold: true
                            wrapMode: Text.WordWrap
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.scope === "ROUTE" ? "Route " + modelData.tmccId :
                                                               "Switch " + modelData.tmccId
                            color: "#aeb5bf"
                            font.pixelSize: 13
                        }
                        Item {
                            Layout.fillHeight: true
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.position
                            color: modelData.position === "THRU" ? "#73d38a" :
                                   modelData.position === "OUT" ? "#f0a35a" : "#55c7ff"
                            font.pixelSize: 16
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 46
                    text: "THRU"
                    enabled: controller && controller.routeComponentIndex >= 0 &&
                             controller.routeComponents[controller.routeComponentIndex].scope === "SWITCH"
                    selected: enabled &&
                              controller.routeComponents[controller.routeComponentIndex].position === "THRU"
                    onClicked: controller.setRouteComponentPosition("THRU")
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 46
                    text: "OUT"
                    enabled: controller && controller.routeComponentIndex >= 0 &&
                             controller.routeComponents[controller.routeComponentIndex].scope === "SWITCH"
                    selected: enabled &&
                              controller.routeComponents[controller.routeComponentIndex].position === "OUT"
                    onClicked: controller.setRouteComponentPosition("OUT")
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 46
                    text: "MOVE LEFT"
                    enabled: controller && controller.routeComponentIndex > 0
                    onClicked: controller.moveRouteComponent(-1)
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 46
                    text: "MOVE RIGHT"
                    enabled: controller && controller.routeComponentIndex >= 0 &&
                             controller.routeComponentIndex < controller.routeComponents.length - 1
                    onClicked: controller.moveRouteComponent(1)
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 46
                    text: "ADD…"
                    enabled: controller && controller.routeComponents.length < 16
                    onClicked: root.openRoutePicker()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 46
                    text: "REMOVE"
                    enabled: controller && controller.routeComponentIndex >= 0
                    onClicked: controller.removeRouteComponent()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 46
                    text: "CLEAR ALL"
                    enabled: controller && controller.routeComponents.length > 0
                    onClicked: controller.clearRouteComponents()
                }
            }

            Label {
                id: routeBuilderError
                Layout.fillWidth: true
                visible: text.length > 0
                color: "#ff7777"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }

            Item {
                Layout.fillHeight: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "CANCEL"
                    onClicked: {
                        controller.closeRouteBuilder()
                        routeBuilder.close()
                    }
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "SAVE ROUTE"
                    font.bold: true
                    enabled: controller && controller.routeBuilderOpen
                    onClicked: {
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
        x: Math.max(0, (Overlay.overlay.width - width) / 2)
        y: Math.max(76, (Overlay.overlay.height - height) / 2)
        width: Math.min(root.width - 50, 640)
        height: Math.min(root.height - 100, 940)
        modal: false
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: "#20242a"
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
                    text: "SWITCHES"
                    selected: root.routeCandidateScope === "SWITCH"
                    onClicked: root.routeCandidateScope = "SWITCH"
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 42
                    text: "ROUTES"
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
                    text: root.showUnnamedRouteSwitches ? "HIDE UNNAMED" : "SHOW UNNAMED"
                    selected: true
                    onClicked: root.showUnnamedRouteSwitches = !root.showUnnamedRouteSwitches
                }
            }
            TextField {
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

                    TapHandler {
                        onDoubleTapped: {
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
                            Label {
                                Layout.fillWidth: true
                                text: modelData.name
                                color: "#f4f6f8"
                                font.pixelSize: 15
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Label {
                                Layout.fillWidth: true
                                text: modelData.scope === "ROUTE" ? "Route" :
                                      (modelData.roadNumber ? "Switch · Road # " + modelData.roadNumber : "Switch")
                                color: "#aeb5bf"
                                font.pixelSize: 12
                            }
                        }
                        CabButton {
                            Layout.preferredWidth: 74
                            Layout.preferredHeight: 42
                            text: "ADD"
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
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                text: "CANCEL"
                onClicked: routePicker.close()
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
            color: "#20242a"
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
                    checked: true
                }
                Label {
                    Layout.fillWidth: true
                    text: "Lionel Command Control Switch"
                    color: "#f4f6f8"
                    font.pixelSize: 16
                    font.bold: true

                    TapHandler {
                        onTapped: commandControlSwitch.checked = !commandControlSwitch.checked
                    }
                }
            }
            Label {
                Layout.fillWidth: true
                visible: commandControlSwitch.checked
                text: "Put the Command Control switch into PROGRAM mode before pressing ADD SWITCH."
                color: "#f0c36a"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            Label {
                text: "TMCC ID (1-98)"
                color: "#aeb5bf"
            }
            TextField {
                id: addSwitchId
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                maximumLength: 2
                inputMethodHints: Qt.ImhDigitsOnly
                validator: IntValidator { bottom: 1; top: 98 }
                font.pixelSize: 18
                onEditingFinished: root.completeExistingSwitchIdentity()
            }
            Label {
                text: "Road Name"
                color: "#aeb5bf"
            }
            TextField {
                id: addRoadName
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                maximumLength: 31
                font.pixelSize: 18
            }
            Label {
                text: "Road Number"
                color: "#aeb5bf"
            }
            TextField {
                id: addRoadNumber
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                maximumLength: 4
                inputMethodHints: Qt.ImhDigitsOnly
                validator: RegularExpressionValidator {
                    regularExpression: /[0-9]{0,4}/
                }
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
                Layout.fillWidth: true
                spacing: 10
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "CANCEL"
                    onClicked: addSwitchPopup.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "ADD SWITCH"
                    font.bold: true
                    enabled: addSwitchId.acceptableInput &&
                             addRoadName.text.trim().length > 0 &&
                             addRoadNumber.acceptableInput &&
                             addRoadNumber.text.trim().length > 0
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
            color: "#20242a"
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
                Layout.fillWidth: true
                spacing: 10
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "CANCEL"
                    onClicked: overwriteSwitchPopup.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "REPLACE SWITCH"
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
        width: Math.min(root.width - 40, 620)
        modal: false
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: "#20242a"
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
                font.pixelSize: 24
                font.bold: true
            }

            Label {
                text: "Road Name"
                color: "#aeb5bf"
                font.pixelSize: 14
            }
            TextField {
                id: roadNameField
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                font.pixelSize: 18
                maximumLength: 31
                selectByMouse: true
            }

            Label {
                text: "Road Number"
                color: "#aeb5bf"
                font.pixelSize: 14
            }
            TextField {
                id: roadNumberField
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                font.pixelSize: 18
                maximumLength: 4
                inputMethodHints: Qt.ImhDigitsOnly
                validator: RegularExpressionValidator {
                    regularExpression: /[0-9]{0,4}/
                }
                selectByMouse: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "CANCEL"
                    onClicked: switchEditor.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.preferredHeight: 50
                    text: "SAVE"
                    font.bold: true
                    enabled: roadNameField.text !== root.editingSwitchOriginalName ||
                             roadNumberField.text !== root.editingSwitchOriginalNumber
                    onClicked: {
                        controller.saveSwitchIdentity(root.editingSwitchId,
                                                      roadNameField.text,
                                                      roadNumberField.text)
                        switchEditor.close()
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
