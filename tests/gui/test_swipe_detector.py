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

from src.pytrain.gui.components.swipe_detector import SwipeDetector


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
