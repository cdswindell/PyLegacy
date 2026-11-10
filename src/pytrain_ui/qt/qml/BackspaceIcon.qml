import QtQuick

Item {
    id: root
    property color color: "#ff6666"
    property real innerGap: 2
    implicitWidth: 48
    implicitHeight: 34

    function artwork() {
        const outline = 3.5
        const cross = 4
        const inset = outline / 2 + root.innerGap + cross / 2
        const top = 3 + inset
        const bottom = 31 - inset
        const right = 45 - inset
        const left = right - (bottom - top)
        return '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="34" viewBox="0 0 48 34">' +
               '<g fill="none" stroke="' + root.color.toString() + '" stroke-linecap="round" stroke-linejoin="round">' +
               '<path stroke-width="' + outline + '" d="M15 3H40A5 5 0 0 1 45 8V26A5 5 0 0 1 40 31H15' +
               'Q13.4 31 12.4 29.8L3.7 19Q2.1 17 3.7 15L12.4 4.2Q13.4 3 15 3Z"/>' +
               '<path stroke-width="' + cross + '" d="M' + left + ' ' + top + 'L' + right + ' ' + bottom +
               'M' + right + ' ' + top + 'L' + left + ' ' + bottom + '"/></g></svg>'
    }

    Image {
        anchors.centerIn: parent
        width: Math.min(root.width, 48)
        height: Math.min(root.height, 34)
        source: "data:image/svg+xml," + encodeURIComponent(root.artwork())
        sourceSize.width: 144
        sourceSize.height: 102
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }
}
