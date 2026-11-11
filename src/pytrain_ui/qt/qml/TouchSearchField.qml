import QtQuick
import QtQuick.Controls

TextField {
    id: root
    placeholderTextColor: "#acbfd8"
    property string keyboardTitle: "Search"
    property bool touchKeyboardEnabled: Qt.platform.os === "linux"
    // Open on a deliberate tap, not when focus is restored after closing.
    TapHandler {
        onTapped: if (root.touchKeyboardEnabled && !keyboard.visible) keyboard.openFor(root)
    }
    SearchKeyboard { id: keyboard; title: root.keyboardTitle }
    onVisibleChanged: if (!visible) keyboard.close()
}
