"""Headless regression tests for the Flatpak-only Admin update indicator."""

from threading import RLock
from types import SimpleNamespace

import src.pytrain.gui.controller.admin_panel as mod


def _panel(tag="v2.12.4-3"):
    panel = mod.AdminPanel.__new__(mod.AdminPanel)
    panel._flatpak_tag = tag
    panel._flatpak_update_lock = RLock()
    panel._flatpak_update_status = None
    panel._flatpak_update_available = False
    panel._flatpak_update_running = False
    panel._flatpak_update_after_id = None
    panel._flatpak_update_generation = 0
    panel._wifi_refresh_after_id = None
    panel._flatpak_update_button = SimpleNamespace(text="Update PyTrain", enable=lambda: None, disable=lambda: None)
    panel._admin_buttons = {}
    panel._overlay = SimpleNamespace(visible=True, tk=SimpleNamespace(after=lambda *_: "poll-1"))
    return panel


def test_available_release_changes_button_label(monkeypatch):
    panel = _panel()
    monkeypatch.setattr(
        mod,
        "check_flatpak_update",
        lambda tag: SimpleNamespace(available=True, available_tag="v2.12.4-4"),
    )
    panel._query_flatpak_update()
    panel._refresh_flatpak_update_status()
    assert panel._flatpak_update_button.text == "Update available!"
    assert panel._flatpak_update_after_id is None


def test_up_to_date_keeps_original_label(monkeypatch):
    panel = _panel()
    monkeypatch.setattr(
        mod,
        "check_flatpak_update",
        lambda tag: SimpleNamespace(available=False, available_tag=tag),
    )
    panel._query_flatpak_update()
    panel._refresh_flatpak_update_status()
    assert panel._flatpak_update_button.text == "Update PyTrain"


def test_network_error_does_not_claim_an_update(monkeypatch):
    panel = _panel()

    def fail(_tag):
        raise OSError("offline")

    monkeypatch.setattr(mod, "check_flatpak_update", fail)
    panel._query_flatpak_update()
    panel._refresh_flatpak_update_status()
    assert panel._flatpak_update_status == "Update check unavailable"
    assert panel._flatpak_update_button.text == "Update PyTrain"


def test_non_flatpak_never_starts_update_check(monkeypatch):
    panel = _panel(tag=None)

    def unexpected(*_args, **_kwargs):
        raise AssertionError("No worker should start outside the Flatpak")

    monkeypatch.setattr(mod, "Thread", unexpected)
    panel._start_flatpak_update_check()
    assert panel._flatpak_update_running is False


def test_single_flight_and_cached_result(monkeypatch):
    panel = _panel()
    started = []

    class FakeThread:
        def __init__(self, *, target, daemon):
            started.append((target, daemon))

        def start(self):
            pass

    monkeypatch.setattr(mod, "Thread", FakeThread)
    panel._start_flatpak_update_check()
    panel._start_flatpak_update_check()
    assert len(started) == 1
    assert started[0][1] is True
    panel._flatpak_update_status = "Up to date"
    panel._flatpak_update_running = False
    panel._start_flatpak_update_check()
    assert len(started) == 1


def test_pending_update_schedules_tk_poll():
    panel = _panel()
    panel._refresh_flatpak_update_status()
    assert panel._flatpak_update_after_id == "poll-1"


def test_pending_update_polls_before_overlay_is_visible():
    """Overlay getter runs before the popup is shown; polling must still start."""
    panel = _panel()
    panel._overlay.visible = False
    panel._refresh_flatpak_update_status()
    assert panel._flatpak_update_after_id == "poll-1"


def test_reopening_admin_starts_fresh_background_check(monkeypatch):
    panel = _panel()
    started = []

    class FakeThread:
        def __init__(self, *, target, daemon):
            assert daemon is True
            self.target = target

        def start(self):
            started.append(self.target)

    monkeypatch.setattr(mod, "Thread", FakeThread)
    panel._start_flatpak_update_check()
    assert len(started) == 1
    panel._flatpak_update_status = "Up to date"
    panel._flatpak_update_running = False
    panel._start_flatpak_update_check()
    assert len(started) == 1  # Same opening: no duplicate query.

    panel._on_popup_close()
    assert panel._flatpak_update_status is None
    assert panel._flatpak_update_available is False
    panel._start_flatpak_update_check()
    assert len(started) == 2  # New opening: fresh background query.


def test_stale_update_result_cannot_override_new_opening(monkeypatch):
    panel = _panel()
    monkeypatch.setattr(
        mod,
        "check_flatpak_update",
        lambda tag: SimpleNamespace(available=True, available_tag="v2.12.4-4"),
    )
    old_generation = panel._flatpak_update_generation
    panel._on_popup_close()
    panel._query_flatpak_update(old_generation)
    assert panel._flatpak_update_status is None
    assert panel._flatpak_update_available is False
    panel._query_flatpak_update(panel._flatpak_update_generation)
    assert panel._flatpak_update_available is True
