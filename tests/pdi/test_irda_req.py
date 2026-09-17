#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#
#  SPDX-License-Identifier: LPGL
#

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, PDI_STF, IrdaAction, PdiCommand
from src.pytrain.pdi.irda_req import IrdaReq, IrdaSequence
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import CommandScope


def test_config_rx_as_bytes_contains_fields():
    """
    CONFIG with RX should serialize tmcc_id, debug, two zero bytes, sequence, loco_rl, loco_lr.
    """
    req = IrdaReq(
        25,
        PdiCommand.IRDA_RX,
        IrdaAction.CONFIG,
        sequence=IrdaSequence.RECORDING,
        debug=7,
        loco_rl=10,
        loco_lr=20,
    )

    # Human payload shape
    s = req.payload
    assert isinstance(s, str)
    # Be lenient about exact formatting; check key tokens
    assert "Sequence:" in s and "Debug:" in s
    assert "When Engine ID (R -> L):" in s and "When Engine ID (L -> R):" in s

    bs = req.as_bytes
    assert isinstance(bs, (bytes, bytearray))
    assert bs[0] == PDI_SOP
    assert bs[-1] == PDI_EOP

    # Core markers
    assert PdiCommand.IRDA_RX.as_bytes in bs
    assert IrdaAction.CONFIG.as_bytes in bs

    # The CONFIG payload for RX should include:
    #   tmcc_id, debug, 0x00, 0x00, sequence_id, loco_rl, loco_lr
    expected_tail = bytes([req.tmcc_id, 7, 0x00, 0x00, req.sequence_id, 10, 20])
    assert expected_tail in bs


def test_sequence_set_includes_sequence_byte():
    """
    SEQUENCE with SET should serialize the sequence byte.
    """
    req = IrdaReq(10, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=IrdaSequence.BELL_NONE)

    s = req.payload
    assert isinstance(s, str)
    assert "Sequence:" in s  # minimal check

    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.IRDA_SET.as_bytes in bs
    assert IrdaAction.SEQUENCE.as_bytes in bs
    # Sequence byte must appear in the packet
    assert IrdaSequence.BELL_NONE.value.to_bytes(1, "big") in bs


def test_identify_set_includes_ident_byte():
    """
    IDENTIFY with SET should serialize the ident byte.
    """
    req = IrdaReq(9, PdiCommand.IRDA_SET, IrdaAction.IDENTIFY, ident=0x55)
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.IRDA_SET.as_bytes in bs
    assert IrdaAction.IDENTIFY.as_bytes in bs
    assert (0x55).to_bytes(1, "big") in bs


def test_get_requests_have_minimal_payload_for_config():
    """
    GET requests should not include the additional CONFIG body bytes.
    """
    req = IrdaReq(
        19,
        PdiCommand.IRDA_GET,
        IrdaAction.CONFIG,
        sequence=IrdaSequence.CROSSING_GATE_NONE,
        debug=2,
        loco_rl=1,
        loco_lr=2,
    )
    bs = req.as_bytes
    assert bs[0] == PDI_SOP and bs[-1] == PDI_EOP
    assert PdiCommand.IRDA_GET.as_bytes in bs
    assert IrdaAction.CONFIG.as_bytes in bs

    # Ensure the characteristic CONFIG body pattern is absent for GET
    unexpected_tail = bytes([req.tmcc_id, 2, 0x00, 0x00, IrdaSequence.CROSSING_GATE_NONE.value, 1, 2])
    assert unexpected_tail not in bs


def _packet(action, payload=b"", command=PdiCommand.IRDA_RX, tmcc_id=25, error=False):
    body = command.as_bytes + bytes([tmcc_id, action.bits | (0x80 if error else 0)]) + payload
    stuffed, checksum = PdiReq._calculate_checksum(body)
    return bytes([PDI_SOP]) + stuffed + checksum + bytes([PDI_EOP])


