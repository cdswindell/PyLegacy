"""Flatpak power commands affect remote nodes only when All is selected."""

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


def test_flatpak_all_scope_restart_dispatches_to_server_not_local():
    panel = _panel("v2.14.3")
    panel._scope_btns.value = "1"
    calls = []
    panel._pytrain = SimpleNamespace(request_local_restart=lambda: pytest.fail("local restart bypasses server"))
    panel._gui = SimpleNamespace(do_tmcc_request=lambda cmd: calls.append(cmd))
    panel.do_admin_command(Sync.RESTART)
    assert calls == [Sync.RESTART]


@pytest.mark.parametrize("command", [Sync.REBOOT, Sync.SHUTDOWN])
def test_flatpak_local_power_commands_are_noops(command):
    panel = _panel("v2.12.4")
    panel._gui = SimpleNamespace(do_tmcc_request=lambda *_: pytest.fail("local power command forwarded"))
    panel.do_admin_command(command)


def test_conda_restart_uses_existing_dispatch(monkeypatch):
    panel = _panel(None)
    calls = []
    panel._pytrain = SimpleNamespace(is_server=False, do_admin_cmd=lambda *args: calls.append(args))

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
    monkeypatch.setattr(mod, "request_flatpak_update", lambda: (marker.write_text("update\n"), marker)[1])
    panel._pytrain = SimpleNamespace(request_local_restart=lambda: calls.append("restart"))
    panel.do_admin_command(Sync.UPDATE)
    assert marker.read_text() == "update\n"
    assert calls == ["restart"]


def test_flatpak_update_without_available_release_does_nothing():
    panel = _panel("v2.12.6")
    panel.do_admin_command(Sync.UPDATE)


@pytest.mark.parametrize("command", [Sync.REBOOT, Sync.SHUTDOWN])
def test_flatpak_all_scope_forwards_power_command(command):
    panel = _panel("v2.12.6")
    panel._scope_btns.value = "1"
    calls = []
    panel._gui = SimpleNamespace(do_tmcc_request=lambda cmd: calls.append(cmd))
    panel.do_admin_command(command)
    assert calls == [command]


def test_flatpak_scope_change_toggles_power_buttons():
    panel = _panel("v2.12.6")
    calls = []

    def button(name):
        return SimpleNamespace(enable=lambda: calls.append((name, True)), disable=lambda: calls.append((name, False)))

    panel._reboot_btn = button("reboot")
    panel._shutdown_btn = button("shutdown")
    panel._refresh_flatpak_power_buttons()
    assert calls == [("reboot", False), ("shutdown", False)]
    calls.clear()
    panel._scope_btns.value = "1"
    panel._refresh_flatpak_power_buttons()
    assert calls == [("reboot", True), ("shutdown", True)]


def test_initially_disabled_admin_button_remains_registered_for_chords(monkeypatch):
    """Flatpak power buttons become chord-accessible after switching to All."""
    panel = _panel("v2.12.6")
    panel._admin_buttons = {}
    events = []

    class FakeHoldButton:
        enabled = True

        def disable(self):
            self.enabled = False

        def enable(self):
            self.enabled = True

        def begin_hold(self):
            if self.enabled:
                events.append("held")

    button = FakeHoldButton()
    monkeypatch.setattr(panel, "_hold_button", lambda *_args, **_kwargs: button)
    result = panel._admin_hold_button(
        None,
        enabled=False,
        on_hold=(panel.do_admin_command, [Sync.REBOOT]),
    )
    assert result is button
    assert panel._admin_buttons["REBOOT"] is button
    assert button.enabled is False
    button.begin_hold()
    assert events == []
    button.enable()
    button.begin_hold()
    assert events == ["held"]


@pytest.mark.parametrize("tag", [None, "v2.12.13"])
@pytest.mark.parametrize("scope", ["0", "1"])
def test_server_gui_quit_broadcasts_and_closes_without_tmcc_or_restart(tag, scope):
    panel = _panel(tag)
    panel._scope_btns.value = scope
    calls = []
    panel._pytrain = SimpleNamespace(
        is_server=True,
        request_gui_server_quit=lambda: calls.append("broadcast"),
    )
    panel._gui = SimpleNamespace(
        close=lambda: calls.append("close"),
        do_tmcc_request=lambda *_: pytest.fail("server Quit must not use TMCC GUI queue"),
    )
    panel.do_admin_command(Sync.QUIT)
    assert calls == ["broadcast", "close"]


@pytest.mark.parametrize("command", [Sync.RESTART, Sync.UPDATE, Sync.UPGRADE, Sync.REBOOT, Sync.SHUTDOWN])
@pytest.mark.parametrize("scope", ["0", "1"])
def test_nonflatpak_server_action_always_broadcasts_and_closes_gui(command, scope):
    panel = _panel(None)
    panel._scope_btns.value = scope
    calls = []
    panel._pytrain = SimpleNamespace(
        is_server=True,
        request_gui_server_action=lambda action, *, broadcast: calls.append(("action", action, broadcast)),
    )
    panel._gui = SimpleNamespace(
        close=lambda: calls.append(("close",)),
        do_tmcc_request=lambda *_: pytest.fail("server action must not enter TMCC queue"),
    )
    panel.do_admin_command(command)
    assert calls == [("action", command, True), ("close",)]


def test_flatpak_server_restart_still_uses_launcher_path():
    panel = _panel("v2.12.13")
    calls = []
    panel._pytrain = SimpleNamespace(
        is_server=True,
        request_local_restart=lambda: calls.append("flatpak-restart"),
        request_gui_server_action=lambda *_args, **_kwargs: pytest.fail("Flatpak must not use GUI server action"),
    )
    panel.do_admin_command(Sync.RESTART)
    assert calls == ["flatpak-restart"]
