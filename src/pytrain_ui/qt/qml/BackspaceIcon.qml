import QtQuick
import QtQuick.Shapes

Item {
    id: root
    property color color: "#ff6666"
    property real innerGap: 2
    implicitWidth: 44
    implicitHeight: 30

    Shape {
        id: symbol
        anchors.centerIn: parent
        width: Math.min(root.width, 44)
        height: Math.min(root.height, 30)
        readonly property real stroke: 2
        readonly property real inset: stroke + root.innerGap + stroke / 2
        readonly property real crossRight: width - inset
        readonly property real crossLeft: crossRight - (height - inset * 2)
        ShapePath {
            strokeColor: root.color
            strokeWidth: symbol.stroke
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            startX: 1
            startY: symbol.height / 2
            PathLine { x: 12; y: 1 }
            PathLine { x: symbol.width - 1; y: 1 }
            PathLine { x: symbol.width - 1; y: symbol.height - 1 }
            PathLine { x: 12; y: symbol.height - 1 }
            PathLine { x: 1; y: symbol.height / 2 }
        }
        ShapePath {
            strokeColor: root.color
            strokeWidth: symbol.stroke
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            startX: symbol.crossLeft
            startY: symbol.inset
            PathLine { x: symbol.crossRight; y: symbol.height - symbol.inset }
            PathMove { x: symbol.crossRight; y: symbol.inset }
            PathLine { x: symbol.crossLeft; y: symbol.height - symbol.inset }
        }
    }
}
