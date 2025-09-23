#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

#
#  Tests for BaseReq
#

from typing import Tuple

from src.pytrain.pdi.base_req import BaseReq, decode_labor_rpm, encode_labor_rpm
from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, PdiCommand
from src.pytrain.protocol.constants import CommandScope


def test_encode_decode_labor_rpm_roundtrip():
    # labor valid range maps via spec in encode/decode
    cases: Tuple[Tuple[int, int], ...] = (
        (0, 0),
        (7, 0),
        (0, 12),
        (7, 12),
        (3, 19),
        (5, 31),
    )
    for rpm, labor in cases:
        v = encode_labor_rpm(rpm, labor)
        rpm_d, labor_d = decode_labor_rpm(v)
        assert rpm_d == rpm
        assert labor_d == labor


def test_base_memory_minimal_as_bytes_structure():
    # Build a BASE_MEMORY request for an engine record with minimal args
    req = BaseReq(20, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE)
    pkt = req.as_bytes
    assert isinstance(pkt, (bytes, bytearray))
    # SOP/EOP framing
    assert pkt[0] == PDI_SOP
    assert pkt[-1] == PDI_EOP
    # Inner command should reflect BASE_MEMORY and tmcc_id
    # Format (inner, before stuffing/checksum):
    # [cmd(2)][tmcc_id(1)][flags(1)][status(1)][record_type(1)][start(4)][port(1)][len(1)]...
    # We can sanity-check tmcc_id appears in the encoded packet near the header.
    # Packet contains tmcc_id value 20 somewhere after command bytes; not strict index-assert to avoid brittle test.
    assert 20 in pkt


def test_update_speed_engine_and_train_encode_distinct():
    # Engine update speed
    eng = BaseReq.update_speed(address=7, speed=45, scope=CommandScope.ENGINE)
    trn = BaseReq.update_speed(address=7, speed=45, scope=CommandScope.TRAIN)

    assert eng.pdi_command == PdiCommand.UPDATE_ENGINE_SPEED
    assert trn.pdi_command == PdiCommand.UPDATE_TRAIN_SPEED
    assert eng.speed == 45
    assert trn.speed == 45

    be = eng.as_bytes
    bt = trn.as_bytes
    # Packets should differ due to different PDI command identifiers
    assert be != bt
    # Both framed
    assert be[0] == PDI_SOP and be[-1] == PDI_EOP
    assert bt[0] == PDI_SOP and bt[-1] == PDI_EOP


def test_properties_defaults_and_payload_safe_strings():
    # Basic BASE req (non-memory) minimal
    req = BaseReq(0, PdiCommand.BASE)
    # Access a variety of properties to ensure no exceptions and types match
    assert isinstance(req.flags, int) or req.flags is None
    assert isinstance(req.status, int) or req.status is None
    assert isinstance(req.valid1, int) or req.valid1 is None
    assert isinstance(req.valid2, int) or req.valid2 is None
    assert isinstance(req.name, str) or req.name is None
    assert isinstance(req.number, str) or req.number is None
    # Payload should be a string for human display
    assert isinstance(req.payload, str)


def test_is_active_logic_for_empty_records_engine_like_fields():
    # Build a BASE_ENGINE-like packet with fwd/rev=255 and empty name/number, which should be inactive
    # Construct minimal packet bytes following BaseReq constructor parsing expectations.
    # We will craft: [SOP][cmd(2)][id][flags][status][spare][valid1(2)][valid2(2)]...[fwd=255][rev=255]...[EOP]
    # Easiest is to instantiate via constructor path that generates bytes for us, then tweak.
    req = BaseReq(1, PdiCommand.BASE_ENGINE)
    _ = bytearray(req.as_bytes)
    # Find indices for tmcc_id and after; conservative modifications:
    # Ensure name/number empty by forcing zeros and set fwd/rev to 255 at known positions for engine view
    # (indexes align with parsing code offsets)
    # The parser uses fixed offsets relative to inner buffer start; to simplify,
    # build a new object using bytes path with required fields populated directly.
    #
    # Create inner payload with required fields for BASE_ENGINE:
    inner = bytearray()
    inner += PdiCommand.BASE_ENGINE.as_bytes  # 2
    inner += (1).to_bytes(1, "big")  # tmcc id
    inner += (0x00).to_bytes(1, "big")  # flags
    inner += (0x00).to_bytes(1, "big")  # status
    inner += (0x00).to_bytes(1, "big")  # spare
    inner += (0).to_bytes(2, "little")  # valid1
    inner += (0).to_bytes(2, "little")  # valid2
    inner += (255).to_bytes(1, "big")  # rev_link at [9]
    inner += (255).to_bytes(1, "big")  # fwd_link at [10]
    inner += b"\x00" * (44 - len(inner))  # pad to name start
    inner += b"\x00" * 33  # name
    inner += b"\x00" * 5  # number
    # Pad a bit more to satisfy parser accesses
    inner += b"\x00" * 40

    stuffed, checksum = BaseReq._calculate_checksum(bytes(inner))  # noqa: SLF001
    pkt = bytes([PDI_SOP]) + stuffed + checksum + bytes([PDI_EOP])

    parsed = BaseReq(pkt)
    assert parsed.pdi_command == PdiCommand.BASE_ENGINE
    assert parsed.is_active is False


def test_as_key_tuple_shape_and_content_stability():
    req = BaseReq(5, PdiCommand.BASE_MEMORY, scope=CommandScope.TRAIN)
    k = req.as_key
    assert isinstance(k, tuple) and len(k) == 4
    # record_no and command should be stable
    assert k[0] == 5
    assert k[1] == PdiCommand.BASE_MEMORY
