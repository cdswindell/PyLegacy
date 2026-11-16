import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    required property var selection

    readonly property bool compactTiles: selection ? selection.count > 4 : false

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

            width: root.compactTiles ? 204 : 244
            height: selectedList.height - 2
            anchors.verticalCenter: parent ? parent.verticalCenter : undefined
            radius: 7
            color: cardTap.pressed ? Qt.darker("#64a9d2", 1.45) : modelData.current ? "#246aa0" : "#292f38"
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
                    font.pixelSize: 20
                    font.bold: true
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 0

                    MarqueeLabel {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: 22
                        text: {
                            const name = card.modelData.roadName || "Engine"
                            const number = card.modelData.roadNumber ? "#" + card.modelData.roadNumber : ""
                            return number.length > 0 ? name + " " + number : name
                        }
                        color: "#f4f6f8"
                        font.pixelSize: 16
                        font.bold: card.modelData.current
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 3

                        Label {
                            visible: root.compactTiles
                            text: modelData.tmccId
                            color: "white"
                            font.pixelSize: 18
                            font.bold: true
                        }
                        Item {
                            Layout.preferredWidth: root.compactTiles && String(modelData.tmccId).length >= 4 ? 0 : 3
                        }
                        Label {
                            text: modelData.direction
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 12
                        }
                        Label {
                            text: "SP " + modelData.speed
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 12
                        }
                        Label {
                            text: "SM " + modelData.smoke
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 12
                        }
                        Label {
                            visible: !root.compactTiles
                            text: "M " + root.shortState(modelData.momentum)
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 12
                        }
                        Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            visible: !root.compactTiles
                            text: "B " + root.shortState(modelData.brake)
                            color: modelData.current ? "#dceffc" : "#aeb7c2"
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignLeft
                            elide: Text.ElideRight
                        }
                    }
                }

                CabButton {
                    Layout.minimumWidth: 44
                    Layout.maximumWidth: 44
                    Layout.preferredWidth: 44
                    Layout.minimumHeight: 44
                    Layout.maximumHeight: 44
                    Layout.preferredHeight: 44
                    text: "×"
                    font.pixelSize: root.compactTiles ? 14 : 16
                    pressedColor: "#4d7ba0"
                    onClicked: {
                        if (root.selection)
                            root.selection.dismissEngine(card.modelData.tmccId)
                    }
                }
            }

            TapHandler {
                id: cardTap
                gesturePolicy: TapHandler.DragThreshold
                onTapped: {
                    if (root.selection)
                        root.selection.selectEngine(card.modelData.tmccId)
                }
            }
        }
    }
}
