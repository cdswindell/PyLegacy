import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var admin
    required property var cab
    property bool allNodes: false
    property int revision: 0
    readonly property bool compact: height < 850
    readonly property int buttonGap: compact ? 10 : 14
    readonly property int sectionGap: compact ? 12 : 18
    signal closeRequested()
    signal accessoriesRequested()
    signal imagesRequested()
    color: "#102858"
    radius: 12

    onVisibleChanged: if (visible) {
        allNodes = false
        admin.refresh()
    }
    Connections {
        target: root.admin
        function onChanged() { root.revision++ }
    }
    Timer {
        running: root.visible
        interval: 1500
        repeat: true
        onTriggered: root.admin.refresh()
    }

    component SectionLabel: Label {
        color: "#bad4ea"
        font.bold: true
        font.pixelSize: 17
    }

    component PanelButton: FunctionButton {
        Layout.fillWidth: true
        Layout.preferredWidth: 0
        Layout.preferredHeight: 54
        font.pixelSize: 19
        wrapLabel: true
    }

    component AdminButton: PanelButton {
        required property string command
        enabled: {
            root.revision
            return root.admin.canRun(command, root.allNodes)
        }
        deferForHold: true
        holdThreshold: 3000
        onHeld: root.admin.run(command, root.allNodes)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compact ? 14 : 18
        spacing: root.buttonGap

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(adminStop.height, adminTitle.implicitHeight)

            ColumnLayout {
                id: adminTitle
                anchors.left: parent.left
                anchors.right: adminStop.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                Label {
                    Layout.fillWidth: true
                    text: "Manage PyTrain"
                    color: "#f4f6f8"
                    font.pixelSize: 26
                    font.bold: true
                    elide: Text.ElideRight
                }
                Label {
                    Layout.fillWidth: true
                    text: root.admin.version
                    color: "#bad4ea"
                    font.pixelSize: 16
                    elide: Text.ElideRight
                }
                Label {
                    visible: text.length > 0
                    Layout.fillWidth: true
                    text: root.admin.serverVersion
                    color: "#bad4ea"
                    font.pixelSize: 16
                    elide: Text.ElideRight
                }
            }
            AllStopButton {
                id: adminStop
                anchors.right: parent.right
                anchors.top: parent.top
                width: Layout.preferredWidth
                height: Layout.preferredHeight
                compact: root.compact
                onClicked: root.cab.halt()
            }
        }

        ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                width: scroll.availableWidth
                spacing: root.buttonGap

                SectionLabel {
                    visible: text.length > 0
                    text: root.admin.layoutName
                }
                Label {
                    Layout.fillWidth: true
                    text: "Local IP  " + root.admin.addresses
                    color: "#f4f6f8"
                    font.pixelSize: 16
                    wrapMode: Text.WordWrap
                }
                SectionLabel { text: "Base 3 Database"; Layout.topMargin: root.sectionGap }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.buttonGap
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: 54
                        radius: 8
                        color: "#16376b"
                        border.color: "#5275a4"
                        Label {
                            anchors.fill: parent
                            anchors.margins: 6
                            text: root.admin.databaseStatus
                            color: "#e2edf9"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.WordWrap
                            font.pixelSize: 19
                        }
                    }
                    AdminButton {
                        objectName: "reloadDatabaseButton"
                        Layout.minimumWidth: 0
                        text: "Reload Database"
                        command: "RESYNC"
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.buttonGap
                    PanelButton { text: "Reload Accessories"; onClicked: root.accessoriesRequested() }
                    PanelButton { text: "Refresh Images"; onClicked: root.imagesRequested() }
                }

                SectionLabel { text: "Logging & Debugging"; Layout.topMargin: root.sectionGap }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.buttonGap
                    PanelButton {
                        text: "Logging"
                        selected: root.admin.logging
                        onClicked: root.admin.setLogging(!selected)
                    }
                    PanelButton {
                        text: "Debugging"
                        selected: root.admin.debugging
                        enabled: root.admin.logging
                        onClicked: root.admin.setDebugging(!selected)
                    }
                }

                SectionLabel { text: "Maintenance Scope"; Layout.topMargin: root.sectionGap }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.buttonGap
                    PanelButton { text: "Local"; selected: !root.allNodes; onClicked: root.allNodes = false }
                    PanelButton { text: "All"; selected: root.allNodes; onClicked: root.allNodes = true }
                }
                SectionLabel { text: "Hold for 3 seconds"; Layout.topMargin: root.sectionGap }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: root.buttonGap
                    columnSpacing: root.buttonGap
                    AdminButton { text: "Restart"; command: "RESTART" }
                    AdminButton { text: "Reboot"; command: "REBOOT" }
                    AdminButton { text: "Update PyTrain"; command: "UPDATE" }
                    AdminButton { text: "Upgrade Pi OS"; command: "UPGRADE" }
                    AdminButton { text: "Quit"; command: "QUIT" }
                    AdminButton { text: "Shutdown"; command: "SHUTDOWN" }
                }
                Label {
                    visible: text.length > 0
                    Layout.fillWidth: true
                    text: root.admin.status
                    wrapMode: Text.WordWrap
                    color: "#f4f6f8"
                }
            }
        }
        CabButton {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 180
            Layout.preferredHeight: 52
            text: "Close"
            onClicked: root.closeRequested()
        }
    }
}
