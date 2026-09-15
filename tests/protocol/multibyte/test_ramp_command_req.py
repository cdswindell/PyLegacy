from ipaddress import IPv4Address
from unittest.mock import Mock, patch

import pytest

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import DEFAULT_ADDRESS, CommandScope
from pytrain.protocol.multibyte.dcds_command_req import VariableCommandReq
from pytrain.protocol.multibyte.multibyte_command_req import MultiByteReq
from pytrain.protocol.multibyte.multibyte_constants import (
    TMCC2DcdsCommandEnum,
    TMCC2EngineCommandEnumEx,
    TMCC2ParameterEnum,
    TMCC2ParameterIndex,
    TMCC2VariableEnum,
    VariableCommandDef,
)
from pytrain.protocol.multibyte.param_command_req import PARAMETER_ENUM_TO_INDEX_MAP, ParameterCommandReq
from pytrain.protocol.multibyte.ramp_command_req import RampCommandReq


RAMP_COMMANDS = (TMCC2EngineCommandEnumEx.RAMP_CLAIM, TMCC2EngineCommandEnumEx.RAMP_RELEASE)
SCOPES = (CommandScope.ENGINE, CommandScope.TRAIN)
TIMESTAMP_MS = 1_700_000_000_123
PAYLOAD = bytes.fromhex("c0a801071234abcd018bcfe5687b")


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("timestamp_ms", (1, TIMESTAMP_MS, (1 << 48) - 1))
def test_ramp_timestamp_roundtrip(command, timestamp_ms):
    req = RampCommandReq.for_endpoint(command, 3180, "192.168.1.7", 0x1234, 0xABCD, timestamp_ms=timestamp_ms)
    assert req.timestamp_ms == timestamp_ms
    assert req.data_bytes == bytes.fromhex("c0a801071234abcd") + timestamp_ms.to_bytes(6, "big")
    assert len(req.data_bytes) == 14
    assert len(req.as_bytes) == req.num_bytes == 63
    for parser in (CommandReq, MultiByteReq, VariableCommandReq, RampCommandReq):
        parsed = parser.from_bytes(req.as_bytes)
        assert isinstance(parsed, RampCommandReq)
        assert parsed.command is command
        assert parsed.timestamp_ms == timestamp_ms
        assert parsed.data_bytes == req.data_bytes
        assert parsed.as_bytes == req.as_bytes
    with pytest.raises(AttributeError):
        req.timestamp_ms = timestamp_ms + 1


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("address", (7, 3180, 9999))
@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize("from_tmcc_rx", (False, True))
def test_ramp_roundtrip(command, address, scope, from_tmcc_rx):
    req = RampCommandReq.for_endpoint(command, address, "192.168.1.7", 0x1234, 0xABCD, scope, timestamp_ms=TIMESTAMP_MS)
    assert isinstance(req, VariableCommandReq)
    assert req.command is command
    assert req.is_noop
    assert bytes(req.data_bytes) == PAYLOAD
    assert (req.host, req.port, req.claim_id) == ("192.168.1.7", 0x1234, 0xABCD)
    assert req.timestamp_ms == TIMESTAMP_MS
    assert not hasattr(req, "destination")
    assert not hasattr(req, "guid")
    assert isinstance(command.value, VariableCommandDef)
    assert command.value.num_data_bytes == 16
    assert command.value.bits == (0xF100 if command is RAMP_COMMANDS[0] else 0xF101)
    assert TMCC2EngineCommandEnumEx.by_value(command.value.bits) is command

    packet = req.as_bytes
    assert len(packet) == 63 == req.num_bytes
    assert packet[:3] == bytes((0xF9 if scope is CommandScope.TRAIN else 0xF8, 3, 0x6F))
    assert packet[5] == 16
    assert packet[8] == command.value.lsb
    assert packet[11] == command.value.msb
    assert packet[14:60:3] == address.to_bytes(2, "big") + PAYLOAD
    assert all(packet[i : i + 2] == bytes((0xFB, 2 + (scope is CommandScope.TRAIN))) for i in range(3, 63, 3))
    assert packet[-1:] == MultiByteReq.checksum(packet[:-1])
    assert req.address == address
    assert req.is_tmcc4 is False

    for parser in (CommandReq, MultiByteReq, VariableCommandReq, RampCommandReq):
        with patch.object(VariableCommandReq, "build", wraps=VariableCommandReq.build) as build:
            parsed = parser.from_bytes(packet, from_tmcc_rx=from_tmcc_rx)
            build.assert_called_once_with(command, 1, list(packet[14:60:3]), scope, address_bytes=packet[1:3])
        assert isinstance(parsed, RampCommandReq)
        assert parsed.command is command
        assert parsed.scope is scope
        assert parsed.address == address
        assert parsed.is_tmcc_rx is from_tmcc_rx
        assert parsed.is_tmcc4 is False
        assert parsed.as_bytes == packet
        assert (parsed.host, parsed.port, parsed.claim_id) == (req.host, req.port, req.claim_id)
        assert parsed.timestamp_ms == req.timestamp_ms


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("builder", (CommandReq, MultiByteReq, VariableCommandReq, RampCommandReq))
def test_build_dispatch(command, builder):
    req = builder.build(command, 7, PAYLOAD, CommandScope.TRAIN)
    assert isinstance(req, RampCommandReq)
    assert req.scope is CommandScope.TRAIN
    assert bytes(req.data_bytes) == PAYLOAD


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("address", (7, 3180, 9999))
@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize("builder", (VariableCommandReq, RampCommandReq))
def test_ramp_builder_decodes_wire_payload(command, address, scope, builder):
    req = builder.build(
        command,
        data_bytes=address.to_bytes(2, "big") + PAYLOAD,
        scope=scope,
        address_bytes=b"\x03\x6f",
    )
    assert isinstance(req, RampCommandReq)
    assert (req.command, req.address, req.scope) == (command, address, scope)
    assert req.data_bytes == PAYLOAD
    assert req.as_bytes == RampCommandReq.build(command, address, PAYLOAD, scope).as_bytes


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("address_bytes", (b"\x01\x6f", b"\x0f\x6f", b"\xc7\x6f", b"\x01\x6f3180"))
@pytest.mark.parametrize("builder", (VariableCommandReq, RampCommandReq))
def test_ramp_builder_rejects_noncanonical_wire_address(command, address_bytes, builder):
    with pytest.raises(ValueError, match="three-byte words at framing address 1"):
        builder.build(command, data_bytes=b"\x0c\x6c" + PAYLOAD, address_bytes=address_bytes)


