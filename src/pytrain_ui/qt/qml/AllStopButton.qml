import QtQuick
import QtQuick.Layouts

CabButton {
    property bool compact: false
    objectName: "allStopButton"
    Layout.minimumWidth: compact ? 106 : 132
    Layout.maximumWidth: compact ? 106 : 132
    Layout.preferredWidth: compact ? 106 : 132
    Layout.minimumHeight: compact ? 72 : 88
    Layout.maximumHeight: compact ? 72 : 88
    Layout.preferredHeight: compact ? 72 : 88
    text: "ALL STOP"
    font.pixelSize: compact ? 18 : 22
    font.bold: true
    normalColor: "#9d2020"
    pressedColor: "#c62d2d"
}
