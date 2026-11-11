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
        const order = panelKey === "crew"
            ? ["Acknowledge", "Conductor", "Arrive/Depart", "Station", "Status", "Steward", "General", "Etc"]
            : ["Arrive/Depart", "General", "Speed"]
        return order.filter(name => actions.some(action => action.section === name))
    }

    readonly property var choices: category
        ? actions.filter(action => action.section === category)
            .sort((first, second) => first.label.localeCompare(second.label))
        : categories.map(name => ({label: name, command: ""}))

    readonly property var towerGeneralActions: panelKey === "tower" && !category
        ? actions.filter(action => action.section === "General")
        : []

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
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0
        Layout.preferredHeight: Math.max(74, implicitHeight)
        text: modelData.label
        navigates: opensCategory
        onClicked: {
            if (opensCategory) {
                root.category = modelData.label
            } else {
                root.cab.playDialog(modelData.command)
                root.category = ""
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
                rowSpacing: 18
                columnSpacing: 18

                Repeater {
                    model: root.choices
                    ChoiceButton {}
                }

                Label {
                    visible: root.towerGeneralActions.length > 0
                    Layout.columnSpan: 2
                    text: "General dialogs"
                    font.pixelSize: 20
                    font.bold: true
                    color: "#bad4ea"
                }

                RowLayout {
                    visible: root.towerGeneralActions.length > 0
                    Layout.columnSpan: 2
                    Layout.fillWidth: true
                    spacing: 18

                    Repeater {
                        model: root.towerGeneralActions
                        ChoiceButton {}
                    }
                }
            }
        }

        DialogButton {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 160
            Layout.preferredHeight: 52
            text: "Close"
            onClicked: root.close()
        }
    }
}