@pytest.mark.parametrize("payload", (None, b"", PAYLOAD, b"\x07" + PAYLOAD, b"\x00\x00\x07" + PAYLOAD))
@pytest.mark.parametrize("builder", (VariableCommandReq, RampCommandReq))
def test_ramp_builder_rejects_incomplete_wire_payload(payload, builder):
    with pytest.raises(ValueError, match="wire payload must contain exactly sixteen bytes"):
        builder.build(RAMP_COMMANDS[0], data_bytes=payload, address_bytes=b"\x03\x6f")


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("address,scope", ((7, CommandScope.ENGINE), (3180, CommandScope.TRAIN)))
@pytest.mark.parametrize("parsed", (False, True))
@pytest.mark.parametrize("entry_point", ("send", "as_action"))
def test_ramp_instance_send_entry_points_rejected(command, address, scope, parsed, entry_point):
    req = RampCommandReq.build(command, address, PAYLOAD, scope)
    if parsed:
        req = CommandReq.from_bytes(req.as_bytes, from_tmcc_rx=True)
    with (
        patch.object(CommandReq, "_enqueue_command") as enqueue,
        patch("pytrain.comm.comm_buffer.CommBuffer.build") as build_buffer,
    ):
        with pytest.raises(ValueError, match=rf"{command.name}.*state-only.*CommBuffer\.update_state"):
            getattr(req, entry_point)()
        enqueue.assert_not_called()
        build_buffer.assert_not_called()


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("builder", (CommandReq, MultiByteReq, VariableCommandReq, RampCommandReq))
@pytest.mark.parametrize("entry_point", ("send_request", "build_action"))
def test_ramp_class_send_entry_points_rejected(command, builder, entry_point):
    with (
        patch.object(CommandReq, "_enqueue_command") as enqueue,
        patch("pytrain.comm.comm_buffer.CommBuffer.build") as build_buffer,
    ):
        with pytest.raises(ValueError, match=rf"{command.name}.*state-only.*CommBuffer\.update_state"):
            getattr(builder, entry_point)(command, 7, PAYLOAD, CommandScope.TRAIN)
        enqueue.assert_not_called()
        build_buffer.assert_not_called()


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("entry_point", ("send_request", "build_action"))
def test_ramp_encoded_send_entry_points_rejected(command, entry_point):
    packet = RampCommandReq.build(command, 3180, PAYLOAD, CommandScope.ENGINE).as_bytes
    with (
        patch.object(CommandReq, "_enqueue_command") as enqueue,
        patch("pytrain.comm.comm_buffer.CommBuffer.build") as build_buffer,
    ):
        with pytest.raises(ValueError, match=rf"{command.name}.*state-only.*CommBuffer\.update_state"):
            getattr(CommandReq, entry_point)(packet)
        enqueue.assert_not_called()
        build_buffer.assert_not_called()


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("as_request", (False, True))
def test_ramp_private_enqueue_rejected(command, as_request):
    req = RampCommandReq.build(command, 7, PAYLOAD)
    buffer = Mock()
    with patch("pytrain.comm.comm_buffer.CommBuffer.build") as build_buffer:
        with pytest.raises(ValueError, match=rf"{command.name}.*state-only.*CommBuffer\.update_state"):
            CommandReq._enqueue_command(
                req.as_bytes if as_request else req,
                repeat=1,
                delay=0,
                duration=0,
                baudrate=9600,
                port="unused",
                server=None,
                buffer=buffer,
                request=req if as_request else None,
                trigger_effects=False,
            )
        buffer.enqueue_command.assert_not_called()
        build_buffer.assert_not_called()


