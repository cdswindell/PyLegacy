import QtQuick

TapHandler {
    id: root

    property int doubleTapInterval: 450
    property bool holdEnabled: false
    property var acceptsTap: null
    property bool holdTriggered: false
    signal tappedOnce()
    signal tappedTwice()
    signal heldGesture()

    acceptedButtons: Qt.LeftButton
    gesturePolicy: TapHandler.DragThreshold

    property Timer tapWindow: Timer {
        interval: root.doubleTapInterval
        onTriggered: root.tappedOnce()
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
        if (tapWindow.running) {
            cancelPendingTap()
            tappedTwice()
        } else {
            tapWindow.start()
        }
    }
}
