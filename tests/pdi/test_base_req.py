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

from types import SimpleNamespace
from typing import Tuple, cast
from unittest.mock import Mock, call

import pytest

from src.pytrain.db.comp_data import CompData, EngineData, UpdatePkg
from src.pytrain.db.component_state import ComponentStateDict, RouteState
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_state import EngineState
from src.pytrain.pdi.base3_db_refresh_manager import Base3DbRefreshManager
import src.pytrain.pdi.base_req as base_req_module
from src.pytrain.pdi.base_req import BaseReq, EngineBits, decode_labor_rpm, encode_labor_rpm
from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE, TMCC_CONTROL_TYPE, CommandScope
from src.pytrain.protocol.sequence.ramp_peer import CLAIM_TTL, RampClaim
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


SPEED_UPDATE_SCOPES = [
    pytest.param(PdiCommand.UPDATE_ENGINE_SPEED, CommandScope.ENGINE, "Engine", id="engine"),
    pytest.param(PdiCommand.UPDATE_TRAIN_SPEED, CommandScope.TRAIN, "Train", id="train"),
]
SPEED_UPDATE_ADDRESSES = [
    pytest.param(1, b"\x01\xff", id="2d-1"),
    pytest.param(7, b"\x07\xff", id="2d-7"),
    pytest.param(99, b"\x63\xff", id="2d-99"),
    pytest.param(100, b"\x34\x12", id="4d-100"),
    pytest.param(1234, b"\x34\x12", id="4d-1234"),
    pytest.param(9999, b"\x34\x12", id="4d-9999"),
]
OUTBOUND_SPEED_UPDATE_ADDRESSES = [
    pytest.param(1, b"\x01", id="2d-1"),
    pytest.param(7, b"\x07", id="2d-7"),
    pytest.param(99, b"\x63", id="2d-99"),
    pytest.param(100, b"\x34\x12", id="4d-100"),
    pytest.param(1234, b"\x34\x12", id="4d-1234"),
    pytest.param(9999, b"\x34\x12", id="4d-9999"),
]


def incoming_speed_packet(command: int, address_bytes: bytes, target_speed: int) -> bytes:
    """Frame an incoming update with its mandatory final target byte independently."""
    return frame_speed_packet(bytes([command]) + address_bytes + bytes([target_speed]))


def outgoing_speed_packet(command: int, address_bytes: bytes, target_speed: int) -> bytes:
    """Frame a transmission using unmarked short addresses or little-endian records."""
    return frame_speed_packet(bytes([command]) + address_bytes + bytes([target_speed]))


def frame_speed_packet(payload: bytes) -> bytes:
    """Apply direction-neutral framing independently of production serialization."""
    stuffed = bytearray()
    for value in payload:
        if value in {0xD1, 0xDE, 0xDF}:
            stuffed.append(0xDE)
        stuffed.append(value)
    checksum = -sum(stuffed) & 0xFF
    if checksum in {0xD1, 0xDE, 0xDF}:
        stuffed.append(0xDE)
        checksum = -sum(stuffed) & 0xFF
    return b"\xd1" + bytes(stuffed) + bytes([checksum]) + b"\xdf"


@pytest.fixture
def speed_update_lookups(monkeypatch):
    reverse = Mock(return_value=None)
    forward = Mock(side_effect=AssertionError("Incoming speed updates must not use forward lookup"))
    monkeypatch.setattr(ComponentStateStore, "by_record_no", reverse)
    monkeypatch.setattr(ComponentStateStore, "get_state", forward)
    return reverse, forward


@pytest.mark.parametrize(
    "command,address_bytes,expected",
    [
        pytest.param(PdiCommand.UPDATE_ENGINE_SPEED, b"\x07\xff", b"\xd1\x2a\x07\xff\x2d\xa3\xdf", id="engine-2d"),
        pytest.param(PdiCommand.UPDATE_TRAIN_SPEED, b"\x07\xff", b"\xd1\x2b\x07\xff\x2d\xa2\xdf", id="train-2d"),
        pytest.param(PdiCommand.UPDATE_ENGINE_SPEED, b"\x34\x12", b"\xd1\x2a\x34\x12\x2d\x63\xdf", id="engine-4d"),
        pytest.param(PdiCommand.UPDATE_TRAIN_SPEED, b"\x34\x12", b"\xd1\x2b\x34\x12\x2d\x62\xdf", id="train-4d"),
    ],
)
def test_incoming_speed_packet_matches_fixed_wire_examples(command, address_bytes, expected):
    assert incoming_speed_packet(command, address_bytes, 45) == expected


@pytest.mark.parametrize(
    "command,scope,target_speed,packet,expected_payload",
    [
        pytest.param(
            PdiCommand.UPDATE_ENGINE_SPEED,
            CommandScope.ENGINE,
            5,
            b"\xd1\x2a\x01\xff\x05\xde\xf3\xdf",
            "Engine #1 Target Speed: 5 (0x2A 01 FF 05)",
            id="engine",
        ),
        pytest.param(
            PdiCommand.UPDATE_TRAIN_SPEED,
            CommandScope.TRAIN,
            4,
            b"\xd1\x2b\x01\xff\x04\xde\xf3\xdf",
            "Train #1 Target Speed: 4 (0x2B 01 FF 04)",
            id="train",
        ),
    ],
)
def test_incoming_speed_echo_preserves_stuffed_checksum(
    command, scope, target_speed, packet, expected_payload, speed_update_lookups
):
    reverse, forward = speed_update_lookups
    assert incoming_speed_packet(command, b"\x01\xff", target_speed) == packet

    parsed = PdiReq.from_bytes(packet)

    assert isinstance(parsed, BaseReq)
    assert parsed.pdi_command == command
    assert parsed.scope == scope
    assert parsed.tmcc_id == 1
    assert parsed.target_speed == target_speed
    assert parsed.speed is None
    assert parsed.is_valid(EngineBits.TARGET_SPEED)
    assert not parsed.is_valid(EngineBits.SPEED)
    assert parsed.payload == expected_payload
    assert parsed.as_bytes == packet
    reverse.assert_not_called()
    forward.assert_not_called()


