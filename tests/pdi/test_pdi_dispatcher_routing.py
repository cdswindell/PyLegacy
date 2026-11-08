"""Verify the topics and forwarding selected for Base 3 packets."""

from collections.abc import Iterator
from unittest.mock import Mock, call

import pytest

from src.pytrain.comm.command_listener import SYNC_COMPLETE, CommandDispatcher
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.pdi.constants import (
    Amc2Action,
    Asc2Action,
    Bpc2Action,
    D4Action,
    IrdaAction,
    PdiCommand,
    Ser2Action,
    Stm2Action,
    WiFiAction,
)
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_listener import PdiDispatcher
from src.pytrain.pdi.pdi_req import PdiReq, TmccReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import BROADCAST_TOPIC, CREATE_TOPIC, DELETE_TOPIC, CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from tests.test_base import wait_until


def _wire(command: int, body: bytes = b"") -> bytes:
    # Use the framing helper to build incoming replies without invoking outgoing serializers.
    # noinspection PyProtectedMember
    stuffed, checksum = PdiReq._calculate_checksum(bytes([command]) + body)
    return b"\xd1" + stuffed + checksum + b"\xdf"


def _base_reply(command: PdiCommand, address: int, link: int = 0) -> bytes:
    return _wire(command, bytes([address, 2, 0, 0, 1, 0, 0, 0, link, link]))


def _addressed_topics(command, scope, address, action=None) -> tuple:
    return (command, action), (scope, address, action), command, (scope, address), scope


def _drain(dispatcher: PdiDispatcher) -> None:
    # Wait for task completion so negative assertions include the entire dispatch.
    # noinspection PyProtectedMember
    assert wait_until(lambda: dispatcher._queue.unfinished_tasks == 0), "Timed out draining the PDI dispatcher"


@pytest.fixture
def routing(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[PdiDispatcher, Mock]]:
    events = Mock()
    tmcc = Mock()
    tmcc.offer.side_effect = events.delegate
    # Use a fresh PDI singleton and keep the TMCC queue and client sockets out of the trace.
    monkeypatch.setattr(PdiDispatcher, "_instance", None)
    monkeypatch.setattr(PdiDispatcher, "is_server", property(lambda _: False))
    monkeypatch.setattr(CommandDispatcher, "build", Mock(return_value=tmcc))
    monkeypatch.setattr(CommandDispatcher, "get", Mock(return_value=tmcc))
    monkeypatch.setattr(ComponentStateStore, "get_state", Mock(return_value=None))
    dispatcher = PdiDispatcher.build()
    events.publish.side_effect = dispatcher.publish
    monkeypatch.setattr(dispatcher, "publish", events.publish)
    monkeypatch.setattr(dispatcher, "update_client_state", events.forward)
    try:
        yield dispatcher, events
    finally:
        dispatcher.shutdown()
        dispatcher.join(timeout=5)
        assert not dispatcher.is_alive()


@pytest.mark.parametrize(
    ("command", "action", "scope"),
    [
        (PdiCommand.ASC2_RX, Asc2Action.CONTROL4, CommandScope.SWITCH),
        (PdiCommand.AMC2_RX, Amc2Action.MOTOR, CommandScope.ACC),
        (PdiCommand.BPC2_RX, Bpc2Action.CONTROL3, CommandScope.ACC),
        (PdiCommand.STM2_RX, Stm2Action.CONTROL1, CommandScope.SWITCH),
        (PdiCommand.IRDA_RX, IrdaAction.STATUS, CommandScope.IRDA),
        (PdiCommand.SER2_RX, Ser2Action.STATUS, CommandScope.SYSTEM),
        (PdiCommand.WIFI_RX, WiFiAction.STATUS, CommandScope.SYSTEM),
    ],
)
@pytest.mark.parametrize("address", [0, 7])
@pytest.mark.parametrize("is_server", [False, True], ids=["client", "server"])
def test_device_replies_publish_the_expected_topics(monkeypatch, routing, command, action, scope, address, is_server):
    dispatcher, events = routing
    monkeypatch.setattr(PdiDispatcher, "is_server", property(lambda _: is_server))
    action_byte = action.bits
    assert action_byte is not None
    packet = _wire(command, bytes([address, action_byte]) + bytes(24))
    request = PdiReq.from_bytes(packet)
    dispatcher.subscribe(events.action_received, command, action=action)
    expected = [call.publish((command, action), request), call.action_received(request)]
    if address:
        dispatcher.subscribe(events.scoped_action_received, scope, address, action)
        expected.extend(
            [
                call.publish((scope, address, action), request),
                call.scoped_action_received(request),
                call.publish(command, request),
                call.publish((scope, address), request),
                call.publish(scope, request),
            ]
        )
    if is_server and address:
        expected.append(call.forward(request))

    dispatcher.offer(packet)
    _drain(dispatcher)

    assert events.mock_calls == expected