def _data_body(engine_id=42, train_id=0, bluetooth_id=b"\x12\x34", direction=0):
    data = bytearray(69)
    data[:3] = PdiCommand.IRDA_RX.as_bytes + bytes([25, IrdaAction.DATA.bits])
    data[3:7] = bytes([0x12, 0x34, 0x56, 0x78])
    data[7:15] = bytes([direction, engine_id, train_id, 4, 128, 255, 33, 7])
    data[15:19] = bytes([0x23, 0x45, 1, 4])
    data[19:21] = bluetooth_id
    data[21:24] = b"24\x00"
    data[24:33] = b"Berkshire"
    data[57:62] = b"765\x00\x00"
    data[62:65] = bytes([1, 8, 199])
    data[65:68] = b"\x56\x34\x12"
    return bytes(data)


@pytest.fixture
def state_lookups(monkeypatch):
    bluetooth = Mock(return_value=None)
    train = Mock(return_value=None)
    monkeypatch.setattr(ComponentStateStore, "by_bluetooth_id", bluetooth)
    monkeypatch.setattr(ComponentStateStore, "get_state", train)
    return bluetooth, train


@pytest.mark.parametrize("engine_id", [0, 1])
@pytest.mark.parametrize("bluetooth_id, expected_id", [(b"\x12\x34", 0x1234), (b"\x00\x00", 0)])
@pytest.mark.parametrize("resolved_id", [0, 1234])
def test_data_resolves_default_engine_by_big_endian_bluetooth_id(
    state_lookups, engine_id, bluetooth_id, expected_id, resolved_id
):
    bluetooth, train = state_lookups
    bluetooth.return_value = SimpleNamespace(tmcc_id=resolved_id)
    body = _data_body(engine_id=engine_id, bluetooth_id=bluetooth_id)
    packet = _packet(IrdaAction.DATA, body[3:])

    req = IrdaReq(packet)

    bluetooth.assert_called_once_with(expected_id)
    train.assert_not_called()
    assert req.bluetooth_id == bluetooth_id
    assert req.bt_id == expected_id
    assert req.engine_id == resolved_id
    assert req.tmcc_id == 25
    assert f"Engine: {resolved_id or 'NA'}" in req.payload
    assert req.as_bytes == packet


@pytest.mark.parametrize("engine_id", [0, 1])
def test_data_bluetooth_lookup_miss_preserves_engine_id(state_lookups, engine_id):
    bluetooth, train = state_lookups
    req = IrdaReq(_packet(IrdaAction.DATA, _data_body(engine_id=engine_id)[3:]))

    bluetooth.assert_called_once_with(0x1234)
    train.assert_not_called()
    assert req.engine_id == engine_id
    assert f"Engine: {engine_id or 'NA'}" in req.payload


@pytest.mark.parametrize("engine_id", [2, 42, 99, 255])
def test_data_nondefault_engine_does_not_use_bluetooth_lookup(state_lookups, engine_id):
    bluetooth, train = state_lookups
    bluetooth.return_value = SimpleNamespace(tmcc_id=9876)
    req = IrdaReq(_packet(IrdaAction.DATA, _data_body(engine_id=engine_id)[3:]))

    assert req.engine_id == engine_id
    assert req.bt_id == 0x1234
    bluetooth.assert_not_called()
    train.assert_not_called()


@pytest.mark.parametrize("train_id, exists, expected", [(0, False, 0), (7, False, 0), (7, True, 7)])
def test_data_validates_train_without_creating_state(state_lookups, train_id, exists, expected):
    bluetooth, train = state_lookups
    train.return_value = SimpleNamespace(tmcc_id=train_id) if exists else None
    req = IrdaReq(_packet(IrdaAction.DATA, _data_body(train_id=train_id)[3:]))

    assert req.train_id == expected
    assert ("Train: 7 " in req.payload) is bool(expected)
    if train_id:
        train.assert_called_once_with(CommandScope.TRAIN, train_id, False)
    else:
        train.assert_not_called()
    bluetooth.assert_not_called()


