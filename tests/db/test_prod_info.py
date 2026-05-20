import json

import pytest
import requests

from src.pytrain.db import prod_info as mod


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None, content: bytes = b""):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content

    def json(self) -> dict:
        return self._payload


def _product_payload(bt_id: str = "ABCD", image_url: str = "https://example.invalid/image.jpg") -> dict:
    return {
        "id": 1,
        "skuNumber": "1234",
        "imageUrl": image_url,
        "blE_HexId": bt_id,
        "engineType": "Diesel",
        "productFamily": 1,
        "engineClass": 2,
        "description": "Test engine",
        "roadName": "Lionel",
        "roadNumber": "1234",
        "gauge": "O",
        "pmid": "PMID",
        "smoke": True,
        "sound": True,
        "frontCoupler": False,
        "rearCoupler": True,
        "masterVolume": True,
        "customSound": False,
    }


def _prod_info(image_url: str = "https://example.invalid/resources/images/engine.png") -> mod.ProdInfo:
    return mod.ProdInfo(
        pid=1,
        sku_number=1234,
        ble_hexid="ABCD",
        product_family=1,
        engine_class=2,
        engine_type="Diesel",
        description="Test engine",
        road_name="Lionel",
        road_number="1234",
        gauge="O",
        pmid="PMID",
        smoke=True,
        sound=True,
        front_coupler=False,
        rear_coupler=True,
        master_volume=True,
        custom_sound=False,
        image_url=image_url,
    )


# noinspection PyProtectedMember
def setup_function() -> None:
    mod.ProdInfo._bt_cache.clear()
    mod.ProdInfo._failed_bt_cache.clear()
    mod.find_file.cache_clear()


def test_get_info_uses_configured_timeouts(monkeypatch) -> None:
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return DummyResponse(
            200,
            _product_payload("ABCD"),
        )

    monkeypatch.setattr(mod, "API_KEY", "tests-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_CONNECT_TIMEOUT", 2.5, raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_READ_TIMEOUT", 7.5, raising=True)
    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", None, raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get, raising=True)

    payload = mod.ProdInfo.get_info("ABCD")

    assert payload["roadName"] == "Lionel"
    assert calls == [
        (
            "https://example.invalid/ABCD",
            {"LionelApiKey": "tests-key"},
            (2.5, 7.5),
        )
    ]


def test_by_btid_caches_successful_lookup(monkeypatch) -> None:
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return DummyResponse(
            200,
            _product_payload("BEEF", "https://example.invalid/engine.jpg"),
        )

    monkeypatch.setattr(mod, "API_KEY", "tests-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", None, raising=True)
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

    monkeypatch.setattr(mod, "API_KEY", "tests-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", None, raising=True)
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
    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", None, raising=True)

    first = mod.ProdInfo.by_btid("C0DE")
    second = mod.ProdInfo.by_btid("C0DE")

    assert first is None
    assert second is None
    assert "C0DE" in mod.ProdInfo._failed_bt_cache


def test_get_info_reads_from_cache_file(monkeypatch, tmp_path) -> None:
    cache_dir = tmp_path / "engine_info"
    cache_dir.mkdir()
    payload = _product_payload("ABCD")
    (cache_dir / "ABCD.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", str(cache_dir), raising=True)
    monkeypatch.setattr(mod.requests, "get", lambda *_args, **_kwargs: pytest.fail("Unexpected product lookup"))

    assert mod.ProdInfo.get_info("ABCD") == payload


def test_get_info_writes_to_cache_file(monkeypatch, tmp_path) -> None:
    cache_dir = tmp_path / "engine_info"
    payload = _product_payload("ABCD")
    notifications = []

    def fake_get(url, headers=None, timeout=None):
        return DummyResponse(200, payload)

    monkeypatch.setattr(mod, "API_KEY", "tests-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", str(cache_dir), raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get, raising=True)
    monkeypatch.setattr(mod, "_notify_cache_changed", lambda cleared=False: notifications.append(cleared), raising=True)

    assert mod.ProdInfo.get_info("ABCD") == payload
    assert json.loads((cache_dir / "ABCD.json").read_text(encoding="utf-8")) == payload
    assert notifications == [False]


def test_get_info_does_not_cache_when_info_cache_dir_is_empty(monkeypatch, tmp_path) -> None:
    payload = _product_payload("ABCD")

    def fake_get(url, headers=None, timeout=None):
        return DummyResponse(200, payload)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "API_KEY", "tests-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", "", raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get, raising=True)

    assert mod.ProdInfo.get_info("ABCD") == payload
    assert not list(tmp_path.rglob("*.json"))


