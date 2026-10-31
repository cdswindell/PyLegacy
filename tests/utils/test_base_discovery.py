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
