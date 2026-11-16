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
from pytrain.gui.controller.lcs_device_registry import AMC2, ASC2, BPC2, SENSOR_TRACK
from pytrain.gui.controller.lcs_id_map import LcsOccupant
from pytrain.pdi.amc2_req import Amc2Req
from pytrain.pdi.asc2_req import Asc2Req
from pytrain.pdi.base_req import BaseReq
from pytrain.pdi.bpc2_req import Bpc2Req
from pytrain.pdi.constants import Asc2Action, Bpc2Action, PdiCommand
from pytrain.pdi.pdi_listener import PdiDispatcher
from pytrain.pdi.pdi_req import PdiReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum, TMCC1SwitchCommandEnum
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


@pytest.mark.parametrize("has_base_record", [True, False])
def test_amc2_state_info_reads_module_configuration_and_protects_clear(monkeypatch, has_base_record) -> None:
    module = pytest.importorskip("pytrain_ui.qt.state_info_controller")
    scope = CommandScope.ACC
    config = Amc2Req.from_bytes(bytes.fromhex("d1461903190000000202020303010100000000000000000077df"))
    state = ComponentStateDict(scope)[config.tmcc_id]
    if has_base_record:
        state.initialize(scope, state.tmcc_id)
        state.comp_data.road_name = "Motor Controller"
    if has_base_record:
        # A client can receive the reported identity before it receives the Base memory record.
        # noinspection PyProtectedMember
        state._road_name = "Wind Turbine #3"
        # noinspection PyProtectedMember
        state._road_number = "26"
    occupant = LcsOccupant(config.tmcc_id, AMC2, AMC2.mode_for_pdi_mode(config.access_type.value), 1, config=config)
    monkeypatch.setattr(ComponentStateStore, "get_state", Mock(return_value=state))
    monkeypatch.setitem(vars(module), "occupants_of", lambda *_args, **_kwargs: [occupant])
    clear = Mock()
    monkeypatch.setattr(ComponentState, "clear", clear)
    controller = module.StateInfoController()
    query = Mock()
    monkeypatch.setattr(PdiReq, "send", lambda packet: query(packet))
    controller.openFor("ACC", config.tmcc_id, False)
    if has_base_record:
        query.assert_not_called()
    else:
        query.assert_called_once()
        request = query.call_args.args[0]
        assert (request.tmcc_id, request.scope, request.pdi_command) == (config.tmcc_id, scope, PdiCommand.BASE_MEMORY)
        assert {row["key"]: row["value"] for row in controller.model["identity"]} == {"name": "", "number": ""}
        # Simulate identity arriving after the module configuration.
        # noinspection PyProtectedMember
        state._road_name = "Wind Turbine #3"
        # noinspection PyProtectedMember
        state._road_number = "26"
        controller.refresh(False)
        query.assert_called_once()

    info = {row["label"]: row["value"] for row in controller.model["lcsConfiguration"]}
    assert info["Device"] == "AMC2"
    assert info["Address Type"] == config.access_type.name
    assert info["Motor 1 Output Type"] == config.motor1.output_type.label
    assert info["Motor 2 Restore"] == ("On" if config.motor2.restore else "Off")
    fields = {row["key"]: row["value"] for row in controller.model["identity"]}
    assert fields == {"name": "Wind Turbine #3", "number": "0026"}
    assert controller.model["editable"]
    assert not controller.model["canClear"]
    controller.clear()
    clear.assert_not_called()

    write = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", write)
    controller.refresh(False)
    assert not controller.edit("name", "Motor Controller")
    assert controller.saveAccessoryIdentity({"number": "0026"})
    assert not controller.saveAccessoryIdentity({"name": "Yard motors", "number": "12AB"})
    write.assert_not_called()

    assert controller.saveAccessoryIdentity({"number": "42"})
    write.assert_called_once()
    number_req, refreshed = write.call_args.args[0]
    assert number_req.tmcc_id == state.tmcc_id
    assert refreshed is state
    assert state.road_name == "Wind Turbine #3"
    assert state.comp_data.road_name != "Wind Turbine #3"
    fields = {row["key"]: row["value"] for row in controller.model["identity"]}
    assert fields == {"name": "Wind Turbine #3", "number": "0042"}

    write.reset_mock()
    assert controller.saveAccessoryIdentity({"name": " Yard motors "})
    write.assert_called_once()
    name_req, refreshed = write.call_args.args[0]
    assert name_req.tmcc_id == state.tmcc_id
    assert refreshed is state
    fields = {row["key"]: row["value"] for row in controller.model["identity"]}
    assert fields == {"name": "Yard motors", "number": "0042"}
    assert controller.model["lcsConfiguration"] == [{"label": label, "value": value} for label, value in info.items()]


