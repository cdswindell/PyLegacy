#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from types import SimpleNamespace

import pytest

from src.pytrain.gui.components.swipe_detector import SwipeDetector, event_screen_y, event_targets


class _HookWidget:
    """Stands in for a guizero widget that has EventsMixin (Picture, PushButton...)."""

    when_left_button_pressed = property(lambda s: None, lambda s, v: s.hooks.__setitem__("press", v))
    when_mouse_moved = property(lambda s: None, lambda s, v: s.hooks.__setitem__("move", v))
    when_left_button_released = property(lambda s: None, lambda s, v: s.hooks.__setitem__("release", v))

    def __init__(self) -> None:
        self.hooks = {}
        self.tk = SimpleNamespace(
            after=lambda _ms, cb: cb(),
            bind=lambda *a, **k: pytest.fail("a widget with guizero hooks must not be tk.bind()ed"),
            winfo_width=lambda: 400,
            winfo_height=lambda: 200,
            winfo_rootx=lambda: 880,
            winfo_rooty=lambda: 300,
        )

    @property
    def press(self):
        return self.hooks["press"]

    @property
    def release(self):
        return self.hooks["release"]

    @property
    def move(self):
        return self.hooks["move"]


class _ContainerWidget:
    """Stands in for a guizero container (Box), which has NO EventsMixin hooks."""

    def __init__(self) -> None:
        self.binds = {}
        self.tk = SimpleNamespace(
            after=lambda _ms, cb: cb(),
            bind=lambda seq, fn, add=None: self.binds.__setitem__(seq, fn),
            winfo_width=lambda: 900,
            winfo_height=lambda: 200,
            winfo_rootx=lambda: 640,
            winfo_rooty=lambda: 300,
        )

    @property
    def press(self):
        return self.binds["<ButtonPress-1>"]

    @property
    def release(self):
        return self.binds["<ButtonRelease-1>"]

    @property
    def move(self):
        return self.binds["<Motion>"]


def _detector(widget):
    detector = SwipeDetector(widget)
    detector.fired = []
    detector.on_swipe_left = lambda: detector.fired.append("LEFT")
    detector.on_swipe_right = lambda: detector.fired.append("RIGHT")
    return detector


