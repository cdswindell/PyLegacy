import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.db import cache_sync as module
from src.pytrain.db.cache_sync import (
    DEFAULT_CACHE_SYNC_POLL,
    CacheSyncManager,
    CacheSyncPaths,
    SidecarCacheTransport,
)


def test_default_cache_sync_poll_interval_is_30_seconds() -> None:
    assert DEFAULT_CACHE_SYNC_POLL == 30.0


@pytest.fixture
def lifecycle(monkeypatch):
    monkeypatch.setattr(CacheSyncManager, "_instance", None)
    monkeypatch.setattr(CacheSyncManager, "_lock", threading.Lock())
    monkeypatch.setattr(CacheSyncManager, "_cache_manifest", lambda self: ())
    monkeypatch.setattr(CacheSyncManager, "start", Mock())
    servers = []
    threads = []

    def server_factory(*args):
        server = Mock()
        servers.append(server)
        return server

    def thread_factory(**kwargs):
        thread = Mock(ident=None)
        thread.is_alive.return_value = False
        thread.start.side_effect = lambda: setattr(thread, "ident", 123)
        threads.append(thread)
        return thread

    monkeypatch.setattr(module, "CacheSyncTCPServer", Mock(side_effect=server_factory))
    monkeypatch.setattr(module, "Thread", Mock(side_effect=thread_factory))

    def build(**kwargs):
        return CacheSyncManager.build(enabled=True, is_server=True, sync_port=5210, **kwargs)

    yield SimpleNamespace(build=build, servers=servers, threads=threads)
    if CacheSyncManager._instance is not None:
        CacheSyncManager._instance._shutdown.set()


@pytest.mark.parametrize("operation", ["shutdown", "server_close"])
@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError])
def test_interrupted_cache_stop_retains_resources_and_retries(lifecycle, caplog, operation, error):
    caplog.set_level(logging.DEBUG, logger=module.log.name)
    manager = lifecycle.build()
    server, thread = manager._server, manager._server_thread
    getattr(server, operation).side_effect = [error("interrupted"), None]
    with pytest.raises(error, match="interrupted"):
        CacheSyncManager.stop()
    assert CacheSyncManager._instance is manager
    assert manager._server is server
    assert manager._server_thread is thread
    assert manager._shutdown.is_set()
    assert not manager.available
    assert not CacheSyncManager._lock.locked()
    assert not manager._shutdown_lock.locked()
    assert not any("stop completed" in message for message in caplog.messages)
    with pytest.raises(RuntimeError, match="stopping"):
        lifecycle.build()
    assert CacheSyncManager.build(enabled=False, is_server=True, sync_port=5210) is None
    CacheSyncManager.stop()
    assert CacheSyncManager._instance is None
    assert manager._server is manager._server_thread is None
    CacheSyncManager.stop()
    attempts = [message for message in caplog.messages if "stop attempt" in message]
    completed = [message for message in caplog.messages if "stop completed" in message]
    assert len(attempts) == 2
    assert len(completed) == 1
    for message in attempts + completed:
        for value in [
            f"manager={id(manager):#x}",
            f"pid={module.os.getpid()}",
            "thread=MainThread",
            "role=server",
            "port=5210",
        ]:
            assert value in message
    assert lifecycle.build() is not manager


def test_stop_without_listener_terminates_real_worker(lifecycle, monkeypatch):
    module.CacheSyncTCPServer.side_effect = OSError("bind failed")
    monkeypatch.setattr(CacheSyncManager, "start", threading.Thread.start)
    manager = lifecycle.build()
    try:
        assert not manager.sidecar_available
        CacheSyncManager.stop()
        assert manager._shutdown.is_set()
        assert not manager.is_alive()
        assert CacheSyncManager._instance is None
    finally:
        manager._shutdown.set()
        manager.join(timeout=2)
        assert not manager.is_alive()


def test_serving_thread_start_failure_closes_socket_without_shutdown(lifecycle):
    thread = Mock(ident=None)
    thread.start.side_effect = RuntimeError("start failed")
    thread.is_alive.return_value = False
    module.Thread.side_effect = None
    module.Thread.return_value = thread
    manager = lifecycle.build()
    server = lifecycle.servers[0]
    assert not manager.sidecar_available
    server.server_close.assert_called_once_with()
    server.shutdown.assert_not_called()
    assert manager._server is manager._server_thread is None
    CacheSyncManager.stop()
    server.shutdown.assert_not_called()
    assert CacheSyncManager._instance is None


