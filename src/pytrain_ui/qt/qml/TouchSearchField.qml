import QtQuick
import QtQuick.Controls

TextField {
    id: root
    placeholderTextColor: "#acbfd8"
    property string keyboardTitle: "Search"
    property bool keyboardModal: true
    property real keyboardBottomMargin: 8
    property bool touchKeyboardEnabled: Qt.platform.os === "linux"
    // Open on a deliberate tap, not when focus is restored after closing.
    TapHandler {
        onTapped: if (root.touchKeyboardEnabled && !keyboard.visible) keyboard.openFor(root)
    }
    SearchKeyboard {
        id: keyboard
        title: root.keyboardTitle
        modal: root.keyboardModal
        keyboardInset: root.keyboardBottomMargin
    }
    onVisibleChanged: if (!visible) keyboard.close()
}
