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


def select_backend(
    args: list[str],
    *,
    qt_installed: bool | None = None,
    legacy_env: str | None = None,
) -> tuple[str, list[str]]:
    """Return (backend, forwarded args) for the cab launcher.

    Explicit command-line selection wins over the environment. Without an
    explicit selection, PYTRAIN_LEGACY_GUI opts out of Qt. Otherwise Qt is the
    preferred presentation when its optional dependency is installed.
    """
    forwarded = list(args)
    force_legacy = LEGACY_FLAG in forwarded
    force_qt = QT_FLAG in forwarded
    if force_legacy and force_qt:
        raise ValueError("Choose either --qt or --legacy, not both")

    forwarded = [arg for arg in forwarded if arg not in {LEGACY_FLAG, QT_FLAG}]
    if qt_installed is None:
        qt_installed = qt_available()
    if legacy_env is None:
        legacy_env = os.getenv(LEGACY_ENV)

    if force_legacy:
        return "legacy", forwarded
    if force_qt:
        if not qt_installed:
            raise RuntimeError("PySide6 is not installed; install the qt-gui extra or omit --qt")
        return "qt", forwarded
    if _truthy(legacy_env):
        return "legacy", forwarded
    return ("qt" if qt_installed else "legacy"), forwarded


def main(args: list[str] | None = None) -> int:
    """Run Qt by default when available, retaining an explicit GuiZero fallback."""
    if args is None:
        args = sys.argv[1:]

    try:
        backend, forwarded = select_backend(list(args))
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    if backend == "qt":
        from pytrain_ui.qt.pycab import main as qt_main

        return qt_main(forwarded)

    from pytrain.cli.pycab import main as legacy_main

    return legacy_main(forwarded)
