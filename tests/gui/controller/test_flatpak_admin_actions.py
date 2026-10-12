"""Flatpak admin actions must never control the remote PyTrain server."""

from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.admin_panel as mod

Sync = mod.TMCC1SyncCommandEnum


def _panel(tag):
    panel = mod.AdminPanel.__new__(mod.AdminPanel)
    panel._flatpak_tag = tag
    panel._flatpak_update_available = False
    panel._scope_btns = SimpleNamespace(value="0")
    return panel


def test_flatpak_restart_requests_clean_local_shutdown():
    panel = _panel("v2.12.4")
    calls = []
    panel._pytrain = SimpleNamespace(request_local_restart=lambda: calls.append("restart"))
    panel.do_admin_command(Sync.RESTART)
    assert calls == ["restart"]


@pytest.mark.parametrize("command", [Sync.REBOOT, Sync.SHUTDOWN])
def test_flatpak_power_commands_are_noops(command):
    panel = _panel("v2.12.4")
    panel.do_admin_command(command)


def test_conda_restart_uses_existing_dispatch(monkeypatch):
    panel = _panel(None)
    calls = []
    panel._pytrain = SimpleNamespace(do_admin_cmd=lambda *args: calls.append(args))

    class ImmediateThread:
        def __init__(self, *, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(mod, "Thread", ImmediateThread)
    panel.do_admin_command(Sync.RESTART)
    assert calls == [(Sync.RESTART, ["me"])]


def test_flatpak_update_requests_host_install_then_local_restart(monkeypatch, tmp_path):
    panel = _panel("v2.12.6")
    panel._flatpak_update_available = True
    calls = []
    marker = tmp_path / "pycab-update-request"
    monkeypatch.setattr(mod, "request_flatpak_update", lambda: (marker.write_text("update\\n"), marker)[1])
    panel._pytrain = SimpleNamespace(request_local_restart=lambda: calls.append("restart"))
    panel.do_admin_command(Sync.UPDATE)
    assert marker.read_text() == "update\\n"
    assert calls == ["restart"]


def test_flatpak_update_without_available_release_does_nothing():
    panel = _panel("v2.12.6")
    panel.do_admin_command(Sync.UPDATE)
