import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("PySide6.QtCore")

from pytrain.db.component_state import ComponentStateDict
from pytrain.gui.accessories.accessory_gui_catalog import AccessoryGuiCatalog, GuiCatalogEntry
from pytrain.gui.accessories.accessory_registry import AccessoryRegistry
from pytrain.gui.accessories.config import configure_accessory
from pytrain.gui.accessories.configured_accessory import ConfiguredAccessory
from pytrain.gui.controller.lcs_device_registry import ASC2
from pytrain.gui.controller.lcs_id_map import LcsOccupant
from pytrain.pdi.amc2_req import Direction
from pytrain.pdi.asc2_req import Asc2Req
from pytrain.pdi.constants import Amc2Action, Asc2Action, Bpc2Action, IrdaAction, PdiCommand
from pytrain.pdi.irda_req import IrdaSequence
from pytrain.pdi.pdi_req import PdiReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import LOCO_ACCESSORY, CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum, TMCC1EngineCommandEnum
from pytrain_ui.adapters import PyTrainCabCommandAdapter, PyTrainCabStateAdapter
from pytrain_ui.qt import accessory_controller as module
from pytrain_ui.qt.accessory_controller import AccessoryCatalogController, AccessoryDescriptor, AccessoryViewKind


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.setattr(module.ConfiguredAccessorySet, "from_file", lambda: SimpleNamespace(configured_all=list))
    monkeypatch.setattr(module.ComponentStateStore, "get", lambda: SimpleNamespace(get_all=lambda _scope: []))
    monkeypatch.setattr(module.ComponentStateStore, "get_state", lambda *_args, **_kwargs: None)
    monkeypatch.setitem(vars(module), "occupants_of", lambda *_args, **_kwargs: [])
    monkeypatch.setitem(vars(module), "occupants", lambda *_args, **_kwargs: [])
    catalog = AccessoryCatalogController()
    yield catalog
    catalog.close()


@pytest.fixture
def sent(monkeypatch):
    requests = []

    def capture(packet):
        requests.append(packet)

    monkeypatch.setattr(PdiReq, "send", capture)
    monkeypatch.setattr(CommandReq, "send", capture)
    return requests


def occupy(monkeypatch, *devices):
    occupants = [
        SimpleNamespace(device=SimpleNamespace(label=kind, key=kind), mode=SimpleNamespace(key=mode))
        for kind, mode in devices
    ]
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_kwargs: occupants if address == 24 else [])


def test_configured_boom_slider_replaces_buttons_and_sends_selected_steps(controller, sent, monkeypatch):
    registry = AccessoryRegistry.get()
    registry.bootstrap()
    configured = ConfiguredAccessory(
        {"gui": "smoke", "tmcc_id": 29, "instance_id": "loader"}, registry, AccessoryGuiCatalog()
    )
    monkeypatch.setattr(
        module.ConfiguredAccessorySet, "from_file", lambda: SimpleNamespace(configured_all=lambda: [configured])
    )
    controller.reload()
    key = "configured:loader"

    operations = controller.operatingView(key)["operations"]
    assert [operation["key"] for operation in operations] == ["lights", "boom", "dispense"]
    assert operations[1]["analogInput"] == {
        "minimum": -5,
        "maximum": 5,
        "neutral": 0,
        "springReturn": True,
        "orientation": "horizontal",
        "repeat": 100,
    }
    legacy_images = {op.key: op.image for op in configured.operation_assets}
    assert legacy_images["boom_left"] == "left_arrow.jpg"
    assert legacy_images["boom_right"] == "right_arrow.jpg"

    for step in (-5, 3, 0, 6):
        controller.sendAnalogOperation(key, "boom", step)
    controller.sendAnalogOperation(key, "boom_left", 2)
    assert [(request.scope, request.address, request.command, request.data) for request in sent] == [
        (CommandScope.ACC, 29, TMCC1AuxCommandEnum.RELATIVE_SPEED, -5),
        (CommandScope.ACC, 29, TMCC1AuxCommandEnum.RELATIVE_SPEED, 3),
        (CommandScope.ACC, 29, TMCC1AuxCommandEnum.RELATIVE_SPEED, 0),
    ]


def install_configured_accessories(controller, monkeypatch, *entries):
    registry = AccessoryRegistry.get()
    registry.bootstrap()
    catalog = AccessoryGuiCatalog()
    configured = [ConfiguredAccessory(entry, registry, catalog) for entry in entries]
    monkeypatch.setattr(
        module.ConfiguredAccessorySet, "from_file", lambda: SimpleNamespace(configured_all=lambda: configured)
    )
    controller.reload()
    return configured


def test_configured_asc2_gate_pulse_and_hold_cleanup(controller, sent, monkeypatch):
    operations = []
    controller.operated.connect(lambda key, roster: operations.append((key, roster)))
    ports = {
        address: LcsOccupant(30, ASC2, ASC2.mode_for_pdi_mode(0), 8, port_index=address - 29, scope=CommandScope.ACC)
        for address in (30, 31, 32, 33)
    }
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_: [ports[address]] if address in ports else [])
    states = ComponentStateDict(CommandScope.ACC)
    monkeypatch.setattr(module.ComponentStateStore, "get_state", lambda _scope, address, **_: states.get(address))

    def update_power(on):
        states[30].update(Asc2Req(30, PdiCommand.ASC2_RX, Asc2Action.CONTROL1, values=int(on)))

    def reject_legacy_import(_entry):
        raise AssertionError("Qt must not load a legacy GUI class")

    monkeypatch.setattr(GuiCatalogEntry, "load_class", reject_legacy_import)
    fire, milk, station = install_configured_accessories(
        controller,
        monkeypatch,
        {"gui": "fire", "instance_id": "fire", "tmcc_ids": {"power": 30, "alarm": 31}},
        {"gui": "milk", "instance_id": "milk", "tmcc_ids": {"power": 30, "conveyor": 32, "eject": 33}},
        {
            "gui": "station",
            "instance_id": "station",
            "variant": "middletown_passenger_station_30_9125",
            "tmcc_ids": {"power": 30, "platform": 32},
        },
    )
    states[32].update(Asc2Req(32, PdiCommand.ASC2_RX, Asc2Action.CONTROL1, values=0))
    update_power(True)
    controller.reload()
    row = controller.descriptor(f"configured:{station.instance_id}")
    assert row["stateSummary"] == "Power: ON · Arrive/Depart: OFF"
    legacy_fire = configure_accessory(fire.definition, tmcc_ids={"power": 30, "alarm": 31})
    assert legacy_fire.image_for("alarm") == "red_light_off.jpg"
    legacy_milk = configure_accessory(milk.definition, tmcc_ids={"power": 30, "conveyor": 32, "eject": 33})
    assert legacy_milk.tmcc_id_for("eject") == 33

    fire_key = "configured:fire"
    milk_key = "configured:milk"
    update_power(False)
    assert not controller.operatingView(fire_key)["operations"][1]["enabled"]
    assert not controller.activateConfiguredOperation(fire_key, "alarm", "fire")
    assert not controller.activateConfiguredOperation(milk_key, "eject", "press")
    assert sent == [] and operations == []
    assert controller.activateConfiguredOperation(fire_key, "power", "on")
    update_power(True)
    alarm = controller.operatingView(fire_key)["operations"][1]
    assert alarm["enabled"] and not controller.operatingView(fire_key)["sharedCommandAddress"]
    assert alarm["animationDuration"] == 5000
    assert alarm["lcsLabels"] == ["ASC2 30 Port 2"]
    assert controller.activateConfiguredOperation(fire_key, "alarm", "fire")
    assert controller.activateConfiguredOperation(milk_key, "eject", "press")
    controller.reload()
    assert controller.operatingView(milk_key)["operations"][2]["held"]
    update_power(False)
    controller.reload()
    assert not controller.activateConfiguredOperation(milk_key, "eject", "release")
    assert [(req.tmcc_id, req.action, req.values, req.time) for req in sent] == [
        (30, Asc2Action.CONTROL1, 1, 0),
        (31, Asc2Action.CONTROL1, 1, alarm["pulseDuration"] / 1000),
        (33, Asc2Action.CONTROL1, 1, 0),
        (33, Asc2Action.CONTROL1, 0, 0),
    ]
    update_power(True)
    assert controller.activateConfiguredOperation(milk_key, "eject", "press")
    controller.releaseConfiguredHolds(milk_key)
    controller.releaseConfiguredHolds(milk_key)
    assert [(req.tmcc_id, req.values) for req in sent[4:]] == [(33, 1), (33, 0)]

    assert operations == [(fire_key, False), (fire_key, False), (milk_key, False), (milk_key, False)]


