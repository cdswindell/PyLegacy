import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var controller
    required property var accessory
    required property bool compact
    property bool editing: false
    property int draftMask: 0
    property int draftValues: 0
    readonly property bool hasUnsavedChanges: editing && draftMask !== 0
    readonly property var states: accessory.relayStates || [-1, -1, -1, -1, -1, -1, -1, -1]
    readonly property int pendingMask: accessory.relayPendingMask || 0
    readonly property string accessoryKey: accessory.key || ""
    spacing: 16
    PanelMetrics { id: metrics }

    function discardChanges() { editing = false; draftMask = 0; draftValues = 0 }
    function refresh() {
        if (controller && accessoryKey)
            controller.requestUncouplerRelays(accessoryKey)
    }
    function stateFor(index) {
        return editing && (draftMask & (1 << index)) ? Number(!!(draftValues & (1 << index))) : states[index]
    }
    function choose(index) {
        const bit = 1 << index
        const on = stateFor(index) !== 1
        if (!editing) {
            controller.setUncouplerRelays(accessoryKey, on ? bit : 0, bit)
            return
        }
        draftValues = on ? draftValues | bit : draftValues & ~bit
        draftMask = states[index] === Number(on) ? draftMask & ~bit : draftMask | bit
    }
    function chooseAll(on) {
        if (!editing) {
            controller.setUncouplerRelays(accessoryKey, on ? 255 : 0, 255)
            return
        }
        draftValues = on ? 255 : 0
        draftMask = states.reduce((mask, value, index) => value === Number(on) ? mask : mask | (1 << index), 0)
    }
    onVisibleChanged: {
        if (visible) refresh()
        else discardChanges()
    }
    onAccessoryKeyChanged: { discardChanges(); if (visible) Qt.callLater(refresh) }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: root.editing ? "Choose relay states, then Apply" : "Tap a relay to toggle On/Off"
            color: "#c3d3e4"
            font.pixelSize: root.compact ? 15 : 18
            wrapMode: Text.WordWrap
        }
        CabButton {
            objectName: "editRelayGroup"
            Layout.preferredWidth: root.compact ? 130 : 150
            Layout.preferredHeight: Math.round((root.compact ? 56 : 64) * 1.2)
            text: root.editing ? "Editing Group" : "Edit Group"
            enabled: !root.editing && !root.pendingMask
            activateOnRelease: true
            onClicked: { root.draftMask = 0; root.editing = true }
        }
    }

    GridLayout {
        Layout.fillWidth: true
        columns: 4
        columnSpacing: 8
        rowSpacing: 8
        Repeater {
            model: 8
            CabButton {
                required property int index
                objectName: "asc2Relay" + (index + 1)
                readonly property int relayState: root.stateFor(index)
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: 1
                Layout.preferredHeight: root.compact ? 52 : metrics.cabActionTileHeight(false)
                text: String(index + 1) + "\n" + (relayState < 0 ? "Unknown" : relayState ? "On" : "Off")
                Accessible.name: "Relay " + (index + 1) + ", " + (relayState < 0 ? "unknown" : relayState ? "On" : "Off")
                selected: relayState === 1
                normalColor: root.editing && (root.draftMask & (1 << index)) ? "#8b6625" : "transparent"
                selectedAccent: root.editing && (root.draftMask & (1 << index)) ? "#8b6625" : "#08784c"
                enabled: !root.pendingMask
                font.pixelSize: root.compact ? 20 : 26
                activateOnRelease: true
                onClicked: root.choose(index)
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        CabButton {
            objectName: "allRelaysOn"
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.preferredHeight: Math.round((root.compact ? 56 : 64) * 1.2)
            text: "All On"
            enabled: !root.pendingMask
            activateOnRelease: true
            onClicked: root.chooseAll(true)
        }
        CabButton {
            objectName: "allRelaysOff"
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.preferredHeight: Math.round((root.compact ? 56 : 64) * 1.2)
            text: "All Off"
            enabled: !root.pendingMask
            activateOnRelease: true
            onClicked: root.chooseAll(false)
        }
        CabButton {
            objectName: "refreshRelays"
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.preferredHeight: Math.round((root.compact ? 56 : 64) * 1.2)
            text: "Refresh"
            enabled: !root.pendingMask
            activateOnRelease: true
            onClicked: root.refresh()
        }
    }

    RowLayout {
        Layout.fillWidth: true
        visible: root.editing
        spacing: 8
        CabButton {
            objectName: "cancelRelayGroup"
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.preferredHeight: root.compact ? 44 : 52
            text: "Cancel"
            activateOnRelease: true
            onClicked: root.discardChanges()
        }
        CabButton {
            objectName: "applyRelayGroup"
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.preferredHeight: root.compact ? 44 : 52
            text: "Apply"
            selected: true
            enabled: root.draftMask !== 0 && !root.pendingMask
            activateOnRelease: true
            onClicked: if (root.controller.setUncouplerRelays(root.accessoryKey, root.draftValues, root.draftMask))
                root.discardChanges()
        }
    }

    Frame {
        objectName: "uncouplerRelayWarning"
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        padding: 8
        background: Rectangle {
            color: "#7a2032"
            border.color: "#ff6b6b"
            border.width: 2
            radius: 8
        }
        contentItem: RowLayout {
            spacing: 8
            Label { text: "⚠"; color: "#ffe285"; font.pixelSize: 28 }
            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: "Do not use with uncoupling tracks; it will burn them out."
                color: "#ffffff"
                font.pixelSize: root.compact ? 16 : 18
                font.bold: true
                wrapMode: Text.WordWrap
            }
        }
    }

    Label {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        text: root.accessory.relayStatus || ""
        visible: text.length > 0
        color: "#f0c36a"
        font.pixelSize: root.compact ? 15 : 18
        wrapMode: Text.WordWrap
    }
}
