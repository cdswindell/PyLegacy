import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var cab
    property string panelKey: ""
    property string title: ""
    property string category: ""
    property var actions: []
    readonly property var categories: {
        if (panelKey === "lights")
            return Array.from(new Set(actions.map(action => action.section)))
                .sort((first, second) => first.localeCompare(second))
        const order = panelKey === "crew"
            ? ["Acknowledge", "Conductor", "Arrive/Depart", "Station", "Status", "Steward", "General", "Etc"]
            : ["Arrive/Depart", "General", "Speed"]
        return order.filter(name => actions.some(action => action.section === name))
    }

    readonly property int choiceHeight: 74
    readonly property int choiceSpacing: 18
    readonly property int sectionHeadingHeight: 26
    readonly property var speedOrder: ["STOP_HOLD", "RESTRICTED", "SLOW", "MEDIUM", "LIMITED", "NORMAL", "HIGHBALL"]
    readonly property var inlineSections: {
        if (category)
            return []

        const candidates = panelKey === "lights"
            ? ["Rule 17", "Marker Lights", "Tender Lights", "Ditch Lights"]
            : panelKey === "tower" ? ["General", "Speed"] : ["General"]
        const sections = []
        let sectionsHeight = 0
        for (const name of candidates) {
            const commands = sortedActions(name)
            if (!commands.length)
                continue

            const ditchLights = name === "Ditch Lights"
            if (ditchLights && choicesView.availableWidth < 540)
                continue
            const columns = ditchLights ? 4 : 3
            const buttonHeight = ditchLights ? 86 : choiceHeight
            const rows = Math.ceil(commands.length / columns)
            const sectionHeight = sectionHeadingHeight + rows * (buttonHeight + choiceSpacing)
            const categoryRows = Math.ceil((categories.length - sections.length - 1) / 2)
            const categoriesHeight = categoryRows * (choiceHeight + choiceSpacing)
            if (categoriesHeight + sectionsHeight + sectionHeight <= choicesView.availableHeight) {
                sections.push({name, commands, columns, buttonHeight})
                sectionsHeight += sectionHeight + choiceSpacing
            }
        }
        return sections
    }

    readonly property var choices: category
        ? sortedActions(category)
        : categories.filter(name => !inlineSections.some(section => section.name === name))
            .map(name => ({label: name, command: ""}))

    function speedRank(command) {
        const match = /^(TOWER|ENGINEER)_SPEED_(.+)$/.exec(command)
        return match ? speedOrder.indexOf(match[2]) : -1
    }

    function sortedActions(section) {
        const commands = actions.filter(action => action.section === section)
        if (panelKey === "tower" && section === "Speed")
            return commands.sort((first, second) => speedRank(first.command) - speedRank(second.command))
        return commands.sort((first, second) => first.label.localeCompare(second.label))
    }

    onCategoryChanged: choicesView.contentItem.contentY = 0

    function openFor(key) {
        title = cab.panelTitle(key)
        actions = cab.panelModel(key)
        category = ""
        panelKey = key
    }

    function close() {
        panelKey = ""
        category = ""
    }

    visible: panelKey.length > 0
    clip: true
    color: "#102858"
    radius: 12
    border.color: "#617f9f"

    // Keep taps and scrolling in the panel from reaching controls it covers.
    MouseArea {
        anchors.fill: parent
        onWheel: function(event) { event.accepted = true }
    }

    Shortcut {
        sequence: "Escape"
        enabled: root.visible
        onActivated: root.close()
    }

    component DialogButton: Button {
        id: button
        property bool navigates: false
        padding: 10
        font.pixelSize: 24
        font.bold: navigates
        rightPadding: navigates ? 36 : padding
        contentItem: Text {
            text: button.text
            font: button.font
            color: "#f5f7fa"
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        Text {
            visible: button.navigates
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            text: "›"
            font.pixelSize: 32
            color: "#a4d8ff"
        }
        background: Rectangle {
            radius: 8
            border.color: button.activeFocus ? "#a4d8ff" : button.navigates ? "#5b9bcb" : "#7287a0"
            gradient: Gradient {
                GradientStop { position: 0; color: button.navigates ? (button.down ? "#12365d" : "#245781") : (button.down ? "#28425e" : "#4e647d") }
                GradientStop { position: 1; color: button.navigates ? (button.down ? "#245781" : "#163658") : (button.down ? "#426482" : "#263950") }
            }
        }
    }

    component ChoiceButton: DialogButton {
        id: choice
        required property var modelData
        readonly property bool opensCategory: !modelData.command
        readonly property int speedChevrons: Math.max(0, root.speedRank(modelData.command))
        topPadding: speedChevrons > 0 ? 32 : padding

        SpeedChevrons {
            anchors.top: parent.top
            anchors.topMargin: 8
            anchors.horizontalCenter: parent.horizontalCenter
            width: implicitWidth
            height: implicitHeight
            count: choice.speedChevrons
        }
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0
        Layout.preferredHeight: Math.max(root.choiceHeight, implicitHeight)
        text: modelData.label
        navigates: opensCategory
        onClicked: {
            if (opensCategory) {
                root.category = modelData.label
            } else if (root.panelKey === "lights") {
                root.cab.triggerPanelCommand(modelData.command)
            } else {
                root.cab.playDialog(modelData.command)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            DialogButton {
                visible: root.category !== ""
                Layout.preferredWidth: 124
                Layout.preferredHeight: 58
                text: "Back"
                onClicked: root.category = ""
            }
            Label {
                Layout.fillWidth: true
                text: root.category || root.title
                font.pixelSize: 24
                font.bold: true
                color: "#f5f7fa"
                wrapMode: Text.WordWrap
            }
        }

        ScrollView {
            id: choicesView
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            GridLayout {
                width: choicesView.availableWidth
                columns: 2
                rowSpacing: root.choiceSpacing
                columnSpacing: root.choiceSpacing

                Label {
                    visible: root.actions.length === 0
                    Layout.columnSpan: 2
                    Layout.fillWidth: true
                    text: root.panelKey === "lights" ? "No lighting commands available" : "No dialogs available"
                    font.pixelSize: 20
                    color: "#bad4ea"
                    wrapMode: Text.WordWrap
                }

                Repeater {
                    model: root.choices
                    ChoiceButton {}
                }

                Repeater {
                    model: root.inlineSections
                    ColumnLayout {
                        id: inlineSection
                        required property var modelData
                        Layout.columnSpan: 2
                        Layout.fillWidth: true
                        spacing: root.choiceSpacing

                        Label {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.sectionHeadingHeight
                            text: inlineSection.modelData.name === "General" ? "General dialogs" : inlineSection.modelData.name
                            font.pixelSize: 20
                            font.bold: true
                            color: "#bad4ea"
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: inlineSection.modelData.columns
                            rowSpacing: root.choiceSpacing
                            columnSpacing: root.choiceSpacing

                            Repeater {
                                model: inlineSection.modelData.commands
                                ChoiceButton {
                                    required property int index
                                    Layout.row: Math.floor(index / inlineSection.modelData.columns)
                                    Layout.column: index % inlineSection.modelData.columns
                                    Layout.preferredHeight: Math.max(inlineSection.modelData.buttonHeight, implicitHeight)
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            id: footer
            readonly property bool lightsPanel: root.panelKey === "lights"
            readonly property int buttonHeight: lightsPanel ? 60 : 52
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: lightsPanel
            Layout.preferredWidth: lightsPanel ? -1 : 160
            spacing: root.choiceSpacing

            DialogButton {
                visible: footer.lightsPanel
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: footer.buttonHeight
                text: "Aux 2"
                onClicked: root.cab.triggerPanelCommand("AUX2_OPTION_ONE")
            }

            DialogButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: footer.buttonHeight
                text: "Close"
                onClicked: root.close()
            }

            DialogButton {
                visible: footer.lightsPanel && root.cab.isLegacy
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: footer.buttonHeight
                text: "Cab"
                onClicked: root.cab.triggerPanelCommand("CAB_AUTO")
            }
        }
    }
}