def test_configured_tmcc_feedback_and_stateless_buttons(controller, sent, monkeypatch):
    states = ComponentStateDict(CommandScope.ACC)
    monkeypatch.setattr(module.ComponentStateStore, "get_state", lambda _scope, address, **_: states.get(address))
    _, smoke = install_configured_accessories(
        controller,
        monkeypatch,
        {"gui": "culvert", "instance_id": "culvert", "tmcc_id": 60},
        {"gui": "smoke", "instance_id": "smoke", "tmcc_id": 29},
    )
    # Exercise the legacy overall-ID call, which accepts None for unused port mappings.
    # noinspection PyTypeChecker
    legacy_smoke = configure_accessory(smoke.definition, tmcc_ids=None, tmcc_id=29)
    assert legacy_smoke.images_for("boom_left", "boom_right") == ("left_arrow.jpg", "right_arrow.jpg")

    culvert = "configured:culvert"
    smoke_key = "configured:smoke"
    assert controller.operatingView(culvert)["operations"][0]["state"] == "UNKNOWN"
    states[60].update(CommandReq.build(TMCC1AuxCommandEnum.AUX2_ON, 60))
    assert controller.operatingView(culvert)["operations"][0]["state"] == "ON"
    states[60].update(CommandReq.build(TMCC1AuxCommandEnum.AUX2_OFF, 60))
    assert controller.operatingView(culvert)["operations"][0]["state"] == "OFF"
    assert controller.activateConfiguredOperation(culvert, "action", "on")
    assert controller.activateConfiguredOperation(culvert, "action", "off")
    assert controller.activateConfiguredOperation(smoke_key, "lights", "on")
    assert controller.activateConfiguredOperation(smoke_key, "lights", "off")
    assert controller.activateConfiguredOperation(smoke_key, "dispense", "fire")
    smoke_view = controller.operatingView(smoke_key)
    assert smoke_view["sharedCommandAddress"] and smoke_view["tmccId"] == 29
    assert smoke_view["cabKeyLabels"] == {
        "NUMERIC:9": "Lights On",
        "NUMERIC:8": "Lights Off",
        "RELATIVE_SPEED": "Fluid Boom",
        "BRAKE": "Dispense",
    }
    assert [(op["label"], op["accessoryKeys"]) for op in smoke_view["operations"]] == [
        ("Lights", "8 (Off) · 9 (On)"),
        ("Fluid Boom", "Throttle"),
        ("Dispense", "Brake"),
    ]
    culvert_view = controller.operatingView(culvert)
    assert culvert_view["sharedCommandAddress"] and culvert_view["operations"][0]["accessoryKeys"] == "Aux 2"
    assert culvert_view["cabKeyLabels"] == {"AUX2_OPT_ONE": "Load"}
    lights = smoke_view["operations"][0]
    assert lights["enabled"] and lights["state"] == "UNKNOWN" and lights["control"] == "command_pair"
    assert [(req.address, req.command, req.data) for req in sent] == [
        (60, TMCC1AuxCommandEnum.AUX2_OPT_ONE, 0),
        (60, TMCC1AuxCommandEnum.AUX2_OPT_ONE, 0),
        (29, TMCC1AuxCommandEnum.AUX_NUMBER_9, 0),
        (29, TMCC1AuxCommandEnum.AUX_NUMBER_8, 0),
        (29, TMCC1AuxCommandEnum.BRAKE, 0),
    ]

    assert [req.as_bytes for req in sent[2:4]] == [
        CommandReq.build(TMCC1AuxCommandEnum.NUMERIC, 29, digit).as_bytes for digit in (9, 8)
    ]

    sent.clear()
    controller.tmccCommand(smoke_key, 29, "NUMERIC", 9)
    controller.tmccCommand(smoke_key, 29, "RELATIVE_SPEED", -5)
    controller.tmccCommand(culvert, 60, "AUX2_OPT_ONE", 0)
    controller.tmccCommand(smoke_key, 60, "NUMERIC", 8)
    assert [(req.address, req.command, req.data) for req in sent] == [
        (29, TMCC1AuxCommandEnum.NUMERIC, 9),
        (29, TMCC1AuxCommandEnum.RELATIVE_SPEED, -5),
        (60, TMCC1AuxCommandEnum.AUX2_OPT_ONE, 0),
    ]


def test_quick_operations_remember_the_exact_roster_row(controller, sent, monkeypatch):
    occupy(monkeypatch, ("ASC2", "acc_8"), ("BPC2", "acc_8"))
    asc2 = AccessoryDescriptor(
        "asc2:24", (24,), 24, "Relay", "", None, ("ASC2 24",), (AccessoryViewKind.LCS,), AccessoryViewKind.LCS, True
    )
    bpc2 = AccessoryDescriptor(
        "bpc2:24", (24,), 24, "Power", "", None, ("BPC2 24",), (AccessoryViewKind.LCS,), AccessoryViewKind.LCS, True
    )
    # Inject colocated rows into the private index to verify retained device identity.
    # noinspection PyProtectedMember,PyUnresolvedReferences
    monkeypatch.setattr(controller, "_descriptors", {asc2.key: asc2, bpc2.key: bpc2})
    operations = []
    controller.operated.connect(lambda key, roster: operations.append((key, roster)))

    controller.holdQuickAction(24, True)
    controller.holdQuickAction(24, False)
    controller.quickAction("ON", 24, "BPC2")
    controller.quickAction("OFF", 25, "BPC2")

    assert operations == [(asc2.key, True), (bpc2.key, True)]
    assert len(sent) == 3


def test_colocated_bpc2_and_asc2_send_to_the_selected_device(controller, sent, monkeypatch):
    occupy(monkeypatch, ("BPC2", "acc_8"), ("ASC2", "acc_8"))
    controller.quickAction("ON", 24, "BPC2")
    controller.quickAction("OFF", 24, "BPC2")
    controller.quickAction("ON", 24, "ASC2")
    controller.quickAction("OFF", 24, "ASC2")
    assert [(req.tmcc_id, req.pdi_command, req.action, req.state) for req in sent] == [
        (24, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, 1),
        (24, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, 0),
        (24, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, 1),
        (24, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, 0),
    ]


def test_asc2_release_reaches_original_address_after_discovery_changes(controller, sent, monkeypatch):
    occupy(monkeypatch, ("ASC2", "acc_8"))
    controller.holdQuickAction(24, True)
    controller.holdQuickAction(24, True)
    occupy(monkeypatch)
    controller.holdQuickAction(25, False)
    controller.holdQuickAction(24, False)
    controller.holdQuickAction(24, False)
    assert [(req.tmcc_id, req.action, req.values, req.time) for req in sent] == [
        (24, Asc2Action.CONTROL1, 1, 0),
        (24, Asc2Action.CONTROL1, 0, 0),
    ]


@pytest.mark.parametrize("kind,mode", [("ASC2", "acc_1"), ("BPC2", "acc_8")])
def test_momentary_is_unavailable_on_uncoupling_asc2_and_bpc2(controller, sent, monkeypatch, kind, mode):
    occupy(monkeypatch, (kind, mode))
    controller.holdQuickAction(24, True)
    controller.holdQuickAction(24, False)
    controller.quickAction("MOMENTARY", 24, kind)
    if kind == "ASC2":
        controller.quickAction("ON", 24, kind)
    assert sent == []


def add_descriptor(controller, monkeypatch, kind):
    # The descriptor prefix is the literal IRDA protocol identity used by the controller.
    # noinspection SpellCheckingInspection
    scope_key = "irda:24" if kind == "SENSOR" else "acc:24"
    labels = () if kind == "TMCC" else (f"{kind} 24",)
    preferred = AccessoryViewKind.GENERIC if kind == "TMCC" else AccessoryViewKind.LCS
    descriptor = AccessoryDescriptor(scope_key, (24,), 24, kind, "", None, labels, (preferred,), preferred, True)

    # Supply a discovered descriptor to exercise the same slots that QML invokes.
    # noinspection PyProtectedMember
    monkeypatch.setitem(controller._descriptors, scope_key, descriptor)
    return scope_key


def test_tmcc_keypad_and_relative_speed_target_the_selected_address(controller, sent, monkeypatch):
    key = add_descriptor(controller, monkeypatch, "TMCC")
    controller.tmccCommand(key, 24, "NUMERIC", 9)
    controller.tmccCommand(key, 24, "RELATIVE_SPEED", -5)
    controller.tmccCommand(key, 24, "RELATIVE_SPEED", 0)
    controller.tmccCommand(key, 24, "BOOST", 0)
    controller.tmccCommand(key, 24, "SET_ADDRESS", 0)
    controller.tmccCommand(key, 24, "AUX1_ON", 0)
    controller.tmccCommand(key, 24, "AUX1_OFF", 0)
    for unsupported in ("HORN", "BELL", "AUX3_OPT_ONE"):
        controller.tmccCommand(key, 24, unsupported, 0)
    controller.tmccCommand(key, 25, "BRAKE", 0)
    controller.tmccCommand(key, 24, "RELATIVE_SPEED", 6)
    assert [(req.address, req.command, req.data) for req in sent] == [
        (24, TMCC1AuxCommandEnum.NUMERIC, 9),
        (24, TMCC1AuxCommandEnum.RELATIVE_SPEED, -5),
        (24, TMCC1AuxCommandEnum.RELATIVE_SPEED, 0),
        (24, TMCC1AuxCommandEnum.BOOST, 0),
        (24, TMCC1AuxCommandEnum.SET_ADDRESS, 0),
        (24, TMCC1AuxCommandEnum.AUX1_ON, 0),
        (24, TMCC1AuxCommandEnum.AUX1_OFF, 0),
    ]


def test_accessory_engine_panel_uses_current_address_and_tmcc1_engine_scope(sent):
    state = SimpleNamespace(scope=CommandScope.ENGINE, tmcc_id=39, engine_type=LOCO_ACCESSORY, is_legacy=True)
    adapter = PyTrainCabCommandAdapter(Mock(spec=PyTrainCabStateAdapter, state=state))
    assert adapter.is_cab1
    adapter.accessory_engine_command("NUMERIC", 0)
    adapter.accessory_engine_command("NUMERIC", 9)
    adapter.accessory_engine_command("HORN", 0)
    adapter.accessory_engine_command("BELL", 0)
    adapter.accessory_engine_command("SET_ADDRESS", 0)
    adapter.accessory_engine_command("NUMERIC", 10)
    adapter.accessory_engine_command("START_UP_IMMEDIATE", 0)
    adapter.accessory_engine_command("SHUTDOWN_IMMEDIATE", 0)
    assert adapter.supports_smoke()
    adapter.set_smoke(1)
    adapter.set_momentum(3)
    assert [(req.scope, req.address, req.command, req.data) for req in sent] == [
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.NUMERIC, 0),
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.NUMERIC, 9),
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.BLOW_HORN_ONE, 0),
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.RING_BELL, 0),
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.SET_ADDRESS, 0),
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.START_UP_IMMEDIATE, 0),
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.SHUTDOWN_IMMEDIATE, 0),
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.SMOKE_ON, 0),
        (CommandScope.ENGINE, 39, TMCC1EngineCommandEnum.MOMENTUM_MEDIUM, 0),
    ]
    assert all(req.command_def.is_aux1_prefixed for req in sent[5:7])
    assert [req.as_bytes[-1] & 0x0F for req in sent[5:7]] == [3, 5]


