from __future__ import annotations

from threading import Condition, RLock
from types import SimpleNamespace
from typing import Callable

import pytest

import src.pytrain.gui.components.hold_button as mod
from src.pytrain.gui.components.hold_button import HoldButton


class FakeTextVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = str(value)


class FakeTk:
    def __init__(
        self,
        *,
        state: str = "normal",
        background: str = "white",
        foreground: str = "black",
        activebackground: str = "darkgrey",
    ) -> None:
        self.values = {
            "state": state,
            "background": background,
            "bg": background,
            "foreground": foreground,
            "fg": foreground,
            "activebackground": activebackground,
            "activeforeground": foreground,
            "selectcolor": background,
            "troughcolor": background,
            "font": "TkDefaultFont",
            "image": "",
            "compound": "",
        }
        self.bindings: dict[str, list[Callable]] = {}
        self.config_calls: list[dict[str, str]] = []
        self.after_calls: list[tuple[int, Callable]] = []
        self.after_cancel_calls: list[str] = []

    def keys(self):
        return self.values.keys()

    def __getitem__(self, key: str):
        return self.values[key]

    def __setitem__(self, key: str, value):
        self._set_value(key, value)

    def cget(self, key: str):
        return self.values[key]

    def config(self, **kwargs) -> None:
        self.config_calls.append(dict(kwargs))
        for key, value in kwargs.items():
            self._set_value(key, value)

    def bind(self, sequence: str, func: Callable, add: str | None = None) -> None:
        self.bindings.setdefault(sequence, []).append(func)

    def after(self, delay_ms: int, func: Callable) -> str:
        self.after_calls.append((delay_ms, func))
        return f"after-{len(self.after_calls)}"

    def after_cancel(self, after_id: str) -> None:
        self.after_cancel_calls.append(after_id)

    # Geometry Tk reports. `unmapped` mimics a widget Tk has not laid out yet, which
    # reports 1x1 until an update_idletasks forces a geometry pass.
    unmapped: bool = False
    idletasks_calls: int = 0

    def update_idletasks(self) -> None:
        self.idletasks_calls = self.idletasks_calls + 1
        self.unmapped = False

    # -- geometry, for _pointer_outside ------------------------------------------------
    # The button occupies (10, 20) to (110, 60) in root coordinates; move `pointer` to
    # place the finger inside or outside it.
    pointer: tuple[int, int] | None = (50, 40)

    def winfo_pointerxy(self):
        if self.pointer is None:
            raise RuntimeError("no pointer")
        return self.pointer

    @staticmethod
    def winfo_rootx() -> int:
        return 10

    @staticmethod
    def winfo_rooty() -> int:
        return 20

    def winfo_width(self) -> int:
        return 1 if self.unmapped else 100

    def winfo_height(self) -> int:
        return 1 if self.unmapped else 40

    def _set_value(self, key: str, value) -> None:
        self.values[key] = value
        if key == "bg":
            self.values["background"] = value
        elif key == "background":
            self.values["bg"] = value
        elif key == "fg":
            self.values["foreground"] = value
        elif key == "foreground":
            self.values["fg"] = value


class DummyHoldButton(HoldButton):
    @property
    def enabled(self) -> bool:
        return self._enabled_value

    def _get_tk_config(self, key: str, default: bool = False):
        return self.tk[key]

    def _set_tk_config(self, keys, value) -> None:
        if isinstance(keys, str):
            keys = [keys]
        for key in keys:
            self.tk[key] = value