@pytest.mark.parametrize(
    "direction, right_to_left, left_to_right", [(0, True, False), (1, False, True), (2, False, False)]
)
def test_data_decodes_fields_and_payload(state_lookups, direction, right_to_left, left_to_right):
    req = IrdaReq(_packet(IrdaAction.DATA, _data_body(direction=direction)[3:]))

    assert req.scope == CommandScope.IRDA
    assert req.action == IrdaAction.DATA
    assert req.pdi_command == PdiCommand.IRDA_RX
    assert req.num_addressable_ports == 1
    assert req.valid1 == 0x12
    assert req.valid2 == 0x56
    assert req.direction == direction
    assert req.is_right_to_left is right_to_left
    assert req.is_left_to_right is left_to_right
    assert req.year == 2024
    assert req.name == "Berkshire"
    assert req.number == "765"
    assert req.product_rev == "Road"
    assert req.product_id == "Steam"
    assert req.status == "Recording..."
    assert (req._fuel, req._water, req._burn, req._fwb_mask) == (128, 255, 33, 7)
    assert req._runtime == 0x23
    assert (req._tsdb_left, req._tsdb_right, req._max_speed) == (1, 8, 199)
    assert req._odometer == 0x123456
    travel = "R -> L" if right_to_left else "L -> R"
    assert req.payload == (
        f"{travel} Engine: 42 Berkshire #765 BT: 1234 2024 Type: Steam Od: 1,193,046 ft "
        f"Fuel: 50.20% Water: 100.00% Status: Recording... ({req.packet})"
    )


@pytest.mark.parametrize(
    "length", [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 24, 25, 58, 59, 63, 64, 65, 68, 69]
)
def test_data_truncated_valid_packets_default_missing_fields(state_lookups, length):
    body = _data_body(engine_id=1)[:length]
    packet = _packet(IrdaAction.DATA, body[3:])
    req = IrdaReq(packet)
    expected_fields = {
        "valid1": (5, 0x12),
        "valid2": (7, 0x56),
        "direction": (8, 0),
        "engine_id": (9, 1),
        "train_id": (10, 0),
        "_status": (11, 4),
        "_fuel": (12, 128),
        "_water": (13, 255),
        "_burn": (14, 33),
        "_fwb_mask": (15, 7),
        "_runtime": (16, 0x23),
        "_prod_rev": (18, 1),
        "_prod_id": (19, 4),
        "bluetooth_id": (21, b"\x12\x34"),
        "bt_id": (21, 0x1234),
        "year": (24, 2024),
        "_tsdb_left": (63, 1),
        "_tsdb_right": (64, 8),
        "_max_speed": (65, 199),
        "_odometer": (69, 0x123456),
    }
    for field, (minimum_length, expected) in expected_fields.items():
        assert getattr(req, field) == (expected if length >= minimum_length else None), field
    assert req.name == ("B" if length == 25 else "Berkshire" if length > 25 else None)
    assert req.number == ("76" if length == 59 else "765" if length > 59 else None)
    assert req.as_bytes == packet
    assert req.payload.endswith(f"({req.packet})")
    bluetooth, train = state_lookups
    if length >= 21:
        bluetooth.assert_called_once_with(0x1234)
    else:
        bluetooth.assert_not_called()
    train.assert_not_called()


def test_minimal_data_payload_omits_missing_fields(state_lookups):
    req = IrdaReq(_packet(IrdaAction.DATA))

    assert req.payload == f"L -> R Engine: NA Type: NA Status: NA ({req.packet})"
    assert not req.is_left_to_right
    assert not req.is_right_to_left


@pytest.mark.parametrize("length", range(8))
def test_config_decodes_available_fields(length):
    body = bytes([25, 7, 0, 0, IrdaSequence.RECORDING.value, 10, 20])[:length]
    req = IrdaReq(_packet(IrdaAction.CONFIG, body))

    assert req.debug == (7 if length >= 2 else None)
    assert req.sequence == (IrdaSequence.RECORDING if length >= 5 else None)
    assert req.sequence_id == (9 if length >= 5 else None)
    assert req.sequence_str == ("Recording" if length >= 5 else "NA")
    assert req.loco_rl == (10 if length >= 6 else None)
    assert req.loco_lr == (20 if length >= 7 else None)


@pytest.mark.parametrize(
    "loco_rl, loco_lr, expected_rl, expected_lr", [(0, 255, "Any", "Any"), (255, 0, "Any", "Any"), (10, 20, "10", "20")]
)
def test_config_payload_engine_filters(loco_rl, loco_lr, expected_rl, expected_lr):
    req = IrdaReq(25, PdiCommand.IRDA_RX, IrdaAction.CONFIG, sequence=0, debug=7, loco_rl=loco_rl, loco_lr=loco_lr)

    assert req.payload == (
        f"Sequence: None When Engine ID (R -> L): {expected_rl} "
        f"When Engine ID (L -> R): {expected_lr} Debug: 7 ({req.packet})"
    )


