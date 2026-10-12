"""Flatpak admin actions must never control the remote PyTrain server."""

from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.admin_panel as mod

Sync = mod.TMCC1SyncCommandEnum


def _panel(tag):
    panel = mod.AdminPanel.__new__(mod.AdminPanel)
    panel._flatpak_tag = tag
    panel._scope_btns = SimpleNamespace(value="0")
    return panel


def test_flatpak_restart_requests_host_relaunch(monkeypatch):
    panel = _panel("v2.12.4")
    calls = []

    def exit_with(code):
        calls.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(mod.os, "_exit", exit_with)
    with pytest.raises(SystemExit, match="75"):
        panel.do_admin_command(Sync.RESTART)
    assert calls == [75]


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