@pytest.mark.parametrize("command,scope,label", SPEED_UPDATE_SCOPES)
@pytest.mark.parametrize("address,address_bytes", SPEED_UPDATE_ADDRESSES)
@pytest.mark.parametrize("target_speed", [0, 45, 199], ids=["stopped", "cruising", "maximum"])
def test_incoming_speed_update_carries_target(
    command, scope, label, address, address_bytes, target_speed, speed_update_lookups
):
    """Complete echoes cover final-byte target limits and the 99/100 address boundary."""
    reverse, forward = speed_update_lookups
    reverse.return_value = SimpleNamespace(tmcc_id=address)
    packet = incoming_speed_packet(command, address_bytes, target_speed)

    parsed = PdiReq.from_bytes(packet)

    assert isinstance(parsed, BaseReq)
    assert parsed.pdi_command == command
    assert parsed.scope == scope
    assert parsed.tmcc_id == address
    assert parsed.target_speed == target_speed
    assert parsed.speed is None
    expected_body = bytes([command]) + address_bytes + bytes([target_speed])
    expected_packet_text = "0x" + expected_body.hex(" ").upper()
    assert parsed.payload == f"{label} #{address} Target Speed: {target_speed} ({expected_packet_text})"
    assert parsed.as_bytes == packet
    forward.assert_not_called()
    if address < 100:
        assert address_bytes == bytes([address, 0xFF])
        reverse.assert_not_called()
    else:
        assert address_bytes == (0x1234).to_bytes(2, "little")
        reverse.assert_called_once_with(0x1234, scope)
    assert parsed.is_valid(EngineBits.TARGET_SPEED)
    assert not parsed.is_valid(EngineBits.SPEED)


@pytest.mark.parametrize("command,scope,label", SPEED_UPDATE_SCOPES)
@pytest.mark.parametrize("target_speed", [0, 45, 199], ids=["stopped", "cruising", "maximum"])
def test_incoming_speed_update_without_record_lookup_result(command, scope, label, target_speed, speed_update_lookups):
    reverse, forward = speed_update_lookups
    packet = incoming_speed_packet(command, b"\x34\x12", target_speed)

    parsed = PdiReq.from_bytes(packet)

    assert isinstance(parsed, BaseReq)
    assert parsed.pdi_command == command
    assert parsed.scope == scope
    assert parsed.target_speed == target_speed
    assert parsed.speed is None
    expected_body = bytes([command, 0x34, 0x12, target_speed])
    expected_packet_text = "0x" + expected_body.hex(" ").upper()
    assert parsed.payload == f"{label} #{parsed.tmcc_id} Target Speed: {target_speed} ({expected_packet_text})"
    assert parsed.as_bytes == packet
    reverse.assert_called_once_with(0x1234, scope)
    forward.assert_not_called()
    assert parsed.is_valid(EngineBits.TARGET_SPEED)
    assert not parsed.is_valid(EngineBits.SPEED)


@pytest.mark.parametrize(
    "command,scope,sent_packet,echo_packet",
    [
        pytest.param(
            PdiCommand.UPDATE_ENGINE_SPEED,
            CommandScope.ENGINE,
            b"\xd1\x2a\x07\x2d\xa2\xdf",
            b"\xd1\x2a\x07\xff\x2d\xa3\xdf",
            id="engine",
        ),
        pytest.param(
            PdiCommand.UPDATE_TRAIN_SPEED,
            CommandScope.TRAIN,
            b"\xd1\x2b\x07\x2d\xa1\xdf",
            b"\xd1\x2b\x07\xff\x2d\xa2\xdf",
            id="train",
        ),
    ],
)
def test_short_speed_send_and_marked_echo(command, scope, sent_packet, echo_packet, speed_update_lookups):
    reverse, forward = speed_update_lookups
    req = BaseReq.update_target_speed(address=7, speed=45, scope=scope)

    assert req.as_bytes == sent_packet
    assert req.pdi_command == command
    assert req.record_no == 7
    assert req.target_speed == 45
    assert outgoing_speed_packet(command, b"\x07", 45) == sent_packet
    assert incoming_speed_packet(command, b"\x07\xff", 45) == echo_packet
    assert sent_packet != echo_packet

    # Only the independently specified Base 3 echo belongs at the receive boundary.
    parsed = PdiReq.from_bytes(echo_packet)

    assert isinstance(parsed, BaseReq)
    assert parsed.pdi_command == command
    assert parsed.scope == scope
    assert parsed.tmcc_id == req.record_no
    assert parsed.target_speed == req.target_speed
    assert parsed.speed is None
    assert parsed.is_valid(EngineBits.TARGET_SPEED)
    assert not parsed.is_valid(EngineBits.SPEED)
    assert parsed.as_bytes == echo_packet
    reverse.assert_not_called()
    forward.assert_not_called()


def engine_memory_req(record: bytes, tmcc_id: int = 20) -> BaseReq:
    """
    A BASE_MEMORY engine record, serialized and parsed back, so the record makes the
    same trip over the wire it makes when the Base 3 answers a configuration request.
    """
    req = BaseReq(tmcc_id, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE, data_bytes=record)
    return cast(BaseReq, PdiReq.from_bytes(req.as_bytes))


@pytest.fixture
def sync_dispatch(monkeypatch):
    events = Mock()
    thread = Mock()
    monkeypatch.setattr(Base3DbRefreshManager, "request_refresh", events.refresh)
    monkeypatch.setattr("src.pytrain.pdi.base_req.Thread", thread)
    return events, thread


@pytest.mark.parametrize("do_async", [False, True])
def test_process_sync_reqs_preserves_mixed_dispatch_order(do_async, sync_dispatch):
    events, thread = sync_dispatch
    first = BaseReq(7, cast(PdiCommand, PdiCommand.BASE_ENGINE))
    second = D4Req(0x1234, cast(PdiCommand, PdiCommand.D4_ENGINE), D4Action.QUERY)
    engine = ComponentStateDict(CommandScope.ENGINE)[7]
    route = ComponentStateDict(CommandScope.ROUTE)[3]
    assert isinstance(route, RouteState)

    def start_thread(**kwargs):
        worker = Mock()
        worker.start.side_effect = lambda: kwargs["target"](*kwargs["args"])
        return worker

    thread.side_effect = start_thread
    assert BaseReq.process_sync_reqs((first, engine, second, route), events.send, do_async) is True
    assert events.mock_calls == [call.send(first), call.refresh(engine), call.send(second), call.refresh(route)]
    if do_async:
        assert thread.call_args_list == [
            call(target=events.send, args=(first,), daemon=True),
            call(target=events.send, args=(second,), daemon=True),
        ]
    else:
        thread.assert_not_called()


@pytest.mark.parametrize("do_async", [False, True])
def test_process_sync_reqs_empty_input(do_async, sync_dispatch):
    events, thread = sync_dispatch
    assert BaseReq.process_sync_reqs([], events.send, do_async) is False
    assert events.mock_calls == []
    thread.assert_not_called()


@pytest.fixture(params=[CommandScope.ENGINE, CommandScope.TRAIN])
def initialized_update_state(request):
    def create(address: int) -> EngineState:
        state = ComponentStateDict(request.param)[address]
        assert isinstance(state, EngineState)
        state.initialize(request.param, address)
        # Seed the Base's mapping without starting discovery or a hardware connection.
        # noinspection PyProtectedMember
        state._d4_rec_no = 0x1234  # noqa: SLF001
        return state

    return create


