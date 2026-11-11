"""Exercise the Qt StateInfo draft and Base 3 record actions without hardware."""

from unittest.mock import Mock

import pytest

from pytrain.db.component_state import ComponentState, ComponentStateDict
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.pdi.base_req import BaseReq
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
