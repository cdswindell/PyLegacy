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
