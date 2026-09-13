import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var cab

    // One cab must fit both portrait Raspberry Pi panels and the much shorter
    // landscape Steam Deck. Width controls the number of operation columns;
    // height controls how aggressively chrome and button heights are reduced.
    readonly property bool shortLayout: height < 1000
    readonly property bool veryShortLayout: height < 850
    readonly property bool narrowLayout: width < 650
    readonly property int operationColumns: width >= 1050 ? 4 : (width >= 600 ? 3 : 2)
    readonly property int compactButtonHeight: veryShortLayout ? 36 : (shortLayout ? 40 : 44)
    readonly property int operationButtonHeight: veryShortLayout ? 38 : (shortLayout ? 42 : 46)

    color: "#171a1f"
    radius: 18

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.shortLayout ? 12 : 18
        spacing: root.shortLayout ? 6 : 9

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ComboBox {
                id: targetPicker
                Layout.fillWidth: true
                Layout.preferredHeight: root.shortLayout ? 44 : 50
                model: cab.targetLabels
                currentIndex: cab.targetIndex
                font.pixelSize: root.shortLayout ? 15 : 17
                onActivated: cab.selectTarget(currentIndex)

                contentItem: Text {
                    leftPadding: 12
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
                    background: Rectangle {
                        color: parent.highlighted ? "#246aa0" : "#292e36"
                    }
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
                    background: Rectangle {
                        color: "#20242a"
                        border.color: "#626b78"
                        radius: 8
                    }
                }
            }

            CabButton {
                Layout.preferredWidth: root.shortLayout ? 88 : 104
                Layout.preferredHeight: root.shortLayout ? 44 : 50
                text: "Refresh"
                font.pixelSize: root.shortLayout ? 14 : 16
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
                font.pixelSize: root.shortLayout ? 23 : 27
                font.bold: true
            }

            Label {
                Layout.fillWidth: true
                text: cab.scope + " " + cab.tmccId + "   " + (cab.direction || "—")
                color: "#aeb5bf"
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: root.shortLayout ? 13 : 15
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: root.shortLayout ? 54 : 64
                radius: 10
                color: "#23272e"
                Column {
                    anchors.centerIn: parent
                    spacing: -1
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: "SPEED"; color: "#9ea6b0"; font.pixelSize: root.shortLayout ? 11 : 12 }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.speed; color: "white"; font.pixelSize: root.shortLayout ? 24 : 28; font.bold: true }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: root.shortLayout ? 54 : 64
                radius: 10
                color: "#23272e"
                Column {
                    anchors.centerIn: parent
                    spacing: -1
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: "TARGET"; color: "#9ea6b0"; font.pixelSize: root.shortLayout ? 11 : 12 }
                    Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.targetSpeed; color: "white"; font.pixelSize: root.shortLayout ? 24 : 28; font.bold: true }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            CabButton {
                Layout.fillWidth: true
                Layout.preferredHeight: root.shortLayout ? 44 : 50
                text: "Reverse"
                selected: cab.direction.indexOf("REVERSE") >= 0
                onClicked: cab.setDirection("REVERSE")
            }

            CabButton {
                Layout.fillWidth: true
                Layout.preferredHeight: root.shortLayout ? 44 : 50
                text: "Forward"
                selected: cab.direction.indexOf("FORWARD") >= 0
                onClicked: cab.setDirection("FORWARD")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: root.shortLayout ? 10 : 14

            ColumnLayout {
                Layout.preferredWidth: root.narrowLayout ? 112 : (root.shortLayout ? 135 : 155)
                Layout.fillHeight: true
                spacing: 2

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "THROTTLE  " + cab.speedMax
                    color: "#b9c0c9"
                    font.pixelSize: root.shortLayout ? 12 : 14
                }

                VerticalThrottle {
                    id: throttle
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillHeight: true
                    Layout.preferredWidth: root.narrowLayout ? 105 : (root.shortLayout ? 125 : 145)
                    minimumValue: 0
                    maximumValue: Math.max(1, cab.speedMax)
                    value: cab.targetSpeed
                    onValueCommitted: function(v) { cab.setSpeed(v) }
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "0"
                    color: "#b9c0c9"
                    font.pixelSize: root.shortLayout ? 12 : 14
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: root.shortLayout ? 4 : 6

                // Driving controls stay one-touch but consume only two rows.
                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: 5
                    rowSpacing: 5

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compactButtonHeight
                        text: "−5"
                        font.pixelSize: root.shortLayout ? 13 : 15
                        onClicked: cab.changeSpeed(-5)
                    }
                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compactButtonHeight
                        text: "+5"
                        font.pixelSize: root.shortLayout ? 13 : 15
                        onClicked: cab.changeSpeed(5)
                    }
                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compactButtonHeight
                        text: "Bell"
                        font.pixelSize: root.shortLayout ? 13 : 15
                        onClicked: cab.bell()
                    }
                    HoldActionButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compactButtonHeight
                        text: "Horn"
                        font.pixelSize: root.shortLayout ? 13 : 15
                        repeatWhileHeld: true
                        repeatInterval: 100
                        onHeldAction: cab.horn(true)
                    }
                    HoldActionButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compactButtonHeight
                        text: "Brake"
                        font.pixelSize: root.shortLayout ? 13 : 15
                        repeatWhileHeld: true
                        repeatInterval: 250
                        onHeldAction: cab.brake(true)
                    }
                    HoldActionButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compactButtonHeight
                        text: "Boost"
                        font.pixelSize: root.shortLayout ? 13 : 15
                        repeatWhileHeld: true
                        repeatInterval: 250
                        onHeldAction: cab.boost(true)
                    }
                }

                Label {
                    Layout.fillWidth: true
                    text: "OPERATIONS"
                    color: "#9ea6b0"
                    font.pixelSize: root.shortLayout ? 11 : 12
                    font.bold: true
                    leftPadding: 2
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: root.operationColumns
                    columnSpacing: 5
                    rowSpacing: 4

                    Repeater {
                        model: cab.actionModel
                        FunctionButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.operationButtonHeight
                            compact: true
                            text: modelData.label
                            iconSource: modelData.iconSource
                            onClicked: cab.triggerAction(modelData.key)
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: 5
                    rowSpacing: 4
                    visible: cab.secondaryActionModel.length > 0

                    Repeater {
                        model: cab.secondaryActionModel
                        CabButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.veryShortLayout ? 32 : 36
                            text: modelData.label
                            font.pixelSize: root.shortLayout ? 11 : 12
                            onClicked: cab.triggerAction(modelData.key)
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 4
                    columnSpacing: 5
                    rowSpacing: 4
                    visible: cab.tuningActionModel.length > 0

                    Repeater {
                        model: cab.tuningActionModel
                        CabButton {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.veryShortLayout ? 32 : 36
                            text: modelData.label
                            font.pixelSize: 11
                            onClicked: cab.triggerAction(modelData.key)
                        }
                    }

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.veryShortLayout ? 32 : 36
                        text: cab.speedLimit > 0 ? "Limit " + cab.speedLimit : "Limit"
                        font.pixelSize: 11
                        onClicked: speedLimitPopup.open()
                    }
                }

                // Artwork is a first-class control surface: never intentionally collapse it.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: root.veryShortLayout ? 80 : (root.shortLayout ? 95 : 120)
                    Layout.preferredHeight: root.shortLayout ? 110 : 145
                    radius: 10
                    color: "#e8ebef"
                    border.width: 1
                    border.color: cab.hasCustomArtwork ? "#3c8dbc" : "#aeb5bf"
                    clip: true

                    Image {
                        anchors.fill: parent
                        anchors.margins: 6
                        source: cab.artworkSource
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: false
                    }

                    Label {
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.margins: 6
                        visible: cab.hasCustomArtwork
                        text: "CUSTOM"
                        color: "#176fa8"
                        font.pixelSize: 10
                        font.bold: true
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.shortLayout ? 46 : 56
                        text: "STOP"
                        font.pixelSize: root.shortLayout ? 18 : 21
                        font.bold: true
                        normalColor: "#8b2d32"
                        pressedColor: "#b43b42"
                        onClicked: cab.stop()
                    }

                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.shortLayout ? 46 : 56
                        text: "Reset"
                        onClicked: cab.reset()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.shortLayout ? 38 : 46
            radius: 8
            color: "#23272e"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10

                Label { text: "RPM " + cab.rpm; color: "#d9dde3"; font.pixelSize: root.shortLayout ? 12 : 14 }
                Item { Layout.fillWidth: true }
                Label { text: "Labor " + cab.labor; color: "#d9dde3"; font.pixelSize: root.shortLayout ? 12 : 14 }
                Item { Layout.fillWidth: true }
                Label { text: "Momentum " + cab.momentum; color: "#d9dde3"; font.pixelSize: root.shortLayout ? 12 : 14 }
                Item { Layout.fillWidth: true }
                Label { text: "Smoke " + cab.smoke; color: "#d9dde3"; font.pixelSize: root.shortLayout ? 12 : 14 }
            }
        }
    }

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

        background: Rectangle {
            radius: 12
            color: "#252a31"
            border.width: 1
            border.color: "#697382"
        }

        contentItem: ColumnLayout {
            spacing: 14

            Label {
                Layout.fillWidth: true
                text: "Speed Limit"
                color: "white"
                font.pixelSize: 22
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
            }

            Label {
                Layout.fillWidth: true
                text: cab.speedLimit > 0 ? "Current limit: " + cab.speedLimit : "No speed limit set"
                color: "#c8ced6"
                font.pixelSize: 15
                horizontalAlignment: Text.AlignHCenter
            }

            SpinBox {
                id: limitSpin
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 180
                from: 1
                to: cab.commandSpeedMax
                editable: true
                font.pixelSize: 20
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                CabButton {
                    Layout.fillWidth: true
                    text: "Clear"
                    enabled: cab.speedLimit > 0
                    onClicked: {
                        cab.clearSpeedLimit()
                        speedLimitPopup.close()
                    }
                }

                CabButton {
                    Layout.fillWidth: true
                    text: "Set"
                    selected: true
                    onClicked: {
                        cab.setSpeedLimit(limitSpin.value)
                        speedLimitPopup.close()
                    }
                }
            }
        }
    }
}
