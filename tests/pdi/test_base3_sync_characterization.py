"""Characterize Base3Buffer synchronization before consolidating its dispatch path.

These tests intentionally assert the existing EngineState-only refresh behavior.
No sockets, serial ports, or background threads are started.
"""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from src.pytrain.comm.command_listener import CommandDispatcher
from src.pytrain.db.engine_state import EngineState, TrainState
from src.pytrain.pdi.base3_buffer import Base3Buffer
from src.pytrain.pdi.base3_db_refresh_manager import Base3DbRefreshManager
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.fixture
def sync_harness(monkeypatch):
    sent = Mock()
    refresh = Mock()
    update = Mock()
    monkeypatch.setattr(Base3Buffer, "_instance", SimpleNamespace(send=sent))
    monkeypatch.setattr(Base3DbRefreshManager, "request_refresh", refresh)
    monkeypatch.setattr(BaseReq, "update_eng", update)
    yield sent, refresh, update
    monkeypatch.setattr(Base3Buffer, "_instance", None)


def _command(speed=10):
    return CommandReq.build(
        TMCC2EngineCommandEnum.ABSOLUTE_SPEED,
        address=3,
        data=speed,
        scope=CommandScope.ENGINE,
    )


def _write(data):
    return SimpleNamespace(as_bytes=data)


def test_sync_state_sends_database_updates(sync_harness):
    sent, refresh, update = sync_harness
    first, second = _write(b"first"), _write(b"second")
    update.return_value = [first, second]

    Base3Buffer.sync_state(_command().as_bytes)

    assert sent.call_args_list == [call(b"first"), call(b"second")]
    refresh.assert_not_called()
    update.assert_called_once()


def test_sync_state_requests_refresh(sync_harness):
    sent, refresh, update = sync_harness
    engine = Mock(spec=EngineState)
    update.return_value = [engine]

    Base3Buffer.sync_state(_command().as_bytes)

    refresh.assert_called_once_with(engine)
    sent.assert_not_called()


def test_sync_state_mixed_requests_preserves_order(sync_harness, monkeypatch):
    sent, refresh, update = sync_harness
    events = []
    first, second = _write(b"first"), _write(b"second")
    engine = Mock(spec=EngineState)
    update.return_value = [first, engine, second]
    sent.side_effect = lambda data: events.append(("send", data))
    refresh.side_effect = lambda state: events.append(("refresh", state))

    Base3Buffer.sync_state(_command().as_bytes)

    assert events == [("send", b"first"), ("refresh", engine), ("send", b"second")]


def test_sync_state_no_updates(sync_harness):
    sent, refresh, update = sync_harness
    update.return_value = []

    Base3Buffer.sync_state(_command().as_bytes)

    update.assert_called_once()
    sent.assert_not_called()
    refresh.assert_not_called()


def test_sync_state_multiple_commands(sync_harness):
    sent, refresh, update = sync_harness
    update.side_effect = [[_write(b"first")], [_write(b"second")]]

    Base3Buffer.sync_state(_command(10).as_bytes + _command(20).as_bytes)

    assert update.call_count == 2
    assert sent.call_args_list == [call(b"first"), call(b"second")]
    refresh.assert_not_called()


def test_dispatcher_client_forwarding_does_not_send_base_writes(sync_harness, monkeypatch):
    sent, refresh, update = sync_harness
    write = _write(b"client-update")
    engine = Mock(spec=EngineState)
    update.return_value = [write, engine]
    forwarded = Mock()
    dispatcher = SimpleNamespace(update_client_state=forwarded)

    # Exercise the actual dispatcher method without starting its worker thread.
    from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2R4LCEnum

    cmd = CommandReq.build(TMCC2R4LCEnum.TRAIN_ADDRESS, address=3, data=4)
    CommandDispatcher.update_base_state(dispatcher, cmd, update_clients=True)

    forwarded.assert_called_once_with(write)
    sent.assert_not_called()
    refresh.assert_called_once_with(engine)


def test_sync_state_train_marker_is_not_treated_as_engine_refresh(sync_harness):
    sent, refresh, update = sync_harness
    train = Mock(spec=TrainState)
    train.as_bytes = b"train-marker"
    update.return_value = [train]

    Base3Buffer.sync_state(_command().as_bytes)

    # This is current behavior, not the desired future behavior:
    # sync_state recognizes only EngineState as a refresh marker.
    sent.assert_called_once_with(b"train-marker")
    refresh.assert_not_called()
