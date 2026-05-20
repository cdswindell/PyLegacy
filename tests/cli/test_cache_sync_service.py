import socket

from zeroconf import ServiceInfo

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