def test_sensor_sequence_targets_the_sensor_track_device(controller, sent, monkeypatch):
    key = add_descriptor(controller, monkeypatch, "SENSOR")
    controller.setSensorSequence(key, 9)
    controller.setSensorSequence(key, 100)
    assert len(sent) == 1
    request = sent[0]
    assert (request.tmcc_id, request.pdi_command, request.action, request.sequence) == (
        24,
        PdiCommand.IRDA_SET,
        IrdaAction.SEQUENCE,
        IrdaSequence(9),
    )


def test_amc2_motor_and_lamp_target_the_selected_outputs(controller, sent, monkeypatch):
    key = add_descriptor(controller, monkeypatch, "AMC2")
    controller.setAmc2Output(key, True, 2, 37)
    controller.setAmc2Output(key, False, 4, 46)
    controller.setAmc2Output(key, True, 3, 50)
    motor, select_motor, power_motor, lamp, select_lamp = sent
    assert (motor.tmcc_id, motor.action, motor.motor, motor.speed) == (24, Amc2Action.MOTOR, 2, 37)
    assert (lamp.tmcc_id, lamp.action, lamp.lamp, lamp.level) == (24, Amc2Action.LAMP, 4, 46)
    assert [(req.command, req.data) for req in (select_motor, power_motor, select_lamp)] == [
        (TMCC1AuxCommandEnum.NUMERIC, 2),
        (TMCC1AuxCommandEnum.AUX1_OPT_ONE, 0),
        (TMCC1AuxCommandEnum.NUMERIC, 6),
    ]


@pytest.mark.parametrize("motor", [True, False])
def test_amc2_power_preserves_the_slider_level_until_set_to_an_endpoint(controller, sent, monkeypatch, motor):
    key = add_descriptor(controller, monkeypatch, "AMC2")
    motor_state = SimpleNamespace(speed=65, direction=Direction.FORWARD)
    lamp_state = SimpleNamespace(level=65)
    state = SimpleNamespace(
        get_motor=lambda _channel: motor_state,
        get_lamp=lambda _channel: lamp_state,
        is_motor_on=lambda motor_readback: motor_readback.speed > 0,
    )
    # Replace only the readback lookup so packet assertions still use the real sender.
    # noinspection PyProtectedMember
    monkeypatch.setattr(
        AccessoryCatalogController, AccessoryCatalogController._state.__name__, staticmethod(lambda _address: state)
    )

    def reading():
        return controller.operatingView(key)["motors" if motor else "lights"][0]

    assert reading() == {"level": 65, "on": True}
    controller.setAmc2Power(key, motor, 1, False)
    if motor:
        assert (sent[0].action, sent[0].speed) == (Amc2Action.MOTOR, 0)
        assert [req.command for req in sent[1:]] == [TMCC1AuxCommandEnum.NUMERIC, TMCC1AuxCommandEnum.AUX2_OPT_ONE]
    else:
        assert (sent[0].action, sent[0].level) == (Amc2Action.LAMP, 0)
    motor_state.speed = lamp_state.level = 0
    assert reading() == {"level": 65, "on": False}

    sent.clear()
    controller.setAmc2Power(key, motor, 1, True)
    if motor:
        assert (sent[0].speed, sent[0].direction) == (65, Direction.FORWARD)
    else:
        assert sent[0].level == 65
    assert reading() == {"level": 65, "on": True}

    controller.setAmc2Output(key, motor, 1, 0)
    assert reading() == {"level": 0, "on": False}
    sent.clear()
    controller.setAmc2Power(key, motor, 1, True)
    assert not sent
    assert reading() == {"level": 0, "on": False}

    controller.setAmc2Output(key, motor, 1, 100)
    assert reading() == {"level": 100, "on": True}


def test_configured_accessory_appears_once_with_its_artwork_and_address_search_keys(controller, monkeypatch, tmp_path):
    artwork = tmp_path / "loading-dock.png"
    artwork.touch()
    monkeypatch.setattr(
        "pytrain_ui.qt.accessory_controller.find_file", lambda filename: artwork if filename == artwork.name else None
    )
    registry = Mock()
    registry.get_spec.return_value = SimpleNamespace(
        operations=[SimpleNamespace(key=key) for key in ("power", "alarm", "optional")]
    )
    registry.get_operation_label_for_state.side_effect = lambda _spec, key, **_kwargs: key.title()
    definition = SimpleNamespace(type="test", variant=None)
    configured = SimpleNamespace(
        instance_id="loading-dock",
        accessory_type=module.AccessoryType.FIRE_STATION,
        label="Loading Dock",
        tmcc_id=24,
        tmcc_ids=[24, 25],
        image_path=artwork.name,
        registry=registry,
        definition=definition,
        tmcc_id_for={"power": 24, "alarm": 25}.__getitem__,
    )
    other = SimpleNamespace(
        instance_id="other-dock",
        accessory_type=module.AccessoryType.FIRE_STATION,
        label="Loading Dock",
        tmcc_id=26,
        tmcc_ids=[26],
        image_path=None,
        registry=Mock(get_spec=Mock(return_value=SimpleNamespace(operations=[]))),
        definition=definition,
    )
    ports = {
        address: LcsOccupant(24, ASC2, ASC2.mode_for_pdi_mode(0), 8, port_index=address - 23, scope=CommandScope.ACC)
        for address in (24, 25)
    }
    monkeypatch.setitem(
        vars(module), "occupants_of", lambda address, **_kwargs: [ports[address]] if address in ports else []
    )
    monkeypatch.setattr(
        module.ConfiguredAccessorySet,
        "from_file",
        lambda: SimpleNamespace(configured_all=lambda: [configured] * 2 + [other]),
    )
    states = ComponentStateDict(CommandScope.ACC)
    records = [states[address] for address in (24, 25, 26, 27)]
    states[24].initialize(CommandScope.ACC, 24)
    states[24].comp_data.road_number = "0024"
    states[24].update(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONTROL1, values=0))
    states[25].update(Asc2Req(25, PdiCommand.ASC2_RX, Asc2Action.CONTROL1, values=1))
    monkeypatch.setattr(module.ComponentStateStore, "get_state", lambda _scope, address, **_kwargs: states.get(address))
    monkeypatch.setattr(
        module.ComponentStateStore,
        "get",
        lambda: SimpleNamespace(get_all=lambda scope: records if scope == CommandScope.ACC else []),
    )

    controller.reload()

    rows = [row for row in controller.rows if row["kind"] != "ASC2"]
    assert [(row["kind"], row["key"], row["tmccIds"]) for row in rows] == [
        ("TMCC", "acc:27", [27]),
        ("OPERATING", "configured:loading-dock", [24, 25]),
        ("OPERATING", "configured:other-dock", [26]),
    ]
    assert rows[1]["imageSource"] == artwork.as_uri()
    assert rows[1]["roadNumber"] == ""
    assert rows[2]["imageSource"] == ""
    assert rows[1]["lcsAssociations"] == "ASC2 24 Port 1 · ASC2 24 Port 2"
    assert rows[1]["stateSummary"] == "Power: OFF · Alarm: ON"
    assert rows[1]["componentNames"] == "Power · Alarm"
    assert rows[2]["componentNames"] == ""


def test_switch_mode_is_excluded_from_accessory_rows_and_mixed_ports_are_discoverable(controller, monkeypatch):
    mixed = LcsOccupant(24, ASC2, ASC2.mode_for_pdi_mode(0), 8, scope=CommandScope.ACC)
    switch = LcsOccupant(40, ASC2, ASC2.mode_for_pdi_mode(3), 4, scope=CommandScope.ACC)
    acc_states = ComponentStateDict(CommandScope.ACC)
    acc_records = [acc_states[address] for address in (30, 40, 41, 55)]
    acc_states[30].initialize(CommandScope.ACC, 30)
    acc_states[30].comp_data.road_number = "0030"

    def get_all(scope):
        return acc_records if scope == CommandScope.ACC else []

    monkeypatch.setattr(module.ComponentStateStore, "get", lambda: SimpleNamespace(get_all=get_all))
    monkeypatch.setitem(vars(module), "occupants", lambda scope: [mixed] if scope == CommandScope.ACC else [switch])
    monkeypatch.setitem(
        vars(module), "occupants_of", lambda address, **_kwargs: [mixed.at(address)] if mixed.claims(address) else []
    )

    controller.reload()
    rows = {row["primaryTmccId"]: row for row in controller.rows}
    assert set(rows) == {*range(24, 32), 55}
    assert rows[55]["kind"] == "TMCC"
    assert rows[31]["kind"] == "ASC2"
    assert not rows[31]["userDefined"]
    assert rows[30]["userDefined"]
    assert [(action["label"], action["selected"]) for action in rows[31]["quickActions"]] == [
        ("On", False),
        ("Off", False),
        ("Hold", False),
    ]


