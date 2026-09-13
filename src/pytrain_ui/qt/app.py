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
    except ImportError as exc:
        raise SystemExit("The Qt UI is not installed. Install PyTrain with the 'qt-gui' extra.") from exc

    from .cab_controller import CabController

    argv = sys.argv if args is None else [sys.argv[0], *args]
    app = QGuiApplication(argv)
    app.setApplicationName("PyTrain")
    app.setOrganizationName("PyTrain")

    cab = CabController(scope, tmcc_id)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("cabController", cab)
    qml = files("pytrain_ui.qt.qml").joinpath("Main.qml")
    with as_file(qml) as qml_path:
        engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        cab.close()
        return 1
    try:
        return app.exec()
    finally:
        cab.close()


def main(args: list[str] | None = None) -> int:
    raise SystemExit("Use the pycab-qt launcher so PyTrain state is synchronized before the Qt UI starts.")


if __name__ == "__main__":
    raise SystemExit(main())
