"""Bridge committed workspace selections to the buttons-file cab handle."""

from PySide6.QtCore import QObject, Slot


class StartupSelectionObserver(QObject):
    def __init__(self, window, interface, parent=None) -> None:
        super().__init__(parent)
        self._window = window
        self._interface = interface
        window.activeTargetChanged.connect(self.publish)

    @Slot()
    def publish(self) -> None:
        target = self._window.property("activeTarget")
        if hasattr(target, "toVariant"):
            target = target.toVariant()
        self._interface.report_selection(target["scope"], target["tmccId"])

    def close(self) -> None:
        self._window.activeTargetChanged.disconnect(self.publish)
