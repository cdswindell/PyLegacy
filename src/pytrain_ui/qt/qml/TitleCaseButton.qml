import QtQuick
import QtQuick.Controls

CabButton {
    id: root
    required property var field

    function titleCase(name) {
        let wordStart = true
        return Array.from(name.toLowerCase(), character => {
            if (character.toUpperCase() !== character.toLowerCase()) {
                const letter = wordStart ? character.toUpperCase() : character
                wordStart = false
                return letter
            }
            if (character !== "'" && character !== "’" && !/[0-9]/.test(character))
                wordStart = true
            return character
        }).join("")
    }

    readonly property string converted: field ? titleCase(field.text) : ""
    text: "Aa"
    font.pixelSize: 22
    implicitWidth: 54
    Accessible.name: "Title Case"
    hoverEnabled: true
    ToolTip.text: "Title Case"
    ToolTip.delay: 500
    ToolTip.visible: hovered
    enabled: field && converted !== field.text && converted.length <= field.maximumLength
    focusPolicy: Qt.NoFocus
    activateOnRelease: true

    onClicked: {
        field.text = converted
        field.cursorPosition = field.length
        field.textEdited()
    }
}
