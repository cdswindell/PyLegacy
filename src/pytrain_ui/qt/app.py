"""Qt Quick application bootstrap for PyTrain."""

from __future__ import annotations

import sys
from importlib.resources import as_file, files


def run_cab(scope, tmcc_id: int, args: list[str] | None = None) -> int:
    """Run the Qt cab for an already-initialized PyTrain runtime."""
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuickControls2 import QQuickStyle
    except ImportError as exc:
        raise SystemExit("The Qt UI is not installed. Install PyTrain with the 'qt-gui' extra.") from exc

    from pytrain.protocol.constants import CommandScope

    from .cab_controller import CabController
    from .catalog_controller import EngineCatalogController
    from .gamepad import QtCabInputSink, QtGamepadInput
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

    restored_id = restore_engine()
    show_catalog = restored_id is None
    if restored_id is not None:
        scope = CommandScope.ENGINE
        tmcc_id = restored_id

    cab = CabController(scope, tmcc_id)
    catalog = EngineCatalogController()
    selection = SelectedEngineController(cab)
    switches = OpsController(CommandScope.SWITCH)
    routes = OpsController(CommandScope.ROUTE)
    gamepad = QtGamepadInput(QtCabInputSink(cab), cab)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("cabController", cab)
    engine.rootContext().setContextProperty("engineCatalogController", catalog)
    engine.rootContext().setContextProperty("selectedEngineController", selection)
    engine.rootContext().setContextProperty("switchOpsController", switches)
    engine.rootContext().setContextProperty("routeOpsController", routes)
    engine.rootContext().setContextProperty("showCatalogAtStartup", show_catalog)

    def remember_current_engine() -> None:
        if cab.scope == CommandScope.ENGINE.name:
            save_engine(cab.tmccId)

    cab.stateChanged.connect(remember_current_engine)

    qml = files("pytrain_ui.qt.qml").joinpath("Main.qml")
    with as_file(qml) as qml_path:
        engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        gamepad.close()
        routes.close()
        switches.close()
        selection.close()
        catalog.close()
        cab.close()
        return 1
    try:
        return app.exec()
    finally:
        remember_current_engine()
        gamepad.close()
        routes.close()
        switches.close()
        selection.close()
        catalog.close()
        cab.close()


def main(args: list[str] | None = None) -> int:
    raise SystemExit("Use the pycab-qt launcher so PyTrain state is synchronized before the Qt UI starts.")


if __name__ == "__main__":
    raise SystemExit(main())
