import QtQuick
import QtQuick.Layouts

RosterFilterList {
    id: root

    readonly property int tabHeight: 60

    signal selected(string key)

    Layout.fillWidth: true
    Layout.preferredHeight: tabHeight + (contentWidth > width ? 12 : 0)
    spacing: 8

    delegate: CabPageTab {
        required property var modelData
        width: Math.max(150, labelMetrics.advanceWidth + 24)
        height: root.tabHeight
        text: modelData.label
        autoExclusive: true
        checked: root.selectedKey === modelData.key
        onClicked: root.selected(modelData.key)

        TextMetrics {
            id: labelMetrics
            text: modelData.label
            font.bold: true
            font.pixelSize: 18
        }
    }
}
