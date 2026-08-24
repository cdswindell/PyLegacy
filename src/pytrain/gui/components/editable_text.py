#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
import time
import tkinter as tk
from enum import Enum, auto
from tkinter import TclError
from typing import Any, Callable

from guizero import Text

log = logging.getLogger(__name__)


class EditorType(Enum):
    KEYBOARD = auto()
    KEYPAD = auto()
    CHOICES = auto()


# Editor sizes for a portrait display, in pixels, clamped to the screen. Authored for the Pi and
# left exactly as they were: full width on an 800px-wide panel, a third of a 1280px-tall one.
PORTRAIT_KEYBOARD_SIZE = (980, 420)
PORTRAIT_KEYPAD_SIZE = (520, 420)
PORTRAIT_CHOICES_SIZE = (680, 560)
# Fraction of the screen an editor may occupy on a compact pane before it is capped. The height
# is the number that matters: these constants are only a backstop, because a compact editor is
# sized to its own content and only clamped if that content is somehow enormous.
COMPACT_MAX_HEIGHT_FRACTION = 0.62
# The editors' own backdrop. Named because on a compact pane it is what the user sees covering
# the app if the editor is hosted in a window rather than in-window -- see _new_editor_host.
EDITOR_BG = "#202020"


class EditableText(Text):
    """
    Drop-in replacement for guizero.Text that becomes editable after a press-and-hold.

    The displayed widget remains the guizero Text/Label. While editing, a Tk Entry is
    temporarily placed over the label, so the existing GuiZero layout code does not need to change.
    """

    def __init__(
        self,
        *args,
        text: str = "",
        hold_threshold: float = 1.0,
        debounce_ms: int = 80,
        max_length: int | None = None,
        editor: EditorType | None = EditorType.KEYBOARD,
        compact: bool = False,
        choices: dict[Any, Any] | None = None,
        initial_value: Any = None,
        choice_rows: int = 12,
        on_commit: Callable[["EditableText", Any, Any], None] | tuple | list | None = None,
        on_cancel: Callable[["EditableText", Any], None] | tuple | list | None = None,
        commit_on_focus_lost: bool = True,
        select_all_on_edit: bool = True,
        cancel_on_leave: bool = False,
        show_keyboard_on_edit: bool = True,
        hide_keyboard_on_finish: bool = True,
        edit_bg: str = "white",
        edit_fg: str = "black",
        **kwargs,
    ):
        super().__init__(*args, text=text, **kwargs)

        self.hold_threshold = float(hold_threshold)
        self.debounce_ms = int(debounce_ms)
        self.editor = editor
        # Landscape alone cannot stand in for this: the legacy Pi display is 800x480, also
        # landscape, and its editors are correct as they are. Only the caller knows it is a Deck
        # pane, so portrait and the 7" Pi are both left untouched by construction.
        self.compact = bool(compact)
        self._editable = editor is not None
        self.max_length = max_length
        self.choices = choices or {}
        self.initial_value = initial_value
        self.choice_rows = max(1, int(choice_rows))
        self.on_commit = on_commit
        self.on_cancel = on_cancel
        self.commit_on_focus_lost = bool(commit_on_focus_lost)
        self.select_all_on_edit = bool(select_all_on_edit)
        self.cancel_on_leave = bool(cancel_on_leave)
        self.show_keyboard_on_edit = bool(show_keyboard_on_edit)
        self.hide_keyboard_on_finish = bool(hide_keyboard_on_finish)
        self.edit_bg = edit_bg
        self.edit_fg = edit_fg

        self._press_time: float | None = None
        self._pressed = False
        self._editing = False
        self._hold_after_id: str | None = None
        self._keyboard_after_id: str | None = None
        self._keyboard_window: tk.Toplevel | None = None
        self._choice_window: tk.Toplevel | None = None
        self._keyboard_mode = "upper"
        self._value_before_edit: Any = ""
        self._display_before_edit = ""
        self._last_committed_value: Any = ""
        self._entry: tk.Entry | None = None
        self._choice_listbox: tk.Listbox | None = None
        self._choice_keys: list[Any] = []
        self._choice_labels: list[str] = []
        self._hold_targets: list[Any] = []

        self.tk.bind("<ButtonPress-1>", self._on_press, add="+")
        self.tk.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.tk.bind("<Leave>", self._on_leave, add="+")
        self.tk.bind("<Configure>", self._on_configure, add="+")

        self._set_editable_cursor()

    def add_hold_target(self, target: Any) -> None:
        """
        Add another Tk or GuiZero widget that should start editing this text on hold.

        This is useful when the Text lives inside a larger labeled field and the whole field
        should feel editable, not only the exact label pixels.
        """
        tk_target = getattr(target, "tk", target)
        try:
            tk_target.bind("<ButtonPress-1>", self._on_press, add="+")
            tk_target.bind("<ButtonRelease-1>", self._on_release, add="+")
            tk_target.bind("<Leave>", self._on_leave, add="+")
            self._hold_targets.append(tk_target)
            self._set_target_cursor(tk_target)
        except (AttributeError, TclError):
            pass

    @property
    def is_editing(self) -> bool:
        return self._editing

    @property
    def editable(self) -> bool:
        return self._editable

    @editable.setter
    def editable(self, value: bool) -> None:
        value = bool(value)
        if value and self.editor is None:
            raise NotImplementedError("EditableText cannot be editable without an editor")

        self._editable = value
        self._set_editable_cursor()
        if not value and self._editing:
            self.cancel_edit()

    def begin_edit(self) -> None:
        if not self._editable:
            return
        if self.editor is None:
            raise NotImplementedError("EditableText cannot begin editing without an editor")
        if self._editing:
            return

        self._cancel_hold_timer()
        self._editing = True
        self._display_before_edit = "" if self.value is None else str(self.value)
        self._value_before_edit = self._editor_initial_value()
        self._last_committed_value = self._value_before_edit

        if self.editor == EditorType.CHOICES:
            self._begin_choice_edit()
            return

        entry = self._ensure_entry()
        self._set_entry_text(self._value_before_edit)
        self._position_entry()

        try:
            entry.lift()
            entry.focus_set()
            if self.select_all_on_edit:
                entry.selection_range(0, "end")
            entry.icursor("end")
            self._schedule_keyboard()
        except TclError:
            self._editing = False
            log.debug("Unable to begin inline text edit", exc_info=True)

    def commit_edit(self) -> None:
        if not self._editing:
            return

        new_value = self._current_editor_value()
        old_value = self._value_before_edit

        self._finish_edit()
        self._last_committed_value = new_value
        if self.editor == EditorType.CHOICES:
            self.initial_value = new_value
        else:
            self.value = new_value

        if new_value != old_value:
            self._invoke_callback(self.on_commit, self, new_value, old_value)

    @property
    def is_changed(self) -> bool:
        if self._editing:
            return self._current_editor_value() != self._value_before_edit
        return self._last_committed_value != self._value_before_edit

    def cancel_edit(self) -> None:
        if not self._editing:
            return

        old_value = self._value_before_edit
        self._finish_edit()
        self.value = self._display_before_edit if self.editor == EditorType.CHOICES else old_value
        self._last_committed_value = old_value
        self._invoke_callback(self.on_cancel, self, old_value)

    def destroy(self):
        self._cancel_hold_timer()
        if self._entry is not None:
            try:
                self._entry.destroy()
            except TclError:
                pass
            self._entry = None
        self._hide_choice_picker()
        self._hide_keyboard()
        super().destroy()

    # -------------------------
    # Event handling
    # -------------------------

    # noinspection PyUnusedLocal,unused-parameter
    def _on_press(self, event=None) -> None:
        if self._editing or not self._editable:
            return

        self._pressed = True
        self._press_time = time.monotonic()
        self._cancel_hold_timer()
        self._hold_after_id = self.tk.after(int(self.hold_threshold * 1000), self._on_hold)

    # noinspection PyUnusedLocal,unused-parameter
    def _on_release(self, event=None) -> None:
        self._pressed = False
        self._cancel_hold_timer()

    # noinspection PyUnusedLocal,unused-parameter
    def _on_leave(self, event=None) -> None:
        if self._editing or not self.cancel_on_leave:
            return
        self._pressed = False
        self._cancel_hold_timer()

    # noinspection PyUnusedLocal,unused-parameter
    def _on_configure(self, event=None) -> None:
        if self._editing:
            if self.editor == EditorType.CHOICES:
                self._position_choice_picker()
            else:
                self._position_entry()

    def _on_hold(self) -> None:
        self._hold_after_id = None
        if not self._pressed or not self._editable:
            return

        elapsed = (time.monotonic() - self._press_time) if self._press_time else 0.0
        if elapsed < (self.debounce_ms / 1000.0):
            return

        self.begin_edit()

    def _set_editable_cursor(self) -> None:
        self._set_target_cursor(self.tk)
        for target in self._hold_targets:
            self._set_target_cursor(target)

    def _set_target_cursor(self, target: Any) -> None:
        try:
            target.configure(cursor="hand2" if self._editable else "")
        except (AttributeError, TclError):
            pass

    # noinspection PyUnusedLocal,unused-parameter
    def _on_entry_key_release(self, event=None) -> None:
        if self.max_length is None or self._entry is None:
            return

        text = self._entry.get()
        if len(text) <= self.max_length:
            return

        pos = self._entry.index("insert")
        self._set_entry_text(text[: self.max_length])
        try:
            self._entry.icursor(min(pos, self.max_length))
        except TclError:
            pass

    # -------------------------
    # Editor overlays
    # -------------------------

    def _begin_choice_edit(self) -> None:
        try:
            self._populate_choices()
            self._show_choice_picker()
        except TclError:
            self._editing = False
            log.debug("Unable to begin inline choice edit", exc_info=True)

    def _ensure_entry(self) -> tk.Entry:
        if self._entry is not None:
            return self._entry

        top = self.tk.winfo_toplevel()
        self._entry = tk.Entry(top)
        self._entry.bind("<Return>", lambda _event: self.commit_edit(), add="+")
        self._entry.bind("<KP_Enter>", lambda _event: self.commit_edit(), add="+")
        self._entry.bind("<Escape>", lambda _event: self.cancel_edit(), add="+")
        self._entry.bind("<KeyRelease>", self._on_entry_key_release, add="+")
        if self.commit_on_focus_lost:
            self._entry.bind("<FocusOut>", self._on_entry_focus_out, add="+")
        return self._entry

    # noinspection PyUnusedLocal,unused-parameter
    def _on_entry_focus_out(self, event=None) -> None:
        try:
            self.tk.after(100, self._commit_if_focus_left_editor)
        except TclError:
            self._commit_if_focus_left_editor()

    def _commit_if_focus_left_editor(self) -> None:
        if not self._editing:
            return
        try:
            focused = self.tk.winfo_toplevel().focus_get()
        except TclError:
            focused = None
        if focused is self._entry or self._is_keyboard_descendant(focused) or self._is_choice_descendant(focused):
            return
        self.commit_edit()

    def _position_entry(self) -> None:
        if self._entry is None:
            return

        top = self._entry.master
        try:
            x = int(self.tk.winfo_rootx()) - int(top.winfo_rootx())
            y = int(self.tk.winfo_rooty()) - int(top.winfo_rooty())
            width = max(1, int(self.tk.winfo_width()))
            height = max(1, int(self.tk.winfo_height()))
            self._entry.place(x=x, y=y, width=width, height=height)
            self._entry.configure(
                background=self.edit_bg,
                foreground=self.edit_fg,
                insertbackground=self.edit_fg,
                font=self.tk.cget("font"),
                justify=self.tk.cget("justify"),
                relief="solid",
                bd=1,
            )
        except TclError:
            pass

    def _populate_choices(self) -> None:
        self._choice_keys = list(self.choices.keys())
        self._choice_labels = [str(value) for value in self.choices.values()]

    def _show_choice_picker(self) -> None:
        if self._choice_window is not None:
            try:
                self._choice_window.lift()
            except TclError:
                pass
            return

        picker = self._new_editor_host("Choices")
        self._choice_window = picker
        self._place_editor(picker, self._build_choice_picker, lambda _w: self._position_choice_picker())
        picker.lift()
        if self._choice_listbox is not None:
            self._choice_listbox.focus_set()

    def _position_choice_picker(self) -> None:
        picker = self._choice_window
        if picker is None:
            return
        if self.compact:
            # A chooser is a short list; half the display is ample and leaves the other pane read-
            # able, which the user asked for explicitly. Only the keyboard earns the full width.
            self._position_compact_editor(picker, anchor="center", span="pane")
            return

        try:
            top = self.tk.winfo_toplevel()
            screen_w = int(top.winfo_screenwidth())
            screen_h = int(top.winfo_screenheight())
            scale = self._screen_scale(screen_w, screen_h)
            want_w, want_h = PORTRAIT_CHOICES_SIZE
            picker_w = min(screen_w, self._scaled(want_w, scale))
            picker_h = min(screen_h, self._scaled(want_h, scale))
            x = max(0, (screen_w - picker_w) // 2)
            y = max(0, (screen_h - picker_h) // 2)
            picker.geometry(f"{picker_w}x{picker_h}+{x}+{y}")
        except TclError:
            pass

    def _build_choice_picker(self, picker: tk.Toplevel) -> None:
        try:
            for child in picker.winfo_children():
                child.destroy()
        except TclError:
            pass

        current_label = self._choice_label_for_key(self._value_before_edit)
        title = tk.Label(
            picker,
            text=f"Current: {current_label}",
            anchor="w",
            font=("TkDefaultFont", self._scaled(20), "bold"),
            background="#202020",
            foreground="#ffffff",
        )
        title.pack(fill="x", padx=self._scaled(12), pady=(self._scaled(12), self._scaled(6)))

        action_row = tk.Frame(picker, background="#202020")
        action_row.pack(side="bottom", fill="x", padx=self._scaled(8), pady=(self._scaled(6), self._scaled(12)))
        self._make_repeat_key(action_row, "↑", lambda: self._move_choice(-1), weight=1)
        self._make_repeat_key(action_row, "↓", lambda: self._move_choice(1), weight=1)
        self._make_key(action_row, "Current", lambda: self._select_choice_key(self._value_before_edit), weight=1)
        self._make_key(action_row, "Cancel", self.cancel_edit, weight=1)
        self._make_key(action_row, "Save", self.commit_edit, weight=1)

        self._choice_listbox = tk.Listbox(
            picker,
            activestyle="dotbox",
            exportselection=False,
            font=("TkDefaultFont", self._scaled(20)),
            height=self.choice_rows,
            relief="solid",
            bd=1,
        )
        self._choice_listbox.pack(fill="both", expand=True, padx=self._scaled(12), pady=self._scaled(6))
        self._choice_listbox.bind("<Up>", lambda _event: self._move_choice(-1), add="+")
        self._choice_listbox.bind("<Down>", lambda _event: self._move_choice(1), add="+")
        self._choice_listbox.bind("<Return>", lambda _event: self.commit_edit(), add="+")
        self._choice_listbox.bind("<KP_Enter>", lambda _event: self.commit_edit(), add="+")
        self._choice_listbox.bind("<Escape>", lambda _event: self.cancel_edit(), add="+")

        for label in self._choice_labels:
            self._choice_listbox.insert("end", label)
        self._select_choice_key(self._value_before_edit)

    def _finish_edit(self) -> None:
        self._editing = False
        self._pressed = False
        self._cancel_hold_timer()
        self._cancel_keyboard_timer()
        if self.hide_keyboard_on_finish:
            self._hide_keyboard()
        self._hide_choice_picker()
        if self._entry is not None:
            try:
                self._entry.place_forget()
            except TclError:
                pass

    def _set_entry_text(self, value: str) -> None:
        if self._entry is None:
            return

        value = self._coerce_text(value)
        try:
            self._entry.delete(0, "end")
            self._entry.insert(0, value)
        except TclError:
            pass

    def _coerce_text(self, value: Any) -> str:
        text = "" if value is None else str(value).strip()
        if self.max_length is not None:
            return text[: self.max_length].strip()
        return text

    def _editor_initial_value(self) -> Any:
        if self.editor == EditorType.CHOICES:
            if self.initial_value is not None:
                return self.initial_value
            label = "" if self.value is None else str(self.value).strip()
            return self._choice_key_for_label(label, default=label)
        return self._coerce_text(self.value)

    def _current_editor_value(self) -> Any:
        if self.editor == EditorType.CHOICES:
            return self._current_choice_value()
        entry = self._entry
        new_value = self._value_before_edit if entry is None else entry.get()
        return self._coerce_text(new_value)

    def _current_choice_value(self) -> Any:
        listbox = self._choice_listbox
        if listbox is None:
            return self._value_before_edit
        try:
            selection = listbox.curselection()
            if selection:
                index = int(selection[0])
                if 0 <= index < len(self._choice_keys):
                    return self._choice_keys[index]
        except TclError:
            pass
        return self._value_before_edit

    def _select_choice_key(self, key: Any) -> None:
        if self._choice_listbox is None:
            return
        try:
            index = self._choice_keys.index(key)
        except ValueError:
            index = 0
        self._select_choice_index(index)

    def _select_choice_index(self, index: int) -> None:
        if self._choice_listbox is None or not self._choice_keys:
            return
        try:
            index = max(0, min(index, len(self._choice_keys) - 1))
            self._choice_listbox.selection_clear(0, "end")
            self._choice_listbox.selection_set(index)
            self._choice_listbox.activate(index)
            self._choice_listbox.see(index)
        except TclError:
            pass

    def _move_choice(self, delta: int) -> None:
        if self._choice_listbox is None or not self._choice_keys:
            return
        try:
            selection = self._choice_listbox.curselection()
            current = int(selection[0]) if selection else 0
        except (TclError, ValueError, TypeError):
            current = 0
        self._select_choice_index(current + delta)

    def _choice_key_for_label(self, label: str, default: Any = None) -> Any:
        for key, value in self.choices.items():
            if str(value) == label:
                return key
        return default

    def _choice_label_for_key(self, key: Any) -> str:
        if key in self.choices:
            return str(self.choices[key])
        return "" if key is None else str(key)

    def _cancel_hold_timer(self) -> None:
        if self._hold_after_id is None:
            return
        try:
            self.tk.after_cancel(self._hold_after_id)
        except TclError:
            pass
        self._hold_after_id = None

    @staticmethod
    def _invoke_callback(cb, *default_args) -> None:
        if not cb:
            return
        if callable(cb):
            cb(*default_args)
        elif isinstance(cb, (tuple, list)) and cb:
            func = cb[0]
            args = cb[1] if len(cb) > 1 else default_args
            kwargs = cb[2] if len(cb) > 2 else {}
            func(*args, **kwargs)

    def _schedule_keyboard(self) -> None:
        if not self.show_keyboard_on_edit:
            return
        self._cancel_keyboard_timer()
        try:
            self._keyboard_after_id = self.tk.after(150, self._show_keyboard)
        except TclError:
            self._show_keyboard()

    def _cancel_keyboard_timer(self) -> None:
        if self._keyboard_after_id is None:
            return
        try:
            self.tk.after_cancel(self._keyboard_after_id)
        except TclError:
            pass
        self._keyboard_after_id = None

    def _show_keyboard(self) -> None:
        self._keyboard_after_id = None
        if not self._editing:
            return
        if self.editor == EditorType.KEYPAD:
            self._show_builtin_keypad()
        elif self.editor == EditorType.KEYBOARD:
            self._show_builtin_keyboard()
        else:
            log.debug("Editor type %s is not implemented", self.editor)

    def _hide_keyboard(self) -> None:
        if self._keyboard_window is not None:
            try:
                self._keyboard_window.destroy()
            except TclError:
                pass
            self._keyboard_window = None

    def _hide_choice_picker(self) -> None:
        if self._choice_window is not None:
            try:
                self._choice_window.destroy()
            except TclError:
                pass
            self._choice_window = None
        self._choice_listbox = None

    def _show_builtin_keyboard(self) -> None:
        if self._entry is None:
            return
        if self._keyboard_window is not None:
            try:
                self._keyboard_window.lift()
            except TclError:
                pass
            return

        try:
            kb = self._new_editor_host("Keyboard")
            self._keyboard_window = kb
            self._keyboard_mode = "upper"
            self._place_editor(kb, self._build_builtin_keyboard, self._position_builtin_keyboard)
            kb.lift()
            self._entry.focus_set()
        except TclError:
            self._keyboard_window = None
            log.debug("Unable to show built-in keyboard", exc_info=True)

    def _show_builtin_keypad(self) -> None:
        if self._entry is None:
            return
        if self._keyboard_window is not None:
            try:
                self._keyboard_window.lift()
            except TclError:
                pass
            return

        try:
            kb = self._new_editor_host("Keypad")
            self._keyboard_window = kb
            self._place_editor(kb, self._build_builtin_keypad, self._position_builtin_keypad)
            kb.lift()
            self._entry.focus_set()
        except TclError:
            self._keyboard_window = None
            log.debug("Unable to show built-in keypad", exc_info=True)

    def _new_editor_host(self, title: str):
        """The container an editor is built into: a window on portrait, a panel in-window on a pane.

        Portrait gets a real ``tk.Toplevel``, sized and positioned by a window manager that honors
        ``geometry()``. That is what the Pi actually shows: a titled keyboard window across the
        bottom, with the panel and the field being edited still visible above it.

        A compact pane cannot use one. Under gamescope there is no window manager cooperating like
        that -- a secondary toplevel is promoted to fill the display -- so the editor's own
        background covered PyTrain entirely and nothing of the field being edited was left on
        screen. The 980x420 keyboard had the same symptom for the same reason: that size was never
        applied. Sizing it differently could not have helped, because the size was not the problem.

        So a compact editor is built into a ``tk.Frame`` placed inside the app's own toplevel.
        That is exactly why the controls help screen works on the Deck -- it is a Box gridded into
        ``body`` rather than a window, so no window manager has to agree to anything. Everything
        the editors do afterwards (``lift``, ``destroy``, ``winfo_children``, packing rows into it)
        means the same for a Frame as for a Toplevel, so the key-building code is shared as it is.
        """
        top = self.tk.winfo_toplevel()
        if self.compact:
            # No transient/title/topmost/protocol: a Frame has no window manager to tell. Its own
            # border is what separates it from the panel it covers, the way the controls screen's
            # raised border does.
            return tk.Frame(top, background=EDITOR_BG, relief="raised", borderwidth=3)
        host = tk.Toplevel(top)
        host.transient(top)
        host.title(title)
        host.configure(background=EDITOR_BG)
        try:
            host.attributes("-topmost", True)
        except TclError:
            pass
        host.protocol("WM_DELETE_WINDOW", self.cancel_edit)
        return host

    def _position_builtin_keyboard(self, kb: tk.Toplevel) -> None:
        if self.compact:
            self._position_compact_editor(kb, anchor="bottom", span="display")
            return
        try:
            top = self.tk.winfo_toplevel()
            screen_w = int(top.winfo_screenwidth())
            screen_h = int(top.winfo_screenheight())
            scale = self._screen_scale(screen_w, screen_h)
            want_w, want_h = PORTRAIT_KEYBOARD_SIZE
            kb_w = min(screen_w, self._scaled(want_w, scale))
            kb_h = min(screen_h, self._scaled(want_h, scale))
            x = max(0, (screen_w - kb_w) // 2)
            y = max(0, screen_h - kb_h)
            kb.geometry(f"{kb_w}x{kb_h}+{x}+{y}")
        except TclError:
            pass

    def _position_builtin_keypad(self, kb: tk.Toplevel) -> None:
        if self.compact:
            self._position_compact_editor(kb, anchor="bottom", span="pane")
            return
        try:
            top = self.tk.winfo_toplevel()
            screen_w = int(top.winfo_screenwidth())
            screen_h = int(top.winfo_screenheight())
            scale = self._screen_scale(screen_w, screen_h)
            want_w, want_h = PORTRAIT_KEYPAD_SIZE
            kb_w = min(screen_w, self._scaled(want_w, scale))
            kb_h = min(screen_h, self._scaled(want_h, scale))
            x = max(0, int(top.winfo_rootx()) + (int(top.winfo_width()) - kb_w) // 2)
            y = max(0, screen_h - kb_h)
            kb.geometry(f"{kb_w}x{kb_h}+{x}+{y}")
        except TclError:
            pass

    def _place_editor(self, window: tk.Toplevel, build: Callable[[Any], None], position: Callable[[Any], None]) -> None:
        """Build and size an editor window, in the order the mode requires.

        Compact geometry is measured from the content's own requested height, so the content has
        to exist before the window is sized.

        Portrait geometry is computed from the screen and never looks at the content, so its
        original order -- size the window, then fill it -- is kept exactly. Not because the
        resulting geometry would differ, but because a Toplevel is mapped the moment it is
        created, so the two orders open the window through different intermediate states, and the
        Pi's editors are not what this change is for.
        """
        if self.compact:
            build(window)
            position(window)
        else:
            position(window)
            build(window)

    def _field_is_in_left_pane(self, top, top_w: int) -> bool:
        """Which half of the display holds this field, worked out from the field's own position.

        Deliberately not by asking about panes: this component is used by whatever wants an
        editable label, and a pane is a Steam Deck idea it has no business knowing about.
        """
        try:
            offset = int(self.tk.winfo_rootx()) - int(top.winfo_rootx())
            return offset + int(self.tk.winfo_width()) // 2 < top_w // 2
        except (TclError, TypeError, ValueError):
            return True

    def _position_compact_editor(self, window, *, anchor: str, span: str) -> None:
        """Place an in-window editor panel, as tall as its own content.

        Modelled on the Deck's controls help screen, which grids across all three columns of the
        body -- both panes and the divider -- and takes no height of its own, so it is "as short
        as it can be and centered on the display rather than a full-height panel with a void under
        the text". Both ideas apply here.

        ``span="display"`` for the keyboard, which earns the full width in bigger keys, and
        ``span="pane"`` for the keypad and the choice picker, which are narrow enough that half the
        display is plenty and leaves the other pane readable.

        Content height is what keeps the field you are editing visible. Anchored to the bottom at
        its natural height, the keyboard leaves the panel above it on screen, so the entry stays
        the one source of truth for the text and there is nothing to mirror. ``anchor="center"``
        for the choice picker, which is a list to point at rather than something to type on.

        Measured against the app's own toplevel rather than the screen: the placement is inside
        that window, so its coordinates are the ones that mean anything.
        """
        try:
            top = self.tk.winfo_toplevel()
            top.update_idletasks()
            top_w = max(1, int(top.winfo_width()))
            top_h = max(1, int(top.winfo_height()))
            # Ask the built content how tall it wants to be, which needs the content to exist --
            # see _place_editor for why the compact path builds first.
            window.update_idletasks()
            wanted = int(window.winfo_reqheight())
            # reqheight is 1 for a container with nothing in it; fall back rather than show a sliver.
            if wanted <= 1:
                wanted = self._scaled(PORTRAIT_KEYBOARD_SIZE[1])
            height = max(1, min(wanted, int(top_h * COMPACT_MAX_HEIGHT_FRACTION)))
            if span == "pane":
                # Half the window, on the side the field is on. One pixel of the 2px divider gets
                # covered; nothing reads it.
                width = max(1, top_w // 2)
                x = 0 if self._field_is_in_left_pane(top, top_w) else top_w - width
            else:
                width = top_w
                x = 0
            y = max(0, top_h - height) if anchor == "bottom" else max(0, (top_h - height) // 2)
            window.place(x=x, y=y, width=width, height=height)
            window.lift()
        except (TclError, TypeError, ValueError):
            pass

    def _build_builtin_keyboard(self, kb: tk.Toplevel) -> None:
        try:
            for child in kb.winfo_children():
                child.destroy()
        except TclError:
            pass

        action_row = tk.Frame(kb, background="#202020")
        action_row.pack(fill="x", padx=self._scaled(8), pady=(self._scaled(8), 0))
        self._make_key(action_row, "Clear", self._clear_entry, weight=1)
        self._make_key(action_row, "Cancel", self.cancel_edit, weight=1)
        self._make_key(action_row, "Save", self.commit_edit, weight=1)

        for row_idx, keys in enumerate(self._keyboard_rows()):
            row = tk.Frame(kb, background="#202020")
            row.pack(
                fill="both",
                expand=True,
                padx=self._scaled(8),
                pady=(self._scaled(6 if row_idx == 0 else 5), 0),
            )
            for key in keys:
                label, value, weight = self._parse_key(key)
                self._make_key(row, label, lambda v=value: self._on_keyboard_key(v), weight=weight)

        controls = tk.Frame(kb, background="#202020")
        controls.pack(fill="both", expand=True, padx=self._scaled(8), pady=self._scaled(8))
        if self._keyboard_mode == "symbols":
            self._make_key(controls, "ABC", lambda: self._set_keyboard_mode("upper"), weight=1)
            self._make_key(controls, "abc", lambda: self._set_keyboard_mode("lower"), weight=1)
        else:
            mode_label = "ABC" if self._keyboard_mode == "lower" else "abc"
            self._make_key(controls, mode_label, self._toggle_case, weight=1)
            self._make_key(controls, "123", self._toggle_symbols, weight=1)
        self._make_key(controls, "Space", lambda: self._insert_text(" "), weight=2)
        self._make_key(controls, "←", self._move_cursor_left, weight=1)
        self._make_key(controls, "→", self._move_cursor_right, weight=1)
        self._make_key(controls, "Del", self._backspace, weight=1)

    def _build_builtin_keypad(self, kb: tk.Toplevel) -> None:
        try:
            for child in kb.winfo_children():
                child.destroy()
        except TclError:
            pass

        action_row = tk.Frame(kb, background="#202020")
        action_row.pack(fill="x", padx=self._scaled(8), pady=(self._scaled(8), 0))
        self._make_key(action_row, "Clear", self._clear_entry, weight=1)
        self._make_key(action_row, "Cancel", self.cancel_edit, weight=1)
        self._make_key(action_row, "Save", self.commit_edit, weight=1)

        for keys in (("7", "8", "9"), ("4", "5", "6"), ("1", "2", "3")):
            row = tk.Frame(kb, background="#202020")
            row.pack(fill="both", expand=True, padx=self._scaled(8), pady=self._scaled(6))
            for key in keys:
                self._make_key(row, key, lambda k=key: self._insert_text(k), weight=1)

        controls = tk.Frame(kb, background="#202020")
        controls.pack(fill="both", expand=True, padx=self._scaled(8), pady=self._scaled(6))
        self._make_key(controls, "←", self._move_cursor_left, weight=1)
        self._make_key(controls, "0", lambda: self._insert_text("0"), weight=1)
        self._make_key(controls, "→", self._move_cursor_right, weight=1)
        self._make_key(controls, "Del", self._backspace, weight=1)

    def _make_key(
        self,
        parent: tk.Frame,
        text: str,
        command: Callable[[], None],
        weight: int = 1,
        **button_kwargs,
    ) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            takefocus=False,
            relief="raised",
            bd=2,
            font=("TkDefaultFont", self._scaled(18)),
            background="#f7f7f7",
            activebackground="#d8d8d8",
            **button_kwargs,
        )
        btn.pack(side="left", fill="both", expand=True, padx=self._scaled(4), ipady=self._scaled(11))
        if weight > 1:
            btn.configure(width=5 * weight)
        return btn

    def _screen_scale(self, screen_w: int | None = None, screen_h: int | None = None) -> float:
        try:
            if screen_w is None or screen_h is None:
                top = self.tk.winfo_toplevel()
                screen_w = int(top.winfo_screenwidth())
                screen_h = int(top.winfo_screenheight())
            short_side = min(screen_w, screen_h)
            long_side = max(screen_w, screen_h)
            if short_side <= 720 or long_side <= 1280:
                return 1.0
            return min(short_side / 720, long_side / 1280)
        except TclError:
            return 1.0

    def _scaled(self, value: int, scale: float | None = None) -> int:
        if scale is None:
            scale = self._screen_scale()
        return max(1, int(round(value * scale)))

    def _make_repeat_key(self, parent: tk.Frame, text: str, command: Callable[[], None], weight: int = 1) -> None:
        self._make_key(
            parent,
            text,
            command,
            weight=weight,
            repeatdelay=550,
            repeatinterval=250,
        )

    def _keyboard_rows(self) -> tuple[tuple[str, ...], ...]:
        if self._keyboard_mode == "symbols":
            return (
                tuple("1234567890"),
                ("!", "@", "#", "$", "%", "^", "&", "*", "(", ")"),
                ("-", "_", "+", "=", "/", "\\", ":", ";", '"', "'"),
                (".", ",", "?", "|", "~", "`", "[", "]", "{", "}"),
            )
        if self._keyboard_mode == "upper":
            return (
                tuple("QWERTYUIOP"),
                tuple("ASDFGHJKL"),
                tuple("ZXCVBNM"),
                ("-", "&", ".", "'", "#"),
            )
        return (
            tuple("qwertyuiop"),
            tuple("asdfghjkl"),
            tuple("zxcvbnm"),
            ("-", "&", ".", "'", "#"),
        )

    @staticmethod
    def _parse_key(key: str | tuple[str, str, int]) -> tuple[str, str, int]:
        if isinstance(key, tuple):
            return key
        return key, key, 1

    def _on_keyboard_key(self, value: str) -> None:
        inserted_text = self._insert_text(value)
        if inserted_text and self._keyboard_mode == "upper" and inserted_text.isupper():
            self._set_keyboard_mode("lower")

    def _toggle_case(self) -> None:
        self._set_keyboard_mode("upper" if self._keyboard_mode == "lower" else "lower")

    def _toggle_symbols(self) -> None:
        self._set_keyboard_mode("lower" if self._keyboard_mode == "symbols" else "symbols")

    def _set_keyboard_mode(self, mode: str) -> None:
        self._keyboard_mode = mode
        if self._keyboard_window is not None:
            self._build_builtin_keyboard(self._keyboard_window)

    def _insert_text(self, text: str) -> str:
        if self._entry is None:
            return ""
        try:
            insert_text = self._text_allowed_for_insert(text)
            if not insert_text:
                self._entry.focus_set()
                return ""
            if self._entry.selection_present():
                self._entry.delete("sel.first", "sel.last")
            self._entry.insert("insert", insert_text)
            self._on_entry_key_release()
            self._entry.focus_set()
            return insert_text
        except TclError:
            return ""

    def _text_allowed_for_insert(self, text: str) -> str:
        if self._entry is None or self.max_length is None:
            return text
        current = self._entry.get()
        selected_len = self._selected_text_length()
        available = self.max_length - (len(current) - selected_len)
        if available <= 0:
            return ""
        return text[:available]

    def _selected_text_length(self) -> int:
        if self._entry is None:
            return 0
        try:
            if not self._entry.selection_present():
                return 0
            return int(self._entry.index("sel.last")) - int(self._entry.index("sel.first"))
        except (TclError, ValueError):
            return 0

    def _backspace(self) -> None:
        if self._entry is None:
            return
        try:
            if self._entry.selection_present():
                self._entry.delete("sel.first", "sel.last")
            else:
                pos = self._entry.index("insert")
                if pos > 0:
                    self._entry.delete(pos - 1, pos)
            self._entry.focus_set()
        except TclError:
            pass

    def _move_cursor_left(self) -> None:
        if self._entry is None:
            return
        try:
            pos = self._entry.index("insert")
            self._entry.selection_clear()
            self._entry.icursor(max(0, pos - 1))
            self._entry.focus_set()
        except TclError:
            pass

    def _move_cursor_right(self) -> None:
        if self._entry is None:
            return
        try:
            pos = self._entry.index("insert")
            self._entry.selection_clear()
            self._entry.icursor(min(len(self._entry.get()), pos + 1))
            self._entry.focus_set()
        except TclError:
            pass

    def _clear_entry(self) -> None:
        if self._entry is None:
            return
        try:
            self._entry.delete(0, "end")
            self._entry.focus_set()
        except TclError:
            pass

    def _is_keyboard_descendant(self, widget: Any) -> bool:
        kb = self._keyboard_window
        if kb is None or widget is None:
            return False
        current = widget
        while current is not None:
            if current is kb:
                return True
            current = getattr(current, "master", None)
        return False

    def _is_choice_descendant(self, widget: Any) -> bool:
        picker = self._choice_window
        if picker is None or widget is None:
            return False
        current = widget
        while current is not None:
            if current is picker:
                return True
            current = getattr(current, "master", None)
        return False
