import QtQuick
import QtQuick.Layouts

GridLayout {
    id: root

    PanelMetrics { id: metrics }
    required property int tmccId
    required property bool compact
    property bool accScope: false
    property var keyLabels: ({})
    signal commandRequested(string command, int value)

    columns: 4
    rows: accScope ? 5 : 6
    columnSpacing: 7
    rowSpacing: 7
    readonly property real keyHeight: Math.max(1, (height - (rows - 1) * rowSpacing) / rows)

    Repeater {
        // Recreate pressed keys when changing targets so a hold cannot continue on another ID.
        model: root.visible && root.tmccId > 0 ? (root.accScope ? [] : [
            {label: "Start Up", command: "START_UP_IMMEDIATE", icon: "power-on"},
            {label: "Shut Down", command: "SHUTDOWN_IMMEDIATE", icon: "power-off"},
            null,
            {label: "Set", command: "SET_ADDRESS"}
        ]).concat([
            {digit: 1, icon: "volume", description: "Volume up"},
            {digit: 2, icon: "crew", description: "Crew"},
            {digit: 3, icon: "numeric-up", description: "Up arrow", small: true},
            {label: "Front Coupler", command: "FRONT_COUPLER", icon: "coupler-front"},
            {digit: 4, icon: "volume-down", description: "Volume down"},
            {digit: 5, glyph: "●", description: "Filled circle"},
            {digit: 6, icon: "numeric-down", description: "Down arrow", small: true},
            {label: "Rear Coupler", command: "REAR_COUPLER", icon: "coupler-rear"},
            {digit: 7, icon: "tower", description: "Tower"},
            {digit: 8, glyph: "−", description: "Minus"},
            {digit: 9, glyph: "+", description: "Plus"},
            {label: "Boost", command: "BOOST", icon: "boost", interval: 250},
            root.accScope ? null : {label: "Horn", command: "HORN", icon: "horn", interval: 100},
            {digit: 0, description: "Reset"},
            root.accScope ? {label: "Set", command: "SET_ADDRESS"} : {label: "Bell", command: "BELL", icon: "bell"},
            {label: "Brake", command: "BRAKE", icon: "brake", interval: 250},
            {label: "Aux 1", command: "AUX1_OPT_ONE", interval: 100},
            {label: "Aux 2", command: "AUX2_OPT_ONE"},
            {label: "Aux 3", command: "AUX3_OPT_ONE"},
            null
        ]) : []
        delegate: Loader {
            id: cell

            required property int index
            required property var modelData
            Layout.row: Math.floor(index / root.columns)
            Layout.column: index % root.columns
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredWidth: 1
            Layout.preferredHeight: root.keyHeight
            Layout.minimumHeight: root.keyHeight
            Layout.maximumHeight: root.keyHeight
            active: modelData !== null

            sourceComponent: FunctionButton {
                readonly property var key: cell.modelData
                readonly property bool numeric: key.digit !== undefined
                objectName: "accessoryCabKey_" + (numeric ? key.digit : key.command)
                enabled: root.tmccId >= 1 && root.tmccId <= 98 && !(root.accScope && key.command === "AUX3_OPT_ONE")
                readonly property string commandKey: numeric ? "NUMERIC:" + key.digit : key.command
                text: root.keyLabels[commandKey] || (numeric ? String(key.digit) : key.label)
                Accessible.name: numeric ? key.description + ", " + text : text
                trialIcon: key.icon || ""
                iconGlyph: key.glyph || ""
                stopSign: numeric && key.digit === 0
                octagonLabel: "R"
                stacked: true
                padding: 3
                fitLabelWidth: true
                labelSideInset: metrics.cabActionLabelInset
                iconSize: Math.max(10, Math.min(width - 8,
                    metrics.cabActionIconSize(height, root.compact) * (key.small ? 0.65 : 1)))
                font.pixelSize: metrics.cabActionLabelSize(root.compact) + (key.label && !key.icon ? 6 : 0)
                font.bold: key.command === "SET_ADDRESS" || /^Aux [123]$/.test(key.label || "")
                showRepeatDecorator: repeatWhileHeld
                repeatWhileHeld: numeric || !!key.interval
                repeatInterval: numeric ? 100 : (key.interval || 250)
                onClicked: root.commandRequested(numeric ? "NUMERIC" : key.command, numeric ? key.digit : 0)
            }
        }
    }
}
