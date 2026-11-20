"""Qt Quick application bootstrap for PyTrain."""

from __future__ import annotations

import logging
import signal
import sys
from importlib.resources import as_file, files


log = logging.getLogger(__name__)


def run_cab(scope, tmcc_id: int, args: list[str] | None = None) -> int:
    """Run the Qt cab for an already-initialized PyTrain runtime."""
    from pytrain.utils.host_info import is_steam_deck

    if is_steam_deck():
        return run_deck(scope, tmcc_id, args)
    return _run(scope, tmcc_id, args)


def run_deck(
    scope,
    tmcc_id: int,
    args: list[str] | None = None,
    *,
    width: int = 1280,
    height: int = 800,
    controller_profile: str | None = None,
    full_screen: bool = True,
) -> int:
    """Run two independent cabs in one Steam Deck window and one Qt event loop."""
    if width <= 0 or height <= 0:
        raise ValueError("Steam Deck dimensions must be positive")
    return _run(
        scope,
        tmcc_id,
        args,
        deck=True,
        width=width,
        height=height,
        controller_profile=controller_profile,
        full_screen=full_screen,
    )


def _run(scope, tmcc_id, args, *, deck=False, width=1280, height=800, controller_profile=None, full_screen=None) -> int:
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuickControls2 import QQuickStyle
    except ImportError as exc:
        raise SystemExit("The Qt UI is not installed. Install PyTrain with the 'qt-gui' extra.") from exc

    from pytrain.cli.pytrain import PyTrain
    from pytrain.pdi.pdi_listener import PdiDispatcher
    from pytrain.protocol.constants import CREATE_TOPIC, DELETE_TOPIC, CommandScope
    from pytrain.utils.host_info import HostInfo, is_linux, is_steam_deck

    from .accessory_controller import AccessoryCatalogController
    from .admin_controller import AdminController
    from .cab_controller import CabController
    from .catalog_controller import EngineCatalogController
    from .gamepad import QtCabInputSink, QtGamepadInput
    from .lcs_controller import LcsConfigController
    from .network_monitor import NetworkMonitor
    from .ops_controller import OpsController
    from .selection_controller import SelectedEngineController
    from .session import restore_engine, save_engine
    from .state_change_bridge import QtStateChangeBridge
    from .state_info_controller import StateInfoController
    from .train_link_controller import TrainLinkController

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

    state_bridge = QtStateChangeBridge(
        {CommandScope.SWITCH, CommandScope.ROUTE, CommandScope.ENGINE, CommandScope.TRAIN}, app
    )
    engine = QQmlApplicationEngine()
    network = NetworkMonitor(app)
    bundles = []
    for side in ("left", "right") if deck else ("",):
        cab = CabController(scope, tmcc_id, remember_initial=not show_catalog)
        accessories = AccessoryCatalogController()
        catalog = EngineCatalogController()
        selection = SelectedEngineController(cab)
        state_bridge.changesReady.connect(selection.applyTrainStateChanges)
        train_links = TrainLinkController(cab)
        state_bridge.changesReady.connect(train_links.applyStateChanges)
        switches = OpsController(CommandScope.SWITCH)
        routes = OpsController(CommandScope.ROUTE)
        state_bridge.changesReady.connect(switches.applyStateChanges)
        state_bridge.changesReady.connect(routes.applyStateChanges)
        lcs = LcsConfigController()
        admin = AdminController(network)
        admin.exitRequested.connect(app.quit)
        state_info = StateInfoController()
        bundle = {
            "cabController": cab,
            "managePyTrainController": admin,
            "stateInfoController": state_info,
            "accessoryCatalogController": accessories,
            "engineCatalogController": catalog,
            "selectedEngineController": selection,
            "trainLinkController": train_links,
            "switchOpsController": switches,
            "routeOpsController": routes,
            "lcsConfigController": lcs,
            "showCatalogAtStartup": show_catalog,
        }
        bundles.append(bundle)
        for name, controller in bundle.items():
            context_name = side + name[0].upper() + name[1:] if side else name
            engine.rootContext().setContextProperty(context_name, controller)
    engine.rootContext().setContextProperty(
        "startFullscreen",
        full_screen if full_screen is not None else is_linux() and (is_steam_deck() or HostInfo().is_pi),
    )
    gamepad = None if deck else QtGamepadInput(QtCabInputSink(cab), cab)
    if deck:
        from .deck import QtDeckController

        gamepad = QtDeckController(bundles[0], bundles[1], controller_profile, app)
        engine.rootContext().setContextProperty("deckController", gamepad)
        engine.rootContext().setContextProperty("deckWindowWidth", width)
        engine.rootContext().setContextProperty("deckWindowHeight", height)

    def remember_current_engine() -> None:
        if cab.scope == CommandScope.ENGINE.name:
            save_engine(cab.tmccId)

    cab.stateChanged.connect(remember_current_engine)

    qml = files("pytrain_ui.qt.qml").joinpath("SteamDeckMain.qml" if deck else "Main.qml")
    with as_file(qml) as qml_path:
        engine.load(QUrl.fromLocalFile(str(qml_path)))
    if deck and engine.rootObjects():
        gamepad.attach(engine.rootObjects()[0])

    def process_python_signals() -> None:
        # Returning to Python lets pending SIGINT handlers run while Qt is idle.
        pass

    def interrupt(_signum, _frame) -> None:
        app.quit()

    signal_timer = QTimer(app)
    signal_timer.timeout.connect(process_python_signals)
    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, interrupt)
    pdi_dispatcher = PdiDispatcher.get() if PdiDispatcher.is_built() else None
    try:
        if pdi_dispatcher is not None:
            for bundle in bundles:
                pdi_dispatcher.subscribe(bundle["stateInfoController"].receive_record_deletion, DELETE_TOPIC)
            pdi_dispatcher.subscribe(state_bridge.receiveRecordChange, CREATE_TOPIC)
        if not engine.rootObjects():
            return 1
        runtime = PyTrain.current(raise_exception=False)
        if runtime is not None and runtime.admin_exit_requested:
            return 0
        signal_timer.start(100)
        return app.exec()
    finally:
        signal_timer.stop()
        signal.signal(signal.SIGINT, previous_sigint)
        cleanup = [
            ("state-change bridge", state_bridge.close),
            ("network monitor", network.close),
            ("session preferences", remember_current_engine),
            ("gamepad", gamepad.close),
        ]
        for bundle in bundles:
            cleanup.extend(
                [
                    ("LCS readback", bundle["lcsConfigController"].clearConfigureStatus),
                    ("admin", bundle["managePyTrainController"].close),
                    ("accessories", bundle["accessoryCatalogController"].close),
                    ("routes", bundle["routeOpsController"].close),
                    ("switches", bundle["switchOpsController"].close),
                    ("train links", bundle["trainLinkController"].close),
                    ("selection", bundle["selectedEngineController"].close),
                    ("catalog", bundle["engineCatalogController"].close),
                    ("cab", bundle["cabController"].close),
                ]
            )
        if pdi_dispatcher is not None:
            cleanup.insert(
                0,
                (
                    "record creation notifications",
                    lambda: pdi_dispatcher.unsubscribe(state_bridge.receiveRecordChange, CREATE_TOPIC),
                ),
            )
            for bundle in bundles:
                callback = bundle["stateInfoController"].receive_record_deletion
                cleanup.insert(
                    0,
                    (
                        "record deletion notifications",
                        lambda callback=callback: pdi_dispatcher.unsubscribe(callback, DELETE_TOPIC),
                    ),
                )
        for name, close in cleanup:
            try:
                close()
            except Exception as exc:
                log.warning("Error closing Qt %s, continuing shutdown: %s", name, exc)


def main(args: list[str] | None = None) -> int:
    raise SystemExit("Use the pycab-qt launcher so PyTrain state is synchronized before the Qt UI starts.")


if __name__ == "__main__":
    raise SystemExit(main())
