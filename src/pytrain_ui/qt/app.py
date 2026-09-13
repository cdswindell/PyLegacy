"""Qt Quick application bootstrap for PyTrain."""

from __future__ import annotations

import sys
from importlib.resources import as_file, files


def main(args: list[str] | None = None) -> int:
    """Launch the Qt Quick presentation shell.

    PySide6 is intentionally imported lazily so installing or importing the PyTrain
    core does not require Qt during the migration from GuiZero.
    """

    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError as exc:
        raise SystemExit("The Qt UI is not installed. Install PyTrain with the 'qt-gui' extra.") from exc

    argv = sys.argv if args is None else [sys.argv[0], *args]
    app = QGuiApplication(argv)
    app.setApplicationName("PyTrain")
    app.setOrganizationName("PyTrain")

    engine = QQmlApplicationEngine()
    qml = files("pytrain_ui.qt.qml").joinpath("Main.qml")
    with as_file(qml) as qml_path:
        engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
