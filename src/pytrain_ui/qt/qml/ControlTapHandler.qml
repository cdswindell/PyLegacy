import QtQuick

TapHandler {
    id: root

    property bool holdEnabled: false
    property var acceptsTap: null
    property bool holdTriggered: false
    signal tappedOnce()
    signal tappedTwice()
    signal heldGesture()

    acceptedButtons: Qt.LeftButton
    gesturePolicy: TapHandler.DragThreshold

    property DoubleTapWindow tapWindow: DoubleTapWindow {
        onSingleTap: root.tappedOnce()
        onDoubleTap: root.tappedTwice()
    }

    function cancelPendingTap() {
        tapWindow.stop()
    }

    onEnabledChanged: if (!enabled) cancelPendingTap()
    onCanceled: cancelPendingTap()
    onPressedChanged: if (pressed) holdTriggered = false
    onLongPressed: {
        cancelPendingTap()
        holdTriggered = true
        if (holdEnabled)
            heldGesture()
    }
    onTapped: point => {
        if (holdTriggered || (acceptsTap && !acceptsTap(point.position))) {
            cancelPendingTap()
            return
        }
        tapWindow.registerTap()
    }
}
