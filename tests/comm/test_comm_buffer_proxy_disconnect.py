#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  SPDX-License-Identifier: LGPL-3.0-only
#

"""Client proxy transport retry and disconnect regression tests."""

import socket
import uuid
from unittest.mock import MagicMock

import pytest

from src.pytrain.comm import comm_buffer
from src.pytrain.comm.comm_buffer import CommBufferProxy
from src.pytrain.comm.enqueue_proxy_requests import EnqueueProxyRequests


@pytest.fixture
def proxy():
    # Avoid CommBuffer singleton initialization, worker threads, and network I/O.
    instance = object.__new__(CommBufferProxy)
    instance._scheduler = MagicMock()
    instance._scheduler.has_scheduled = False
    instance._server = "127.0.0.1"
    instance._port = 5110
    instance._client_port = 5111
    instance._uuid = uuid.uuid4()
    instance._heartbeat_bytes = None
    instance._heart_beat_thread = None
    instance._server_version = None
    instance._server_version_available = MagicMock()
    instance._base3_address = None
    instance._ephemeral_port = None
    return instance


@pytest.fixture
def fake_socket(monkeypatch):
    sock = MagicMock()
    sock.__enter__.return_value = sock
    sock.recv.return_value = bytes((2, 12, 13))
    sock.getsockname.return_value = ("127.0.0.1", 12345)
    factory = MagicMock(return_value=sock)
    monkeypatch.setattr(comm_buffer.socket, "socket", factory)
    monkeypatch.setattr(comm_buffer.time, "sleep", lambda _: None)
    return sock


def test_normal_command_sent_on_first_connection(proxy, fake_socket):
    proxy.enqueue_command(b"command")

    fake_socket.connect.assert_called_once_with(("127.0.0.1", 5110))
    fake_socket.sendall.assert_called_once_with(b"command")


def test_normal_command_retries_transient_connection_failure(proxy, fake_socket):
    fake_socket.connect.side_effect = [ConnectionRefusedError(111, "refused"), None]

    proxy.enqueue_command(b"command", max_retries=1)

    assert fake_socket.connect.call_count == 2
    fake_socket.sendall.assert_called_once_with(b"command")


def test_normal_command_raises_after_retry_limit(proxy, fake_socket):
    fake_socket.connect.side_effect = ConnectionRefusedError(111, "refused")

    with pytest.raises(ConnectionRefusedError):
        proxy.enqueue_command(b"command", max_retries=1)

    assert fake_socket.connect.call_count == 2


def test_normal_command_retains_default_retry_limit(proxy, fake_socket):
    fake_socket.connect.side_effect = ConnectionRefusedError(111, "refused")

    with pytest.raises(ConnectionRefusedError):
        proxy.enqueue_command(b"command")

    assert fake_socket.connect.call_count == 91


def test_disconnect_sends_request_when_server_available(proxy, fake_socket):
    proxy.disconnect()

    fake_socket.connect.assert_called_once()
    fake_socket.sendall.assert_called_once_with(
        EnqueueProxyRequests.disconnect_request(proxy.client_port, proxy.session_id)
    )


def test_disconnect_does_not_retry_when_server_unavailable(proxy, fake_socket):
    fake_socket.connect.side_effect = ConnectionRefusedError(111, "refused")

    proxy.disconnect()

    fake_socket.connect.assert_called_once()
    fake_socket.sendall.assert_not_called()


def test_disconnect_stops_heartbeat_before_attempting_send(proxy, fake_socket):
    heartbeat = MagicMock()
    proxy._heart_beat_thread = heartbeat
    fake_socket.connect.side_effect = ConnectionRefusedError(111, "refused")

    proxy.disconnect()

    heartbeat.shutdown.assert_called_once_with()
    fake_socket.connect.assert_called_once()