@pytest.fixture(params=[pytest.param(TMCC_CONTROL_TYPE, id="tmcc"), pytest.param(LEGACY_CONTROL_TYPE, id="legacy")])
def native_speed_state(request, initialized_update_state, outbound_speed_lookups, sync_dispatch, monkeypatch):
    forward, reverse = outbound_speed_lookups
    # Route lookups to the mocked get_state while exercising real conversion and filtering.
    monkeypatch.setattr(CompData, "state_store", Mock(return_value=ComponentStateStore))
    build = Mock(side_effect=AssertionError("Speed conversion must not create the state store"))
    sent = Mock(side_effect=AssertionError("Speed conversion must not send requests"))
    monkeypatch.setattr(ComponentStateStore, "build", build)
    monkeypatch.setattr(PdiReq, "send", sent)
    state = initialized_update_state(7)
    assert isinstance(state.comp_data, EngineData)
    state.comp_data.control_type = request.param
    state.comp_data.speed = 0x13
    state.comp_data.target_speed = 0xC7
    assert state.is_legacy is (request.param == LEGACY_CONTROL_TYPE)
    assert state.speed_max == (199 if state.is_legacy else 31)
    forward.return_value = state

    yield state

    reverse.assert_not_called()
    build.assert_not_called()
    sent.assert_not_called()
    events, thread = sync_dispatch
    assert events.mock_calls == []
    thread.assert_not_called()


@pytest.mark.parametrize("address", [7, 3180])
@pytest.mark.parametrize("ending", ["release", "expiration"])
def test_remote_claim_preserves_command_targets(
    native_speed_state, initialized_update_state, outbound_speed_lookups, monkeypatch, address, ending
):
    state: EngineState = native_speed_state if address == 7 else initialized_update_state(address)
    assert isinstance(state.comp_data, EngineData)
    if address > 99:
        state.comp_data.control_type = LEGACY_CONTROL_TYPE
    command_type = TMCC2EngineCommandEnum.ABSOLUTE_SPEED if state.is_legacy else TMCC1EngineCommandEnum.ABSOLUTE_SPEED
    speed = 45 if state.is_legacy else 7
    forward, _ = outbound_speed_lookups
    other_scope = CommandScope.TRAIN if state.scope == CommandScope.ENGINE else CommandScope.ENGINE
    other = ComponentStateDict(other_scope)[address]
    assert isinstance(other, EngineState)
    other.initialize(other_scope, address)
    other.comp_data.control_type = LEGACY_CONTROL_TYPE if state.is_legacy else TMCC_CONTROL_TYPE
    neighbor = initialized_update_state(8)
    neighbor.comp_data.control_type = LEGACY_CONTROL_TYPE if state.is_legacy else TMCC_CONTROL_TYPE
    states = {(item.scope, item.tmcc_id): item for item in (state, other, neighbor)}
    forward.side_effect = lambda scope, tmcc_id, create=False: states.get((scope, tmcc_id))
    clock = Mock(return_value=100.0)
    monkeypatch.setattr("src.pytrain.db.engine_state.monotonic", clock)
    owner = RampClaim(state.scope, address, "127.0.0.1", 50000, 1, 1_800_000_000_001)
    req = CommandReq.build(command_type, address, data=speed, scope=state.scope)

    def check_updates(command, target_state, active):
        requests = BaseReq.update_eng(command)
        assert target_state.is_ramp_active is active
        has_refresh_marker = not active
        assert (requests[-1] is target_state) is has_refresh_marker
        updates: list[BaseReq | D4Req] = []
        for item in requests[:-1] if has_refresh_marker else requests:
            assert isinstance(item, (BaseReq, D4Req))
            updates.append(item)
        memory = [
            item
            for item in updates
            if item.pdi_command not in {PdiCommand.UPDATE_ENGINE_SPEED, PdiCommand.UPDATE_TRAIN_SPEED}
        ]
        assert [item.start for item in memory] == ([0x07] if active else [0x07, 0x08])
        for item in memory:
            assert item.scope == target_state.scope
            assert item.data_length == 1
            if target_state.tmcc_id > 99:
                assert isinstance(item, D4Req)
                assert item.action == D4Action.UPDATE
                assert item.record_no == 0x1234
                # D4Req has no public accessor for the outgoing memory payload.
                # noinspection PyProtectedMember
                assert item._data_bytes == b"\x2d"
            else:
                assert isinstance(item, BaseReq)
                assert item.data_bytes == b"\x2d"
                assert item.tmcc_id == target_state.tmcc_id
        injections = [
            item._target_speed_update for item in memory if getattr(item, "_target_speed_update", None) is not None
        ]
        if active or target_state.tmcc_id > 99:
            assert injections == []
        else:
            expected = (
                PdiCommand.UPDATE_ENGINE_SPEED
                if target_state.scope == CommandScope.ENGINE
                else PdiCommand.UPDATE_TRAIN_SPEED
            )
            assert [item.pdi_command for item in injections] == [expected]
            native = injections[0]
            assert isinstance(native, BaseReq)
            assert native.target_speed == speed

    check_updates(req, state, False)
    state.update(CommandReq.from_bytes(owner.request().as_bytes))
    assert state.ramp is None
    assert state.is_ramping is False
    assert state.is_remote_ramping is True
    check_updates(req, state, True)
    for unaffected in (neighbor, other):
        unaffected_address = unaffected.tmcc_id
        assert isinstance(unaffected_address, int)
        if unaffected is other and address > 99:
            # Seed the mapping directly to avoid hardware discovery for the other scope.
            # noinspection PyProtectedMember
            unaffected._d4_rec_no = 0x1234
        check_updates(
            CommandReq.build(command_type, unaffected_address, data=speed, scope=unaffected.scope), unaffected, False
        )

    for field, offsets in (("ABSOLUTE_SPEED", [0x07, 0x08]), ("RAMP_TARGET_SPEED", [0x08])):
        packages = CompData.field_to_updates(field, address, state.scope, speed, state.is_legacy)
        assert [package.offset for package in packages] == offsets
        assert all(package.data_bytes == b"\x2d" for package in packages)
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    explicit = BaseReq.do_update_field("RAMP_TARGET_SPEED", speed, state)
    assert state.is_ramp_active is True
    assert explicit[-1] is not state
    assert any(isinstance(item, (BaseReq, D4Req)) and item.start == 0x08 for item in explicit)
    dispatch.assert_called_once()
    assert BaseReq.update_target_speed(address=7, scope=state.scope, speed=45).target_speed == 45

    if ending == "release":
        state.update(CommandReq.from_bytes(owner.request(release=True).as_bytes))
    else:
        clock.return_value += CLAIM_TTL + 1
    assert state.is_ramp_active is False
    check_updates(req, state, False)


