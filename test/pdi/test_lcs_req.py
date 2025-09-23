#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from typing import cast

# Python
import pytest

from src.pytrain.pdi.constants import (
    ALL_FIRMWARE,
    ALL_IDENTIFY,
    ALL_INFO,
    ALL_STATUS,
    PDI_EOP,
    PDI_SOP,
    ALL_SETs,
    PdiAction,
    PdiCommand,
    Ser2Action,
)
from src.pytrain.pdi.lcs_req import ERROR_CODE_MAP, LcsReq, Ser2Req
from src.pytrain.pdi.pdi_req import PdiReq


# noinspection PyProtectedMember
def build_lcs_packet(
    pdi_cmd: PdiCommand, action: PdiAction, tmcc_id: int, payload: bytes = b"", is_error=False
) -> bytes:
    # [SOP][PDI command(2)][tmcc id(1)][action(1)][payload...][EOP]
    # action with MSB set indicates error
    if is_error:
        act = action.value.bits | 0x80
    else:
        act = action.value.bits
    inner = b"".join(
        [
            pdi_cmd.as_bytes,
            tmcc_id.to_bytes(1, "big"),
            act.to_bytes(1, "big"),
            payload,
        ]
    )
    stuffed, checksum = PdiReq._calculate_checksum(inner, add_stf=True)  # noqa: SLF001
    return b"".join([PDI_SOP.to_bytes(1, "big"), stuffed, checksum, PDI_EOP.to_bytes(1, "big")])


def test_is_lcs_true_and_repr_safe_without_payload():
    req = Ser2Req(7, PdiCommand.SER2_GET, Ser2Action.CONFIG)
    assert req.is_lcs is True
    s = repr(req)
    assert "PDI" in s and "ID: 7" in s


def test_parse_status_from_bytes_populates_fields_and_payload_text():
    # payload fields per LcsReq for ALL_STATUS
    # [board_id, num_ids, model, uart0, uart1, base_type, dc_volts*10, ec0..ec15]
    board_id = 2
    num_ids = 5
    model = 9
    uart0 = 2
    uart1 = 3
    base_type = 1  # "Legacy"
    dc_volts_tenths = 178  # -> 17.8V
    errs = bytes(range(0x10, 0x10 + 16))  # ec0..ec15 diverse data
    payload = bytes([board_id, num_ids, model, uart0, uart1, base_type, dc_volts_tenths]) + errs

    pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.STATUS, 25, payload)
    parsed = PdiReq.from_bytes(pkt)
    assert isinstance(parsed, Ser2Req)

    # action mapping
    assert parsed.action == Ser2Action.STATUS

    # fields
    assert parsed.board_id == board_id
    assert parsed.num_ids == num_ids
    assert parsed.model == model
    assert parsed.uart0 == uart0
    assert parsed.uart1 == uart1
    assert parsed.base_type == "Legacy"
    assert pytest.approx(parsed.dc_volts, rel=0, abs=1e-6) == dc_volts_tenths / 10.0

    # payload (human text) should include key tokens and packet echo
    s = parsed.payload
    assert "Board ID:" in s and "Num IDs:" in s and "Model:" in s and "DC Volts:" in s
    assert "UART0:" in s and "UART1:" in s and "Base:" in s
    # ensure UART mode mapping text appears
    assert ">Base<" in s or "->Base" in s or "Base->" in s


def test_parse_firmware_payload_text():
    version, revision, sub_rev = 1, 2, 3
    payload = bytes([version, revision, sub_rev])
    pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.FIRMWARE, 3, payload)
    parsed = PdiReq.from_bytes(pkt)

    assert isinstance(parsed, Ser2Req)
    assert parsed.action == Ser2Action.FIRMWARE
    assert parsed.payload == f"Firmware {version}.{revision}.{sub_rev}"


