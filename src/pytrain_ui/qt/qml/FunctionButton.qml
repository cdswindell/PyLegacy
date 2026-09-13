import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Control {
    id: root

    property string text: ""
    property url iconSource: ""
    property bool selected: false
    property bool compact: false
    property bool deferForHold: false
    property int holdThreshold: 1000
    property bool repeatWhileHeld: false
    property int repeatInterval: 250
    property color normalColor: "#303640"
    property color selectedColor: "#176fa8"
    property color pressedColor: "#48515e"
    property bool holdTriggered: false
    readonly property bool pressed: tapHandler.pressed

    signal clicked()
    signal held()

    implicitHeight: compact ? 44 : 58
    font.pixelSize: compact ? 12 : 14
    focusPolicy: Qt.StrongFocus

    contentItem: RowLayout {
        spacing: root.compact ? 5 : 8

        Rectangle {
            Layout.preferredWidth: root.compact ? 30 : 42
            Layout.preferredHeight: root.compact ? 30 : 42
            Layout.alignment: Qt.AlignVCenter
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
            Layout.alignment: Qt.AlignVCenter
            text: root.text
            color: root.enabled ? "#f5f7fa" : "#858c96"
            font: root.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    background: Rectangle {
        radius: root.compact ? 7 : 9
        color: !root.enabled ? "#242930" : root.pressed ? root.pressedColor : root.selected ? root.selectedColor : root.normalColor
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
