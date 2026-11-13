import QtQuick

Rectangle {
    id: root
    property bool depressed: false
    property bool selected: false
    property bool focused: false
    property color accent: "transparent"
    readonly property bool tinted: accent.a > 0

    radius: 9
    color: tinted ? Qt.darker(accent, 2.3) : "#17232d"
    border.width: selected ? 2 : 1
    border.color: focused || selected ? "#78bff0" : tinted ? Qt.lighter(accent, 1.35) : "#626b78"

    Rectangle {
        anchors.fill: parent
        anchors.margins: root.selected ? 3 : 2
        anchors.topMargin: root.depressed ? 5 : 2
        anchors.bottomMargin: root.depressed ? 2 : 5
        radius: Math.max(0, root.radius - 2)
        border.color: root.tinted ? Qt.lighter(root.accent, 1.4) : "#718a9c"
        opacity: root.enabled ? 1 : 0.45
        gradient: Gradient {
            GradientStop {
                position: 0
                color: root.tinted ? (root.depressed ? Qt.darker(root.accent, 1.8) : Qt.lighter(root.accent, 1.55))
                                   : root.depressed ? "#101a25" : "#405667"
            }
            GradientStop { position: 0.22; color: root.tinted ? root.accent : "#2d4152" }
            GradientStop { position: 0.65; color: root.tinted ? Qt.darker(root.accent, 1.12) : "#253748" }
            GradientStop {
                position: 1
                color: root.tinted ? (root.depressed ? Qt.lighter(root.accent, 1.3) : Qt.darker(root.accent, 1.4))
                                   : root.depressed ? "#5c8199" : "#263b50"
            }
        }
    }
}