@pytest.mark.parametrize(
    "data_bytes,tmcc_speed,tmcc_packets,legacy_speed,legacy_packets",
    [
        pytest.param(
            b"\x2d",
            7,
            (b"\xd1\x2a\x07\x07\xc8\xdf", b"\xd1\x2b\x07\x07\xc7\xdf"),
            45,
            (b"\xd1\x2a\x07\x2d\xa2\xdf", b"\xd1\x2b\x07\x2d\xa1\xdf"),
            id="cruising",
        ),
        pytest.param(
            b"\xc7",
            31,
            (b"\xd1\x2a\x07\x1f\xb0\xdf", b"\xd1\x2b\x07\x1f\xaf\xdf"),
            199,
            (b"\xd1\x2a\x07\xc7\x08\xdf", b"\xd1\x2b\x07\xc7\x07\xdf"),
            id="maximum",
        ),
    ],
)
def test_absolute_speed_updates_follow_ramp_lifecycle(
    data_bytes,
    tmcc_speed,
    tmcc_packets,
    legacy_speed,
    legacy_packets,
    native_speed_state: EngineState,
    outbound_speed_lookups,
):
    """Real conversion suppresses only target writes during ramps, including at maximum speed."""
    state = native_speed_state
    command = TMCC2EngineCommandEnum.ABSOLUTE_SPEED if state.is_legacy else TMCC1EngineCommandEnum.ABSOLUTE_SPEED
    speed = legacy_speed if state.is_legacy else tmcc_speed
    packets = legacy_packets if state.is_legacy else tmcc_packets
    packet_index = 0 if state.scope == CommandScope.ENGINE else 1
    req = CommandReq.build(command, 7, data=speed, scope=state.scope)
    native_command = (
        PdiCommand.UPDATE_ENGINE_SPEED if state.scope == CommandScope.ENGINE else PdiCommand.UPDATE_TRAIN_SPEED
    )
    forward, _ = outbound_speed_lookups

    # Reusing the same command also catches accidental mutation of the shared update map.
    for is_ramping in (False, True, False):
        state.is_ramping = is_ramping
        forward.reset_mock()

        reqs = BaseReq.update_eng(req)

        assert state.is_ramp_active is is_ramping
        has_refresh_marker = not is_ramping
        assert (reqs[-1] is state) is has_refresh_marker
        updates: list[BaseReq] = []
        for update in reqs[:-1] if has_refresh_marker else reqs:
            assert isinstance(update, BaseReq)
            updates.append(update)
        expected_commands = [PdiCommand.BASE_MEMORY]
        if not is_ramping:
            expected_commands.append(PdiCommand.BASE_MEMORY)
        assert [update.pdi_command for update in updates] == expected_commands
        memory_updates = [update for update in updates if update.pdi_command == PdiCommand.BASE_MEMORY]
        assert [(update.start, update.data_length, update.data_bytes) for update in memory_updates] == (
            [(0x07, 1, data_bytes)] if is_ramping else [(0x07, 1, data_bytes), (0x08, 1, data_bytes)]
        )
        for update in memory_updates:
            assert update.tmcc_id == 7
            assert update.scope == state.scope
            assert update.flags == 0xC2
        if not is_ramping:
            native = updates[1]._target_speed_update
            assert native.pdi_command == native_command
            assert isinstance(native, BaseReq)
            assert native.record_no == 7
            assert native.target_speed == speed
            assert native.speed is None
            assert native.as_bytes == packets[packet_index]
        assert forward.call_args_list == [call(state.scope, 7, False), call(state.scope, 7, create=False)]
        # Request generation must not change local speed, target, or ramp state.
        assert state.speed == (19 if state.is_legacy else 3)
        assert state.target_speed == (199 if state.is_legacy else 31)
        assert state.is_ramping is is_ramping


@pytest.mark.parametrize(
    "data_bytes,tmcc_speed,tmcc_packets,legacy_speed,legacy_packets",
    [
        pytest.param(
            b"\x00",
            0,
            (b"\xd1\x2a\x07\x00\xcf\xdf", b"\xd1\x2b\x07\x00\xce\xdf"),
            0,
            (b"\xd1\x2a\x07\x00\xcf\xdf", b"\xd1\x2b\x07\x00\xce\xdf"),
            id="stopped",
        ),
        pytest.param(
            b"\x2d",
            7,
            (b"\xd1\x2a\x07\x07\xc8\xdf", b"\xd1\x2b\x07\x07\xc7\xdf"),
            45,
            (b"\xd1\x2a\x07\x2d\xa2\xdf", b"\xd1\x2b\x07\x2d\xa1\xdf"),
            id="cruising",
        ),
        pytest.param(
            b"\xc7",
            31,
            (b"\xd1\x2a\x07\x1f\xb0\xdf", b"\xd1\x2b\x07\x1f\xaf\xdf"),
            199,
            (b"\xd1\x2a\x07\xc7\x08\xdf", b"\xd1\x2b\x07\xc7\x07\xdf"),
            id="maximum",
        ),
    ],
)
def test_updates_to_reqs_converts_native_target_to_engine_speed_scale(
    data_bytes,
    tmcc_speed,
    tmcc_packets,
    legacy_speed,
    legacy_packets,
    native_speed_state: EngineState,
    outbound_speed_lookups,
):
    """updates_to_reqs emits engine-scale native targets and database-scale memory writes.

    This is specific to updates_to_reqs; SpeedRamp broadcasts database-scale targets.
    """
    state = native_speed_state
    expected_speed = legacy_speed if state.is_legacy else tmcc_speed
    packets = legacy_packets if state.is_legacy else tmcc_packets
    packet_index = 0 if state.scope == CommandScope.ENGINE else 1
    expected_command = (
        PdiCommand.UPDATE_ENGINE_SPEED if state.scope == CommandScope.ENGINE else PdiCommand.UPDATE_TRAIN_SPEED
    )

    reqs = BaseReq.updates_to_reqs(state, [UpdatePkg("target_speed", 0x08, 1, data_bytes)], refresh=False)

    assert len(reqs) == 1
    memory = reqs[0]
    native = memory._target_speed_update
    assert isinstance(native, BaseReq)
    # Constructed native requests carry scope in the command and address in record_no.
    assert native.pdi_command == expected_command
    assert native.record_no == 7
    assert native.target_speed == expected_speed
    assert 0 <= native.target_speed <= (199 if state.is_legacy else 31)
    assert native.speed is None
    assert native.as_bytes == packets[packet_index]
    assert isinstance(memory, BaseReq)
    assert memory.pdi_command == PdiCommand.BASE_MEMORY
    assert memory.scope == state.scope
    assert memory.tmcc_id == 7
    assert memory.flags == 0xC2
    assert (memory.start, memory.data_length, memory.data_bytes) == (0x08, 1, data_bytes)
    forward, _ = outbound_speed_lookups
    forward.assert_not_called()


