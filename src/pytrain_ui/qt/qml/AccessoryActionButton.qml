import QtQuick

CabButton {
    id: root

    required property var controller
    required property int tmccId
    required property string action
    property int heldAddress: 0
    signal accessoryHoldChanged(bool active)

    activateOnRelease: true
    activateOnHold: action === "HOLD"

    function releaseAccessory() {
        if (!heldAddress)
            return
        const address = heldAddress
        heldAddress = 0
        if (controller)
            controller.holdQuickAction(address, false)
        accessoryHoldChanged(false)
    }

    onClicked: {
        if (action !== "HOLD")
            controller.quickAction(action, tmccId)
    }
    onGestureHeld: {
        heldAddress = tmccId
        accessoryHoldChanged(true)
        controller.holdQuickAction(heldAddress, true)
    }
    onReleased: releaseAccessory()
    onPressCanceled: releaseAccessory()
    onEnabledChanged: if (!enabled) releaseAccessory()
    onVisibleChanged: if (!visible) releaseAccessory()
    Component.onDestruction: releaseAccessory()
}