@pytest.mark.parametrize("owned_thread", ["worker", "server"])
def test_join_timeout_retains_ownership_until_thread_terminates(lifecycle, monkeypatch, owned_thread):
    manager = lifecycle.build()
    thread = manager if owned_thread == "worker" else manager._server_thread
    if owned_thread == "worker":
        monkeypatch.setattr(manager, "_ident", 456)
    monkeypatch.setattr(thread, "join", Mock())
    monkeypatch.setattr(thread, "is_alive", Mock(return_value=True))
    with pytest.raises(RuntimeError, match="did not terminate"):
        CacheSyncManager.stop()
    thread.join.assert_called_once_with(timeout=2.0)
    assert CacheSyncManager._instance is manager
    if owned_thread == "server":
        assert manager._server_thread is thread
    with pytest.raises(RuntimeError, match="stopping"):
        lifecycle.build()
    thread.is_alive.return_value = False
    CacheSyncManager.stop()
    assert CacheSyncManager._instance is None
    assert lifecycle.build() is not manager


@pytest.mark.parametrize("owned_thread", ["worker", "server"])
def test_stop_from_owned_thread_rejects_self_join_and_retains_manager(lifecycle, monkeypatch, owned_thread):
    manager = lifecycle.build()
    thread = manager if owned_thread == "worker" else manager._server_thread
    monkeypatch.setattr(module, "current_thread", lambda: thread)
    with pytest.raises(RuntimeError, match="own thread"):
        CacheSyncManager.stop()
    assert CacheSyncManager._instance is manager
    manager._server.shutdown.assert_not_called()
    monkeypatch.setattr(module, "current_thread", threading.current_thread)
    CacheSyncManager.stop()
    assert CacheSyncManager._instance is None


def test_unstarted_threads_are_not_joined(lifecycle):
    manager = lifecycle.build()
    thread = manager._server_thread
    thread.ident = None
    server = manager._server
    manager.shutdown()
    thread.join.assert_not_called()
    server.shutdown.assert_not_called()
    server.server_close.assert_called_once_with()
    assert manager._shutdown.is_set()
    assert manager._server_thread is None
    CacheSyncManager.stop()


@pytest.mark.parametrize("failure", [False, True])
def test_build_serializes_with_stop_and_retains_failed_stop(lifecycle, failure):
    manager = lifecycle.build()
    stopping = threading.Event()
    build_entered = threading.Event()
    release = threading.Event()

    def shutdown_server():
        stopping.set()
        assert release.wait(2)
        if failure:
            raise OSError("stop failed")

    def build():
        build_entered.set()
        return lifecycle.build()

    manager._server.shutdown.side_effect = shutdown_server
    with ThreadPoolExecutor(max_workers=2) as pool:
        stop = pool.submit(CacheSyncManager.stop)
        try:
            assert stopping.wait(2)
            build_result = pool.submit(build)
            assert build_entered.wait(2)
            assert CacheSyncManager._lock.locked()
            assert not build_result.done()
            assert len(lifecycle.servers) == 1
        finally:
            release.set()
        if failure:
            with pytest.raises(OSError, match="stop failed"):
                stop.result(timeout=2)
            with pytest.raises(RuntimeError, match="stopping"):
                build_result.result(timeout=2)
            assert CacheSyncManager._instance is manager
            manager._server.shutdown.side_effect = None
            CacheSyncManager.stop()
        else:
            stop.result(timeout=2)
            assert build_result.result(timeout=2) is not manager
            assert len(lifecycle.servers) == 2
            CacheSyncManager.stop()


def test_manager_creation_and_listener_logs_are_distinct(lifecycle, caplog, capsys):
    caplog.set_level(logging.DEBUG, logger=module.log.name)
    manager = lifecycle.build()
    assert lifecycle.build() is manager
    assert CacheSyncManager.build(enabled=False, is_server=True, sync_port=5210) is None
    messages = [message for message in caplog.messages if "manager created" in message]
    assert len(messages) == 1
    assert f"manager={id(manager):#x}" in messages[0]
    assert "cache listening on port 5210" in caplog.text
    assert "*** Starting cacher ***" not in capsys.readouterr().out
    CacheSyncManager.stop()


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


def test_sidecar_payload_syncs_config_json_files(tmp_path) -> None:
    local = CacheSyncPaths(
        tmp_path / "local_info",
        tmp_path / "local_images",
        tmp_path / "local_config",
    )
    remote = CacheSyncPaths(
        tmp_path / "remote_info",
        tmp_path / "remote_images",
        tmp_path / "remote_config",
    )
    for path in local.iter_existing_or_configured():
        path.mkdir(parents=True)
    for path in remote.iter_existing_or_configured():
        path.mkdir(parents=True)

    (local.config / "accessory_config.json").write_text('{"accessories": []}', encoding="utf-8")
    (remote.config / "stale.json").write_text("stale", encoding="utf-8")

    payload = SidecarCacheTransport.build_payload(local, remote, delete=True)
    SidecarCacheTransport.apply_payload(remote, payload)

    assert (remote.config / "accessory_config.json").read_text(encoding="utf-8") == '{"accessories": []}'
    assert not (remote.config / "stale.json").exists()