@pytest.mark.parametrize("sequence", list(IrdaSequence))
def test_sequence_decode_and_integer_construction(sequence):
    received = IrdaReq(_packet(IrdaAction.SEQUENCE, bytes([sequence.value])))
    outgoing = IrdaReq(25, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=sequence.value)

    for req in (received, outgoing):
        assert req.sequence is sequence
        assert req.sequence_id == sequence.value
        assert req.sequence_str == sequence.name.title()
        assert req.payload == f"Sequence: {sequence.name.title()} ({req.packet})"
    assert outgoing.as_bytes == _packet(IrdaAction.SEQUENCE, bytes([sequence.value]), PdiCommand.IRDA_SET)


@pytest.mark.parametrize("action", [IrdaAction.SEQUENCE, IrdaAction.RECORD])
def test_empty_action_payload_defaults(action):
    req = IrdaReq(_packet(action))

    assert req.sequence is None
    assert req.sequence_id is None
    assert req.sequence_str == "NA"
    assert req.status == "NA"
    label = "Sequence" if action == IrdaAction.SEQUENCE else "Status"
    assert req.payload == f"{label}: NA ({req.packet})"


@pytest.mark.parametrize(
    "code, expected",
    [(0, "No Recording"), (1, "Idle"), (2, "Playback..."), (3, "Armed..."), (4, "Recording..."), (255, "NA")],
)
def test_record_status_map(code, expected):
    packet = _packet(IrdaAction.RECORD, bytes([code]))
    req = IrdaReq(packet)

    assert req.status == expected
    assert req.payload == f"Status: {expected} ({req.packet})"
    assert req.as_bytes == packet


@pytest.mark.parametrize("code, expected", [(0, "Switcher"), (1, "Road"), (255, "NA")])
def test_product_revision_map(state_lookups, code, expected):
    body = bytearray(_data_body())
    body[17] = code
    assert IrdaReq(_packet(IrdaAction.DATA, body[3:])).product_rev == expected


@pytest.mark.parametrize(
    "code, expected",
    [
        (2, "Diesel"),
        (3, "Diesel Switcher"),
        (4, "Steam"),
        (5, "Steam Switcher"),
        (6, "Subway"),
        (7, "Electric"),
        (8, "Acela"),
        (9, "Pullmor Diesel"),
        (10, "Pullmor Steam"),
        (11, "Breakdown"),
        (12, "Track Crane"),
        (13, "Accessory"),
        (14, "Stock Car"),
        (15, "Passenger Car"),
        (0, "NA"),
        (255, "NA"),
    ],
)
def test_product_id_map(state_lookups, code, expected):
    body = bytearray(_data_body())
    body[18] = code
    assert IrdaReq(_packet(IrdaAction.DATA, body[3:])).product_id == expected


@pytest.mark.parametrize(
    "code, expected",
    [
        (1, "Ditch Lights"),
        (2, "Ground Lights"),
        (3, "MARS Lights"),
        (4, "Hazard Lights"),
        (5, "Strobe Lights"),
        (6, "Reserved"),
        (7, "Reserved"),
        (8, "Rule 17"),
        (9, "Loco Marker"),
        (10, "Tender Marker"),
        (11, "Doghouse"),
        (12, "Reserved"),
        (13, "Reserved"),
        (14, "Reserved"),
        (15, "Reserved"),
        (0, "<Blank>"),
        (255, "<Blank>"),
        (None, "<Blank>"),
    ],
)
def test_tsdb_map(code, expected):
    assert IrdaReq.tsdb(code) == expected


