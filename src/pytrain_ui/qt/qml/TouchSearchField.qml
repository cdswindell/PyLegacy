import QtQuick
import QtQuick.Controls

TextField {
    id: root
    placeholderTextColor: "#acbfd8"
    property bool touchKeyboardEnabled: Qt.platform.os === "linux"
    // Open on a deliberate tap, not when focus is restored after closing.
    TapHandler {
        onTapped: if (root.touchKeyboardEnabled && !keyboard.visible) keyboard.openFor(root)
    }
    SearchKeyboard { id: keyboard }
    onVisibleChanged: if (!visible) keyboard.close()
}
