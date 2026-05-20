import logging
from types import SimpleNamespace

from src.pytrain.cli import cache as mod


def test_cache_sync_command_skips_gracefully_when_manager_unavailable(monkeypatch, caplog) -> None:
    cmd = object.__new__(mod.CacheCmd)
    cmd._cli = SimpleNamespace(cache_command="sync")
    cmd._pytrain = SimpleNamespace(is_client=True)

    monkeypatch.setattr(mod.CacheCmd, "wait_for_sync", lambda self: None)
    monkeypatch.setattr(mod.CacheSyncManager, "current", classmethod(lambda cls: None))

    with caplog.at_level(logging.WARNING):
        cmd.send()

    assert "connected server does not advertise cache sync support" in caplog.text
