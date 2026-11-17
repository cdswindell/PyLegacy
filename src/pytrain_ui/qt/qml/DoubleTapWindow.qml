import QtQuick

Timer {
    id: root

    interval: 400
    property double firstTapTime: 0
    signal singleTap()
    signal doubleTap()

    onTriggered: singleTap()

    function registerTap() {
        const now = Date.now()
        const pending = running
        const elapsed = now - firstTapTime
        // A busy event loop may deliver the next tap before the timer's timeout.
        if (pending && elapsed >= 0 && elapsed <= interval) {
            stop()
            doubleTap()
            return
        }
        firstTapTime = now
        restart()
        if (pending)
            singleTap()
    }
}
