import QtQuick
import QtQuick.Controls

ApplicationWindow {
    visible: true
    width: 800
    height: 1280
    minimumWidth: 480
    minimumHeight: 720
    title: "PyTrain — " + cabController.scope + " " + cabController.tmccId

    CabView {
        anchors.fill: parent
        anchors.margins: 24
        cab: cabController
    }
}