# The embedded Qt API identifiers retain their exact spelling.
# noinspection SpellCheckingInspection
ROSTER_CHILD = r"""
from pathlib import Path
import sys

from PySide6.QtCore import QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine)
component.setData(b'''
import QtQuick
import QtQuick.Controls
import "."
ApplicationWindow {
    id: win
    width: 639
    height: 800
    visible: true
    property string calls: ""
    property bool cover: false
    property string relayFilter: ""
    property string recalledRow: ""
    property int feedbackRevision: 0
    property var missingKinds: []
    property var unnamedKinds: []
    property string openedAccessory: ""
    readonly property string filterKeys: roster.typeFilters.map(filter => filter.key).join(",")
    readonly property string selectedFilter: roster.typeFilter
    QtObject {
        id: backend
        readonly property var rows: ["OPERATING", "BPC2", "ASC2", "AMC2", "SENSOR", "TMCC"].map((kind, index) => ({
            kind: kind, key: kind, primaryTmccId: index + 10, tmccIds: [index + 10],
            roadName: kind, roadNumber: "0001", lcsAssociations: "Port 1", stateSummary: "",
            userDefined: !win.unnamedKinds.includes(kind), availableViews: [], imageSource: "",
            quickActions: kind === "BPC2" || kind === "ASC2" ? [
                {key: "ON", label: "On", selected: win.feedbackRevision > 0},
                {key: "OFF", label: "Off", selected: false}
            ].concat(kind === "ASC2" ? [{key: "HOLD", label: "Hold", selected: false}] : []) : []
        })).filter(row => !win.missingKinds.includes(row.kind))
        function holdQuickAction(address, pressed) { win.calls += address + (pressed ? "+" : "-") }
        function quickAction(action, address, kind) { win.calls += action + address + kind }
    }
    AccessoryCatalog {
        id: roster
        width: parent.width
        height: parent.height - 106
        visible: win.relayFilter.length > 0
        controller: backend
        onAccessoryRequested: key => win.openedAccessory = key
        onEditRequested: (address, kind) => win.calls += "EDIT" + address + kind
        Connections {
            target: win
            function onRelayFilterChanged() { roster.typeFilter = win.relayFilter }
            function onRecalledRowChanged() { roster.restoreRosterPosition(win.recalledRow) }
        }
    }

    AccessoryOperatingView {
        width: 639; height: 800
        visible: false
        controller: backend
        accessory: ({kind: "TMCC", key: "acc:24", tmccId: 24, title: "Test Accessory"})
    }

    AccessoryActionButton {
        width: 180; height: 60
        objectName: "momentary"
        controller: backend
        tmccId: 24
        deviceKind: "ASC2"
        action: "HOLD"
        enabled: !win.cover
    }
    component PowerButton: AccessoryActionButton {
        width: 110; height: 60
        controller: backend
    }
    PowerButton { objectName: "ON24ASC2"; x: 185; tmccId: 24; deviceKind: "ASC2"; action: "ON" }
    PowerButton { objectName: "OFF24ASC2"; x: 305; tmccId: 24; deviceKind: "ASC2"; action: "OFF" }
    PowerButton { objectName: "ON42BPC2"; x: 425; tmccId: 42; deviceKind: "BPC2"; action: "ON" }
    PowerButton { objectName: "OFF42BPC2"; x: 525; tmccId: 42; deviceKind: "BPC2"; action: "OFF" }
    Component.onCompleted: {
        const expected = {
            All: "OPERATING,BPC2,ASC2,AMC2,SENSOR,TMCC",
            Operating: "OPERATING", LCS: "BPC2,ASC2,AMC2,SENSOR", TMCC: "TMCC",
            Sensor: "SENSOR", BPC2: "BPC2", ASC2: "ASC2", AMC2: "AMC2"
        }
        for (const label of Object.keys(expected)) {
            roster.typeFilter = label.toUpperCase()
            const actual = roster.visibleRows().map(row => row.kind).join(",")
            if (actual !== expected[label])
                throw new Error(label + " filter returned " + actual)
        }
        roster.typeFilter = "ALL"
        roster.searchText = "13"
        if (roster.visibleRows()[0].kind !== "AMC2")
            throw new Error("Address search did not find AMC2")
        roster.searchText = ""
        roster.sortMode = "TMCC"
        if (roster.visibleRows()[0].primaryTmccId !== 10)
            throw new Error("Address sort failed")
        if (roster.showUnnamedAccessories)
            throw new Error("Show Unnamed must be unchecked by default")
        win.unnamedKinds = ["ASC2", "AMC2", "SENSOR"]
        for (const filter of ["ALL", "LCS", "ASC2"]) {
            roster.typeFilter = filter
            if (roster.visibleRows().some(row => row.kind === "ASC2"))
                throw new Error("Unnamed ASC2 appeared in " + filter)
        }
        roster.showUnnamedAccessories = true
        if (roster.visibleRows().map(row => row.kind).join(",") !== "ASC2")
            throw new Error("Show Unnamed did not reveal ASC2")
        roster.showUnnamedAccessories = false
        roster.selectTmccId(12, true)
        if (roster.visibleRows().map(row => row.kind).join(",") !== "ASC2")
            throw new Error("Exact address did not reveal unnamed ASC2")
        roster.showRoster()
        for (const [address, kind] of [[10, "OPERATING"], [13, "AMC2"], [14, "SENSOR"], [15, "TMCC"]]) {
            roster.selectTmccId(address, true)
            if (win.openedAccessory !== kind)
                throw new Error("Exact address did not open unnamed " + kind)
        }
        win.unnamedKinds = ["AMC2", "SENSOR", "TMCC"]
        for (const fromSearch of [false, true]) {
            for (const [address, kind] of [[10, "OPERATING"], [13, "AMC2"], [14, "SENSOR"], [15, "TMCC"]]) {
                win.openedAccessory = ""
                roster.typeFilter = "BPC2"
                roster.searchText = "unrelated search"
                roster.selectTmccId(address, fromSearch)
                if (win.openedAccessory !== kind || roster.directTmccId !== 0 || roster.searchText !== "")
                    throw new Error("Exact ID did not open " + kind + " directly")
            }
        }
        win.unnamedKinds = []
    }
}
''', QUrl.fromLocalFile(str(Path(sys.argv[1]) / "accessory_validation.qml")))
assert component.isReady(), [error.toString() for error in component.errors()]
window = component.create()
assert isinstance(window, QQuickWindow)
window.requestActivate()
QTest.qWait(100)
button = window.findChild(QQuickItem, "momentary")
assert button is not None
point = button.mapToScene(button.boundingRect().center()).toPoint()

QTest.mousePress(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+", "Hold must energize the port on press"
QTest.mouseRelease(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+24-", "Even a short press must release the port"

window.setProperty("calls", "")
QTest.mousePress(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+"
QTest.mouseMove(window, point + QPoint(0, 120))
assert window.property("calls") == "24+24-", "Dragging off Hold must release the port"
QTest.mouseRelease(window, Qt.LeftButton, pos=point + QPoint(0, 120))
assert window.property("calls") == "24+24-"

window.setProperty("calls", "")
QTest.mousePress(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+"
window.setProperty("cover", True)
QTest.mouseRelease(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+24-", "Covering the roster must release the port once"

for expected in ("ON24ASC2", "OFF24ASC2", "ON42BPC2", "OFF42BPC2"):
    window.setProperty("calls", "")
    action_button = window.findChild(QQuickItem, expected)
    assert action_button is not None
    position = action_button.mapToScene(action_button.boundingRect().center()).toPoint()
    QTest.mousePress(window, Qt.LeftButton, pos=position)
    assert window.property("calls") == ""
    QTest.mouseRelease(window, Qt.LeftButton, pos=position)
    assert window.property("calls") == expected

def descendants(parent):
    for child in parent.childItems():
        yield child
        yield from descendants(child)

for kind, address in (("ASC2", 12), ("BPC2", 11)):
    window.setProperty("relayFilter", kind)
    QTest.qWait(80)
    viewport = window.findChild(QQuickItem, "accessoryRoster")
    assert viewport is not None
    on = next(item for item in descendants(viewport) if item.property("action") == "ON")
    position = on.mapToScene(on.boundingRect().center())
    assert viewport.contains(viewport.mapFromScene(position)), "The first relay row must fit inside the compact list"
    window.setProperty("calls", "")
    QTest.mousePress(window, Qt.LeftButton, pos=position.toPoint())
    window.setProperty("feedbackRevision", window.property("feedbackRevision") + 1)
    QTest.qWait(35)
    assert not window.property("calls")
    QTest.mouseRelease(window, Qt.LeftButton, pos=position.toPoint())
    assert window.property("calls") == f"ON{address}{kind}", "Feedback must preserve the in-progress relay click"

window.setProperty("relayFilter", "ASC2")
QTest.qWait(80)
viewport = window.findChild(QQuickItem, "accessoryRoster")
row = next(item for item in descendants(viewport) if item.objectName() == "accessoryRosterRow-ASC2")
position = row.mapToScene(QPointF(row.width() / 2, 30)).toPoint()
window.setProperty("calls", "")
QTest.mousePress(window, Qt.LeftButton, pos=position)
assert window.property("calls") == "", "A row tap must not begin a hold before the threshold"
QTest.qWait(700)
assert window.property("calls") == "12+", "Holding the ASC2 row body must energize its port"
window.setProperty("feedbackRevision", window.property("feedbackRevision") + 1)
QTest.qWait(60)
QTest.mouseRelease(window, Qt.LeftButton, pos=position)
assert window.property("calls") == "12+12-", "Feedback must not lose or duplicate the row release"
QTest.qWait(40)

for action in ("ON", "OFF", "HOLD", "EDIT"):
    window.setProperty("calls", "")
    row = next(item for item in descendants(viewport) if item.objectName() == "accessoryRosterRow-ASC2")
    button = next(item for item in descendants(row)
                  if item.property("action") == action or (action == "EDIT" and item.property("text") == "Edit"))
    point = button.mapToScene(button.boundingRect().center()).toPoint()
    QTest.mousePress(window, Qt.LeftButton, pos=point)
    QTest.qWait(700)
    expected = "12+" if action == "HOLD" else ""
    assert window.property("calls") == expected, "Row hold must exclude nested " + action
    QTest.mouseRelease(window, Qt.LeftButton, pos=point)
    expected = "12+12-" if action == "HOLD" else action + "12ASC2"
    assert window.property("calls") == expected, "Nested action must run exactly once: " + action
    QTest.qWait(40)

window.setProperty("calls", "")
row = next(item for item in descendants(viewport) if item.objectName() == "accessoryRosterRow-ASC2")
position = row.mapToScene(QPointF(row.width() / 2, 30)).toPoint()
QTest.mousePress(window, Qt.LeftButton, pos=position)
QTest.qWait(700)
assert window.property("calls") == "12+"
QTest.mouseMove(window, position + QPoint(0, 120))
QTest.mouseRelease(window, Qt.LeftButton, pos=position + QPoint(0, 120))
assert window.property("calls") == "12+12-", "Canceling a row hold must release once"

window.setProperty("calls", "")
row = next(item for item in descendants(viewport) if item.objectName() == "accessoryRosterRow-ASC2")
position = row.mapToScene(QPointF(row.width() / 2, 30)).toPoint()
QTest.mousePress(window, Qt.LeftButton, pos=position)
QTest.mouseMove(window, position + QPoint(0, 120))
QTest.mouseRelease(window, Qt.LeftButton, pos=position + QPoint(0, 120))
QTest.qWait(700)
assert window.property("calls") == "", "Scrolling before the hold threshold must not energize the port"

window.setProperty("calls", "")
row = next(item for item in descendants(viewport) if item.objectName() == "accessoryRosterRow-ASC2")
position = row.mapToScene(QPointF(row.width() / 2, 30)).toPoint()
QTest.mousePress(window, Qt.LeftButton, pos=position)
QTest.qWait(700)
assert window.property("calls") == "12+"
viewport.setEnabled(False)
QTest.mouseRelease(window, Qt.LeftButton, pos=position)
assert window.property("calls") == "12+12-", "Disabling the roster must release a row hold once"
viewport.setEnabled(True)

# Restore the original filter before checking removal of its device type.
window.setProperty("relayFilter", "BPC2")
QTest.qWait(40)
assert window.property("filterKeys") == "ALL,OPERATING,LCS,TMCC,SENSOR,BPC2,ASC2,AMC2"
window.setProperty("missingKinds", ["BPC2", "OPERATING", "SENSOR"])
QTest.qWait(35)
assert window.property("filterKeys") == "ALL,LCS,TMCC,ASC2,AMC2"
assert window.property("selectedFilter") == "ALL"

window.setProperty("missingKinds", ["BPC2", "ASC2", "AMC2", "SENSOR"])
QTest.qWait(35)
assert window.property("filterKeys") == "ALL,OPERATING,TMCC"
window.setProperty("missingKinds", ["BPC2", "ASC2", "AMC2", "SENSOR", "OPERATING"])
QTest.qWait(35)
assert window.property("filterKeys") == "ALL,TMCC"

window.setProperty("missingKinds", [])
window.setProperty("relayFilter", "ASC2")
QTest.qWait(40)
window.setProperty("recalledRow", "TMCC")
QTest.qWait(80)
viewport = window.findChild(QQuickItem, "accessoryRoster")
target = next(item for item in descendants(viewport) if item.objectName() == "accessoryRosterRow-TMCC")
assert abs(target.mapToItem(viewport, 0, 0).y()) <= 1, "Recall must top-align the last row"
assert window.property("selectedFilter") == "ALL", "Recall must reveal a row excluded by the current filter"

window.close()
"""


