import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var selection

    color: "#15191f"
    radius: 8
    clip: true

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 6

        Label {
            text: "SELECTED"
            color: "#9ea6b0"
            font.pixelSize: 10
            font.bold: true
        }

        ListView {
            id: selectedList
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: ListView.Horizontal
            spacing: 6
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.selection ? root.selection.selectedEngines : []

            delegate: Rectangle {
                id: card
                required property var modelData

                width: 185
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
                    spacing: 6

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

                            Text {
                                id: nameText
                                y: 0
                                text: card.modelData.roadName || "Engine"
                                color: "#f4f6f8"
                                font.pixelSize: 11
                                font.bold: card.modelData.current
                                verticalAlignment: Text.AlignVCenter

                                SequentialAnimation on x {
                                    running: nameText.width > nameViewport.width
                                    loops: Animation.Infinite
                                    PauseAnimation { duration: 1200 }
                                    NumberAnimation {
                                        from: 0
                                        to: Math.min(0, nameViewport.width - nameText.width - 8)
                                        duration: Math.max(800, (nameText.width - nameViewport.width) * 18)
                                        easing.type: Easing.Linear
                                    }
                                    PauseAnimation { duration: 900 }
                                    NumberAnimation {
                                        to: 0
                                        duration: 300
                                        easing.type: Easing.OutQuad
                                    }
                                }
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: (modelData.roadNumber ? modelData.roadNumber + "   " : "") +
                                  modelData.direction + "   SM " + modelData.smoke + "   SP " + modelData.speed
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 9
                            elide: Text.ElideRight
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
}
