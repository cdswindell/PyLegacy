import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    required property real headerWidth
    required property real headerSpacing
    required property real stopWidth
    required property font titleFont
    property bool paired: true
    readonly property real titleRightMargin: {
        const titleWidth = headerWidth - Layout.preferredWidth - stopWidth - 2 * headerSpacing
        return Math.max(0, Math.min(Layout.preferredWidth - stopWidth, titleWidth - titleMetrics.advanceWidth - 8))
    }

    Layout.fillWidth: false
    Layout.preferredWidth: {
        if (!paired)
            return stopWidth
        const centeredTitleStart = (headerWidth - titleMetrics.advanceWidth) / 2
        // Two equal buttons, their spacing, and a quarter-button gap before the title.
        return 2 * Math.max(82, Math.floor((centeredTitleStart - spacing) / 2.25)) + spacing
    }
    spacing: 6

    TextMetrics {
        id: titleMetrics
        font: root.titleFont
        text: "Accessories  ▾"
    }
}
