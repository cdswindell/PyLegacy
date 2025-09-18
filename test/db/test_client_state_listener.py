#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import threading

import pytest

from src.pytrain.db.client_state_listener import ClientStateHandler, ClientStateListener
from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, PDI_STF


@pytest.fixture(autouse=True)
def reset_singleton_state():
    # Ensure singleton state doesn't leak between tests
    ClientStateListener._instance = None
    yield
    ClientStateListener._instance = None


class FakeCommBufferProxy:
    def __init__(self, version=None):
        self._server_version = version
        self._ev = threading.Event()
        self._ev.set()
        self._registered = []
        self._synced = False
        self._hb = False

    @staticmethod
    def server_port():
        return 12345

    def register(self, port):
        self._registered.append(port)

    def sync_state(self):
        self._synced = True

    def start_heart_beat(self):
        self._hb = True

    def server_version_available(self):
        return self._ev

    @property
    def server_version(self):
        return self._server_version

    @server_version.setter
    def server_version(self, v):
        self._server_version = v


class FakeListener:
    def __init__(self):
        self.offered = []
        self.subscribed = []
        self.unsubscribed = []

    def offer(self, data):
        self.offered.append(data)

    def subscribe(self, listener, channel, address=None, command=None, data=None):
        self.subscribed.append((listener, channel, address, command, data))

    def unsubscribe(self, listener, channel, address=None, command=None, data=None):
        self.unsubscribed.append((listener, channel, address, command, data))


def build_minimal_csl_with_fakes():
    """
    Build a ClientStateListener instance without running __init__, then inject the fakes
    we need to exercise utility methods (subscribe/unsubscribe/offer).
    """
    inst = ClientStateListener.__new__(ClientStateListener)
    inst._initialized = True
    inst._tmcc_listener = FakeListener()
    inst._pdi_listener = FakeListener()
    inst._tmcc_buffer = FakeCommBufferProxy()
    inst._port = 10000
    inst._is_running = False
    return inst


def test_singleton_build_returns_same_instance(monkeypatch):
    # Avoid running real __init__ internals by mocking __init__ to be a no-op for this test
    def _noop_init(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

    monkeypatch.setattr(ClientStateListener, "__init__", _noop_init)

    a = ClientStateListener.build()
    b = ClientStateListener.build()
    assert a is b, "ClientStateListener.build should return singleton instance"


def test_offer_routes_to_pdi_when_sop(monkeypatch):
    csl = build_minimal_csl_with_fakes()

    data_pdi = bytes([PDI_SOP, 0x10, 0x20, PDI_EOP])
    data_tmcc = b"\xf0\x12\x34"

    # Route PDI
    csl.offer(data_pdi)
    assert csl._pdi_listener.offered[-1] == data_pdi
    # Route TMCC
    csl.offer(data_tmcc)
    assert csl._tmcc_listener.offered[-1] == data_tmcc


# noinspection PyTypeChecker
def test_subscribe_and_unsubscribe_delegate_to_both_listeners():
    csl = build_minimal_csl_with_fakes()
    fake_sub = object()
    channel = object()

    csl.subscribe(fake_sub, channel, address=1, command=None, data=None)
    assert csl._tmcc_listener.subscribed[-1][0] is fake_sub
    assert csl._pdi_listener.subscribed[-1][0] is fake_sub

    csl.unsubscribe(fake_sub, channel, address=1, command=None, data=None)
    assert csl._tmcc_listener.unsubscribed[-1][0] is fake_sub
    assert csl._pdi_listener.unsubscribed[-1][0] is fake_sub


def test_update_client_if_needed_compares_versions(monkeypatch):
    # Make an instance without running __init__
    csl = build_minimal_csl_with_fakes()

    # Monkeypatch pytrain.get_version and get_version_tuple used inside the method
    import src.pytrain as pytrain_pkg

    monkeypatch.setattr(pytrain_pkg, "get_version", lambda: "1.2.3")
    monkeypatch.setattr(pytrain_pkg, "get_version_tuple", lambda: (1, 2, 3))

    # Case 1: server newer -> True
    csl._tmcc_buffer.server_version = (1, 3, 0)
    assert csl.update_client_if_needed(do_upgrade=False) is True

    # Case 2: server equal -> False
    csl._tmcc_buffer.server_version = (1, 2, 3)
    assert csl.update_client_if_needed(do_upgrade=False) is False

    # Case 3: server None -> True
    csl._tmcc_buffer.server_version = None
    assert csl.update_client_if_needed(do_upgrade=False) is True


# noinspection PyTypeChecker, PyUnusedLocal
def test_client_state_handler_splits_pdi_then_tmcc(monkeypatch):
    # Build a fake CSL that only records offers
    class FakeCSL:
        def __init__(self):
            self.offers = []

        def offer(self, data):
            self.offers.append(bytes(data))

    fake_csl = FakeCSL()

    # Patch ClientStateListener.build() to return our fake without touching threads/init
    monkeypatch.setattr(ClientStateListener, "build", classmethod(lambda cls: fake_csl))

    # Create a PDI frame with stuffed EOP sequence inside; then TMCC bytes
    # PDI: [SOP, 0xAA, STF, EOP, 0xBB, EOP]  -> last EOP is actual terminator
    pdi_payload = bytes([PDI_SOP, 0xAA, PDI_STF, PDI_EOP, 0xBB, PDI_EOP])
    tmcc_payload = b"\xf0\x12\x34"
    combined = pdi_payload + tmcc_payload

    # Fake socket request that returns data then empty
    # noinspection PyUnusedLocal
    class FakeReq:
        def __init__(self, chunks):
            self._chunks = list(chunks)
            self.sent = []

        def recv(self, size):
            return self._chunks.pop(0) if self._chunks else b""

        def sendall(self, data):
            self.sent.append(data)

    # Build a handler instance with our fake request; BaseRequestHandler would call handle
    handler = ClientStateHandler.__new__(ClientStateHandler)
    handler.request = FakeReq([combined])
    handler.client_address = ("127.0.0.1", 9999)
    handler.server = object()

    # Invoke handle directly
    ClientStateHandler.handle(handler)

    # It should ack once for the single recv
    assert handler.request.sent == [b"ack"]

    # Two offers: first the PDI segment, then the TMCC bytes
    assert len(fake_csl.offers) == 2
    assert fake_csl.offers[0] == pdi_payload  # exact PDI frame
    assert fake_csl.offers[1] == tmcc_payload


def test_handler_handles_multiple_recv_chunks(monkeypatch):
    # Verify that handler concatenates chunks before splitting
    class FakeCSL:
        def __init__(self):
            self.offers = []

        def offer(self, data):
            self.offers.append(bytes(data))

    fake_csl = FakeCSL()
    monkeypatch.setattr(ClientStateListener, "build", classmethod(lambda cls: fake_csl))

    pdi = bytes([PDI_SOP, 0x01, 0x02, PDI_EOP])
    tmcc = b"\xf0\xab\xcd"
    chunks = [pdi[:2], pdi[2:], tmcc, b""]  # fragmented receive  # noqa: F841

    # noinspection PyUnusedLocal,PyShadowingNames
    class FakeReq:
        def __init__(self, chunks):
            self._chunks = list(chunks)
            self.sent = []

        def recv(self, size):
            return self._chunks.pop(0) if self._chunks else b""

        def sendall(self, data):
            self.sent.append(data)

    handler = ClientStateHandler.__new__(ClientStateHandler)
    handler.request = FakeReq
