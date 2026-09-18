import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    required property var controller

    anchors.centerIn: Overlay.overlay
    width: Math.min(parent ? parent.width - 32 : 688, 688)
    height: Math.min(parent ? parent.height - 48 : 1180, 1180)
    modal: true
    focus: true
    closePolicy: Popup.NoAutoClose
    property bool showingModules: false
    property string moduleSortKey: "module"

    onOpened: {
        showingModules = false
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
            text: root.showingModules ? "My LCS Modules" : "Which module are you configuring?"
            color: root.showingModules ? "#f4f6f8" : "#aeb5bf"
            font.pixelSize: root.showingModules ? 20 : 16
            font.bold: root.showingModules
        }

        Repeater {
            model: root.showingModules || !root.controller ? [] : root.controller.devices

            delegate: CabButton {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 70
                selected: root.controller.deviceKey === modelData.key
                text: modelData.label + (modelData.blurb.length ? "   " + modelData.blurb : "")
                font.bold: selected
                onClicked: root.controller.selectDevice(modelData.key)
            }
        }

        Label {
            Layout.fillWidth: true
            visible: !root.showingModules && root.controller && root.controller.deviceKey.length > 0
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
                        root.showingModules = false
                        root.controller.selectDevice(modelData.deviceKey)
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
            visible: !root.showingModules
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            CabButton {
                visible: !root.showingModules
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 52
                text: "CANCEL"
                onClicked: root.close()
            }

            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 52
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
                text: root.showingModules ? "CLOSE" : "NEXT"
                font.bold: !root.showingModules
                enabled: root.showingModules || (root.controller && root.controller.deviceKey.length > 0)
                onClicked: {
                    if (root.showingModules)
                        root.close()
                }
            }
        }
    }
}
