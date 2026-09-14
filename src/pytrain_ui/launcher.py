"""Select the preferred PyTrain cab presentation without coupling core PyTrain to Qt."""

from __future__ import annotations

import importlib.util
import os
import sys

LEGACY_FLAG = "--legacy"
QT_FLAG = "--qt"
LEGACY_ENV = "PYTRAIN_LEGACY_GUI"


def qt_available() -> bool:
    """Return whether the optional Qt presentation dependency is installed."""
    return importlib.util.find_spec("PySide6") is not None


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def main(args: list[str] | None = None) -> int:
    """Run Qt by default when available, retaining an explicit GuiZero fallback."""
    if args is None:
        args = sys.argv[1:]
    else:
        args = list(args)

    force_legacy = LEGACY_FLAG in args or _truthy(os.getenv(LEGACY_ENV))
    force_qt = QT_FLAG in args
    args = [arg for arg in args if arg not in {LEGACY_FLAG, QT_FLAG}]

    if force_qt and not qt_available():
        raise RuntimeError("PySide6 is not installed; install the qt-gui extra or omit --qt")

    if not force_legacy and qt_available():
        from pytrain_ui.qt.pycab import main as qt_main

        return qt_main(args)

    from pytrain.cli.pycab import main as legacy_main

    return legacy_main(args)