def make_button(enabled: bool, *, text: str = "Hold") -> DummyHoldButton:
    button = DummyHoldButton.__new__(DummyHoldButton)
    button._enabled_value = enabled
    button._tk = FakeTk(state="normal" if enabled else "disabled")
    button._text = FakeTextVar(text)
    button._cv = Condition(RLock())
    button._image = None
    button._normal_bg = "white"
    button._normal_fg = "black"
    button._normal_text_bg = "white"
    button._normal_text_fg = "black"
    button._normal_img = None
    button._inverted_img = None
    button._hover_normal_bg = None
    button._hover_active_bg = None
    button.hold_threshold = 1.0
    button.repeat_interval = 0.2
    button.debounce_ms = 80
    button._press_time = None
    button._pressed = False
    button._held = False
    button._repeating = False
    button._after_id = None
    button._handled_hold = False
    button._handled_flash = False
    button._flash_requested = False
    button._show_hold_progress = False
    button._progress_update_ms = 40
    button._progress_fill_color = "darkgrey"
    button._critical_fill_color = "darkgrey"
    button._progress_empty_color = None
    button._progress_keep_full_until_release = True
    button._progress_start = None
    button._progress_after_id = None
    button._progress_canvas = None
    button._progress_rect = None
    button._progress_bg_rect = None
    button._progress_text_item = None
    button._overlay_visible = False
    button._saved_button_text = None
    button._cancel_on_leave = True
    button._overlay_geometry = None
    button._leave_pending = False
    button._leave_after_id = None
    button._press_recovery_ms = 0  # opt-in; the recovery tests turn it on explicitly
    button._release_pending = False
    button._release_after_id = None
    button._held_elapsed = 0.0
    button._diag_label = text
    button._abandoned_at = None
    button._abandoned_banked = 0.0
    # _note_abandoned consults these; the recovery fixtures override them.
    button._on_hold = None
    button._on_press = None
    button._on_repeat = None
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


def test_press_event_starts_progress_and_hold_timer_when_enabled() -> None:
    button = make_button(enabled=True)
    calls = []
    button.hold_threshold = 1.25
    button._cancel_after = lambda: calls.append("cancel_after")
    button._start_progress = lambda: calls.append("start_progress")

    button._on_press_event()

    assert button._pressed is True
    assert button._held is False
    assert button._repeating is False
    assert button._handled_hold is False
    assert calls == ["start_progress", "cancel_after"]
    assert button._after_id == "after-1"
    assert button.tk.after_calls == [(1250, button._trigger_hold_or_repeat)]


def test_progress_does_not_start_when_disabled() -> None:
    button = make_button(enabled=False)
    button._show_hold_progress = True
    button.hold_threshold = 1.0
    button._ensure_overlay = lambda: (_ for _ in ()).throw(AssertionError("overlay should not be created"))

    button._start_progress()

    assert button._progress_start is None


def test_progress_starts_when_enabled() -> None:
    button = make_button(enabled=True)
    button._show_hold_progress = True
    calls = []
    button._cancel_progress_after = lambda: calls.append("cancel_progress_after")
    button._ensure_overlay = lambda: calls.append("ensure_overlay")
    button._position_overlay = lambda: calls.append("position_overlay")
    button._set_overlay_fraction = lambda frac: calls.append(("set_overlay_fraction", frac))
    button._schedule_progress_tick = lambda: calls.append("schedule_progress_tick")

    button._start_progress()

    assert button._progress_start is not None
    assert button._overlay_visible is True
    assert button._saved_button_text == "Hold"
    assert button.text == ""
    assert calls == [
        "cancel_progress_after",
        "ensure_overlay",
        "position_overlay",
        ("set_overlay_fraction", 0.0),
        "schedule_progress_tick",
    ]


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


def test_progress_tick_updates_and_reschedules_when_enabled() -> None:
    button = make_button(enabled=True)
    button._pressed = True
    button._progress_start = 1.0
    button._progress_fraction = lambda: 0.5
    calls = []
    button._set_overlay_fraction = lambda frac: calls.append(("set_overlay_fraction", frac))
    button._schedule_progress_tick = lambda: calls.append("schedule_progress_tick")

    button._progress_tick()

    assert button._pressed is True
    assert calls == [("set_overlay_fraction", 0.5), "schedule_progress_tick"]


def test_hover_enter_does_not_paint_disabled_button() -> None:
    button = make_button(enabled=False)
    button.tk["activebackground"] = "black"

    button._on_hover_enter()

    assert button.tk["background"] == "white"
    assert button._hover_normal_bg is None