@pytest.mark.parametrize("entry_point", ("send", "as_action", "send_request", "build_action"))
def test_normal_variable_send_entry_points_unchanged(entry_point):
    command = TMCC2DcdsCommandEnum.MASTER_VOLUME
    req = CommandReq.build(command, 7, 127)
    with (
        patch.object(CommandReq, "_enqueue_command") as enqueue,
        patch("pytrain.comm.comm_buffer.CommBuffer.build"),
    ):
        if entry_point in {"send_request", "build_action"}:
            result = getattr(CommandReq, entry_point)(command, 7, 127)
        else:
            result = getattr(req, entry_point)()
        if entry_point in {"as_action", "build_action"}:
            result()
        enqueue.assert_called_once()
        assert enqueue.call_args.kwargs["request"].command is command


@pytest.mark.parametrize("payload_type", (bytearray, list))
def test_build_defaults_and_payload_copy(payload_type):
    payload = payload_type(PAYLOAD)
    assert DEFAULT_ADDRESS == 99
    with pytest.raises(ValueError, match="address"):
        RampCommandReq.build(RAMP_COMMANDS[0], data_bytes=payload)
    req = RampCommandReq.build(RAMP_COMMANDS[0], 7, data_bytes=payload)
    payload[0] = 0
    payload[8:] = bytes(6)
    assert req.address == 7
    assert req.scope is CommandScope.ENGINE
    assert bytes(req.data_bytes) == PAYLOAD
    assert req.timestamp_ms == TIMESTAMP_MS
    with pytest.raises(TypeError):
        req.data_bytes[8] = 0
    with pytest.raises(AttributeError):
        req.data_bytes = bytes(14)
    assert RampCommandReq.build(RAMP_COMMANDS[0], 7, data_bytes=list(PAYLOAD)).as_bytes == req.as_bytes


def test_claim_wire_encoding():
    req = RampCommandReq.build(RAMP_COMMANDS[0], 7, PAYLOAD)
    assert req.as_bytes == bytes.fromhex(
        "f8 03 6f fb 02 10 fb 02 00 fb 02 f1 fb 02 00 fb 02 07 "
        "fb 02 c0 fb 02 a8 fb 02 01 fb 02 07 "
        "fb 02 12 fb 02 34 fb 02 ab fb 02 cd "
        "fb 02 01 fb 02 8b fb 02 cf fb 02 e5 fb 02 68 fb 02 7b fb 02 0c"
    )


@pytest.mark.parametrize("address", (7, 3180, 9999))
@pytest.mark.parametrize("scope", SCOPES)
def test_serialization_does_not_mutate_request(address, scope):
    req = RampCommandReq.build(RAMP_COMMANDS[0], address, PAYLOAD, scope)
    original = req.__dict__.copy()
    with patch.object(
        RampCommandReq, "__setattr__", side_effect=AssertionError("Serialization must not mutate requests")
    ):
        packet = req.as_bytes
        assert req.as_bytes == packet
    assert req.__dict__ == original
    assert CommandReq.from_bytes(packet).address == address


