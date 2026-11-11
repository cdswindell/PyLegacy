import QtQuick

Rectangle {
    id: root
    required property int level
    radius: 6
    color: "#e8ebef"
    border.color: "#c6cbd2"

    Canvas {
        id: dial
        anchors.fill: parent
        anchors.margins: 2

        onPaint: {
            const context = getContext("2d")
            context.clearRect(0, 0, width, height)
            const x = width / 2
            const y = height * 0.69
            const radius = Math.min(width, height) * 0.39
            const start = 5 * Math.PI / 6
            const sweep = 4 * Math.PI / 3
            context.strokeStyle = "#243140"
            context.lineWidth = 2
            context.beginPath()
            context.arc(x, y, radius, start, start + sweep)
            context.stroke()

            if (root.level < 0)
                return
            const angle = start + Math.min(root.level, 100) * sweep / 100
            context.strokeStyle = "#176fa8"
            context.beginPath()
            context.moveTo(x, y)
            context.lineTo(x + radius * 0.85 * Math.cos(angle), y + radius * 0.85 * Math.sin(angle))
            context.stroke()
        }
    }

    onLevelChanged: dial.requestPaint()
}