def assert_qml_scenario(source: str) -> None:
    qml_directory = Path(__file__).resolve().parents[2] / "src" / "pytrain_ui" / "qt" / "qml"
    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-c", source, str(qml_directory)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Error:" not in result.stderr, result.stderr


@pytest.mark.qt_gui
def test_roster_filters_and_momentary_pointer_behavior() -> None:
    assert_qml_scenario(ROSTER_CHILD)


# The embedded Qt API identifiers retain their exact spelling.
# noinspection SpellCheckingInspection
OPERATING_CHILD = r"""
from pathlib import Path
import sys

from PySide6.QtCore import QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine)
component.setData(b'''
import QtQuick
import QtQuick.Controls
import "."
ApplicationWindow {
    id: window
    width: 720
    height: 850
    visible: true
    property bool powerOn: false
    property bool held: false
    property string calls: ""
    property bool panelVisible: true
    property bool stationPreview: false
    property bool platformOn: false
    property bool thirdControl: false
    QtObject {
        id: backend
        function activateConfiguredOperation(key, operation, action) {
            if (operation === "hold" && action === "release" && !window.held)
                return false
            window.calls += operation + ":" + action + ";"
            if (operation === "hold")
                window.held = action === "press"
            return true
        }
        function releaseConfiguredHolds(key) {
            if (window.held)
                activateConfiguredOperation(key, "hold", "release")
        }
    }
    AccessoryOperatingView {
        anchors.fill: parent
        visible: window.panelVisible
        controller: backend
        accessory: window.stationPreview ? ({key: "station", kind: "OPERATING", tmccId: 30, operations: [
            {key: "power", label: "Power", control: "latch", enabled: true, state: window.powerOn ? "ON" : "OFF"},
            {key: "platform", label: "Platform", control: "latch", enabled: window.powerOn,
                state: window.platformOn ? "ON" : "OFF", actionLabel: window.platformOn ? "Arrive" : "Depart"}
        ].concat(window.thirdControl ? [
            {key: "eject", label: "Eject", control: "momentary_hold", enabled: window.powerOn, state: "OFF"}
        ] : [])}) : ({key: "test", kind: "OPERATING", tmccId: 30, operations: [
            {key: "alarm", label: "Alarm", control: "momentary_pulse", enabled: window.powerOn,
                state: "OFF", pulseDuration: 50, animationDuration: 500, lcsLabels: []},
            {key: "hold", label: "Eject", control: "momentary_hold", enabled: window.powerOn,
                state: window.held ? "ON" : "OFF", held: window.held, lcsLabels: []}
        ]})
    }
}
''', QUrl.fromLocalFile(str(Path(sys.argv[1]) / "OperatingGestureTest.qml")))
window = component.create()
assert window is not None, component.errorString()

def find_item(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = find_item(child, name)
        if found is not None:
            return found
    return None

def center(button):
    return button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()

QTest.qWait(75)
alarm = find_item(window.contentItem(), "accessoryOperation-alarm-fire")
hold = find_item(window.contentItem(), "accessoryOperation-hold-press")
assert alarm is not None and hold is not None
assert not alarm.isEnabled() and not hold.isEnabled()
QTest.mouseClick(window, Qt.LeftButton, pos=center(alarm))
assert window.property("calls") == ""

window.setProperty("powerOn", True)
QTest.qWait(40)
assert alarm.isEnabled() and hold.isEnabled()
QTest.mouseClick(window, Qt.LeftButton, pos=center(alarm))
assert window.property("calls") == "alarm:fire;"
alarm_row = alarm.parentItem().parentItem().parentItem().parentItem()
assert alarm_row.property("artworkActive") is True
QTest.qWait(100)
assert alarm_row.property("artworkActive") is True
QTest.qWait(500)
assert alarm_row.property("artworkActive") is False

point = center(hold)
QTest.mousePress(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "alarm:fire;hold:press;"
assert window.property("held") is True
QTest.mouseRelease(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "alarm:fire;hold:press;hold:release;"

QTest.mousePress(window, Qt.LeftButton, pos=point)
window.setProperty("panelVisible", False)
QTest.mouseRelease(window, Qt.LeftButton, pos=point)
calls = window.property("calls")
assert calls == "alarm:fire;hold:press;hold:release;hold:press;hold:release;", calls
window.setProperty("powerOn", False)
window.setProperty("stationPreview", True)
window.setProperty("panelVisible", True)
QTest.qWait(60)
power = find_item(window.contentItem(), "accessoryOperation-power-toggle")
platform = find_item(window.contentItem(), "accessoryOperation-platform-toggle")
assert power is not None and platform is not None
assert center(power).y() == center(platform).y() and center(power).x() < center(platform).x()
assert power.property("trialIcon") == "power-on" and not platform.isEnabled()
QTest.mouseClick(window, Qt.LeftButton, pos=center(power))
assert window.property("calls").endswith("power:on;")
assert power.property("trialIcon") == "power-on"
window.setProperty("powerOn", True)
assert power.property("trialIcon") == "power-off" and platform.isEnabled()
assert platform.property("text") == "Depart"
QTest.mouseClick(window, Qt.LeftButton, pos=center(platform))
assert window.property("calls").endswith("platform:on;")
window.setProperty("platformOn", True)
assert platform.property("text") == "Arrive"
QTest.mouseClick(window, Qt.LeftButton, pos=center(platform))
assert window.property("calls").endswith("platform:off;")
QTest.mouseClick(window, Qt.LeftButton, pos=center(power))
assert window.property("calls").endswith("power:off;")

window.setProperty("thirdControl", True)
QTest.qWait(60)
power = find_item(window.contentItem(), "accessoryOperation-power-toggle")
platform = find_item(window.contentItem(), "accessoryOperation-platform-toggle")
eject = find_item(window.contentItem(), "accessoryOperation-eject-press")
assert power is not None and platform is not None and eject is not None
assert center(power).y() == center(platform).y() == center(eject).y()
assert center(power).x() < center(platform).x() < center(eject).x()
assert center(eject).x() + eject.width() / 2 <= window.width()
assert power.width() == power.height() == platform.width() == eject.width()

tabs = find_item(window.contentItem(), "operatingAccessoryTabs")
controls_tab = find_item(window.contentItem(), "operatingControlsTab")
info_tab = find_item(window.contentItem(), "operatingInfoTab")
assert tabs is not None and controls_tab is not None and info_tab is not None
QTest.mousePress(window, Qt.LeftButton, pos=center(eject))
tabs.setProperty("currentIndex", 1)
QTest.mouseRelease(window, Qt.LeftButton, pos=center(eject))
assert info_tab.property("checked") and not eject.isVisible()
assert window.property("calls").endswith("eject:press;eject:release;")
QTest.mouseClick(window, Qt.LeftButton, pos=center(controls_tab))
assert controls_tab.property("checked") and eject.isVisible()
window.close()
"""


