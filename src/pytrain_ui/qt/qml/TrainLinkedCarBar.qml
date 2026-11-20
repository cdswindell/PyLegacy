import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    objectName: "trainLinkedCarBar"
    signal carRequested(int tmccId)
    required property var links
    readonly property var carRows: links ? links.rows : []
    color: "#0d1f58"
    radius: 8
    border.width: 1
    border.color: "#5275a4"

    Label {
        id: boxTitle
        anchors.left: parent.left
        anchors.leftMargin: 10
        y: -implicitHeight / 2
        leftPadding: 6
        rightPadding: 6
        text: "Train-linked Cars"
        color: "#bad4ea"
        font.pixelSize: 14
        background: Rectangle { color: root.color }
    }

    Label {
        objectName: "noTrainLinkedCars"
        anchors.centerIn: parent
        visible: root.carRows.length === 0
        text: "None"
        color: "#bad4ea"
        font.pixelSize: 17
    }

    ListView {
        id: cars
        objectName: "trainLinkedCarList"
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        anchors.topMargin: 12
        anchors.bottomMargin: overflow ? 18 : 6
        readonly property bool overflow: contentWidth > width + 1
        orientation: ListView.Horizontal
        spacing: 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.carRows
        ScrollBar.horizontal: ScrollBar {
            objectName: "trainLinkedCarScrollIndicator"
            // Keep the indicator outside the clipped list viewport.
            parent: root
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            anchors.bottomMargin: 4
            policy: cars.overflow ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            height: 8
            active: cars.overflow
            contentItem: Rectangle { radius: 3; color: "#82bedb" }
            background: Rectangle { radius: 3; color: "#162a3d" }
        }

        delegate: Rectangle {
            id: card
            objectName: "trainLinkedCar-" + modelData.tmccId
            required property var modelData
            width: Math.min(244, Math.max(1, Math.floor((cars.width - cars.spacing * 2) / 3)))
            height: cars.height - 2
            anchors.verticalCenter: parent ? parent.verticalCenter : undefined
            radius: 7
            color: root.links.selectedId === modelData.tmccId ? "#246aa0" : "#292f38"
            border.color: "#505b68"
            clip: true
            Accessible.role: Accessible.Button
            Accessible.name: "Train-linked Car " + modelData.tmccId + ", " + modelData.roadName + " " + modelData.roadNumber

            TapHandler {
                gesturePolicy: TapHandler.DragThreshold
                onTapped: root.carRequested(card.modelData.tmccId)
            }

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6
                Label {
                    text: card.modelData.tmccId
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
                        text: card.modelData.roadName + (card.modelData.roadNumber ? " #" + card.modelData.roadNumber : "")
                        color: "#f4f6f8"
                        font.pixelSize: 16
                    }
                    Label {
                        objectName: "trainLinkedCarType-" + card.modelData.tmccId
                        text: card.modelData.engineType
                        color: "#aeb7c2"
                        font.pixelSize: 12
                    }
                }
            }
        }
    }
}
