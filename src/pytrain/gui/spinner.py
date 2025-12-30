#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#  All Rights Reserved.
#
#  This work is licensed under the terms of the LPGL license.
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

from dataclasses import dataclass
from tkinter import TclError
from typing import Callable, List, Optional, Sequence, Union

from guizero import Box, PushButton, TextBox

ValueT = Union[int, str]


@dataclass(frozen=True)
class SpinnerStyle:
    button_width: int = 2
    value_width: int = 2
    button_padx: int = 2
    button_pady: int = 0
    button_text_size: int = 28
    value_text_size: int = 28


class Spinner(Box):
    """
    GuiZero-compatible spinner (numeric up/down).

    Layout:
      - orientation="horizontal":  [ − ] [ value ] [ + ]
      - orientation="vertical":    [ + ]
                                  [ value ]
                                  [ − ]

    Modes:
      - Integer range via min_value/max_value/step
      - Enum mode via values=[...] (overrides integer mode)

    Tap vs hold:
      - repeat=False: tap only
      - repeat=True: tap = one step, hold starts repeating after repeat_delay_ms

    Callback:
      on_change(spinner, value)
    """

    def __init__(
        self,
        parent,
        *,
        value: Optional[ValueT] = None,
        # Integer mode:
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        step: int = 1,
        # Enum mode:
        values: Optional[Sequence[ValueT]] = None,
        # Behavior:
        wrap: bool = False,
        readonly: bool = True,
        allow_typing: bool = False,
        clamp_on_focus_lost: bool = True,
        # Layout:
        orientation: str = "horizontal",  # "horizontal" | "vertical"
        # Repeat:
        repeat: bool = False,
        repeat_delay_ms: int = 450,
        repeat_interval_ms: int = 120,
        # Callback:
        on_change: Optional[Callable[["Spinner", ValueT], None]] = None,
        # Style:
        style: SpinnerStyle = SpinnerStyle(),
        align: str = "left",
        **box_kwargs,
    ):
        super().__init__(parent, align=align, **box_kwargs)

        if step == 0:
            raise ValueError("step must be non-zero")

        if orientation not in ("horizontal", "vertical"):
            raise ValueError("orientation must be 'horizontal' or 'vertical'")

        self._style = style
        self._on_change = on_change

        self._values: Optional[List[ValueT]] = list(values) if values is not None else None
        self._wrap = bool(wrap)

        self._min = 0 if min_value is None else min_value
        self._max = 100 if max_value is None else max_value
        self._step = int(step)

        self._orientation = orientation

        # Repeat config/state (tap vs. hold)
        self._repeat = bool(repeat)
        self._repeat_delay_ms = int(repeat_delay_ms)
        self._repeat_interval_ms = int(repeat_interval_ms)
        self._repeat_job: Optional[str] = None
        self._repeat_direction: int = 0
        self._repeat_started: bool = False

        # Determine initial value + mode
        if self._values is not None:
            if len(self._values) == 0:
                raise ValueError("values must be non-empty if provided")
            if value is None:
                value = self._values[0]
            if value not in self._values:
                raise ValueError(f"Initial value {value!r} not in values list")
            self._value: ValueT = value
        else:
            if self._min > self._max:
                raise ValueError("min_value must be <= max_value")
            if value is None:
                value = self._min
            try:
                iv = int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError) as e:
                raise ValueError(f"Initial value {value!r} not an int") from e
            self._value = self._clamp_int(iv)

        # Inner container so we can control orientation reliably
        self._inner = Box(self, layout="auto")

        # If repeat is enabled, do NOT also use command= (prevents double-trigger)
        down_cmd = None if self._repeat else self.decrement
        up_cmd = None if self._repeat else self.increment

        self._btn_down = PushButton(
            self._inner,
            text="−",
            width=self._style.button_width,
            padx=self._style.button_padx,
            pady=self._style.button_pady,
            command=down_cmd,
        )
        self._btn_down.text_size = self._style.button_text_size

        self._txt = TextBox(self._inner, text=str(self._value), width=self._style.value_width)
        self._txt.text_size = self._style.value_text_size

        self._btn_up = PushButton(
            self._inner,
            text="+",
            width=self._style.button_width,
            padx=self._style.button_padx,
            pady=self._style.button_pady,
            command=up_cmd,
        )
        self._btn_up.text_size = self._style.button_text_size

        # Apply orientation ordering
        self._apply_orientation()

        # Text behavior: non-editable display that stays black-on-white
        self._txt_is_readonly = bool(readonly and not allow_typing)

        # If typing is allowed, leave it as a normal TextBox (GuiZero handles it)
        if not self._txt_is_readonly:
            self._txt.enabled = True
        else:
            self._set_textbox_readonly_appearance()

        if clamp_on_focus_lost:
            self._install_commit_bindings()

        if self._repeat:
            self._install_repeat_bindings()

        self._update_buttons_enabled()

    def _set_textbox_readonly_appearance(self) -> None:
        try:
            self._txt.tk.configure(
                state="readonly",
                readonlybackground="white",
                fg="black",
                disabledbackground="white",
                disabledforeground="black",
            )
            # Optional: prevent focus/caret
            self._txt.tk.configure(takefocus=0)
        except (AttributeError, TclError):
            pass

    def _set_textbox_text(self, text: str) -> None:
        """
        Update the Entry *without* using guizero's TextBox.value setter,
        because that setter can disable the widget when state='readonly'.
        """
        try:
            entry = self._txt.tk
            if self._txt_is_readonly:
                entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, text)
            if self._txt_is_readonly:
                entry.configure(state="readonly")
                # Re-assert colors in case anything toggled state internally
                entry.configure(
                    readonlybackground="white",
                    fg="black",
                    disabledbackground="white",
                    disabledforeground="black",
                )
        except (AttributeError, TclError):
            # Fallback (may gray out again on some guizero versions, but better than crashing)
            self._txt.value = text

    # ----------------------------
    # Public API
    # ----------------------------

    @property
    def value(self) -> ValueT:
        return self._value

    @value.setter
    def value(self, v: ValueT) -> None:
        self.set(v, fire=True)

    def set(self, v: ValueT, *, fire: bool = False) -> None:
        new_val = self._coerce_to_mode(v)
        if new_val == self._value:
            self._render()
            self._update_buttons_enabled()
            return

        self._value = new_val
        self._render()
        self._update_buttons_enabled()
        if fire and self._on_change:
            self._on_change(self, self._value)

    def increment(self) -> None:
        self._step_by(+1)

    def decrement(self) -> None:
        self._step_by(-1)

    def configure(
        self,
        *,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        step: Optional[int] = None,
        values: Optional[Sequence[ValueT]] = None,
        wrap: Optional[bool] = None,
        orientation: Optional[str] = None,
        repeat: Optional[bool] = None,
        repeat_delay_ms: Optional[int] = None,
        repeat_interval_ms: Optional[int] = None,
    ) -> None:
        if values is not None:
            if len(values) == 0:
                raise ValueError("values must be non-empty")
            self._values = list(values)

        if min_value is not None:
            self._min = min_value
        if max_value is not None:
            self._max = max_value
        if step is not None:
            if step == 0:
                raise ValueError("step must be non-zero")
            self._step = int(step)
        if wrap is not None:
            self._wrap = bool(wrap)

        if orientation is not None:
            if orientation not in ("horizontal", "vertical"):
                raise ValueError("orientation must be 'horizontal' or 'vertical'")
            self._orientation = orientation
            self._apply_orientation()

        if repeat is not None:
            self._repeat = bool(repeat)
            # Swap command usage depending on repeat mode
            self._btn_down.command = None if self._repeat else self.decrement
            self._btn_up.command = None if self._repeat else self.increment
            if self._repeat:
                self._install_repeat_bindings()

        if repeat_delay_ms is not None:
            self._repeat_delay_ms = int(repeat_delay_ms)
        if repeat_interval_ms is not None:
            self._repeat_interval_ms = int(repeat_interval_ms)

        self._value = self._coerce_to_mode(self._value)
        self._render()
        self._update_buttons_enabled()

    # ----------------------------
    # Internals
    # ----------------------------

    def _mode_is_enum(self) -> bool:
        return self._values is not None

    def _coerce_to_mode(self, v: ValueT) -> ValueT:
        if self._mode_is_enum():
            assert self._values is not None
            if v in self._values:
                return v
            sv = str(v)
            for item in self._values:
                if str(item) == sv:
                    return item
            return self._value

        try:
            iv = int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return self._value
        return self._clamp_int(iv)

    def _clamp_int(self, iv: int) -> int:
        if iv < self._min:
            return self._min
        if iv > self._max:
            return self._max
        return iv

    def _at_min(self) -> bool:
        if self._mode_is_enum():
            assert self._values is not None
            try:
                return self._values.index(self._value) == 0
            except ValueError:
                return True
        return int(self._value) <= self._min  # type: ignore[arg-type]

    def _at_max(self) -> bool:
        if self._mode_is_enum():
            assert self._values is not None
            try:
                return self._values.index(self._value) == (len(self._values) - 1)
            except ValueError:
                return True
        return int(self._value) >= self._max  # type: ignore[arg-type]

    def _step_by(self, direction: int) -> None:
        old = self._value

        if self._mode_is_enum():
            assert self._values is not None
            try:
                idx = self._values.index(self._value)
            except ValueError:
                idx = 0

            nxt = idx + direction
            if nxt < 0:
                nxt = (len(self._values) - 1) if self._wrap else 0
            elif nxt >= len(self._values):
                nxt = 0 if self._wrap else (len(self._values) - 1)

            self._value = self._values[nxt]

        else:
            iv = int(self._value)  # type: ignore[arg-type]
            iv2 = iv + (direction * self._step)

            if self._wrap:
                span = self._max - self._min + 1
                if span <= 0:
                    self._value = self._min
                elif iv2 < self._min:
                    self._value = self._max - ((self._min - iv2 - 1) % span)
                elif iv2 > self._max:
                    self._value = self._min + ((iv2 - self._max - 1) % span)
                else:
                    self._value = iv2
            else:
                self._value = self._clamp_int(iv2)

        self._render()
        self._update_buttons_enabled()

        if self._value != old and self._on_change:
            self._on_change(self, self._value)

    def _render(self) -> None:
        self._set_textbox_text(str(self._value))

    def _update_buttons_enabled(self) -> None:
        if self._wrap:
            self._btn_down.enable()
            self._btn_up.enable()
            return

        (self._btn_down.disable() if self._at_min() else self._btn_down.enable())
        (self._btn_up.disable() if self._at_max() else self._btn_up.enable())

    def _commit_typed_value(self) -> None:
        self.set(self._txt.value, fire=True)

    # ----------------------------
    # Orientation
    # ----------------------------

    def _apply_orientation(self) -> None:
        """
        Re-pack the inner widgets in the requested order.
        Requires access to underlying tk widgets.
        """
        try:
            down = self._btn_down.tk
            txt = self._txt.tk
            up = self._btn_up.tk
        except AttributeError:
            return

        try:
            down.pack_forget()
            txt.pack_forget()
            up.pack_forget()
        except TclError:
            return

        try:
            if self._orientation == "horizontal":
                down.pack(side="left")
                txt.pack(side="left")
                up.pack(side="left")
            else:
                up.pack(side="top")
                txt.pack(side="top")
                down.pack(side="top")
        except TclError:
            return

    # ----------------------------
    # Tk bindings: commit + repeat
    # ----------------------------

    def _install_commit_bindings(self) -> None:
        try:
            tk = self._txt.tk
        except AttributeError:
            return
        try:
            tk.bind("<FocusOut>", lambda _e: self._commit_typed_value())
            tk.bind("<Return>", lambda _e: self._commit_typed_value())
        except TclError:
            return

    def _install_repeat_bindings(self) -> None:
        try:
            down_tk = self._btn_down.tk
            up_tk = self._btn_up.tk
        except AttributeError:
            self._repeat = False
            return

        try:
            down_tk.bind("<ButtonPress-1>", lambda _e: self._on_press(-1))
            down_tk.bind("<ButtonRelease-1>", lambda _e: self._on_release(-1))
            down_tk.bind("<Leave>", lambda _e: self._stop_repeat())

            up_tk.bind("<ButtonPress-1>", lambda _e: self._on_press(+1))
            up_tk.bind("<ButtonRelease-1>", lambda _e: self._on_release(+1))
            up_tk.bind("<Leave>", lambda _e: self._stop_repeat())
        except TclError:
            self._repeat = False

    def _on_press(self, direction: int) -> None:
        # Schedule repeat; no immediate step (prevents "light press" jumping)
        self._stop_repeat()
        self._repeat_direction = direction
        self._repeat_started = False
        try:
            self._repeat_job = self.tk.after(self._repeat_delay_ms, self._begin_repeat)
        except (AttributeError, TclError):
            self._repeat_job = None

    def _on_release(self, direction: int) -> None:
        # If repeat never started, treat as a tap => exactly one step.
        started = self._repeat_started
        self._stop_repeat()
        if not started:
            self._step_by(direction)

    def _begin_repeat(self) -> None:
        if self._repeat_direction == 0:
            return
        self._repeat_started = True
        self._repeat_tick()

    def _repeat_tick(self) -> None:
        if self._repeat_direction == 0:
            return
        self._step_by(self._repeat_direction)
        try:
            self._repeat_job = self.tk.after(self._repeat_interval_ms, self._repeat_tick)
        except (AttributeError, TclError):
            self._repeat_job = None

    def _stop_repeat(self) -> None:
        self._repeat_direction = 0
        self._repeat_started = False
        if self._repeat_job is None:
            return
        try:
            self.tk.after_cancel(self._repeat_job)
        except (AttributeError, TclError):
            pass
        finally:
            self._repeat_job = None
