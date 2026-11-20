import QtQuick
import QtQuick.Controls

Control {
    id: root

    property string text: ""
    property bool selected: false
    property bool activateOnRelease: false
    property bool activateOnHold: false
    property bool distinguishDoubleClick: false
    property bool holdWithinBounds: false
    property bool mouseHoldEnabled: false
    property bool repeatWhileHeld: false
    property int repeatInterval: 250
    property color normalColor: "transparent"
    property color selectedColor: "#246aa0"
    property color selectedAccent: "transparent"
    property color pressedColor: "#5c9fc6"
    property bool interactionCanceled: false
    function cancelInteraction() {
        interactionCanceled = true
        doubleTapTimer.stop()
        pressFlash.stop()
        if (isPointerPressed())
            pressCanceled()
    }
    readonly property bool pressed: isPointerPressed() && !interactionCanceled

    function isPointerPressed() {
        return tapHandler.pressed || touchHandler.pressed
    }
    readonly property bool visualPressed: pressed || pressFlash.running

    Timer { id: pressFlash; interval: 140 }
    onClicked: pressFlash.restart()
    onEnabledChanged: if (!enabled) cancelInteraction()
    onVisibleChanged: if (!visible) cancelInteraction()

    DoubleTapWindow {
        id: doubleTapTimer
        onSingleTap: root.clicked()
        onDoubleTap: root.doubleClicked()
    }

    signal clicked()
    signal released()
    signal pressCanceled()
    signal doubleClicked()
    signal gestureHeld()

    implicitHeight: 62
    font.pixelSize: 20
    font.bold: true
    focusPolicy: Qt.StrongFocus

    contentItem: Text {
        text: root.text
        font: root.font
        color: root.enabled ? "#ffffff" : "#7d8591"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: ButtonFace {
        depressed: root.visualPressed
        selected: root.selected
        focused: root.activeFocus
        accent: root.normalColor
        selectedAccent: root.selectedAccent
    }

    component ButtonTapHandler: TapHandler {
        property bool holdTriggered: false
        enabled: root.enabled
        acceptedButtons: Qt.LeftButton
        longPressThreshold: root.holdWithinBounds ? 0.55 : undefined
        onTapped: {
            if (root.interactionCanceled)
                return
            if (root.distinguishDoubleClick && !holdTriggered) {
                doubleTapTimer.registerTap()
            } else if (root.activateOnRelease && !root.distinguishDoubleClick) {
                root.clicked()
            }
        }
        onLongPressed: {
            if (root.interactionCanceled)
                return
            if (root.activateOnHold || (root.distinguishDoubleClick &&
                (root.mouseHoldEnabled || point.device.type === PointerDevice.TouchScreen))) {
                holdTriggered = true
                doubleTapTimer.stop()
                root.gestureHeld()
            }
        }
        onPressedChanged: {
            if (pressed) {
                root.interactionCanceled = false
                holdTriggered = false
                if (!root.activateOnRelease && !root.distinguishDoubleClick)
                    root.clicked()
            } else {
                root.released()
            }
        }
        onCanceled: {
            doubleTapTimer.stop()
            root.pressCanceled()
        }
    }

    ButtonTapHandler {
        id: tapHandler
        acceptedDevices: root.holdWithinBounds
            ? PointerDevice.AllDevices & ~PointerDevice.TouchScreen : PointerDevice.AllDevices
    }

    ButtonTapHandler {
        id: touchHandler
        enabled: root.enabled && root.holdWithinBounds
        acceptedDevices: PointerDevice.TouchScreen
        gesturePolicy: TapHandler.DragWithinBounds
    }

    Timer {
        interval: root.repeatInterval
        repeat: true
        running: root.visible && root.enabled && !root.interactionCanceled && root.repeatWhileHeld && root.pressed
        onTriggered: root.clicked()
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
