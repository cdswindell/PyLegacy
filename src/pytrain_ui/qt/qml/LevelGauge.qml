import QtQuick

Rectangle {
    id: root
    required property int level
    required property string label
    color: "white"
    border.color: "black"

    Canvas {
        id: dial
        anchors.fill: parent
        anchors.margins: 2

        onPaint: {
            const context = getContext("2d")
            context.clearRect(0, 0, width, height)
            const size = Math.min(width, height)
            const x = width / 2
            const y = height * 0.49
            const start = 5 * Math.PI / 6
            const sweep = 4 * Math.PI / 3
            context.strokeStyle = "black"
            context.fillStyle = "black"

            for (const rim of [{radius: 0.40, weight: 0.024}, {radius: 0.35, weight: 0.012}]) {
                context.lineWidth = Math.max(1, size * rim.weight)
                context.beginPath()
                context.arc(x, y, size * rim.radius, start, start + sweep)
                context.stroke()
            }

            const tickRadius = size * 0.32
            for (let tick = 0; tick <= 10; ++tick) {
                const angle = start + sweep * tick / 10
                const major = tick % 5 === 0
                const inner = tickRadius - size * (major ? 0.068 : 0.035)
                context.lineWidth = Math.max(1, size * (major ? 0.027 : 0.012))
                context.beginPath()
                context.moveTo(x + inner * Math.cos(angle), y + inner * Math.sin(angle))
                context.lineTo(x + tickRadius * Math.cos(angle), y + tickRadius * Math.sin(angle))
                context.stroke()
            }

            context.textAlign = "center"
            context.textBaseline = "middle"
            context.font = "bold " + Math.round(size * 0.15) + "px sans-serif"
            context.fillText("E", x - size * 0.105, y + size * 0.14)
            context.fillText("F", x + size * 0.105, y + size * 0.14)
            context.font = "bold " + Math.round(size * 0.175) + "px sans-serif"
            context.fillText(root.label, x, height * 0.83)

            if (root.level >= 0) {
                const angle = start + Math.min(root.level, 100) * sweep / 100
                const length = size * 0.30
                context.lineWidth = size * 0.062
                context.beginPath()
                context.moveTo(x, y)
                context.lineTo(x + length * Math.cos(angle), y + length * Math.sin(angle))
                context.stroke()
                context.beginPath()
                context.arc(x, y, size * 0.062, 0, 2 * Math.PI)
                context.fill()
            }
        }
    }

    onLevelChanged: dial.requestPaint()
    onLabelChanged: dial.requestPaint()
}
