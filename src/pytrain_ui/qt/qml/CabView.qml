import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property var cab
    required property var selection
    property bool moreControlsVisible: false

    readonly property bool piLayout: width <= 720
    readonly property bool shortLayout: height < 1000
    readonly property bool veryShortLayout: height < 850
    readonly property bool narrowLayout: width < 650
    readonly property int controlHeaderHeight: piLayout ? 34 : 32
    readonly property int controlFooterHeight: 20
    readonly property int piControlHeight: 520

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

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Label { Layout.fillWidth: true; text: (cab.roadName || "PyTrain") + (cab.roadNumber ? "  " + cab.roadNumber : ""); color: "#f4f6f8"; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; font.pixelSize: root.piLayout ? 22 : 27; font.bold: true }
            Label { Layout.fillWidth: true; text: cab.scope + " " + cab.tmccId + "   " + (cab.direction || "—"); color: "#aeb5bf"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: root.piLayout ? 12 : 15 }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 48 : 64; radius: 9; color: "#23272e"
                Column { anchors.centerIn: parent; spacing: -1; Label { anchors.horizontalCenter: parent.horizontalCenter; text: "SPEED"; color: "#9ea6b0"; font.pixelSize: root.piLayout ? 10 : 12 }; Label { anchors.horizontalCenter: parent.horizontalCenter; text: cab.speed; color: "white"; font.pixelSize: root.piLayout ? 22 : 28; font.bold: true } }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 48 : 64; radius: 9; color: "#23272e"
                Column { anchors.centerIn: parent; spacing: -1; Label { anchors.horizontalCenter: parent.horizontalCenter; text: "TARGET"; color: "#9ea6b0"; font.pixelSize: root.piLayout ? 10 : 12 }; Label { anchors.horizontalCenter: parent.horizontalCenter; text: throttle.dragging ? throttle.pendingValue : cab.targetSpeed; color: "white"; font.pixelSize: root.piLayout ? 22 : 28; font.bold: true } }
            }
        }

        RowLayout {
            Layout.fillWidth: true; spacing: 6
            CabButton { Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 44 : 50; text: "Reverse"; font.pixelSize: root.piLayout ? 16 : 20; selected: cab.direction.indexOf("REVERSE") >= 0; onClicked: cab.setDirection("REVERSE") }
            CabButton { Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 44 : 50; text: "Forward"; font.pixelSize: root.piLayout ? 16 : 20; selected: cab.direction.indexOf("FORWARD") >= 0; onClicked: cab.setDirection("FORWARD") }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: root.piLayout ? 7 : 12; layoutDirection: Qt.RightToLeft
            RowLayout {
                Layout.preferredWidth: root.piLayout ? 158 : 225; Layout.preferredHeight: root.piLayout ? root.piControlHeight : -1; Layout.maximumHeight: root.piLayout ? root.piControlHeight : 16777215; Layout.alignment: Qt.AlignTop; Layout.topMargin: root.piLayout ? 18 : 20; Layout.fillHeight: !root.piLayout; spacing: 2; layoutDirection: Qt.LeftToRight
                ColumnLayout {
                    Layout.preferredWidth: root.piLayout ? 70 : 78; Layout.fillHeight: true; spacing: 2; visible: cab.analogModes.length > 0
                    ComboBox { id: analogMode; Layout.fillWidth: true; Layout.preferredHeight: root.controlHeaderHeight; Layout.maximumHeight: root.controlHeaderHeight; model: cab.analogModes; font.pixelSize: root.piLayout ? 10 : 11; contentItem: Text { leftPadding: 4; rightPadding: 16; text: analogMode.displayText; font: analogMode.font; color: "#e9edf2"; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight }; background: Rectangle { radius: 6; color: "#292e36"; border.width: 1; border.color: "#626b78" } }
                    VerticalCabControl { id: analogControl; Layout.fillHeight: true; Layout.fillWidth: true; minimumValue: 0; maximumValue: analogMode.currentText === "Horn" ? 15 : 7; springReturn: analogMode.currentText === "Horn"; value: analogMode.currentText === "Brake" ? cab.trainBrake : analogMode.currentText === "Momentum" ? cab.momentum : 0; onValueMoved: function(v) { if (analogMode.currentText === "Brake") cab.setTrainBrake(v); else if (analogMode.currentText === "Horn") cab.setQuillingHorn(v) }; onValueCommitted: function(v) { if (analogMode.currentText === "Momentum") cab.setMomentum(v); else if (analogMode.currentText === "Brake") cab.setTrainBrake(v); else if (analogMode.currentText === "Horn") cab.setQuillingHorn(v) } }
                    Label { Layout.fillWidth: true; Layout.preferredHeight: root.controlFooterHeight; text: analogMode.currentText === "Horn" ? "0–15" : "0–7"; color: "#b9c0c9"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 9 }
                    Timer { interval: 500; repeat: true; running: analogMode.currentText === "Horn" && analogControl.dragging && analogControl.pendingValue > 0; onTriggered: cab.setQuillingHorn(analogControl.pendingValue) }
                }
                ColumnLayout {
                    Layout.preferredWidth: root.piLayout ? 86 : 140; Layout.fillHeight: true; spacing: 2
                    Label { Layout.fillWidth: true; Layout.preferredHeight: root.controlHeaderHeight; text: "THROTTLE " + cab.speedMax; color: "#b9c0c9"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: root.piLayout ? 10 : 14 }
                    VerticalThrottle { id: throttle; Layout.fillHeight: true; Layout.fillWidth: true; minimumValue: 0; maximumValue: Math.max(1, cab.speedMax); value: cab.speed; onValueCommitted: function(v) { cab.setSpeed(v) } }
                    Label { Layout.fillWidth: true; Layout.preferredHeight: root.controlFooterHeight; text: "0"; color: "#b9c0c9"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 10 }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: root.piLayout ? 6 : 8
                Label { Layout.fillWidth: true; text: "DRIVE & EFFECTS"; color: "#9ea6b0"; font.pixelSize: 10; font.bold: true; leftPadding: 2 }
                GridLayout { Layout.fillWidth: true; columns: 2; columnSpacing: 6; rowSpacing: 6; Repeater { model: cab.primaryActionModel; FunctionButton { required property var modelData; Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 58 : 52; compact: true; text: modelData.label; iconSource: modelData.iconSource; font.pixelSize: root.piLayout ? 16 : 15; font.bold: modelData.key === "brake" || modelData.key === "boost"; deferForHold: modelData.hold; holdThreshold: modelData.holdThreshold; repeatWhileHeld: modelData.repeat; repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250; onClicked: cab.triggerAction(modelData.key); onHeld: root.handleModelHold(modelData) } } }
                Label { Layout.fillWidth: true; text: "QUICK ACTIONS"; color: "#9ea6b0"; font.pixelSize: 10; font.bold: true; leftPadding: 2 }
                GridLayout { Layout.fillWidth: true; columns: 2; columnSpacing: 6; rowSpacing: 6; Repeater { model: cab.actionModel; FunctionButton { required property var modelData; visible: root.isQuickAction(modelData.key); Layout.fillWidth: visible; Layout.preferredHeight: visible ? (root.piLayout ? 54 : 50) : 0; compact: true; text: modelData.label; iconSource: modelData.iconSource; font.pixelSize: root.piLayout ? 13 : 14; deferForHold: modelData.hold; holdThreshold: modelData.holdThreshold; repeatWhileHeld: modelData.repeat; repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250; onClicked: cab.triggerAction(modelData.key); onHeld: root.handleModelHold(modelData) } } }
                GridLayout { Layout.fillWidth: true; columns: 4; columnSpacing: 5; rowSpacing: 4; Repeater { model: cab.secondaryActionModel; FunctionButton { required property var modelData; Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 38 : 36; compact: true; text: modelData.label; font.pixelSize: root.piLayout ? 11 : 10; deferForHold: modelData.hold; holdThreshold: modelData.holdThreshold; repeatWhileHeld: modelData.repeat; repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250; onClicked: cab.triggerAction(modelData.key); onHeld: root.handleModelHold(modelData) } }; CabButton { Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 38 : 36; text: cab.speedLimit > 0 ? "Limit " + cab.speedLimit : "Limit"; font.pixelSize: 11; onClicked: speedLimitPopup.open() } }
                Rectangle { id: artwork; Layout.fillWidth: true; Layout.preferredHeight: Math.round(width / 3); Layout.maximumHeight: Math.round(width / 3); radius: 9; color: "#e8ebef"; border.width: 1; border.color: cab.hasCustomArtwork ? "#3c8dbc" : "#aeb5bf"; clip: true; Image { anchors.fill: parent; anchors.margins: 4; source: cab.artworkSource; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false }; Label { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 6; visible: cab.hasCustomArtwork; text: "CUSTOM"; color: "#176fa8"; font.pixelSize: 10; font.bold: true }; DragHandler { id: artworkSwipe; target: null; xAxis.enabled: true; yAxis.enabled: false; onActiveChanged: { if (!active && Math.abs(translation.x) >= 48 && root.selection) root.selection.selectRelative(translation.x < 0 ? 1 : -1) } } }
                CabButton { Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 44 : 42; text: root.moreControlsVisible ? "Less Controls  ▲" : "More Controls  ▼"; font.pixelSize: root.piLayout ? 13 : 14; onClicked: root.moreControlsVisible = !root.moreControlsVisible }
                GridLayout { visible: root.moreControlsVisible; Layout.fillWidth: true; columns: 4; columnSpacing: 5; rowSpacing: 5; Repeater { model: cab.moreActionModel; FunctionButton { required property var modelData; Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 38 : 36; compact: true; text: modelData.label; font.pixelSize: 10; deferForHold: modelData.hold; holdThreshold: modelData.holdThreshold; repeatWhileHeld: modelData.repeat; repeatInterval: modelData.repeatInterval > 0 ? modelData.repeatInterval : 250; onClicked: cab.triggerAction(modelData.key); onHeld: root.handleModelHold(modelData) } } }
                Item { Layout.fillHeight: true }
                RowLayout { Layout.fillWidth: true; spacing: 8; CabButton { Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 50 : 56; text: "HALT"; font.pixelSize: root.piLayout ? 18 : 20; font.bold: true; normalColor: "#9d2020"; pressedColor: "#c62d2d"; onClicked: cab.stop() }; CabButton { Layout.preferredWidth: root.piLayout ? 94 : 112; Layout.preferredHeight: root.piLayout ? 50 : 56; text: "Reset"; font.pixelSize: root.piLayout ? 14 : 15; onClicked: cab.reset() } }
            }
        }

        GridLayout { Layout.fillWidth: true; columns: 6; columnSpacing: 5; rowSpacing: 0; Repeater { model: cab.infoModel; Rectangle { required property var modelData; Layout.fillWidth: true; Layout.preferredHeight: root.piLayout ? 42 : 50; radius: 6; color: "#20242a"; Column { anchors.centerIn: parent; spacing: -1; Label { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.label; color: "#8f98a4"; font.pixelSize: root.piLayout ? 8 : 10 }; Label { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.value; color: "#e7eaee"; font.pixelSize: root.piLayout ? 11 : 13; font.bold: true } } } } }
    }

    CommandPanelPopup { id: commandPanel; parent: Overlay.overlay; cab: root.cab; width: Math.min(Overlay.overlay.width - 24, 620); height: Math.min(Overlay.overlay.height - 24, 760); x: (Overlay.overlay.width - width) / 2; y: (Overlay.overlay.height - height) / 2 }
    Popup { id: speedLimitPopup; parent: Overlay.overlay; modal: true; focus: true; anchors.centerIn: parent; width: Math.min(Overlay.overlay.width - 36, 360); padding: 14; background: Rectangle { color: "#22272e"; radius: 10; border.width: 1; border.color: "#56606c" }; ColumnLayout { width: parent.width; spacing: 10; Label { Layout.fillWidth: true; text: "Speed Limit"; color: "white"; font.pixelSize: 18; font.bold: true }; Slider { id: speedLimitSlider; Layout.fillWidth: true; from: 0; to: Math.max(1, cab.speedMax); stepSize: 1; value: cab.speedLimit }; Label { Layout.fillWidth: true; text: Math.round(speedLimitSlider.value); color: "#dce3eb"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 18 }; RowLayout { Layout.fillWidth: true; CabButton { Layout.fillWidth: true; text: "Clear"; onClicked: { cab.clearSpeedLimit(); speedLimitPopup.close() } }; CabButton { Layout.fillWidth: true; text: "Set"; normalColor: "#246aa0"; onClicked: { cab.setSpeedLimit(Math.round(speedLimitSlider.value)); speedLimitPopup.close() } } } } }
}