def test_image_content_reads_from_cache_file(monkeypatch, tmp_path) -> None:
    cache_dir = tmp_path / "engine_images"
    cache_dir.mkdir()
    image_bytes = b"cached image bytes"
    (cache_dir / "engine.png").write_bytes(image_bytes)

    monkeypatch.setattr(mod, "ENGINE_IMAGES_CACHE_DIR", str(cache_dir), raising=True)
    monkeypatch.setattr(mod.requests, "get", lambda *_args, **_kwargs: pytest.fail("Unexpected image lookup"))

    assert _prod_info().image_content == image_bytes


def test_image_content_writes_to_cache_file(monkeypatch, tmp_path) -> None:
    cache_dir = tmp_path / "engine_images"
    image_bytes = b"downloaded image bytes"
    notifications = []

    def fake_get(url, timeout=None):
        return DummyResponse(200, content=image_bytes)

    monkeypatch.setattr(mod, "ENGINE_IMAGES_CACHE_DIR", str(cache_dir), raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get, raising=True)
    monkeypatch.setattr(mod, "_notify_cache_changed", lambda cleared=False: notifications.append(cleared), raising=True)

    assert _prod_info().image_content == image_bytes
    assert (cache_dir / "engine.png").read_bytes() == image_bytes
    assert notifications == [False]


def test_image_content_does_not_cache_when_image_cache_dir_is_empty(monkeypatch, tmp_path) -> None:
    image_bytes = b"downloaded image bytes"

    def fake_get(url, timeout=None):
        return DummyResponse(200, content=image_bytes)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ENGINE_IMAGES_CACHE_DIR", "", raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get, raising=True)

    assert _prod_info().image_content == image_bytes
    assert not list(tmp_path.rglob("*.png"))


def test_no_file_caching_when_both_cache_dirs_are_empty(monkeypatch, tmp_path) -> None:
    payload = _product_payload("ABCD")
    image_bytes = b"downloaded image bytes"

    def fake_get_info(url, headers=None, timeout=None):
        return DummyResponse(200, payload)

    def fake_get_image(url, timeout=None):
        return DummyResponse(200, content=image_bytes)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "API_KEY", "tests-key", raising=True)
    monkeypatch.setattr(mod, "PROD_INFO_URL", "https://example.invalid/{}", raising=True)
    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", "", raising=True)
    monkeypatch.setattr(mod, "ENGINE_IMAGES_CACHE_DIR", "", raising=True)
    monkeypatch.setattr(mod.requests, "get", fake_get_info, raising=True)

    assert mod.ProdInfo.get_info("ABCD") == payload

    monkeypatch.setattr(mod.requests, "get", fake_get_image, raising=True)

    assert _prod_info().image_content == image_bytes
    assert not list(tmp_path.rglob("*"))


def test_clear_caches_removes_cache_files_and_clears_memory(monkeypatch, tmp_path) -> None:
    info_cache_dir = tmp_path / "engine_info"
    image_cache_dir = tmp_path / "engine_images"
    info_cache_dir.mkdir()
    image_cache_dir.mkdir()
    (info_cache_dir / "ABCD.json").write_text("{}", encoding="utf-8")
    (image_cache_dir / "engine.png").write_bytes(b"image bytes")
    mod.ProdInfo._bt_cache["ABCD"] = {"cached": True}
    mod.ProdInfo._failed_bt_cache.add("DEAD")
    notifications = []

    monkeypatch.setattr(mod, "ENGINE_INFO_CACHE_DIR", str(info_cache_dir), raising=True)
    monkeypatch.setattr(mod, "ENGINE_IMAGES_CACHE_DIR", str(image_cache_dir), raising=True)
    monkeypatch.setattr(mod, "_notify_cache_changed", lambda cleared=False: notifications.append(cleared), raising=True)

    mod.ProdInfo.clear_caches()

    assert not list(info_cache_dir.iterdir())
    assert not list(image_cache_dir.iterdir())
    assert mod.ProdInfo._bt_cache == {}
    assert mod.ProdInfo._failed_bt_cache == set()
    assert notifications == [True]
