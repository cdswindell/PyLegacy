import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    PanelMetrics { id: metrics }
    required property var controller
    required property var accessory
    readonly property string accessoryKey: accessory.key || ""
    readonly property bool motorsSelected: tabs.currentIndex === 0
    onAccessoryKeyChanged: tabs.currentIndex = 0

    Rectangle {
        anchors.fill: parent
        anchors.topMargin: tabs.height - 1
        radius: 8
        color: "#16376b"
        border.color: "#5275a4"
    }

    TabBar {
        id: tabs
        objectName: "amc2Tabs"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.topMargin: metrics.accessoryTabInset
        width: parent.width * 2 / 3
        height: 56
        spacing: 6
        padding: 0
        background: Item {}
        CabPageTab { text: "Motors"; height: tabs.height }
        CabPageTab { text: "Lights"; height: tabs.height }
    }

    RowLayout {
        readonly property int defaultGap: 8
        // The original pair occupied the panel width minus two margins and one gap.
        readonly property real motorGap: (root.width - (root.width - 3 * defaultGap) * 0.8) / 3

        anchors.fill: parent
        anchors.topMargin: tabs.height + metrics.accessoryTabContentGap
        anchors.leftMargin: spacing
        anchors.rightMargin: spacing
        anchors.bottomMargin: defaultGap
        spacing: root.motorsSelected ? motorGap : defaultGap

        Repeater {
            model: root.visible ? (root.motorsSelected ? 2 : 4) : 0

            delegate: Rectangle {
                id: channel
                required property int index
                readonly property int output: index + 1
                readonly property var readings: (root.motorsSelected ? root.accessory.motors : root.accessory.lights) || []
                readonly property var observed: readings[index] || ({level: 0, on: false})
                readonly property string label: (root.motorsSelected ? "Motor " : "Light ") + output
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                Layout.minimumWidth: 0
                radius: 8
                color: "#102858"
                border.color: "#375983"

                function setLevel(level) {
                    root.controller.setAmc2Output(root.accessoryKey, root.motorsSelected, output, level)
                }

                function setPower(on) {
                    root.controller.setAmc2Power(root.accessoryKey, root.motorsSelected, output, on)
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 4

                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: channel.label
                        color: "white"
                        font.bold: true
                        font.pixelSize: 20
                    }

                    VerticalThrottle {
                        objectName: "amc2Slider" + channel.output
                        Layout.fillHeight: true
                        Layout.preferredHeight: 180
                        Layout.minimumHeight: 76
                        Layout.preferredWidth: Math.min(144, channel.width - 12)
                        Layout.alignment: Qt.AlignHCenter
                        minimumValue: 0
                        maximumValue: 100
                        scaleStep: 25
                        thumbScale: 1.25
                        value: channel.observed.level
                        handleCaption: ""
                        valueSuffix: "%"
                        muted: !channel.observed.on
                        opacity: muted ? 0.66 : 1
                        Accessible.name: channel.label + " level"
                        onValueCommitted: level => channel.setLevel(level)
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 5

                        CabButton {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: 1
                            Layout.preferredHeight: 72
                            text: "On"
                            selected: channel.observed.on
                            distinguishDoubleClick: true
                            onClicked: channel.setPower(true)
                            onDoubleClicked: channel.setLevel(100)
                        }
                        CabButton {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: 1
                            Layout.preferredHeight: 72
                            text: "Off"
                            selected: !channel.observed.on
                            distinguishDoubleClick: true
                            onClicked: channel.setPower(false)
                            onDoubleClicked: channel.setLevel(0)
                        }
                    }
                }
            }
        }
    }
}
