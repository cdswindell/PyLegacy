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


def test_sidecar_payload_can_skip_tombstoned_file_names(tmp_path) -> None:
    local = CacheSyncPaths(tmp_path / "local_info", tmp_path / "local_images")
    remote = CacheSyncPaths(tmp_path / "remote_info", tmp_path / "remote_images")
    for path in local.iter_existing_or_configured():
        path.mkdir(parents=True)
    for path in remote.iter_existing_or_configured():
        path.mkdir(parents=True)

    (local.engine_images / "42.jpg").write_bytes(b"deleted")
    (local.engine_images / "43.jpg").write_bytes(b"keep")

    payload = SidecarCacheTransport.build_payload(local, remote, delete=False)
    SidecarCacheTransport.apply_payload(remote, payload, skip_file_names={"42.jpg"})

    assert not (remote.engine_images / "42.jpg").exists()
    assert (remote.engine_images / "43.jpg").read_bytes() == b"keep"


def test_delete_matching_files_removes_named_files_in_all_cache_subdirs(tmp_path) -> None:
    paths = CacheSyncPaths(tmp_path / "engine_info", tmp_path / "engine_images")
    for path in paths.iter_existing_or_configured():
        path.mkdir(parents=True)

    (paths.engine_info / "42.jpg").write_text("info", encoding="utf-8")
    (paths.engine_info / "nested").mkdir()
    (paths.engine_info / "nested" / "42.jpg").write_text("nested info", encoding="utf-8")
    (paths.engine_images / "42.jpg").write_text("custom", encoding="utf-8")
    (paths.engine_images / "43.jpg").write_text("keep", encoding="utf-8")

    assert SidecarCacheTransport.delete_matching_files(paths, "42.jpg") == 3

    assert not (paths.engine_info / "42.jpg").exists()
    assert not (paths.engine_info / "nested").exists()
    assert not (paths.engine_images / "42.jpg").exists()
    assert (paths.engine_images / "43.jpg").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("unsafe_name", ["../42.jpg", "nested/42.jpg", r"nested\42.jpg", "", ".", ".."])
def test_delete_matching_files_rejects_unsafe_file_names(tmp_path, unsafe_name) -> None:
    paths = CacheSyncPaths(tmp_path / "engine_info", tmp_path / "engine_images")

    with pytest.raises(ValueError):
        SidecarCacheTransport.delete_matching_files(paths, unsafe_name)


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


def test_client_delete_deletes_local_file_then_forwards_to_server() -> None:
    calls = []

    class FakeTransport:
        def delete_from_peer(self, host, port, file_name, *, propagate):
            calls.append(("server", host, port, file_name, propagate))
            return True

    manager = object.__new__(CacheSyncManager)
    manager._is_server = False
    manager._server_ip = "192.168.3.100"
    manager._server_sync_port = 5655
    manager._server_advertised_sync = True
    manager._transport = FakeTransport()
    manager._delete_local_cache_file = lambda file_name, **_kwargs: calls.append(("local", file_name)) or 1
    manager._cache_manifest = lambda: ()

    assert manager.delete_cache_file("42.jpg") == 1

    assert calls == [
        ("local", "42.jpg"),
        ("server", "192.168.3.100", 5655, "42.jpg", True),
    ]


def test_server_delete_deletes_local_file_then_propagates_to_clients() -> None:
    calls = []

    class FakeTransport:
        def delete_from_peer(self, host, port, file_name, *, propagate):
            calls.append(("client", host, port, file_name, propagate))
            return True

    manager = object.__new__(CacheSyncManager)
    manager._is_server = True
    manager._sync_port = 5655
    manager._clients_provider = lambda: {("192.168.3.101", 5655), ("192.168.3.102", 5655)}
    manager._transport = FakeTransport()
    manager._delete_local_cache_file = lambda file_name, **_kwargs: calls.append(("local", file_name)) or 1
    manager._cache_manifest = lambda: ()

    assert manager.delete_cache_file("42.jpg") == 1

    assert calls[0] == ("local", "42.jpg")
    assert set(calls[1:]) == {
        ("client", "192.168.3.101", 5655, "42.jpg", False),
        ("client", "192.168.3.102", 5655, "42.jpg", False),
    }


def test_server_delete_keeps_tombstone_until_client_delete_requests_are_sent() -> None:
    calls = []
    manager = object.__new__(CacheSyncManager)

    class FakeTransport:
        def delete_from_peer(self, host, port, file_name, *, propagate):
            calls.append(("client", file_name, manager._delete_tombstone_snapshot()))
            return True

    manager._is_server = True
    manager._sync_port = 5655
    manager._clients_provider = lambda: {("192.168.3.101", 5655)}
    manager._transport = FakeTransport()
    manager._delete_local_cache_file = lambda file_name, **_kwargs: (
        calls.append(("local", file_name, manager._delete_tombstone_snapshot())) or 1
    )
    manager._cache_manifest = lambda: ()

    assert manager.delete_cache_file("42.jpg") == 1

    assert calls == [
        ("local", "42.jpg", {"42.jpg"}),
        ("client", "42.jpg", {"42.jpg"}),
    ]
    assert manager._delete_tombstone_snapshot() == set()


def test_propagated_delete_does_not_log_when_file_is_already_missing(tmp_path, monkeypatch, caplog) -> None:
    paths = CacheSyncPaths(tmp_path / "engine_info", tmp_path / "engine_images")
    for path in paths.iter_existing_or_configured():
        path.mkdir(parents=True)
    monkeypatch.setattr("src.pytrain.db.prod_info.ENGINE_INFO_CACHE_DIR", str(paths.engine_info), raising=True)
    monkeypatch.setattr("src.pytrain.db.prod_info.ENGINE_IMAGES_CACHE_DIR", str(paths.engine_images), raising=True)

    manager = object.__new__(CacheSyncManager)
    manager._is_server = False
    manager._cache_manifest = lambda: ()

    with caplog.at_level("INFO"):
        assert manager.delete_cache_file("42.jpg", propagate=False, log_not_found=False) == 0

    assert "No cache files named 42.jpg found" not in caplog.text


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
