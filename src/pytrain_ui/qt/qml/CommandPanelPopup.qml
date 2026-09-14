import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root

    required property var cab
    property string panelKey: ""
    property string panelTitle: ""
    property var actionModel: []
    readonly property var sectionModel: buildSections(actionModel)

    function openFor(key) {
        panelKey = key
        panelTitle = cab.panelTitle(key)
        actionModel = cab.panelModel(key)
        open()
    }

    function buildSections(actions) {
        const sections = []
        for (let i = 0; i < actions.length; ++i) {
            const action = actions[i]
            const name = action.section || "Options"
            let section = null
            for (let j = 0; j < sections.length; ++j) {
                if (sections[j].title === name) {
                    section = sections[j]
                    break
                }
            }
            if (section === null) {
                section = {"title": name, "actions": []}
                sections.push(section)
            }
            section.actions.push(action)
        }
        return sections
    }

    function holdCommandFor(command) {
        switch (command) {
        case "START_UP_IMMEDIATE":
            return "START_UP_DELAYED"
        case "SHUTDOWN_IMMEDIATE":
            return "SHUTDOWN_DELAYED"
        case "ENGINEER_FUEL_LEVEL":
            return "ENGINEER_FUEL_REFILLED"
        case "ENGINEER_WATER_LEVEL":
            return "ENGINEER_WATER_REFILLED"
        default:
            return ""
        }
    }

    width: Math.min(620, (parent ? parent.width : 680) - 32)
    height: Math.min(700, Math.max(240, (parent ? parent.height : 740) - 48))
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    padding: 0

    background: Rectangle {
        radius: 14
        color: "#20252c"
        border.width: 1
        border.color: "#626c79"
    }

    contentItem: ColumnLayout {
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 62
            color: "#292f38"
            radius: 14

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 14
                color: parent.color
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 10
                spacing: 10

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Label {
                        Layout.fillWidth: true
                        text: root.panelTitle
                        color: "#f5f7fa"
                        font.pixelSize: 20
                        font.bold: true
                        elide: Text.ElideRight
                    }

                    Label {
                        Layout.fillWidth: true
                        text: root.actionModel.length + (root.actionModel.length === 1 ? " command" : " commands")
                        color: "#aeb6c2"
                        font.pixelSize: 11
                    }
                }

                ToolButton {
                    Layout.preferredWidth: 42
                    Layout.preferredHeight: 42
                    text: "✕"
                    font.pixelSize: 17
                    onClicked: root.close()

                    contentItem: Text {
                        text: parent.text
                        color: "#dfe4ea"
                        font: parent.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        radius: 8
                        color: parent.down ? "#48515e" : "#343b45"
                        border.width: 1
                        border.color: "#596371"
                    }
                }
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            Layout.topMargin: 10
            Layout.bottomMargin: 10
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 10

                Repeater {
                    model: root.sectionModel

                    Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: sectionLayout.implicitHeight + 20
                        radius: 10
                        color: "#282e36"
                        border.width: 1
                        border.color: "#414a56"

                        ColumnLayout {
                            id: sectionLayout
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 10
                            spacing: 7

                            Label {
                                Layout.fillWidth: true
                                text: modelData.title
                                color: "#aeb8c5"
                                font.pixelSize: 11
                                font.bold: true
                                font.capitalization: Font.AllUppercase
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: width >= 500 ? 3 : width >= 310 ? 2 : 1
                                columnSpacing: 7
                                rowSpacing: 7

                                Repeater {
                                    model: modelData.actions

                                    FunctionButton {
                                        required property var modelData
                                        readonly property string holdCommand: root.holdCommandFor(modelData.command)
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 44
                                        compact: true
                                        text: modelData.label
                                        deferForHold: holdCommand.length > 0
                                        onClicked: root.cab.triggerPanelCommand(modelData.command)
                                        onHeld: root.cab.triggerPanelCommand(holdCommand)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
