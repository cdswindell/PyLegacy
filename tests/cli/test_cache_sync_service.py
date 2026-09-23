import threading
import socket
from ipaddress import IPv4Address
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from zeroconf import ServiceInfo

from src.pytrain.cli import pytrain as module
from src.pytrain.cli.pytrain import PyTrain


def _service_info(properties: dict[str, str]) -> ServiceInfo:
    return ServiceInfo(
        "_pytrain._tcp.local.",
        "PyTrain._pytrain._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=5555,
        properties=properties,
        server="pytrain.local.",
    )


def test_cache_sync_properties_default_to_disabled_and_derived_port() -> None:
    assert PyTrain.cache_sync_properties(_service_info({})) == (False, 5655)


def test_cache_sync_properties_parse_enabled_and_port() -> None:
    assert PyTrain.cache_sync_properties(_service_info({"CacheSync": "1", "CacheSyncPort": "6000"})) == (True, 6000)


@pytest.mark.parametrize(
    "properties,expected",
    [
        ({"CacheSync": "0"}, (False, 5655)),
        ({"CacheSync": "true"}, (False, 5655)),
        ({"CacheSync": None, "CacheSyncPort": None}, (False, 5655)),
        ({"CacheSync": "", "CacheSyncPort": ""}, (False, 5655)),
        ({"CacheSync": "1", "CacheSyncPort": "not-a-port"}, (True, 5655)),
        ({"CacheSyncPort": "0"}, (False, 0)),
        ({"CacheSyncPort": "-1"}, (False, -1)),
        ({"CacheSyncPort": "65536"}, (False, 65536)),
        ({"unrelated": None, "CacheSyncPort": " 6001 "}, (False, 6001)),
    ],
)
def test_cache_sync_property_variants(properties, expected):
    assert PyTrain.cache_sync_properties(_service_info(properties)) == expected


@pytest.mark.parametrize("properties", [{b"\xff": b"1"}, {b"CacheSyncPort": b"\xff"}])
def test_invalid_utf8_service_properties_raise(properties):
    with pytest.raises(UnicodeDecodeError):
        PyTrain.cache_sync_properties(_service_info(properties))


@pytest.fixture
def cache_service(bare_pytrain, monkeypatch):
    p = bare_pytrain
    p._shutdown_lock = threading.Lock()
    p._cache_sync_started = False
    p._cache_sync_enabled = True
    p._cache_sync_manager = None
    p._cache_sync_port = 6000
    p._server_cache_sync_port = 6100
    p._server_cache_sync_capable = None
    p._server = None
    p._tmcc_buffer = Mock(spec=module.CommBufferSingleton)
    p._tmcc_buffer.base3_address = None
    p._version = "9.8.7"
    p._service_info = None
    p._zeroconf = Mock(spec=module.Zeroconf)
    build = Mock(return_value=Mock())
    stop = Mock()
    monkeypatch.setattr(module.CacheSyncManager, "build", build)
    monkeypatch.setattr(module.CacheSyncManager, "stop", stop)
    monkeypatch.setattr(module, "get_ip_address", Mock(return_value=["192.0.2.10", "192.0.2.11"]))
    monkeypatch.setattr(module.socket, "gethostname", Mock(return_value="pytrain"))
    return SimpleNamespace(p=p, build=build, stop=stop)


@pytest.mark.parametrize("hostname", ["pytrain", "pytrain.local"])
@pytest.mark.parametrize("enabled,port", [(False, None), (True, 6000)])
def test_register_service_encodes_capabilities_and_addresses(cache_service, monkeypatch, hostname, enabled, port):
    p = cache_service.p
    monkeypatch.setattr(module.socket, "gethostname", Mock(return_value=hostname))
    info = p.register_service(enabled, enabled, 5110, enabled, port)
    assert isinstance(info, ServiceInfo)
    assert info.type == module.SERVICE_TYPE
    assert info.name == module.SERVICE_NAME
    assert info.server == "pytrain.local"
    assert info.port == 5110
    assert info.parsed_addresses() == p._server_ips == ["192.0.2.10", "192.0.2.11"]
    flag = b"1" if enabled else b"0"
    assert info.properties == {
        b"version": b"PyTrain Server 9.8.7",
        b"Ser2": flag,
        b"Base3": flag,
        b"CacheSync": flag,
        b"CacheSyncPort": str(port or 5210).encode(),
    }
    p._zeroconf.register_service.assert_called_once_with(info, allow_name_change=True)


@pytest.mark.parametrize("updates", [{}, {"CacheSync": 1, "CacheSyncPort": 6200, "description": "caf\u00e9"}])
def test_update_service_preserves_existing_properties_and_reregisters(cache_service, updates):
    p = cache_service.p
    p._service_info = info = _service_info({"version": "9.8.7", "CacheSync": "0"})
    expected = dict(info.properties)
    expected.update({key.encode(): str(value).encode() for key, value in updates.items()})
    p.update_service(updates)
    assert info.properties == expected
    assert p._zeroconf.mock_calls == [call.unregister_service(info), call.register_service(info)]


