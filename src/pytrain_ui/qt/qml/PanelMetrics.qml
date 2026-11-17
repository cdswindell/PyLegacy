import QtQml

QtObject {
    // Extra separation beyond the regular spacing within a button group.
    readonly property int sectionGap: 12
    readonly property int accessoryTabInset: 10
    readonly property int accessoryTabContentGap: 4
    readonly property int cabStateTilesBottomInset: 4
    function selectedEngineBarHeight(compact) {
        return compact ? 74 : 86
    }
    function footerOffset(rowHeight, layoutSpacing) {
        return Math.max(0, rowHeight - layoutSpacing)
    }
    function cabActionTileHeight(compact) {
        return compact ? 72 : 112
    }
    function cabActionIconSize(tileHeight, compact) {
        // Reserve the same space for the label and padding at both sizes.
        return Math.max(12, Math.min(compact ? 40 : 72, tileHeight - (compact ? 32 : 40)))
    }
    readonly property int editorButtonFontSize: 20
}
