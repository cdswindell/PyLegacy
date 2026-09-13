import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    visible: true
    width: 800
    height: 1280
    minimumWidth: 480
    minimumHeight: 720
    title: "PyTrain"

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 12

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: "PyTrain"
            font.pixelSize: 42
            font.bold: true
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: "Qt Quick presentation layer"
            font.pixelSize: 20
        }
    }
}
