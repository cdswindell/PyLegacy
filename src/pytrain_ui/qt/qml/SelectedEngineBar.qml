import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    objectName: "activeEngineTrainBar"
    required property var selection
    signal trainSelected(int tmccId)

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
    border.width: 1
    border.color: "#5275a4"

    Label {
        objectName: "activeEngineTrainTitle"
        anchors.left: parent.left
        anchors.leftMargin: 10
        y: -implicitHeight / 2
        leftPadding: 6
        rightPadding: 6
        text: "Active Engines and Trains"
        color: "#bad4ea"
        font.pixelSize: 14
        background: Rectangle { color: root.color }
    }

    ListView {
        id: selectedList
        objectName: "activeEngineTrainList"
        readonly property bool overflow: contentWidth > width + 1
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        anchors.topMargin: 12
        anchors.bottomMargin: overflow ? 18 : 6
        orientation: ListView.Horizontal
        spacing: root.compactTiles ? 4 : 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.selection ? root.selection.selectedEngines : []
        ScrollBar.horizontal: ScrollBar {
            objectName: "activeEngineTrainScrollIndicator"
            parent: root
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            anchors.bottomMargin: 4
            policy: selectedList.overflow ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            height: 8
            active: selectedList.overflow
            contentItem: Rectangle { radius: 3; color: "#82bedb" }
            background: Rectangle { radius: 3; color: "#162a3d" }
        }

        delegate: Rectangle {
            id: card
            objectName: "activeTile-" + modelData.scope + "-" + modelData.tmccId
            required property var modelData

            readonly property bool train: modelData.scope === "TRAIN"
            width: root.compactTiles ? 204 : 244
            height: selectedList.height - 2
            anchors.verticalCenter: parent ? parent.verticalCenter : undefined
            radius: 7
            readonly property bool trainLinked: !train && modelData.trainLinked === true
            readonly property bool trainMember: !train && modelData.trainId > 0
            color: cardTap.pressed ? Qt.darker(card.train ? "#b3a0e0" : "#64a9d2", 1.45) : card.train ? "#37334e" : card.trainLinked ? "#36556f" : card.trainMember ? "#335b58" : modelData.current ? "#246aa0" : "#292f38"
            border.width: modelData.current ? 2 : 1
            border.color: card.train ? "#b3a0e0" : card.trainLinked ? "#86acc9" : card.trainMember ? "#83cabc" : modelData.current ? "#78bff0" : (modelData.active ? "#d0a24c" : "#505b68")
            clip: true

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: root.compactTiles ? 6 : 8
                anchors.rightMargin: root.compactTiles ? 3 : 5
                spacing: root.compactTiles ? 3 : 5

                ColumnLayout {
                    spacing: 0
                    Label {
                        objectName: "activeTargetKind-" + card.modelData.scope + "-" + card.modelData.tmccId
                        Layout.alignment: Qt.AlignHCenter
                        text: card.modelData.kind || (card.train ? "TRN" : "ENG")
                        color: card.train ? "#d6c6f6" : "#9aafc2"
                        font.pixelSize: 10
                        font.bold: true
                    }
                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: card.modelData.tmccId
                        color: "white"
                        font.pixelSize: root.compactTiles ? 18 : 20
                        font.bold: true
                    }
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
                            const name = card.modelData.roadName || (card.train ? "Train" : "Engine")
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
                            if (card.train)
                                root.selection.dismissTrain(card.modelData.tmccId)
                            else
                                root.selection.dismissEngine(card.modelData.tmccId)
                    }
                }
            }

            TapHandler {
                id: cardTap
                gesturePolicy: TapHandler.DragThreshold
                onTapped: {
                    if (root.selection)
                        if (card.train)
                            root.trainSelected(card.modelData.tmccId)
                        else
                            root.selection.selectEngine(card.modelData.tmccId)
                }
            }
        }
    }
}