def test_config_sync_ignores_non_json_and_nested_files(tmp_path) -> None:
    local = CacheSyncPaths(None, None, tmp_path / "local_config")
    remote = CacheSyncPaths(None, None, tmp_path / "remote_config")
    local.config.mkdir(parents=True)
    remote.config.mkdir(parents=True)
    (local.config / "accessory_config.json").write_text("{}", encoding="utf-8")
    (local.config / "notes.txt").write_text("ignore", encoding="utf-8")
    (local.config / "nested").mkdir()
    (local.config / "nested" / "nested.json").write_text("ignore", encoding="utf-8")
    (remote.config / "keep.txt").write_text("keep", encoding="utf-8")
    (remote.config / "nested").mkdir()
    (remote.config / "nested" / "keep.json").write_text("keep", encoding="utf-8")

    payload = SidecarCacheTransport.build_payload(local, remote, delete=True)
    SidecarCacheTransport.apply_payload(remote, payload)

    assert payload["caches"] == ["config"]
    assert [item["path"] for item in payload["files"]] == ["accessory_config.json"]
    assert (remote.config / "accessory_config.json").read_text(encoding="utf-8") == "{}"
    assert (remote.config / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (remote.config / "nested" / "keep.json").read_text(encoding="utf-8") == "keep"


def test_config_sync_handles_missing_directories(tmp_path) -> None:
    local = CacheSyncPaths(None, None, tmp_path / "missing_local_config")
    remote = CacheSyncPaths(None, None, tmp_path / "missing_remote_config")

    payload = SidecarCacheTransport.build_payload(local, remote, delete=True)
    SidecarCacheTransport.apply_payload(remote, payload)

    assert payload == {"delete": True, "caches": ["config"], "files": []}
    assert not local.config.exists()
    assert not remote.config.exists()


def test_sync_skips_config_when_peer_does_not_advertise_it(tmp_path) -> None:
    local = CacheSyncPaths(
        tmp_path / "local_info",
        tmp_path / "local_images",
        tmp_path / "local_config",
    )
    remote = CacheSyncPaths(
        tmp_path / "remote_info",
        tmp_path / "remote_images",
        None,
    )
    for path in local.iter_existing_or_configured():
        path.mkdir(parents=True)
    for path in remote.iter_existing_or_configured():
        path.mkdir(parents=True)

    (local.engine_info / "abc.json").write_text("engine", encoding="utf-8")
    (local.config / "accessory_config.json").write_text("accessory", encoding="utf-8")

    payload = SidecarCacheTransport.build_payload(local, remote, delete=False)

    assert payload["caches"] == ["engine_info", "engine_images"]
    assert {item["cache"] for item in payload["files"]} == {"engine_info"}


def test_apply_payload_preserves_config_when_payload_does_not_include_config_cache(tmp_path) -> None:
    local = CacheSyncPaths(
        tmp_path / "local_info",
        tmp_path / "local_images",
        tmp_path / "local_config",
    )
    for path in local.iter_existing_or_configured():
        path.mkdir(parents=True)

    (local.config / "accessory_config.json").write_text("keep", encoding="utf-8")
    payload = {
        "delete": True,
        "caches": ["engine_info", "engine_images"],
        "files": [],
    }

    SidecarCacheTransport.apply_payload(local, payload)

    assert (local.config / "accessory_config.json").read_text(encoding="utf-8") == "keep"


def test_cache_sync_paths_decode_peer_without_config(tmp_path) -> None:
    decoded = CacheSyncPaths.from_wire_dict(
        {
            "engine_info": str(tmp_path / "engine_info"),
            "engine_images": str(tmp_path / "engine_images"),
        }
    )

    assert decoded.engine_info == (tmp_path / "engine_info").resolve()
    assert decoded.engine_images == (tmp_path / "engine_images").resolve()
    assert decoded.config is None


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
    paths = CacheSyncPaths(tmp_path / "engine_info", tmp_path / "engine_images", tmp_path / "config")

    decoded = CacheSyncPaths.from_wire_dict(paths.as_wire_dict())

    assert decoded == paths


def test_cache_manifest_uses_config_cache_key(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "cache" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "accessory_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("src.pytrain.db.prod_info.ENGINE_INFO_CACHE_DIR", "", raising=True)
    monkeypatch.setattr("src.pytrain.db.prod_info.ENGINE_IMAGES_CACHE_DIR", "", raising=True)
    monkeypatch.setattr("src.pytrain.db.cache_sync.CONFIG_CACHE_DIR", str(config_dir), raising=True)

    manifest = CacheSyncManager._cache_manifest()

    assert manifest[0][0] == "config/accessory_config.json"


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