@pytest.mark.parametrize("address", [7, 100, 1234])
@pytest.mark.parametrize("refresh", [False, True])
def test_updates_to_reqs_preserves_requests_and_refresh_marker(
    address, refresh, initialized_update_state, sync_dispatch
):
    state = initialized_update_state(address)
    packages = [UpdatePkg("speed", 7, 1, b"\x2d"), UpdatePkg("momentum", 24, 1, b"\x03")]
    reqs = BaseReq.updates_to_reqs(state, packages, refresh=refresh)
    assert len(reqs) == 2 + int(refresh)
    for req, pkg in zip(reqs[:2], packages):
        if address <= 100:
            assert isinstance(req, BaseReq)
            expected = BaseReq(
                address,
                PdiCommand.BASE_MEMORY,
                flags=0xC2,
                scope=state.scope,
                start=pkg.offset,
                data_length=pkg.length,
                data_bytes=pkg.data_bytes,
            )
        else:
            assert isinstance(req, D4Req)
            command = PdiCommand.D4_ENGINE if state.scope == CommandScope.ENGINE else PdiCommand.D4_TRAIN
            expected = D4Req(
                0x1234,
                cast(PdiCommand, command),
                D4Action.UPDATE,
                start=pkg.offset,
                data_length=pkg.length,
                data_bytes=pkg.data_bytes,
            )
        assert req.as_bytes == expected.as_bytes
    if refresh:
        assert reqs[-1] is state
    events, thread = sync_dispatch
    assert BaseReq.process_sync_reqs(reqs, events.send) is refresh
    assert events.send.call_args_list == [call(reqs[0]), call(reqs[1])]
    assert events.refresh.call_args_list == ([call(state)] if refresh else [])
    thread.assert_not_called()
    assert BaseReq.updates_to_reqs(state, [], refresh=refresh) == []


@pytest.fixture
def isolated_db_write_history():
    # This test checks each entry point independently, not suppression across calls.
    with base_req_module._write_dedup_lock:
        base_req_module._recent_db_writes.clear()
    yield
    with base_req_module._write_dedup_lock:
        base_req_module._recent_db_writes.clear()


@pytest.mark.parametrize("address", [7, 1234])
@pytest.mark.parametrize("entry_point", ["update_eng", "do_update_eng", "do_update_field"])
def test_initialized_update_paths_preserve_mixed_results(
    address, entry_point, initialized_update_state, sync_dispatch, monkeypatch, isolated_db_write_history
):
    state = initialized_update_state(address)
    package = UpdatePkg("speed", 7, 1, b"\x2d")
    lookup = Mock(return_value=state)
    monkeypatch.setattr(ComponentStateStore, "get_state", lookup)
    monkeypatch.setattr(CompData, "request_to_updates", Mock(return_value=[package]))
    monkeypatch.setattr(CompData, "field_to_updates", Mock(return_value=[package]))
    sent = Mock()
    monkeypatch.setattr(PdiReq, "send", sent)
    command = CommandReq(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, address, data=45, scope=state.scope)
    if entry_point == "do_update_field":
        reqs = BaseReq.do_update_field("speed", 45, state, do_async=False)
        lookup.assert_not_called()
    else:
        reqs = getattr(BaseReq, entry_point)(command)
        lookup.assert_called_once_with(state.scope, address, False)
    assert len(reqs) == 2
    assert isinstance(reqs[0], BaseReq if address < 100 else D4Req)
    assert reqs[-1] is state
    events, thread = sync_dispatch
    if entry_point == "update_eng":
        sent.assert_not_called()
        events.refresh.assert_not_called()
    else:
        sent.assert_called_once_with()
        events.refresh.assert_called_once_with(state)
    thread.assert_not_called()


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


@pytest.mark.parametrize(
    "rate,expected",
    [(None, 9), (0.0, 1), (0.24, 1), (0.25, 2), (1.0, 5), (1.75, 8), (2.0, 9), (-0.1, 9), (2.25, 9)],
)
def test_encode_throw_rate_defaults_and_mapped_values(rate, expected):
    assert BaseReq.encode_throw_rate(rate) == expected


def numeric_record_req(command: PdiCommand, values: dict[int, int]) -> BaseReq:
    """Parse an independent record, omitting numeric fields when no values are supplied."""
    inner = bytearray(69 if values else 61)
    inner[0] = command.value
    inner[1] = 7
    for offset, value in values.items():
        inner[offset] = value
    # The checksum helper frames the independent record for the public parser.
    # noinspection PyProtectedMember
    stuffed, checksum = PdiReq._calculate_checksum(bytes(inner))  # noqa: SLF001
    return BaseReq(bytes([PDI_SOP]) + stuffed + checksum + bytes([PDI_EOP]))


@pytest.mark.parametrize("command", [PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN])
@pytest.mark.parametrize(
    "brake,momentum,expected_brake,expected_momentum",
    [
        (None, None, None, None),
        (0, 0, 0, 0),
        (1, 9, 0, 0),
        (2, 10, 1, 1),
        (7, 63, 3, 3),
        (15, 127, 7, 7),
        (255, 255, 7, 7),
    ],
)
def test_parsed_numeric_conversions(command: PdiCommand, brake, momentum, expected_brake, expected_momentum):
    values = {}
    if brake is not None:
        assert momentum is not None
        values = {67: brake, 68: momentum}
    req = numeric_record_req(command, values)

    assert req.train_brake == brake
    assert req.momentum == momentum
    assert req.train_brake_tmcc == expected_brake
    assert req.momentum_tmcc == expected_momentum


@pytest.mark.parametrize("command", [PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN])
@pytest.mark.parametrize("level,percentage", [(None, None), (0, "0.00%"), (128, "50.20%"), (255, "100.00%")])
def test_parsed_fuel_and_water_display(command: PdiCommand, level, percentage):
    req = numeric_record_req(command, {} if level is None else {61: level, 62: level})

    if level is None:
        assert " Fuel:" not in req.payload
        assert " Water:" not in req.payload
    else:
        assert f" Fuel: {percentage} Water: {percentage}" in req.payload


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
    # Packet contains tmcc_id value 20 somewhere after command bytes; not strict index-assert to avoid brittle tests.
    assert 20 in pkt


@pytest.fixture
def outbound_speed_lookups(monkeypatch):
    forward = Mock()
    reverse = Mock()
    monkeypatch.setattr(ComponentStateStore, "get_state", forward)
    monkeypatch.setattr(ComponentStateStore, "by_record_no", reverse)
    return forward, reverse


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN], ids=["engine", "train"])
@pytest.mark.parametrize("address", [100, 9999], ids=["first-record-address", "maximum-address"])
@pytest.mark.parametrize(
    "state",
    [
        pytest.param(None, id="missing-state"),
        pytest.param(SimpleNamespace(is_d4=False, record_no=0x1234), id="non-d4-state"),
    ],
)
def test_outbound_speed_update_rejects_missing_d4_mapping(scope, address, state, outbound_speed_lookups):
    """Reject unmapped four-digit addresses before returning a packet."""
    forward, reverse = outbound_speed_lookups
    forward.return_value = state
    req = BaseReq.update_target_speed(address=address, speed=45, scope=scope)

    with pytest.raises(ValueError, match=rf"^Invalid record number {address}$"):
        _ = req.as_bytes

    forward.assert_called_once_with(scope, address, False)
    reverse.assert_not_called()