@pytest.mark.qt_gui
def test_operating_panel_disables_gated_buttons_and_preserves_gesture_lifecycle() -> None:
    assert_qml_scenario(OPERATING_CHILD)


# Embedded JavaScript uses Qt's required identifier spelling.
# noinspection SpellCheckingInspection
SCOPE_NAVIGATION_CHILD = r"""
from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine

app = QCoreApplication([])
engine = QJSEngine()
source = Path(sys.argv[1]).read_text()
function = source.split("    function changeScope(", 1)[1].split("    function navigateFromMenu(", 1)[0]
result = engine.evaluate('''
var window = {
    activeScope: "ACCESSORY", activeAccessoryKey: "configured:loader",
    lastOperatedAccessoryKey: "", lastAccessoryOperationFromRoster: false,
    accessoryOperatingVisible: true, engineCatalogVisible: false
};
var valid = true;
var restored = "";
var keypadCount = 0;
var accessoryCatalogController = {
    reload: function() {},
    descriptor: function(key) { return valid ? {key: key} : {}; }
};
var accessoryCatalog = {
    restoreRosterPosition: function(key) { restored = key; },
    openTmccKeypad: function() { keypadCount++; }
};
var Qt = {callLater: function(callback, argument) { callback(argument); }};
function closeOpenPanels() { window.accessoryOperatingVisible = false; }
function check(condition, message) { if (!condition) throw new Error(message); }
''' + "function changeScope(" + function + '''
changeScope("ACCESSORY", false);
check(!window.accessoryOperatingVisible, "Controls should return to the roster");
check(restored === "configured:loader", "The roster should reveal the selected accessory");
changeScope("ACCESSORY", false);
check(window.accessoryOperatingVisible, "The roster should return to the selected controls");
changeScope("ACCESSORY", true);
check(!window.accessoryOperatingVisible && keypadCount === 1, "The keypad gesture should open the keypad");
changeScope("ACCESSORY", false);
check(window.accessoryOperatingVisible, "The keypad should preserve the selected accessory");
valid = false;
changeScope("ACCESSORY", false);
check(!window.accessoryOperatingVisible && !window.activeAccessoryKey, "Deleted selections should be cleared");
changeScope("ACCESSORY", false);
check(!window.accessoryOperatingVisible, "An empty selection should stay on the roster");
valid = true;
window.activeScope = "ENGINE";
window.lastOperatedAccessoryKey = "configured:loader";
changeScope("ACCESSORY", false);
check(window.accessoryOperatingVisible, "Returning from another scope should recall the last accessory");
window.activeScope = "ENGINE";
window.lastOperatedAccessoryKey = "relay:30";
window.lastAccessoryOperationFromRoster = true;
changeScope("ACCESSORY", false);
check(!window.accessoryOperatingVisible && restored === "relay:30", "Relay recall should restore its roster row");
''')
assert not result.isError(), result.toString()
"""


@pytest.mark.qt_gui
def test_accessory_scope_toggles_controls_roster_and_preserves_keypad_navigation() -> None:
    main_qml = Path(__file__).resolve().parents[2] / "src" / "pytrain_ui" / "qt" / "qml" / "CabWorkspace.qml"
    result = subprocess.run(
        [sys.executable, "-c", SCOPE_NAVIGATION_CHILD, str(main_qml)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# Embedded Qt identifiers retain their API spelling.
# noinspection SpellCheckingInspection
CAB_LABELS_CHILD = r"""
from pathlib import Path
import sys

from PySide6.QtCore import QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine)
component.setData(b'''
import QtQuick
import QtQuick.Controls
import "."
ApplicationWindow {
    id: window
    width: 720; height: 1280
    visible: true
    property string calls: ""
    property bool configured: true
    property bool verticalBoom: false
    QtObject {
        id: backend
        function tmccCommand(key, address, command, value) {
            window.calls += address + ":" + command + ":" + value + ";"
        }
        function releaseConfiguredHolds(key) {}
        function sendAnalogOperation(key, operation, value) { window.calls += operation + "=" + value + ";" }
    }
    AccessoryOperatingView {
        id: panel
        anchors.fill: parent
        controller: backend
        accessory: window.configured
            ? ({kind: "OPERATING", key: "configured:smoke", tmccId: 29, title: "Smoke Loader",
                sharedCommandAddress: true, artworkSource: "crew-relief.png", operations: [
                    {key: "boom", label: "Fluid Boom", enabled: true, control: "command", state: "UNKNOWN",
                     analogInput: {minimum: -5, maximum: 5, neutral: 0, springReturn: true,
                                   orientation: window.verticalBoom ? "vertical" : "horizontal", repeat: 100}}
                ],
                cabKeyLabels: ({"NUMERIC:8": "Lights Off", "NUMERIC:9": "Lights On",
                    "BRAKE": "Dispense", "RELATIVE_SPEED": "Fluid Boom"})})
            : ({kind: "TMCC", key: "acc:60", tmccId: 60, title: "Generic Accessory"})
    }
}
''', QUrl.fromLocalFile(str(Path(sys.argv[1]) / "operating_captions.qml")))
assert component.isReady(), [error.toString() for error in component.errors()]
window = component.create()
assert window is not None
QTest.qWait(80)


def find_visible(item, name):
    if item.objectName() == name and item.isVisible():
        return item
    for child in item.childItems():
        found = find_visible(child, name)
        if found is not None:
            return found
    return None


def click(item):
    assert item is not None
    point = item.mapToScene(item.boundingRect().center()).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, pos=point)
    QTest.qWait(30)


for gesture in ("double_click", "hold"):
    image = find_visible(window.contentItem(), "accessoryArtwork")
    point = image.mapToScene(image.boundingRect().center()).toPoint()
    if gesture == "hold":
        QTest.mousePress(window, Qt.LeftButton, pos=point)
        QTest.qWait(900)
        QTest.mouseRelease(window, Qt.LeftButton, pos=point)
    else:
        click(image)
        click(image)
    QTest.qWait(60)
    assert find_visible(window.contentItem(), "operatingInfoTab").property("checked"), gesture
    click(find_visible(window.contentItem(), "operatingControlsTab"))

slider = find_visible(window.contentItem(), "accessoryAnalogSlider-boom")
assert slider is not None
for vertical in (False, True):
    window.setProperty("verticalBoom", vertical)
    QTest.qWait(60)
    slider = find_visible(window.contentItem(), "accessoryAnalogSlider-boom")
    def slider_point(fraction):
        handle = slider.property("handle")
        if vertical:
            y = slider.height() - slider.property("bottomPadding") - handle.height() / 2
            y -= fraction * (slider.property("availableHeight") - handle.height())
            local = QPointF(slider.width() / 2, y)
        else:
            x = slider.property("leftPadding") + handle.width() / 2
            x += fraction * (slider.property("availableWidth") - handle.width())
            local = QPointF(x, 16)
        return slider.mapToScene(local).toPoint()
    for fraction, expected in [(0.9, 4), (0, -5), (1, 5), (0.5, 0)]:
        window.setProperty("calls", "")
        QTest.mouseClick(window, Qt.LeftButton, pos=slider_point(fraction))
        QTest.qWait(40)
        assert window.property("calls") == "boom=" + str(expected) + ";", (vertical, window.property("calls"))
        assert slider.property("value") == 0
    window.setProperty("calls", "")
    QTest.mousePress(window, Qt.LeftButton, pos=slider_point(0.5))
    QTest.mouseMove(window, slider_point(1))
    QTest.qWait(250)
    QTest.mouseRelease(window, Qt.LeftButton, pos=slider_point(1))
    calls = window.property("calls")
    assert calls.count("boom=5;") >= 2, (vertical, calls)
    QTest.qWait(150)
    assert window.property("calls") == calls and slider.property("value") == 0
window.setProperty("calls", "")
click(find_visible(window.contentItem(), "operatingAccTab"))
assert find_visible(window.contentItem(), "accessoryThrottleTitle").property("text") == "Fluid Boom"
for key, label in [("8", "Lights Off"), ("9", "Lights On"), ("BRAKE", "Dispense"),
                   ("FRONT_COUPLER", "Front Coupler"), ("1", "1"), ("AUX1_OPT_ONE", "Aux 1")]:
    button = find_visible(window.contentItem(), "accessoryCabKey_" + key)
    assert button is not None and button.property("text") == label, (key, label)
    if key in ("8", "9", "BRAKE"):
        click(button)
assert window.property("calls") == "29:NUMERIC:8;29:NUMERIC:9;29:BRAKE:0;"
window.setProperty("configured", False)
QTest.qWait(80)
assert find_visible(window.contentItem(), "accessoryThrottleTitle").property("text") == "Current Speed"
for key, label in [("8", "8"), ("9", "9"), ("BRAKE", "Brake")]:
    button = find_visible(window.contentItem(), "accessoryCabKey_" + key)
    assert button is not None and button.property("text") == label
window.close()
"""


@pytest.mark.qt_gui
def test_operating_acc_tab_labels_match_functions_without_changing_commands_or_generic_labels() -> None:
    assert_qml_scenario(CAB_LABELS_CHILD)


@pytest.mark.parametrize(("variant", "caption"), [("loader", "Load"), ("unloader", "Unload")])
def test_culvert_acc_key_caption_uses_variant_operation_label(controller, sent, monkeypatch, variant, caption):
    install_configured_accessories(
        controller,
        monkeypatch,
        {"gui": "culvert", "instance_id": "culvert", "tmcc_id": 60, "variant": variant},
    )
    key = "configured:culvert"
    assert controller.operatingView(key)["cabKeyLabels"] == {"AUX2_OPT_ONE": caption}
    controller.tmccCommand(key, 60, "AUX2_OPT_ONE", 0)
    assert [(req.address, req.command, req.data) for req in sent] == [(60, TMCC1AuxCommandEnum.AUX2_OPT_ONE, 0)]


@pytest.mark.parametrize("configured", [False, True])
def test_mode_one_uncoupler_uses_one_address_and_eight_timed_control3_outputs(
    controller, sent, monkeypatch, configured
):
    occupant = LcsOccupant(24, ASC2, ASC2.mode_for_pdi_mode(1), 1, port_index=1, scope=CommandScope.ACC)
    monkeypatch.setitem(vars(module), "occupants", lambda **_: [occupant])
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_: [occupant] if address == 24 else [])
    if configured:
        install_configured_accessories(
            controller, monkeypatch, {"gui": "uncoupler", "instance_id": "tracks", "tmcc_ids": {"uncouple": 24}}
        )
    else:
        controller.reload()
    row = next(row for row in controller.rows if row["configured"] == configured)
    key = row["key"]
    assert row["uncoupler"] and row["tmccIds"] == [24] and row["quickActions"] == []
    assert row["stateSummary"] == ""
    panel = controller.operatingView(key)
    assert panel["uncoupler"] and panel["uncouplerAddress"] == 24
    operated = []
    controller.operated.connect(lambda selected, roster: operated.append((selected, roster)))
    for sub_id in range(1, 9):
        assert controller.pulseUncoupler(key, sub_id)
    assert [(req.tmcc_id, req.action, req.sub_id, req.time) for req in sent] == [
        (24, Asc2Action.CONTROL3, sub_id, 1.0) for sub_id in range(1, 9)
    ]
    assert [req.as_bytes[4:6] for req in sent] == [bytes([sub_id, 100]) for sub_id in range(1, 9)]
    assert operated == [(key, False)] * 8
    controller.tmccCommand(key, 24, "NUMERIC", 8)
    controller.tmccCommand(key, 24, "RELATIVE_SPEED", -3)
    assert [(req.address, req.command, req.data) for req in sent[8:]] == [
        (24, TMCC1AuxCommandEnum.NUMERIC, 8),
        (24, TMCC1AuxCommandEnum.RELATIVE_SPEED, -3),
    ]
    del sent[8:]
    for invalid in (0, 9, -1, True, 1.5):
        assert not controller.pulseUncoupler(key, invalid)
    assert not controller.pulseUncoupler("missing", 1)
    assert len(sent) == 8
    # Recheck the live mode at activation, rather than trusting an old displayed row.
    changed = LcsOccupant(24, ASC2, ASC2.mode_for_pdi_mode(0), 8, port_index=1, scope=CommandScope.ACC)
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_: [changed] if address == 24 else [])
    assert not controller.pulseUncoupler(key, 1)
    assert len(sent) == 8


