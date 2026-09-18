import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    required property var controller

    x: Math.max(0, (Overlay.overlay.width - width) / 2)
    y: Math.max(76, (Overlay.overlay.height - height) / 2)
    width: Math.min(parent ? parent.width - 32 : 688, 688)
    height: Math.min(parent ? parent.height - 80 : 1150, 1150)
    modal: false
    focus: true
    closePolicy: Popup.NoAutoClose
    property bool showingModules: false
    property string moduleSortKey: "module"
    property int page: 0
    property string configureError: ""
    property alias baseIdText: baseIdField.text

    onOpened: {
        showingModules = false
        page = 0
        controller.reset()
        controller.refreshModules()
    }

    background: Rectangle {
        color: "#171b20"
        radius: 14
        border.width: 1
        border.color: "#59616c"
    }

    contentItem: ColumnLayout {
        spacing: 12

        Label {
            Layout.fillWidth: true
            text: "LCS Module Configuration"
            color: "#f4f6f8"
            font.pixelSize: 26
            font.bold: true
        }

        Label {
            Layout.fillWidth: true
            visible: root.showingModules || root.page === 0
            text: root.showingModules ? "My LCS Modules" : "Which module are you configuring?"
            color: root.showingModules ? "#f4f6f8" : "#aeb5bf"
            font.pixelSize: root.showingModules ? 20 : 16
            font.bold: root.showingModules
        }

        Repeater {
            model: root.showingModules || root.page !== 0 || !root.controller ? [] : root.controller.devices

            delegate: CabButton {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 70
                selected: root.controller.deviceKey === modelData.key
                text: modelData.label + (modelData.blurb.length ? "   " + modelData.blurb : "")
                font.bold: selected
                onClicked: root.controller.selectDevice(modelData.key)
                onDoubleClicked: {
                    root.controller.selectDevice(modelData.key)
                    root.page = 1
                    root.baseIdText = String(root.controller.baseId)
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: !root.showingModules && root.page === 0 && root.controller && root.controller.deviceKey.length > 0
            text: {
                if (!root.controller)
                    return ""
                const rows = root.controller.devices
                for (let i = 0; i < rows.length; ++i) {
                    if (rows[i].key === root.controller.deviceKey)
                        return rows[i].warning
                }
                return ""
            }
            color: "#f0c36a"
            font.pixelSize: 14
            wrapMode: Text.WordWrap
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: !root.showingModules && root.page === 1
            spacing: 10

            Image {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Math.min(480, root.width - 80)
                Layout.preferredHeight: Layout.preferredWidth / 3
                source: root.controller ? root.controller.deviceImage : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                visible: source.toString().length > 0
            }

            Label {
                text: "Base TMCC ID (1-" + (root.controller && root.controller.modes.length ? root.controller.modes.find(function(m) { return m.key === root.controller.modeKey }).maxBase : 98) + ")"
                color: "#f4f6f8"
                font.pixelSize: 20
                font.bold: true
            }

            TextField {
                id: baseIdField
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                text: root.controller ? String(root.controller.baseId) : "1"
                font.pixelSize: 20
                inputMethodHints: Qt.ImhDigitsOnly
                validator: IntValidator { bottom: 1; top: 98 }
                onEditingFinished: {
                    if (root.controller)
                        root.controller.setBaseId(Number(text))
                }
            }

            Label {
                text: "Mode"
                color: "#f4f6f8"
                font.pixelSize: 18
                font.bold: true
            }

            Repeater {
                model: root.controller ? root.controller.modes : []
                delegate: CabButton {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    text: modelData.idsLabel
                    selected: root.controller.modeKey === modelData.key
                    onClicked: root.controller.selectMode(modelData.key)
                }
            }

            Label {
                Layout.fillWidth: true
                visible: root.controller && root.controller.modes.some(function(m) { return m.key === root.controller.modeKey && m.note.length > 0 })
                text: {
                    if (!root.controller)
                        return ""
                    const mode = root.controller.modes.find(function(m) { return m.key === root.controller.modeKey })
                    return mode ? mode.note : ""
                }
                color: "#aeb5bf"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }

            Label {
                Layout.fillWidth: true
                text: "Current Device Configuration"
                color: "#f4f6f8"
                font.pixelSize: 16
                font.bold: true
            }

            Repeater {
                model: root.controller ? root.controller.currentConfiguration : []
                delegate: Label {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData
                    color: "#aeb5bf"
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: root.controller && root.controller.options.length > 0 && root.controller.options.length <= 2
                spacing: 8

                Label {
                    text: "Options"
                    color: "#f4f6f8"
                    font.pixelSize: 18
                    font.bold: true
                }

                Repeater {
                    model: root.controller ? root.controller.options : []
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 6

                        Label {
                            Layout.fillWidth: true
                            visible: modelData.kind !== "CHECKBOX"
                            text: modelData.label
                            color: "#f4f6f8"
                            font.pixelSize: 16
                            font.bold: true
                            wrapMode: Text.WordWrap
                        }

                        Repeater {
                            model: modelData.choices
                            delegate: CabButton {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 48
                                text: modelData.label
                                selected: modelData.selected
                                onClicked: root.controller.selectOption(parent.parent.modelData.key, modelData.index)
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            visible: modelData.kind === "CHECKBOX"
                            spacing: 10

                            CheckBox {
                                id: inlineOptionCheck
                                checked: modelData.checked
                                onClicked: root.controller.setOptionChecked(modelData.key, checked)
                            }

                            Label {
                                Layout.fillWidth: true
                                text: modelData.label
                                color: "#f4f6f8"
                                font.pixelSize: 16
                                wrapMode: Text.WordWrap

                                TapHandler {
                                    onTapped: inlineOptionCheck.toggle()
                                }
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            visible: modelData.note.length > 0
                            text: modelData.note
                            color: "#aeb5bf"
                            font.pixelSize: 14
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }

            Label {
                Layout.fillWidth: true
                text: root.controller && root.controller.assignments.length ? "Currently Assigned" : "Currently Assigned: Unassigned"
                color: root.controller && root.controller.assignments.length ? "#f0c36a" : "#62d98b"
                font.pixelSize: 16
                font.bold: true
            }

            Repeater {
                model: root.controller ? root.controller.assignments : []
                delegate: Label {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData.text
                    color: "#f0c36a"
                    font.pixelSize: 14
                }
            }

            Label {
                Layout.fillWidth: true
                visible: root.controller && root.controller.conflicts.length > 0
                text: "Overlaps"
                color: "#f0c36a"
                font.pixelSize: 16
                font.bold: true
            }

            Repeater {
                model: root.controller ? root.controller.conflicts : []
                delegate: Label {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData.text
                    color: "#f0c36a"
                    font.pixelSize: 14
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.showingModules && root.page === 2
            spacing: 10

            Label {
                text: "Options"
                color: "#f4f6f8"
                font.pixelSize: 20
                font.bold: true
            }

            Repeater {
                model: root.controller ? root.controller.options : []

                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 6

                    Label {
                        Layout.fillWidth: true
                        text: modelData.label
                        color: "#f4f6f8"
                        font.pixelSize: 16
                        font.bold: true
                        wrapMode: Text.WordWrap
                    }

                    Repeater {
                        model: modelData.choices
                        delegate: CabButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            text: modelData.label
                            selected: modelData.selected
                            onClicked: root.controller.selectOption(parent.parent.modelData.key, modelData.index)
                        }
                    }

                    CheckBox {
                        visible: modelData.kind === "CHECKBOX"
                        text: modelData.label
                        checked: modelData.checked
                        onClicked: root.controller.setOptionChecked(modelData.key, checked)
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: modelData.note.length > 0
                        text: modelData.note
                        color: "#aeb5bf"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Label {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: root.controller && root.controller.options.length === 0
                text: "No additional options are required for this module."
                color: "#aeb5bf"
                font.pixelSize: 16
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.showingModules && root.page === 3
            spacing: 10

            Label {
                text: "Review and Configure"
                color: "#f4f6f8"
                font.pixelSize: 20
                font.bold: true
            }

            Label {
                Layout.fillWidth: true
                Layout.topMargin: 8
                Layout.bottomMargin: 10
                horizontalAlignment: Text.AlignHCenter
                text: root.controller && root.controller.programInstruction.length > 0
                      ? root.controller.programInstruction + " then press CONFIGURE below"
                      : ""
                color: "#f0c36a"
                font.pixelSize: 19
                font.bold: true
                lineHeight: 1.15
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: manualSteps.implicitHeight + 38
                color: "transparent"
                radius: 8
                border.width: 1
                border.color: "#59616c"

                Label {
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.top: parent.top
                    anchors.topMargin: -11
                    text: "Manual Configuration"
                    color: "#f4f6f8"
                    font.pixelSize: 16
                    font.bold: true

                    background: Rectangle {
                        color: "#171b20"
                    }
                }

                ColumnLayout {
                    id: manualSteps
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    anchors.topMargin: 22
                    spacing: 8

                    Label {
                        Layout.fillWidth: true
                        text: "These are the Cab-remote steps you would perform manually. CONFIGURE sends them automatically."
                        color: "#aeb5bf"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }

                    Repeater {
                        model: root.controller ? root.controller.review : []
                        delegate: Label {
                            required property var modelData
                            Layout.fillWidth: true
                            text: modelData
                            color: "#f4f6f8"
                            font.pixelSize: 15
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: root.controller && root.controller.configureStatus.length > 0
                implicitHeight: configureStatusLabel.implicitHeight + 24
                radius: 8
                color: "transparent"
                border.width: 1
                border.color: root.controller && root.controller.configureState === "success"
                              ? "#62d98b"
                              : (root.controller && root.controller.configureState === "error" ? "#ff9b78" : "#59616c")

                Label {
                    id: configureStatusLabel
                    anchors.fill: parent
                    anchors.margins: 12
                    text: root.controller ? root.controller.configureStatus : ""
                    color: root.controller && root.controller.configureState === "success"
                           ? "#62d98b"
                           : (root.controller && root.controller.configureState === "error" ? "#ff9b78" : "#f0c36a")
                    font.pixelSize: 15
                    font.bold: root.controller && root.controller.configureState !== "polling"
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Label {
                Layout.fillWidth: true
                visible: root.configureError.length > 0
                text: root.configureError
                color: "#ff9b78"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }

            Item {
                Layout.fillHeight: true
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: root.showingModules
            spacing: 8

            Label {
                text: "Sort:"
                color: "#aeb5bf"
                font.pixelSize: 14
            }

            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 42
                text: "TMCC ID"
                selected: root.moduleSortKey === "tmccId"
                onClicked: root.moduleSortKey = "tmccId"
            }

            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 42
                text: "MODULE TYPE"
                selected: root.moduleSortKey === "module"
                onClicked: root.moduleSortKey = "module"
            }

            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 42
                text: "SCOPE"
                selected: root.moduleSortKey === "scope"
                onClicked: root.moduleSortKey = "scope"
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.showingModules
            clip: true
            spacing: 8
            model: {
                if (!root.controller)
                    return []
                const rows = root.controller.modules.slice()
                rows.sort(function(a, b) {
                    if (root.moduleSortKey === "tmccId")
                        return a.tmccId - b.tmccId || a.module.localeCompare(b.module) || a.scope.localeCompare(b.scope)
                    if (root.moduleSortKey === "scope")
                        return a.scope.localeCompare(b.scope) || a.module.localeCompare(b.module) || a.tmccId - b.tmccId
                    return a.module.localeCompare(b.module) || a.tmccId - b.tmccId
                })
                return rows
            }

            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width
                height: 74
                radius: 8
                color: "#242b33"
                border.width: 1
                border.color: "#4d5966"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    Label {
                        Layout.preferredWidth: 100
                        text: modelData.module
                        color: "#f4f6f8"
                        font.pixelSize: 18
                        font.bold: true
                    }

                    Label {
                        Layout.preferredWidth: 70
                        text: "ID " + modelData.tmccId
                        color: "#f4f6f8"
                        font.pixelSize: 16
                    }

                    Label {
                        Layout.preferredWidth: 70
                        text: modelData.scope
                        color: "#aeb5bf"
                        font.pixelSize: 16
                    }

                    Label {
                        Layout.fillWidth: true
                        text: {
                            const parts = []
                            if (modelData.mode.length)
                                parts.push(modelData.mode)
                            if (modelData.ids.length && modelData.ids !== String(modelData.tmccId))
                                parts.push(modelData.scope + " " + modelData.ids)
                            if (modelData.action.length)
                                parts.push("Action: " + modelData.action)
                            return parts.join(" · ")
                        }
                        color: "#aeb5bf"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }
                }

                TapHandler {
                    onTapped: {
                        root.controller.selectConfiguredModule(modelData.deviceKey, modelData.tmccId, modelData.scope)
                        root.showingModules = false
                        root.page = 1
                        root.baseIdText = String(root.controller.baseId)
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.showingModules && root.controller && root.controller.modules.length === 0
            text: "No LCS modules have reported themselves yet."
            color: "#aeb5bf"
            font.pixelSize: 16
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        Item {
            Layout.fillHeight: true
            visible: !root.showingModules && root.page === 0
        }

        RowLayout {
            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 52
                text: "CANCEL"
                onClicked: root.close()
            }

            CabButton {
                visible: !root.showingModules && root.page > 0
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 52
                text: "BACK"
                onClicked: {
                    if (root.page === 3 && root.controller && root.controller.options.length <= 2)
                        root.page = 1
                    else
                        root.page = root.page - 1
                }
            }

            Layout.fillWidth: true
            spacing: 10

            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 52
                visible: root.showingModules || root.page === 0
                text: root.showingModules ? "BACK" : "MY MODULES"
                onClicked: {
                    if (root.showingModules) {
                        root.showingModules = false
                    } else {
                        root.controller.refreshModules()
                        root.showingModules = true
                    }
                }
            }

            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 52
                text: root.showingModules ? "CLOSE" : (root.page === 3 ? "CONFIGURE" : "NEXT")
                font.bold: !root.showingModules
                enabled: root.showingModules || (root.controller && root.controller.deviceKey.length > 0)
                onClicked: {
                    if (root.showingModules) {
                        root.close()
                    } else if (root.page === 0) {
                        root.page = 1
                        root.baseIdText = String(root.controller.baseId)
                    } else if (root.page === 1) {
                        root.page = root.controller.options.length > 2 ? 2 : 3
                    } else if (root.page === 2) {
                        root.page = 3
                    } else {
                        root.configureError = root.controller.configure()
                    }
                }
            }
        }
    }
}