@pytest.mark.parametrize("command,scope,label", SPEED_UPDATE_SCOPES)
@pytest.mark.parametrize(
    "address,address_bytes,engine_target,engine_packet,train_packet",
    [
        pytest.param(7, b"\x07", 45, b"\xd1\x2a\x07\x2d\xa2\xdf", b"\xd1\x2b\x07\x2c\xa2\xdf", id="2d"),
        pytest.param(100, b"\x34\x12", 45, b"\xd1\x2a\x34\x12\x2d\x63\xdf", b"\xd1\x2b\x34\x12\x2c\x63\xdf", id="4d"),
        pytest.param(
            1, b"\x01", 4, b"\xd1\x2a\x01\x04\xde\xf3\xdf", b"\xd1\x2b\x01\x03\xde\xf3\xdf", id="checksum-sop"
        ),
        pytest.param(
            99, b"\x63", 149, b"\xd1\x2a\x63\x95\xde\x00\xdf", b"\xd1\x2b\x63\x94\xde\x00\xdf", id="checksum-stuff"
        ),
        pytest.param(
            99, b"\x63", 148, b"\xd1\x2a\x63\x94\xde\x01\xdf", b"\xd1\x2b\x63\x93\xde\x01\xdf", id="checksum-eop"
        ),
    ],
)
def test_outbound_speed_packet_matches_fixed_wire_examples(
    command, scope, label, address, address_bytes, engine_target, engine_packet, train_packet, outbound_speed_lookups
):
    # Offset the train command byte with a lower target to preserve the checksum stuffing class.
    target_speed = engine_target if scope == CommandScope.ENGINE else engine_target - 1
    expected = engine_packet if scope == CommandScope.ENGINE else train_packet
    assert outgoing_speed_packet(command, address_bytes, target_speed) == expected
    req = BaseReq.update_target_speed(address=address, speed=target_speed, scope=scope)
    assert_outbound_speed_packet(
        req, command, scope, label, address, address_bytes, target_speed, outbound_speed_lookups
    )


def assert_outbound_speed_packet(req, command, scope, label, address, address_bytes, target_speed, lookups):
    forward, reverse = lookups
    forward.return_value = SimpleNamespace(is_d4=True, record_no=0x1234, tmcc_id=address)
    expected = outgoing_speed_packet(command, address_bytes, target_speed)

    packet = req.as_bytes

    if address < 100:
        forward.assert_not_called()
    else:
        forward.assert_called_once_with(scope, address, False)
    reverse.assert_not_called()
    assert packet == expected
    assert packet[0] == PDI_SOP and packet[-1] == PDI_EOP
    assert req.pdi_command == command
    assert req.pdi_command.name == f"UPDATE_{label.upper()}_SPEED"
    assert req.record_no == address
    assert req.target_speed == target_speed


@pytest.mark.parametrize("command,scope,label", SPEED_UPDATE_SCOPES)
@pytest.mark.parametrize("address,address_bytes", OUTBOUND_SPEED_UPDATE_ADDRESSES)
@pytest.mark.parametrize("target_speed", [0, 45, 199], ids=["stopped", "cruising", "maximum"])
@pytest.mark.parametrize("use_factory", [True, False], ids=["factory", "distinct-current-speed"])
def test_outbound_speed_update_carries_target(
    command, scope, label, address, address_bytes, target_speed, use_factory, outbound_speed_lookups
):
    if use_factory:
        req = BaseReq.update_target_speed(address=address, speed=target_speed, scope=scope)
        assert req.speed is None
    else:
        req = BaseReq(address, command, scope=scope, speed=17, target_speed=target_speed)
        assert req.speed == 17
    assert req.pdi_command == command
    assert req.target_speed == target_speed
    assert_outbound_speed_packet(
        req, command, scope, label, address, address_bytes, target_speed, outbound_speed_lookups
    )


@pytest.mark.parametrize("address,address_bytes", OUTBOUND_SPEED_UPDATE_ADDRESSES)
@pytest.mark.parametrize("target_speed", [0, 45, 199], ids=["stopped", "cruising", "maximum"])
def test_outbound_speed_factory_defaults_to_engine(address, address_bytes, target_speed, outbound_speed_lookups):
    req = BaseReq.update_target_speed(address=address, speed=target_speed)

    assert req.pdi_command == PdiCommand.UPDATE_ENGINE_SPEED
    assert req.target_speed == target_speed
    assert_outbound_speed_packet(
        req,
        PdiCommand.UPDATE_ENGINE_SPEED,
        CommandScope.ENGINE,
        "Engine",
        address,
        address_bytes,
        target_speed,
        outbound_speed_lookups,
    )


@pytest.mark.parametrize(
    "address,engine_packet,train_packet",
    [
        pytest.param(7, b"\xd1\x2a\x07\x2d\xa2\xdf", b"\xd1\x2b\x07\x2d\xa1\xdf", id="2d"),
        pytest.param(100, b"\xd1\x2a\x34\x12\x2d\x63\xdf", b"\xd1\x2b\x34\x12\x2d\x62\xdf", id="4d"),
    ],
)
def test_update_speed_engine_and_train_encode_distinct(address, engine_packet, train_packet, outbound_speed_lookups):
    forward, reverse = outbound_speed_lookups
    forward.return_value = SimpleNamespace(is_d4=True, record_no=0x1234, tmcc_id=address)
    eng = BaseReq.update_target_speed(address=address, speed=45, scope=CommandScope.ENGINE)
    trn = BaseReq.update_target_speed(address=address, speed=45, scope=CommandScope.TRAIN)

    assert eng.pdi_command == PdiCommand.UPDATE_ENGINE_SPEED
    assert trn.pdi_command == PdiCommand.UPDATE_TRAIN_SPEED
    assert eng.target_speed == 45
    assert trn.target_speed == 45

    be = eng.as_bytes
    bt = trn.as_bytes
    assert be == engine_packet
    assert bt == train_packet
    reverse.assert_not_called()
    if address < 100:
        forward.assert_not_called()
    else:
        assert forward.call_count == 2
        forward.assert_any_call(CommandScope.ENGINE, address, False)
        forward.assert_any_call(CommandScope.TRAIN, address, False)
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