def test_mode_zero_uncoupler_keeps_its_existing_held_control(controller, sent, monkeypatch):
    occupant = LcsOccupant(24, ASC2, ASC2.mode_for_pdi_mode(0), 8, port_index=1, scope=CommandScope.ACC)
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_: [occupant] if address == 24 else [])
    install_configured_accessories(
        controller, monkeypatch, {"gui": "uncoupler", "instance_id": "track", "tmcc_ids": {"uncouple": 24}}
    )
    key = "configured:track"
    assert not controller.operatingView(key)["uncoupler"]
    assert controller.activateConfiguredOperation(key, "uncouple", "press")
    assert controller.activateConfiguredOperation(key, "uncouple", "release")
    assert [(req.action, req.values) for req in sent] == [(Asc2Action.CONTROL1, 1), (Asc2Action.CONTROL1, 0)]


# Embedded Qt identifiers retain their API spelling.
# noinspection SpellCheckingInspection
UNCOUPLER_CHILD = r"""
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
touch_device = QTest.createTouchDevice()
engine = QQmlEngine()
component = QQmlComponent(engine)
component.setData(b'''
import QtQuick
import QtQuick.Controls
import "."
ApplicationWindow {
    id: window
    width: 720; height: 1280; visible: true
    property string selectedKey: ""
    property string calls: ""
    property bool info: false
    property int activeMask: 0
    property var relayStates: [0, 0, 0, 0, 0, 0, 0, 0]
    QtObject {
        id: backend
        readonly property var rows: [
            {key: "op", kind: "OPERATING", primaryTmccId: 24, tmccIds: [24], roadName: "Tracks",
             roadNumber: "", userDefined: true, quickActions: [], uncoupler: true,
             imageSource: "", lcsAssociations: "ASC2 24", stateSummary: "", availableViews: []},
            {key: "board", kind: "ASC2", primaryTmccId: 40, tmccIds: [40], roadName: "ASC2 Tracks",
             roadNumber: "0040", userDefined: false, quickActions: [], uncoupler: true,
             imageSource: "", lcsAssociations: "ASC2 40", stateSummary: "", availableViews: []}
        ]
        property var model: ({})
        function pulseUncoupler(key, digit) {
            window.calls += key + ":" + digit + ";"
            window.activeMask |= 1 << (digit - 1)
            return true
        }
        function tmccCommand(key, address, name, value) {
            window.calls += key + ":" + address + ":" + name + ":" + value + ";"
        }
        function requestUncouplerRelays(key) { return true }
        function setUncouplerRelays(key, values, valids) {
            window.calls += "relays:" + key + ":" + values + ":" + valids + ";"
            window.relayStates = window.relayStates.map((value, index) =>
                valids & (1 << index) ? Number(!!(values & (1 << index))) : value)
            return true
        }
        function releaseConfiguredHolds(key) {}
        function refresh(editorOpen) {}
        function canClearRecord() { return false }
    }
    AccessoryCatalog {
        id: roster
        anchors.fill: parent
        visible: window.selectedKey === ""
        controller: backend
        onAccessoryRequested: key => window.selectedKey = key
    }
    AccessoryOperatingView {
        anchors.fill: parent
        visible: window.selectedKey !== ""
        controller: backend
        infoController: backend
        infoSelected: window.info
        onDeviceTabRequested: index => {
            window.info = index === 3
            if (!window.info) deviceControlTabIndex = index
        }
        accessory: ({key: window.selectedKey, kind: window.selectedKey === "op" ? "OPERATING" : "ASC2",
                     title: "Uncoupling Tracks", tmccId: window.selectedKey === "op" ? 24 : 40,
                     uncoupler: true, operations: [], relayStates: window.relayStates,
                     uncouplerActiveMask: window.activeMask})
    }
    function enterId(address) { roster.selectTmccId(address, false) }
}
''', QUrl.fromLocalFile(str(Path(sys.argv[1]) / "uncoupler_validation.qml")))
assert component.isReady(), [error.toString() for error in component.errors()]
window = component.create()
assert window is not None
QTest.qWait(80)


def items(item):
    yield item
    for child in item.childItems():
        yield from items(child)


def visible(name):
    return next(item for item in items(window.contentItem()) if item.isVisible() and item.objectName() == name)


def point(item):
    return item.mapToScene(item.boundingRect().center()).toPoint()


for width, height in ((720, 1280), (639, 800)):
    window.resize(width, height)
    for address, key in ((24, "op"), (40, "board")):
        window.setProperty("selectedKey", "")
        window.setProperty("info", False)
        QTest.qWait(40)
        window.enterId(address)
        QTest.qWait(80)
        assert window.property("selectedKey") == key
        track_tab = visible("operatingControlsTab" if key == "op" else "accessoryDeviceControlTab0")
        assert track_tab.property("text") == "Uncouplers"
        note = visible("uncouplerInstructions")
        assert note.isVisible()
        window.setProperty("relayStates", [0] * 8)
        window.setProperty("activeMask", 0)
        for digit in range(1, 9):
            button = visible("uncouplerKey" + str(digit))
            assert button.property("text") == str(digit)
            top = button.mapToScene(button.boundingRect().topLeft())
            bottom = button.mapToScene(button.boundingRect().bottomRight())
            assert top.x() >= 0 and top.y() >= 0 and bottom.x() <= width and bottom.y() <= height
            window.setProperty("calls", "")
            QTest.mousePress(window, Qt.LeftButton, pos=point(button))
            QTest.qWait(150)
            assert window.property("calls") == "", "A pulse should fire once on release"
            QTest.mouseRelease(window, Qt.LeftButton, pos=point(button))
            QTest.qWait(30)
            assert window.property("calls") == key + ":" + str(digit) + ";"
            assert button.property("selected"), "The tapped track must stay highlighted after release"
            window.setProperty("activeMask", 0)
            QTest.qWait(10)
            assert not button.property("selected"), "Off feedback must clear the track highlight"
        window.setProperty("calls", "")
        button = visible("uncouplerKey8")
        QTest.touchEvent(window, touch_device).press(0, point(button), window).commit()
        QTest.qWait(200)
        assert window.property("calls") == ""
        QTest.touchEvent(window, touch_device).release(0, point(button), window).commit()
        QTest.qWait(40)
        assert window.property("calls") == key + ":8;"
        window.setProperty("calls", "")
        button = visible("uncouplerKey1")
        button.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Return)
        assert window.property("calls") == key + ":1;"
        relay_tab = visible("operatingRelaysTab" if key == "op" else "accessoryDeviceControlTab1")
        assert relay_tab.property("text") == "Relays"
        QTest.mouseClick(window, Qt.LeftButton, pos=point(relay_tab))
        QTest.qWait(40)
        for digit in range(1, 9):
            button = visible("asc2Relay" + str(digit))
            bottom = button.mapToScene(button.boundingRect().bottomRight())
            assert bottom.x() <= width and bottom.y() <= height
        warning = visible("uncouplerRelayWarning")
        warning_bottom = warning.mapToScene(warning.boundingRect().bottomRight())
        assert warning_bottom.y() <= height
        assert visible("editRelayGroup").height() > 48
        for action in ("allRelaysOn", "allRelaysOff", "refreshRelays"):
            assert visible(action).height() > 48
        window.setProperty("calls", "")
        QTest.mouseClick(window, Qt.LeftButton, pos=point(visible("asc2Relay1")))
        QTest.qWait(30)
        assert window.property("calls") == "relays:" + key + ":1:1;"
        QTest.mouseClick(window, Qt.LeftButton, pos=point(visible("editRelayGroup")))
        QTest.qWait(40)
        window.setProperty("calls", "")
        for digit in (2, 4):
            QTest.mouseClick(window, Qt.LeftButton, pos=point(visible("asc2Relay" + str(digit))))
        QTest.qWait(40)
        assert window.property("calls") == "", "Group changes must wait for Apply"
        QTest.mouseClick(window, Qt.LeftButton, pos=point(visible("applyRelayGroup")))
        QTest.qWait(30)
        assert window.property("calls") == "relays:" + key + ":10:10;"
        QTest.mouseClick(window, Qt.LeftButton, pos=point(visible("editRelayGroup")))
        QTest.qWait(40)
        window.setProperty("calls", "")
        QTest.mouseClick(window, Qt.LeftButton, pos=point(visible("asc2Relay3")))
        QTest.mouseClick(window, Qt.LeftButton, pos=point(visible("cancelRelayGroup")))
        assert window.property("calls") == "", "Cancel must discard group changes"
        acc_tab = visible("operatingAccTab" if key == "op" else "accessoryDeviceControlTab2")
        assert acc_tab.property("text") == "ACC"
        QTest.mouseClick(window, Qt.LeftButton, pos=point(acc_tab))
        QTest.qWait(60)
        assert visible("tmccAccessoryThrottle").isVisible()
        slider = visible("tmccAccessoryThrottleSlider")
        assert slider.property("scaleStep") == (5 if slider.height() < 170 else 1)
        assert not any(item.isVisible() and item.objectName().startswith("uncouplerKey")
                       for item in items(window.contentItem()))
        window.setProperty("calls", "")
        numeric = visible("accessoryCabKey_8")
        QTest.mouseClick(window, Qt.LeftButton, pos=point(numeric))
        QTest.qWait(30)
        assert window.property("calls") == key + ":" + str(address) + ":NUMERIC:8;"
        throttle = visible("tmccAccessoryThrottle")
        plus = next(item for item in items(throttle) if item.isVisible() and item.property("text") == "+")
        window.setProperty("calls", "")
        QTest.mouseClick(window, Qt.LeftButton, pos=point(plus))
        QTest.qWait(30)
        assert window.property("calls") == (
            key + ":" + str(address) + ":RELATIVE_SPEED:1;" + key + ":" + str(address) + ":RELATIVE_SPEED:0;")
        tab = visible("operatingInfoTab" if key == "op" else "accessoryDeviceInfoTab")
        QTest.mouseClick(window, Qt.LeftButton, pos=point(tab))
        QTest.qWait(60)
        assert not any(item.isVisible() and item.objectName().startswith("uncouplerKey")
                       for item in items(window.contentItem()))
window.close()
"""


