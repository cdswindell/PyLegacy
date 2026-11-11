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
        padding: 10
        font.pixelSize: 22
        contentItem: Text {
            text: button.text
            font: button.font
            color: "#f5f7fa"
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 8
            border.color: button.activeFocus ? "#a4d8ff" : "#7287a0"
            gradient: Gradient {
                GradientStop { position: 0; color: button.down ? "#28425e" : "#4e647d" }
                GradientStop { position: 1; color: button.down ? "#426482" : "#263950" }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            DialogButton {
                visible: root.category !== ""
                Layout.preferredWidth: 98
                Layout.preferredHeight: 48
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
            id: categoryView
            visible: root.category === ""
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            GridLayout {
                width: categoryView.availableWidth
                columns: 2
                rowSpacing: 14
                columnSpacing: 14

                Repeater {
                    model: root.categories
                    DialogButton {
                        required property string modelData
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: 70
                        text: modelData
                        onClicked: {
                            root.category = modelData
                            commandList.positionViewAtBeginning()
                            commandList.forceActiveFocus()
                        }
                    }
                }
            }
        }

        ListView {
            id: commandList
            visible: root.category !== ""
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            clip: true
            spacing: 12
            boundsBehavior: Flickable.StopAtBounds
            model: root.actions.filter(action => action.section === root.category)
            ScrollBar.vertical: ScrollBar {}
            delegate: DialogButton {
                required property var modelData
                width: ListView.view.width - 12
                height: Math.max(64, implicitHeight)
                text: modelData.label
                onClicked: {
                    root.cab.triggerPanelCommand(modelData.command)
                    root.category = ""
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
