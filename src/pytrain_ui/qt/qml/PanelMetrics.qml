import QtQml

QtObject {
    // Extra separation beyond the regular spacing within a button group.
    readonly property int sectionGap: 12
    function footerOffset(rowHeight, layoutSpacing) {
        return Math.max(0, rowHeight - layoutSpacing)
    }
    readonly property int editorButtonFontSize: 20
}
