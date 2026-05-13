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
import os
import shlex
import shutil
import subprocess
import time
import tkinter as tk
from tkinter import TclError
from typing import Any, Callable, Sequence

from guizero import Text

log = logging.getLogger(__name__)

OSK_COMMAND_ENV = "PYTRAIN_OSK_COMMAND"
DEFAULT_OSK_COMMANDS = (
    ("wvkbd-mobintl",),
    ("wvkbd",),
    ("squeekboard",),
    ("onboard",),
    ("matchbox-keyboard",),
    ("florence",),
)


class EditableText(Text):
    """
    Drop-in replacement for guizero.Text that becomes editable after a press-and-hold.

    The displayed widget remains the guizero Text/Label. While editing, a Tk Entry is
    temporarily placed over the label so existing GuiZero layout code does not need to change.
    """

    def __init__(
        self,
        *args,
        text: str = "",
        hold_threshold: float = 1.0,
        debounce_ms: int = 80,
        max_length: int | None = None,
        on_commit: Callable[["EditableText", str, str], None] | tuple | list | None = None,
        on_cancel: Callable[["EditableText", str], None] | tuple | list | None = None,
        commit_on_focus_lost: bool = True,
        select_all_on_edit: bool = True,
        cancel_on_leave: bool = False,
        show_keyboard_on_edit: bool = True,
        keyboard_command: str | Sequence[str] | None = None,
        keyboard_candidates: Sequence[str | Sequence[str]] | None = None,
        prefer_system_keyboard: bool = False,
        use_builtin_keyboard: bool = True,
        hide_keyboard_on_finish: bool = True,
        edit_bg: str = "white",
        edit_fg: str = "black",
        **kwargs,
    ):
        super().__init__(*args, text=text, **kwargs)

        self.hold_threshold = float(hold_threshold)
        self.debounce_ms = int(debounce_ms)
        self.max_length = max_length
        self.on_commit = on_commit
        self.on_cancel = on_cancel
        self.commit_on_focus_lost = bool(commit_on_focus_lost)
        self.select_all_on_edit = bool(select_all_on_edit)
        self.cancel_on_leave = bool(cancel_on_leave)
        self.show_keyboard_on_edit = bool(show_keyboard_on_edit)
        self.keyboard_command = keyboard_command
        self.keyboard_candidates = (
            tuple(keyboard_candidates) if keyboard_candidates is not None else DEFAULT_OSK_COMMANDS
        )
        self.prefer_system_keyboard = bool(prefer_system_keyboard)
        self.use_builtin_keyboard = bool(use_builtin_keyboard)
        self.hide_keyboard_on_finish = bool(hide_keyboard_on_finish)
        self.edit_bg = edit_bg
        self.edit_fg = edit_fg

        self._press_time: float | None = None
        self._pressed = False
        self._editing = False
        self._hold_after_id: str | None = None
        self._keyboard_after_id: str | None = None
        self._keyboard_process: subprocess.Popen | None = None
        self._keyboard_window: tk.Toplevel | None = None
        self._keyboard_mode = "lower"
        self._value_before_edit = ""
        self._entry: tk.Entry | None = None

        self.tk.bind("<ButtonPress-1>", self._on_press, add="+")
        self.tk.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.tk.bind("<Leave>", self._on_leave, add="+")
        self.tk.bind("<Configure>", self._on_configure, add="+")

        try:
            self.tk.configure(cursor="hand2")
        except TclError:
            pass

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
            tk_target.configure(cursor="hand2")
        except (AttributeError, TclError):
            pass

    @property
    def is_editing(self) -> bool:
        return self._editing

    def begin_edit(self) -> None:
        if self._editing:
            return

        self._cancel_hold_timer()
        self._editing = True
        self._value_before_edit = "" if self.value is None else str(self.value)

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

        entry = self._entry
        new_value = self._value_before_edit if entry is None else entry.get()
        new_value = self._coerce_text(new_value)
        old_value = self._value_before_edit

        self._finish_edit()
        self.value = new_value

        if new_value != old_value:
            self._invoke_callback(self.on_commit, self, new_value, old_value)

    def cancel_edit(self) -> None:
        if not self._editing:
            return

        old_value = self._value_before_edit
        self._finish_edit()
        self.value = old_value
        self._invoke_callback(self.on_cancel, self, old_value)

    def destroy(self):
        self._cancel_hold_timer()
        if self._entry is not None:
            try:
                self._entry.destroy()
            except TclError:
                pass
            self._entry = None
        self._hide_keyboard()
        super().destroy()

    # -------------------------
    # Event handling
    # -------------------------

    # noinspection PyUnusedLocal
    def _on_press(self, event=None) -> None:
        if self._editing:
            return

        self._pressed = True
        self._press_time = time.monotonic()
        self._cancel_hold_timer()
        self._hold_after_id = self.tk.after(int(self.hold_threshold * 1000), self._on_hold)

    # noinspection PyUnusedLocal
    def _on_release(self, event=None) -> None:
        self._pressed = False
        self._cancel_hold_timer()

    # noinspection PyUnusedLocal
    def _on_leave(self, event=None) -> None:
        if self._editing or not self.cancel_on_leave:
            return
        self._pressed = False
        self._cancel_hold_timer()

    # noinspection PyUnusedLocal
    def _on_configure(self, event=None) -> None:
        if self._editing:
            self._position_entry()

    def _on_hold(self) -> None:
        self._hold_after_id = None
        if not self._pressed:
            return

        elapsed = (time.monotonic() - self._press_time) if self._press_time else 0.0
        if elapsed < (self.debounce_ms / 1000.0):
            return

        self.begin_edit()

    # noinspection PyUnusedLocal
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
    # Entry overlay
    # -------------------------

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

    # noinspection PyUnusedLocal
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
        if focused is self._entry or self._is_keyboard_descendant(focused):
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

    def _finish_edit(self) -> None:
        self._editing = False
        self._pressed = False
        self._cancel_hold_timer()
        self._cancel_keyboard_timer()
        if self.hide_keyboard_on_finish:
            self._hide_keyboard()
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
        text = "" if value is None else str(value)
        if self.max_length is not None:
            return text[: self.max_length]
        return text

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
        if self._keyboard_process is not None and self._keyboard_process.poll() is None:
            return

        cmd = self._resolve_keyboard_command() if self.prefer_system_keyboard else self._explicit_keyboard_command()
        if not cmd:
            if self.use_builtin_keyboard:
                self._show_builtin_keyboard()
            return

        try:
            self._keyboard_process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except (FileNotFoundError, OSError):
            log.debug("Unable to show on-screen keyboard with command: %s", cmd, exc_info=True)
            if self.use_builtin_keyboard:
                self._show_builtin_keyboard()

    def _hide_keyboard(self) -> None:
        if self._keyboard_window is not None:
            try:
                self._keyboard_window.destroy()
            except TclError:
                pass
            self._keyboard_window = None

        proc = self._keyboard_process
        self._keyboard_process = None
        if proc is None or proc.poll() is not None:
            return

        try:
            proc.terminate()
        except OSError:
            pass

    # noinspection PyDeprecation
    def _resolve_keyboard_command(self) -> list[str] | None:
        command = self._explicit_keyboard_command()
        if command:
            return command

        for candidate in self.keyboard_candidates:
            cmd = self._normalize_command(candidate)
            if cmd and shutil.which(cmd[0]):
                return cmd
        return None

    def _explicit_keyboard_command(self) -> list[str] | None:
        command = self.keyboard_command or os.environ.get(OSK_COMMAND_ENV)
        return self._normalize_command(command) if command else None

    @staticmethod
    def _normalize_command(command: str | Sequence[str]) -> list[str] | None:
        if isinstance(command, str):
            cmd = shlex.split(command)
        else:
            cmd = [str(part) for part in command]
        return cmd or None

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
            top = self.tk.winfo_toplevel()
            kb = tk.Toplevel(top)
            self._keyboard_window = kb
            kb.transient(top)
            kb.title("Keyboard")
            kb.configure(background="#202020")
            try:
                kb.attributes("-topmost", True)
            except TclError:
                pass
            kb.protocol("WM_DELETE_WINDOW", self.cancel_edit)
            self._position_builtin_keyboard(kb)
            self._build_builtin_keyboard(kb)
            kb.lift()
            self._entry.focus_set()
        except TclError:
            self._keyboard_window = None
            log.debug("Unable to show built-in keyboard", exc_info=True)

    def _position_builtin_keyboard(self, kb: tk.Toplevel) -> None:
        try:
            top = self.tk.winfo_toplevel()
            screen_w = int(top.winfo_screenwidth())
            screen_h = int(top.winfo_screenheight())
            kb_w = min(screen_w, 980)
            kb_h = min(screen_h, 420)
            x = max(0, int(top.winfo_rootx()) + (int(top.winfo_width()) - kb_w) // 2)
            y = max(0, screen_h - kb_h)
            kb.geometry(f"{kb_w}x{kb_h}+{x}+{y}")
        except TclError:
            pass

    def _build_builtin_keyboard(self, kb: tk.Toplevel) -> None:
        try:
            for child in kb.winfo_children():
                child.destroy()
        except TclError:
            pass

        action_row = tk.Frame(kb, background="#202020")
        action_row.pack(fill="x", padx=8, pady=(8, 0))
        self._make_key(action_row, "Clear", self._clear_entry, weight=1)
        self._make_key(action_row, "Cancel", self.cancel_edit, weight=1)
        self._make_key(action_row, "Enter", self.commit_edit, weight=1)

        for row_idx, keys in enumerate(self._keyboard_rows()):
            row = tk.Frame(kb, background="#202020")
            row.pack(fill="x", padx=8, pady=(6 if row_idx == 0 else 5, 0))
            for key in keys:
                label, value, weight = self._parse_key(key)
                self._make_key(row, label, lambda v=value: self._on_keyboard_key(v), weight=weight)

        controls = tk.Frame(kb, background="#202020")
        controls.pack(fill="x", padx=8, pady=8)
        mode_label = "ABC" if self._keyboard_mode == "lower" else "abc" if self._keyboard_mode == "upper" else "abc"
        self._make_key(controls, mode_label, self._toggle_case, weight=1)
        symbol_label = "123" if self._keyboard_mode != "symbols" else "abc"
        self._make_key(controls, symbol_label, self._toggle_symbols, weight=1)
        self._make_key(controls, "Space", lambda: self._insert_text(" "), weight=4)
        self._make_key(controls, "Backspace", self._backspace, weight=2)

    @staticmethod
    def _make_key(parent: tk.Frame, text: str, command: Callable[[], None], weight: int = 1) -> None:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            takefocus=False,
            relief="raised",
            bd=2,
            font=("TkDefaultFont", 18),
            background="#f7f7f7",
            activebackground="#d8d8d8",
        )
        btn.pack(side="left", fill="both", expand=True, padx=4, ipady=11)
        if weight > 1:
            btn.configure(width=5 * weight)

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
        self._insert_text(value)

    def _toggle_case(self) -> None:
        self._keyboard_mode = "upper" if self._keyboard_mode == "lower" else "lower"
        if self._keyboard_window is not None:
            self._build_builtin_keyboard(self._keyboard_window)

    def _toggle_symbols(self) -> None:
        self._keyboard_mode = "lower" if self._keyboard_mode == "symbols" else "symbols"
        if self._keyboard_window is not None:
            self._build_builtin_keyboard(self._keyboard_window)

    def _insert_text(self, text: str) -> None:
        if self._entry is None:
            return
        try:
            if self._entry.selection_present():
                self._entry.delete("sel.first", "sel.last")
            self._entry.insert("insert", text)
            self._on_entry_key_release()
            self._entry.focus_set()
        except TclError:
            pass

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