def test_hover_enter_and_leave_paint_enabled_button() -> None:
    button = make_button(enabled=True)
    button.tk["activebackground"] = "black"

    button._on_hover_enter()

    assert button.tk["background"] == "black"
    assert button._hover_normal_bg == "white"
    assert button._hover_active_bg == "black"

    button._on_hover_leave()

    assert button.tk["background"] == "white"


def test_flash_press_does_not_paint_disabled_button() -> None:
    button = make_button(enabled=False)

    button.do_flash()
    button.tk.bindings["<ButtonPress-1>"][0](None)

    assert button.tk["background"] == "white"
    assert button.tk["foreground"] == "black"


def test_flash_press_paints_enabled_button() -> None:
    button = make_button(enabled=True)

    button.do_flash()
    button.tk.bindings["<ButtonPress-1>"][0](None)

    assert button.tk["background"] == "black"
    assert button.tk["foreground"] == "white"


def test_begin_hold_starts_the_same_hold_a_finger_would() -> None:
    # Synthetic input (a controller chord) drives the real widget, so the progress
    # animation and the hold_threshold timing have a single implementation.
    button = make_button(enabled=True)
    button.hold_threshold = 3.0
    calls = []
    button._start_progress = lambda: calls.append("start_progress")

    button.begin_hold()

    assert button._pressed is True
    assert calls == ["start_progress"]
    assert button.tk.after_calls[-1][0] == 3000  # on_hold scheduled at the threshold


def test_cancel_hold_stops_progress_without_firing_the_short_press() -> None:
    button = make_button(enabled=True)
    pressed_calls = []
    button.on_press = lambda: pressed_calls.append("press")
    calls = []
    button._stop_progress = lambda: calls.append("stop_progress")
    button._cancel_after = lambda: calls.append("cancel_after")
    button.begin_hold()
    calls.clear()  # begin_hold cancels any prior timer; only the cancel matters here

    button.cancel_hold()

    # Abandoning a hold is not a click: the short-press callback must stay unfired.
    assert button._pressed is False
    assert pressed_calls == []
    assert calls == ["stop_progress", "cancel_after"]


def _held_button() -> DummyHoldButton:
    """A button mid-hold: pressed, with the progress animation and hold timer armed."""
    button = make_button(True)
    button._show_hold_progress = True
    button._pressed = True
    button._press_time = 100.0
    button._progress_start = 100.0
    button._after_id = "after-1"
    button._progress_after_id = "after-2"
    return button


def _crossing(x: int, y: int, width: int = 100, height: int = 40) -> SimpleNamespace:
    """A <Leave> event reporting a position relative to the widget it crossed."""
    return SimpleNamespace(
        x=x,
        y=y,
        widget=SimpleNamespace(winfo_width=lambda: width, winfo_height=lambda: height),
    )


def _run_pending_leave(button: DummyHoldButton) -> None:
    """Fire the deferred leave check the way the Tk event loop would."""
    for delay, func in button.tk.after_calls:
        if delay == mod.LEAVE_CONFIRM_MS:
            func()


def test_a_crossing_still_inside_the_button_is_discarded_outright() -> None:
    # The event's own coordinates say where the crossing happened. Inside the widget
    # (plus slop) means jitter, and jitter must not even provisionally cancel.
    button = _held_button()

    button._on_leave_candidate(_crossing(50, 20))

    assert button._leave_pending is False
    assert button._pressed is True


def test_jitter_cancelled_by_a_following_enter_does_not_abort_the_hold() -> None:
    # A jitter crossing is followed within milliseconds by an <Enter>. That clears the
    # provisional cancel, so the deferred check does nothing -- this is what stops the
    # ~50% abort rate that a pointer-position check alone did not.
    button = _held_button()
    button.tk.pointer = (300, 400)  # outside, so only the Enter can save the hold

    button._on_leave_candidate(_crossing(200, 20))  # reads as outside
    assert button._leave_pending is True
    button._on_enter_candidate()
    _run_pending_leave(button)

    assert button._pressed is True
    assert button._progress_start == 100.0