def test_sensor_track_state_info_edits_accessory_identity_and_uses_sensor_board(monkeypatch) -> None:
    module = pytest.importorskip("pytrain_ui.qt.state_info_controller")
    address = 50
    accessory = ComponentStateDict(CommandScope.ACC)[address]
    accessory.initialize(CommandScope.ACC, address)
    accessory.comp_data.road_name = "Upper Main West"
    accessory.comp_data.road_number = "50"
    sensor = ComponentStateDict(CommandScope.IRDA)[address]
    config = PdiReq.from_bytes(bytes.fromhex("d13232033200000005ffff64df"))
    sensor.update(config)
    occupant = LcsOccupant(address, SENSOR_TRACK, SENSOR_TRACK.modes[0], 1, scope=CommandScope.IRDA, config=config)
    monkeypatch.setitem(vars(module), "occupants_of", lambda *_args, **_kwargs: [occupant])
    sensor.update(PdiReq.from_bytes(bytes.fromhex("d132320102030096df")))
    sensor.update(PdiReq.from_bytes(bytes.fromhex("d1323204b101006f77df")))
    states = {CommandScope.ACC: accessory, CommandScope.IRDA: sensor}
    monkeypatch.setattr(ComponentStateStore, "get_state", lambda scope, _address, create=False: states.get(scope))
    write = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", write)
    controller = module.StateInfoController()

    controller.openFor("ACC", address, False, "SENSOR")

    assert controller.model["inlineIdentity"] and controller.model["editable"]
    assert not controller.model["canClear"]
    assert {row["label"]: row["value"] for row in controller.model["lcsConfiguration"]} == {
        "Device": "IR Sensor Track",
        "TMCC ID": "50",
        "Address Type": "ACC",
        "Action": "Begin Run R➟L/End Run L➟R",
        "Engine ID Right ➟ Left": "Any",
        "Engine ID Left ➟ Right": "Any",
    }
    assert {row["label"]: row["value"] for row in controller.model["lcsBoard"]} == {
        "Board ID": "177",
        "Model": "0",
        "Firmware": "2.3.0",
    }
    assert {row["key"]: row["value"] for row in controller.model["identity"]} == {
        "name": "Upper Main West",
        "number": "0050",
    }
    controller.refresh(False)
    write.assert_not_called()
    assert controller.saveAccessoryIdentity({"name": "West Sensor", "number": "51"})
    requests = write.call_args.args[0]
    assert len(requests) == 3 and requests[-1] is accessory
    assert all(req.scope == CommandScope.ACC and req.tmcc_id == address for req in requests[:-1])
    assert {row["key"]: row["value"] for row in controller.model["identity"]} == {
        "name": "West Sensor",
        "number": "0051",
    }


@pytest.mark.parametrize(
    "device,packets,base_id,details,firmware",
    [
        (
            ASC2,
            ["d13e1e031e00000000196adf", "d13e1e0102090098df", "d13e1e041101046d1ddf"],
            30,
            {"Mode": "ACC (mixed)", "Delay": "0.25 s"},
            "2.9.0",
        ),
        (
            BPC2,
            ["d1420103010000008237df", "d1420101020300b7df", "d14201041301056e32df"],
            1,
            {"Mode": "ACC", "Restore on Power-Up": "On"},
            "2.3.0",
        ),
    ],
)
def test_relay_state_info_shows_module_configuration_and_saves_port_identity(
    monkeypatch, device, packets, base_id, details, firmware
) -> None:
    module = pytest.importorskip("pytrain_ui.qt.state_info_controller")
    scope = CommandScope.ACC
    states = ComponentStateDict(scope)
    base, port = states[base_id], states[base_id + 2]
    monkeypatch.setattr(
        ComponentStateStore,
        "get_state",
        lambda requested_scope, address, create=False: states.get(address) if requested_scope == scope else None,
    )
    config, info, board_info = [PdiReq.from_bytes(bytes.fromhex(packet)) for packet in packets]
    for packet in (config, info, board_info):
        base.update(packet)
    port.initialize(scope, port.tmcc_id)
    port.comp_data.road_name = "Loader"
    port.comp_data.road_number = "3"
    assert isinstance(config, (Asc2Req, Bpc2Req))
    occupant = LcsOccupant(
        base_id, device, device.mode_for_pdi_mode(config.mode), 8, scope=scope, state=base, config=config
    )
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_kwargs: [occupant.at(address)])
    writes = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", writes)
    controller = module.StateInfoController()
    controller.openFor("ACC", port.tmcc_id, False, device.label)

    assert controller.model["inlineIdentity"]
    assert controller.model["lcsDeviceType"] == device.label
    assert not controller.model["canClear"]
    assert {row["label"]: row["value"] for row in controller.model["lcsConfiguration"]} == {
        "Device": device.label,
        "Base TMCC ID": str(base_id),
        "Address Type": "ACC",
        "Port": "3",
        **details,
    }
    assert {row["label"]: row["value"] for row in controller.model["lcsBoard"]}["Firmware"] == firmware
    assert {row["key"]: row["value"] for row in controller.model["identity"]} == {"name": "Loader", "number": "0003"}
    writes.assert_not_called()

    assert controller.saveAccessoryIdentity({"number": "81"})
    number, state = writes.call_args.args[0]
    assert state is port and number.tmcc_id == port.tmcc_id
    assert port.comp_data.road_name == "Loader"
    assert port.comp_data.road_number == "0081"


