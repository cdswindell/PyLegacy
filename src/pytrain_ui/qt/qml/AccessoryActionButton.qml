import QtQuick

CabButton {
    id: root

    required property var controller
    required property int tmccId
    required property string deviceKind
    required property string action
    property int heldAddress: 0
    property bool trackingPress: false
    signal accessoryPressChanged(bool active)

    activateOnRelease: true

    Item {
        objectName: "asc2HoldDecoration"
        visible: root.deviceKind === "ASC2" && root.action === "HOLD"
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 7
        width: 17
        height: 16
        opacity: root.enabled ? 1 : 0.45

        Repeater {
            model: 2
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
    }

    function releaseAccessory() {
        if (!heldAddress)
            return
        const address = heldAddress
        heldAddress = 0
        if (controller)
            controller.holdQuickAction(address, false)
    }

    onClicked: {
        if (action !== "HOLD")
            controller.quickAction(action, tmccId, deviceKind)
    }
    function trackPress(active) {
        if (trackingPress === active)
            return
        trackingPress = active
        accessoryPressChanged(active)
    }

    onPressedChanged: {
        trackPress(pressed)
        if (pressed && enabled && action === "HOLD" && deviceKind === "ASC2" && !heldAddress) {
            heldAddress = tmccId
            controller.holdQuickAction(heldAddress, true)
        }
    }
    onReleased: releaseAccessory()
    onPressCanceled: releaseAccessory()
    onEnabledChanged: if (!enabled) releaseAccessory()
    onVisibleChanged: if (!visible) releaseAccessory()
    Component.onDestruction: {
        releaseAccessory()
        trackPress(false)
    }
}
