import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Control {
    id: root

    property string text: ""
    property string displayLabel: text
    property int labelChevron: 0
    property string gaugeLabel: ""
    readonly property bool showGauge: gaugeLabel.length > 0
    property int gaugeLevel: -1
    property url iconSource: ""
    property string trialIcon: ""
    property bool auxFace: false
    property string subtitle: ""
    readonly property bool trialFace: auxFace || trialIcon !== "" || speedFace
    readonly property bool neutralFace: auxFace || /^(power|smoke|coupler|crane|car-(car-lights|freight))-/.test(trialIcon)
    readonly property string detailedIcon: /^(crane-|speaker-|car-|panto-|horn$|whistle$|let-off$|water-inject$)/.test(trialIcon)
        ? trialIcon + "-relief.png" : ({
        volume: "speaker-up-relief.png",
        "volume-down": "speaker-down-relief.png",
        "rpm-up": "speaker-up-relief.png",
        "rpm-down": "speaker-down-relief.png",
        "coupler-front": "front-coupler-relief.png",
        "coupler-rear": "rear-coupler-relief.png"
    })[trialIcon] || ""
    readonly property bool speedFace: speedChevrons > 0 || trialIcon === "boost" || trialIcon === "brake"
    property int speedChevrons: 0
    property bool stopSign: false
    property bool selected: false
    property bool compact: false
    property bool stacked: false
    property bool wrapLabel: false
    property bool fitLabelWidth: false
    property int iconSize: compact ? 30 : 42
    property bool deferForHold: false
    property bool additionalHoldAction: false
    property string holdHint: ""
    property int holdThreshold: 1000
    property bool repeatWhileHeld: false
    property int repeatInterval: 250
    property color normalColor: "#303640"
    property color selectedColor: "#176fa8"
    property color pressedColor: "#5c9fc6"
    property color textColor: "#f5f7fa"
    property bool holdTriggered: false
    readonly property bool pressed: tapHandler.pressed
    readonly property bool visualPressed: pressed || pressFlash.running

    ToolTip.text: holdHint
    ToolTip.delay: 500
    ToolTip.visible: root.enabled && root.pressed && root.holdHint.length > 0 && !root.holdTriggered

    Timer { id: pressFlash; interval: 140 }
    onClicked: pressFlash.restart()

    signal clicked()
    signal held()

    implicitHeight: compact ? 44 : 58
    font.pixelSize: compact ? 12 : 14
    focusPolicy: Qt.StrongFocus

    readonly property real iconOpacity: enabled ? 1 : 0.5

    contentItem: GridLayout {
        columns: root.stacked ? 1 : 2
        rowSpacing: 4
        columnSpacing: root.compact ? 5 : 8

        Rectangle {
            Layout.preferredWidth: root.iconSize
            Layout.preferredHeight: root.iconSize
            Layout.alignment: Qt.AlignCenter
            visible: !root.trialFace && root.iconSource.toString().length > 0
            opacity: root.iconOpacity
            radius: root.compact ? 4 : 6
            color: "#e8ebef"
            border.width: 1
            border.color: "#c6cbd2"

            Image {
                anchors.fill: parent
                anchors.margins: root.compact ? 2 : 3
                source: root.iconSource
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
        }

        Image {
            visible: root.detailedIcon !== ""
            source: visible ? Qt.resolvedUrl(root.detailedIcon) : ""
            opacity: root.iconOpacity
            Layout.alignment: Qt.AlignCenter
            Layout.preferredWidth: Math.min(root.iconSize, root.availableWidth)
            Layout.preferredHeight: Layout.preferredWidth
            fillMode: Image.PreserveAspectFit
            mipmap: true
            transform: Translate { y: root.visualPressed ? 2 : 0 }
        }

        Canvas {
            id: trialArtwork
            readonly property bool raisedIcon: root.trialIcon !== "clack"

            visible: root.trialIcon !== "" && root.detailedIcon === ""
            transform: [
                Scale {
                    origin.x: trialArtwork.width / 2
                    origin.y: trialArtwork.height / 2
                    xScale: root.trialIcon.startsWith("smoke-diesel-") ? 1.25 : 1
                    yScale: xScale
                },
                Translate { y: trialArtwork.raisedIcon && root.visualPressed ? 2 : 0 }
            ]
            opacity: root.iconOpacity
            Layout.alignment: Qt.AlignCenter
            Layout.preferredWidth: Math.min(root.iconSize, root.availableWidth)
            Layout.preferredHeight: Layout.preferredWidth
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onVisibleChanged: requestPaint()
            Connections {
                target: root
                function onTrialIconChanged() { trialArtwork.requestPaint() }
            }
            onPaint: {
                const ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)
                ctx.scale(width / 64, height / 64)
                ctx.fillStyle = "#ffffff"
                ctx.strokeStyle = ctx.fillStyle
                if (raisedIcon) {
                    const relief = ctx.createLinearGradient(10, 7, 51, 58)
                    const on = root.trialIcon === "power-on"
                    const off = root.trialIcon === "power-off"
                    const bell = root.trialIcon === "bell"
                    relief.addColorStop(0, on ? "#a2edaa" : off ? "#ffb3af" : "#ffffff")
                    relief.addColorStop(0.37, on ? "#5ed671" : off ? "#f16a64" : "#f7faff")
                    relief.addColorStop(0.75, on ? "#3cc357" : off ? "#dd4946" : "#e7edf4")
                    relief.addColorStop(1, on ? "#229840" : off ? "#ad302e" : "#dce4ec")
                    ctx.fillStyle = relief
                    ctx.strokeStyle = relief
                    ctx.shadowColor = bell ? "rgba(18, 27, 36, 0.7)" : "rgba(11, 19, 28, 0.85)"
                    ctx.shadowOffsetX = bell ? 1 : 2
                    ctx.shadowOffsetY = bell ? 2 : 3
                    ctx.shadowBlur = 2
                }
                ctx.lineWidth = 4
                ctx.lineCap = "round"
                ctx.lineJoin = "round"

                function polygon(points) {
                    ctx.beginPath()
                    ctx.moveTo(points[0][0], points[0][1])
                    for (const point of points.slice(1))
                        ctx.lineTo(point[0], point[1])
                    ctx.closePath()
                    ctx.fill()
                }

                function line(points) {
                    ctx.beginPath()
                    ctx.moveTo(points[0][0], points[0][1])
                    for (const point of points.slice(1))
                        ctx.lineTo(point[0], point[1])
                    ctx.stroke()
                }

                function plume(x, y, scale) {
                    ctx.save()
                    ctx.translate(x, y)
                    ctx.scale(scale, scale)
                    ctx.beginPath()
                    ctx.moveTo(-2, 0)
                    ctx.bezierCurveTo(-8, -4, -7, -10, -2, -12)
                    ctx.bezierCurveTo(-3, -18, 3, -23, 8, -21)
                    ctx.bezierCurveTo(16, -22, 18, -12, 12, -9)
                    ctx.bezierCurveTo(10, -5, 6, -4, 3, -5)
                    ctx.quadraticCurveTo(3, -1, -2, 0)
                    ctx.fill()
                    ctx.restore()
                }

                switch (root.trialIcon) {
                case "power-on":
                case "power-off":
                    ctx.lineWidth = 6
                    ctx.beginPath()
                    ctx.arc(32, 33, 20, -Math.PI / 3, 4 * Math.PI / 3)
                    ctx.stroke()
                    line([[32, 8], [32, 33]])
                    break
                case "tower":
                    polygon([[13, 17], [51, 17], [46, 34], [18, 34]])
                    ctx.save()
                    ctx.shadowColor = "rgba(11, 19, 28, 0.35)"
                    ctx.shadowOffsetX = 0
                    ctx.shadowOffsetY = 1
                    ctx.shadowBlur = 1
                    line([[24, 34], [17, 57], [47, 57], [40, 34]])
                    line([[23, 36], [45, 56]])
                    line([[41, 36], [19, 56]])
                    ctx.restore()
                    line([[22, 12], [42, 12]])
                    line([[32, 6], [32, 12]])
                    for (let x = 21; x <= 39; x += 9)
                        ctx.clearRect(x, 22, 5, 5)
                    break
                case "smoke-steam-up":
                case "smoke-steam-down":
                case "smoke-diesel-up":
                case "smoke-diesel-down": {
                    const diesel = root.trialIcon.startsWith("smoke-diesel-")
                    ctx.fillRect(24, 34, 16, diesel ? 20 : 19)
                    ctx.beginPath()
                    ctx.ellipse(19, 29, 26, 10)
                    ctx.fill()
                    if (diesel) {
                        line([[9, 54], [55, 54]])
                    } else {
                        ctx.beginPath()
                        ctx.moveTo(8, 60)
                        ctx.quadraticCurveTo(32, 44, 56, 60)
                        ctx.stroke()
                    }
                    ctx.clearRect(23, 33, 18, 2)
                    if (root.trialIcon.endsWith("-up"))
                        plume(32, 27, 1)
                    break
                }
                case "bell":
                    ctx.beginPath()
                    ctx.moveTo(10, 46)
                    ctx.bezierCurveTo(20, 37, 16, 20, 25, 15)
                    ctx.quadraticCurveTo(32, 10, 39, 15)
                    ctx.bezierCurveTo(48, 20, 44, 37, 54, 46)
                    ctx.quadraticCurveTo(57, 51, 50, 51)
                    ctx.lineTo(14, 51)
                    ctx.quadraticCurveTo(7, 51, 10, 46)
                    ctx.fill()
                    ctx.beginPath()
                    ctx.arc(32, 53, 6, 0, Math.PI)
                    ctx.fill()
                    break
                case "crew":
                    ctx.fillRect(36, 4, 5, 21)
                    ctx.beginPath()
                    ctx.roundedRect(18, 21, 28, 38, 5, 5)
                    ctx.fill()
                    ctx.globalCompositeOperation = "destination-out"
                    for (let y = 28; y <= 46; y += 9)
                        ctx.clearRect(24, y, 16, 4)
                    break
                case "clack":
                    ctx.beginPath()
                    ctx.arc(32, 29, 20, 0, 2 * Math.PI)
                    ctx.stroke()
                    for (let spoke = 0; spoke < 8; ++spoke) {
                        const angle = spoke * Math.PI / 4
                        ctx.beginPath()
                        ctx.moveTo(32, 29)
                        ctx.lineTo(32 + 19 * Math.cos(angle), 29 + 19 * Math.sin(angle))
                        ctx.stroke()
                    }
                    ctx.fillRect(4, 51, 24, 5)
                    ctx.fillRect(36, 51, 24, 5)
                    break
                case "brake":
                    ctx.translate(64, 64)
                    ctx.rotate(Math.PI)
                    // Fall through to the shared arrow.
                case "boost":
                    polygon([[32, 5], [57, 32], [42, 32], [42, 58], [22, 58], [22, 32], [7, 32]])
                    break
                }
            }
        }

        Canvas {
            visible: root.stopSign
            opacity: root.iconOpacity
            Layout.alignment: Qt.AlignCenter
            Layout.preferredWidth: root.iconSize
            Layout.preferredHeight: root.iconSize

            onPaint: {
                const context = getContext("2d")
                context.clearRect(0, 0, width, height)
                const edge = width - 2
                const cut = width * 0.30
                context.beginPath()
                context.moveTo(cut, 2)
                context.lineTo(width - cut, 2)
                context.lineTo(edge, cut)
                context.lineTo(edge, height - cut)
                context.lineTo(width - cut, height - 2)
                context.lineTo(cut, height - 2)
                context.lineTo(2, height - cut)
                context.lineTo(2, cut)
                context.closePath()
                context.fillStyle = "#b51f2a"
                context.strokeStyle = "#ffffff"
                context.lineWidth = 2
                context.fill()
                context.stroke()
            }

            Text {
                anchors.centerIn: parent
                text: "STOP"
                color: "#ffffff"
                font.pixelSize: Math.round(root.iconSize * 0.25)
                font.bold: true
            }
        }

        LevelGauge {
            visible: root.showGauge
            opacity: root.iconOpacity
            Layout.alignment: Qt.AlignCenter
            Layout.preferredWidth: root.iconSize
            Layout.preferredHeight: root.iconSize
            level: root.gaugeLevel
            label: root.gaugeLabel
        }

        SpeedChevrons {
            Layout.alignment: Qt.AlignCenter
            count: root.speedChevrons
            ink: "#ffffff"
            opacity: root.iconOpacity
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignCenter
            visible: root.labelChevron === 0 && !root.auxFace
            text: root.displayLabel
            wrapMode: root.wrapLabel ? Text.WordWrap : Text.NoWrap
            fontSizeMode: root.fitLabelWidth ? Text.HorizontalFit : Text.FixedSize
            minimumPixelSize: 10
            color: root.enabled ? (root.trialFace ? "#ffffff" : root.textColor) : "#858c96"
            font: root.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        Column {
            visible: root.auxFace
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignCenter
            spacing: 2
            transform: Translate { y: root.visualPressed ? 2 : 0 }

            Text {
                width: parent.width
                text: root.displayLabel
                color: root.enabled ? "#ffffff" : "#858c96"
                font.pixelSize: root.font.pixelSize + 6
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
            }

            Text {
                width: parent.width
                text: root.subtitle || " "
                color: root.enabled ? "#ffffff" : "#858c96"
                font.pixelSize: Math.max(11, root.font.pixelSize - 2)
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
        }

        Item {
            visible: root.labelChevron !== 0
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignCenter
            implicitHeight: smokeLabel.implicitHeight

            Row {
                anchors.centerIn: parent
                height: smokeLabel.height
                spacing: 4
                layoutDirection: root.labelChevron < 0 ? Qt.LeftToRight : Qt.RightToLeft

                FontMetrics {
                    id: labelMetrics
                    font: smokeLabel.font
                }

                Canvas {
                    width: Math.ceil(labelMetrics.capitalHeight * 0.65) + 2
                    height: Math.ceil(labelMetrics.capitalHeight) + 2
                    // Align the drawing to the ink above the label baseline.
                    y: smokeLabel.y + smokeLabel.baselineOffset - (labelMetrics.capitalHeight + height) / 2
                    onPaint: {
                        const context = getContext("2d")
                        const pointsLeft = root.labelChevron < 0
                        const edge = pointsLeft ? width - 2 : 2
                        const point = pointsLeft ? 2 : width - 2
                        context.clearRect(0, 0, width, height)
                        context.strokeStyle = smokeLabel.color
                        context.lineWidth = Math.max(2, labelMetrics.capitalHeight * 0.2)
                        context.lineJoin = "round"
                        context.beginPath()
                        context.moveTo(edge, 2)
                        context.lineTo(point, height / 2)
                        context.lineTo(edge, height - 2)
                        context.stroke()
                    }
                }

                Text {
                    id: smokeLabel
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.displayLabel
                    color: root.enabled ? (root.trialFace ? "#ffffff" : root.textColor) : "#858c96"
                    font: root.font
                }
            }
        }
    }

    background: Rectangle {
        radius: root.compact ? 7 : 9
        color: root.trialFace ? "#17232d" : !root.enabled ? "#242930"
            : root.visualPressed ? ((root.deferForHold || root.repeatWhileHeld) ? root.pressedColor : Qt.darker(root.pressedColor, 1.45))
            : root.selected ? root.selectedColor : root.normalColor
        border.width: 1
        border.color: root.selected ? "#78c9ff" : "#626b78"

        Rectangle {
            visible: root.trialFace
            anchors.fill: parent
            anchors.margins: 3
            anchors.topMargin: root.visualPressed ? 5 : 2
            anchors.bottomMargin: root.visualPressed ? 2 : 5
            radius: parent.radius - 2
            border.color: root.visualPressed ? "#121c27" : "#718a9c"
            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: root.visualPressed ? "#101a25" : root.neutralFace ? "#405667" : root.speedFace ? "#405372" : "#365768"
                }
                GradientStop {
                    position: 0.22
                    color: root.neutralFace ? "#2d4152" : root.speedFace ? "#2b3e56" : "#274653"
                }
                GradientStop {
                    position: 0.65
                    color: root.neutralFace ? "#253748" : root.speedFace ? "#23354b" : "#203944"
                }
                GradientStop {
                    position: 1
                    color: root.visualPressed ? "#5c8199" : "#263b50"
                }
            }
            opacity: root.enabled ? 1 : 0.45
        }

        Item {
            visible: root.trialFace && (root.additionalHoldAction || root.deferForHold || root.repeatWhileHeld)
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 7
            width: 17
            height: 16
            opacity: root.iconOpacity

            Repeater {
                model: root.deferForHold && !root.additionalHoldAction ? 2 : 0
                Rectangle {
                    required property int index
                    x: index * 4
                    y: (1 - index) * 4
                    width: 12
                    height: 10
                    radius: 1
                    color: "transparent"
                    border.color: "#ffffff"
                    border.width: 1
                }
            }

            Text {
                visible: root.additionalHoldAction || !root.deferForHold
                anchors.centerIn: parent
                text: root.additionalHoldAction ? "+" : "↻"
                color: "#ffffff"
                font.pixelSize: 18
            }
        }

        Rectangle {
            visible: root.deferForHold && root.pressed && !root.holdTriggered
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            height: 5
            width: parent.width * Math.min(1, holdProgress.elapsed / Math.max(1, root.holdThreshold))
            color: "#78c9ff"
            radius: 2
        }
    }

    Timer {
        id: holdTimer
        interval: root.holdThreshold
        repeat: false
        onTriggered: {
            if (tapHandler.pressed && root.deferForHold) {
                root.holdTriggered = true
                root.held()
            }
        }
    }

    Timer {
        id: holdProgress
        property int elapsed: 0
        interval: 25
        repeat: true
        running: root.deferForHold && tapHandler.pressed && !root.holdTriggered
        onTriggered: elapsed += interval
        onRunningChanged: if (!running) elapsed = 0
    }

    Timer {
        interval: root.repeatInterval
        repeat: true
        running: root.repeatWhileHeld && !root.deferForHold && tapHandler.pressed
        onTriggered: root.clicked()
    }

    TapHandler {
        id: tapHandler
        enabled: root.enabled
        acceptedButtons: Qt.LeftButton
        onPressedChanged: {
            if (pressed) {
                root.holdTriggered = false
                if (root.deferForHold)
                    holdTimer.restart()
                else
                    root.clicked()
            } else {
                holdTimer.stop()
                if (root.deferForHold && !root.holdTriggered)
                    root.clicked()
            }
        }
    }

    Keys.onPressed: function(event) {
        if (!root.enabled || event.isAutoRepeat)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.clicked()
            event.accepted = true
        }
    }
}
