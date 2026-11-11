import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Control {
    id: root

    property string text: ""
    property url iconSource: ""
    property bool selected: false
    property bool compact: false
    property bool stacked: false
    property bool wrapLabel: false
    property int iconSize: compact ? 30 : 42
    property bool deferForHold: false
    property string holdHint: ""
    property int holdThreshold: 1000
    property bool repeatWhileHeld: false
    property int repeatInterval: 250
    property color normalColor: "#303640"
    property color selectedColor: "#176fa8"
    property color pressedColor: "#5c9fc6"
    property bool holdTriggered: false
    readonly property bool pressed: tapHandler.pressed
    readonly property bool visualPressed: pressed || pressFlash.running

    ToolTip.text: holdHint
    ToolTip.delay: 500
    ToolTip.visible: root.enabled && root.pressed && root.holdHint.length > 0 && !root.holdTriggered

    Timer { id: pressFlash; interval: 140 }
    onClicked: pressFlash.restart()

    signal clicked()
    signal held()

    implicitHeight: compact ? 44 : 58
    font.pixelSize: compact ? 12 : 14
    focusPolicy: Qt.StrongFocus

    contentItem: GridLayout {
        columns: root.stacked ? 1 : 2
        rowSpacing: 4
        columnSpacing: root.compact ? 5 : 8

        Rectangle {
            Layout.preferredWidth: root.iconSize
            Layout.preferredHeight: root.iconSize
            Layout.alignment: Qt.AlignCenter
            visible: root.iconSource.toString().length > 0
            radius: root.compact ? 4 : 6
            color: "#e8ebef"
            border.width: 1
            border.color: "#c6cbd2"

            Image {
                anchors.fill: parent
                anchors.margins: root.compact ? 2 : 3
                source: root.iconSource
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignCenter
            text: root.text
            wrapMode: root.wrapLabel ? Text.WordWrap : Text.NoWrap
            color: root.enabled ? "#f5f7fa" : "#858c96"
            font: root.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    background: Rectangle {
        radius: root.compact ? 7 : 9
        color: !root.enabled ? "#242930"
            : root.visualPressed ? (root.deferForHold ? Qt.darker(root.pressedColor, 1.45) : root.pressedColor)
            : root.selected ? root.selectedColor : root.normalColor
        border.width: 1
        border.color: root.selected ? "#78c9ff" : "#626b78"

        Rectangle {
            visible: root.deferForHold && root.pressed && !root.holdTriggered
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            height: 3
            width: parent.width * Math.min(1, holdProgress.elapsed / Math.max(1, root.holdThreshold))
            color: "#78c9ff"
            radius: 2
        }
    }

    Timer {
        id: holdTimer
        interval: root.holdThreshold
        repeat: false
        onTriggered: {
            if (tapHandler.pressed && root.deferForHold) {
                root.holdTriggered = true
                root.held()
            }
        }
    }

    Timer {
        id: holdProgress
        property int elapsed: 0
        interval: 25
        repeat: true
        running: root.deferForHold && tapHandler.pressed && !root.holdTriggered
        onTriggered: elapsed += interval
        onRunningChanged: if (!running) elapsed = 0
    }

    Timer {
        interval: root.repeatInterval
        repeat: true
        running: root.repeatWhileHeld && !root.deferForHold && tapHandler.pressed
        onTriggered: root.clicked()
    }

    TapHandler {
        id: tapHandler
        enabled: root.enabled
        acceptedButtons: Qt.LeftButton
        onPressedChanged: {
            if (pressed) {
                root.holdTriggered = false
                if (root.deferForHold)
                    holdTimer.restart()
                else
                    root.clicked()
            } else {
                holdTimer.stop()
                if (root.deferForHold && !root.holdTriggered)
                    root.clicked()
            }
        }
    }

    Keys.onPressed: function(event) {
        if (!root.enabled || event.isAutoRepeat)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.clicked()
            event.accepted = true
        }
    }
}
