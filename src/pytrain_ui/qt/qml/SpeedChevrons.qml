import QtQuick

Canvas {
    id: root
    property int count: 0
    implicitWidth: 92
    implicitHeight: 22
    visible: count > 0
    onCountChanged: requestPaint()

    onPaint: {
        const context = getContext("2d")
        context.clearRect(0, 0, width, height)
        const count = root.count
        const step = 10
        const firstX = (width - (count - 1) * step - 8) / 2
        context.strokeStyle = "#f5f7fa"
        context.lineWidth = 4
        context.lineJoin = "miter"
        context.beginPath()
        for (let i = 0; i < count; ++i) {
            const x = firstX + i * step
            context.moveTo(x, 2)
            context.lineTo(x + 8, height / 2)
            context.lineTo(x, height - 2)
        }
        context.stroke()
    }
}
