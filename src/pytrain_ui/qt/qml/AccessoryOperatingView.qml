import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var controller
    property var accessory: ({})
    readonly property string kind: accessory.kind || ""
    signal infoRequested(int tmccId)
    signal closeRequested()
    signal cabMenuRequested()

    color: "#102858"
    radius: 10

    function operationSource(operation) {
        if (operation.state === "ON" && operation.onImageSource)
            return operation.onImageSource
        if (operation.state === "OFF" && operation.offImageSource)
            return operation.offImageSource
        return operation.imageSource || operation.onImageSource || operation.offImageSource || ""
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        anchors.leftMargin: 6
        anchors.rightMargin: anchors.leftMargin
        spacing: 10

        RowLayout {
            Layout.fillWidth: true

            CabButton {
                Layout.preferredWidth: 96
                Layout.preferredHeight: 46
                text: "Back"
                onClicked: root.closeRequested()
            }

            RosterMenuButton {
                text: (root.accessory.title || "Accessory") + (root.accessory.tmccId ? " · " + root.accessory.tmccId : "")
                font.pixelSize: 24
                onClicked: root.cabMenuRequested()
            }

            CabButton {
                Layout.preferredWidth: 96
                text: "Info"
                enabled: !!root.accessory.tmccId
                onClicked: root.infoRequested(root.accessory.tmccId)
            }

            AllStopButton {
                compact: root.height < 850
                onClicked: root.controller.halt()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(root.height * 0.23, width / Math.max(1, Number(root.accessory.artworkAspectRatio || 3)))
            visible: (root.accessory.artworkSource || "").length > 0
            color: "#0f1216"
            radius: 8
            clip: true

            Image {
                anchors.fill: parent
                source: root.accessory.artworkSource || ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: root.kind === "OPERATING"

            Label {
                text: "Power"
                color: "#aeb7c2"
                font.pixelSize: 14
            }
            Label {
                text: root.accessory.powerState || "UNKNOWN"
                color: root.accessory.powerState === "ON" ? "#62d98b" :
                       root.accessory.powerState === "OFF" ? "#8fc9ef" : "#e9c46a"
                font.pixelSize: 16
                font.bold: true
            }
            Label {
                visible: root.accessory.powerStateAuthoritative === true
                text: "LCS"
                color: "#8fa2b5"
                font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
        }

        AccessoryDeviceControls {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.kind !== "" && root.kind !== "OPERATING"
            controller: root.controller
            accessory: root.accessory
        }

        ListView {
            id: operationList
            visible: root.kind === "OPERATING"
            ScrollBar.vertical: ListScrollBar {}
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: root.accessory.operations || []

            delegate: Rectangle {
                id: operationRow
                required property var modelData
                width: ListView.view.width
                height: Math.max(104, Math.min(190, Number(modelData.height || 120)))
                radius: 8
                color: "#272d35"
                border.width: 1
                border.color: "#4b5664"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 9
                    spacing: 10

                    Rectangle {
                        Layout.preferredWidth: Math.min(230, operationRow.width * 0.34)
                        Layout.fillHeight: true
                        visible: root.operationSource(operationRow.modelData).length > 0
                        color: "#11151a"
                        radius: 6
                        clip: true

                        AnimatedImage {
                            anchors.fill: parent
                            source: root.operationSource(operationRow.modelData)
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            playing: operationRow.modelData.animationRunning === true
                            visible: source.toString().toLowerCase().endsWith(".gif")
                        }

                        Image {
                            anchors.fill: parent
                            source: root.operationSource(operationRow.modelData)
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            visible: !source.toString().toLowerCase().endsWith(".gif")
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 4

                        Label {
                            Layout.fillWidth: true
                            text: operationRow.modelData.label
                            color: "#f4f6f8"
                            font.pixelSize: 18
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            text: "TMCC " + operationRow.modelData.tmccId + " · " +
                                  operationRow.modelData.behavior.replace("_", " ")
                            color: "#aeb7c2"
                            font.pixelSize: 12
                        }
                        Label {
                            text: operationRow.modelData.state
                            color: operationRow.modelData.state === "ON" ? "#62d98b" :
                                   operationRow.modelData.state === "OFF" ? "#8fc9ef" : "#e9c46a"
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Item { Layout.fillHeight: true }


                    }
                }
            }
        }
    }
}