@pytest.mark.parametrize("address", (7, 3180, 9999))
@pytest.mark.parametrize("scope", SCOPES)
def test_updated_logical_address_and_scope(address, scope):
    req = RampCommandReq.build(RAMP_COMMANDS[0], 1, PAYLOAD)
    req.address = address
    req.scope = scope
    parsed = CommandReq.from_bytes(req.as_bytes)
    assert parsed.address == address
    assert parsed.scope is scope
    assert parsed.data_bytes == PAYLOAD
    assert parsed.timestamp_ms == TIMESTAMP_MS
    assert parsed.num_bytes == 63


def test_endpoint_and_claim_id_form_identity():
    req = RampCommandReq.for_endpoint(RAMP_COMMANDS[0], 7, "192.168.1.7", 1234, 1, timestamp_ms=TIMESTAMP_MS)
    for host, port, claim_id in (("192.168.1.8", 1234, 1), ("192.168.1.7", 1235, 1), ("192.168.1.7", 1234, 2)):
        other = RampCommandReq.for_endpoint(RAMP_COMMANDS[0], 7, host, port, claim_id, timestamp_ms=TIMESTAMP_MS)
        assert req != other
        assert req.data_bytes != other.data_bytes
        assert req.as_bytes != other.as_bytes


@pytest.mark.parametrize("host", ("127.0.0.1", "10.0.0.7", "169.254.1.7", "192.0.2.7", "8.8.8.8"))
@pytest.mark.parametrize("port,claim_id", ((1, 1), (65535, 65535)))
def test_valid_endpoints(host, port, claim_id):
    req = RampCommandReq.for_endpoint(RAMP_COMMANDS[0], 7, host, port, claim_id, timestamp_ms=TIMESTAMP_MS)
    assert bytes(req.data_bytes) == (
        IPv4Address(host).packed
        + port.to_bytes(2, "big")
        + claim_id.to_bytes(2, "big")
        + TIMESTAMP_MS.to_bytes(6, "big")
    )
    parsed = CommandReq.from_bytes(req.as_bytes)
    assert (parsed.host, parsed.port, parsed.claim_id) == (host, port, claim_id)
    assert parsed.timestamp_ms == TIMESTAMP_MS


@pytest.mark.parametrize(
    "payload",
    (
        None,
        14,
        "12345678901234",
        b"",
        PAYLOAD[:8],
        PAYLOAD[:-1],
        PAYLOAD + b"\x00",
        b"\x00\x07" + PAYLOAD,
        [256] * 14,
        [-1] * 14,
    ),
)
def test_invalid_payload(payload):
    with pytest.raises(ValueError):
        RampCommandReq.build(RAMP_COMMANDS[0], 7, payload)


@pytest.mark.parametrize("host", ("0.0.0.0", "0.1.2.3", "224.0.0.1", "239.255.255.255", "240.0.0.1", "255.255.255.255"))
def test_invalid_unicast_endpoint(host):
    with pytest.raises(ValueError):
        RampCommandReq.for_endpoint(RAMP_COMMANDS[0], 7, host, 1234, 1, timestamp_ms=TIMESTAMP_MS)
    with pytest.raises(ValueError):
        RampCommandReq.build(RAMP_COMMANDS[0], 7, IPv4Address(host).packed + PAYLOAD[4:])


@pytest.mark.parametrize("host", ("::1", "::ffff:192.168.1.7", "localhost", "bad-ip", "192.168.1.256", 1, None))
def test_invalid_host(host):
    with pytest.raises(ValueError):
        RampCommandReq.for_endpoint(RAMP_COMMANDS[0], 7, host, 1234, 1, timestamp_ms=TIMESTAMP_MS)


@pytest.mark.parametrize("field", ("port", "claim_id"))
@pytest.mark.parametrize("value", (0, -1, 65536, True, 1.5, "1234", None))
def test_invalid_endpoint_integer(field, value):
    endpoint = {"host": "127.0.0.1", "port": 1234, "claim_id": 1}
    endpoint[field] = value
    with pytest.raises(ValueError):
        RampCommandReq.for_endpoint(RAMP_COMMANDS[0], 7, **endpoint, timestamp_ms=TIMESTAMP_MS)


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize("timestamp_ms", (0, -1, 1 << 48, (1 << 48) + 1, True, False, 1.0, "1", None))
def test_invalid_timestamp(command, timestamp_ms):
    with pytest.raises(ValueError, match="timestamp_ms"):
        RampCommandReq.for_endpoint(command, 7, "192.168.1.7", 1234, 1, timestamp_ms=timestamp_ms)


