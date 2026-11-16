"""Exercise the Qt StateInfo draft and Base 3 record actions without hardware."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.component_state import ComponentState, ComponentStateDict, SwitchState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.engine_state import TrainState
from pytrain.pdi.asc2_req import Asc2Req
from pytrain.pdi.base_req import BaseReq
from pytrain.pdi.bpc2_req import Bpc2Req
from pytrain.pdi.constants import Asc2Action, Bpc2Action, PdiCommand
from pytrain.pdi.pdi_listener import PdiDispatcher
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.fixture
def state_info(monkeypatch):
    module = pytest.importorskip("pytrain_ui.qt.state_info_controller")
    states = ComponentStateDict(CommandScope.ENGINE)
    monkeypatch.setattr(ComponentStateStore, "get_state", lambda _scope, address, create=False: states.get(address))
    return module.StateInfoController(), states


def populate(state, name: str, number: str) -> None:
    state.initialize(CommandScope.ENGINE, state.tmcc_id)
    state.comp_data.road_name = name
    state.comp_data.road_number = number
    state.comp_data.control_type = 1
    state.comp_data.engine_type = 0
    state.comp_data.sound_type = 0


def test_create_stages_metadata_and_waits_for_base_readback(state_info, monkeypatch) -> None:
    controller, states = state_info
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    ready = Mock()
    controller.recordReady.connect(ready)

    controller.openFor("ENGINE", 8, True)
    assert controller.model["canCreate"]
    assert controller.edit("name", "Test locomotive")
    assert controller.edit("number", "84")
    dispatch.assert_not_called()
    assert not states

    controller.create()
    dispatch.assert_called_once()
    assert controller.model["busy"]
    ready.assert_not_called()
    populate(states[8], "Test locomotive", "0084")
    controller.refresh(False)
    ready.assert_called_once_with("ENGINE", 8)


def test_four_digit_set_address_is_explicit_and_cancel_discards_draft(state_info, monkeypatch) -> None:
    controller, states = state_info
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)

    controller.openFor("ENGINE", 2468, True)
    assert not controller.model["canCreate"]
    assert controller.edit("name", "Draft")
    build.assert_not_called()

    controller.setAddress()
    build.assert_called_once_with(TMCC2EngineCommandEnum.SET_ADDRESS, address=2468, scope=CommandScope.ENGINE)
    build.return_value.send.assert_called_once_with()
    assert not states
    controller.close()
    placeholder = states[2468]
    assert placeholder.comp_data is None
    assert controller.needsEngineRecord(2468)
    controller.openFor("ENGINE", 2468, True)
    assert controller.model["identity"][0]["value"] == "Engine 2468"


def test_existing_record_edits_and_clear_delegate_to_base_state(state_info, monkeypatch) -> None:
    controller, states = state_info
    state = states[8]
    populate(state, "Test locomotive", "0084")
    update = Mock()
    clear = Mock(return_value=True)
    monkeypatch.setattr(BaseReq, "do_update_field", update)
    monkeypatch.setattr(ComponentState, "clear", clear)
    cleared = Mock()
    controller.recordCleared.connect(cleared)

    assert not controller.needsEngineRecord(8)
    controller.openFor("ENGINE", 8, False)
    assert controller.model["canClear"]
    assert len(controller.model["live"]) == 12
    assert controller.edit("control", "2")
    update.assert_called_once_with("CONTROL_TYPE", 2, state, do_async=False)
    controller.clear()
    clear.assert_called_once_with(notify=True, clear_db=True)
    cleared.assert_called_once_with("ENGINE", 8)


def test_state_info_cannot_clear_bpc2_train(state_info, monkeypatch) -> None:
    controller, _ = state_info
    train = TrainState(CommandScope.TRAIN)
    train.update(Bpc2Req(20, PdiCommand.BPC2_SET, Bpc2Action.CONTROL1, state=1))
    assert train.is_bpc2
    assert not train.is_deletable
    lookup = Mock(return_value=train)
    monkeypatch.setattr(ComponentStateStore, "get_state", lookup)
    clear = Mock()
    monkeypatch.setattr(ComponentState, "clear", clear)
    cleared = Mock()
    controller.recordCleared.connect(cleared)

    controller.openFor("TRAIN", 20, False)
    lookup.assert_called_with(CommandScope.TRAIN, 20, create=False)
    assert controller.model["scopeTitle"] == CommandScope.TRAIN.title
    assert not controller.model["canClear"]
    controller.clear()

    clear.assert_not_called()
    cleared.assert_not_called()


def test_switch_editor_cannot_clear_asc2_switch(monkeypatch) -> None:
    module = pytest.importorskip("pytrain_ui.qt.ops_controller")
    scope = CommandScope.SWITCH
    switch = SwitchState(scope)
    switch.initialize(scope, 19)
    switch.comp_data.road_name = "Yard turnout"
    monkeypatch.setattr(ComponentStateStore, "get_state", Mock(return_value=switch))
    monkeypatch.setattr(CommandDispatcher, "get", Mock(return_value=Mock()))
    monkeypatch.setattr(PdiDispatcher, "is_built", lambda: False)
    store = Mock()
    store.get_all.return_value = []
    monkeypatch.setattr(ComponentStateStore, "get", Mock(return_value=store))
    controller = module.OpsController(scope)
    assert controller.canClearRecord(19)

    switch.update(Asc2Req(19, PdiCommand.ASC2_SET, Asc2Action.CONTROL4, values=0, scope=scope))
    assert switch.is_lcs_component
    assert not switch.is_deletable
    clear = Mock(return_value=True)
    monkeypatch.setattr(ComponentState, "clear", clear)

    assert not controller.canClearRecord(19)
    assert controller.clearRecord(19)
    clear.assert_not_called()


# Embedded Qt API identifiers must retain their exact spelling.
# noinspection SpellCheckingInspection
CLEAR_BUTTON_CHILD = """
import sys

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuickControls2 import QQuickStyle

QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine, QUrl.fromLocalFile(sys.argv[1]))
for creating, can_clear, expected in (
    (False, False, (True, False)),
    (False, True, (True, True)),
    (True, False, (False, False)),
):
    panel = component.createWithInitialProperties({
        "controller": {"model": {"creating": creating, "canClear": can_clear}}
    })
    assert panel is not None, component.errorString()
    clear = next(
        item for item in panel.findChildren(QObject)
        if item.property("text") == "Clear" and item.property("delay") == 3000
    )
    assert (clear.property("visible"), clear.property("enabled")) == expected
    panel.setProperty("visible", False)
    panel.deleteLater()
"""


def test_state_info_clear_button_tracks_record_permissions() -> None:
    pytest.importorskip("PySide6")
    qml = Path(__file__).resolve().parents[2] / "src/pytrain_ui/qt/qml/StateInfoView.qml"
    result = subprocess.run(
        [sys.executable, "-c", CLEAR_BUTTON_CHILD, str(qml)],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
