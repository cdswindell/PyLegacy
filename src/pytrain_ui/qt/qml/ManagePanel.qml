import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    PanelMetrics { id: metrics }
    required property var admin
    required property var cab
    property bool allNodes: false
    property int revision: 0
    readonly property bool compact: height < 850
    readonly property int buttonGap: compact ? 16 : 22
    readonly property int buttonHeight: compact ? 64 : 68
    property string refreshStatus: ""
    readonly property int sectionGap: compact ? 7 : 11
    signal closeRequested()
    signal accessoriesRequested()
    signal imagesRequested()
    color: "#102858"
    radius: 12

    onVisibleChanged: {
        if (visible) {
            allNodes = false
            admin.refresh()
        } else {
            refreshStatus = ""
            refreshStatusTimer.stop()
        }
    }

    function showRefreshStatus(message) {
        refreshStatus = message
        refreshStatusTimer.restart()
    }

    Timer {
        id: refreshStatusTimer
        interval: 2400
        onTriggered: root.refreshStatus = ""
    }
    Connections {
        target: root.admin
        function onChanged() { root.revision++ }
    }
    Timer {
        running: root.visible
        interval: 500
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
        Layout.preferredHeight: root.buttonHeight
        steelFace: true
        font.pixelSize: 20
        font.bold: true
        fitLabelWidth: true
    }

    component SelectionButton: PanelButton {
        id: selectionButton
        property bool radio: false
        Accessible.role: radio ? Accessible.RadioButton : Accessible.CheckBox
        Accessible.name: text
        Accessible.checkable: true
        Accessible.checked: selected

        contentItem: Item {
            Row {
                anchors.centerIn: parent
                spacing: 10

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 20
                    height: 20
                    radius: selectionButton.radio ? width / 2 : 3
                    color: "transparent"
                    border.color: selectionButton.enabled ? "#ffffff" : "#858c96"
                    border.width: 2

                    Rectangle {
                        visible: selectionButton.radio && selectionButton.selected
                        anchors.centerIn: parent
                        width: 10
                        height: 10
                        radius: width / 2
                        color: parent.border.color
                    }
                    Text {
                        visible: !selectionButton.radio && selectionButton.selected
                        anchors.centerIn: parent
                        text: "✓"
                        color: parent.border.color
                        font.pixelSize: 17
                        font.bold: true
                    }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: selectionButton.text
                    color: selectionButton.enabled ? "#ffffff" : "#858c96"
                    font: selectionButton.font
                }
            }
        }
    }

    component AdminButton: PanelButton {
        required property string command
        enabled: {
            root.revision
            return root.admin.canRun(command, root.allNodes)
        }
        deferForHold: true
        holdThreshold: 3000
        holdWarningFraction: 5 / 6
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
                SectionLabel {
                    visible: text.length > 0
                    Layout.fillWidth: true
                    text: root.admin.layoutName
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
                x: Math.min(18, scroll.availableWidth * 0.03)
                width: scroll.availableWidth - 2 * x
                spacing: root.compact ? 8 : 10

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
                        Layout.preferredHeight: root.buttonHeight
                        radius: 8
                        color: "#16376b"
                        border.color: "#5275a4"
                        Label {
                            id: databaseStatus
                            anchors.fill: parent
                            anchors.margins: 6
                            text: root.admin.databaseStatus

                            SequentialAnimation on opacity {
                                running: databaseStatus.visible && root.admin.databaseLoading
                                loops: Animation.Infinite
                                NumberAnimation { from: 1; to: 0.35; duration: 350 }
                                NumberAnimation { from: 0.35; to: 1; duration: 350 }
                                onStopped: databaseStatus.opacity = 1
                            }

                            color: "#e2edf9"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.WordWrap
                            font.pixelSize: 19
                        }
                    }
                    AdminButton {
                        objectName: "reloadDatabaseButton"
                        holdThreshold: 1000
                        holdWarningFraction: 1
                        Layout.minimumWidth: 0
                        text: "Reload Database"
                        command: "RESYNC"
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.buttonGap
                    PanelButton {
                        text: "Reload Accessories"
                        onClicked: {
                            root.showRefreshStatus("Reloading accessories…")
                            root.accessoriesRequested()
                        }
                    }
                    PanelButton {
                        text: "Refresh Images"
                        onClicked: {
                            root.showRefreshStatus("Refreshing images…")
                            root.imagesRequested()
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: root.sectionGap
                    SectionLabel { text: "Logging & Debugging" }
                    Label {
                        Layout.fillWidth: true
                        text: root.refreshStatus
                        color: "#bad4ea"
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.buttonGap
                    SelectionButton {
                        text: "Logging"
                        selected: root.admin.logging
                        onClicked: root.admin.setLogging(!selected)
                    }
                    SelectionButton {
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
                    SelectionButton { text: "Local"; radio: true; selected: !root.allNodes; onClicked: root.allNodes = false }
                    SelectionButton { text: "All"; radio: true; selected: root.allNodes; onClicked: root.allNodes = true }
                }
                SectionLabel { text: "Hold for 3 Seconds"; Layout.topMargin: root.sectionGap }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: root.compact ? 10 : 12
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
        PanelButton {
            Layout.topMargin: metrics.footerGap
            Layout.fillWidth: false
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 180
            text: "Close"
            onClicked: root.closeRequested()
        }
    }
}
