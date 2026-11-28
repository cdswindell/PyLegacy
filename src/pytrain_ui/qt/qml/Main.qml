import QtQuick

CabWindow {
    id: host
    width: 720
    height: 1280
    minimumWidth: 480
    minimumHeight: workspaceItem.devicePreviewActive ? 400 : 720
    title: "PyTrain — " + workspaceItem.activePanelTitle
    readonly property var activeTarget: workspaceItem.activeTarget
    property alias activeScope: workspaceItem.activeScope
    property Item workspace: workspaceItem
    property var context_cabController: cabController
    property var context_managePyTrainController: managePyTrainController
    property var context_stateInfoController: stateInfoController
    property var context_accessoryCatalogController: accessoryCatalogController
    property var context_engineCatalogController: engineCatalogController
    property var context_trainLinkController: trainLinkController
    property var context_selectedEngineController: selectedEngineController
    property var context_switchOpsController: switchOpsController
    property var context_routeOpsController: routeOpsController
    property var context_lcsConfigController: lcsConfigController
    property var context_showCatalogAtStartup: showCatalogAtStartup
    CabWorkspace {
        id: workspaceItem
        anchors.fill: parent
        cabController: host.context_cabController
        managePyTrainController: host.context_managePyTrainController
        stateInfoController: host.context_stateInfoController
        accessoryCatalogController: host.context_accessoryCatalogController
        engineCatalogController: host.context_engineCatalogController
        trainLinkController: host.context_trainLinkController
        selectedEngineController: host.context_selectedEngineController
        switchOpsController: host.context_switchOpsController
        routeOpsController: host.context_routeOpsController
        lcsConfigController: host.context_lcsConfigController
        showCatalogAtStartup: host.context_showCatalogAtStartup
        onWindowSizeRequested: (displayWidth, displayHeight) => {
            host.width = displayWidth
            host.height = displayHeight
        }
    }
}
