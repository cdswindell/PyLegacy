import QtQuick

Item {
    id: root

    property alias text: nameText.text
    property alias font: nameText.font
    property alias color: nameText.color
    readonly property bool overflowing: width > 0 && nameText.implicitWidth > width
    readonly property real cycleDistance: nameText.implicitWidth + names.spacing

    implicitHeight: nameText.implicitHeight
    clip: true
    Accessible.role: Accessible.StaticText
    Accessible.name: text

    onTextChanged: if (scroll.running) scroll.restart()

    Row {
        id: names
        spacing: 18
        anchors.verticalCenter: parent.verticalCenter

        Text {
            id: nameText
            textFormat: Text.PlainText
            elide: Text.ElideNone
            wrapMode: Text.NoWrap
        }

        Text {
            visible: root.overflowing
            text: nameText.text
            textFormat: Text.PlainText
            color: nameText.color
            font: nameText.font
        }
    }

    SequentialAnimation {
        id: scroll
        running: root.visible && root.enabled && root.overflowing
        loops: Animation.Infinite

        PauseAnimation { duration: 900 }
        NumberAnimation {
            target: names
            property: "x"
            from: 0
            to: -root.cycleDistance
            duration: Math.max(1200, root.cycleDistance * 18)
            easing.type: Easing.Linear
        }
        ScriptAction { script: names.x = 0 }
        onStopped: names.x = 0
    }
}