@pytest.mark.parametrize("command", RAMP_COMMANDS)
def test_timestamp_is_required_keyword(command):
    with pytest.raises(TypeError, match="timestamp_ms"):
        RampCommandReq.for_endpoint(command, 7, "192.168.1.7", 1234, 1)
    with pytest.raises(TypeError):
        RampCommandReq.for_endpoint(command, 7, "192.168.1.7", 1234, 1, CommandScope.ENGINE, TIMESTAMP_MS)


@pytest.mark.parametrize("command", RAMP_COMMANDS)
@pytest.mark.parametrize(
    "builder", (CommandReq.build, MultiByteReq.build, VariableCommandReq.build, RampCommandReq.build, RampCommandReq)
)
def test_zero_timestamp_in_payload(command, builder):
    with pytest.raises(ValueError, match="timestamp_ms"):
        builder(command, 7, PAYLOAD[:8] + bytes(6))


@pytest.mark.parametrize("offset", (4, 6))
def test_zero_endpoint_integer_in_payload(offset):
    payload = bytearray(PAYLOAD)
    payload[offset : offset + 2] = b"\x00\x00"
    with pytest.raises(ValueError):
        RampCommandReq.build(RAMP_COMMANDS[0], 7, payload)


@pytest.mark.parametrize("scope", (CommandScope.ACC, CommandScope.SWITCH, "ENGINE", 1))
def test_invalid_scope(scope):
    with pytest.raises(ValueError):
        RampCommandReq.build(RAMP_COMMANDS[0], 7, PAYLOAD, scope)


@pytest.mark.parametrize("address", (0, -1, 99, 10000, True, 7.5, "7", None))
def test_invalid_address(address):
    with pytest.raises(ValueError):
        RampCommandReq.build(RAMP_COMMANDS[0], address, PAYLOAD)


@pytest.mark.parametrize("command", (TMCC2EngineCommandEnumEx.TARGET_SPEED, TMCC2DcdsCommandEnum.MASTER_VOLUME))
def test_ramp_rejects_other_commands(command):
    with pytest.raises(ValueError):
        RampCommandReq.build(command, 7, PAYLOAD)


def repair_checksum(packet, word_length):
    index = len(packet) - word_length + 2
    packet[index] = MultiByteReq.checksum(bytes(packet[:index]), is_d4=word_length == 7)[0]
    return bytes(packet)


@pytest.mark.parametrize("address,is_d4", ((7, False), (99, False), (7, True), (99, True)))
@pytest.mark.parametrize("scope", SCOPES)
def test_variable_parser_delegates_address_values_to_builder(address, is_d4, scope):
    command = TMCC2DcdsCommandEnum.MASTER_VOLUME
    packet = bytearray(VariableCommandReq.build(command, 3180 if is_d4 else 7, 127, scope).as_bytes)
    word_length = 7 if is_d4 else 3
    if is_d4:
        for i in range(0, len(packet), word_length):
            packet[i + 3 : i + 7] = f"{address:04d}".encode()
    else:
        packet[1] = (address << 1) | 1
        for i in range(word_length, len(packet), word_length):
            packet[i + 1] = (address << 1) | (scope is CommandScope.TRAIN)
    with patch.object(VariableCommandReq, "build", wraps=VariableCommandReq.build) as build:
        parsed = VariableCommandReq.from_bytes(repair_checksum(packet, word_length), from_tmcc_rx=True)
        build.assert_called_once_with(
            command, address, [127], scope, address_bytes=bytes(packet[1:7] if is_d4 else packet[1:3])
        )
    assert (parsed.command, parsed.address, parsed.data, parsed.scope) == (command, address, 127, scope)
    assert parsed.is_tmcc_rx
    assert parsed.is_tmcc4 is is_d4