@pytest.mark.qt_gui
def test_uncoupler_controls_open_directly_and_display_eight_single_pulse_keys() -> None:
    assert_qml_scenario(UNCOUPLER_CHILD)


def test_uncoupler_mode_can_be_resolved_from_component_state_without_a_cached_mapping(controller, sent, monkeypatch):
    states = ComponentStateDict(CommandScope.ACC)
    state = states[24]
    state.update(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONFIG, mode=1))
    monkeypatch.setattr(module.ComponentStateStore, "get_state", lambda _scope, address, **_: states.get(address))
    key = add_descriptor(controller, monkeypatch, "ASC2")
    assert controller.operatingView(key)["uncoupler"]
    assert controller.pulseUncoupler(key, 7)
    assert sent[0].as_bytes[4:6] == bytes([7, 100])
    state.update(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONFIG, mode=0))
    assert not controller.pulseUncoupler(key, 7)
    assert not controller.operatingView(key)["uncoupler"]


@pytest.mark.parametrize("configured", [False, True])
def test_uncoupler_control2_uses_independent_masks_and_only_device_feedback_confirms(
    controller, sent, monkeypatch, configured
):
    occupant = LcsOccupant(24, ASC2, ASC2.mode_for_pdi_mode(1), 1, scope=CommandScope.ACC)
    monkeypatch.setitem(vars(module), "occupants", lambda **_: [occupant])
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_: [occupant] if address == 24 else [])
    if configured:
        install_configured_accessories(
            controller, monkeypatch, {"gui": "uncoupler", "instance_id": "relay-test", "tmcc_ids": {"uncouple": 24}}
        )
    else:
        controller.reload()
    key = next(row["key"] for row in controller.rows if row["configured"] == configured)
    monkeypatch.setitem(vars(module), "monotonic", lambda: 10.0)
    assert controller.operatingView(key)["relayStates"] == [-1] * 8
    assert controller.pulseUncoupler(key, 2)
    assert controller.pulseUncoupler(key, 8)
    assert controller.operatingView(key)["uncouplerActiveMask"] == 130
    # SET echoes and unrelated Off reports must not clear a pulse highlight.
    # ASC2_SET is an IntEnum member; PyCharm resolves its same-named module integer here.
    # noinspection PyProtectedMember,PyTypeChecker
    controller._pdi_command(Asc2Req(24, PdiCommand.ASC2_SET, Asc2Action.CONTROL2, values=0, valids=255))
    # noinspection PyProtectedMember
    controller._pdi_command(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONTROL3, values=0, valids=1))
    assert controller.operatingView(key)["uncouplerActiveMask"] == 130
    # An On response retains the highlight; a valid Off clears only its relay.
    # noinspection PyProtectedMember
    controller._pdi_command(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONTROL3, values=2, valids=2))
    assert controller.operatingView(key)["uncouplerActiveMask"] == 130
    # noinspection PyProtectedMember
    controller._pdi_command(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONTROL3, values=0, valids=2))
    assert controller.operatingView(key)["uncouplerActiveMask"] == 128
    # noinspection PyProtectedMember
    controller._pdi_command(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONTROL2, values=0, valids=128))
    assert controller.operatingView(key)["uncouplerActiveMask"] == 0
    # Broadcasts initiated by another controller must also highlight the affected tracks.
    # noinspection PyProtectedMember
    controller._pdi_command(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONTROL3, values=64, valids=64))
    assert controller.operatingView(key)["uncouplerActiveMask"] == 64
    # noinspection PyProtectedMember
    controller._pdi_command(Asc2Req(24, PdiCommand.ASC2_RX, Asc2Action.CONTROL3, values=0, valids=64))
    assert controller.operatingView(key)["uncouplerActiveMask"] == 0
    assert controller.requestUncouplerRelays(key)
    assert (sent[-1].pdi_command, sent[-1].action) == (PdiCommand.ASC2_GET, Asc2Action.CONTROL2)
    assert controller.setUncouplerRelays(key, 1, 9)
    assert sent[-1].as_bytes[1:6] == bytes([0x3D, 24, 0x11, 1, 9])
    assert controller.operatingView(key)["relayStates"] == [0, 0, -1, -1, -1, -1, 0, 0]
    assert controller.operatingView(key)["relayPendingMask"] == 9
    assert not controller.setUncouplerRelays(key, 0, 255)

    def receive(command, action, values, valids):
        # Exercise the real broadcast entry point rather than mutating the feedback cache.
        # noinspection PyProtectedMember
        controller._pdi_command(Asc2Req(24, command, action, values=values, valids=valids))

    receive(PdiCommand.ASC2_SET, Asc2Action.CONTROL2, 1, 9)
    assert controller.operatingView(key)["relayPendingMask"] == 9
    receive(PdiCommand.ASC2_RX, Asc2Action.CONTROL2, 0, 1)
    assert controller.operatingView(key)["relayPendingMask"] == 9
    assert controller.operatingView(key)["relayStates"][0] == 0
    receive(PdiCommand.ASC2_RX, Asc2Action.CONTROL2, 1, 1)
    assert controller.operatingView(key)["relayStates"] == [1, 0, -1, -1, -1, -1, 0, 0]
    assert controller.operatingView(key)["relayPendingMask"] == 8
    receive(PdiCommand.ASC2_RX, Asc2Action.CONTROL3, 0, 8)
    assert controller.operatingView(key)["relayStates"] == [1, 0, -1, 0, -1, -1, 0, 0]
    assert controller.operatingView(key)["relayPendingMask"] == 0
    assert controller.setUncouplerRelays(key, 0, 255)
    assert sent[-1].as_bytes[4:6] == bytes([0, 255])
    receive(PdiCommand.ASC2_RX, Asc2Action.CONTROL2, 0, 255)
    assert controller.operatingView(key)["relayStates"] == [0] * 8
    assert controller.setUncouplerRelays(key, 255, 255)
    monkeypatch.setitem(vars(module), "monotonic", lambda: 13.0)
    # Exercise the timer callback deterministically without waiting for wall-clock time.
    # noinspection PyProtectedMember
    controller._expire_relay_requests()
    assert controller.operatingView(key)["relayPendingMask"] == 0
    assert controller.operatingView(key)["relayStates"] == [-1] * 8
    assert "not confirmed" in controller.operatingView(key)["relayStatus"]
    for invalid_values, invalid_valids in ((-1, 1), (256, 1), (0, 0), (0, 256), (True, 1), (0, False), (0, 1.5)):
        assert not controller.setUncouplerRelays(key, invalid_values, invalid_valids)
    assert not controller.setUncouplerRelays("missing", 0, 255)
    changed = LcsOccupant(24, ASC2, ASC2.mode_for_pdi_mode(0), 8, scope=CommandScope.ACC)
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_: [changed] if address == 24 else [])
    assert not controller.requestUncouplerRelays(key)
    assert not controller.setUncouplerRelays(key, 0, 255)
