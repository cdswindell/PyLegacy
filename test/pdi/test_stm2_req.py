#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, PdiCommand, Stm2Action
from src.pytrain.pdi.stm2_req import Stm2Req
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum


def test_config_set_as_bytes_contains_fields():
    """
    CONFIG with SET should serialize tmcc_id, debug, two zero bytes, and mode.
    """
    req = Stm2Req(
        25,
        PdiCommand.STM2_SET,
        Stm2Action.CONFIG,
        mode=0,
        debug=7,
    )

    # Human payload shape
    s = req.payload
    assert isinstance(s, str)
    # Be lenient about exact formatting; check key tokens
    assert "Mode:" in s and "Debug:" in s

    bs = req.as_bytes
    assert isinstance(bs, (bytes, bytearray))
    assert bs[0] == PDI_SOP
    assert bs[-1] == PDI_EOP

    # Core markers
    assert PdiCommand.STM2_SET.as_bytes in bs
    assert Stm2Action.CONFIG.as_bytes in bs

    # The CONFIG payload for SET should include:
    #   tmcc_id, debug, 0x00, 0x00, mode
    expected_tail = bytes([req.tmcc_id, 7, 0x00, 0x00, 0x00])
    assert expected_tail in bs


def test_control1_set_payload_and_state_byte_out():
    """
    CONTROL1 with SET should encode the switch state byte and payload should include 'OUT'.
    """
    req = Stm2Req(10, PdiCommand.STM2_SET, Stm2Action.CONTROL1, state=TMCC1SwitchCommandEnum.OUT)

    s = req.payload
    assert isinstance(s, str)
    assert "OUT" in s  # enum string should contain OUT

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.STM2_SET.as_bytes in bs
    assert Stm2Action.CONTROL1.as_bytes in bs
    # State byte must appear in the packet; OUT -> 1
    assert (1).to_bytes(1, "big") in bs


def test_control1_set_payload_and_state_byte_thru():
    """
    CONTROL1 with SET should encode the switch state byte and payload should include 'THRU'.
    """
    req = Stm2Req(11, PdiCommand.STM2_SET, Stm2Action.CONTROL1, state=TMCC1SwitchCommandEnum.THRU)

    s = req.payload
    assert isinstance(s, str)
    assert "THRU" in s

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.STM2_SET.as_bytes in bs
    assert Stm2Action.CONTROL1.as_bytes in bs
    # THRU -> 0
    assert (0).to_bytes(1, "big") in bs


def test_identify_set_includes_ident_byte():
    """
    IDENTIFY with SET should serialize the ident byte.
    """
    req = Stm2Req(9, PdiCommand.STM2_SET, Stm2Action.IDENTIFY, ident=0x55)
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.STM2_SET.as_bytes in bs
    assert Stm2Action.IDENTIFY.as_bytes in bs
    assert (0x55).to_bytes(1, "big") in bs


def test_get_requests_have_minimal_payload_for_config():
    """
    GET requests should not include the additional CONFIG body bytes.
    """
    # CONFIG + GET should not append the CONFIG body (tmcc_id/debug/zeros/mode).
    req = Stm2Req(19, PdiCommand.STM2_GET, Stm2Action.CONFIG, mode=1, debug=2)
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.STM2_GET.as_bytes in bs
    assert Stm2Action.CONFIG.as_bytes in bs
    # Ensure the characteristic CONFIG body pattern is absent
    unexpected_tail = bytes([req.tmcc_id, 2, 0x00, 0x00, 0x01])
    assert unexpected_tail not in bs


def test_is_thru_is_out_properties_match_state():
    # OUT
    req_out = Stm2Req(3, PdiCommand.STM2_SET, Stm2Action.CONTROL1, state=TMCC1SwitchCommandEnum.OUT)
    assert req_out.is_out is True
    assert req_out.is_thru is False

    # THRU
    req_thru = Stm2Req(4, PdiCommand.STM2_SET, Stm2Action.CONTROL1, state=TMCC1SwitchCommandEnum.THRU)
    assert req_thru.is_thru is True
    assert req_thru.is_out is False
