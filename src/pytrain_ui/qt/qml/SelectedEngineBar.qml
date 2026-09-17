import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var selection

    color: "#15191f"
    radius: 8
    clip: true

    ListView {
        id: selectedList
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        orientation: ListView.Horizontal
        spacing: 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.selection ? root.selection.selectedEngines : []

        delegate: Rectangle {
            id: card
            required property var modelData

            width: 170
            height: selectedList.height - 6
            anchors.verticalCenter: parent ? parent.verticalCenter : undefined
            radius: 7
            color: modelData.current ? "#246aa0" : "#292f38"
            border.width: modelData.current ? 2 : 1
            border.color: modelData.current ? "#78bff0" : (modelData.active ? "#d0a24c" : "#505b68")

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 5
                spacing: 5

                Label {
                    text: modelData.tmccId
                    color: "white"
                    font.pixelSize: 15
                    font.bold: true
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    Item {
                        id: nameViewport
                        Layout.fillWidth: true
                        Layout.preferredHeight: 15
                        clip: true

                        readonly property real marqueeGap: 18
                        readonly property real marqueeDistance: nameText.width + marqueeGap

                        Row {
                            id: marqueeRow
                            y: 0
                            spacing: nameViewport.marqueeGap

                            Text {
                                id: nameText
                                text: card.modelData.roadName || "Engine"
                                color: "#f4f6f8"
                                font.pixelSize: 11
                                font.bold: card.modelData.current
                                verticalAlignment: Text.AlignVCenter
                            }

                            Text {
                                visible: nameText.width > nameViewport.width
                                text: nameText.text
                                color: nameText.color
                                font: nameText.font
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        SequentialAnimation {
                            running: nameText.width > nameViewport.width
                            loops: Animation.Infinite

                            PauseAnimation { duration: 900 }
                            NumberAnimation {
                                target: marqueeRow
                                property: "x"
                                from: 0
                                to: -nameViewport.marqueeDistance
                                duration: Math.max(1200, nameViewport.marqueeDistance * 18)
                                easing.type: Easing.Linear
                            }
                            ScriptAction { script: marqueeRow.x = 0 }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Label {
                            visible: text.length > 0
                            text: modelData.roadNumber || ""
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 9
                        }
                        Label {
                            text: modelData.direction
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 9
                        }
                        Label {
                            text: "SP " + modelData.speed
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 9
                        }
                        Label {
                            Layout.fillWidth: true
                            text: "SM " + modelData.smoke
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 9
                            horizontalAlignment: Text.AlignLeft
                        }
                    }
                }

                CabButton {
                    visible: root.selection ? root.selection.count > 1 : false
                    Layout.preferredWidth: visible ? 28 : 0
                    Layout.preferredHeight: 28
                    text: "×"
                    font.pixelSize: 16
                    normalColor: "#343a44"
                    pressedColor: "#4d5968"
                    onClicked: {
                        if (root.selection)
                            root.selection.dismissEngine(card.modelData.tmccId)
                    }
                }
            }

            TapHandler {
                gesturePolicy: TapHandler.DragThreshold
                onTapped: {
                    if (root.selection)
                        root.selection.selectEngine(card.modelData.tmccId)
                }
            }
        }
    }
}