VALIDITY_FIELDS = [
    pytest.param(EngineBits.REVERSE_LINK, id="low-bit-0"),
    pytest.param(EngineBits.SPEED, id="low-speed-11"),
    pytest.param(EngineBits.MAX_SPEED, id="low-boundary-15"),
    pytest.param(EngineBits.FUEL_LEVEL, id="high-boundary-16"),
    pytest.param(EngineBits.TARGET_SPEED, id="high-target-24"),
]
VALIDITY_MASKS = [
    pytest.param(None, None, id="both-none"),
    pytest.param(0, 0, id="both-zero"),
    pytest.param(None, 0x42, id="low-none-high-populated"),
    pytest.param(0x124, None, id="low-populated-high-none"),
    pytest.param(0, 0x42, id="low-zero-high-populated"),
    pytest.param(0x124, 0, id="low-populated-high-zero"),
    pytest.param(0x124, 0x42, id="distinct-populated-words"),
]


def validity_mask_req(valid1: int | None, valid2: int | None) -> BaseReq:
    """Seed masks through the public parser, independently of the mutation helpers."""
    inner = cast(PdiCommand, PdiCommand.BASE_ENGINE).as_bytes + b"\x01\x00\x00\x00"
    inner += (valid1 or 0).to_bytes(2, "little") + (valid2 or 0).to_bytes(2, "little")
    inner += bytes(60)
    # The checksum helper frames the independently constructed base-record payload.
    # noinspection PyProtectedMember
    stuffed, checksum = BaseReq._calculate_checksum(inner)  # noqa: SLF001
    req = PdiReq.from_bytes(bytes([PDI_SOP]) + stuffed + checksum + bytes([PDI_EOP]))
    assert isinstance(req, BaseReq)
    # A complete wire record cannot represent None; seed only these missing words directly.
    if valid1 is None:
        # noinspection PyProtectedMember
        req._valid1 = None  # noqa: SLF001
    if valid2 is None:
        # noinspection PyProtectedMember
        req._valid2 = None  # noqa: SLF001
    assert (req.valid1, req.valid2) == (valid1, valid2)
    return req


@pytest.mark.parametrize("field", VALIDITY_FIELDS)
@pytest.mark.parametrize("valid1,valid2", VALIDITY_MASKS)
@pytest.mark.parametrize("already_set", [False, True], ids=["absent", "present"])
def test_set_valid_preserves_masks_and_is_idempotent(field, valid1, valid2, already_set):
    word = 0 if field.value < 16 else 1
    bit = 1 << (field.value if word == 0 else field.value - 16)
    initial = [valid1, valid2]
    if already_set:
        initial[word] = (initial[word] or 0) | bit
    req = validity_mask_req(*initial)
    expected = initial.copy()
    expected[word] = (expected[word] or 0) | bit

    for _ in range(2):
        # Direct access is required to test the validity helper's mutation contract.
        # noinspection PyProtectedMember
        req._set_valid(field)  # noqa: SLF001
        assert (req.valid1, req.valid2) == tuple(expected)
        assert req.is_valid(field)


@pytest.mark.parametrize("field", VALIDITY_FIELDS)
@pytest.mark.parametrize("valid1,valid2", VALIDITY_MASKS)
@pytest.mark.parametrize("already_set", [False, True], ids=["absent", "present"])
def test_clear_valid_preserves_masks_and_is_idempotent(field, valid1, valid2, already_set):
    word = 0 if field.value < 16 else 1
    bit = 1 << (field.value if word == 0 else field.value - 16)
    initial = [valid1, valid2]
    if already_set:
        initial[word] = (initial[word] or 0) | bit
    req = validity_mask_req(*initial)
    expected = initial.copy()
    expected[word] = (expected[word] or 0) & ~bit

    for _ in range(2):
        # Direct access is required to test the validity helper's mutation contract.
        # noinspection PyProtectedMember
        req._clear_valid(field)  # noqa: SLF001
        assert (req.valid1, req.valid2) == tuple(expected)
        assert not req.is_valid(field)


@pytest.mark.parametrize("field", VALIDITY_FIELDS)
@pytest.mark.parametrize("valid1,valid2", VALIDITY_MASKS)
def test_set_then_clear_valid_restores_unrelated_masks(field, valid1, valid2):
    req = validity_mask_req(valid1, valid2)
    word = 0 if field.value < 16 else 1
    bit = 1 << (field.value if word == 0 else field.value - 16)
    restored = [valid1, valid2]
    restored[word] = restored[word] or 0
    after_set = restored.copy()
    after_set[word] |= bit

    # Direct helper calls verify restoration, including normalization of only the selected word.
    # noinspection PyProtectedMember
    req._set_valid(field)  # noqa: SLF001
    assert (req.valid1, req.valid2) == tuple(after_set)
    assert req.is_valid(field)
    # noinspection PyProtectedMember
    req._clear_valid(field)  # noqa: SLF001
    assert (req.valid1, req.valid2) == tuple(restored)
    assert not req.is_valid(field)


@pytest.mark.parametrize("field", VALIDITY_FIELDS[:3])
@pytest.mark.parametrize("valid1", [None, 0], ids=["none", "zero"])
def test_is_valid_low_field_with_empty_low_word_and_populated_high_word(field, valid1):
    req = validity_mask_req(valid1, 0x142)

    assert not req.is_valid(field)
    assert req.is_valid(EngineBits.TARGET_SPEED)
    assert (req.valid1, req.valid2) == (valid1, 0x142)


def test_is_active_logic_for_empty_records_engine_like_fields():
    # Build a BASE_ENGINE-like packet with fwd/rev=255 and empty name/number, which should be inactive
    # Construct minimal packet bytes following BaseReq constructor parsing expectations.
    # We will craft: [SOP][cmd(2)][id][flags][status][spare][valid1(2)][valid2(2)]...[fwd=255][rev=255]...[EOP]
    # Easiest is to instantiate via constructor path that generates bytes for us, then tweak.
    req = BaseReq(1, cast(PdiCommand, PdiCommand.BASE_ENGINE))
    _ = bytearray(req.as_bytes)
    # Find indices for tmcc_id and after; conservative modifications:
    # Ensure name/number empty by forcing zeros and set fwd/rev to 255 at known positions for engine view
    # (indexes align with parsing code offsets)
    # The parser uses fixed offsets relative to inner buffer start; to simplify,
    # build a new object using bytes path with required fields populated directly.
    #
    # Create inner payload with required fields for BASE_ENGINE:
    inner = bytearray()
    inner += cast(PdiCommand, PdiCommand.BASE_ENGINE).as_bytes  # 2
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

    # The checksum helper is needed to frame this hand-built parser test packet.
    # noinspection PyProtectedMember
    stuffed, checksum = BaseReq._calculate_checksum(bytes(inner))  # noqa: SLF001
    pkt = bytes([PDI_SOP]) + stuffed + checksum + bytes([PDI_EOP])

    parsed = BaseReq(pkt)
    assert parsed.pdi_command == PdiCommand.BASE_ENGINE
    assert parsed.is_active is False


