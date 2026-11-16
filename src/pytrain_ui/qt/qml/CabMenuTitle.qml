import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root

    required property string title
    property string identity: ""
    property string identityObjectName: ""
    property bool compact: false
    property bool menuEnabled: true
    signal activated()

    spacing: 2
    activeFocusOnTab: menuEnabled
    Accessible.role: Accessible.Button
    Accessible.name: "Cab menu"
    Accessible.onPressAction: if (menuEnabled) activated()
    Keys.onReturnPressed: if (menuEnabled) activated()
    Keys.onSpacePressed: if (menuEnabled) activated()

    TapHandler {
        enabled: root.menuEnabled
        onTapped: root.activated()
    }

    Label {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        text: root.title + (root.menuEnabled ? "  ▾" : "")
        color: "#f4f6f8"
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        font.pixelSize: root.compact ? 20 : 24
        font.bold: true
    }

    Label {
        objectName: root.identityObjectName
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        text: root.identity
        visible: text.length > 0
        color: "#c7d1dd"
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: root.compact ? 16 : 20
    }
}