def test_dragging_off_the_button_cancels_once_the_leave_persists() -> None:
    # Deliberate: these are destructive commands, so sliding off must abandon the hold.
    button = _held_button()
    button.tk.pointer = (300, 400)  # still outside when the deferred check runs

    button._on_leave_candidate(_crossing(200, 20))
    _run_pending_leave(button)

    assert button._pressed is False
    assert button._progress_start is None


def test_a_persisting_leave_whose_pointer_is_back_inside_does_not_cancel() -> None:
    # Belt and braces: even with no Enter, the pointer check gets the final say.
    button = _held_button()
    button.tk.pointer = (60, 45)  # inside

    button._on_leave_candidate(_crossing(200, 20))
    _run_pending_leave(button)

    assert button._pressed is True


def test_unreadable_pointer_position_does_not_cancel() -> None:
    # An unknown position must not cancel: a spurious cancel is the failure this path
    # exists to prevent, and releasing early still cancels either way.
    button = _held_button()
    button.tk.pointer = None  # winfo_pointerxy raises

    button._on_leave_candidate(_crossing(200, 20))
    _run_pending_leave(button)

    assert button._pressed is True


def test_a_leave_is_ignored_when_no_hold_is_in_flight() -> None:
    button = make_button(True)
    button._pressed = False

    button._on_leave_candidate(_crossing(200, 20))

    assert button._leave_pending is False


def test_cancel_hold_always_cancels_regardless_of_the_pointer() -> None:
    # cancel_hold() is the controller-chord release path; it must not consult geometry
    # and must not be deferred.
    button = _held_button()
    button.tk.pointer = (60, 45)  # inside

    button.cancel_hold()

    assert button._pressed is False


def test_slop_is_wide_enough_to_absorb_touch_wander() -> None:
    # Literal, not derived from the constant: a test computed from LEAVE_SLOP_PX passes
    # even when the tolerance is zero, which is the case being guarded against.
    assert mod.LEAVE_SLOP_PX >= 8


def test_a_crossing_just_outside_the_widget_is_still_treated_as_inside() -> None:
    # 4px past the edge is finger wander, not a drag-off.
    button = _held_button()

    button._on_leave_candidate(_crossing(104, 20, width=100, height=40))

    assert button._leave_pending is False
    assert button._pressed is True


def test_pointer_outside_allows_slop_around_the_edges() -> None:
    # The rectangle is (10,20)-(110,60); LEAVE_SLOP_PX of wander still counts as inside.
    button = make_button(True)
    slop = mod.LEAVE_SLOP_PX
    cases = {
        (60, 40): False,  # dead centre
        (10 - slop, 40): False,  # exactly one slop to the left
        (10 - slop - 1, 40): True,  # a pixel further, genuinely off
        (110 + slop, 40): True,  # past the right edge plus slop
        (60, 20 - slop): False,  # one slop above
        (60, 60 + slop + 1): True,  # below, past slop
    }
    for pointer, expected in cases.items():
        button.tk.pointer = pointer
        assert button._pointer_outside() is expected, pointer


class FakeCanvas:
    """Just enough tk.Canvas for _position_overlay."""

    def __init__(self) -> None:
        self.master = SimpleNamespace(winfo_rootx=lambda: 0, winfo_rooty=lambda: 0)
        self.places: list[dict] = []

    def place(self, **kwargs) -> None:
        self.places.append(kwargs)

    def place_forget(self) -> None:
        return

    def config(self, **_kwargs) -> None:
        return

    def itemconfig(self, *_args, **_kwargs) -> None:
        return

    def coords(self, *_args, **_kwargs) -> None:
        return

    # _position_overlay raises the overlay via tk.call("raise", ...)
    @property
    def tk(self):
        return SimpleNamespace(call=lambda *_args: None)

    def __str__(self) -> str:
        return "fake-canvas"


