"""Keep late state feedback from replacing the operator's selected cab target."""

from threading import Thread, current_thread, main_thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.constants import CommandScope
from pytrain_ui.contracts import EngineViewState, StateListener


class DelayedStateAdapter:
    """Allow a captured callback to complete after its subscription is removed."""

    def __init__(self, scope: CommandScope, tmcc_id: int) -> None:
        self.state = SimpleNamespace(scope=scope, tmcc_id=tmcc_id, is_legacy=True)
        self.snapshot = EngineViewState(scope=scope.name, tmcc_id=tmcc_id, road_name=f"Engine {tmcc_id}")
        self.listener: StateListener | None = None

    def current(self) -> EngineViewState:
        return self.snapshot

    def subscribe(self, listener: StateListener):
        self.listener = listener
        listener(self.snapshot)

        def unsubscribe() -> None:
            self.listener = None

        return unsubscribe

    def shutdown(self) -> None:
        pass


@pytest.fixture
def selected_cab(monkeypatch: pytest.MonkeyPatch):
    core = pytest.importorskip("PySide6.QtCore")
    module = pytest.importorskip("pytrain_ui.qt.cab_controller")
    application = core.QCoreApplication.instance() or core.QCoreApplication([])
    store = Mock()
    store.get_all.return_value = []
    monkeypatch.setattr(ComponentStateStore, "get", lambda: store)
    monkeypatch.setattr(ComponentStateStore, "get_state", lambda *_args, **_kwargs: object())
    adapters: list[DelayedStateAdapter] = []
    commands: list[tuple[int, int, CommandScope]] = []

    def state_adapter(scope: CommandScope, tmcc_id: int) -> DelayedStateAdapter:
        adapter = DelayedStateAdapter(scope, tmcc_id)
        adapters.append(adapter)
        return adapter

    def speed_request(tmcc_id: int, speed: int, scope: CommandScope):
        commands.append((tmcc_id, speed, scope))
        return Mock()

    monkeypatch.setattr("pytrain_ui.qt.cab_controller.PyTrainCabStateAdapter", state_adapter)
    monkeypatch.setattr("pytrain_ui.adapters.commands.RampSpeedReq", speed_request)
    cab = module.CabController(CommandScope.ENGINE, 10)
    try:
        yield cab, adapters, commands, application
    finally:
        cab.close()
        application.processEvents()


def test_late_engine_feedback_preserves_selected_display_and_command_target(selected_cab) -> None:
    cab, adapters, commands, application = selected_cab
    previous_listener = adapters[0].listener
    assert previous_listener is not None
    assert cab.selectAddress("ENGINE", 60)

    previous_listener(EngineViewState(scope="ENGINE", tmcc_id=10, road_name="Previous engine", speed=73))
    application.processEvents()

    assert cab.tmccId == 60
    assert cab.roadName == "Engine 60"
    assert cab.speed == 0
    cab.setSpeed(20)
    assert commands == [(60, 20, CommandScope.ENGINE)]


def test_feedback_from_an_earlier_visit_to_the_same_engine_is_ignored(selected_cab) -> None:
    cab, adapters, _commands, application = selected_cab
    assert cab.selectAddress("ENGINE", 60)
    earlier_listener = adapters[-1].listener
    assert earlier_listener is not None
    assert cab.selectAddress("ENGINE", 10)
    assert cab.selectAddress("ENGINE", 60)

    earlier_listener(EngineViewState(scope="ENGINE", tmcc_id=60, speed=80))
    application.processEvents()

    assert cab.tmccId == 60
    assert cab.speed == 0


def test_engine_feedback_cannot_replace_a_train_with_the_same_address(selected_cab) -> None:
    cab, adapters, _commands, application = selected_cab
    previous_listener = adapters[0].listener
    assert previous_listener is not None
    assert cab.selectAddress("TRAIN", 10)

    previous_listener(EngineViewState(scope="ENGINE", tmcc_id=10, speed=73))
    application.processEvents()

    assert cab.scope == "TRAIN"
    assert cab.tmccId == 10
    assert cab.speed == 0


def test_current_target_feedback_is_applied_on_the_main_thread(selected_cab) -> None:
    cab, adapters, _commands, application = selected_cab
    assert cab.selectAddress("ENGINE", 60)
    listener = adapters[-1].listener
    assert listener is not None
    update_threads = []
    cab.stateChanged.connect(lambda: update_threads.append(current_thread()))
    snapshot = EngineViewState(scope="ENGINE", tmcc_id=60, road_name="Selected engine", speed=12)
    worker = Thread(target=listener, args=(snapshot,))
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert cab.speed == 0
    application.processEvents()

    assert cab.tmccId == 60
    assert cab.roadName == "Selected engine"
    assert cab.speed == 12
    assert update_threads == [main_thread()]
