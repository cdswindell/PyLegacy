from __future__ import annotations

from src.pytrain.gui.components.hold_button import HoldButton


class DummyHoldButton(HoldButton):
    @property
    def enabled(self) -> bool:
        return self._enabled_value


def make_button(enabled: bool) -> DummyHoldButton:
    button = DummyHoldButton.__new__(DummyHoldButton)
    button._enabled_value = enabled
    button._pressed = False
    button._repeating = False
    button._progress_start = None
    return button


def test_press_event_does_not_start_progress_when_disabled() -> None:
    button = make_button(enabled=False)
    calls = []
    button._cancel_after = lambda: calls.append("cancel_after")
    button._stop_progress = lambda: calls.append("stop_progress")
    button._start_progress = lambda: calls.append("start_progress")

    button._on_press_event()

    assert button._pressed is False
    assert button._repeating is False
    assert calls == ["cancel_after", "stop_progress"]


def test_progress_does_not_start_when_disabled() -> None:
    button = make_button(enabled=False)
    button._show_hold_progress = True
    button.hold_threshold = 1.0
    button._ensure_overlay = lambda: (_ for _ in ()).throw(AssertionError("overlay should not be created"))

    button._start_progress()

    assert button._progress_start is None


def test_progress_tick_stops_existing_progress_when_disabled() -> None:
    button = make_button(enabled=False)
    button._pressed = True
    button._repeating = True
    button._progress_start = 1.0
    calls = []
    button._stop_progress = lambda: calls.append("stop_progress")
    button._cancel_after = lambda: calls.append("cancel_after")
    button._set_overlay_fraction = lambda frac: (_ for _ in ()).throw(AssertionError("progress should not be updated"))

    button._progress_tick()

    assert button._pressed is False
    assert button._repeating is False
    assert calls == ["stop_progress", "cancel_after"]
