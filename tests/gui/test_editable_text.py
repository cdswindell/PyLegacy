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

    def update_idletasks(self) -> None:
        return

    def configure(self, **kwargs: Any) -> None:
        self.config(**kwargs)

    def cget(self, key: str) -> Any:
        return self._config[key]

    def winfo_toplevel(self):
        return self._top

    def focus_get(self):
        return self._focus

    @staticmethod
    def winfo_screenwidth() -> int:
        return 800

    @staticmethod
    def winfo_screenheight() -> int:
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
        if index == "sel.first" and self._selection is not None:
            return self._selection[0]
        if index == "sel.last" and self._selection is not None:
            return self._selection[1]
        return self.cursor

    def destroy(self) -> None:
        self.destroyed = True


class DummyLabel:
    instances = []

    def __init__(self, master=None, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self.text = kwargs.get("text")
        DummyLabel.instances.append(self)
        if hasattr(master, "children"):
            master.children.append(self)

    def pack(self, **_kwargs) -> None:
        return

    def destroy(self) -> None:
        return


class DummyListbox:
    instances = []

    def __init__(self, master=None, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self._bindings: dict[str, list[Callable]] = {}
        self.items: list[str] = []
        self.selection: tuple[int, ...] = ()
        self.active = None
        self.seen = None
        self.pack_kwargs: dict[str, Any] = {}
        DummyListbox.instances.append(self)
        if hasattr(master, "children"):
            master.children.append(self)

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

    def pack(self, **kwargs) -> None:
        self.pack_kwargs = kwargs

    def insert(self, index: int | str, value: str) -> None:
        if index == "end":
            self.items.append(value)
        else:
            self.items.insert(int(index), value)

    def selection_clear(self, _start: int, _end: str) -> None:
        self.selection = ()

    def selection_set(self, index: int) -> None:
        self.selection = (index,)

    def activate(self, index: int) -> None:
        self.active = index

    def see(self, index: int) -> None:
        self.seen = index

    def curselection(self) -> tuple[int, ...]:
        return self.selection

    def focus_set(self) -> None:
        self.master._focus = self

    def destroy(self) -> None:
        return


class DummyWindow(DummyTk):
    # Class-level so a test can raise it before the window is built; the height a real toplevel
    # would request once it has content.
    req_height = 360

    def __init__(self, master=None) -> None:
        super().__init__(top=self)
        self.master = master
        self.destroyed = False
        self.geometry_value = None
        self.geometry_child_counts: list[int] = []
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
        # How much content existed when the window was sized. Portrait sizes an empty window and
        # then fills it; compact has to fill it first so it has a height to measure.
        self.geometry_child_counts.append(len(self.children))

    def update_idletasks(self) -> None:
        return

    def winfo_reqheight(self) -> int:
        # What real Tk reports: an empty toplevel requests 1x1, and only takes on a height once it
        # has content. That is what makes the compact path's build-before-position order testable.
        return self.req_height if self.children else 1

    def lift(self) -> None:
        return

    def destroy(self) -> None:
        self.destroyed = True

    def winfo_children(self):
        return self.children


class DummyFrame:
    """A Tk Frame -- also what hosts a compact editor, which is a panel in-window, not a window."""

    instances = []
    # The height a real Frame would request once it has content.
    req_height = 360

    def __init__(self, master=None, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children = []
        self.pack_kwargs: dict[str, Any] = {}
        self.place_kwargs: dict[str, Any] | None = None
        # How much content existed each time it was placed, so build-before-place is testable.
        self.place_child_counts: list[int] = []
        self.lifted = 0
        self.destroyed = False
        DummyFrame.instances.append(self)
        if hasattr(master, "children"):
            master.children.append(self)

    def pack(self, **kwargs) -> None:
        self.pack_kwargs = kwargs

    def pack_configure(self, **_kwargs) -> None:
        return

    def place(self, **kwargs) -> None:
        self.place_kwargs = kwargs
        self.place_child_counts.append(len(self.children))

    def lift(self) -> None:
        self.lifted += 1

    def configure(self, **kwargs) -> None:
        self.kwargs.update(kwargs)

    def update_idletasks(self) -> None:
        return

    def winfo_reqheight(self) -> int:
        # As with a real container: 1 until it holds something.
        return self.req_height if self.children else 1

    def winfo_children(self):
        return self.children

    def destroy(self) -> None:
        self.destroyed = True


class DummyButton:
    instances = []

    def __init__(self, master=None, command=None, **kwargs) -> None:
        self.master = master
        self.command = command
        self.kwargs = kwargs
        self.text = kwargs.get("text")
        self._bindings: dict[str, list[Callable]] = {}
        DummyButton.instances.append(self)
        if hasattr(master, "children"):
            master.children.append(self)

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

    def pack(self, **_kwargs) -> None:
        return

    def configure(self, **kwargs) -> None:
        self.kwargs.update(kwargs)


class DummyText:
    def __init__(self, *_args: Any, text: str = "", **_kwargs: Any) -> None:
        self._text = str(text)
        # A distinct toplevel, as in the real thing. The label's own geometry is not the app
        # window's, and a compact editor compares the two to work out which pane owns the field --
        # which was untestable while the stub let a widget be its own toplevel.
        self.tk = DummyTk(top=DummyTk())

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


def test_editable_false_makes_text_ignore_hold(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Original", hold_threshold=0.5, debounce_ms=0)
    hold_target = DummyTk()
    widget.add_hold_target(hold_target)

    widget.editable = False

    assert widget.editable is False
    assert widget.tk._config["cursor"] == ""
    assert hold_target._config["cursor"] == ""

    widget._on_press()

    assert widget._hold_after_id is None
    assert widget.is_editing is False


def test_editable_true_enables_hold_to_edit(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Original", hold_threshold=0.5, debounce_ms=0)
    widget.editable = False

    widget.editable = True

    assert widget.editable is True
    assert widget.tk._config["cursor"] == "hand2"
    assert widget.is_editing is False

    widget._on_press()
    after_id = widget._hold_after_id
    assert after_id is not None
    widget.tk.run_after(after_id)

    assert widget.is_editing is True
    assert widget._entry.get() == "Original"


def test_editable_true_without_editor_raises_unsupported_mode(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Original", editor=None, debounce_ms=0)

    assert widget.editable is False
    assert widget.tk._config["cursor"] == ""
    with pytest.raises(NotImplementedError, match="without an editor"):
        widget.editable = True
    assert widget.is_editing is False


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


def test_commit_cancels_pending_keyboard_launch(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="Old", debounce_ms=0)

    widget.begin_edit()
    after_id = widget._keyboard_after_id
    widget.commit_edit()

    assert after_id not in widget.tk._after_calls


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
    assert any(btn.text == "Save" for btn in DummyButton.instances)
    assert any(btn.text == "←" for btn in DummyButton.instances)
    assert any(btn.text == "→" for btn in DummyButton.instances)
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
    assert any(btn.text == "Q" for btn in DummyButton.instances)

    widget._toggle_case()
    assert widget._keyboard_mode == "lower"
    assert any(btn.text == "q" for btn in DummyButton.instances)

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


def test_builtin_keyboard_enforces_max_length_on_touch_input(editable_text_module) -> None:
    widget = editable_text_module.EditableText(None, text="", debounce_ms=0, max_length=3)

    widget.begin_edit()
    widget._insert_text("12345")

    assert widget._entry.get() == "123"
    assert widget._entry.index("insert") == 3


def test_keypad_editor_shows_number_pad_and_enforces_max_length(
    editable_text_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DummyButton.instances = []
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="",
        debounce_ms=0,
        max_length=2,
        editor=editable_text_module.EditorType.KEYPAD,
    )

    widget.begin_edit()
    widget.tk.run_after(widget._keyboard_after_id)
    widget._insert_text("123")

    assert isinstance(widget._keyboard_window, DummyWindow)
    assert widget._keyboard_window.geometry_value == "520x420+0+60"
    assert widget._entry.get() == "12"
    assert all(any(btn.text == key for btn in DummyButton.instances) for key in "0123456789")
    assert any(btn.text == "Clear" for btn in DummyButton.instances)
    assert any(btn.text == "Cancel" for btn in DummyButton.instances)
    assert any(btn.text == "Save" for btn in DummyButton.instances)
    assert any(btn.text == "Del" for btn in DummyButton.instances)


def test_choices_editor_commits_choice_keys_and_keeps_display_text(
    editable_text_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = []
    DummyButton.instances = []
    DummyFrame.instances = []
    DummyLabel.instances = []
    DummyListbox.instances = []
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Label", DummyLabel, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Listbox", DummyListbox, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="Composite Diesel",
        debounce_ms=0,
        editor=editable_text_module.EditorType.CHOICES,
        choices={0: "Diesel", 1: "Steam"},
        initial_value=0,
        on_commit=lambda field, new, old: seen.append((field, new, old, field.is_changed)),
    )

    widget.begin_edit()
    widget._select_choice_index(1)
    widget.commit_edit()

    assert widget.value == "Composite Diesel"
    assert widget.initial_value == 1
    assert seen == [(widget, 1, 0, True)]
    assert isinstance(widget._choice_window, type(None))
    assert DummyListbox.instances[0].items == ["Diesel", "Steam"]
    assert DummyListbox.instances[0].pack_kwargs["fill"] == "both"
    assert DummyListbox.instances[0].kwargs["font"] == ("TkDefaultFont", 20)
    assert DummyListbox.instances[0].kwargs["height"] == 12
    assert DummyFrame.instances[0].pack_kwargs["side"] == "bottom"
    assert "selectbackground" not in DummyListbox.instances[0].kwargs
    assert "selectforeground" not in DummyListbox.instances[0].kwargs
    assert DummyLabel.instances[0].text == "Current: Diesel"
    assert any(btn.text == "↑" for btn in DummyButton.instances)
    assert any(btn.text == "↓" for btn in DummyButton.instances)
    assert any(btn.text == "Current" for btn in DummyButton.instances)
    assert any(btn.text == "Cancel" for btn in DummyButton.instances)
    assert any(btn.text == "Save" for btn in DummyButton.instances)


def test_choices_editor_current_button_restores_original_selection(
    editable_text_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DummyButton.instances = []
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Label", DummyLabel, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Listbox", DummyListbox, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="Composite Diesel",
        debounce_ms=0,
        editor=editable_text_module.EditorType.CHOICES,
        choices={0: "Diesel", 1: "Steam"},
        initial_value=0,
    )

    widget.begin_edit()
    widget._select_choice_index(1)
    current_button = next(btn for btn in DummyButton.instances if btn.text == "Current")
    current_button.command()

    assert widget._current_choice_value() == 0


def test_choices_editor_arrow_buttons_move_selection(
    editable_text_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DummyButton.instances = []
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Label", DummyLabel, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Listbox", DummyListbox, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="Composite Diesel",
        debounce_ms=0,
        editor=editable_text_module.EditorType.CHOICES,
        choices={0: "Diesel", 1: "Steam", 2: "Electric"},
        initial_value=1,
    )

    widget.begin_edit()
    down_button = next(btn for btn in DummyButton.instances if btn.text == "↓")
    up_button = next(btn for btn in DummyButton.instances if btn.text == "↑")

    down_button.command()
    assert widget._current_choice_value() == 2

    up_button.command()
    assert widget._current_choice_value() == 1


def test_choices_editor_arrow_buttons_use_native_button_repeat(
    editable_text_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DummyButton.instances = []
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Label", DummyLabel, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Listbox", DummyListbox, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="Composite Diesel",
        debounce_ms=0,
        editor=editable_text_module.EditorType.CHOICES,
        choices={0: "Diesel", 1: "Steam", 2: "Electric", 3: "Subway"},
        initial_value=0,
    )

    widget.begin_edit()
    down_button = next(btn for btn in DummyButton.instances if btn.text == "↓")

    assert down_button.kwargs["repeatdelay"] == 550
    assert down_button.kwargs["repeatinterval"] == 250

    down_button.command()
    assert widget._current_choice_value() == 1

    down_button.command()
    assert widget._current_choice_value() == 2

    down_button.command()
    assert widget._current_choice_value() == 3


def test_choices_editor_allows_configurable_visible_rows(
    editable_text_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DummyListbox.instances = []
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Label", DummyLabel, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Listbox", DummyListbox, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="Composite Diesel",
        debounce_ms=0,
        editor=editable_text_module.EditorType.CHOICES,
        choices={0: "Diesel", 1: "Steam"},
        initial_value=0,
        choice_rows=6,
    )

    widget.begin_edit()

    assert DummyListbox.instances[0].kwargs["height"] == 6


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


def _deck_screen(module, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Steam Deck: a 1280x800 app window with two panes side by side, under gamescope."""
    monkeypatch.setattr(DummyTk, "winfo_screenwidth", staticmethod(lambda: 1280), raising=True)
    monkeypatch.setattr(DummyTk, "winfo_screenheight", staticmethod(lambda: 800), raising=True)
    monkeypatch.setattr(module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(module.tk, "Button", DummyButton, raising=True)


def _size_app_window(widget, width: int = 1280, height: int = 800) -> None:
    """Give the app window Deck dimensions, per instance -- the field keeps its own, smaller size.

    A compact editor is placed inside this window, so these are the numbers it measures against.
    """
    top = widget.tk.winfo_toplevel()
    top.winfo_width = lambda: width
    top.winfo_height = lambda: height


def _open_keyboard(module, *, compact: bool, editor=None):
    widget = module.EditableText(
        None,
        text="Old",
        debounce_ms=0,
        compact=compact,
        editor=editor or module.EditorType.KEYBOARD,
    )
    if compact:
        _size_app_window(widget)
    widget.begin_edit()
    widget.tk.run_after(widget._keyboard_after_id)
    return widget


def test_a_compact_editor_is_a_panel_in_the_app_window_not_a_window_of_its_own(
    editable_text_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point. A second toplevel is no good on the Deck.

    Under gamescope nothing honors geometry() for a secondary toplevel -- it is promoted to fill
    the display, so the editor's own dark background covered PyTrain and none of the field being
    edited was left visible. The 980x420 keyboard had the same symptom for the same reason: the
    size was never applied, so no choice of size could have fixed it. A Frame placed inside the
    app's own window needs no window manager to agree to anything, which is exactly why the
    controls help screen works there.
    """
    _deck_screen(editable_text_module, monkeypatch)
    widget = _open_keyboard(editable_text_module, compact=True)

    host = widget._keyboard_window
    assert isinstance(host, DummyFrame), "a Frame in the app window, not a Toplevel"
    assert not isinstance(host, DummyWindow)
    # No window-manager calls to make, so it does not pretend to: a Frame has no title or topmost.
    assert host.kwargs["background"] == editable_text_module.EDITOR_BG
    assert host.kwargs["relief"] == "raised", "its own border separates it from the panel beneath"


def test_the_compact_keyboard_spans_the_display_and_is_as_tall_as_its_own_keys(
    editable_text_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    _deck_screen(editable_text_module, monkeypatch)
    widget = _open_keyboard(editable_text_module, compact=True)

    # Full width buys bigger keys; 800 - 360 leaves the panel above it -- including the field
    # being edited -- on screen, which is what the Pi shows and what was asked for.
    assert widget._keyboard_window.place_kwargs == {"x": 0, "y": 440, "width": 1280, "height": 360}


def test_the_compact_keypad_takes_only_the_pane_that_owns_the_field(
    editable_text_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Asked for explicitly: only the keyboard spans both panes. A keypad is narrow enough that
    # half the display is ample, and it leaves the other pane readable.
    _deck_screen(editable_text_module, monkeypatch)
    widget = _open_keyboard(editable_text_module, compact=True, editor=editable_text_module.EditorType.KEYPAD)

    assert widget._keyboard_window.place_kwargs == {"x": 0, "y": 440, "width": 640, "height": 360}


def test_the_compact_chooser_takes_one_pane_and_is_centered_in_it(
    editable_text_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A list to point at, not something to type on, so it sits where the eye already is.
    _deck_screen(editable_text_module, monkeypatch)
    monkeypatch.setattr(editable_text_module.tk, "Label", DummyLabel, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Listbox", DummyListbox, raising=True)
    widget = editable_text_module.EditableText(
        None,
        text="Old",
        debounce_ms=0,
        compact=True,
        editor=editable_text_module.EditorType.CHOICES,
        choices={1: "Steam", 2: "Diesel"},
        initial_value=1,
    )
    _size_app_window(widget)

    widget.begin_edit()

    assert widget._choice_window.place_kwargs == {"x": 0, "y": 220, "width": 640, "height": 360}


def test_a_pane_editor_follows_the_field_to_the_right_hand_pane(
    editable_text_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Worked out from the field's own position, so the component needs no notion of a "pane".
    _deck_screen(editable_text_module, monkeypatch)
    widget = editable_text_module.EditableText(
        None, text="7", debounce_ms=0, compact=True, editor=editable_text_module.EditorType.KEYPAD
    )
    _size_app_window(widget)
    widget.tk.winfo_rootx = lambda: 700  # the field sits in the right-hand pane
    widget.tk.winfo_width = lambda: 200

    widget.begin_edit()
    widget.tk.run_after(widget._keyboard_after_id)

    assert widget._keyboard_window.place_kwargs["x"] == 640


def test_a_compact_editor_is_built_before_it_is_placed(editable_text_module, monkeypatch: pytest.MonkeyPatch) -> None:
    # The height is the content's own requested height, so the content has to exist first. Place
    # it while still empty and reqheight reads 1, which is what the fallback covers.
    _deck_screen(editable_text_module, monkeypatch)
    widget = _open_keyboard(editable_text_module, compact=True)

    assert widget._keyboard_window.place_child_counts[0] > 0


def test_a_compact_editor_never_takes_more_than_its_share_of_the_display(
    editable_text_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Content height with no ceiling would let a long choice list cover the whole window.
    _deck_screen(editable_text_module, monkeypatch)
    monkeypatch.setattr(DummyFrame, "req_height", 5000, raising=False)
    widget = _open_keyboard(editable_text_module, compact=True)

    capped = int(800 * editable_text_module.COMPACT_MAX_HEIGHT_FRACTION)
    assert widget._keyboard_window.place_kwargs == {"x": 0, "y": 800 - capped, "width": 1280, "height": capped}


def test_portrait_editor_geometry_is_untouched(editable_text_module, monkeypatch: pytest.MonkeyPatch) -> None:
    # The Pi renders these correctly and must not move. Same 800x480 stub screen as the tests
    # above it, and compact defaults to False, so the caller has to opt in.
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = _open_keyboard(editable_text_module, compact=False)

    assert widget.compact is False
    assert widget._keyboard_window.geometry_value == "800x420+0+60"
    assert editable_text_module.PORTRAIT_KEYBOARD_SIZE == (980, 420)
    assert editable_text_module.PORTRAIT_KEYPAD_SIZE == (520, 420)
    assert editable_text_module.PORTRAIT_CHOICES_SIZE == (680, 560)


def test_portrait_sizes_the_window_before_filling_it(editable_text_module, monkeypatch: pytest.MonkeyPatch) -> None:
    # The Pi's original order, kept exactly. Its geometry comes from the screen and never looks at
    # the content, so the order does not change the result -- but a Toplevel is mapped as soon as
    # it is created, so sizing an empty window and sizing a full one open it through different
    # intermediate states, and the Pi's editors are not what the compact work is for.
    monkeypatch.setattr(editable_text_module.tk, "Toplevel", DummyWindow, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Frame", DummyFrame, raising=True)
    monkeypatch.setattr(editable_text_module.tk, "Button", DummyButton, raising=True)
    widget = _open_keyboard(editable_text_module, compact=False)

    assert widget._keyboard_window.geometry_child_counts == [0], "sized before any keys existed"


def test_a_compact_editor_is_measured_against_the_app_window_not_the_screen(
    editable_text_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    # They are the same 1280x800 on a Deck, which is exactly why this needs saying: the panel is
    # placed *inside* the window, so the window's coordinates are the ones that mean anything. A
    # screen-sized placement in a smaller window overhangs it and the keys fall off the edge.
    _deck_screen(editable_text_module, monkeypatch)
    widget = editable_text_module.EditableText(
        None, text="Old", debounce_ms=0, compact=True, editor=editable_text_module.EditorType.KEYBOARD
    )
    _size_app_window(widget, width=1000, height=600)

    widget.begin_edit()
    widget.tk.run_after(widget._keyboard_after_id)

    assert widget._keyboard_window.place_kwargs == {"x": 0, "y": 240, "width": 1000, "height": 360}