def _overlay_button() -> tuple[DummyHoldButton, FakeCanvas]:
    button = _held_button()
    canvas = FakeCanvas()
    button._progress_canvas = canvas
    button._progress_rect = "rect"
    button._progress_bg_rect = "bg"
    button._progress_text_item = None
    button._overlay_visible = True
    return button, canvas


def test_overlay_is_placed_once_while_the_geometry_is_unchanged() -> None:
    # Re-placing the window under the pointer can synthesise a crossing, which is what
    # used to cancel the hold. A <Configure> that did not move the button must not place.
    button, canvas = _overlay_button()

    button._position_overlay()
    button._position_overlay()
    button._on_configure_event()

    assert len(canvas.places) == 1
    assert canvas.places[0] == {"x": 10, "y": 20, "width": 100, "height": 40}


def test_overlay_is_re_placed_after_it_has_been_hidden() -> None:
    # _stop_progress forgets the placement, so the cache has to be cleared with it or the
    # next hold would skip its place() and show no progress bar at all.
    button, canvas = _overlay_button()
    button._position_overlay()

    button._stop_progress()
    button._overlay_visible = True
    button._position_overlay()

    assert len(canvas.places) == 2


def _recovering_button(*, banked: float = 0.0) -> DummyHoldButton:
    """A hold button that tolerates the Deck interrupting a held contact."""
    button = make_button(True)
    button._press_recovery_ms = 250
    button._on_hold = lambda: None
    button._on_press = None
    button._on_repeat = None
    button._held_elapsed = banked
    return button


def _spurious_release() -> SimpleNamespace:
    """A release with no button-state mask, as the Deck emits mid-gesture."""
    return SimpleNamespace(x=50, y=20, widget=SimpleNamespace(winfo_width=lambda: 100, winfo_height=lambda: 40))


def _genuine_release() -> SimpleNamespace:
    """A release carrying the state mask a real X transition has."""
    event = _spurious_release()
    event.state = mod.B1_MASK
    return event


def _run_after(button: DummyHoldButton, delay: int) -> None:
    for scheduled, func in button.tk.after_calls:
        if scheduled == delay:
            func()


def _mid_hold(button: DummyHoldButton, monkeypatch, *, elapsed: float = 0.4) -> None:
    button._pressed = True
    button._press_time = 100.0
    button._progress_start = 100.0
    monkeypatch.setattr(mod.time, "monotonic", lambda: 100.0 + elapsed)


def test_a_state_less_release_off_the_button_is_deferred(monkeypatch) -> None:
    # Could be a genuine drag-off, so pause and let a returning contact rescue it.
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button.tk.pointer = (900, 900)  # well away

    button._on_release_event(_spurious_release())

    assert button._release_pending is True
    assert button._held_elapsed == pytest.approx(0.4)


def test_banking_does_not_double_count_the_running_clock(monkeypatch) -> None:
    # _defer_release banked the elapsed time but left the clock running, so the next call
    # added it again -- pushing a second release past the threshold, where it was treated
    # as authoritative and ended the hold.
    button = _recovering_button()
    button.hold_threshold = 3.0  # the real admin-button threshold
    _mid_hold(button, monkeypatch, elapsed=1.6)
    button.tk.pointer = (900, 900)

    button._on_release_event(_spurious_release())
    assert button._held_elapsed == pytest.approx(1.6)

    monkeypatch.setattr(mod.time, "monotonic", lambda: 101.8)
    assert button._elapsed_held() == pytest.approx(1.6), "the clock must be stopped while banked"


def test_the_countdown_is_paused_while_a_release_is_deferred(monkeypatch) -> None:
    # Left running, a contact genuinely lifted at 2.9s would still fire at 3.0s. For a
    # Reboot button that is an unacceptable false positive.
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button.tk.pointer = (900, 900)
    button._after_id = "after-hold"

    button._on_release_event(_spurious_release())

    assert "after-hold" in button.tk.after_cancel_calls


