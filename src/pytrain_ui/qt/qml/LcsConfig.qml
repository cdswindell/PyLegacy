import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    required property var controller

    anchors.centerIn: Overlay.overlay
    width: Math.min(parent ? parent.width - 32 : 688, 688)
    height: Math.min(parent ? parent.height - 48 : 1180, 1180)
    modal: true
    focus: true
    closePolicy: Popup.NoAutoClose

    onOpened: controller.reset()

    background: Rectangle {
        color: "#171b20"
        radius: 14
        border.width: 1
        border.color: "#59616c"
    }

    contentItem: ColumnLayout {
        spacing: 12

        Label {
            Layout.fillWidth: true
            text: "LCS Module Configuration"
            color: "#f4f6f8"
            font.pixelSize: 26
            font.bold: true
        }

        Label {
            Layout.fillWidth: true
            text: "Which module are you configuring?"
            color: "#aeb5bf"
            font.pixelSize: 16
        }

        Repeater {
            model: root.controller ? root.controller.devices : []

            delegate: CabButton {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 70
                highlighted: root.controller.deviceKey === modelData.key
                text: modelData.label + (modelData.blurb.length ? "   " + modelData.blurb : "")
                font.bold: highlighted
                onClicked: root.controller.selectDevice(modelData.key)
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.controller && root.controller.deviceKey.length > 0
            text: {
                if (!root.controller)
                    return ""
                const rows = root.controller.devices
                for (let i = 0; i < rows.length; ++i) {
                    if (rows[i].key === root.controller.deviceKey)
                        return rows[i].warning
                }
                return ""
            }
            color: "#f0c36a"
            font.pixelSize: 14
            wrapMode: Text.WordWrap
        }

        Item {
            Layout.fillHeight: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 52
                text: "CANCEL"
                onClicked: root.close()
            }

            CabButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.preferredHeight: 52
                text: "NEXT"
                font.bold: true
                enabled: root.controller && root.controller.deviceKey.length > 0
            }
        }
    }
}