def test_add_accessory_sends_set_address_before_base_identity_writes(monkeypatch) -> None:
    module = pytest.importorskip("pytrain_ui.qt.state_info_controller")
    scope = CommandScope.ACC
    states = ComponentStateDict(scope)
    monkeypatch.setattr(
        ComponentStateStore,
        "get_state",
        lambda requested_scope, address, create=False: (
            (states[address] if create else states.get(address)) if requested_scope == scope else None
        ),
    )
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_kwargs: [object()] if address == 33 else [])
    calls = Mock()
    monkeypatch.setattr(CommandReq, "send", lambda packet: calls.program(packet))
    monkeypatch.setattr(BaseReq, "process_sync_reqs", calls.write)
    controller = module.StateInfoController()
    controller.recordReady.connect(calls.ready)
    controller.openFor("ACC", 0, True)

    assert controller.model["addingAccessory"]
    assert not controller.addAccessory(99, "Conveyor", "4", False)
    assert not controller.addAccessory(4, "", "4", False)
    assert not controller.addAccessory(4, "Conveyor", "", False)
    assert not controller.addAccessory(33, "Conveyor", "4", True)
    assert not calls.mock_calls

    assert controller.addAccessory(4, " Conveyor ", "4", False)

    assert [call[0] for call in calls.mock_calls] == ["program", "write", "ready"]
    command = calls.program.call_args.args[0]
    assert (command.command, command.scope, command.address) == (TMCC1AuxCommandEnum.SET_ADDRESS, scope, 4)
    name, number, state = calls.write.call_args.args[0]
    assert (name.scope, name.tmcc_id, number.scope, number.tmcc_id) == (scope, 4, scope, 4)
    assert state is states[4]
    assert (state.comp_data.road_name, state.comp_data.road_number) == ("Conveyor", "0004")
    calls.ready.assert_called_once_with("ACC", 4)

    calls.reset_mock()
    controller.openFor("ACC", 0, True)
    assert not controller.addAccessory(4, "Replacement", "5", False)
    assert not calls.mock_calls
    assert controller.addAccessory(4, "Replacement", "5", True)
    assert (state.comp_data.road_name, state.comp_data.road_number) == ("Replacement", "0005")


@pytest.mark.parametrize("mode,has_record", [(2, True), (3, False)])
def test_add_asc2_switch_saves_identity_without_programming(monkeypatch, mode, has_record) -> None:
    module = pytest.importorskip("pytrain_ui.qt.ops_controller")
    scope = CommandScope.SWITCH
    states = ComponentStateDict(scope)
    occupant = LcsOccupant(17, ASC2, ASC2.mode_for_pdi_mode(mode), 4, scope=scope).at(19)
    if has_record:
        states[19].initialize(scope, 19)
        states[19].comp_data.road_name = "Yard turnout"
        states[19].comp_data.road_number = "0080"

    def lookup(_scope, address, create=False):
        return states[address] if create else states.get(address)

    monkeypatch.setattr(ComponentStateStore, "get_state", lookup)
    monkeypatch.setattr(ComponentStateStore, "get", Mock(return_value=Mock(get_all=lambda _: list(states.values()))))
    monkeypatch.setattr(CommandDispatcher, "get", Mock(return_value=Mock()))
    monkeypatch.setattr(PdiDispatcher, "is_built", lambda: False)
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_: [occupant] if address == 19 else [])
    dispatch = Mock()
    program = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    monkeypatch.setattr(CommandReq, "build", program)
    controller = module.OpsController(scope)

    identity = controller.switchIdentity(19)
    assert identity["asc2Switch"]
    assert identity["roadName"] == ("Yard turnout" if has_record else "")
    assert not controller.switchIdentity(22)["asc2Switch"]
    assert not controller.canProgramSwitchAddress(19)
    assert controller.programSwitchAddress(19) == "This switch address belongs to an ASC2 port."
    assert controller.canProgramSwitchAddress(22)
    assert controller.addSwitch(19, "East yard", "83", True) == ""
    program.assert_not_called()
    dispatch.assert_called_once()
    name, number, refresh_state = dispatch.call_args.args[0]
    assert name.tmcc_id == number.tmcc_id == 19
    assert refresh_state is states[19]
    assert controller.switchIdentity(19)["roadName"] == "East yard"
    assert controller.switchIdentity(19)["roadNumber"] == "0083"
    assert controller.programSwitchAddress(22) == ""
    program.assert_called_once_with(TMCC1SwitchCommandEnum.SET_ADDRESS, 22)
    program.return_value.send.assert_called_once_with()
    controller.close()


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
