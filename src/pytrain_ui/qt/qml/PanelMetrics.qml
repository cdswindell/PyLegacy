import QtQml

QtObject {
    // Extra separation beyond the regular spacing within a button group.
    readonly property int sectionGap: 12
    readonly property int accessoryTabInset: 10
    readonly property int accessoryTabContentGap: 4
    function footerOffset(rowHeight, layoutSpacing) {
        return Math.max(0, rowHeight - layoutSpacing)
    }
    readonly property int editorButtonFontSize: 20
}