@pytest.mark.parametrize("address", (100, 127))
@pytest.mark.parametrize("scope", SCOPES)
def test_variable_parser_delegates_unsupported_address_encoding(address, scope):
    command = TMCC2DcdsCommandEnum.MASTER_VOLUME
    packet = bytearray(VariableCommandReq.build(command, 7, 127, scope).as_bytes)
    packet[1] = (address << 1) | 1
    for i in range(3, len(packet), 3):
        packet[i + 1] = (address << 1) | (scope is CommandScope.TRAIN)
    with patch.object(command.value, "address_from_bytes", wraps=command.value.address_from_bytes) as decode:
        with pytest.raises(AttributeError, match="Cannot decode address from bytes"):
            VariableCommandReq.from_bytes(repair_checksum(packet, 3))
        decode.assert_called_once_with(bytes(packet[1:3]))


@pytest.mark.parametrize("digit_count", range(4))
def test_variable_address_decoder_rejects_incomplete_four_digit_address(digit_count):
    with pytest.raises(AttributeError, match="Cannot decode address from bytes"):
        TMCC2DcdsCommandEnum.MASTER_VOLUME.value.address_from_bytes(b"\x01\x6f" + b"3180"[:digit_count])


@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize("mutation", ("late_prefix", "word_address", "scope", "data_length"))
def test_variable_parser_preserves_original_framing_checks(scope, mutation):
    command = TMCC2DcdsCommandEnum.GET_STATUS
    packet = bytearray(VariableCommandReq.build(command, 7, scope=scope).as_bytes)
    if mutation == "late_prefix":
        packet[18] = 0xF8
    elif mutation == "word_address":
        packet[19] ^= 2
    elif mutation == "scope":
        packet[0] = 0xF9 if scope is CommandScope.ENGINE else 0xF8
    else:
        del packet[18:21]
        packet[5] -= 1
    packet = repair_checksum(packet, 3)
    with patch.object(VariableCommandReq, "build", wraps=VariableCommandReq.build) as build:
        parsed = VariableCommandReq.from_bytes(packet, from_tmcc_rx=True)
        build.assert_called_once_with(
            command,
            7,
            list(packet[14:-3:3]),
            CommandScope.TRAIN if packet[0] == 0xF9 else CommandScope.ENGINE,
            address_bytes=packet[1:3],
        )
    assert parsed.command is command
    assert parsed.address == 7
    assert parsed.is_tmcc_rx


@pytest.mark.parametrize("address", (7, 3180))
@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize(
    "mutation",
    (
        "checksum",
        "first_address",
        "index",
        "command",
        "count",
        "zero_port",
        "zero_id",
        "zero_timestamp",
        "multicast",
        "broadcast",
    ),
)
def test_malformed_packets(address, scope, mutation):
    req = RampCommandReq.build(RAMP_COMMANDS[0], address, PAYLOAD, scope)
    packet = bytearray(req.as_bytes)
    word_length = 3
    if mutation == "checksum":
        packet[-word_length + 2] ^= 1
    elif mutation == "first_address":
        packet[1] &= 0xFE
    elif mutation == "index":
        packet[2] = 0x6E
    elif mutation == "command":
        packet[3 * word_length + 2] = 0xF2
    elif mutation == "count":
        packet[word_length + 2] = 15
    elif mutation in {"zero_port", "zero_id"}:
        offset = 10 if mutation == "zero_port" else 12
        packet[offset * word_length + 2] = 0
        packet[(offset + 1) * word_length + 2] = 0
    elif mutation == "zero_timestamp":
        packet[44:60:3] = bytes(6)
    elif mutation == "multicast":
        packet[6 * word_length + 2] = 224
    elif mutation == "broadcast":
        packet[4 * word_length + 2] = 0
        packet[5 * word_length + 2] = 99
    if mutation != "checksum":
        packet = repair_checksum(packet, word_length)
    with pytest.raises(ValueError):
        CommandReq.from_bytes(bytes(packet))


@pytest.mark.parametrize("suffix", (b"3180", b"3181", b"3x80", b"\xff180", b"0007"))
@pytest.mark.parametrize("scope", SCOPES)
def test_malformed_four_digit_address(suffix, scope):
    packet = bytearray(RampCommandReq.build(RAMP_COMMANDS[0], 3180, PAYLOAD, scope).as_bytes)
    packet[1] = 1
    for i in range(3, len(packet), 3):
        packet[i + 1] = scope is CommandScope.TRAIN
    packet = bytearray(b"".join(bytes(packet[i : i + 3]) + suffix for i in range(0, len(packet), 3)))
    with pytest.raises(ValueError):
        CommandReq.from_bytes(repair_checksum(packet, 7))


