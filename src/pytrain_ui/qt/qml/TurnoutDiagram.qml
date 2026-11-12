import QtQuick

Canvas {
    id: root
    required property bool diverging
    Accessible.role: Accessible.Graphic
    Accessible.name: diverging ? "Three-rail turnout set to Out" : "Three-rail turnout set to Thru"

    onDivergingChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        ctx.clearRect(0, 0, width, height)
        const scale = Math.min(width / 156, height / 70)
        ctx.translate((width - 156 * scale) / 2, (height - 70 * scale) / 2)
        ctx.scale(scale, scale)
        ctx.lineCap = "round"
        ctx.lineJoin = "round"

        function segment(x1, y1, x2, y2, color, weight) {
            ctx.strokeStyle = color
            ctx.lineWidth = weight
            ctx.beginPath()
            ctx.moveTo(x1, y1)
            ctx.lineTo(x2, y2)
            ctx.stroke()
        }

        function branchRail(offset, color, weight) {
            ctx.strokeStyle = color
            ctx.lineWidth = weight
            ctx.beginPath()
            ctx.moveTo(10, 51 + offset)
            ctx.lineTo(35, 51 + offset)
            ctx.bezierCurveTo(77, 51 + offset, 90, 27 + offset, 145, 14 + offset)
            ctx.stroke()
        }

        for (let x = 10; x <= 145; x += 10)
            segment(x, 38, x, 64, "#526175", 4)

        // The branch ties rotate with the track as it diverges from the straight leg.
        for (let step = 3; step <= 10; step++) {
            const t = step / 10
            const u = 1 - t
            const x = u * u * u * 35 + 3 * u * u * t * 77 + 3 * u * t * t * 90 + t * t * t * 145
            const y = u * u * u * 51 + 3 * u * u * t * 51 + 3 * u * t * t * 27 + t * t * t * 14
            const dx = 3 * u * u * 42 + 6 * u * t * 13 + 3 * t * t * 55
            const dy = -6 * u * t * 24 - 3 * t * t * 13
            const span = Math.hypot(dx, dy)
            const nx = -dy / span * 12
            const ny = dx / span * 12
            segment(x - nx, y - ny, x + nx, y + ny, "#526175", 4)
        }

        const inactive = "#8999ad"
        const active = root.diverging ? "#ffbe80" : "#81e5a0"
        for (const offset of [-8, 0, 8]) {
            if (root.diverging)
                segment(10, 51 + offset, 145, 51 + offset, inactive, 1.5)
            else
                branchRail(offset, inactive, 1.5)
        }
        for (const offset of [-8, 0, 8]) {
            if (root.diverging)
                branchRail(offset, active, 2.25)
            else
                segment(10, 51 + offset, 145, 51 + offset, active, 2.25)
        }
    }
}
