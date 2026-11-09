import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var cab
    required property var selection
    property bool effectsVisible: false
    property string requestedDirection: ""
    readonly property string reportedDirection: cab.direction
    readonly property string targetKey: cab.scope + ":" + cab.tmccId
    readonly property string displayedDirection: requestedDirection || reportedDirection

    // A button reflects the operator's request immediately. Delayed snapshots
    // with the old direction must not undo it; fresh direction feedback wins.
    onReportedDirectionChanged: requestedDirection = ""
    onTargetKeyChanged: requestedDirection = ""

    function requestDirection(direction) {
        cab.setDirection(direction)
        requestedDirection = reportedDirection.indexOf(direction) >= 0 ? "" : direction
    }

    Connections {
        target: root.cab
        function onStateChanged() {
            if (root.requestedDirection && root.reportedDirection.indexOf(root.requestedDirection) >= 0)
                root.requestedDirection = ""
        }
    }
    readonly property bool compact: height < 850
    readonly property int gap: compact ? 6 : 8
    readonly property int tileHeight: compact ? 84 : 112
    readonly property int auxSide: compact ? 72 : 108

    function handleModelHold(action) {
        if (action.holdKind === "panel") {
            commandPanel.openFor(action.holdTarget)
        } else if (action.holdKind === "analog") {
            const index = analogMode.find(action.holdTarget)
            if (index >= 0)
                analogMode.currentIndex = index
        } else {
            cab.triggerHoldAction(action.key)
        }
    }

    component ActionTile: FunctionButton {
        required property var action
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 0
        Layout.preferredHeight: root.tileHeight
        stacked: true
        wrapLabel: true
        padding: 6
        iconSize: root.compact ? 48 : 72
        text: action.label
        iconSource: action.iconSource
        font.pixelSize: root.compact ? 14 : 18
        deferForHold: action.hold
        holdThreshold: action.holdThreshold
        repeatWhileHeld: action.repeat
        repeatInterval: action.repeatInterval > 0 ? action.repeatInterval : 250
        onClicked: root.cab.triggerAction(action.key)
        onHeld: root.handleModelHold(action)
    }

    color: "#171a1f"
    radius: 14

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compact ? 10 : 14
        spacing: root.gap

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumHeight: root.compact ? 64 : 72
            Layout.maximumHeight: root.compact ? 64 : 72
            Layout.preferredHeight: root.compact ? 64 : 72
            spacing: 8
            CabButton {
                Layout.preferredWidth: root.compact ? 88 : 120
                Layout.preferredHeight: root.compact ? 42 : 54
                text: "Reset"
                font.pixelSize: root.compact ? 15 : 18
                onClicked: cab.reset()
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Label {
                    Layout.fillWidth: true
                    text: (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : "")
                    color: "#f4f6f8"
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    font.pixelSize: root.compact ? 18 : 22
                    font.bold: true
                }
                Label {
                    Layout.fillWidth: true
                    text: cab.scope + " " + cab.tmccId
                    color: "#aeb5bf"
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: root.compact ? 12 : 14
                }
            }
            CabButton {
                Layout.preferredWidth: root.compact ? 106 : 132
                Layout.preferredHeight: root.compact ? 42 : 54
                text: "ALL STOP"
                font.pixelSize: root.compact ? 16 : 18
                font.bold: true
                normalColor: "#9d2020"
                pressedColor: "#c62d2d"
                onClicked: cab.halt()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Button {
                objectName: "driveTab"
                Layout.preferredWidth: root.compact ? 104 : 117
                Layout.preferredHeight: 40
                text: "Drive"
                checked: !root.effectsVisible
                onClicked: root.effectsVisible = false
                contentItem: Text {
                    text: parent.text
                    color: parent.checked ? "#ffffff" : "#aeb7c2"
                    font.pixelSize: 18
                    font.bold: parent.checked
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 6
                    color: parent.checked ? "#246aa0" : "#252b33"
                    border.color: parent.checked ? "#78bff0" : "#434c58"
                }
            }
            Button {
                objectName: "effectsTab"
                Layout.preferredWidth: root.compact ? 104 : 117
                Layout.preferredHeight: 40
                text: "Effects"
                checked: root.effectsVisible
                onClicked: root.effectsVisible = true
                contentItem: Text {
                    text: parent.text
                    color: parent.checked ? "#ffffff" : "#aeb7c2"
                    font.pixelSize: 18
                    font.bold: parent.checked
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 6
                    color: parent.checked ? "#246aa0" : "#252b33"
                    border.color: parent.checked ? "#78bff0" : "#434c58"
                }
            }
            Item { Layout.fillWidth: true }
        }

        Item {
            id: drivingArea
            objectName: "drivingArea"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0

            Item {
                id: operatingColumns
                objectName: "operatingColumns"
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: (drivingArea.width - root.gap) * 3 / 5

                Rectangle {
                    id: artwork
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    visible: !root.effectsVisible
                    height: visible ? (root.compact ? 64 : 120) : 0
                    radius: 8
                    color: "#e8ebef"
                    clip: true
                    Image {
                        anchors.fill: parent
                        anchors.margins: 5
                        source: cab.artworkSource
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: false
                    }
                    DragHandler {
                        target: null
                        xAxis.enabled: true
                        yAxis.enabled: false
                        onActiveChanged: {
                            if (!active && Math.abs(translation.x) >= 48 && root.selection)
                                root.selection.selectRelative(translation.x < 0 ? 1 : -1)
                        }
                    }
                }

                ScrollView {
                    id: actionScroll
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: artwork.bottom
                    anchors.topMargin: artwork.visible ? root.gap : 0
                    anchors.bottom: auxGrid.top
                    anchors.bottomMargin: root.gap
                    clip: true
                    contentWidth: availableWidth
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    ColumnLayout {
                        id: actionContent
                        width: actionScroll.availableWidth
                        spacing: root.gap
                        GridLayout {
                            visible: !root.effectsVisible
                            Layout.fillWidth: true
                            columns: 3
                            columnSpacing: root.gap
                            rowSpacing: root.gap
                            Repeater {
                                model: cab.primaryActionModel.concat(cab.quickActionModel)
                                ActionTile {
                                    required property var modelData
                                    action: modelData
                                }
                            }
                        }
                        GridLayout {
                            visible: root.effectsVisible
                            Layout.fillWidth: true
                            columns: 3
                            columnSpacing: 6
                            rowSpacing: 6
                            Repeater {
                                model: cab.moreActionModel
                                ActionTile {
                                    required property var modelData
                                    action: modelData
                                    Layout.preferredHeight: root.tileHeight
                                    iconSize: root.compact ? 44 : 72
                                    font.pixelSize: root.compact ? 13 : 18
                                }
                            }
                        }
                    }
                }

                GridLayout {
                    id: auxGrid
                    objectName: "auxiliaryGrid"
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: root.auxSide
                    y: root.effectsVisible ? parent.height - height :
                        Math.min(parent.height - height, artwork.height + (artwork.visible ? root.gap : 0) + actionContent.implicitHeight + root.gap)
                    columns: 3
                    columnSpacing: root.gap
                    Repeater {
                        model: cab.secondaryActionModel
                        Item {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: 0
                            Layout.preferredHeight: root.auxSide
                            FunctionButton {
                                objectName: "auxControl_" + modelData.key
                                anchors.centerIn: parent
                                width: Math.min(root.auxSide, parent.width)
                                height: width
                                compact: true
                                text: modelData.label.replace(" · ", "\n")
                                holdHint: modelData.holdTarget === "lights" ? "Lighting panel" :
                                          modelData.holdTarget === "more" ? "More controls" :
                                          modelData.key === "sequence" ? "Repeat sequence" : ""
                                font.pixelSize: root.compact ? 13 : 18
                                deferForHold: modelData.hold
                                holdThreshold: modelData.holdThreshold
                                repeatWhileHeld: modelData.repeat
                                repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250
                                onClicked: cab.triggerAction(modelData.key)
                                onHeld: root.handleModelHold(modelData)
                            }
                        }
                    }
                }
            }

            Rectangle {
                objectName: "drivingSliders"
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: (drivingArea.width - root.gap) * 2 / 5
                radius: 10
                color: "#20262e"
                border.color: "#394450"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: root.compact ? 6 : 10
                    Item {
                        id: speedReadoutRow
                        Layout.fillWidth: true
                        Layout.minimumHeight: root.compact ? 50 : 64
                        Layout.maximumHeight: root.compact ? 50 : 64
                        Layout.preferredHeight: root.compact ? 50 : 64
                        ColumnLayout {
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: cab.analogModes.length > 0 ? (parent.width - 6) * 3 / 4 : parent.width
                            spacing: 0
                            Label {
                                Layout.fillWidth: true
                                text: "CURRENT SPEED"
                                color: "#9aabba"
                                horizontalAlignment: Text.AlignHCenter
                                font.pixelSize: root.compact ? 10 : 15
                            }
                            Label {
                                objectName: "currentSpeedReadout"
                                Layout.fillWidth: true
                                text: cab.speed
                                color: "white"
                                horizontalAlignment: Text.AlignHCenter
                                font.pixelSize: root.compact ? 28 : 36
                                font.bold: true
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        CabButton {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.compact ? 32 : 45
                            Layout.preferredWidth: 0
                            Layout.minimumWidth: 0
                            id: reverseButton
                            objectName: "reverseDirectionButton"
                            text: "◀ REV" + (root.requestedDirection === "REVERSE" ? " …" : "")
                            font.pixelSize: root.compact ? 12 : 20
                            selected: root.displayedDirection.indexOf("REVERSE") >= 0
                            onClicked: root.requestDirection("REVERSE")
                        }
                        CabButton {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.compact ? 32 : 45
                            Layout.preferredWidth: 0
                            Layout.minimumWidth: 0
                            id: forwardButton
                            objectName: "forwardDirectionButton"
                            text: "FWD ▶" + (root.requestedDirection === "FORWARD" ? " …" : "")
                            font.pixelSize: root.compact ? 12 : 20
                            selected: root.displayedDirection.indexOf("FORWARD") >= 0
                            onClicked: root.requestDirection("FORWARD")
                        }
                    }
                    ComboBox {
                        id: analogMode
                        visible: cab.analogModes.length > 0
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compact ? 32 : 40
                        model: cab.analogModes
                        font.pixelSize: root.compact ? 11 : 18
                        leftPadding: 4
                        rightPadding: 14
                        topPadding: 0
                        bottomPadding: 0
                        indicator: Text {
                            x: analogMode.width - width - 4
                            anchors.verticalCenter: parent.verticalCenter
                            text: "▾"
                            color: "#c7d5e3"
                            font.pixelSize: 12
                        }
                        popup.width: root.compact ? 150 : 220
                        contentItem: Text {
                            leftPadding: 2
                            rightPadding: 0
                            text: root.compact && analogMode.currentText === "Momentum" ? "Mom." : analogMode.displayText
                            color: "#e9edf2"
                            font: analogMode.font
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }
                        background: Rectangle {
                            color: "#303945"
                            radius: 6
                            border.color: "#627384"
                        }
                    }
                    Item {
                        id: sliderColumns
                        objectName: "sliderColumns"
                        readonly property real laneWidth: (width - 6) / 4
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 0
                        ColumnLayout {
                            visible: cab.analogModes.length > 0
                            objectName: "variableControlLane"
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: sliderColumns.laneWidth
                            spacing: 6
                            Item {
                                Layout.minimumHeight: root.compact ? 32 : 40
                                Layout.maximumHeight: root.compact ? 32 : 40
                                Layout.preferredHeight: root.compact ? 32 : 40
                            }
                            VerticalCabControl {
                                id: analogControl
                                objectName: "variableCabControl"
                                largeTouch: !root.compact
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 80
                                maximumValue: analogMode.currentText === "Horn" ? 15 : 7
                                springReturn: analogMode.currentText === "Horn"
                                value: analogMode.currentText === "Brake" ? cab.trainBrake : analogMode.currentText === "Momentum" ? cab.momentum : 0
                                onValueMoved: function(v) {
                                    if (analogMode.currentText === "Brake") cab.setTrainBrake(v)
                                    else if (analogMode.currentText === "Horn") cab.setQuillingHorn(v)
                                }
                                onValueCommitted: function(v) {
                                    if (analogMode.currentText === "Momentum") cab.setMomentum(v)
                                    else if (analogMode.currentText === "Brake") cab.setTrainBrake(v)
                                    else if (analogMode.currentText === "Horn") cab.setQuillingHorn(v)
                                }
                            }
                            Item {
                                Layout.fillWidth: true
                                Layout.minimumHeight: root.compact ? 32 : 40
                                Layout.maximumHeight: root.compact ? 32 : 40
                                Layout.preferredHeight: root.compact ? 32 : 40
                                Label {
                                    anchors.centerIn: parent
                                    text: analogMode.currentText === "Horn" ? "0–15" : "0–7"
                                    color: "#9aabba"
                                    font.pixelSize: root.compact ? 10 : 15
                                }
                            }
                            Timer {
                                interval: 500
                                repeat: true
                                running: analogMode.currentText === "Horn" && analogControl.dragging && analogControl.pendingValue > 0
                                onTriggered: cab.setQuillingHorn(analogControl.pendingValue)
                            }
                        }
                        ColumnLayout {
                            objectName: "throttleLane"
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: cab.analogModes.length > 0 ? sliderColumns.laneWidth * 3 : sliderColumns.width
                            spacing: 6
                            CabButton {
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.compact ? 32 : 40
                                objectName: "speedStepUp"
                                text: "+"
                                font.pixelSize: root.compact ? 22 : 26
                                enabled: !cab.rampActive
                                repeatWhileHeld: true
                                onClicked: cab.stepSpeed(1)
                            }
                            VerticalThrottle {
                                id: throttle
                                objectName: "targetSpeedThrottle"
                                largeTouch: !root.compact
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 80
                                maximumValue: Math.max(1, cab.speedMax)
                                value: cab.targetSpeed
                                onValueCommitted: function(v) { cab.setSpeed(v) }
                            }
                            CabButton {
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.compact ? 32 : 40
                                objectName: "speedStepDown"
                                text: "−"
                                font.pixelSize: root.compact ? 22 : 26
                                enabled: !cab.rampActive
                                repeatWhileHeld: true
                                onClicked: cab.stepSpeed(-1)
                            }
                        }
                    }
                    CabButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compact ? 32 : 40
                        text: cab.speedLimit > 0 ? "Speed limit · " + cab.speedLimit : "Set speed limit"
                        font.pixelSize: root.compact ? 12 : 18
                        onClicked: speedLimitPopup.open()
                    }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 6
            columnSpacing: 4
            Repeater {
                model: cab.infoModel
                Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: root.compact ? 38 : 54
                    radius: 6
                    color: "#222a33"
                    Column {
                        anchors.centerIn: parent
                        spacing: 2
                        Label {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.label
                            color: "#9aabba"
                            font.pixelSize: root.compact ? 9 : 15
                        }
                        Label {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.value === "" ? "—" : modelData.value
                            color: "#f1f5f9"
                            font.pixelSize: root.compact ? 12 : 20
                            font.bold: true
                        }
                    }
                }
            }
        }
    }

    CommandPanelPopup {
        id: commandPanel
        parent: Overlay.overlay
        cab: root.cab
        width: Math.min(Overlay.overlay.width - 24, 620)
        height: Math.min(Overlay.overlay.height - 24, 760)
        x: (Overlay.overlay.width - width) / 2
        y: (Overlay.overlay.height - height) / 2
    }

    Popup {
        id: speedLimitPopup
        parent: Overlay.overlay
        modal: true
        focus: true
        anchors.centerIn: parent
        width: Math.min(Overlay.overlay.width - 36, 360)
        padding: 14
        background: Rectangle {
            color: "#22272e"
            radius: 10
            border.width: 1
            border.color: "#56606c"
        }
        ColumnLayout {
            width: parent.width
            spacing: 10
            Label {
                Layout.fillWidth: true
                text: "Speed Limit"
                color: "white"
                font.pixelSize: 18
                font.bold: true
            }
            Slider {
                id: speedLimitSlider
                Layout.fillWidth: true
                from: 0
                to: Math.max(1, cab.speedMax)
                stepSize: 1
                value: cab.speedLimit
            }
            Label {
                Layout.fillWidth: true
                text: Math.round(speedLimitSlider.value)
                color: "#dce3eb"
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 18
            }
            RowLayout {
                Layout.fillWidth: true
                CabButton {
                    Layout.fillWidth: true
                    text: "Clear"
                    onClicked: {
                        cab.clearSpeedLimit()
                        speedLimitPopup.close()
                    }
                }
                CabButton {
                    Layout.fillWidth: true
                    text: "Set"
                    normalColor: "#246aa0"
                    onClicked: {
                        cab.setSpeedLimit(Math.round(speedLimitSlider.value))
                        speedLimitPopup.close()
                    }
                }
            }
        }
    }
}
