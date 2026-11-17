import QtQuick
import QtQuick.Controls

ApplicationWindow {
    visibility: startFullscreen ? Window.FullScreen : Window.Windowed
    onClosing: Qt.quit()
    palette.window: "#102858"
    palette.windowText: "#f4f6f8"
    palette.base: "#0a2045"
    palette.text: "#f4f6f8"
    palette.placeholderText: "#acbfd8"
    palette.button: "#344862"
    palette.buttonText: "#ffffff"
    palette.highlight: "#246aa0"
    palette.highlightedText: "#ffffff"
}
