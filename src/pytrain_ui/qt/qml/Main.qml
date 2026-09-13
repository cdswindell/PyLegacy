import QtQuick
import QtQuick.Controls

ApplicationWindow {
    visible: true
    width: 800
    height: 1280
    minimumWidth: 480
    minimumHeight: 720
    title: "PyTrain — " + cab.scope + " " + cab.tmccId

    CabView {
        anchors.fill: parent
        anchors.margins: 24
        cab: cab
    }
}
