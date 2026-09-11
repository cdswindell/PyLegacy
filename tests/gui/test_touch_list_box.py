from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable

import pytest


class DummyTkListbox:
    items = ["A", "B", "C"]

    def __init__(self, initial_xview: float = 0.0) -> None:
        self._xview = float(initial_xview)
        self._bindings: dict[str, Callable[..., Any]] = {}
        self.item_styles: dict[int, dict[str, Any]] = {}
        self._after_id = 0
        self._selection: tuple[int, ...] = ()
        self._active = 0
        self._yview = 0.0
        self.state = "normal"
        self.tk = SimpleNamespace(call=lambda *_args: 8)

    def config(self, **_kwargs: Any) -> None:
        return

    def curselection(self) -> tuple[int, ...]:
        return self._selection

    def index(self, spec: str) -> int:
        return self._active if spec == "active" else 0

    def selection_clear(self, _first: Any, _last: Any = None) -> None:
        self._selection = ()

    def selection_set(self, index: int) -> None:
        self._selection = (int(index),)

    def activate(self, index: int) -> None:
        self._active = int(index)

    def see(self, index: int) -> None:
        self.seen = int(index)

    def get(self, index: int) -> str:
        return self.items[int(index)]

    def itemconfig(self, index: int, **kwargs: Any) -> None:
        self.item_styles.setdefault(index, {}).update(kwargs)

    def bind(self, event: str, func: Callable[..., Any], add: str | None = None) -> None:
        _ = add
        self._bindings[event] = func

    def after(self, _delay_ms: int, _func: Callable[..., Any]) -> str:
        self._after_id += 1
        return f"after-{self._after_id}"

    @staticmethod
    def after_cancel(_after_id: str) -> None:
        return

    @staticmethod
    def size() -> int:
        return 3

    def xview(self) -> tuple[float, float]:
        return self._xview, min(1.0, self._xview + 0.2)

    def xview_moveto(self, fraction: float) -> None:
        self._xview = float(fraction)

    def xview_scroll(self, count, _units):
        self._xview = max(0, min(0.8, self._xview + count * 0.1))

    def yview(self):
        return self._yview, min(1.0, self._yview + 1 / 3)

    def yview_scroll(self, count, _units):
        self._yview = max(0, min(2 / 3, self._yview + count / 3))

    def nearest(self, _y):
        return round(self._yview * 3)

    def bbox(self, _index):
        return 0, 0, 80, 20

    def cget(self, option):
        return self.state if option == "state" else "Helvetica"


class DummyListBox:
    initial_xview = 0.0

    def __init__(self, _master: Any, items=None, selected=None, **_kwargs: Any) -> None:
        _ = items, selected
        self.children = [SimpleNamespace(tk=DummyTkListbox(self.initial_xview))]


@pytest.fixture
def mod(monkeypatch: pytest.MonkeyPatch):
    fake_guizero = ModuleType("guizero")
    fake_guizero.ListBox = DummyListBox
    monkeypatch.setitem(sys.modules, "guizero", fake_guizero)
    module_name = "src.pytrain.gui.components._test_touch_list_box_module"
    sys.modules.pop(module_name, None)
    module_path = Path(__file__).resolve().parents[2] / "src/pytrain/gui/components/touch_list_box.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "platform", "darwin")
    yield module
    sys.modules.pop(module_name, None)


def test_precise_scrolling_accumulates_small_deltas_without_selecting(mod):
    calls = []
    widget = mod.TouchListBox(object(), on_hold_select=lambda *args: calls.append(args), tap_highlight=True)
    lb = widget._lb
    lb.selection_set(1)
    widget._on_press(SimpleNamespace(y=0))
    handler = lb._bindings["<TouchpadScroll>"]
    for _ in range(19):
        assert handler(SimpleNamespace(delta=0xFFFF)) == "break"
    assert lb.yview()[0] == 0
    handler(SimpleNamespace(delta=0xFFFF))
    assert lb.yview()[0] == pytest.approx(1 / 3)
    assert widget._after_id is None
    widget._fire_hold_select()
    widget._on_release(None)
    assert calls == []
    assert lb.curselection() == (1,)


@pytest.mark.parametrize("horizontal", [False, True])
def test_precise_horizontal_scroll_obeys_policy(mod, horizontal):
    DummyListBox.initial_xview = 0
    widget = mod.TouchListBox(object(), horizontal_scroll=horizontal)
    widget._lb._bindings["<TouchpadScroll>"](SimpleNamespace(delta=(-16 << 16)))
    assert widget._lb.xview()[0] == pytest.approx(0.2 if horizontal else 0)
    assert widget._lb.yview()[0] == 0


def test_precise_scroll_clamps_and_discards_outward_remainder(mod):
    widget = mod.TouchListBox(object())
    handler = widget._lb._bindings["<TouchpadScroll>"]
    handler(SimpleNamespace(delta=0x8000))
    assert widget._lb.yview()[1] == 1
    handler(SimpleNamespace(delta=0xFFFF))
    handler(SimpleNamespace(delta=20))
    assert widget._lb.yview()[0] == pytest.approx(1 / 3)
    handler(SimpleNamespace(delta=32767))
    assert widget._lb.yview()[0] == 0