@pytest.mark.parametrize(
    ("packet", "topics", "forward"),
    [
        pytest.param(
            _base_reply(PdiCommand.BASE, 0),
            _addressed_topics(PdiCommand.BASE, CommandScope.BASE, 0),
            True,
            id="base-status-id-zero",
        ),
        pytest.param(
            _base_reply(PdiCommand.BASE_SWITCH, 7),
            _addressed_topics(PdiCommand.BASE_SWITCH, CommandScope.SWITCH, 7),
            True,
            id="base-switch",
        ),
        pytest.param(
            _base_reply(PdiCommand.BASE_ENGINE, 100),
            (),
            True,
            id="base-id-100",
        ),
        pytest.param(
            D4Req(0, PdiCommand.D4_ENGINE, D4Action.MAP, tmcc_id=100).as_bytes,
            _addressed_topics(PdiCommand.D4_ENGINE, CommandScope.ENGINE, 100, D4Action.MAP),
            True,
            id="d4-id-100",
        ),
        pytest.param(
            _wire(PdiCommand.BLOCK_RX, b"\x07\0\0\x01\0\0"),
            _addressed_topics(PdiCommand.BLOCK_RX, CommandScope.BLOCK, 7),
            True,
            id="block-occupancy",
        ),
        pytest.param(
            bytes.fromhex("d12b07ff2da2df"),
            _addressed_topics(PdiCommand.UPDATE_TRAIN_SPEED, CommandScope.TRAIN, 7),
            True,
            id="train-speed",
        ),
        pytest.param(
            _wire(PdiCommand.D4_TRAIN, b"\0\0" + D4Action.FIRST_REC.as_bytes + b"\0"),
            ((PdiCommand.D4_TRAIN, D4Action.FIRST_REC),),
            False,
            id="addressless-d4-action",
        ),
        pytest.param(_wire(PdiCommand.ALL_GET), (PdiCommand.ALL_GET,), False, id="addressless-no-action"),
        pytest.param(
            bytes.fromhex("d1760012000030373337a7df"),
            _addressed_topics(PdiCommand.BLE_RX, CommandScope.ENGINE, 737),
            True,
            id="addressed-ble",
        ),
        pytest.param(bytes.fromhex("d1760212ffff78df"), (PdiCommand.BLE_RX,), True, id="addressless-ble"),
    ],
)
@pytest.mark.parametrize("broadcast", [False, True], ids=["no-broadcast", "broadcast"])
@pytest.mark.parametrize("create", [False, True], ids=["no-create", "create"])
def test_broadcast_and_create_topics_preserve_packet_routing(
    monkeypatch, routing, packet, topics, forward, broadcast, create
):
    dispatcher, events = routing
    monkeypatch.setattr(PdiDispatcher, "is_server", property(lambda _: True))
    if broadcast:
        dispatcher.subscribe_any(events.broadcast_received)
    if create:
        dispatcher.subscribe_create(events.create_received)
    request = PdiReq.from_bytes(packet)

    dispatcher.offer(packet)
    _drain(dispatcher)

    expected = []
    if broadcast:
        expected.extend([call.publish(BROADCAST_TOPIC, request), call.broadcast_received(request)])
    if create and request.command == PdiCommand.BLE_RX:
        expected.extend([call.publish(CREATE_TOPIC, request), call.create_received(request)])
    expected.extend(call.publish(topic, request) for topic in topics)
    if forward:
        expected.append(call.forward(request))
    assert events.mock_calls == expected


