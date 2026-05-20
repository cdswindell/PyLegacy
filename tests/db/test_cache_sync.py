import pytest

from src.pytrain.db.cache_sync import (
    DEFAULT_CACHE_SYNC_POLL,
    CacheSyncManager,
    CacheSyncPaths,
    SidecarCacheTransport,
)


def test_default_cache_sync_poll_interval_is_30_seconds() -> None:
    assert DEFAULT_CACHE_SYNC_POLL == 30.0


def test_sidecar_payload_round_trip_syncs_files_and_deletes_stale_client_cache(tmp_path) -> None:
    local = CacheSyncPaths(tmp_path / "local_info", tmp_path / "local_images")
    remote = CacheSyncPaths(tmp_path / "remote_info", tmp_path / "remote_images")
    for path in local.iter_existing_or_configured():
        path.mkdir(parents=True)
    for path in remote.iter_existing_or_configured():
        path.mkdir(parents=True)

    (local.engine_info / "abc.json").write_text('{"name": "abc"}', encoding="utf-8")
    (local.engine_images / "catalog.jpg").write_bytes(b"catalog")
    (remote.engine_info / "stale.json").write_text("stale", encoding="utf-8")
    (remote.engine_images / "stale.jpg").write_bytes(b"stale")
    (remote.engine_images / "1234.jpg").write_bytes(b"custom")

    payload = SidecarCacheTransport.build_payload(local, remote, delete=True)
    SidecarCacheTransport.apply_payload(remote, payload)

    assert (remote.engine_info / "abc.json").read_text(encoding="utf-8") == '{"name": "abc"}'
    assert (remote.engine_images / "catalog.jpg").read_bytes() == b"catalog"
    assert not (remote.engine_info / "stale.json").exists()
    assert not (remote.engine_images / "stale.jpg").exists()
    assert (remote.engine_images / "1234.jpg").read_bytes() == b"custom"


def test_sidecar_payload_without_delete_keeps_stale_server_cache(tmp_path) -> None:
    local = CacheSyncPaths(tmp_path / "local_info", tmp_path / "local_images")
    remote = CacheSyncPaths(tmp_path / "remote_info", tmp_path / "remote_images")
    for path in local.iter_existing_or_configured():
        path.mkdir(parents=True)
    for path in remote.iter_existing_or_configured():
        path.mkdir(parents=True)

    (local.engine_info / "abc.json").write_text("new", encoding="utf-8")
    (remote.engine_info / "stale.json").write_text("stale", encoding="utf-8")

    payload = SidecarCacheTransport.build_payload(local, remote, delete=False)
    SidecarCacheTransport.apply_payload(remote, payload)

    assert (remote.engine_info / "abc.json").read_text(encoding="utf-8") == "new"
    assert (remote.engine_info / "stale.json").read_text(encoding="utf-8") == "stale"


@pytest.mark.parametrize("unsafe_path", ["../bad.json", "/bad.json", "nested/../bad.json", r"nested\bad.json"])
def test_sidecar_payload_rejects_unsafe_paths(tmp_path, unsafe_path) -> None:
    paths = CacheSyncPaths(tmp_path / "engine_info", tmp_path / "engine_images")
    for path in paths.iter_existing_or_configured():
        path.mkdir(parents=True)

    payload = {
        "delete": False,
        "caches": ["engine_info"],
        "files": [{"cache": "engine_info", "path": unsafe_path, "content": ""}],
    }

    with pytest.raises(ValueError):
        SidecarCacheTransport.apply_payload(paths, payload)


def test_cache_sync_paths_round_trip_wire_dict(tmp_path) -> None:
    paths = CacheSyncPaths(tmp_path / "engine_info", tmp_path / "engine_images")

    decoded = CacheSyncPaths.from_wire_dict(paths.as_wire_dict())

    assert decoded == paths


def test_force_sync_skips_when_client_server_does_not_advertise_support(monkeypatch) -> None:
    calls = []
    manager = object.__new__(CacheSyncManager)
    manager._is_server = False
    manager._server_advertised_sync = False
    manager._sidecar_available = True
    manager._sync_to_server = lambda: calls.append("sync")
    manager._cache_manifest = lambda: ()

    manager.force_sync()

    assert calls == []


def test_sync_to_peer_posts_payload_to_sidecar(tmp_path, monkeypatch) -> None:
    local = CacheSyncPaths(tmp_path / "local_info", tmp_path / "local_images")
    remote = CacheSyncPaths(tmp_path / "remote_info", tmp_path / "remote_images")
    for path in local.iter_existing_or_configured():
        path.mkdir(parents=True)
    for path in remote.iter_existing_or_configured():
        path.mkdir(parents=True)
    (local.engine_info / "abc.json").write_text("new", encoding="utf-8")

    calls = []

    def fake_request(host, port, payload, body=None, **_kwargs):
        calls.append((host, port, payload, body))
        return {"ok": True}

    monkeypatch.setattr(CacheSyncManager, "sidecar_request", fake_request)

    transport = SidecarCacheTransport()

    assert transport.sync_to_peer("192.168.3.150", 5655, local, remote, delete=False) is True
    assert calls[0][0] == "192.168.3.150"
    assert calls[0][1] == 5655
    assert calls[0][2]["command"] == "sync"
    assert calls[0][2]["content_length"] == len(calls[0][3])
    assert b"abc.json" in calls[0][3]
