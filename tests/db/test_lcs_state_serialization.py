#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import pytest

from src.pytrain.db.accessory_state import AccessoryState
from src.pytrain.db.component_state import ComponentState, LcsProxyState, LcsState, SwitchState
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_state import EngineState, TrainState
from src.pytrain.pdi.asc2_req import Asc2Req
from src.pytrain.pdi.bpc2_req import Bpc2Req
from src.pytrain.pdi.constants import (
    PDI_EOP,
    PDI_SOP,
    Asc2Action,
    Bpc2Action,
    PdiCommand,
    Stm2Action,
)
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.pdi.stm2_req import Stm2Req
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum as Switch


def _received_lcs_packet(pdi_command: PdiCommand, address: int, action, payload: bytes = bytes()) -> bytes:
    body = pdi_command.as_bytes
    body += address.to_bytes(1, byteorder="big")
    body += action.as_bytes
    body += payload
    body, checksum = PdiReq._calculate_checksum(body)
    return PDI_SOP.to_bytes(1, byteorder="big") + body + checksum + PDI_EOP.to_bytes(1, byteorder="big")


def _new_accessory(address: int) -> AccessoryState:
    state = AccessoryState(CommandScope.ACC)
    state.initialize(CommandScope.ACC, address)
    state._address = address  # type: ignore[attr-defined]
    return state


def _new_switch(address: int) -> SwitchState:
    state = SwitchState(CommandScope.SWITCH)
    state.initialize(CommandScope.SWITCH, address)
    state._address = address  # type: ignore[attr-defined]
    return state


def _new_train(address: int) -> TrainState:
    state = TrainState(CommandScope.TRAIN)
    state.initialize(CommandScope.TRAIN, address)
    state._address = address  # type: ignore[attr-defined]
    return state


def test_accessory_state_as_bytes_includes_received_lcs_config_firmware_and_info_packets() -> None:
    address = 41
    state = _new_accessory(address)
    config = Asc2Req(
        _received_lcs_packet(
            PdiCommand.ASC2_RX,
            address,
            Asc2Action.CONFIG,
            bytes([address, 0x07, 0x00, 0x00, 0x01, 0x19]),
        )
    )
    firmware = Asc2Req(
        _received_lcs_packet(PdiCommand.ASC2_RX, address, Asc2Action.FIRMWARE, bytes([0x01, 0x02, 0x03]))
    )
    info = Asc2Req(_received_lcs_packet(PdiCommand.ASC2_RX, address, Asc2Action.INFO, bytes([0x04, 0x08, 0x04, 0x78])))

    state.update(config)
    state.update(firmware)
    state.update(info)

    payload = state.as_bytes()

    assert state.is_lcs_component is True
    assert isinstance(payload, bytes)
    assert config.as_bytes in payload
    assert firmware.as_bytes in payload
    assert info.as_bytes in payload
    assert payload.index(config.as_bytes) < payload.index(firmware.as_bytes) < payload.index(info.as_bytes)


def test_switch_state_as_bytes_includes_received_lcs_config_firmware_and_info_packets() -> None:
    address = 42
    state = _new_switch(address)
    config = Stm2Req(
        _received_lcs_packet(
            PdiCommand.STM2_RX,
            address,
            Stm2Action.CONFIG,
            bytes([address, 0x05, 0x00, 0x00, 0x01]),
        )
    )
    firmware = Stm2Req(
        _received_lcs_packet(PdiCommand.STM2_RX, address, Stm2Action.FIRMWARE, bytes([0x02, 0x03, 0x04]))
    )
    info = Stm2Req(_received_lcs_packet(PdiCommand.STM2_RX, address, Stm2Action.INFO, bytes([0x05, 0x08, 0x08, 0x74])))

    state.update(config)
    state.update(firmware)
    state.update(info)

    payload = state.as_bytes()

    assert state.is_lcs_component is True
    assert isinstance(payload, bytes)
    position = state.state
    assert position is not None
    assert payload == (
        ComponentState.as_bytes(state)
        + config.as_bytes
        + firmware.as_bytes
        + info.as_bytes
        + CommandReq.build(position, address).as_bytes
    )
    assert config.as_bytes in payload
    assert firmware.as_bytes in payload
    assert info.as_bytes in payload
    assert payload.index(config.as_bytes) < payload.index(firmware.as_bytes) < payload.index(info.as_bytes)


def test_train_state_as_bytes_includes_received_lcs_config_firmware_and_info_packets(monkeypatch) -> None:
    address = 43
    state = _new_train(address)
    config = Bpc2Req(
        _received_lcs_packet(
            PdiCommand.BPC2_RX,
            address,
            Bpc2Action.CONFIG,
            bytes([address, 0x06, 0x00, 0x00, 0x01]),
        )
    )
    state.update(config)
    monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(lambda *_args: state))

    firmware = Bpc2Req(
        _received_lcs_packet(PdiCommand.BPC2_RX, address, Bpc2Action.FIRMWARE, bytes([0x03, 0x04, 0x05]))
    )
    info = Bpc2Req(_received_lcs_packet(PdiCommand.BPC2_RX, address, Bpc2Action.INFO, bytes([0x06, 0x08, 0x05, 0x76])))

    state.update(firmware)
    state.update(info)

    packets = state.as_bytes()

    assert state.is_lcs is True
    assert isinstance(packets, list)
    assert all(isinstance(packet, bytes) for packet in packets)
    assert packets[0].endswith(config.as_bytes + firmware.as_bytes + info.as_bytes)


@pytest.mark.parametrize("inherited", [b"firstsecond", [b"first", b"second"], b"", []])
@pytest.mark.parametrize("include_lcs", [False, True])
def test_lcs_as_bytes_normalizes_inherited_packets(monkeypatch, inherited, include_lcs) -> None:
    state = _new_switch(42)
    monkeypatch.setattr(ComponentState, "as_bytes", lambda self: inherited)
    suffix = b""
    if include_lcs:
        state._config_req = Stm2Req(42, PdiCommand.STM2_GET, Stm2Action.CONFIG)
        state._firmware_req = Stm2Req(42, PdiCommand.STM2_GET, Stm2Action.FIRMWARE)
        state._info_req = Stm2Req(42, PdiCommand.STM2_GET, Stm2Action.INFO)
        suffix = state._config_req.as_bytes + state._firmware_req.as_bytes + state._info_req.as_bytes

    payload = LcsState.as_bytes(state)

    assert isinstance(payload, bytes)
    assert payload == (b"firstsecond" if inherited else b"") + suffix


@pytest.mark.parametrize("inherited", [b"firstsecond", [b"first", b"second"], b"", []])
@pytest.mark.parametrize("position", [None, Switch.THRU, Switch.OUT])
def test_switch_as_bytes_normalizes_inherited_packets(monkeypatch, inherited, position) -> None:
    state = _new_switch(42)
    state._state = position
    monkeypatch.setattr(LcsProxyState, "as_bytes", lambda self: inherited)

    payload = state.as_bytes()

    assert isinstance(payload, bytes)
    suffix = CommandReq.build(position, 42).as_bytes if position is not None else b""
    assert payload == (b"firstsecond" if inherited else b"") + suffix


@pytest.mark.parametrize("state_class, scope", [(EngineState, CommandScope.ENGINE), (TrainState, CommandScope.TRAIN)])
def test_engine_and_train_serialization_retains_packet_lists(state_class, scope) -> None:
    state = state_class(scope)
    state.initialize(scope, 43)
    state._address = 43

    packets = state.as_bytes()

    assert isinstance(packets, list)
    assert packets
    assert all(isinstance(packet, bytes) for packet in packets)
