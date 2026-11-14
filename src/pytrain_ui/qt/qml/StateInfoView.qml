import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    PanelMetrics { id: metrics }
    required property var controller
    signal closeRequested()
    readonly property bool useTouchKeyboard: Qt.platform.os === "linux"
    readonly property bool editorOpen: fieldEditor.visible || roadNameKeyboard.visible
    readonly property bool hasUnsavedChanges: !!record.unsaved || fieldEditor.hasUnsavedChanges || roadNameKeyboard.hasUnsavedChanges
    readonly property color fieldLabelColor: "#b5c9e5"
    readonly property var record: controller ? controller.model : ({})
    color: "#102858"
    radius: 10
    border.color: "#496b9d"

    onVisibleChanged: {
        if (!visible) {
            fieldEditor.close()
            roadNameKeyboard.close()
        } else
            details.contentItem.contentY = 0
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
        font.pixelSize: 18
    }

    component DetailGrid: GridLayout {
        id: section
        required property var rows
        columns: width >= 520 ? 4 : 2
        columnSpacing: 8
        rowSpacing: 8
        Repeater {
            model: section.rows
            delegate: Rectangle {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.minimumWidth: 0
                Layout.preferredHeight: detailLabels.implicitHeight + 16
                color: "#173765"
                radius: 6
                ColumnLayout {
                    id: detailLabels
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 8
                    spacing: 2
                    Label {
                        Layout.fillWidth: true
                        text: modelData.label
                        color: root.fieldLabelColor
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }
                    Label {
                        Layout.fillWidth: true
                        text: modelData.value
                        color: "white"
                        font.pixelSize: 17
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: root.record.creating ? "Create Engine" : (root.record.scopeTitle || "Engine") + " Information"
                color: "white"
                font.pixelSize: 22
                font.bold: true
            }
            Label {
                Layout.fillWidth: true
                visible: !root.record.creating && !!root.record.editable
                text: root.useTouchKeyboard ? "Tap to edit" : "Click to edit"
                color: "#b5c9e5"
                font.pixelSize: 15
                wrapMode: Text.WordWrap
            }
            Item { Layout.fillWidth: true; visible: root.record.creating || !root.record.editable }
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
            font.pixelSize: 16
        }

        ScrollView {
            id: details
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                width: details.availableWidth
                spacing: 8

                GridLayout {
                    Layout.fillWidth: true
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
                            font.pixelSize: 17
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
                    font.pixelSize: 16
                }

                Label {
                    visible: live.rows.length > 0
                    Layout.topMargin: metrics.sectionGap
                    text: "Real Time Status"
                    color: "white"
                    font.pixelSize: 19
                    font.bold: true
                }
                DetailGrid {
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
                    font.pixelSize: 19
                    font.bold: true
                }
                DetailGrid {
                    id: membership
                    Layout.fillWidth: true
                    rows: root.record.membership || []
                    visible: rows.length > 0
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: metrics.footerGap
            spacing: 18
            DelayButton {
                id: clearButton
                visible: !root.record.creating && !!root.record.canClear
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.minimumWidth: 0
                Layout.preferredHeight: 56
                text: "Hold to Clear"
                Accessible.name: "Hold to clear this Base 3 record"
                delay: 3000
                onVisibleChanged: if (visible) checked = false
                onActivated: root.controller.clear()
                contentItem: Text {
                    text: clearButton.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 18
                    color: "#ff6666"
                }
                background: ButtonFace {
                    depressed: clearButton.down
                    focused: clearButton.activeFocus
                    Rectangle {
                        visible: clearButton.down && clearButton.progress > 0
                        anchors.left: parent.left
                        anchors.leftMargin: 3
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 2
                        width: Math.max(0, parent.width - 6) * clearButton.progress
                        height: 5
                        radius: 2
                        color: clearButton.contentItem.color
                    }
                }
            }
            FooterButton {
                text: root.record.creating && !root.record.busy ? "Cancel" : "Close"
                onClicked: root.closeRequested()
            }
            FooterButton {
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

    SearchKeyboard {
        id: roadNameKeyboard
        title: "Road Name"
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
        width: Math.min(parent.width - 24, roadName ? 840 : (numeric ? 560 : 480 * editorScale))
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
                Layout.topMargin: metrics.footerGap
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
