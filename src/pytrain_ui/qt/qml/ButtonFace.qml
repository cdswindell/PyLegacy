import QtQuick

Rectangle {
    id: root
    property bool depressed: false
    property bool selected: false
    property bool focused: false
    property color accent: "transparent"
    property color selectedAccent: "transparent"
    readonly property color faceAccent: selected && selectedAccent.a > 0 ? selectedAccent : accent
    readonly property bool tinted: faceAccent.a > 0

    radius: 9
    color: tinted ? Qt.darker(faceAccent, 2.3) : "#17232d"
    border.width: selected ? 2 : 1
    border.color: focused || selected ? "#78bff0" : tinted ? Qt.lighter(faceAccent, 1.35) : "#626b78"

    Rectangle {
        anchors.fill: parent
        anchors.margins: root.selected ? 3 : 2
        anchors.topMargin: root.depressed ? 5 : 2
        anchors.bottomMargin: root.depressed ? 2 : 5
        radius: Math.max(0, root.radius - 2)
        border.color: root.tinted ? Qt.lighter(root.faceAccent, 1.4) : "#718a9c"
        opacity: root.enabled ? 1 : 0.45
        gradient: root.selected && root.selectedAccent.a === 0 ? selectionGradient : standardGradient
        SelectionGradient {
            id: selectionGradient
            selected: true
            depressed: root.depressed
        }
        Gradient {
            id: standardGradient
            GradientStop {
                position: 0
                color: root.tinted ? (root.depressed ? Qt.darker(root.faceAccent, 1.8) : Qt.lighter(root.faceAccent, 1.55))
                                   : root.depressed ? "#101a25" : "#405667"
            }
            GradientStop { position: 0.22; color: root.tinted ? root.faceAccent : "#2d4152" }
            GradientStop { position: 0.65; color: root.tinted ? Qt.darker(root.faceAccent, 1.12) : "#253748" }
            GradientStop {
                position: 1
                color: root.tinted ? (root.depressed ? Qt.lighter(root.faceAccent, 1.3) : Qt.darker(root.faceAccent, 1.4))
                                   : root.depressed ? "#5c8199" : "#263b50"
            }
        }
    }
}
