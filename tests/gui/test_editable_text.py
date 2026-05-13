from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

import pytest


class DummyTk:
    def __init__(self, top=None) -> None:
        self._top = top or self
        self._config: dict[str, Any] = {"font": "TkDefaultFont", "justify": "left"}
        self._bindings: dict[str, list[Callable]] = {}
        self._after_calls: dict[str, tuple[int, Callable]] = {}
        self._next_after_id = 1

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

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

    def configure(self, **kwargs: Any) -> None:
        self.config(**kwargs)

    def cget(self, key: str) -> Any:
        return self._config[key]

    def winfo_toplevel(self):
        return self._top

    @staticmethod
    def winfo_rootx() -> int:
        return 10

    @staticmethod
    def winfo_rooty() -> int:
        return 20

    @staticmethod
    def winfo_width() -> int:
        return 120

    @staticmethod
    def winfo_height() -> int:
        return 24


class DummyEntry:
    def __init__(self, master) -> None:
        self.master = master
        self.text = ""
        self.placed = False
        self.destroyed = False
        self._bindings: dict[str, list[Callable]] = {}
        self._config: dict[str, Any] = {}
        self.cursor = 0

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

    def delete(self, start: int, end: str) -> None:
        _ = start, end
        self.text = ""

    def insert(self, index: int, value: str) -> None:
        _ = index
        self.text = value

    def get(self) -> str:
        return self.text

    def place(self, **_kwargs: Any) -> None:
        self.placed = True

    def place_forget(self) -> None:
        self.placed = False

    def configure(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def lift(self) -> None:
        return

    def focus_set(self) -> None:
        return

    def selection_range(self, start: int, end: str) -> None:
        _ = start, end

    def icursor(self, index: int | str) -> None:
        self.cursor = len(self.text) if index == "end" else int(index)

    def index(self, index: str) -> int:
        _ = index
        return self.cursor

    def destroy(self) -> None:
        self.destroyed = True


class DummyText:
    def __init__(self, *_args: Any, text: str = "", **_kwargs: Any) -> None:
        self._text = str(text)
        self.tk = DummyTk()

    @property
    def value(self) -> str:
        return self._text

    @value.setter
    def value(self, value: str) -> None:
        self._text = str(value)
        self.tk.config(text=value)

    def destroy(self) -> None:
        return


@pytest.fixture()
def editable_text_module(monkeypatch: pytest.MonkeyPatch):
    fake_guizero = ModuleType("guizero")
    fake_guizero.Text = DummyText
    monkeypatch.setitem(sys.modules, "guizero", fake_guizero)

    module_name = "editable_text_under_test"
    module_path = Path(__file__).parents[2] / "src" / "pytrain" / "gui" / "components" / "editable_text.py"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.tk, "Entry", DummyEntry, raising=True)
    return mod


def test_hold_begins_inline_edit(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Original", hold_threshold=0.5, debounce_ms=0)

    widget._on_press()
    after_id = widget._hold_after_id
    assert after_id is not None

    widget.tk.run_after(after_id)

    assert widget.is_editing is True
    assert widget._entry.get() == "Original"
    assert widget._entry.placed is True


def test_release_before_hold_cancels_inline_edit(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Original", hold_threshold=0.5, debounce_ms=0)

    widget._on_press()
    after_id = widget._hold_after_id
    widget._on_release()

    assert after_id not in widget.tk._after_calls
    assert widget.is_editing is False


def test_leave_does_not_cancel_hold_by_default(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Original", hold_threshold=0.5, debounce_ms=0)

    widget._on_press()
    after_id = widget._hold_after_id
    widget._on_leave()
    widget.tk.run_after(after_id)

    assert widget.is_editing is True


def test_leave_can_cancel_hold_when_configured(editable_text_module) -> None:
    widget = editable_text_module.EditableText(
        None,
        text="Original",
        hold_threshold=0.5,
        debounce_ms=0,
        cancel_on_leave=True,
    )

    widget._on_press()
    after_id = widget._hold_after_id
    widget._on_leave()

    assert after_id not in widget.tk._after_calls
    assert widget.is_editing is False


def test_added_hold_target_can_begin_edit(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Original", hold_threshold=0.5, debounce_ms=0)
    target = DummyTk(top=widget.tk.winfo_toplevel())

    widget.add_hold_target(target)
    target._bindings["<ButtonPress-1>"][0]()
    after_id = widget._hold_after_id
    assert after_id is not None

    widget.tk.run_after(after_id)

    assert widget.is_editing is True


def test_commit_updates_value_truncates_and_invokes_callback(editable_text_module) -> None:
    seen = []
    widget = editable_text_module.EditableText(
        None,
        text="Old",
        hold_threshold=0.5,
        debounce_ms=0,
        max_length=5,
        on_commit=lambda field, new, old: seen.append((field, new, old)),
    )

    widget.begin_edit()
    widget._set_entry_text("Longer Name")
    widget.commit_edit()

    assert widget.value == "Longe"
    assert widget.is_editing is False
    assert seen == [(widget, "Longe", "Old")]


def test_cancel_restores_original_value(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Old", debounce_ms=0)

    widget.begin_edit()
    widget._set_entry_text("New")
    widget.cancel_edit()

    assert widget.value == "Old"
    assert widget.is_editing is False