def _swipe(detector, widget, dx, dy=0, duration=0.05, monkeypatch=None):
    # Drive the *bound* handlers, so the binding path itself is under test.
    times = iter([100.0, 100.0 + duration])
    monkeypatch.setattr("time.monotonic", lambda: next(times))
    widget.press(SimpleNamespace(x=320, y=100))
    widget.move(SimpleNamespace(x=320 + dx // 2, y=100 + dy // 2))
    widget.release(SimpleNamespace(x=320 + dx, y=100 + dy))


def test_widget_with_guizero_hooks_uses_them() -> None:
    widget = _HookWidget()
    _detector(widget)

    # Picture and friends inherit EventsMixin, so the hooks are the binding surface.
    assert sorted(widget.hooks) == ["move", "press", "release"]


def test_container_without_hooks_falls_back_to_tk_bind() -> None:
    widget = _ContainerWidget()
    _detector(widget)

    # guizero's ContainerWidget (Box) has no EventsMixin. Assigning the hooks would
    # silently create a plain attribute and bind nothing, so the detector must bind
    # the Tk widget directly -- this is what makes a swipe beside the image work.
    assert sorted(widget.binds) == ["<ButtonPress-1>", "<ButtonRelease-1>", "<Motion>"]


@pytest.mark.parametrize("widget_factory", [_HookWidget, _ContainerWidget])
def test_swipe_direction_dispatches_on_either_binding_path(widget_factory, monkeypatch) -> None:
    widget = widget_factory()
    detector = _detector(widget)

    _swipe(detector, widget, dx=-300, monkeypatch=monkeypatch)
    _swipe(detector, widget, dx=300, monkeypatch=monkeypatch)

    assert detector.fired == ["LEFT", "RIGHT"]


@pytest.mark.parametrize("widget_factory", [_HookWidget, _ContainerWidget])
def test_swipe_ending_outside_the_widget_still_registers(widget_factory, monkeypatch) -> None:
    widget = widget_factory()
    detector = _detector(widget)

    # Tk reports a negative x once the finger leaves the left edge; the gesture is
    # still a swipe.
    _swipe(detector, widget, dx=-500, monkeypatch=monkeypatch)

    assert detector.fired == ["LEFT"]


def test_swipe_rejected_when_too_short(monkeypatch) -> None:
    widget = _HookWidget()
    detector = _detector(widget)

    _swipe(detector, widget, dx=-30, monkeypatch=monkeypatch)

    assert detector.fired == []


def test_swipe_rejected_when_too_slow(monkeypatch) -> None:
    widget = _HookWidget()
    detector = _detector(widget)

    _swipe(detector, widget, dx=-300, duration=0.75, monkeypatch=monkeypatch)

    assert detector.fired == []


def test_swipe_rejected_when_mostly_vertical(monkeypatch) -> None:
    widget = _HookWidget()
    detector = _detector(widget)

    _swipe(detector, widget, dx=-60, dy=-200, monkeypatch=monkeypatch)

    assert detector.fired == []


def test_event_screen_y_reads_both_event_shapes() -> None:
    # guizero hooks deliver EventData (display_y); a direct Tk bind delivers the raw
    # event (y_root). A predicate keyed to only one of them silently rejects every
    # gesture from the other -- which is exactly how this went wrong.
    assert event_screen_y(SimpleNamespace(display_y=440)) == 440
    assert event_screen_y(SimpleNamespace(y_root=441)) == 441
    assert event_screen_y(SimpleNamespace(x=1, y=2)) is None


def test_event_targets_covers_guizero_and_tk_widgets() -> None:
    tk_widget = object()
    guizero_widget = SimpleNamespace(tk=tk_widget)

    # EventData.widget is the guizero widget; a raw Tk event's is the Tk widget.
    assert event_targets(SimpleNamespace(widget=guizero_widget)) == (guizero_widget, tk_widget)
    assert event_targets(SimpleNamespace(widget=tk_widget)) == (tk_widget, None)
    assert event_targets(SimpleNamespace()) == ()


def test_bind_directly_avoids_guizero_hooks_and_preserves_bindings() -> None:
    widget = _HookWidget()
    binds = {}
    widget.tk.bind = lambda seq, fn, add=None: binds.__setitem__(seq, add)

    SwipeDetector(widget, bind_directly=True)

    # guizero binds without add="+", so its hooks replace existing bindings for the
    # same sequence (<Button-1> and <ButtonPress-1> are one sequence in Tk). Direct
    # binding must be additive so a widget's other handlers survive.
    assert widget.hooks == {}
    assert sorted(binds) == ["<ButtonPress-1>", "<ButtonRelease-1>", "<Motion>"]
    assert set(binds.values()) == {"+"}


def test_should_start_predicate_ignores_gestures_outside_the_region(monkeypatch) -> None:
    widget = _ContainerWidget()
    seen = []
    detector = SwipeDetector(widget, should_start=lambda e: seen.append(e.y) or e.y < 100)
    detector.fired = []
    detector.on_swipe_left = lambda: detector.fired.append("LEFT")
    detector.on_swipe_right = lambda: detector.fired.append("RIGHT")

    # A container detector covers more than the region of interest (e.g. the whole
    # pane), so a press outside the band must drop the entire gesture -- including its
    # release, which must not be mistaken for a swipe.
    times = iter([100.0, 100.05, 200.0, 200.05])
    monkeypatch.setattr("time.monotonic", lambda: next(times))
    widget.press(SimpleNamespace(x=320, y=500))
    widget.release(SimpleNamespace(x=20, y=500))
    assert detector.fired == []

    widget.press(SimpleNamespace(x=320, y=50))
    widget.release(SimpleNamespace(x=20, y=50))
    assert detector.fired == ["LEFT"]
    assert seen == [500, 50]


def test_should_start_rejection_does_not_leave_a_stale_press(monkeypatch) -> None:
    widget = _ContainerWidget()
    detector = SwipeDetector(widget, should_start=lambda e: e.y < 100)
    detector.fired = []
    detector.on_swipe_right = lambda: detector.fired.append("RIGHT")

    times = iter([100.0, 100.05])
    monkeypatch.setattr("time.monotonic", lambda: next(times))
    widget.press(SimpleNamespace(x=10, y=500))  # rejected
    widget.release(SimpleNamespace(x=400, y=500))

    assert detector.start_x is None
    assert detector.fired == []


def test_long_press_suppresses_the_swipe(monkeypatch) -> None:
    widget = _HookWidget()
    detector = _detector(widget)
    long_presses = []
    detector.on_long_press = lambda: long_presses.append("LONG")

    times = iter([100.0, 100.2])
    monkeypatch.setattr("time.monotonic", lambda: next(times))
    widget.press(SimpleNamespace(x=320, y=100))
    detector._trigger_long_press()  # the timer would do this after long_press_time
    widget.release(SimpleNamespace(x=320 - 300, y=100))

    # A fired long press must not also be reported as a swipe. _on_release reads the
    # flag *before* cancelling the timer, because cancelling resets it.
    assert long_presses == ["LONG"]
    assert detector.fired == []
