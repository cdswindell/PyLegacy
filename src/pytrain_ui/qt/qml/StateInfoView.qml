import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    PanelMetrics { id: metrics }
    required property var controller
    signal closeRequested()
    readonly property bool useTouchKeyboard: Qt.platform.os === "linux"
    readonly property bool editorOpen: fieldEditor.visible || roadNameKeyboard.visible ||
        accessoryName.keyboardOpen || accessoryNumberPad.visible
    readonly property bool inlineIdentity: !!record.inlineIdentity
    readonly property bool amc2Info: !!record.lcsConfiguration && record.lcsConfiguration.length > 0
    property int accessoryDraftId: 0
    property string initialAccessoryName: ""
    property string initialAccessoryNumber: ""
    readonly property bool accessoryIdentityDirty: inlineIdentity && accessoryDraftId === record.tmccId &&
        (accessoryName.text !== initialAccessoryName || accessoryNumber.text !== initialAccessoryNumber)
    readonly property bool hasUnsavedChanges: !!record.unsaved || fieldEditor.hasUnsavedChanges || roadNameKeyboard.hasUnsavedChanges || accessoryIdentityDirty
    readonly property color fieldLabelColor: "#b5c9e5"
    readonly property var record: controller ? controller.model : ({})
    implicitHeight: panelLayout.implicitHeight + 20
    color: "#102858"
    radius: 10
    border.color: "#496b9d"

    function loadAccessoryIdentity() {
        const fields = record.identity || []
        const name = fields.find(field => field.key === "name")
        const number = fields.find(field => field.key === "number")
        initialAccessoryName = name && name.value ? String(name.value) : ""
        initialAccessoryNumber = number && number.value ? String(number.value) : ""
        accessoryName.text = initialAccessoryName
        accessoryNumber.text = initialAccessoryNumber
        accessoryDraftId = record.tmccId || 0
    }

    function syncAccessoryIdentity() {
        if (!visible || !inlineIdentity)
            return
        if (accessoryDraftId !== record.tmccId) {
            loadAccessoryIdentity()
            return
        }
        const fields = record.identity || []
        // Let late identity data populate an empty field without replacing an open draft.
        if (!initialAccessoryName && !accessoryName.text) {
            const name = fields.find(field => field.key === "name")
            initialAccessoryName = name && name.value ? String(name.value) : ""
            accessoryName.text = initialAccessoryName
        }
        if (!initialAccessoryNumber && !accessoryNumber.text) {
            const number = fields.find(field => field.key === "number")
            initialAccessoryNumber = number && number.value ? String(number.value) : ""
            accessoryNumber.text = initialAccessoryNumber
        }
    }

    onRecordChanged: Qt.callLater(syncAccessoryIdentity)

    onVisibleChanged: {
        if (!visible) {
            fieldEditor.close()
            roadNameKeyboard.close()
            accessoryNumberPad.close()
            accessoryDraftId = 0
        } else {
            details.contentItem.contentY = 0
            Qt.callLater(syncAccessoryIdentity)
        }
    }

    Timer {
        interval: 400
        running: root.visible
        repeat: true
        onTriggered: root.controller.refresh(root.editorOpen)
    }

    component InfoButton: Button {
        id: button
        property bool selected: false
        font.bold: true
        contentItem: Text {
            text: button.text
            font: button.font
            color: button.enabled ? "#ffffff" : "#9bacbf"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        background: ButtonFace {
            depressed: button.down
            selected: button.selected
            focused: button.activeFocus
        }
    }

    component FooterButton: InfoButton {
        Layout.fillWidth: true
        Layout.preferredWidth: 0
        Layout.minimumWidth: 0
        Layout.preferredHeight: 56
        font.pixelSize: 22
    }

    ColumnLayout {
        id: panelLayout
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: root.record.creating ? "Create Engine" : (root.record.scopeTitle || "Engine") + " Information"
                color: "white"
                font.pixelSize: 26
                font.bold: true
            }
            Label {
                Layout.fillWidth: true
                visible: !root.inlineIdentity && !root.record.creating && !!root.record.editable
                text: root.useTouchKeyboard ? "Tap to edit" : "Click to edit"
                color: "#b5c9e5"
                font.pixelSize: 18
                wrapMode: Text.WordWrap
            }
            Item { Layout.fillWidth: true; visible: root.inlineIdentity || root.record.creating || !root.record.editable }
            FooterButton {
                visible: !!root.record.creating
                Layout.fillWidth: false
                Layout.preferredWidth: 145
                text: "Set Address"
                enabled: !root.record.busy
                onClicked: root.controller.setAddress()
            }
        }

        Label {
            Layout.fillWidth: true
            visible: text.length > 0
            text: root.record.status || ""
            color: "#d0def2"
            wrapMode: Text.WordWrap
            font.pixelSize: 19
        }

        ScrollView {
            id: details
            Layout.fillWidth: true
            Layout.preferredHeight: detailsContent.implicitHeight
            Layout.fillHeight: true
            Layout.maximumHeight: detailsContent.implicitHeight
            Layout.minimumHeight: 0
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: detailsContent
                width: details.availableWidth
                spacing: 8

                ColumnLayout {
                    visible: root.inlineIdentity
                    Layout.fillWidth: true
                    spacing: 8

                    Label {
                        text: "Road Name"
                        color: root.fieldLabelColor
                        font.pixelSize: 17
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        TouchSearchField {
                            id: accessoryName
                            objectName: "accessoryRoadName"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredHeight: 52
                            maximumLength: 31
                            titleCaseEnabled: true
                            keyboardTitle: "Road Name"
                            readOnly: !root.record.editable
                            touchKeyboardEnabled: root.useTouchKeyboard && !readOnly
                            font.pixelSize: 22
                            selectByMouse: true
                            Accessible.name: "Road Name"
                        }
                        TitleCaseButton {
                            field: accessoryName
                            Layout.preferredHeight: accessoryName.Layout.preferredHeight
                            visible: !!root.record.editable
                        }
                    }

                    Label {
                        text: "Road Number"
                        color: root.fieldLabelColor
                        font.pixelSize: 17
                    }
                    TextField {
                        id: accessoryNumber
                        objectName: "accessoryRoadNumber"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 52
                        maximumLength: 4
                        validator: RegularExpressionValidator { regularExpression: /[0-9]{0,4}/ }
                        readOnly: !root.record.editable
                        font.pixelSize: 22
                        selectByMouse: true
                        inputMethodHints: Qt.ImhDigitsOnly
                        Accessible.name: "Road Number"
                        TapHandler {
                            enabled: root.useTouchKeyboard && !accessoryNumber.readOnly
                            onTapped: accessoryNumberPad.openFor(accessoryNumber.text)
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    visible: !root.inlineIdentity
                    columns: 2
                    columnSpacing: 8
                    rowSpacing: 8
                    Repeater {
                        model: root.record.identity || []
                        delegate: InfoButton {
                            id: identityButton
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 0
                            Layout.minimumWidth: 0
                            Layout.columnSpan: modelData.key === "name" ? 2 : 1
                            Layout.preferredHeight: 64
                            text: modelData.label + "\n" + modelData.display
                            font.pixelSize: 20
                            enabled: !!root.record.editable
                            contentItem: Item {
                                ColumnLayout {
                                    width: parent.width
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 0
                                    Label {
                                        Layout.fillWidth: true
                                        text: modelData.label
                                        textFormat: Text.PlainText
                                        font: identityButton.font
                                        color: root.fieldLabelColor
                                        horizontalAlignment: Text.AlignHCenter
                                        elide: Text.ElideRight
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: modelData.display
                                        textFormat: Text.PlainText
                                        font: identityButton.font
                                        color: "white"
                                        horizontalAlignment: Text.AlignHCenter
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                            onClicked: {
                                if (modelData.key === "name" && root.useTouchKeyboard)
                                    roadNameKeyboard.openWithText(modelData.value || "")
                                else
                                    fieldEditor.openFor(modelData)
                            }
                        }
                    }
                }

                Label {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: {
                        const recordId = root.record.record || ""
                        const bluetooth = root.record.bluetoothId
                        if (!bluetooth)
                            return recordId
                        return (recordId ? recordId + "  ·  " : "") + "Bluetooth ID: " + bluetooth
                    }
                    wrapMode: Text.WordWrap
                    color: "#b5c9e5"
                    font.pixelSize: 19
                }

                Label {
                    visible: root.amc2Info
                    Layout.topMargin: metrics.sectionGap
                    text: "AMC2 Configuration"
                    color: "white"
                    font.pixelSize: 23
                    font.bold: true
                }
                StateInfoGrid {
                    id: amc2Device
                    objectName: "amc2DeviceConfiguration"
                    Layout.fillWidth: true
                    columns: 3
                    tileHeight: 84
                    rows: (root.record.lcsConfiguration || []).slice(0, 3)
                    visible: root.amc2Info
                }
                StateInfoGrid {
                    id: amc2Motors
                    objectName: "amc2MotorConfiguration"
                    Layout.fillWidth: true
                    columns: 2
                    tileHeight: amc2Device.tileHeight
                    rows: (root.record.lcsConfiguration || []).slice(3)
                    visible: rows.length > 0
                }
                Label {
                    visible: lcsBoard.rows.length > 0
                    Layout.topMargin: metrics.sectionGap
                    text: "LCS Board Information"
                    color: "white"
                    font.pixelSize: 23
                    font.bold: true
                }
                StateInfoGrid {
                    id: lcsBoard
                    objectName: "lcsBoardInformation"
                    Layout.fillWidth: true
                    columns: 3
                    rows: root.record.lcsBoard || []
                    visible: rows.length > 0
                }
                Label {
                    visible: live.rows.length > 0
                    Layout.topMargin: metrics.sectionGap
                    text: "Real Time Status"
                    color: "white"
                    font.pixelSize: 23
                    font.bold: true
                }
                StateInfoGrid {
                    id: live
                    Layout.fillWidth: true
                    rows: root.record.live || []
                    visible: rows.length > 0
                }
                Label {
                    visible: membership.rows.length > 0
                    Layout.topMargin: metrics.sectionGap
                    text: "Consist Details"
                    color: "white"
                    font.pixelSize: 23
                    font.bold: true
                }
                StateInfoGrid {
                    id: membership
                    Layout.fillWidth: true
                    rows: root.record.membership || []
                    visible: rows.length > 0
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: metrics.footerOffset(implicitHeight, parent.spacing)
            spacing: 18
            readonly property int buttonHeight: 70
            id: recordFooter

            ClearRecordButton {
                visible: !root.record.creating
                enabled: !!root.record.canClear
                Layout.preferredHeight: recordFooter.buttonHeight
                font.pixelSize: 22
                onActivated: root.controller.clear()
            }
            FooterButton {
                Layout.preferredHeight: recordFooter.buttonHeight
                text: root.record.creating && !root.record.busy ? "Cancel" : "Close"
                onClicked: root.closeRequested()
            }
            FooterButton {
                objectName: "saveAccessoryIdentity"
                visible: root.inlineIdentity
                Layout.preferredHeight: recordFooter.buttonHeight
                text: "Save"
                selected: true
                enabled: !!root.record.editable && root.accessoryIdentityDirty && accessoryNumber.acceptableInput
                onClicked: {
                    const edits = {}
                    if (accessoryName.text !== root.initialAccessoryName)
                        edits.name = accessoryName.text
                    if (accessoryNumber.text !== root.initialAccessoryNumber)
                        edits.number = accessoryNumber.text
                    if (root.controller.saveAccessoryIdentity(edits)) {
                        root.loadAccessoryIdentity()
                        root.closeRequested()
                    }
                }
            }
            FooterButton {
                Layout.preferredHeight: recordFooter.buttonHeight
                visible: !!root.record.creating
                text: "Create"
                enabled: !!root.record.canCreate
                selected: true
                onClicked: root.controller.create()
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        visible: fieldEditor.visible
        onWheel: event => event.accepted = true
    }

    TmccKeypad {
        id: accessoryNumberPad
        title: "Road Number"
        minimumId: 0
        maximumId: 9999
        allowEmpty: true
        onSubmitted: {
            accessoryNumber.text = entryText
            close()
        }
    }

    SearchKeyboard {
        id: roadNameKeyboard
        title: "Road Name"
        titleCaseEnabled: true
        entryLimit: 31
        saveEntry: function(text) {
            if (root.controller.edit("name", text))
                return true
            errorText = root.controller.model.status || "Unable to save the road name."
            return false
        }
    }

    Popup {
        id: fieldEditor
        property var field: ({})
        property string errorText: ""
        readonly property bool roadName: field.key === "name"
        readonly property bool numeric: field.key === "number"
        readonly property bool choice: !!field.options && field.options.length > 0
        readonly property bool engineTypeList: choice && field.key === "type"
        readonly property real editorScale: choice ? 1.25 : 1
        readonly property int choiceHeight: Math.round(50 * editorScale)
        readonly property int choiceGap: Math.round(10 * editorScale)
        readonly property real choiceBodyHeight: Math.max(choiceHeight, parent.height - 200)
        readonly property bool shortList: choice && !engineTypeList && field.options.length <= 6
            && field.options.length * (choiceHeight + choiceGap) - choiceGap <= choiceBodyHeight
        readonly property bool scrollChoices: choice && (engineTypeList || (!shortList && field.options.length <= 6))
        readonly property string originalValue: field.value === undefined || field.value === null ? "" : String(field.value)
        readonly property bool hasUnsavedChanges: visible && (choice
            ? picker.currentIndex >= 0 && String(picker.currentValue) !== originalValue
            : entry.text.trim() !== originalValue.trim())

        Timer {
            id: revealEngineType
            interval: 60
            onTriggered: {
                if (fieldEditor.visible && picker.currentIndex >= 0) {
                    engineTypes.forceLayout()
                    engineTypes.positionViewAtIndex(picker.currentIndex, ListView.Center)
                }
            }
        }

        component FieldChoice: InfoButton {
            required property int index
            required property var modelData
            text: modelData.label
            font.pixelSize: Math.round(18 * fieldEditor.editorScale)
            selected: picker.currentIndex === index
            Accessible.checkable: true
            Accessible.checked: selected
            onClicked: picker.currentIndex = index
        }

        function openFor(row) {
            field = row
            errorText = ""
            entry.text = row.value === undefined || row.value === null ? "" : String(row.value)
            picker.currentIndex = choice ? picker.indexOfValue(row.value) : -1
            open()
            if (scrollChoices)
                revealEngineType.restart()
            if (!choice) {
                entry.forceActiveFocus()
                entry.cursorPosition = entry.length
            }
        }

        function submit() {
            if (choice && picker.currentIndex < 0)
                return false
            if (root.controller.edit(field.key, choice ? String(picker.currentValue) : entry.text)) {
                close()
                return true
            }
            errorText = root.controller.model.status || "Unable to save this field."
            return false
        }

        parent: Overlay.overlay
        width: Math.min(parent.width - 24, roadName ? 600 : (numeric ? 560 : 480 * editorScale))
        x: (parent.width - width) / 2
        y: Math.max(12, (parent.height - height) / 2)
        padding: Math.round(16 * editorScale)
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape
        background: Rectangle { color: "#102858"; radius: 12; border.color: "#7094c0" }
        contentItem: ColumnLayout {
            spacing: Math.round(10 * fieldEditor.editorScale)
            Label {
                text: fieldEditor.field.label || ""
                color: "white"
                font.pixelSize: Math.round(24 * fieldEditor.editorScale)
                font.bold: true
            }
            ComboBox {
                id: picker
                visible: fieldEditor.choice && !fieldEditor.shortList && !fieldEditor.scrollChoices
                Layout.fillWidth: true
                Layout.preferredHeight: Math.round(54 * fieldEditor.editorScale)
                textRole: "label"
                valueRole: "value"
                model: fieldEditor.field.options || []
                font.pixelSize: Math.round(18 * fieldEditor.editorScale)
            }
            ColumnLayout {
                Layout.fillWidth: true
                visible: fieldEditor.shortList
                spacing: fieldEditor.choiceGap
                Repeater {
                    model: fieldEditor.shortList ? fieldEditor.field.options : []
                    FieldChoice {
                        Layout.fillWidth: true
                        Layout.preferredHeight: fieldEditor.choiceHeight
                    }
                }
            }
            ListView {
                id: engineTypes
                visible: fieldEditor.scrollChoices
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(fieldEditor.choiceBodyHeight,
                    Math.min(count, 5) * (fieldEditor.choiceHeight + spacing) - (count > 0 ? spacing : 0))
                clip: true
                spacing: fieldEditor.choiceGap
                boundsBehavior: Flickable.StopAtBounds
                model: fieldEditor.scrollChoices ? fieldEditor.field.options : []
                ScrollBar.vertical: ListScrollBar { id: typeScrollBar }
                delegate: FieldChoice {
                    width: engineTypes.width - typeScrollBar.gutterWidth
                    height: fieldEditor.choiceHeight
                }
            }
            RowLayout {
                visible: !fieldEditor.choice
                Layout.fillWidth: true
                TextField {
                    id: entry
                    Layout.fillWidth: true
                    Layout.preferredHeight: fieldEditor.numeric ? 68 : 52
                    maximumLength: fieldEditor.numeric ? 4 : 31
                    inputMethodHints: fieldEditor.numeric ? Qt.ImhDigitsOnly : Qt.ImhNone
                    selectByMouse: true
                    font.pixelSize: 20
                    onAccepted: fieldEditor.submit()
                }
                TitleCaseButton {
                    visible: fieldEditor.roadName
                    field: entry
                    Layout.preferredHeight: 52
                }
                RosterBackspaceButton {
                    visible: fieldEditor.field.key === "name"
                    field: entry
                    Accessible.name: "Backspace road name"
                    Layout.preferredHeight: 52
                }
            }
            GridLayout {
                visible: fieldEditor.numeric
                Layout.fillWidth: true
                columns: 3
                rowSpacing: 8
                columnSpacing: 8
                Repeater {
                    model: fieldEditor.numeric ? ["1", "2", "3", "4", "5", "6", "7", "8", "9", "Clear", "0", "⌫"] : []
                    FooterButton {
                        required property string modelData
                        text: modelData
                        Layout.preferredHeight: 74
                        font.pixelSize: 26
                        onClicked: {
                            if (modelData === "Clear") {
                                entry.clear()
                            } else if (modelData === "⌫") {
                                const end = entry.selectionEnd
                                const start = entry.selectedText.length ? entry.selectionStart : Math.max(0, end - 1)
                                entry.remove(start, end)
                            } else {
                                const start = entry.selectionStart
                                entry.remove(start, entry.selectionEnd)
                                entry.insert(start, modelData)
                            }
                        }
                    }
                }
            }
            Label {
                Layout.fillWidth: true
                visible: text.length > 0
                text: fieldEditor.errorText
                wrapMode: Text.WordWrap
                color: "#ffd4d8"
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: metrics.footerOffset(implicitHeight, parent.spacing)
                spacing: 18
                FooterButton {
                    text: fieldEditor.choice || fieldEditor.roadName ? "Cancel" : "Close"
                    Layout.preferredHeight: Math.round(56 * fieldEditor.editorScale)
                    font.pixelSize: Math.round(18 * fieldEditor.editorScale)
                    onClicked: fieldEditor.close()
                }
                FooterButton {
                    text: fieldEditor.roadName ? "Save" : "Apply"
                    Layout.preferredHeight: Math.round(56 * fieldEditor.editorScale)
                    font.pixelSize: Math.round(18 * fieldEditor.editorScale)
                    selected: true
                    enabled: fieldEditor.choice ? picker.currentIndex >= 0 :
                             !root.record.creating || entry.text.trim().length > 0
                    onClicked: fieldEditor.submit()
                }
            }
        }
    }
}
