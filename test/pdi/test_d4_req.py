#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import time
from datetime import datetime


from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req, LIONEL_EPOCH
from src.pytrain.pdi.pdi_req import PdiReq


def test_lionel_timestamp_bytes_length_and_endianness(monkeypatch):
    # Freeze time to validate little-endian encoding
    fixed_now = LIONEL_EPOCH + 123456
    monkeypatch.setattr(time, "time", lambda: fixed_now)
    ts_bytes = D4Req.lionel_timestamp(as_bytes=True)
    assert isinstance(ts_bytes, (bytes, bytearray))
    assert len(ts_bytes) == 4
    # 123456 seconds since LIONEL_EPOCH, little endian
    assert ts_bytes == (123456).to_bytes(4, "little")


def test_build_count_request_roundtrip_engine():
    req = D4Req(0, PdiCommand.D4_ENGINE, D4Action.COUNT, count=5)
    assert req.action == D4Action.COUNT
    # COUNT requests are scoped to BASE
    from src.pytrain.protocol.constants import CommandScope

    assert req.scope == CommandScope.BASE

    packet = req.as_bytes
    parsed = PdiReq.from_bytes(packet)
    assert isinstance(parsed, D4Req)
    assert parsed.action == D4Action.COUNT
    assert parsed.count == 5
    # COUNT responses maintain BASE scope
    assert parsed.scope == CommandScope.BASE


def test_build_first_rec_request_roundtrip_train():
    req = D4Req(0, PdiCommand.D4_TRAIN, D4Action.FIRST_REC)
    packet = req.as_bytes
    parsed = PdiReq.from_bytes(packet)
    assert isinstance(parsed, D4Req)
    assert parsed.action == D4Action.FIRST_REC
    # FIRST_REC requests are sent to SYSTEM but parsed responses set BASE (see __init__ logic)
    from src.pytrain.protocol.constants import CommandScope

    assert parsed.scope == CommandScope.BASE


def test_build_map_request_roundtrip_with_tmcc_id():
    req = D4Req(0, PdiCommand.D4_ENGINE, D4Action.MAP, tmcc_id=1234)
    packet = req.as_bytes
    parsed = PdiReq.from_bytes(packet)
    assert isinstance(parsed, D4Req)
    assert parsed.action == D4Action.MAP
    # The parser extracts the TMCC id from the ASCII digits in payload
    assert parsed.tmcc_id == 1234


def test_build_query_request_with_data_bytes_and_auto_timestamp_roundtrip(monkeypatch):
    # Freeze Lionel-relative time for deterministic timestamp in payload
    fixed_now = LIONEL_EPOCH + 42
    monkeypatch.setattr(time, "time", lambda: fixed_now)

    rec_no = 42
    start = 0x10
    data_len = 3
    data_bytes = b"\x01\x02\x03"
    req = D4Req(
        rec_no,
        PdiCommand.D4_ENGINE,
        D4Action.QUERY,
        start=start,
        data_length=data_len,
        data_bytes=data_bytes,
        timestamp=None,  # force auto-stamp
    )
    packet = req.as_bytes

    parsed = PdiReq.from_bytes(packet)
    assert isinstance(parsed, D4Req)
    assert parsed.action == D4Action.QUERY
    assert parsed.record_no == rec_no
    assert parsed.start == start
    assert parsed.data_length == data_len
    # Parsed instance should keep the raw data bytes intact
    assert parsed._data_bytes == data_bytes  # pylint: disable=protected-access

    # Timestamp should be present and equal to time() - LIONEL_EPOCH
    assert parsed.timestamp == int(fixed_now - LIONEL_EPOCH)

    # Human-readable timestamp_str should reflect absolute datetime
    expected_dt = datetime.fromtimestamp(fixed_now).strftime("%Y-%m-%d %H:%M:%S")
    assert parsed.timestamp_str == expected_dt


def test_timestamp_str_empty_when_none():
    req = D4Req(1, PdiCommand.D4_ENGINE, D4Action.QUERY, start=0x00, data_length=1, timestamp=None, data_bytes=b"\x00")
    # When building, as_bytes will insert a timestamp; but the object still has timestamp=None before build()
    assert req.timestamp is None
    assert req.timestamp_str == ""


def test_as_key_structure_and_stability():
    req = D4Req(7, PdiCommand.D4_TRAIN, D4Action.COUNT, count=2)
    k1 = req.as_key
    assert isinstance(k1, tuple) and len(k1) == 4

    # Build another logically identical request and ensure key matches the same tuple components
    req2 = D4Req(7, PdiCommand.D4_TRAIN, D4Action.COUNT, count=2)
    k2 = req2.as_key
    assert k1 == k2