def test_parse_info_payload_text():
    board_id = 7
    num_ids = 42
    model = 11
    dc_volts_tenths = 129
    payload = bytes([board_id, num_ids, model, dc_volts_tenths])
    pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.INFO, 77, payload)
    parsed = PdiReq.from_bytes(pkt)

    assert isinstance(parsed, Ser2Req)
    assert parsed.action == Ser2Action.INFO
    s = parsed.payload
    assert "Board ID:" in s and "Num IDs:" in s and "Model:" in s
    assert "DC Volts:" in s
    assert str(dc_volts_tenths / 10.0) in s


def test_error_flag_sets_is_error_and_maps_error_code_text():
    # Action with MSB set indicates error; error code is first payload byte
    error_code = 2  # "Action not supported"
    pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.CONFIG, 9, bytes([error_code]), is_error=True)
    parsed = PdiReq.from_bytes(pkt)

    assert isinstance(parsed, Ser2Req)
    assert parsed.is_error is True
    assert "Action not supported" in parsed.error
    # payload falls back to base PdiReq payload when error
    assert isinstance(parsed.payload, str)


def test_error_code_unknown_maps_to_none_text():
    error_code = 0x00  # supported; use an unmapped like 0 to force "None"
    pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.CONFIG, 9, bytes([error_code]), is_error=True)
    parsed = cast(LcsReq, PdiReq.from_bytes(pkt))
    assert parsed.error == "None"


def test_error_code_error_texts():
    for error_code, error_text in ERROR_CODE_MAP.items():
        pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.CONFIG, 9, bytes([error_code]), is_error=True)
        parsed = cast(LcsReq, PdiReq.from_bytes(pkt))
        assert parsed.error == error_text


def test_uart_mode_mapping_and_base_type_defaults_to_na():
    # Use a non-mapped base_type and uart values
    payload = bytes([0, 0, 0, 99, 100, 99, 0])
    pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.STATUS, 1, payload)
    parsed = cast(LcsReq, PdiReq.from_bytes(pkt))
    assert parsed.base_type == "NA"
    assert LcsReq.uart_mode(99) == "NA"
    assert LcsReq.uart_mode(1) == ">Base<"


def test_identify_set_payload_includes_ident_when_command_is_set():
    # Only ALL_IDENTIFY with a command in ALL_SETs returns "Ident: {ident} ..."
    # Build a request object (not from bytes) so action gate evaluates AND command name endswith _SET
    ident = 0x5A
    req = Ser2Req(12, PdiCommand.SER2_SET, Ser2Action.IDENTIFY, ident=ident)
    assert Ser2Action.IDENTIFY in ALL_IDENTIFY
    assert req.pdi_command in ALL_SETs
    assert "Ident: 90" in req.payload  # 0x5A == 90


def test_payload_falls_back_when_not_matching_any_clause():
    # Build a GET CONFIG where payload should fall back unless special formatting defined
    req = Ser2Req(2, PdiCommand.SER2_GET, Ser2Action.CONFIG)
    s = req.payload
    # base PdiReq payload is a string or None; ensure not crashing and is str
    assert s is None or isinstance(s, str)


def test_ser2req_from_bytes_sets_action_enum():
    pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.CONFIG, 5)
    parsed = PdiReq.from_bytes(pkt)
    assert isinstance(parsed, Ser2Req)
    assert parsed.action == Ser2Action.CONFIG


def test_is_action_helper_against_lists():
    # Ensure _is_action recognizes membership for different lists
    # Build minimal object via bytes to exercise internal path
    pkt = build_lcs_packet(PdiCommand.SER2_RX, Ser2Action.STATUS, 9, b"\x00\x00\x00\x00\x00\x00\x00")
    parsed = PdiReq.from_bytes(pkt)
    assert isinstance(parsed, Ser2Req)
    assert parsed.action in ALL_STATUS
    assert parsed.action not in ALL_FIRMWARE
    assert parsed.action not in ALL_INFO
    assert parsed.action not in ALL_IDENTIFY