def test_a_press_inside_the_window_resumes_the_same_hold(monkeypatch) -> None:
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button.tk.pointer = (900, 900)

    button._on_release_event(_spurious_release())
    banked = button._held_elapsed
    button._on_press_event(None)

    assert button._release_pending is False
    assert button._pressed is True
    assert button._held_elapsed == pytest.approx(banked)
    remaining_ms = max(1, int((button.hold_threshold - banked) * 1000))
    assert any(delay == remaining_ms for delay, _ in button.tk.after_calls)


def test_a_resumed_hold_keeps_its_progress_bar_position(monkeypatch) -> None:
    button = _recovering_button()
    _mid_hold(button, monkeypatch, elapsed=0.5)
    button.tk.pointer = (900, 900)

    button._on_release_event(_spurious_release())
    button._on_press_event(None)

    assert button._progress_start == pytest.approx(100.5 - button._held_elapsed)


def test_no_return_inside_the_window_is_a_real_release(monkeypatch) -> None:
    released: list[str] = []
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button.tk.pointer = (900, 900)
    button._do_release = lambda _event=None: released.append("release")

    button._on_release_event(_spurious_release())
    _run_after(button, 250)

    assert released == ["release"]
    assert button._release_pending is False


def test_recovery_is_off_by_default(monkeypatch) -> None:
    # Other HoldButtons -- and the Raspberry Pi's -- must be untouched by any of this.
    released: list[str] = []
    button = make_button(True)
    button._on_hold = lambda: None
    _mid_hold(button, monkeypatch)
    button._do_release = lambda _event=None: released.append("release")

    button._on_release_event(_spurious_release())

    assert released == ["release"]
    assert button._release_pending is False


def test_a_completed_hold_is_not_deferred(monkeypatch) -> None:
    # Once on_hold has fired there is nothing left to protect.
    released: list[str] = []
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button._handled_hold = True
    button._do_release = lambda _event=None: released.append("release")

    button._on_release_event(_spurious_release())

    assert released == ["release"]


def test_cancelling_clears_a_deferred_release(monkeypatch) -> None:
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button.tk.pointer = (900, 900)
    button._on_release_event(_spurious_release())

    button.cancel_hold()

    assert button._release_pending is False
    assert button._held_elapsed == 0.0


def _crossing_with_state(state: int) -> SimpleNamespace:
    """An Enter/Motion event carrying an X button mask."""
    return SimpleNamespace(
        x=50, y=20, state=state, widget=SimpleNamespace(winfo_width=lambda: 100, winfo_height=lambda: 40)
    )


def test_an_enter_with_the_contact_still_down_resumes_the_hold(monkeypatch) -> None:
    # The Deck does not always follow a spurious release with a press: the pointer gets
    # warped off the button and back inside one continuous press. Waiting for a press
    # left the hold to expire; the button mask on the crossing settles it directly.
    button = _recovering_button()
    _mid_hold(button, monkeypatch, elapsed=0.6)
    button.tk.pointer = (900, 900)
    button._on_release_event(_spurious_release())
    assert button._release_pending is True

    button._on_enter_candidate(_crossing_with_state(mod.B1_MASK))

    assert button._release_pending is False
    assert button._pressed is True
    assert button._held_elapsed == pytest.approx(0.6)


def test_an_enter_without_the_contact_does_not_resume(monkeypatch) -> None:
    # A genuine lift followed by the pointer drifting back must still cancel.
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button.tk.pointer = (900, 900)
    button._on_release_event(_spurious_release())

    button._on_enter_candidate(_crossing_with_state(0))

    assert button._release_pending is True, "no button mask means no evidence of a hold"


def test_motion_with_the_contact_down_also_resumes(monkeypatch) -> None:
    # Motion arrives more often than crossings, so it is the more reliable rescue.
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button.tk.pointer = (900, 900)
    button._on_release_event(_spurious_release())

    button._on_motion_candidate(_crossing_with_state(mod.B1_MASK))

    assert button._release_pending is False


def test_motion_is_ignored_when_no_release_is_deferred() -> None:
    # Motion is frequent; it must do nothing outside the recovery window.
    button = _recovering_button()
    button._pressed = True

    button._on_motion_candidate(_crossing_with_state(mod.B1_MASK))

    assert button._release_pending is False
    assert button._pressed is True


