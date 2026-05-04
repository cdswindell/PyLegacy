#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
import pytest

from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, PDI_STF, PdiCommand
from src.pytrain.pdi.pdi_req import PdiReq, PingReq, TmccReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as Engine2


# noinspection PyTypeChecker
def test_encode_decode_text_roundtrip_ascii_and_nulls():
    # Normal ASCII text, padded to field length
    txt = "ABC"
    enc = PdiReq.encode_text(txt, 5)
    assert isinstance(enc, (bytes, bytearray))
    assert enc == b"ABC\x00\x00"
    dec = PdiReq.decode_text(enc)
    assert dec == "ABC"

    # None encodes to all zero bytes; decoder stops at first zero and returns empty string
    enc_none = PdiReq.encode_text(None, 4)
    assert enc_none == b"\x00\x00\x00\x00"
    dec_none = PdiReq.decode_text(enc_none)
    assert dec_none == ""

    # All 0xFF payload decodes to None
    dec_ffs = PdiReq.decode_text(b"\xff\xff\xff\xff")
    assert dec_ffs is None


def test_decode_text_stops_at_null_and_skips_ffs():
    # Stops at NUL terminator
    assert PdiReq.decode_text(b"ABC\x00XYZ") == "ABC"

    # Skips 0xFF bytes inside the field
    assert PdiReq.decode_text(b"A\xffB\x00") == "AB"

    # Empty input -> empty string (current behavior)
    assert PdiReq.decode_text(b"") == ""


def test_decode_int_valid_and_invalid():
    # Positive: plain integer (with NUL terminator)
    assert PdiReq.decode_int(b"123\x00") == 123

    # Positive: signed integer with whitespace (mirrors int() behavior)
    assert PdiReq.decode_int(b" -7\x00") == -7

    # Negative: non-numeric returns 0 (ValueError path)
    assert PdiReq.decode_int(b"ABC\x00") == 0


def test_decode_int_all_ffs_returns_zero():
    # decode_text returns None for all-0xFF fields; int(None) raises TypeError (not caught)
    assert PdiReq.decode_int(b"\xff\xff\xff\xff") == 0


def test_decode_int_none_raises_type_error():
    # decode_text returns None for all-0xFF fields; int(None) raises TypeError (not caught)
    with pytest.raises(TypeError):
        # noinspection PyTypeChecker
        _ = PdiReq.decode_int(None)


def test_scope_record_length_map():
    assert PdiReq.scope_record_length(CommandScope.ENGINE) == 0xC0
    assert PdiReq.scope_record_length(CommandScope.TRAIN) == 0xC0
    assert PdiReq.scope_record_length(CommandScope.ACC) == 0xC0
    assert PdiReq.scope_record_length(CommandScope.SWITCH) == 0x40
    assert PdiReq.scope_record_length(CommandScope.ROUTE) == 0x80


def test_ping_req_as_bytes_framing_and_checksum():
    req = PingReq()
    bs = req.as_bytes

    # Basic framing
    assert isinstance(bs, (bytes, bytearray))
    assert len(bs) >= 4  # SOP + payload (>=1) + checksum + EOP
    assert bs[0] == PDI_SOP
    assert bs[-1] == PDI_EOP

    # Correct command ID
    assert bs[1] == PdiCommand.PING.value

    # Checksum validation using the receiver-side calculation (strip stuffing)
    # This mirrors how PdiReq.__init__ validates incoming frames
    payload_no_sop_eop_cs = bs[1:-2]
    _, computed_checksum = PdiReq._calculate_checksum(payload_no_sop_eop_cs, add_stf=False)
    assert bs[-2] == int.from_bytes(computed_checksum, "big")


# noinspection PyProtectedMember
def _extract_payload_from_pdi_packet(packet: bytes) -> bytes:
    """
    Helper: Strip SOP/EOP and verify checksum using the receiver path.
    Returns the de-stuffed payload (pdi_cmd + tmcc bytes).
    """
    assert packet[0] == PDI_SOP and packet[-1] == PDI_EOP
    recv = packet[1:-2]
    payload, checksum = PdiReq._calculate_checksum(recv, add_stf=False)
    assert packet[-2] == int.from_bytes(checksum, "big")
    return payload


def test_tmcc_as_packets_three_byte_tmcc2_command():
    # 3-byte TMCC2 engine command (e.g., ring bell) at 1-2 digit address
    tmcc = CommandReq.build(Engine2.RING_BELL, address=7)
    tmcc_bytes = tmcc.as_bytes
    assert len(tmcc_bytes) == 3  # standard TMCC/TMCC2 short command

    packets = TmccReq.as_packets(tmcc)
    assert isinstance(packets, list)
    assert len(packets) == 1

    pkt = packets[0]
    # Extract and validate de-stuffed payload (pdi_cmd + tmcc_bytes)
    payload = _extract_payload_from_pdi_packet(pkt)
    assert len(payload) == 1 + len(tmcc_bytes)
    assert payload[0] == PdiCommand.TMCC_TX.value
    assert payload[1:] == tmcc_bytes


def test_tmcc_as_packets_four_digit_tmcc4_command():
    # 4-digit address should produce TMCC4_TX packets with 7-byte TMCC payload (3 + 4 ASCII digits)
    tmcc_4d = CommandReq.build(Engine2.SPEED_MEDIUM, address=1234)
    tmcc_4d_bytes = tmcc_4d.as_bytes
    assert len(tmcc_4d_bytes) == 7  # 3 + 4 ASCII digits

    packets = TmccReq.as_packets(tmcc_4d)
    assert len(packets) == 1

    pkt = packets[0]
    payload = _extract_payload_from_pdi_packet(pkt)
    assert payload[0] == PdiCommand.TMCC4_TX.value
    assert payload[1:] == tmcc_4d_bytes


def test_calculate_checksum_adds_stuff_bytes_for_reserved_values():
    # Build a payload that includes reserved values to trigger stuffing:
    # payload layout: [pdi_cmd, arbitrary, SOP, arbitrary, EOP, STF]
    payload = bytes(
        [
            PdiCommand.TMCC_TX.value,
            0x12,
            PDI_SOP,  # reserved -> should be preceded by STF
            0x34,
            PDI_EOP,  # reserved -> should be preceded by STF
            PDI_STF,  # reserved -> should be preceded by STF
        ]
    )

    stuffed_stream, checksum = PdiReq._calculate_checksum(payload, add_stf=True)
    assert isinstance(stuffed_stream, (bytes, bytearray))
    assert isinstance(checksum, (bytes, bytearray))
    assert len(checksum) == 1

    # Verify that each reserved byte appears in the stuffed stream, immediately
    # preceded by a STF byte (0xFD)
    # We scan forward through stuffed_stream to match each reserved byte in order.
    sidx = 0
    for b in payload:
        if b in (PDI_SOP, PDI_EOP, PDI_STF):
            # find next occurrence of STF followed by this reserved byte
            # starting at sidx
            pos = stuffed_stream.find(bytes([PDI_STF, b]), sidx)
            assert pos != -1, f"Expected STF before reserved byte {hex(b)}"
            sidx = pos + 2
        else:
            # non-reserved bytes appear as-is; find next occurrence in order
            pos = stuffed_stream.find(bytes([b]), sidx)
            assert pos != -1, f"Expected to find byte {hex(b)} in stuffed stream"
            sidx = pos + 1
