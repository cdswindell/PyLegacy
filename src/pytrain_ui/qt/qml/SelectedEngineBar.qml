import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var selection

    readonly property bool compactTiles: selection ? selection.count > 4 : false

    function roadNumber(number) {
        const raw = String(number || "")
        if (raw.length === 0)
            return ""
        const stripped = raw.replace(/^0+/, "")
        return "#" + (stripped.length > 0 ? stripped : "0")
    }

    function shortState(value) {
        const raw = String(value || "-")
        const upper = raw.toUpperCase()
        if (upper.indexOf("LOW") >= 0)
            return "L"
        if (upper.indexOf("MED") >= 0)
            return "M"
        if (upper.indexOf("HIGH") >= 0)
            return "H"
        if (upper.indexOf("OFF") >= 0 || upper.indexOf("NONE") >= 0)
            return "-"
        return raw
    }

    color: "#15191f"
    radius: 8
    clip: true

    ListView {
        id: selectedList
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        orientation: ListView.Horizontal
        spacing: root.compactTiles ? 4 : 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.selection ? root.selection.selectedEngines : []

        delegate: Rectangle {
            id: card
            required property var modelData

            width: root.compactTiles ? 137 : 170
            height: selectedList.height - 6
            anchors.verticalCenter: parent ? parent.verticalCenter : undefined
            radius: 7
            color: modelData.current ? "#246aa0" : "#292f38"
            border.width: modelData.current ? 2 : 1
            border.color: modelData.current ? "#78bff0" : (modelData.active ? "#d0a24c" : "#505b68")
            clip: true

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: root.compactTiles ? 6 : 8
                anchors.rightMargin: root.compactTiles ? 3 : 5
                spacing: root.compactTiles ? 3 : 5

                Label {
                    visible: !root.compactTiles
                    text: modelData.tmccId
                    color: "white"
                    font.pixelSize: 15
                    font.bold: true
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 0

                    Item {
                        id: nameViewport
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
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
                                text: {
                                    const name = card.modelData.roadName || "Engine"
                                    const number = root.roadNumber(card.modelData.roadNumber)
                                    return number.length > 0 ? name + " " + number : name
                                }
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
                        Layout.minimumWidth: 0
                        spacing: 3

                        Label {
                            visible: root.compactTiles
                            text: modelData.tmccId
                            color: "white"
                            font.pixelSize: 12
                            font.bold: true
                        }
                        Item {
                            Layout.preferredWidth: root.compactTiles && String(modelData.tmccId).length >= 4 ? 0 : 3
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
                            text: "SM " + modelData.smoke
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 9
                        }
                        Label {
                            visible: !root.compactTiles
                            text: "M " + root.shortState(modelData.momentum)
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 9
                        }
                        Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            visible: !root.compactTiles
                            text: "B " + root.shortState(modelData.brake)
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 9
                            horizontalAlignment: Text.AlignLeft
                            elide: Text.ElideRight
                        }
                    }
                }

                CabButton {
                    Layout.minimumWidth: root.compactTiles ? 24 : 28
                    Layout.maximumWidth: root.compactTiles ? 24 : 28
                    Layout.preferredWidth: root.compactTiles ? 24 : 28
                    Layout.minimumHeight: root.compactTiles ? 24 : 28
                    Layout.maximumHeight: root.compactTiles ? 24 : 28
                    Layout.preferredHeight: root.compactTiles ? 24 : 28
                    text: "×"
                    font.pixelSize: root.compactTiles ? 14 : 16
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