@pytest.mark.parametrize(
    "scope, expected",
    [(None, CommandScope.IRDA), (CommandScope.IRDA, CommandScope.IRDA), (CommandScope.TRAIN, CommandScope.TRAIN)],
)
def test_outgoing_defaults_and_scope(scope, expected):
    req = IrdaReq(25, scope=scope)

    assert req.scope == expected
    assert req.pdi_command == PdiCommand.IRDA_GET
    assert req.action == IrdaAction.CONFIG
    assert req.debug == 0
    assert req.loco_rl == req.loco_lr == 255
    assert req.sequence is None
    assert req.sequence_id is None
    assert req.sequence_str == req.status == "NA"
    assert req.engine_id is req.train_id is req.direction is None
    assert req.num_addressable_ports == 1
    assert req.payload == f"({req.packet})"


@pytest.mark.parametrize("action", [IrdaAction.CONFIG, IrdaAction.SEQUENCE, IrdaAction.RECORD, IrdaAction.IDENTIFY])
def test_get_serialization_is_exactly_header_only(action):
    req = IrdaReq(25, PdiCommand.IRDA_GET, action, sequence=9, ident=85, debug=7)

    assert req.as_bytes == _packet(action, command=PdiCommand.IRDA_GET)
    assert req.payload == f"({req.packet})"


@pytest.mark.parametrize("ident", [None, 0, 85, PDI_SOP, PDI_STF, PDI_EOP])
def test_identify_serialization_defaults_and_stuffing(ident):
    req = IrdaReq(25, PdiCommand.IRDA_SET, IrdaAction.IDENTIFY, ident=ident)
    packet = req.as_bytes

    assert packet == _packet(IrdaAction.IDENTIFY, bytes([ident or 0]), PdiCommand.IRDA_SET)
    assert sum(packet[1:-1]) & 0xFF == 0
    decoded, _ = PdiReq._calculate_checksum(packet[1:-2], False)
    assert decoded == PdiCommand.IRDA_SET.as_bytes + bytes([25, IrdaAction.IDENTIFY.bits, ident or 0])


@pytest.mark.parametrize("debug", [None, 0, 7, PDI_SOP])
def test_config_rx_serialization_round_trip(debug):
    req = IrdaReq(25, PdiCommand.IRDA_RX, IrdaAction.CONFIG, sequence=9, debug=debug, loco_rl=10, loco_lr=20)
    expected = bytes([25, debug or 0, 0, 0, 9, 10, 20])

    assert req.as_bytes == _packet(IrdaAction.CONFIG, expected)
    assert sum(req.as_bytes[1:-1]) & 0xFF == 0
    decoded = IrdaReq(req.as_bytes)
    assert decoded.debug == (debug or 0)
    assert decoded.sequence == IrdaSequence.RECORDING
    assert decoded.loco_rl == 10
    assert decoded.loco_lr == 20
    assert decoded.as_bytes == req.as_bytes


@pytest.mark.parametrize(
    "action, command",
    [
        (IrdaAction.CONFIG, PdiCommand.IRDA_SET),
        (IrdaAction.SEQUENCE, PdiCommand.IRDA_RX),
        (IrdaAction.SEQUENCE, PdiCommand.IRDA_SET),
        (IrdaAction.RECORD, PdiCommand.IRDA_SET),
    ],
)
def test_serialization_falls_back_without_action_body(action, command):
    req = IrdaReq(25, command, action)
    assert req.as_bytes == _packet(action, command=command)


def test_info_decodes_inherited_fields_and_forces_irda_scope():
    packet = _packet(IrdaAction.INFO, bytes([3, 1, 9, 123]))
    # LcsReq decodes inherited fields before IrdaReq reads the action from the packet.
    req = IrdaReq(packet, action=IrdaAction.INFO, scope=CommandScope.TRAIN)

    assert req.scope == CommandScope.IRDA
    assert (req.board_id, req.num_ids, req.model, req.dc_volts) == (3, 1, 9, 12.3)
    assert req.payload == f"Board ID: 3 Num IDs: 1 Model: 9 DC Volts: 12.3 ({req.packet})"
    assert req.as_bytes == packet


def test_error_payload_uses_inherited_representation():
    packet = _packet(IrdaAction.RECORD, bytes([2]), error=True)
    req = IrdaReq(packet)

    assert req.is_error
    assert req.action == IrdaAction.RECORD
    assert req.error == "Action not supported"
    assert req.payload == f"({req.packet})"
    assert req.as_bytes == packet
