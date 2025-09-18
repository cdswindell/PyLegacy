#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import uuid

import pytest

from src.pytrain.comm.enqueue_proxy_requests import EnqueueHandler, EnqueueProxyRequests
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import DEFAULT_SERVER_PORT
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum


class DummyBuffer:
    def __init__(self):
        self.enqueued = []
        self.session_id = 123
        self.base3_address = None

    def enqueue_command(self, data: bytes):
        self.enqueued.append(data)


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch):
    # Prevent the background server thread from creating a real TCP server
    monkeypatch.setattr(EnqueueProxyRequests, "run", lambda self: None)
    # Reset singleton before each test
    EnqueueProxyRequests._instance = None
    yield
    # Reset singleton after each test
    EnqueueProxyRequests._instance = None


def test_build_request_register_with_uuid_and_version():
    port = 12345
    client_id = uuid.uuid4()
    version = (1, 2, 3)
    base = CommandReq(TMCC1SyncCommandEnum.REGISTER).as_bytes

    built = EnqueueProxyRequests.register_request(port, client_id, version)

    assert built.startswith(base)
    # After first 3 bytes, expect: port(2) + uuid(16) + version(3)
    payload = built[3:]
    assert int.from_bytes(payload[:2], "big") == (port & 0xFFFF)
    assert payload[2:18] == client_id.bytes
    assert payload[18:21] == bytes(version)


def test_build_request_disconnect_with_uuid_no_version():
    port = 43210
    client_id = uuid.uuid4()
    base = CommandReq(TMCC1SyncCommandEnum.DISCONNECT).as_bytes

    built = EnqueueProxyRequests.disconnect_request(port, client_id)

    assert built.startswith(base)
    payload = built[3:]
    assert int.from_bytes(payload[:2], "big") == (port & 0xFFFF)
    assert payload[2:18] == client_id.bytes
    # No version afterward
    assert len(payload) == 2 + 16


def test_build_request_sync_state_minimal_defaults():
    # No client_id provided, default port
    base = CommandReq(TMCC1SyncCommandEnum.SYNC_REQUEST).as_bytes

    built = EnqueueProxyRequests.sync_state_request()

    assert built.startswith(base)
    payload = built[3:]
    # default port
    assert int.from_bytes(payload, "big") == (DEFAULT_SERVER_PORT & 0xFFFF)


@pytest.mark.parametrize(
    "cmd_enum",
    [
        TMCC1SyncCommandEnum.QUIT,
        TMCC1SyncCommandEnum.REBOOT,
        TMCC1SyncCommandEnum.RESTART,
        TMCC1SyncCommandEnum.SHUTDOWN,
        TMCC1SyncCommandEnum.UPDATE,
        TMCC1SyncCommandEnum.UPGRADE,
        TMCC1SyncCommandEnum.RESYNC,
        TMCC1SyncCommandEnum.KEEP_ALIVE,
    ],
)
def test_extract_addendum_variants_port_uuid_and_version(cmd_enum):
    port = 25000
    client_id = uuid.uuid4()
    version = (9, 8, 7)

    base = CommandReq(cmd_enum).as_bytes
    # emulate "register-like" framing: 3 bytes header + port(2) + uuid(16) + version(3)
    byte_stream = base + (port & 0xFFFF).to_bytes(2, "big") + client_id.bytes + bytes(version)

    ip, dec_port, dec_uuid, dec_version = EnqueueHandler.extract_addendum(byte_stream)

    assert ip is None
    assert dec_port == port
    assert dec_uuid == client_id
    assert dec_version == version


def test_extract_addendum_port_and_uuid_only():
    port = 11001
    client_id = uuid.uuid4()
    base = CommandReq(TMCC1SyncCommandEnum.DISCONNECT).as_bytes
    byte_stream = base + (port & 0xFFFF).to_bytes(2, "big") + client_id.bytes

    ip, dec_port, dec_uuid, dec_version = EnqueueHandler.extract_addendum(byte_stream)

    assert ip is None
    assert dec_port == port
    assert dec_uuid == client_id
    assert dec_version is None


def test_extract_addendum_ip_port_text():
    ip_text = "192.168.1.77"
    port = 5678
    base = CommandReq(TMCC1SyncCommandEnum.RESTART).as_bytes
    byte_stream = base + f"{ip_text}:{port}".encode("utf-8")

    ip, dec_port, dec_uuid, dec_version = EnqueueHandler.extract_addendum(byte_stream)

    assert ip == ip_text
    assert dec_port == port
    assert dec_uuid is None
    assert dec_version is None


def test_extract_addendum_port_only_two_bytes():
    port = 60001
    base = CommandReq(TMCC1SyncCommandEnum.KEEP_ALIVE).as_bytes
    byte_stream = base + (port & 0xFFFF).to_bytes(2, "big")

    ip, dec_port, dec_uuid, dec_version = EnqueueHandler.extract_addendum(byte_stream)

    assert ip is None
    assert dec_port == (port & 0xFFFF)  # truncated to 16 bits per implementation
    assert dec_uuid is None
    assert dec_version is None


# noinspection PyTypeChecker
def test_client_session_tracking_connect_disconnect_and_replace():
    buf = DummyBuffer()
    proxy = EnqueueProxyRequests(buf, server_port=0)  # run() patched to no-op; thread returns immediately

    ip = "10.0.0.5"
    port = 12345
    cid1 = uuid.uuid4()
    cid2 = uuid.uuid4()

    # Initial connect
    proxy.client_connect(ip, port, cid1)
    assert proxy.is_client(ip, port, cid1) is True
    assert (ip, port) in proxy.client_sessions

    # Connect with same (ip,port) but different client_id should purge prior session
    proxy.client_connect(ip, port, cid2)
    assert proxy.is_client(ip, port, cid1) is False
    assert proxy.is_client(ip, port, cid2) is True
    assert (ip, port) in proxy.client_sessions
    # Only one tuple for (ip,port) across sessions
    assert {(c[0], c[1]) for c in proxy.client_sessions} == {(ip, port)}

    # KEEP_ALIVE refresh doesn't error
    proxy.client_alive(ip, port, cid2)

    # Disconnect
    proxy.client_disconnect(ip, port, cid2)
    assert proxy.is_client(ip, port, cid2) is False
    assert (ip, port) not in proxy.client_sessions


# noinspection PyTypeChecker
def test_enqueue_request_forwards_to_buffer():
    buf = DummyBuffer()
    proxy = EnqueueProxyRequests(buf, server_port=0)

    data = b"\xfe\xf0\x01\x02"
    proxy.enqueue_request(data)

    assert buf.enqueued == [data]
