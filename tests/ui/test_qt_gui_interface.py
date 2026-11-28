"""The startup handle reuses PyTrain and publishes atomic selection snapshots."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, current_thread, main_thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pytrain.cli.pytrain import PyTrain
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt import CabSelection, QtCabGui


@pytest.fixture
def runtime(monkeypatch):
    existing = Mock(spec=PyTrain)
    monkeypatch.setattr(PyTrain, "current", lambda: existing)
    return existing


def test_buttons_registration_reuses_current_runtime_without_starting_qt(runtime):
    gui = QtCabGui(tmcc_id=37, width=800, height=1280, full_screen=True)
    runtime.register_startup_gui.assert_called_once_with(gui.run, gui.close)
    assert gui.selection == CabSelection()
    assert gui.active_engine_state is None


@pytest.mark.parametrize(
    "options",
    [
        {"tmcc_id": 0},
        {"tmcc_id": 10000},
        {"width": 0},
        {"height": -1},
        {"scope": CommandScope.SWITCH},
    ],
)
def test_invalid_configuration_does_not_register_a_gui(runtime, options):
    with pytest.raises(ValueError):
        QtCabGui(**options)
    runtime.register_startup_gui.assert_not_called()


# The fixture name below is supplied by pytest.
# noinspection SpellCheckingInspection
@pytest.mark.usefixtures("runtime")
def test_notifications_only_report_target_changes_and_unsubscribe(caplog):
    gui = QtCabGui()
    seen = []
    broken = Mock(side_effect=RuntimeError("subscriber failure"))
    stop_broken = gui.subscribe(broken)
    stop = gui.subscribe(seen.append)
    gui.report_selection("ENGINE", 37)
    gui.report_selection("ENGINE", 37)
    gui.report_selection("TRAIN", 37)
    assert seen == [CabSelection(CommandScope.ENGINE, 37, 1), CabSelection(CommandScope.TRAIN, 37, 2)]
    assert gui.scope is CommandScope.TRAIN
    assert gui.tmcc_id == 37
    assert "subscriber failure" in caplog.text
    stop()
    stop()
    stop_broken()
    gui.report_selection("SWITCH", 4)
    assert len(seen) == 2


@pytest.mark.usefixtures("runtime")
def test_all_waiters_wake_and_a_change_before_wait_is_not_lost():
    gui = QtCabGui()
    ready = Barrier(3)

    def wait():
        ready.wait(timeout=2)
        return gui.wait_for_selection_change(0, timeout=2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        waits = [executor.submit(wait) for _ in range(2)]
        ready.wait(timeout=2)
        gui.report_selection("TRAIN", 502)
        assert [future.result(timeout=3) for future in waits] == [gui.selection, gui.selection]
    assert gui.wait_for_selection_change(0, timeout=0) == gui.selection
    assert gui.wait_for_selection_change(gui.selection.revision, timeout=0) is None


@pytest.mark.usefixtures("runtime")
def test_selected_state_lookup_never_creates_records_and_handles_deletion(monkeypatch):
    gui = QtCabGui()
    state = SimpleNamespace(is_deleted=False)
    lookup = Mock(return_value=state)
    monkeypatch.setattr(ComponentStateStore, "get_state", lookup)
    gui.report_selection("ENGINE", 37)
    assert gui.active_engine_state is state
    lookup.assert_called_once_with(CommandScope.ENGINE, 37, create=False)
    state.is_deleted = True
    assert gui.active_state is None
    gui.report_selection("ROUTE", 6)
    assert gui.active_engine_state is None
    gui.report_selection("ACC", 0)
    assert gui.selection.tmcc_id is None
    assert gui.active_state is None


@pytest.mark.usefixtures("runtime")
def test_run_forwards_configuration_and_close_wakes_waiters(monkeypatch):
    from pytrain_ui.qt import app

    gui = QtCabGui(tmcc_id=502, scope=CommandScope.TRAIN, width=900, height=1200, full_screen=False, deck=False)
    seen = []
    gui.subscribe(seen.append)

    def launch(scope, address, args, **options):
        assert current_thread() is main_thread()
        assert (scope, address, args) == (CommandScope.TRAIN, 502, [])
        assert options == dict(
            deck=False,
            width=900,
            height=1200,
            controller_profile=None,
            full_screen=False,
            explicit_target=True,
            interface=gui,
        )
        gui.report_selection("TRAIN", 502)
        return 0

    monkeypatch.setattr(app, "_run", launch)
    with ThreadPoolExecutor(max_workers=1) as executor:
        waiter = executor.submit(gui.wait_for_selection_change, 1, 2)
        assert gui.run() == 0
        assert waiter.result(timeout=3) is None
    assert seen == [CabSelection(CommandScope.TRAIN, 502, 1)]
    with pytest.raises(RuntimeError, match="closed"):
        gui.subscribe(seen.append)


@pytest.mark.usefixtures("runtime")
def test_close_before_start_prevents_window_creation(monkeypatch):
    from pytrain_ui.qt import app

    launch = Mock()
    monkeypatch.setattr(app, "_run", launch)
    gui = QtCabGui()
    gui.close()
    assert gui.run() == 0
    launch.assert_not_called()


@pytest.mark.usefixtures("runtime")
def test_worker_thread_cannot_start_qt():
    gui = QtCabGui()
    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(RuntimeError, match="main thread"):
            executor.submit(gui.run).result(timeout=3)
