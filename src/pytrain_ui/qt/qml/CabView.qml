import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var cab
    property bool moreControlsVisible: false

    readonly property bool piLayout: width <= 720
    readonly property bool shortLayout: height < 1000
    readonly property bool veryShortLayout: height < 850
    readonly property bool narrowLayout: width < 650
    readonly property int controlHeaderHeight: piLayout ? 36 : 32
    readonly property int controlFooterHeight: 20

    function isQuickAction(key) {
        return key === "rear_coupler" || key === "front_coupler" ||
               key === "engineer_chatter" || key === "tower_chatter" ||
               key === "conductor" || key === "station" || key === "steward"
    }

    function handleModelHold(modelData) {
        if (modelData.holdKind === "panel") {
            commandPanel.openFor(modelData.holdTarget)
        } else if (modelData.holdKind === "analog") {
            const index = analogMode.find(modelData.holdTarget)
            if (index >= 0)
                analogMode.currentIndex = index
        } else {
            cab.triggerHoldAction(modelData.key)
        }
    }

    color: "#171a1f"
    radius: root.piLayout ? 14 : 18

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.piLayout ? 10 : (root.shortLayout ? 12 : 18)
        spacing: root.piLayout ? 5 : (root.shortLayout ? 6 : 9)

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            ComboBox {
                id: targetPicker
                Layout.fillWidth: true
                Layout.preferredHeight: root.piLayout ? 40 : 50
                model: cab.targetLabels
                currentIndex: cab.targetIndex
                font.pixelSize: root.piLayout ? 14 : 17
                onActivated: cab.selectTarget(currentIndex)
                contentItem: Text {
                    leftPadding: 10
                    rightPadding: 30
                    text: targetPicker.displayText
                    font: targetPicker.font
                    color: "#ffffff"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: 8
                    color: "#292e36"
                    border.width: 1
                    border.color: targetPicker.activeFocus ? "#78bff0" : "#626b78"
                }
                delegate: ItemDelegate {
                    required property int index
                    required property var modelData
                    width: targetPicker.width
                    height: 42
                    text: modelData
                    font.pixelSize: 15
                    highlighted: targetPicker.highlightedIndex === index
                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: "#ffffff"
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    background: Rectangle { color: parent.highlighted ? "#246aa0" : "#292e36" }
                }
                popup: Popup {
                    y: targetPicker.height
                    width: targetPicker.width
                    implicitHeight: Math.min(contentItem.implicitHeight, 420)
                    padding: 1
                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: targetPicker.popup.visible ? targetPicker.delegateModel : null
                        currentIndex: targetPicker.highlightedIndex
                        ScrollIndicator.vertical: ScrollIndicator { }
                    }
                    background: Rectangle { color: "#20242a"; border.color: "#626b78"; radius: 8 }
                }
            }
            CabButton {
                Layout.preferredWidth: root.piLayout ? 92 : 104
                Layout.preferredHeight: root.piLayout ? 40 : 50
                text: "Refresh"
                font.pixelSize: root.piLayout ? 14 : 16
                onClicked: cab.refreshRoster()
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Label {
                Layout.fillWidth: true
                text: (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : "")
                color: "#f4f6f8"
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                font.pixelSize: root.piLayout ? 22 : 27
                font.bold: true
            }
            Label {
                Layout.fillWidth: true
                text: cab.scope + " " + cab.tmccId + "   " + (cab.direction || "—")
                color: "#aeb5bf"
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: root.piLayout ? 12 : 15
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: root.piLayout ? 48 : 64
                radius: 9
                color: "#23272e"
                Column {
                    anchors.centerIn: parent
                    spacing: -1
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: "SPEED"; color: "#9ea6b0"; font.pixelSize: root.piLayout ? 10 : 12 }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.speed; color: "white"; font.pixelSize: root.piLayout ? 22 : 28; font.bold: true }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: root.piLayout ? 48 : 64
                radius: 9
                color: "#23272e"
                Column {
                    anchors.centerIn: parent
                    spacing: -1
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: "TARGET"; color: "#9ea6b0"; font.pixelSize: root.piLayout ? 10 : 12 }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.targetSpeed; color: "white"; font.pixelSize: root.piLayout ? 22 : 28; font.bold: true }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            CabButton { Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 44 : 50; text: "Reverse"; font.pixelSize: root.piLayout ? 16 : 20; selected: cab.direction.indexOf("REVERSE") >= 0; onClicked: cab.setDirection("REVERSE") }
            CabButton { Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 44 : 50; text: "Forward"; font.pixelSize: root.piLayout ? 16 : 20; selected: cab.direction.indexOf("FORWARD") >= 0; onClicked: cab.setDirection("FORWARD") }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: root.piLayout ? 7 : 12
            layoutDirection: Qt.RightToLeft

            RowLayout {
                Layout.preferredWidth: root.piLayout ? 184 : 225
                Layout.fillHeight: true
                spacing: 4
                layoutDirection: Qt.LeftToRight

                ColumnLayout {
                    Layout.preferredWidth: root.piLayout ? 82 : 78
                    Layout.fillHeight: true
                    spacing: 2
                    visible: cab.analogModes.length > 0
                    ComboBox {
                        id: analogMode
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.controlHeaderHeight
                        Layout.maximumHeight: root.controlHeaderHeight
                        model: cab.analogModes
                        font.pixelSize: root.piLayout ? 10 : 11
                        contentItem: Text {
                            leftPadding: 5
                            rightPadding: 18
                            text: analogMode.displayText
                            font: analogMode.font
                            color: "#e9edf2"
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                        }
                        background: Rectangle { radius: 6; color: "#292e36"; border.width: 1; border.color: "#626b78" }
                    }
                    VerticalCabControl {
                        id: analogControl
                        Layout.fillHeight: true
                        Layout.fillWidth: true
                        minimumValue: 0
                        maximumValue: analogMode.currentText === "Horn" ? 15 : 7
                        springReturn: analogMode.currentText === "Horn"
                        value: analogMode.currentText === "Brake" ? cab.trainBrake : analogMode.currentText === "Momentum" ? cab.momentum : 0
                        onValueMoved: function(v) { if (analogMode.currentText === "Brake") cab.setTrainBrake(v); else if (analogMode.currentText === "Horn") cab.setQuillingHorn(v) }
                        onValueCommitted: function(v) { if (analogMode.currentText === "Momentum") cab.setMomentum(v); else if (analogMode.currentText === "Brake") cab.setTrainBrake(v); else if (analogMode.currentText === "Horn") cab.setQuillingHorn(v) }
                    }
                    Label { Layout.fillWidth: true; Layout.preferredHeight: root.controlFooterHeight; text: analogMode.currentText === "Horn" ? "0–15" : "0–7"; color: "#b9c0c9"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 9 }
                    Timer { interval: 500; repeat: true; running: analogMode.currentText === "Horn" && analogControl.dragging && analogControl.pendingValue > 0; onTriggered: cab.setQuillingHorn(analogControl.pendingValue) }
                }

                ColumnLayout {
                    Layout.preferredWidth: root.piLayout ? 98 : 140
                    Layout.fillHeight: true
                    spacing: 2
                    Label { Layout.fillWidth: true; Layout.preferredHeight: root.controlHeaderHeight; text: "THROTTLE  " + cab.speedMax; color: "#b9c0c9"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: root.piLayout ? 10 : 14 }
                    VerticalThrottle { id: throttle; Layout.fillHeight: true; Layout.fillWidth: true; minimumValue: 0; maximumValue: Math.max(1, cab.speedMax); value: cab.targetSpeed; onValueCommitted: function(v) { cab.setSpeed(v) } }
                    Label { Layout.fillWidth: true; Layout.preferredHeight: root.controlFooterHeight; text: "0"; color: "#b9c0c9"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 10 }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: root.piLayout ? 6 : 8

                Label {
                    Layout.fillWidth: true
                    text: "DRIVE & EFFECTS"
                    color: "#9ea6b0"
                    font.pixelSize: 10
                    font.bold: true
                    leftPadding: 2
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 6
                    rowSpacing: 6
                    Repeater {
                        model: cab.primaryActionModel
                        FunctionButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.piLayout ? 58 : 52
                            compact: true
                            text: modelData.label
                            font.pixelSize: root.piLayout ? 16 : 15
                            font.bold: modelData.key === "brake" || modelData.key === "boost"
                            deferForHold: modelData.hold
                            holdThreshold: modelData.holdThreshold
                            repeatWhileHeld: modelData.repeat
                            repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250
                            onClicked: cab.triggerAction(modelData.key)
                            onHeld: root.handleModelHold(modelData)
                        }
                    }
                }

                Label {
                    Layout.fillWidth: true
                    text: "QUICK ACTIONS"
                    color: "#9ea6b0"
                    font.pixelSize: 10
                    font.bold: true
                    leftPadding: 2
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 6
                    rowSpacing: 6
                    Repeater {
                        model: cab.actionModel
                        FunctionButton {
                            required property var modelData
                            visible: root.isQuickAction(modelData.key)
                            Layout.fillWidth: visible
                            Layout.preferredHeight: visible ? (root.piLayout ? 48 : 46) : 0
                            compact: true
                            text: modelData.label
                            iconSource: modelData.iconSource
                            font.pixelSize: root.piLayout ? 13 : 14
                            deferForHold: modelData.hold
                            holdThreshold: modelData.holdThreshold
                            repeatWhileHeld: modelData.repeat
                            repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250
                            onClicked: cab.triggerAction(modelData.key)
                            onHeld: root.handleModelHold(modelData)
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 4
                    columnSpacing: 5
                    rowSpacing: 4
                    Repeater {
                        model: cab.secondaryActionModel
                        FunctionButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.piLayout ? 38 : 36
                            compact: true
                            text: modelData.label
                            font.pixelSize: root.piLayout ? 11 : 10
                            deferForHold: modelData.hold
                            holdThreshold: modelData.holdThreshold
                            repeatWhileHeld: modelData.repeat
                            repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250
                            onClicked: cab.triggerAction(modelData.key)
                            onHeld: root.handleModelHold(modelData)
                        }
                    }
                    CabButton { Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 38 : 36; text: cab.speedLimit > 0 ? "Limit " + cab.speedLimit : "Limit"; font.pixelSize: 11; onClicked: speedLimitPopup.open() }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.round(width / 3)
                    Layout.maximumHeight: Math.round(width / 3)
                    radius: 9
                    color: "#e8ebef"
                    border.width: 1
                    border.color: cab.hasCustomArtwork ? "#3c8dbc" : "#aeb5bf"
                    clip: true
                    Image { anchors.fill: parent; anchors.margins: 4; source: cab.artworkSource; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false }
                    Label { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 6; visible: cab.hasCustomArtwork; text: "CUSTOM"; color: "#176fa8"; font.pixelSize: 10; font.bold: true }
                }

                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.piLayout ? 44 : 42
                    text: root.moreControlsVisible ? "Less Controls  ▲" : "More Controls  ▼"
                    font.pixelSize: root.piLayout ? 13 : 14
                    selected: root.moreControlsVisible
                    onClicked: root.moreControlsVisible = !root.moreControlsVisible
                }

                GridLayout {
                    Layout.fillWidth: true
                    visible: root.moreControlsVisible
                    columns: 3
                    columnSpacing: 5
                    rowSpacing: 5
                    Repeater {
                        model: cab.actionModel
                        FunctionButton {
                            required property var modelData
                            visible: !root.isQuickAction(modelData.key)
                            Layout.fillWidth: visible
                            Layout.preferredHeight: visible ? (root.piLayout ? 44 : 42) : 0
                            compact: true
                            text: modelData.label
                            iconSource: modelData.iconSource
                            font.pixelSize: root.piLayout ? 11 : 12
                            deferForHold: modelData.hold
                            holdThreshold: modelData.holdThreshold
                            repeatWhileHeld: modelData.repeat
                            repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250
                            onClicked: cab.triggerAction(modelData.key)
                            onHeld: root.handleModelHold(modelData)
                        }
                    }
                    Repeater {
                        model: cab.tuningActionModel
                        FunctionButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.piLayout ? 44 : 42
                            compact: true
                            text: modelData.label
                            font.pixelSize: root.piLayout ? 11 : 12
                            onClicked: cab.triggerAction(modelData.key)
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 7
                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.piLayout ? 60 : 58
                        text: "HALT"
                        font.pixelSize: root.piLayout ? 20 : 21
                        font.bold: true
                        normalColor: "#8b2d32"
                        pressedColor: "#b43b42"
                        onClicked: cab.stop()
                    }
                    CabButton {
                        Layout.preferredWidth: root.piLayout ? 150 : 180
                        Layout.preferredHeight: root.piLayout ? 60 : 58
                        text: "Reset"
                        font.pixelSize: root.piLayout ? 16 : 18
                        repeatWhileHeld: true
                        repeatInterval: 100
                        onClicked: cab.reset()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.piLayout ? 44 : 50
            radius: 8
            color: "#23272e"
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                spacing: 4
                Repeater {
                    model: cab.infoModel
                    ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        spacing: -2
                        Label { Layout.fillWidth: true; text: modelData.label === "Speed Lim" ? "Speed\nLimit" : modelData.label; color: "#9ea6b0"; horizontalAlignment: Text.AlignHCenter; lineHeight: 0.85; font.pixelSize: root.piLayout ? 9 : 10 }
                        Label { Layout.fillWidth: true; text: modelData.value; color: "#d9dde3"; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; font.pixelSize: root.piLayout ? 11 : 13 }
                    }
                }
            }
        }
    }

    CommandPanelPopup { id: commandPanel; cab: root.cab }

    Popup {
        id: speedLimitPopup
        x: Math.round((root.width - width) / 2)
        y: Math.round((root.height - height) / 2)
        width: Math.min(440, root.width - 48)
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: 18
        onOpened: limitSpin.value = cab.speedLimit > 0 ? cab.speedLimit : Math.max(1, cab.targetSpeed)
        background: Rectangle { radius: 12; color: "#252a31"; border.width: 1; border.color: "#697382" }
        contentItem: ColumnLayout {
            spacing: 14
            Label { Layout.fillWidth: true; text: "Speed Limit"; color: "white"; font.pixelSize: 22; font.bold: true; horizontalAlignment: Text.AlignHCenter }
            Label { Layout.fillWidth: true; text: cab.speedLimit > 0 ? "Current limit: " + cab.speedLimit : "No speed limit set"; color: "#c8ced6"; font.pixelSize: 15; horizontalAlignment: Text.AlignHCenter }
            SpinBox { id: limitSpin; Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: 180; from: 1; to: cab.commandSpeedMax; editable: true; font.pixelSize: 20 }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CabButton { Layout.fillWidth: true; text: "Clear"; enabled: cab.speedLimit > 0; onClicked: { cab.clearSpeedLimit(); speedLimitPopup.close() } }
                CabButton { Layout.fillWidth: true; text: "Set"; selected: true; onClicked: { cab.setSpeedLimit(limitSpin.value); speedLimitPopup.close() } }
            }
        }
    }
}