def test_a_populated_base_memory_record_does_not_report_itself_empty():
    record = bytearray(b"\xff" * PdiReq.scope_record_length(CommandScope.ENGINE))
    record[0x00] = record[0x01] = 0x00  # prev/next link
    record[0x1E] = 6
    record[0x1F : 0x1F + 6] = b"Pennsy"
    record[0x3E] = 4
    record[0x3F : 0x3F + 4] = b"1234"

    parsed = engine_memory_req(bytes(record))

    assert parsed.is_comp_data_record is True
    assert parsed.name == "Pennsy"
    assert parsed.number == "1234"
    assert parsed.is_comp_data_empty is False


def test_a_never_written_base_memory_record_reports_itself_empty():
    # a roster slot the base has never written: no road name or number, both links 255
    parsed = engine_memory_req(b"\xff" * PdiReq.scope_record_length(CommandScope.ENGINE))

    assert parsed.is_comp_data_record is True
    assert parsed.name is None
    assert parsed.number is None
    assert parsed.is_comp_data_empty is True


def test_as_key_tuple_shape_and_content_stability():
    req = BaseReq(5, PdiCommand.BASE_MEMORY, scope=CommandScope.TRAIN)
    k = req.as_key
    assert isinstance(k, tuple) and len(k) == 4
    # record_no and command should be stable
    assert k[0] == 5
    assert k[1] == PdiCommand.BASE_MEMORY


@pytest.mark.parametrize("address", [7, 1234])
def test_compdata_update_package_dedup_key_survives_request_conversion(
    address, initialized_update_state, isolated_db_write_history, monkeypatch
):
    """Exercise the real UpdatePkg -> BaseReq/D4Req -> deduplicating dispatch path."""
    state = initialized_update_state(address)
    pkg = UpdatePkg("speed", 0x07, 1, b"\x12")
    requests = BaseReq.updates_to_reqs(state, [pkg], refresh=False)
    assert len(requests) == 1
    req = requests[0]
    assert BaseReq._database_write_key(req) == (state.scope, address, pkg.offset, pkg.length, pkg.data_bytes)

    clock = [100.0]
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: clock[0])
    send = Mock()
    BaseReq.process_sync_reqs(requests, send, deduplicate_writes=True)
    BaseReq.process_sync_reqs(BaseReq.updates_to_reqs(state, [pkg], refresh=False), send, deduplicate_writes=True)
    assert send.call_count == 1

    changed = UpdatePkg("speed", 0x07, 1, b"\x13")
    BaseReq.process_sync_reqs(BaseReq.updates_to_reqs(state, [changed], refresh=False), send, deduplicate_writes=True)
    assert send.call_count == 2


@pytest.mark.parametrize(
    "rpm,labor,expected_byte",
    [
        pytest.param(0, 12, b"\x00", id="stopped"),
        pytest.param(2, 12, b"\x02", id="rpm-2"),
        pytest.param(2, 13, b"\x0a", id="rpm-2-labor-13"),
    ],
)
def test_rpm_labor_updates_generate_base_memory_write(rpm, labor, expected_byte, initialized_update_state):
    """RPM and labor share the single BASE_MEMORY byte at offset 0x0C."""
    state = initialized_update_state(60)
    encoded = bytes([encode_labor_rpm(rpm, labor)])
    assert encoded == expected_byte
    pkg = UpdatePkg("rpm_labor", 0x0C, 1, encoded)

    requests = BaseReq.updates_to_reqs(state, [pkg], refresh=False)

    assert len(requests) == 1
    request = requests[0]
    assert isinstance(request, BaseReq)
    assert request.pdi_command == PdiCommand.BASE_MEMORY
    assert request.flags == 0xC2
    assert BaseReq._database_write_key(request) == (state.scope, 60, 0x0C, 1, expected_byte)
    assert request.as_bytes.startswith(b"\xd1\x26\x3c\xc2")


def test_changed_rpm_labor_byte_is_not_deduplicated(monkeypatch, initialized_update_state, isolated_db_write_history):
    """A nonzero RPM change and subsequent labor change must both be sent inside 25 ms."""
    state = initialized_update_state(60)
    clock = [100.0]
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: clock[0])
    sent_packets = []

    def dispatch(rpm, labor):
        data = bytes([encode_labor_rpm(rpm, labor)])
        requests = BaseReq.updates_to_reqs(state, [UpdatePkg("rpm_labor", 0x0C, 1, data)], refresh=False)
        BaseReq.process_sync_reqs(requests, lambda req: sent_packets.append(req.as_bytes), deduplicate_writes=True)

    dispatch(0, 12)
    clock[0] += 0.005
    dispatch(2, 12)
    clock[0] += 0.005
    dispatch(2, 12)  # Identical byte is suppressed.
    clock[0] += 0.005
    dispatch(2, 13)  # Same offset, changed labor bits: must be sent.

    assert len(sent_packets) == 3
    assert [PdiReq.from_bytes(packet).data_bytes for packet in sent_packets] == [
        b"\x00",
        b"\x02",
        b"\x0a",
    ]


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_synthetic_target_update_follows_accepted_write_only(scope, isolated_db_write_history, monkeypatch):
    """The synthetic speed update is dispatched only with a non-suppressed 2D write."""
    state = SimpleNamespace(tmcc_id=60, scope=scope, is_legacy=True, is_ramp_active=False)
    clock = [100.0]
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: clock[0])
    sent = []

    def dispatch(value):
        reqs = BaseReq.updates_to_reqs(state, [UpdatePkg("target_speed", 0x08, 1, bytes([value]))], refresh=False)
        assert len(reqs) == 1
        BaseReq.process_sync_reqs(reqs, sent.append, deduplicate_writes=True)

    dispatch(0)
    assert [req.pdi_command for req in sent] == [
        PdiCommand.UPDATE_ENGINE_SPEED if scope == CommandScope.ENGINE else PdiCommand.UPDATE_TRAIN_SPEED,
        PdiCommand.BASE_MEMORY,
    ]
    assert sent[0].target_speed == 0

    clock[0] += 0.005
    dispatch(0)
    assert len(sent) == 2  # Both synthetic command and duplicate write are suppressed.

    clock[0] += 0.005
    dispatch(5)
    assert len(sent) == 4  # Changed target speed must never be suppressed.
    assert sent[2].target_speed == 5
    assert sent[3].data_bytes == bytes([5])

    clock[0] += base_req_module.BASE3_WRITE_DEDUP_SECONDS
    dispatch(5)
    assert len(sent) == 6  # Both commands are sent again after the window.


def test_non_target_database_write_has_no_synthetic_command(initialized_update_state, isolated_db_write_history):
    state = initialized_update_state(60)
    reqs = BaseReq.updates_to_reqs(state, [UpdatePkg("speed", 0x07, 1, bytes([16]))], refresh=False)
    sent = []
    BaseReq.process_sync_reqs(reqs, sent.append, deduplicate_writes=True)
    assert len(sent) == 1
    assert sent[0].pdi_command == PdiCommand.BASE_MEMORY
