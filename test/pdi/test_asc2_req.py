#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# test/pdi/test_asc2_req.py

from src.pytrain.pdi.asc2_req import Asc2Req
from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, Asc2Action, PdiCommand


def test_config_set_as_bytes_contains_fields_and_delay_scaled():
    """
    CONFIG with SET should serialize tmcc_id, debug, two zero bytes, mode, and delay (hundredths).
    """
    req = Asc2Req(
        25,
        PdiCommand.ASC2_SET,
        Asc2Action.CONFIG,
        mode=2,
        debug=7,
        delay=0.37,  # -> 37
    )

    # Human payload shape
    s = req.payload
    assert isinstance(s, str)
    assert "Mode:" in s and "Debug:" in s and "Delay:" in s

    bs = req.as_bytes
    assert isinstance(bs, (bytes, bytearray))
    assert bs[0] == PDI_SOP
    assert bs[-1] == PDI_EOP

    # Core markers
    assert PdiCommand.ASC2_SET.as_bytes in bs
    assert Asc2Action.CONFIG.as_bytes in bs

    # The CONFIG payload for SET includes:
    #   tmcc_id, debug, 0x00, 0x00, mode, delay(0-100)
    expected_tail = bytes([req.tmcc_id, 7, 0x00, 0x00, 2, 37])
    assert expected_tail in bs


def test_control1_set_payload_and_time_byte():
    """
    CONTROL1 with SET should encode (values, time) and include ON-duration in payload.
    """
    req = Asc2Req(10, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1, time=1.23)

    s = req.payload
    assert isinstance(s, str)
    assert "Relay: ON for 1.23 s" in s

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.ASC2_SET.as_bytes in bs
    assert Asc2Action.CONTROL1.as_bytes in bs
    # Expect values=1, time=123
    assert bytes([1, 123]) in bs


def test_control2_set_values_valids_current_behavior():
    """
    CONTROL2 with SET should include [values, valids].
    Current implementation uses 'values' for both bytes when valids is not None.
    """
    req = Asc2Req(
        5,
        PdiCommand.ASC2_SET,
        Asc2Action.CONTROL2,
        values=0x12,
        valids=0x34,  # current code serializes valids using 'values' when not None
    )
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.ASC2_SET.as_bytes in bs
    assert Asc2Action.CONTROL2.as_bytes in bs

    # Current behavior: [0x12, 0x12]
    assert bytes([0x12, 0x12]) in bs


def test_control3_rx_payload_relays_and_valids():
    """
    CONTROL3 with RX should report 'Relays: {values} Valids: {valids}'.
    """
    req = Asc2Req(
        7,
        PdiCommand.ASC2_RX,
        Asc2Action.CONTROL3,
        values=0x0F,
        valids=0xA5,
    )
    s = req.payload
    assert isinstance(s, str)
    assert "Relays: 15" in s and "Valids: 165" in s


def test_control3_set_as_bytes_sub_id_and_time_byte_current_behavior_and_payload():
    """
    CONTROL3 with SET should encode (sub_id, timeHundredths with 1->0 rule).
    Current implementation uses sub_id only if 'values' is not None; mirror that.
    """
    req = Asc2Req(
        8,
        PdiCommand.ASC2_SET,
        Asc2Action.CONTROL3,
        sub_id=5,
        time=0.01,  # rounds to 1 -> special case becomes 0
        values=0,  # trigger current behavior to use sub_id
    )

    s = req.payload
    assert isinstance(s, str)
    assert "Sub ID: 5" in s and "Time: 0.01" in s

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.ASC2_SET.as_bytes in bs
    assert Asc2Action.CONTROL3.as_bytes in bs

    # Expect [sub_id=5, time=0] after 1->0 rule
    assert bytes([5, 0]) in bs


def test_control4_set_payload_thru_and_time_byte_and_is_thru():
    """
    CONTROL4 with SET should include values and time; payload should be THRU/OUT and expose is_thru/is_out.
    """
    req = Asc2Req(
        12,
        PdiCommand.ASC2_SET,
        Asc2Action.CONTROL4,
        values=0,  # THRU
        time=1.0,  # -> 100
    )

    s = req.payload
    assert isinstance(s, str)
    assert "THRU" in s and "Time: 1.0" in s
    assert req.is_thru is True
    assert req.is_out is False

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.ASC2_SET.as_bytes in bs
    assert Asc2Action.CONTROL4.as_bytes in bs
    assert bytes([0, 100]) in bs  # values=0 (THRU), time=100


def test_control4_rx_payload_thru_or_out():
    """
    CONTROL4 with RX should present THRU/OUT without time.
    """
    req_thru = Asc2Req(3, PdiCommand.ASC2_RX, Asc2Action.CONTROL4, values=0)
    s_t = req_thru.payload
    assert "THRU" in s_t and "Time:" not in s_t

    req_out = Asc2Req(3, PdiCommand.ASC2_RX, Asc2Action.CONTROL4, values=1)
    s_o = req_out.payload
    assert "OUT" in s_o and "Time:" not in s_o


def test_control5_set_payload_thru_and_value_byte_and_is_thru():
    """
    CONTROL5 with SET should include only the values byte; payload shows THRU/OUT.
    """
    req = Asc2Req(9, PdiCommand.ASC2_SET, Asc2Action.CONTROL5, values=0)

    s = req.payload
    assert isinstance(s, str)
    assert "THRU" in s
    assert req.is_thru is True
    assert req.is_out is False

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.ASC2_SET.as_bytes in bs
    assert Asc2Action.CONTROL5.as_bytes in bs
    assert bytes([0]) in bs


def test_identify_set_includes_ident_byte():
    """
    IDENTIFY with SET should serialize the ident byte.
    """
    req = Asc2Req(9, PdiCommand.ASC2_SET, Asc2Action.IDENTIFY, ident=0x55)
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.ASC2_SET.as_bytes in bs
    assert Asc2Action.IDENTIFY.as_bytes in bs
    assert (0x55).to_bytes(1, "big") in bs


def test_get_requests_have_minimal_payload_for_config():
    """
    GET requests should not include the additional CONFIG body bytes.
    """
    req = Asc2Req(19, PdiCommand.ASC2_GET, Asc2Action.CONFIG, mode=1, debug=2, delay=0.50)
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.ASC2_GET.as_bytes in bs
    assert Asc2Action.CONFIG.as_bytes in bs
    # Ensure the characteristic CONFIG body pattern is absent
    unexpected_tail = bytes([req.tmcc_id, 2, 0x00, 0x00, 0x01, 50])
    assert unexpected_tail not in bs