def test_update_service_currently_leaves_serialized_txt_properties_stale(cache_service):
    p = cache_service.p
    p._service_info = info = _service_info({"CacheSync": "0", "CacheSyncPort": "6000"})
    original_text = info.text
    p.update_service({"CacheSync": "1", "CacheSyncPort": "6200"})
    assert PyTrain.cache_sync_properties(info) == (True, 6200)
    # Characterize the existing wire-format defect pending production review.
    assert info.text == original_text
    received = ServiceInfo(info.type, info.name, port=info.port, properties=info.text)
    assert PyTrain.cache_sync_properties(received) == (False, 6000)
    p._zeroconf.register_service.assert_called_once_with(info)


@pytest.mark.parametrize("operation", ["register", "unregister", "reregister"])
def test_advertisement_transport_failures_propagate(cache_service, operation):
    p = cache_service.p
    p._service_info = info = _service_info({"CacheSync": "0"})
    method = p._zeroconf.unregister_service if operation == "unregister" else p._zeroconf.register_service
    method.side_effect = RuntimeError("advertisement failed")
    with pytest.raises(RuntimeError, match="advertisement failed"):
        if operation == "register":
            p.register_service(False, True, 5110)
        else:
            p.update_service({"CacheSync": "1"})
    if operation == "unregister":
        assert info.properties[b"CacheSync"] == b"0"
        p._zeroconf.register_service.assert_not_called()
    elif operation == "reregister":
        assert info.properties[b"CacheSync"] == b"1"


@pytest.mark.parametrize(
    "is_server,capable,has_address",
    [(True, None, False)] + [(False, capable, address) for capable in (False, None, True) for address in (False, True)],
)
def test_cache_sync_manager_arguments_and_startup_idempotence(cache_service, is_server, capable, has_address):
    p = cache_service.p
    if not is_server:
        p._tmcc_buffer = Mock(spec=module.CommBuffer)
    p._server = IPv4Address("192.0.2.20") if has_address else None
    p._server_cache_sync_capable = capable
    p._start_cache_sync()
    p._start_cache_sync()
    assert p._cache_sync_started is True
    if not is_server and capable is False:
        cache_service.build.assert_not_called()
        assert p._cache_sync_manager is None
    else:
        cache_service.build.assert_called_once_with(
            enabled=True,
            is_server=is_server,
            sync_port=6000,
            server_ip="192.0.2.20" if has_address and not is_server else None,
            server_sync_port=6100,
            server_advertised_sync=capable,
            clients_provider=module.EnqueueProxyRequests.clients if is_server else None,
        )
        assert p._cache_sync_manager is cache_service.build.return_value


def test_disabled_cache_sync_does_not_construct_manager(cache_service):
    p = cache_service.p
    p._cache_sync_enabled = False
    p._start_cache_sync()
    p._start_cache_sync()
    cache_service.build.assert_not_called()
    assert p._cache_sync_started is True
    assert p._cache_sync_manager is None


def test_failed_cache_sync_start_is_not_retried(cache_service):
    p = cache_service.p
    cache_service.build.side_effect = RuntimeError("cache startup failed")
    with pytest.raises(RuntimeError, match="cache startup failed"):
        p._start_cache_sync()
    p._start_cache_sync()
    cache_service.build.assert_called_once()
    assert p._cache_sync_started is True
    assert p._cache_sync_manager is None


@pytest.mark.parametrize("has_manager", [False, True])
def test_shutdown_cache_preserves_service_and_is_idempotent(cache_service, has_manager):
    p = cache_service.p
    p._cache_sync_manager = Mock() if has_manager else None
    p._service_info = info = _service_info({})
    zeroconf = p._zeroconf
    for _ in range(2):
        p.shutdown_cache()
        assert not p._shutdown_lock.locked()
        assert p._cache_sync_manager is None
        if has_manager:
            cache_service.stop.assert_called_once_with()
        else:
            cache_service.stop.assert_not_called()
        assert p._service_info is info
        assert p._zeroconf is zeroconf
        assert zeroconf.mock_calls == []


def test_shutdown_cache_retains_manager_on_failure_then_retries(cache_service):
    p = cache_service.p
    p._cache_sync_manager = manager = Mock()
    p._service_info = info = _service_info({})
    zeroconf = p._zeroconf
    error = RuntimeError("cache stop failed")
    cache_service.stop.side_effect = [error, None]
    with pytest.raises(RuntimeError, match="cache stop failed") as exc:
        p.shutdown_cache()
    assert exc.value is error
    assert not p._shutdown_lock.locked()
    cache_service.stop.assert_called_once_with()
    assert p._cache_sync_manager is manager
    assert p._service_info is info
    assert p._zeroconf is zeroconf
    assert zeroconf.mock_calls == []

    p.shutdown_cache()
    assert not p._shutdown_lock.locked()
    assert cache_service.stop.mock_calls == [call(), call()]
    assert p._cache_sync_manager is None
    p.shutdown_cache()
    assert not p._shutdown_lock.locked()
    assert cache_service.stop.mock_calls == [call(), call()]
    assert p._cache_sync_manager is None
    assert p._service_info is info
    assert p._zeroconf is zeroconf
    assert zeroconf.mock_calls == []
