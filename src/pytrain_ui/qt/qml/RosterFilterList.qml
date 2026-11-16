import QtQuick
import QtQuick.Controls

ListView {
    id: root

    required property string selectedKey

    orientation: ListView.Horizontal
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ScrollBar.horizontal: ListScrollBar {
        width: root.width
        height: 10
    }

    function revealSelected() {
        if (!visible || width <= 0 || !model)
            return
        const index = model.findIndex(filter => filter.key === selectedKey)
        if (index < 0)
            return
        forceLayout()
        positionViewAtIndex(index, ListView.Contain)
    }

    onVisibleChanged: if (visible) Qt.callLater(revealSelected)
    onWidthChanged: Qt.callLater(revealSelected)
    onModelChanged: Qt.callLater(revealSelected)
    onSelectedKeyChanged: Qt.callLater(revealSelected)
}
