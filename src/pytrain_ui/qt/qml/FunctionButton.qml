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
    property color normalColor: "#303640"
    property color selectedColor: "#176fa8"
    property color pressedColor: "#48515e"
    readonly property bool pressed: tapHandler.pressed

    signal clicked()

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
    }

    TapHandler {
        id: tapHandler
        enabled: root.enabled
        acceptedButtons: Qt.LeftButton
        onPressedChanged: {
            if (pressed && !root.deferForHold)
                root.clicked()
            else if (!pressed && root.deferForHold)
                root.clicked()
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
