import pytest

from pytrain.utils import ip_tools


def test_threaded_base_discovery_finds_base(monkeypatch):
    monkeypatch.setattr(ip_tools, "get_ip_address", lambda: ["192.168.1.10"])
    monkeypatch.setattr(
        ip_tools,
        "is_base_address",
        lambda address: address if address == "192.168.1.42" else None,
    )
    assert ip_tools.find_base_address() == "192.168.1.42"


def test_threaded_base_discovery_no_match(monkeypatch):
    monkeypatch.setattr(ip_tools, "get_ip_address", lambda: ["192.168.1.10"])
    monkeypatch.setattr(ip_tools, "is_base_address", lambda address: None)
    assert ip_tools.find_base_address() is None


def test_threaded_base_discovery_no_addresses(monkeypatch):
    monkeypatch.setattr(ip_tools, "get_ip_address", lambda: [])
    assert ip_tools.find_base_address() is None


def test_threaded_base_discovery_includes_host_one(monkeypatch):
    monkeypatch.setattr(ip_tools, "get_ip_address", lambda: ["192.168.1.10"])
    monkeypatch.setattr(
        ip_tools,
        "is_base_address",
        lambda address: address if address == "192.168.1.1" else None,
    )
    assert ip_tools.find_base_address() == "192.168.1.1"


def test_threaded_base_discovery_excludes_local_host(monkeypatch):
    monkeypatch.setattr(ip_tools, "get_ip_address", lambda: ["192.168.1.1"])
    scanned = []

    def probe(address):
        scanned.append(address)
        return None

    monkeypatch.setattr(ip_tools, "is_base_address", probe)
    assert ip_tools.find_base_address() is None
    assert "192.168.1.1" not in scanned
    assert "192.168.1.2" in scanned
    assert "192.168.1.254" in scanned
    assert "192.168.1.255" not in scanned


@pytest.mark.parametrize(
    ("explicit", "environment", "expected"),
    [
        (None, None, 32),
        (None, "12", 12),
        (8, "12", 8),
        (500, None, 253),
    ],
)
def test_discovery_worker_configuration(monkeypatch, explicit, environment, expected):
    monkeypatch.setattr(ip_tools, "get_ip_address", lambda: ["192.168.1.10"])
    monkeypatch.setattr(ip_tools, "is_base_address", lambda address: None)
    if environment is None:
        monkeypatch.delenv("PYTRAIN_DISCOVERY_WORKERS", raising=False)
    else:
        monkeypatch.setenv("PYTRAIN_DISCOVERY_WORKERS", environment)

    actual_workers = []
    original_executor = ip_tools.ThreadPoolExecutor

    def capture_executor(*args, **kwargs):
        actual_workers.append(kwargs["max_workers"])
        return original_executor(*args, **kwargs)

    monkeypatch.setattr(ip_tools, "ThreadPoolExecutor", capture_executor)
    assert ip_tools.find_base_address(max_workers=explicit) is None
    assert actual_workers == [expected]


@pytest.mark.parametrize(
    "value",
    ["0", "-2", "abc", "1.5", ""],
)
def test_invalid_discovery_environment(monkeypatch, value):
    monkeypatch.setenv("PYTRAIN_DISCOVERY_WORKERS", value)
    with pytest.raises(ValueError, match="positive integer"):
        ip_tools.find_base_address()


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "8"])
def test_invalid_explicit_discovery_workers(monkeypatch, value):
    monkeypatch.setenv("PYTRAIN_DISCOVERY_WORKERS", "8")
    with pytest.raises(ValueError, match="positive integer"):
        ip_tools.find_base_address(max_workers=value)
