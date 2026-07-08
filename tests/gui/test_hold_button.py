from __future__ import annotations

from threading import Condition, RLock
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
