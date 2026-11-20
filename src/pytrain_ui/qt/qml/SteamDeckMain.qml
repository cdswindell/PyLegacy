import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

CabWindow {
    id: host
    width: deckWindowWidth
    height: deckWindowHeight
    onActiveChanged: if (!active) deckController.release()
    minimumWidth: 960
    minimumHeight: 640
    title: "PyTrain — " + (deckController.focusedPane === "left" ? leftWorkspace.activePanelTitle : rightWorkspace.activePanelTitle)
    property Item leftPane: leftWorkspace
    property Item rightPane: rightWorkspace
    RowLayout {
        anchors.fill: parent
        spacing: 2
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: deckController.focusedPane === "left" ? "#6bc9f1" : "#243d57"
            CabWorkspace {
                id: leftWorkspace
                objectName: "leftWorkspace"
                anchors.fill: parent
                anchors.margins: 3
                deckPane: true
                inputActive: deckController.focusedPane === "left"
                cabController: leftCabController
                managePyTrainController: leftManagePyTrainController
                stateInfoController: leftStateInfoController
                accessoryCatalogController: leftAccessoryCatalogController
                engineCatalogController: leftEngineCatalogController
                trainLinkController: leftTrainLinkController
                selectedEngineController: leftSelectedEngineController
                switchOpsController: leftSwitchOpsController
                routeOpsController: leftRouteOpsController
                lcsConfigController: leftLcsConfigController
                showCatalogAtStartup: leftShowCatalogAtStartup
            }
            TapHandler {
                gesturePolicy: TapHandler.DragThreshold
                onPressedChanged: if (pressed) deckController.focusPane("left")
            }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: deckController.focusedPane === "right" ? "#6bc9f1" : "#243d57"
            CabWorkspace {
                id: rightWorkspace
                objectName: "rightWorkspace"
                anchors.fill: parent
                anchors.margins: 3
                deckPane: true
                inputActive: deckController.focusedPane === "right"
                cabController: rightCabController
                managePyTrainController: rightManagePyTrainController
                stateInfoController: rightStateInfoController
                accessoryCatalogController: rightAccessoryCatalogController
                engineCatalogController: rightEngineCatalogController
                trainLinkController: rightTrainLinkController
                selectedEngineController: rightSelectedEngineController
                switchOpsController: rightSwitchOpsController
                routeOpsController: rightRouteOpsController
                lcsConfigController: rightLcsConfigController
                showCatalogAtStartup: rightShowCatalogAtStartup
            }
            TapHandler {
                gesturePolicy: TapHandler.DragThreshold
                onPressedChanged: if (pressed) deckController.focusPane("right")
            }
        }
    }
    Popup {
        id: helpPopup
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(host.width - 40, 760)
        height: host.height - 60
        visible: deckController.controlsVisible
        modal: true
        closePolicy: Popup.CloseOnEscape
        onClosed: deckController.closeControls()
        background: Rectangle { color: "#102858"; border.color: "#6bc9f1"; radius: 12 }
        ColumnLayout {
            anchors.fill: parent
            ScrollView {
                id: helpScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                TextArea {
                    readOnly: true
                    text: deckController.controlsText
                    color: "#ffffff"
                    font.pixelSize: 20
                    wrapMode: TextEdit.Wrap
                }
            }
            FunctionButton {
                Layout.fillWidth: true
                text: "Close"
                onClicked: deckController.closeControls()
            }
        }
        Connections {
            target: deckController
            function onHelpPageRequested(direction) {
                const view = helpScroll.contentItem
                view.contentY = Math.max(0, Math.min(view.contentHeight - view.height,
                                                    view.contentY + direction * view.height / 2))
            }
        }
    }

}