@pytest.mark.parametrize("size", (0, 1, 7, 8, 9, 10, 11, 14, 15, 17))
@pytest.mark.parametrize("address", (7, 3180))
def test_framed_wrong_payload_length(size, address):
    packet = RampCommandReq.build(RAMP_COMMANDS[0], address, PAYLOAD).as_bytes
    word_length = 3
    words = [packet[i : i + word_length] for i in range(0, len(packet), word_length)]
    data_words = (words[4:20] + [words[4]])[:size]
    invalid = bytearray(b"".join(words[:4] + data_words + words[-1:]))
    invalid[word_length + 2] = size
    with pytest.raises(ValueError):
        CommandReq.from_bytes(repair_checksum(invalid, word_length))


@pytest.mark.parametrize("address", (0, 99, 10000, 65535))
@pytest.mark.parametrize("scope", SCOPES)
def test_invalid_logical_address_header(address, scope):
    packet = bytearray(RampCommandReq.build(RAMP_COMMANDS[0], 3180, PAYLOAD, scope).as_bytes)
    packet[14:18:3] = address.to_bytes(2, "big")
    for parser in (CommandReq, MultiByteReq, VariableCommandReq, RampCommandReq):
        with pytest.raises(ValueError, match="ramp address"):
            parser.from_bytes(repair_checksum(packet, 3))


@pytest.mark.parametrize("offset", (14, 17))
def test_logical_address_header_checksum(offset):
    packet = bytearray(RampCommandReq.build(RAMP_COMMANDS[0], 3180, PAYLOAD).as_bytes)
    packet[offset] ^= 1
    with pytest.raises(ValueError, match="checksum"):
        CommandReq.from_bytes(bytes(packet))
    parsed = CommandReq.from_bytes(repair_checksum(packet, 3))
    assert parsed.address == int.from_bytes(packet[14:18:3], "big")
    assert parsed.address != 3180


@pytest.mark.parametrize("address", (0, 7, 99))
@pytest.mark.parametrize("scope", SCOPES)
def test_noncanonical_framing_address(address, scope):
    packet = bytearray(RampCommandReq.build(RAMP_COMMANDS[0], 3180, PAYLOAD, scope).as_bytes)
    packet[1] = (address << 1) | 1
    for i in range(3, len(packet), 3):
        packet[i + 1] = (address << 1) | (scope is CommandScope.TRAIN)
    with patch.object(RampCommandReq, "build", wraps=RampCommandReq.build) as build:
        error = AttributeError if address == 0 else ValueError
        message = "Cannot decode address from bytes" if address == 0 else "framing address 1"
        with pytest.raises(error, match=message):
            CommandReq.from_bytes(repair_checksum(packet, 3))
        if address == 0:
            build.assert_not_called()
        else:
            build.assert_called_once_with(
                RAMP_COMMANDS[0], address, list(packet[14:60:3]), scope, address_bytes=bytes(packet[1:3])
            )


@pytest.mark.parametrize("address", (7, 3180))
def test_truncated_packets(address):
    packet = RampCommandReq.build(RAMP_COMMANDS[0], address, PAYLOAD).as_bytes
    for size in range(len(packet)):
        with pytest.raises(ValueError):
            VariableCommandReq.from_bytes(packet[:size])


def test_shared_variable_command_family():
    assert not TMCC2VariableEnum.__members__
    for enum in (TMCC2DcdsCommandEnum, TMCC2EngineCommandEnumEx):
        assert issubclass(enum, TMCC2VariableEnum)
        assert not issubclass(enum, TMCC2ParameterEnum)
        assert enum not in PARAMETER_ENUM_TO_INDEX_MAP
        for command in enum:
            assert isinstance(command, TMCC2VariableEnum)
            assert isinstance(command.value, VariableCommandDef)
            assert command.value._second_byte is TMCC2ParameterIndex.VARIABLE_LENGTH_COMMAND
            assert command.num_data_bytes == command.value.num_data_bytes
    assert TMCC2EngineCommandEnumEx.TARGET_SPEED.num_data_bytes == 1
    assert TMCC2EngineCommandEnumEx.TARGET_SPEED.value.data_max == 199