@pytest.mark.parametrize(
    "packet",
    [
        pytest.param(D4Req(3, PdiCommand.D4_ENGINE, D4Action.CLEAR).as_bytes, id="d4-clear"),
        pytest.param(_base_reply(PdiCommand.BASE_ENGINE, 7, link=255), id="inactive-base-record"),
    ],
)
@pytest.mark.parametrize("is_server", [False, True], ids=["client", "server"])
@pytest.mark.parametrize("subscribe", [False, True], ids=["no-delete", "delete"])
@pytest.mark.parametrize("state_status", ["active", "deleted", "missing", "protected"])
def test_deletion_publishes_only_eligible_state(monkeypatch, routing, packet, is_server, subscribe, state_status):
    dispatcher, events = routing
    monkeypatch.setattr(PdiDispatcher, "is_server", property(lambda _: is_server))
    state = Mock(is_deleted=state_status == "deleted", is_deletable=state_status != "protected")
    state.clear.side_effect = events.clear_state
    lookup_result = None if state_status == "missing" else state
    by_id = Mock(return_value=lookup_result)
    by_record = Mock(return_value=lookup_result)
    monkeypatch.setattr(ComponentStateStore, "get_state", by_id)
    monkeypatch.setattr(ComponentStateStore, "by_record_no", by_record)
    dispatcher.subscribe_any(events.broadcast_received)
    if subscribe:
        dispatcher.subscribe_delete(events.delete_received)
    request = PdiReq.from_bytes(packet)

    dispatcher.offer(packet)
    _drain(dispatcher)

    if isinstance(request, D4Req):
        by_record.assert_called_once_with(3, CommandScope.ENGINE)
        by_id.assert_not_called()
    else:
        by_id.assert_called_once_with(CommandScope.ENGINE, 7, create=False)
        by_record.assert_not_called()
    expected = [call.publish(BROADCAST_TOPIC, request), call.broadcast_received(request)]
    if state_status == "active":
        expected.append(call.clear_state())
        if subscribe:
            expected.extend([call.publish(DELETE_TOPIC, state), call.delete_received(state)])
    if is_server:
        expected.append(call.forward(request))
    assert events.mock_calls == expected


@pytest.mark.parametrize(
    ("command", "packet_type", "address"),
    [
        (TMCC1SwitchCommandEnum.THRU, PdiCommand.TMCC_RX, 7),
        (TMCC2EngineCommandEnum.FORWARD_DIRECTION, PdiCommand.TMCC4_RX, 737),
    ],
)
def test_tmcc_packets_broadcast_then_delegate(monkeypatch, routing, command, packet_type, address):
    dispatcher, events = routing
    monkeypatch.setattr(PdiDispatcher, "is_server", property(lambda _: True))
    dispatcher.subscribe_any(events.broadcast_received)
    packet = TmccReq(CommandReq.build(command, address), packet_type).as_bytes
    request = TmccReq(packet)

    dispatcher.offer(packet)
    _drain(dispatcher)

    assert events.mock_calls == [
        call.publish(BROADCAST_TOPIC, request),
        call.broadcast_received(request),
        call.delegate(request.tmcc_command, from_pdi=True),
    ]


def test_base_train_98_signals_sync_before_publishing_scoped_topics(routing):
    dispatcher, events = routing
    dispatcher.subscribe_any(events.broadcast_received)
    packet = _base_reply(PdiCommand.BASE_TRAIN, 98)
    request = PdiReq.from_bytes(packet)

    dispatcher.offer(packet)
    _drain(dispatcher)

    topics = _addressed_topics(PdiCommand.BASE_TRAIN, CommandScope.TRAIN, 98)
    assert events.mock_calls == [
        call.publish(BROADCAST_TOPIC, request),
        call.broadcast_received(request),
        call.delegate(SYNC_COMPLETE),
        *(call.publish(topic, request) for topic in topics),
    ]


@pytest.mark.parametrize(
    "packet",
    [_wire(PdiCommand.PING), _wire(PdiCommand.BASE_ENGINE, b"\x07\x02\x00")],
    ids=["ping", "base-ack"],
)
def test_ping_and_ack_publish_nothing(monkeypatch, routing, packet):
    dispatcher, events = routing
    monkeypatch.setattr(PdiDispatcher, "is_server", property(lambda _: True))
    dispatcher.subscribe_any(events.broadcast_received)

    dispatcher.offer(packet)
    _drain(dispatcher)

    assert events.mock_calls == []
