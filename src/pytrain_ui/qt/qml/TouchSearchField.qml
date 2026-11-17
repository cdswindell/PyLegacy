import QtQuick
import QtQuick.Controls

TextField {
    id: root
    signal touchKeyboardFinished()

    placeholderTextColor: "#acbfd8"
    property string keyboardTitle: "Search"
    property bool keyboardModal: true
    property bool titleCaseEnabled: false
    property real keyboardBottomMargin: 8
    readonly property alias keyboardOpen: keyboard.visible
    readonly property alias keyboardDirty: keyboard.hasUnsavedChanges

    function closeTouchKeyboard() {
        keyboard.close()
    }

    property bool touchKeyboardEnabled: Qt.platform.os === "linux"
    // Open on a deliberate tap, not when focus is restored after closing.
    TapHandler {
        onTapped: if (root.touchKeyboardEnabled && !keyboard.visible) keyboard.openFor(root)
    }
    SearchKeyboard {
        id: keyboard
        title: root.keyboardTitle
        titleCaseEnabled: root.titleCaseEnabled
        modal: root.keyboardModal
        keyboardInset: root.keyboardBottomMargin
        onFinished: root.touchKeyboardFinished()
    }
    onVisibleChanged: if (!visible) keyboard.close()
}
