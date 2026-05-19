from __future__ import annotations

from typing import Any, Callable

from src.pytrain.gui.components.scrolling_text import ScrollingText


class DummyFont:
    def measure(self, text: str) -> int:
        return len(text) * 10


class DummyTk:
    def __init__(self, *, width: int = 100, mapped: bool = True) -> None:
        self.width = width
        self.mapped = mapped
        self._config: dict[str, Any] = {"font": "TkDefaultFont", "text": ""}
        self._bindings: dict[str, list[Callable]] = {}
        self._after_calls: dict[str, tuple[int, Callable]] = {}
        self._next_after_id = 1

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

    def unbind(self, event: str) -> None:
        self._bindings.pop(event, None)

    def after(self, delay_ms: int, func: Callable) -> str:
        after_id = f"after#{self._next_after_id}"
        self._next_after_id += 1
        self._after_calls[after_id] = (delay_ms, func)
        return after_id

    def after_cancel(self, after_id: str) -> None:
        self._after_calls.pop(after_id, None)

    def run_after(self, after_id: str) -> None:
        _delay, func = self._after_calls.pop(after_id)
        func()

    def config(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def cget(self, key: str) -> Any:
        return self._config[key]

    def winfo_ismapped(self) -> bool:
        return self.mapped

    def winfo_width(self) -> int:
        return self.width


class DummyMaster:
    def __init__(self, *, width: int) -> None:
        self.tk = DummyTk(width=width)


def make_widget(
    text: str = "Very Long Road Name",
    *,
    width: int = 100,
    mapped: bool = True,
    master_width: int | None = None,
) -> ScrollingText:
    widget = ScrollingText.__new__(ScrollingText)
    widget._tk = DummyTk(width=width, mapped=mapped)
    widget._master = DummyMaster(width=master_width) if master_width is not None else None
    widget._text = text
    widget._base_text = text
    widget._gap = "  "
    widget._speed_ms = 500
    widget._pause_ms = 0
    widget._start_delay_ms = 10_000
    widget._auto_scroll = True
    widget._touch_mode = "toggle"
    widget._running = False
    widget._pressed = False
    widget._tick_after_id = None
    widget._start_after_id = None
    widget._manage_after_id = None
    widget._scroll_buf = ""
    widget._font_cache = DummyFont()
    widget._font_key = "TkDefaultFont"
    widget.tk.config(text=text)
    return widget


def test_value_returns_base_text_while_label_is_scrolling() -> None:
    widget = make_widget("Burlington Northern")

    widget._set_label_text("urlington Northern  B")

    assert widget.value == "Burlington Northern"
    assert widget.tk.cget("text") == "urlington Northern  B"


def test_auto_manage_retries_when_width_is_not_ready() -> None:
    widget = make_widget(width=1)

    widget._auto_manage_scroll()

    assert widget._manage_after_id is not None
    assert widget.tk._after_calls[widget._manage_after_id][0] == 250
    assert widget._start_after_id is None


def test_configure_event_rechecks_scroll_need() -> None:
    widget = make_widget()

    widget._on_configure()

    assert widget._manage_after_id is not None
    assert widget.tk._after_calls[widget._manage_after_id][0] == 75


def test_auto_manage_schedules_one_start_when_text_needs_scroll() -> None:
    widget = make_widget(width=40)

    widget._auto_manage_scroll()
    first_start_id = widget._start_after_id
    widget._auto_manage_scroll()

    assert first_start_id is not None
    assert widget._start_after_id == first_start_id
    assert list(widget.tk._after_calls) == [first_start_id]


def test_needs_scroll_uses_parent_width_when_label_reports_natural_width() -> None:
    widget = make_widget("Very Long Road Name", width=260, master_width=80)

    assert widget.needs_scroll()
