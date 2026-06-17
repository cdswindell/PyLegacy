#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

from src.pytrain.db.accessory_state import AccessoryState
from src.pytrain.db.component_state import SwitchState
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_state import TrainState
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
from src.pytrain.protocol.constants import CommandScope


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
    assert packets[:3] == [config.as_bytes, firmware.as_bytes, info.as_bytes]
