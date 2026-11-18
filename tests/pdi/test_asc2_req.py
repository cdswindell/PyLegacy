#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# tests/pdi/test_asc2_req.py

import pytest

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


@pytest.mark.parametrize("command", [PdiCommand.ASC2_SET, PdiCommand.ASC2_RX])
@pytest.mark.parametrize(
    ("values", "valids", "expected_values", "expected_valids"),
    [
        (0x12, 0x34, 0x12, 0x34),
        (0x00, 0x09, 0x00, 0x09),
        (0x01, 0x09, 0x01, 0x09),
        (0x80, 0xFF, 0x80, 0xFF),
        (0xFF, 0x00, 0xFF, 0x00),
        (None, 0xFF, 0x00, 0xFF),
        (0x12, None, 0x12, 0x00),
        (None, None, 0x00, 0x00),
    ],
)
def test_control2_serializes_independent_relay_and_valid_masks(
    command, values, valids, expected_values, expected_valids
):
    """Preserve independent masks, including selective Off and omitted fields."""
    request = Asc2Req(20, command, Asc2Action.CONTROL2, values=values, valids=valids)
    packet = request.as_bytes
    assert packet[1:-2] == bytes([command.value, 20, 0x11, expected_values, expected_valids])
    decoded = Asc2Req(packet)
    assert decoded.values == expected_values
    assert decoded.valids == expected_valids
    assert decoded.as_bytes == packet


def test_control2_get_omits_relay_and_valid_masks():
    request = Asc2Req(20, PdiCommand.ASC2_GET, Asc2Action.CONTROL2, values=0x12, valids=0x34)
    assert request.as_bytes[1:-2] == bytes([0x3C, 20, 0x11])


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


def test_control3_set_encodes_sub_id_without_unrelated_values_and_preserves_time_rule():
    """
    CONTROL3 with SET should encode (sub_id, timeHundredths with 1->0 rule).
    """
    req = Asc2Req(
        8,
        PdiCommand.ASC2_SET,
        Asc2Action.CONTROL3,
        sub_id=5,
        time=0.01,  # rounds to 1 -> special case becomes 0
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
    CONTROL4 with SET includes values and time and exposes the through/out switch position.
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
    # Keep assertions local to each action's packet test so failures identify the command.
    # noinspection DuplicatedCode
    assert req.is_thru is True
    assert req.is_out is False

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.ASC2_SET.as_bytes in bs
    assert Asc2Action.CONTROL4.as_bytes in bs
    assert bytes([0, 100]) in bs  # values=0 (THRU), time=100


def test_control4_rx_payload_thru_or_out():
    """
    CONTROL4 with RX presents the through/out switch position without time.
    """
    req_thru = Asc2Req(3, PdiCommand.ASC2_RX, Asc2Action.CONTROL4, values=0)
    s_t = req_thru.payload
    assert "THRU" in s_t and "Time:" not in s_t

    req_out = Asc2Req(3, PdiCommand.ASC2_RX, Asc2Action.CONTROL4, values=1)
    s_o = req_out.payload
    assert "OUT" in s_o and "Time:" not in s_o


def test_control5_set_payload_thru_and_value_byte_and_is_thru():
    """
    CONTROL5 with SET includes only the values byte and shows the through/out switch position.
    """
    req = Asc2Req(9, PdiCommand.ASC2_SET, Asc2Action.CONTROL5, values=0)

    s = req.payload
    assert isinstance(s, str)
    assert "THRU" in s
    # Keep assertions local to each action's packet test so failures identify the command.
    # noinspection DuplicatedCode
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


@pytest.mark.parametrize("sub_id", range(1, 9))
@pytest.mark.parametrize("values", [None, 0])
def test_control3_uncoupling_pulse_encodes_selected_output_and_one_second(sub_id, values):
    request = Asc2Req(24, PdiCommand.ASC2_SET, Asc2Action.CONTROL3, sub_id=sub_id, time=1.0, values=values)
    assert request.as_bytes[1:6] == PdiCommand.ASC2_SET.as_bytes + bytes([24]) + Asc2Action.CONTROL3.as_bytes + bytes(
        [sub_id, 100]
    )


@pytest.mark.parametrize("sub_id", [-1, 0, 9])
def test_control3_rejects_invalid_output_numbers(sub_id):
    with pytest.raises(ValueError, match="sub_id"):
        Asc2Req(24, PdiCommand.ASC2_SET, Asc2Action.CONTROL3, sub_id=sub_id, time=1.0)


@pytest.mark.parametrize("action", [Asc2Action.CONTROL1, Asc2Action.CONTROL4])
@pytest.mark.parametrize("values", [0, 1])
def test_zero_time_preserves_latching_requests_when_constructed_and_decoded(action, values):
    request = Asc2Req(20, PdiCommand.ASC2_SET, action, values=values, time=0)
    assert request.time == 0
    assert request.as_bytes[4:6] == bytes([values, 0])
    decoded = Asc2Req(request.as_bytes)
    assert decoded.time == 0
    assert decoded.values == values


@pytest.mark.parametrize("duration", [0, 0.5, 1.0, 2.55])
def test_control3_set_decodes_output_and_applies_only_its_default_pulse_time(duration):
    request = Asc2Req(20, PdiCommand.ASC2_SET, Asc2Action.CONTROL3, sub_id=8, time=duration)
    expected = 1.0 if duration == 0 else duration
    assert request.time == expected
    assert request.as_bytes[4:6] == bytes([8, round(expected * 100)])
    decoded = Asc2Req(request.as_bytes)
    assert decoded.sub_id == 8
    assert decoded.time == expected
    assert "Sub ID: 8" in decoded.payload


def test_control3_set_decodes_wire_zero_as_one_second_without_rewriting_packet():
    packet = Asc2Req(20, PdiCommand.ASC2_SET, Asc2Action.CONTROL3, sub_id=8).as_bytes
    assert packet[4:6] == bytes([8, 0])
    decoded = Asc2Req(packet)
    assert decoded.sub_id == 8
    assert decoded.time == 1.0
    assert decoded.as_bytes == packet


@pytest.mark.parametrize("command", [PdiCommand.ASC2_SET, PdiCommand.ASC2_RX])
def test_control2_bitfields_are_not_decoded_as_sub_id_or_pulse_time(command):
    request = Asc2Req(20, command, Asc2Action.CONTROL2, values=8, valids=255)
    decoded = Asc2Req(request.as_bytes)
    assert decoded.sub_id is None
    assert decoded.time is None


def test_control3_rx_keeps_relay_bitmask_and_valid_bits():
    request = Asc2Req(20, PdiCommand.ASC2_RX, Asc2Action.CONTROL3, values=128, valids=255)
    decoded = Asc2Req(request.as_bytes)
    assert decoded.values == 128
    assert decoded.valids == 255
    assert decoded.sub_id is None
    assert decoded.time is None
