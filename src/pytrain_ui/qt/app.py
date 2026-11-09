"""Qt Quick application bootstrap for PyTrain."""

from __future__ import annotations

import logging
import signal
import sys
from importlib.resources import as_file, files


log = logging.getLogger(__name__)


def run_cab(scope, tmcc_id: int, args: list[str] | None = None) -> int:
    """Run the Qt cab for an already-initialized PyTrain runtime."""
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuickControls2 import QQuickStyle
    except ImportError as exc:
        raise SystemExit("The Qt UI is not installed. Install PyTrain with the 'qt-gui' extra.") from exc

    from pytrain.protocol.constants import CommandScope

    from .accessory_controller import AccessoryCatalogController
    from .cab_controller import CabController
    from .catalog_controller import EngineCatalogController
    from .gamepad import QtCabInputSink, QtGamepadInput
    from .lcs_controller import LcsConfigController
    from .ops_controller import OpsController
    from .selection_controller import SelectedEngineController
    from .session import restore_engine, save_engine

    # PyTrain supplies custom backgrounds/content for its controls. The native macOS
    # style intentionally rejects those delegates, so use a customizable style on every
    # platform for deterministic rendering on macOS, Raspberry Pi, and Steam Deck.
    QQuickStyle.setStyle("Basic")

    argv = sys.argv if args is None else [sys.argv[0], *args]
    app = QGuiApplication(argv)
    app.setApplicationName("PyTrain")
    app.setOrganizationName("PyTrain")

    icon = QIcon()
    for size in ("small", "large"):
        artwork = files("pytrain.gui.images").joinpath(f"en-US_pycab_{size}.png")
        try:
            pixmap = QPixmap()
            if pixmap.loadFromData(artwork.read_bytes(), "PNG"):
                icon.addPixmap(pixmap)
        except OSError as exc:
            log.warning("Unable to load PyCab app icon: %s", exc)
    if not icon.isNull():
        app.setWindowIcon(icon)

    restored_id = restore_engine()
    show_catalog = restored_id is None
    if restored_id is not None:
        scope = CommandScope.ENGINE
        tmcc_id = restored_id

    cab = CabController(scope, tmcc_id)
    accessories = AccessoryCatalogController()
    catalog = EngineCatalogController()
    selection = SelectedEngineController(cab)
    switches = OpsController(CommandScope.SWITCH)
    routes = OpsController(CommandScope.ROUTE)
    lcs = LcsConfigController()
    gamepad = QtGamepadInput(QtCabInputSink(cab), cab)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("cabController", cab)
    engine.rootContext().setContextProperty("accessoryCatalogController", accessories)
    engine.rootContext().setContextProperty("engineCatalogController", catalog)
    engine.rootContext().setContextProperty("selectedEngineController", selection)
    engine.rootContext().setContextProperty("switchOpsController", switches)
    engine.rootContext().setContextProperty("routeOpsController", routes)
    engine.rootContext().setContextProperty("lcsConfigController", lcs)
    engine.rootContext().setContextProperty("showCatalogAtStartup", show_catalog)

    def remember_current_engine() -> None:
        if cab.scope == CommandScope.ENGINE.name:
            save_engine(cab.tmccId)

    cab.stateChanged.connect(remember_current_engine)

    qml = files("pytrain_ui.qt.qml").joinpath("Main.qml")
    with as_file(qml) as qml_path:
        engine.load(QUrl.fromLocalFile(str(qml_path)))

    def process_python_signals() -> None:
        # Returning to Python lets pending SIGINT handlers run while Qt is idle.
        pass

    def interrupt(_signum, _frame) -> None:
        app.quit()

    signal_timer = QTimer(app)
    signal_timer.timeout.connect(process_python_signals)
    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, interrupt)
    try:
        if not engine.rootObjects():
            return 1
        signal_timer.start(100)
        return app.exec()
    finally:
        signal_timer.stop()
        signal.signal(signal.SIGINT, previous_sigint)
        cleanup = [
            ("session preferences", remember_current_engine),
            ("gamepad", gamepad.close),
            ("accessories", accessories.close),
            ("routes", routes.close),
            ("switches", switches.close),
            ("selection", selection.close),
            ("catalog", catalog.close),
            ("cab", cab.close),
        ]
        for name, close in cleanup:
            try:
                close()
            except Exception as exc:
                log.warning("Error closing Qt %s, continuing shutdown: %s", name, exc)


def main(args: list[str] | None = None) -> int:
    raise SystemExit("Use the pycab-qt launcher so PyTrain state is synchronized before the Qt UI starts.")


if __name__ == "__main__":
    raise SystemExit(main())