@pytest.mark.parametrize("builder", (CommandReq, MultiByteReq, VariableCommandReq))
@pytest.mark.parametrize("address", (7, 99, 3180))
@pytest.mark.parametrize("scope", SCOPES)
def test_variable_target_speed_roundtrip(builder, address, scope):
    command = TMCC2EngineCommandEnumEx.TARGET_SPEED
    assert TMCC2EngineCommandEnumEx.by_value(command.value.bits) is command
    word_length = 7 if address > 99 else 3
    for speed in range(200):
        req = builder.build(command, address, speed, scope)
        assert type(req) is VariableCommandReq
        assert req.is_noop
        assert req.index_byte == b"\x6f"
        assert bytes(req.data_bytes) == bytes([speed])
        packet = req.as_bytes
        assert len(packet) == req.num_bytes == 6 * word_length
        assert packet[word_length + 2] == 1
        assert packet[2 * word_length + 2] == command.value.lsb
        assert packet[3 * word_length + 2] == command.value.msb
        assert packet[4 * word_length + 2] == speed
        for from_tmcc_rx in (False, True):
            parsed = builder.from_bytes(packet, from_tmcc_rx=from_tmcc_rx)
            assert type(parsed) is VariableCommandReq
            assert (parsed.command, parsed.address, parsed.scope, parsed.data) == (command, address, scope, speed)
            assert parsed.is_tmcc_rx is from_tmcc_rx
            assert parsed.as_bytes == packet
    with pytest.raises(ValueError, match="TARGET_SPEED"):
        req.send()
    with pytest.raises(ValueError, match="TARGET_SPEED"):
        req.as_action()


@pytest.mark.parametrize("payload", (42, [42], b"\x2a"))
def test_variable_target_speed_payload(payload):
    req = VariableCommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, payload)
    assert req.data == 42
    assert bytes(req.data_bytes) == b"\x2a"


@pytest.mark.parametrize("payload", (-1, 200, 256, [-1], [200], b"\xc8"))
def test_variable_target_speed_rejects_invalid_speed(payload):
    with pytest.raises(ValueError):
        VariableCommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, payload)


@pytest.mark.parametrize("mutation", ("checksum", "count", "command", "speed"))
def test_variable_target_speed_rejects_invalid_packets(mutation):
    packet = bytearray(CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, 42).as_bytes)
    if mutation == "checksum":
        packet[-1] ^= 1
    else:
        packet[{"count": 5, "command": 11, "speed": 14}[mutation]] = 200
        packet = repair_checksum(packet, 3)
    with pytest.raises(ValueError):
        CommandReq.from_bytes(bytes(packet))


def test_variable_parser_preserves_payload_without_range_validation():
    command = TMCC2DcdsCommandEnum.HORN_DIRECT
    packet = bytearray(VariableCommandReq.build(command, 7, 7).as_bytes)
    packet[17] = 8
    packet = repair_checksum(packet, 3)
    parsed = VariableCommandReq.from_bytes(packet)
    assert parsed.command is command
    assert parsed.data == 8
    assert parsed.as_bytes == packet


@pytest.mark.parametrize("command", tuple(TMCC2EngineCommandEnumEx) + tuple(TMCC2DcdsCommandEnum))
def test_parameter_builder_rejects_variable_definitions(command):
    with pytest.raises(ValueError):
        ParameterCommandReq.build(command, 7)


@pytest.mark.parametrize(
    "command,data",
    (
        (TMCC2DcdsCommandEnum.MASTER_VOLUME, 127),
        (TMCC2DcdsCommandEnum.BLEND_VOLUME, 248),
        (TMCC2DcdsCommandEnum.HORN_DIRECT, 7),
        (TMCC2DcdsCommandEnum.GET_INFO, None),
        (TMCC2DcdsCommandEnum.GET_STATUS, None),
    ),
)
@pytest.mark.parametrize("address", (7, 3180))
@pytest.mark.parametrize("scope", SCOPES)
def test_existing_variable_commands(command, data, address, scope):
    req = VariableCommandReq.build(command, address, data, scope)
    assert type(req) is VariableCommandReq
    parsed = CommandReq.from_bytes(req.as_bytes, from_tmcc_rx=True)
    assert type(parsed) is VariableCommandReq
    assert parsed.command is command
    assert parsed.address == address
    assert parsed.scope is scope
    assert parsed.is_tmcc_rx
    assert parsed.as_bytes == req.as_bytes
