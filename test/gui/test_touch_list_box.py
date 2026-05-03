from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable

import pytest


class DummyTkListbox:
    def __init__(self, initial_xview: float = 0.0) -> None:
        self._xview = float(initial_xview)
        self._bindings: dict[str, Callable[..., Any]] = {}
        self._after_id = 0

    def config(self, **_kwargs: Any) -> None:
        return

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
    module_name = "_test_touch_list_box_module"
    sys.modules.pop(module_name, None)
    module_path = Path(__file__).resolve().parents[2] / "src/pytrain/gui/components/touch_list_box.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(module_name, None)


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


def test_release_realigns_list_when_horizontal_scroll_is_disabled(mod) -> None:
    DummyListBox.initial_xview = 0.0
    widget = mod.TouchListBox(object(), items=["A", "B"])
    widget._lb.xview_moveto(0.35)

    widget._on_release(None)

    assert widget._lb.xview()[0] == pytest.approx(0.0)