def test_empty_disabled_and_destroyed_list_ignores_scroll(mod):
    widget = mod.TouchListBox(object())
    handler = widget._lb._bindings["<TouchpadScroll>"]
    widget._lb.state = "disabled"
    handler(SimpleNamespace(delta=0x8000))
    assert widget._lb.yview()[0] == 0
    widget._lb.state = "normal"
    widget._lb.size = lambda: 0
    handler(SimpleNamespace(delta=0x8000))
    assert widget._lb.yview()[0] == 0
    widget._lb.size = lambda: 3

    def destroyed(_option):
        raise mod.TclError("destroyed")

    widget._lb.cget = destroyed
    assert handler(SimpleNamespace(delta=0x8000)) == "break"


def test_old_tk_retains_small_mac_wheel_events(mod, monkeypatch):
    bind = DummyTkListbox.bind

    def old_bind(self, sequence, handler, add=None):
        if sequence == "<TouchpadScroll>":
            raise mod.TclError("unknown event")
        bind(self, sequence, handler, add)

    monkeypatch.setattr(DummyTkListbox, "bind", old_bind)
    from src.pytrain.gui.components import scroll_input

    monkeypatch.setattr(scroll_input, "platform", "darwin")
    widget = mod.TouchListBox(object())
    assert "<TouchpadScroll>" not in widget._lb._bindings
    for _ in range(3):
        assert widget._lb._bindings["<MouseWheel>"](SimpleNamespace(delta=-1)) == "break"
    assert widget._lb.yview()[0] == pytest.approx(1 / 3)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_non_mac_list_keeps_native_wheel_bindings(mod, monkeypatch, platform):
    monkeypatch.setattr(mod, "platform", platform)
    widget = mod.TouchListBox(object())
    assert "<MouseWheel>" not in widget._lb._bindings
    assert "<TouchpadScroll>" not in widget._lb._bindings


def test_init_disables_horizontal_scroll_by_default(mod) -> None:
    DummyListBox.initial_xview = 0.45

    widget = mod.TouchListBox(object(), items=["A", "B"])

    assert widget.horizontal_scroll is False
    assert widget._lb.xview()[0] == pytest.approx(0.0)


def test_set_horizontal_scroll_false_realigns_scrolled_list(mod) -> None:
    DummyListBox.initial_xview = 0.0
    widget = mod.TouchListBox(object(), items=["A", "B"], horizontal_scroll=True)
    widget._lb.xview_moveto(0.6)

    widget.set_horizontal_scroll(False)

    assert widget._lb.xview()[0] == pytest.approx(0.0)


def test_set_item_style_applies_per_row_colors(mod) -> None:
    DummyListBox.initial_xview = 0.0
    widget = mod.TouchListBox(object(), items=["A", "B"])

    widget.set_item_style(1, foreground="red", background="#ffeeee")

    assert widget._lb.item_styles[1] == {"foreground": "red", "background": "#ffeeee"}


def test_set_item_style_with_none_styles_last_row(mod) -> None:
    DummyListBox.initial_xview = 0.0
    widget = mod.TouchListBox(object(), items=["A", "B", "C"])

    widget.set_item_style(None, foreground="green")

    assert widget._lb.item_styles[2] == {"foreground": "green"}


def test_set_item_style_ignores_empty_style(mod) -> None:
    DummyListBox.initial_xview = 0.0
    widget = mod.TouchListBox(object(), items=["A", "B"])

    widget.set_item_style(1)

    assert widget._lb.item_styles == {}


def test_release_realigns_list_when_horizontal_scroll_is_disabled(mod) -> None:
    DummyListBox.initial_xview = 0.0
    widget = mod.TouchListBox(object(), items=["A", "B"])
    widget._lb.xview_moveto(0.35)

    widget._on_release(None)

    assert widget._lb.xview()[0] == pytest.approx(0.0)


def test_activate_highlighted_fires_hold_select_for_selected_row(mod) -> None:
    DummyListBox.initial_xview = 0.0
    calls: list[tuple[int, str]] = []
    widget = mod.TouchListBox(
        object(), items=["A", "B", "C"], on_hold_select=lambda idx, text: calls.append((idx, text))
    )
    widget._lb.selection_set(2)

    assert widget.activate_highlighted() is True
    assert calls == [(2, "C")]


def test_activate_highlighted_falls_back_to_active_row(mod) -> None:
    DummyListBox.initial_xview = 0.0
    calls: list[tuple[int, str]] = []
    widget = mod.TouchListBox(
        object(), items=["A", "B", "C"], on_hold_select=lambda idx, text: calls.append((idx, text))
    )
    widget._lb.activate(1)

    assert widget.highlighted_index() == 1
    assert widget.activate_highlighted() is True
    assert calls == [(1, "B")]


def test_move_highlight_shifts_selection_and_scrolls_into_view(mod) -> None:
    DummyListBox.initial_xview = 0.0
    widget = mod.TouchListBox(object(), items=["A", "B", "C"])
    widget._lb.selection_set(0)

    assert widget.move_highlight(1) is True
    assert widget.highlighted_index() == 1
    assert widget._lb.seen == 1


def test_move_highlight_clamps_at_ends_without_wrapping(mod) -> None:
    DummyListBox.initial_xview = 0.0
    widget = mod.TouchListBox(object(), items=["A", "B", "C"])
    widget._lb.selection_set(0)

    # Already at the top: moving up is clamped and reports no movement.
    assert widget.move_highlight(-1) is False
    assert widget.highlighted_index() == 0

    widget._lb.selection_set(2)
    # Already at the bottom: moving down is clamped and reports no movement.
    assert widget.move_highlight(1) is False
    assert widget.highlighted_index() == 2
