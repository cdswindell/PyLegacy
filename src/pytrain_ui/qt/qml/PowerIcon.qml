import QtQuick

Canvas {
    id: root

    property bool powerOn: true
    property bool depressed: false

    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPowerOnChanged: requestPaint()
    onDepressedChanged: requestPaint()
    onVisibleChanged: requestPaint()
    transform: Translate { y: root.depressed ? 2 : 0 }

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        ctx.clearRect(0, 0, width, height)
        ctx.scale(width / 64, height / 64)
        const relief = ctx.createLinearGradient(10, 7, 51, 58)
        relief.addColorStop(0, powerOn ? "#a2edaa" : "#ffb3af")
        relief.addColorStop(0.37, powerOn ? "#5ed671" : "#f16a64")
        relief.addColorStop(0.75, powerOn ? "#3cc357" : "#dd4946")
        relief.addColorStop(1, powerOn ? "#229840" : "#ad302e")
        ctx.strokeStyle = relief
        ctx.shadowColor = "rgba(11, 19, 28, 0.85)"
        ctx.shadowOffsetX = 2
        ctx.shadowOffsetY = 3
        ctx.shadowBlur = 2
        ctx.lineWidth = 6
        ctx.lineCap = "round"
        ctx.lineJoin = "round"
        ctx.beginPath()
        ctx.arc(32, 33, 20, -Math.PI / 3, 4 * Math.PI / 3)
        ctx.stroke()
        ctx.beginPath()
        ctx.moveTo(32, 8)
        ctx.lineTo(32, 33)
        ctx.stroke()
    }
}
