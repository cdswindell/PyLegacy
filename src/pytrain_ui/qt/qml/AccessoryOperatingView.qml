import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var controller
    property var accessory: ({})
    property bool configurationVisible: false
    readonly property bool compact: height < 850
    readonly property bool hasArtwork: (accessory.artworkSource || "").length > 0
    readonly property real editorTop: pageLayout.y + cabHeader.y + cabHeader.height + 8
    readonly property string kind: accessory.kind || ""
    signal infoRequested(int tmccId)
    signal configureRequested(int tmccId)
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
        id: pageLayout
        anchors.fill: parent
        anchors.margins: 12
        anchors.leftMargin: 6
        anchors.rightMargin: anchors.leftMargin
        spacing: 10

        RowLayout {
            id: cabHeader
            Layout.fillWidth: true
            Layout.minimumHeight: titleControls.implicitHeight
            Layout.preferredHeight: Math.max(titleControls.implicitHeight, root.compact ? 76 : 96)
            spacing: 8

            CabButton {
                Layout.preferredWidth: root.compact ? 106 : 132
                Layout.preferredHeight: root.compact ? 72 : 88
                text: "Back"
                enabled: !root.configurationVisible
                font.pixelSize: root.compact ? 20 : 24
                onClicked: root.closeRequested()
            }

            CabMenuTitle {
                id: titleControls
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                compact: root.compact
                menuEnabled: !root.configurationVisible
                title: root.accessory.title || "Accessory"
                identity: root.accessory.tmccId ? "ACC " + root.accessory.tmccId : ""
                onActivated: root.cabMenuRequested()
            }

            AllStopButton {
                compact: root.compact
                onClicked: root.controller.halt()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            enabled: !root.configurationVisible
            visible: root.hasArtwork || !!root.accessory.tmccId
            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredHeight: root.hasArtwork ? Math.min(root.height * 0.23,
                    width / Math.max(1, Number(root.accessory.artworkAspectRatio || 3))) : 0

                Rectangle {
                    objectName: "accessoryArtwork"
                    anchors.fill: parent
                    visible: root.hasArtwork
                    color: root.kind === "AMC2" || root.kind === "SENSOR" ? "#e8ebef" : "#0f1216"
                    radius: 8
                    clip: true

                    Image {
                        anchors.fill: parent
                        source: root.accessory.artworkSource || ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }

                    TapHandler {
                        enabled: root.kind === "AMC2" && !!root.accessory.tmccId
                        gesturePolicy: TapHandler.DragThreshold
                        onDoubleTapped: root.infoRequested(root.accessory.tmccId)
                        onLongPressed: root.infoRequested(root.accessory.tmccId)
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: root.compact ? 108 : 132
                Layout.minimumWidth: Layout.preferredWidth
                Layout.maximumWidth: Layout.preferredWidth
                Layout.alignment: Qt.AlignVCenter
                spacing: 14

                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: (root.compact ? 48 : 56) * 1.1
                    text: "Info"
                    font.pixelSize: root.compact ? 17 : 20
                    enabled: !!root.accessory.tmccId
                    onClicked: root.infoRequested(root.accessory.tmccId)
                }

                CabButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: (root.compact ? 48 : 56) * 1.1
                    text: "Configure"
                    font.pixelSize: root.compact ? 17 : 20
                    visible: root.kind === "AMC2"
                    enabled: !!root.accessory.tmccId
                    onClicked: root.configureRequested(root.accessory.tmccId)
                }
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
            Layout.topMargin: root.kind === "AMC2" ? 12 : 0
            enabled: !root.configurationVisible
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
