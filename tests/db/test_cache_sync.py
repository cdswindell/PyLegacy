from pathlib import Path

from src.pytrain.db.cache_sync import CacheSyncManager, CacheSyncPaths, RsyncCacheTransport


def test_rsync_push_command_without_delete(monkeypatch) -> None:
    transport = RsyncCacheTransport(user="pi", ssh_opts="", timeout=1)
    monkeypatch.setattr(transport, "_rsync", "rsync", raising=True)

    cmd = transport.build_command(
        "192.168.1.20",
        Path("/local/cache/engine_info"),
        Path("/remote/cache/engine_info"),
        cache_name="engine_info",
        delete=False,
    )

    assert cmd == [
        "rsync",
        "-az",
        "/local/cache/engine_info/",
        "pi@192.168.1.20:/remote/cache/engine_info/",
    ]


def test_rsync_default_ssh_options_accept_new_host_keys(monkeypatch) -> None:
    transport = RsyncCacheTransport(user="", timeout=1)
    monkeypatch.setattr(transport, "_rsync", "rsync", raising=True)

    cmd = transport.build_command(
        "192.168.1.20",
        Path("/local/cache/engine_info"),
        Path("/remote/cache/engine_info"),
        cache_name="engine_info",
        delete=False,
    )

    assert cmd == [
        "rsync",
        "-az",
        "-e",
        "ssh -oBatchMode=yes -oConnectTimeout=5 -oStrictHostKeyChecking=accept-new",
        "/local/cache/engine_info/",
        "192.168.1.20:/remote/cache/engine_info/",
    ]


def test_rsync_server_image_command_deletes_but_protects_custom_images(monkeypatch) -> None:
    transport = RsyncCacheTransport(user="", ssh_opts="-oBatchMode=yes", timeout=1)
    monkeypatch.setattr(transport, "_rsync", "rsync", raising=True)

    cmd = transport.build_command(
        "client.local",
        Path("/local/cache/engine_images"),
        Path("/remote/cache/engine_images"),
        cache_name="engine_images",
        delete=True,
    )

    assert cmd == [
        "rsync",
        "-az",
        "-e",
        "ssh -oBatchMode=yes",
        "--delete",
        "--filter",
        "P /[0-9]*.jpg",
        "/local/cache/engine_images/",
        "client.local:/remote/cache/engine_images/",
    ]


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
