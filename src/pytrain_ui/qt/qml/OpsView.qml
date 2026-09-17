import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var controller
    property string sortKey: "roadName"
    property int editingSwitchId: 0
    property bool showInactiveSwitches: false
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
        switchEditor.open()
        roadNameField.forceActiveFocus()
    }

    function openAddSwitch() {
        addSwitchId.text = ""
        addRoadName.text = ""
        addRoadNumber.text = ""
        commandControlSwitch.checked = true
        addError.text = ""
        addSwitchPopup.open()
        addSwitchId.forceActiveFocus()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: controller && controller.scope === "SWITCH" ? "Switch Operations" : "Route Operations"
                color: "#f4f6f8"
                font.pixelSize: 24
                font.bold: true
            }
            CabButton {
                visible: controller && controller.scope === "SWITCH"
                Layout.preferredWidth: 90
                Layout.preferredHeight: 46
                text: "ADD"
                font.bold: true
                onClicked: root.openAddSwitch()
            }
            CabButton {
                Layout.preferredWidth: 100
                Layout.preferredHeight: 46
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
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    text: modelData.label
                    selected: root.sortKey === modelData.key
                    onClicked: root.sortKey = modelData.key
                }
            }
            CabButton {
                visible: controller && controller.scope === "SWITCH"
                Layout.preferredWidth: 154
                Layout.preferredHeight: 38
                text: root.showInactiveSwitches ? "HIDE INACTIVE" : "SHOW INACTIVE"
                selected: root.showInactiveSwitches
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
                        font.pixelSize: 16
                        font.bold: true
                        normalColor: "#a84418"
                        pressedColor: "#d65a20"
                        onClicked: controller.fireRoute(row.modelData.tmccId)
                    }
                    CabButton {
                        visible: controller && controller.scope === "SWITCH"
                        Layout.preferredWidth: 58
                        Layout.preferredHeight: 46
                        text: "EDIT"
                        onClicked: root.editSwitch(row.modelData.tmccId)
                    }
                }
            }
        }
    }

    Popup {
        id: addSwitchPopup
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 40, 620)
        modal: true
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
                    Layout.preferredHeight: 50
                    text: "CANCEL"
                    onClicked: addSwitchPopup.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    text: "ADD SWITCH"
                    font.bold: true
                    onClicked: {
                        const error = controller.addSwitch(Number(addSwitchId.text),
                                                           addRoadName.text,
                                                           addRoadNumber.text,
                                                           commandControlSwitch.checked)
                        if (error.length > 0)
                            addError.text = error
                        else
                            addSwitchPopup.close()
                    }
                }
            }
        }
    }

    Popup {
        id: switchEditor
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 40, 620)
        modal: true
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
                    Layout.preferredHeight: 50
                    text: "CANCEL"
                    onClicked: switchEditor.close()
                }
                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    text: "SAVE"
                    font.bold: true
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
}