def test_an_unreadable_state_mask_does_not_resume() -> None:
    # Some drivers omit state. Absence is not evidence the finger is still down.
    button = _recovering_button()

    assert button._event_button1_down(SimpleNamespace()) is False
    assert button._event_button1_down(SimpleNamespace(state="nonsense")) is False


def test_a_quick_restart_inherits_the_abandoned_progress(monkeypatch, caplog) -> None:
    # "It keeps resetting to zero" is the symptom users report, and it is otherwise
    # invisible in a trace: a fresh press looks the same whether or not it is really the
    # same finger continuing.
    import logging

    button = _recovering_button()
    button.hold_threshold = 3.0
    _mid_hold(button, monkeypatch, elapsed=1.5)
    button.tk.pointer = (900, 900)  # off the button, so the release is honoured

    with caplog.at_level(logging.DEBUG, logger=mod.log.name):
        button._on_release_event(_spurious_release())
        _run_after(button, 250)  # deferral expires: the hold is abandoned
        monkeypatch.setattr(mod.time, "monotonic", lambda: 101.7)
        button._on_press_event(None)

    assert "restart-resumed" in caplog.text
    assert "inherited=1.500s" in caplog.text
    assert "gap=200ms" in caplog.text
    assert button._held_elapsed == pytest.approx(1.5), "the countdown must not start over"


def test_an_unrelated_later_press_is_not_flagged_as_a_restart(monkeypatch, caplog) -> None:
    # A press long after the fact is a new gesture, not a lost countdown.
    import logging

    button = _recovering_button()
    button.hold_threshold = 3.0
    _mid_hold(button, monkeypatch, elapsed=1.5)
    button.tk.pointer = (900, 900)
    button._on_release_event(_genuine_release())

    with caplog.at_level(logging.DEBUG, logger=mod.log.name):
        monkeypatch.setattr(mod.time, "monotonic", lambda: 110.0)
        button._on_press_event(None)

    assert "restart-after-abandon" not in caplog.text


def test_a_hold_that_fired_is_not_counted_as_abandoned(monkeypatch) -> None:
    button = _recovering_button()
    _mid_hold(button, monkeypatch)
    button._handled_hold = True

    button._note_abandoned(2.0)

    assert button._abandoned_at is None


class _EventData:
    """guizero's wrapper: exposes x/y/widget but deliberately no state."""

    def __init__(self, tk_event) -> None:
        self.tk_event = tk_event
        self.x = tk_event.x
        self.y = tk_event.y
        self.widget = object()


def test_a_slower_restart_is_flagged_but_starts_over(monkeypatch, caplog) -> None:
    # Past RESTART_RESUME_MS this is a fresh gesture, not a jitter: it starts at zero and
    # is only logged, so a deliberate re-press cannot inherit a nearly-complete countdown.
    import logging

    button = _recovering_button()
    button.hold_threshold = 3.0
    _mid_hold(button, monkeypatch, elapsed=2.9)
    button.tk.pointer = (900, 900)
    button._on_release_event(_spurious_release())
    _run_after(button, 250)

    with caplog.at_level(logging.DEBUG, logger=mod.log.name):
        monkeypatch.setattr(mod.time, "monotonic", lambda: 103.5)
        button._on_press_event(None)

    assert "restart-after-abandon" in caplog.text
    assert "restart-resumed" not in caplog.text
    assert button._held_elapsed == 0.0


def test_the_unwrap_reads_state_through_guizeros_wrapper() -> None:
    # guizero's EventData exposes no .state, which made every button-delivered event look
    # stateless regardless of provenance. The unwrap is what makes the mask readable.
    wrapped = _EventData(_genuine_release())

    assert HoldButton._event_button1_down(wrapped) is True
    assert "guizero wrapper" in HoldButton._describe_state(wrapped)
    assert HoldButton._event_button1_down(_EventData(_spurious_release())) is False
