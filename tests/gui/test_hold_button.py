from __future__ import annotations

from threading import Condition, RLock
from types import SimpleNamespace
from typing import Callable

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

    @staticmethod
    def winfo_width() -> int:
        return 100

    @staticmethod
    def winfo_height() -> int:
        return 40

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


def test_touch_drift_inside_the_button_does_not_cancel_the_hold() -> None:
    # The bug: the progress overlay covers the button, so its <Leave> fired on the few
    # pixels of drift a finger makes over a 3s hold and killed the hold about half the
    # time. A crossing only counts if the pointer really left the button.
    button = _held_button()
    button.tk.pointer = (60, 45)  # still within (10,20)-(110,60)

    button._on_leave_candidate()

    assert button._pressed is True
    assert button._progress_start == 100.0


def test_dragging_off_the_button_cancels_the_hold() -> None:
    # Deliberate: these are destructive commands, so sliding off must abandon the hold.
    button = _held_button()
    button.tk.pointer = (300, 400)  # well outside

    button._on_leave_candidate()

    assert button._pressed is False
    assert button._progress_start is None


def test_unreadable_pointer_position_does_not_cancel() -> None:
    # An unknown position must not cancel: a spurious cancel is the failure this path
    # exists to prevent, and releasing early still cancels either way.
    button = _held_button()
    button.tk.pointer = None  # winfo_pointerxy raises

    button._on_leave_candidate()

    assert button._pressed is True


def test_cancel_hold_always_cancels_regardless_of_the_pointer() -> None:
    # cancel_hold() is the controller-chord release path; it must not consult geometry.
    button = _held_button()
    button.tk.pointer = (60, 45)  # inside

    button.cancel_hold()

    assert button._pressed is False


def test_pointer_outside_checks_each_edge() -> None:
    button = make_button(True)
    inside_and_outside = {
        (10, 20): False,  # top-left corner is inside
        (109, 59): False,  # bottom-right, exclusive upper bound
        (9, 40): True,  # left of it
        (110, 40): True,  # right of it
        (60, 19): True,  # above it
        (60, 60): True,  # below it
    }
    for pointer, expected in inside_and_outside.items():
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
