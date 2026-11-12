import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var controller
    signal closeRequested()
    readonly property bool editorOpen: fieldEditor.visible
    readonly property var record: controller ? controller.model : ({})
    color: "#102858"
    radius: 10
    border.color: "#496b9d"

    onVisibleChanged: {
        if (!visible)
            fieldEditor.close()
        else
            details.contentItem.contentY = 0
    }

    Timer {
        interval: 400
        running: root.visible
        repeat: true
        onTriggered: root.controller.refresh(fieldEditor.visible)
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
        background: Rectangle {
            radius: 8
            color: button.down ? Qt.darker("#5c9fc6", 1.45) : button.selected ? "#246aa0" : "#344862"
            border.color: button.selected ? "#78bff0" : "#657c98"
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
                        color: "#b5c9e5"
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
                Layout.fillWidth: true
                text: root.record.creating ? "Create Engine" : (root.record.scopeTitle || "Engine") + " Information"
                color: "white"
                font.pixelSize: 22
                font.bold: true
            }
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
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 0
                            Layout.minimumWidth: 0
                            Layout.columnSpan: modelData.key === "name" ? 2 : 1
                            Layout.preferredHeight: 64
                            text: modelData.label + "\n" + modelData.display
                            font.pixelSize: 17
                            enabled: !!root.record.editable
                            onClicked: fieldEditor.openFor(modelData)
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
                    color: "white"
                }
                background: Rectangle {
                    color: "#572f43"
                    border.color: "#b67580"
                    radius: 8
                    Rectangle {
                        width: parent.width * clearButton.progress
                        height: parent.height
                        radius: 8
                        color: "#a93c4b"
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

    Popup {
        id: fieldEditor
        property var field: ({})
        property string errorText: ""
        readonly property bool numeric: field.key === "number"
        readonly property bool choice: !!field.options && field.options.length > 0
        readonly property bool engineTypeList: choice && field.key === "type"
        readonly property bool shortList: choice && !engineTypeList && field.options.length <= 6

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
            if (engineTypeList)
                revealEngineType.restart()
            if (!choice) {
                entry.forceActiveFocus()
                entry.selectAll()
            }
        }

        function submit() {
            if (choice && picker.currentIndex < 0)
                return
            if (root.controller.edit(field.key, choice ? String(picker.currentValue) : entry.text))
                close()
            else
                errorText = root.controller.model.status || "Unable to save this field."
        }

        parent: Overlay.overlay
        width: Math.min(parent.width - 24, numeric ? 560 : 480)
        x: (parent.width - width) / 2
        y: Math.max(12, (parent.height - height) / 2)
        padding: 16
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape
        background: Rectangle { color: "#102858"; radius: 12; border.color: "#7094c0" }
        contentItem: ColumnLayout {
            spacing: 10
            Label {
                text: fieldEditor.field.label || ""
                color: "white"
                font.pixelSize: 24
                font.bold: true
            }
            ComboBox {
                id: picker
                visible: fieldEditor.choice && !fieldEditor.shortList && !fieldEditor.engineTypeList
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                textRole: "label"
                valueRole: "value"
                model: fieldEditor.field.options || []
                font.pixelSize: 18
            }
            ColumnLayout {
                Layout.fillWidth: true
                visible: fieldEditor.shortList
                spacing: 6
                Repeater {
                    model: fieldEditor.shortList ? fieldEditor.field.options : []
                    FieldChoice {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 50
                    }
                }
            }
            ListView {
                id: engineTypes
                visible: fieldEditor.engineTypeList
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(count, fieldEditor.parent.height < 450 ? 4 : 5) * 56 - (count > 0 ? 6 : 0)
                clip: true
                spacing: 6
                boundsBehavior: Flickable.StopAtBounds
                model: fieldEditor.engineTypeList ? fieldEditor.field.options : []
                ScrollBar.vertical: ScrollBar { id: typeScrollBar }
                delegate: FieldChoice {
                    width: engineTypes.width - typeScrollBar.width - 4
                    height: 50
                }
            }
            RowLayout {
                visible: !fieldEditor.choice
                Layout.fillWidth: true
                TouchSearchField {
                    id: entry
                    touchKeyboardEnabled: fieldEditor.field.key === "name"
                    keyboardTitle: fieldEditor.field.label || ""
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
                spacing: 18
                FooterButton { text: fieldEditor.choice ? "Cancel" : "Close"; onClicked: fieldEditor.close() }
                FooterButton {
                    text: "Apply"
                    selected: true
                    enabled: fieldEditor.choice ? picker.currentIndex >= 0 :
                             !root.record.creating || entry.text.trim().length > 0
                    onClicked: fieldEditor.submit()
                }
            }
        }
    }
}
