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
        self._focus = None

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

    def focus_get(self):
        return self._focus

    def winfo_screenwidth(self) -> int:
        return 800

    def winfo_screenheight(self) -> int:
        return 480

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
        self._selection: tuple[int, int] | None = None

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

    def delete(self, start: int, end: str) -> None:
        if start == "sel.first" and end == "sel.last" and self._selection is not None:
            first, last = self._selection
            self.text = self.text[:first] + self.text[last:]
            self.cursor = first
        elif isinstance(start, int) and isinstance(end, int):
            self.text = self.text[:start] + self.text[end:]
            self.cursor = start
        else:
            self.text = ""
            self.cursor = 0
        self._selection = None

    def insert(self, index: int | str, value: str) -> None:
        pos = self.cursor if index == "insert" else int(index)
        self.text = self.text[:pos] + value + self.text[pos:]
        self.cursor = pos + len(value)

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
        self.master._focus = self

    def selection_range(self, start: int, end: str) -> None:
        last = len(self.text) if end == "end" else int(end)
        self._selection = (start, last)

    def selection_present(self) -> bool:
        return self._selection is not None

    def selection_clear(self) -> None:
        self._selection = None

    def icursor(self, index: int | str) -> None:
        self.cursor = len(self.text) if index == "end" else int(index)

    def index(self, index: str) -> int:
        _ = index
        return self.cursor

    def destroy(self) -> None:
        self.destroyed = True


class DummyProcess:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self):
        return None if not self.terminated else 0

    def terminate(self) -> None:
        self.terminated = True


class DummyWindow(DummyTk):
    def __init__(self, master=None) -> None:
        super().__init__(top=self)
        self.master = master
        self.destroyed = False
        self.geometry_value = None
        self.children = []

    def transient(self, _top) -> None:
        return

    def title(self, _text: str) -> None:
        return

    def attributes(self, *_args) -> None:
        return

    def protocol(self, *_args) -> None:
        return

    def geometry(self, value: str) -> None:
        self.geometry_value = value

    def lift(self) -> None:
        return

    def destroy(self) -> None:
        self.destroyed = True

    def winfo_children(self):
        return self.children


class DummyFrame:
    def __init__(self, master=None, **_kwargs) -> None:
        self.master = master
        self.children = []
        if hasattr(master, "children"):
            master.children.append(self)

    def pack(self, **_kwargs) -> None:
        return

    def pack_configure(self, **_kwargs) -> None:
        return

    def destroy(self) -> None:
        return


class DummyButton:
    instances = []

    def __init__(self, master=None, command=None, **kwargs) -> None:
        self.master = master
        self.command = command
        self.kwargs = kwargs
        self.text = kwargs.get("text")
        DummyButton.instances.append(self)
        if hasattr(master, "children"):
            master.children.append(self)

    def pack(self, **_kwargs) -> None:
        return

    def configure(self, **kwargs) -> None:
        self.kwargs.update(kwargs)


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


def test_begin_edit_launches_configured_keyboard(editable_text_module, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    proc = DummyProcess()

    def fake_popen(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return proc

    monkeypatch.setattr(editable_text_module.subprocess, "Popen", fake_popen, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="Old",
        debounce_ms=0,
        keyboard_command=["fake-keyboard", "--show"],
    )

    widget.begin_edit()
    after_id = widget._keyboard_after_id
    assert after_id is not None

    widget.tk.run_after(after_id)

    assert calls[0][0] == ["fake-keyboard", "--show"]
    assert widget._keyboard_process is proc


def test_commit_cancels_pending_keyboard_launch(editable_text_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        editable_text_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("keyboard should not launch after commit"),
        raising=True,
    )
    widget = editable_text_module.EditableText(
        None,
        text="Old",
        debounce_ms=0,
        keyboard_command=["fake-keyboard"],
    )

    widget.begin_edit()
    after_id = widget._keyboard_after_id
    widget.commit_edit()

    assert after_id not in widget.tk._after_calls


def test_commit_terminates_started_keyboard(editable_text_module, monkeypatch: pytest.MonkeyPatch) -> None:
    proc = DummyProcess()
    monkeypatch.setattr(editable_text_module.subprocess, "Popen", lambda *_args, **_kwargs: proc, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="Old",
        debounce_ms=0,
        keyboard_command=["fake-keyboard"],
    )

    widget.begin_edit()
    widget.tk.run_after(widget._keyboard_after_id)
    widget.commit_edit()

    assert proc.terminated is True


def test_builtin_keyboard_is_shown_and_inserts_text(editable_text_module, monkeypatch: pytest.MonkeyPatch) -> None:
    DummyButton.instances = []
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = editable_text_module.EditableText(None, text="Old", debounce_ms=0)

    widget.begin_edit()
    widget.tk.run_after(widget._keyboard_after_id)
    widget._insert_text("A")

    assert isinstance(widget._keyboard_window, DummyWindow)
    assert widget._entry.get() == "A"
    assert widget._keyboard_window.geometry_value == "800x420+0+60"
    assert any(btn.text == "Clear" for btn in DummyButton.instances)
    assert any(btn.text == "Cancel" for btn in DummyButton.instances)
    assert any(btn.text == "Enter" for btn in DummyButton.instances)
    assert any(btn.text == "<--" for btn in DummyButton.instances)
    assert any(btn.text == "-->" for btn in DummyButton.instances)
    assert any(btn.text == "Del" for btn in DummyButton.instances)


def test_builtin_keyboard_supports_lower_upper_and_symbols(
    editable_text_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DummyButton.instances = []
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = editable_text_module.EditableText(None, text="Old", debounce_ms=0)

    widget.begin_edit()
    widget.tk.run_after(widget._keyboard_after_id)
    assert any(btn.text == "q" for btn in DummyButton.instances)

    widget._toggle_case()
    assert widget._keyboard_mode == "upper"
    assert any(btn.text == "Q" for btn in DummyButton.instances)

    widget._toggle_symbols()
    assert widget._keyboard_mode == "symbols"
    assert any(btn.text == "&" for btn in DummyButton.instances)
    assert any(btn.text == "ABC" for btn in DummyButton.instances)
    assert any(btn.text == "abc" for btn in DummyButton.instances)

    widget._set_keyboard_mode("upper")
    assert widget._keyboard_mode == "upper"
    assert any(btn.text == "Q" for btn in DummyButton.instances)


def test_builtin_keyboard_moves_cursor_and_del_deletes_left(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Old", debounce_ms=0)

    widget.begin_edit()
    widget._entry.selection_clear()
    widget._entry.icursor(1)
    widget._move_cursor_right()
    assert widget._entry.index("insert") == 2

    widget._move_cursor_left()
    assert widget._entry.index("insert") == 1

    widget._backspace()
    assert widget._entry.get() == "ld"
    assert widget._entry.index("insert") == 0


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
