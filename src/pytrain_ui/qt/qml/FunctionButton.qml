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
    readonly property bool trialFace: trialIcon !== ""
    readonly property bool speedFace: trialIcon === "boost" || trialIcon === "brake"
    property int speedChevrons: 0
    property bool stopSign: false
    property bool selected: false
    property bool compact: false
    property bool stacked: false
    property bool wrapLabel: false
    property bool fitLabelWidth: false
    property int iconSize: compact ? 30 : 42
    property bool deferForHold: false
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

        Canvas {
            id: trialArtwork
            readonly property bool raisedIvory: ["bell", "crew", "boost"].includes(root.trialIcon)

            visible: root.trialFace
            transform: Translate {
                y: trialArtwork.raisedIvory && root.visualPressed ? 2 : 0
            }
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
                ctx.fillStyle = "#fff3dc"
                ctx.strokeStyle = ctx.fillStyle
                if (raisedIvory) {
                    const ivory = ctx.createLinearGradient(10, 7, 51, 58)
                    ivory.addColorStop(0, "#fffdf6")
                    ivory.addColorStop(0.37, "#fff5e2")
                    const bell = root.trialIcon === "bell"
                    ivory.addColorStop(0.75, bell ? "#efe0c5" : "#e8d6b8")
                    ivory.addColorStop(1, bell ? "#cab796" : "#bba485")
                    ctx.fillStyle = ivory
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

                switch (root.trialIcon) {
                case "volume":
                    polygon([[5, 23], [16, 23], [33, 10], [33, 54], [16, 41], [5, 41]])
                    ctx.fillRect(41, 29, 18, 6)
                    ctx.fillRect(47, 23, 6, 18)
                    break
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
            opacity: root.iconOpacity
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignCenter
            visible: root.labelChevron === 0
            text: root.displayLabel
            wrapMode: root.wrapLabel ? Text.WordWrap : Text.NoWrap
            fontSizeMode: root.fitLabelWidth ? Text.HorizontalFit : Text.FixedSize
            minimumPixelSize: 10
            color: root.enabled ? (root.trialFace ? "#fff3dc" : root.textColor) : "#858c96"
            font: root.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
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
                    color: root.enabled ? root.textColor : "#858c96"
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
                    color: root.visualPressed ? "#101a25" : root.speedFace ? "#617b99" : "#5c8a9a"
                }
                GradientStop {
                    position: 0.22
                    color: root.speedFace ? "#3d536f" : "#335b6c"
                }
                GradientStop {
                    position: 0.65
                    color: root.speedFace ? "#344963" : "#2a4d5d"
                }
                GradientStop {
                    position: 1
                    color: root.visualPressed ? "#5c8199" : "#263b50"
                }
            }
            opacity: root.enabled ? 1 : 0.45
        }

        Item {
            visible: root.trialFace && (root.deferForHold || root.repeatWhileHeld)
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 7
            width: 17
            height: 16
            opacity: root.iconOpacity

            Repeater {
                model: root.deferForHold ? 2 : 0
                Rectangle {
                    required property int index
                    x: index * 4
                    y: (1 - index) * 4
                    width: 12
                    height: 10
                    radius: 1
                    color: "transparent"
                    border.color: "#fff3dc"
                    border.width: 1
                }
            }

            Text {
                visible: !root.deferForHold
                anchors.centerIn: parent
                text: "↻"
                color: "#fff3dc"
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
