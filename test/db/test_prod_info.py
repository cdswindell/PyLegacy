import requests

from pytrain.db import prod_info as mod


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def setup_function() -> None:
    mod.ProdInfo._bt_cache.clear()
    mod.ProdInfo._failed_bt_cache.clear()


def test_get_info_uses_configured_timeouts(monkeypatch) -> None:
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return DummyResponse(
            200,
            {
                "id": 1,
                "skuNumber": "1234",
                "imageUrl": "https://example.invalid/image.jpg",
                "blE_HexId": "ABCD",
                "engineType": "Diesel",
                "productFamily": 1,
                "engineClass": 2,
                "description": "Test engine",
                "roadName": "Lionel",
                "roadNumber": "1234",
                "gauge": "O",
            },
        )

    monkeypatch.setattr(mod, "API_KEY", "test-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_CONNECT_TIMEOUT", 2.5, raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_READ_TIMEOUT", 7.5, raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get, raising=True)

    payload = mod.ProdInfo.get_info("ABCD")

    assert payload["roadName"] == "Lionel"
    assert calls == [
        (
            "https://example.invalid/ABCD",
            {"LionelApiKey": "test-key"},
            (2.5, 7.5),
        )
    ]


def test_by_btid_caches_successful_lookup(monkeypatch) -> None:
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return DummyResponse(
            200,
            {
                "id": 7,
                "skuNumber": "7777",
                "imageUrl": "https://example.invalid/engine.jpg",
                "blE_HexId": "BEEF",
                "engineType": "Diesel",
                "productFamily": 1,
                "engineClass": 2,
                "description": "Cached engine",
                "roadName": "NYC",
                "roadNumber": "7777",
                "gauge": "O",
            },
        )

    monkeypatch.setattr(mod, "API_KEY", "test-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get, raising=True)

    first = mod.ProdInfo.by_btid("BEEF")
    second = mod.ProdInfo.by_btid("BEEF")

    assert first is not None
    assert second is first
    assert len(calls) == 1
    assert "BEEF" in mod.ProdInfo._bt_cache
    assert "BEEF" not in mod.ProdInfo._failed_bt_cache


def test_by_btid_failure_is_negative_cached(monkeypatch) -> None:
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        raise requests.Timeout("timed out")

    monkeypatch.setattr(mod, "API_KEY", "test-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get, raising=True)

    first = mod.ProdInfo.by_btid("DEAD")
    second = mod.ProdInfo.by_btid("DEAD")

    assert first is None
    assert second is None
    assert len(calls) == 1
    assert "DEAD" in mod.ProdInfo._failed_bt_cache
    assert "DEAD" not in mod.ProdInfo._bt_cache


def test_by_btid_missing_configuration_is_negative_cached(monkeypatch) -> None:
    monkeypatch.setattr(mod, "API_KEY", None, raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", None, raising=True)

    first = mod.ProdInfo.by_btid("C0DE")
    second = mod.ProdInfo.by_btid("C0DE")

    assert first is None
    assert second is None
    assert "C0DE" in mod.ProdInfo._failed_bt_cache
