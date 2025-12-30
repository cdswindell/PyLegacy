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
    value_width: int = 6
    button_padx: int = 2
    button_pady: int = 0


class Spinner(Box):
    """
    GuiZero-compatible spinner (numeric up/down):
      [-] [ value ] [+]

    Modes:
      - Integer range mode via min_value/max_value/step
      - Enum mode via values=[...] (overrides integer mode)

    Callback:
      on_change(spinner, value)
    """

    def __init__(
        self,
        parent,
        *,
        value: Optional[ValueT] = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        step: int = 1,
        values: Optional[Sequence[ValueT]] = None,
        wrap: bool = False,
        readonly: bool = True,
        allow_typing: bool = False,
        clamp_on_focus_lost: bool = True,
        repeat: bool = True,
        repeat_delay_ms: int = 450,
        repeat_interval_ms: int = 90,
        on_change: Optional[Callable[["Spinner", ValueT], None]] = None,
        style: SpinnerStyle = SpinnerStyle(),
        align: str = "left",
        **box_kwargs,
    ):
        super().__init__(parent, align=align, **box_kwargs)

        if step == 0:
            raise ValueError("step must be non-zero")

        self._style = style
        self._on_change = on_change

        self._values: Optional[List[ValueT]] = list(values) if values is not None else None
        self._wrap = bool(wrap)

        self._min = min_value
        self._max = max_value
        self._step = int(step)

        self._repeat = bool(repeat)
        self._repeat_delay_ms = int(repeat_delay_ms)
        self._repeat_interval_ms = int(repeat_interval_ms)
        self._repeat_job: Optional[str] = None
        self._repeat_direction = 0

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
            if self._min is None:
                self._min = 0
            if self._max is None:
                self._max = 100
            if self._min > self._max:
                raise ValueError("min_value must be <= max_value")
            if value is None:
                value = self._min

            try:
                iv = int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError) as e:
                raise ValueError(f"Initial value {value!r} not an int") from e

            self._value = self._clamp_int(iv)

        # Widgets
        self._btn_down = PushButton(
            self,
            text="−",
            width=self._style.button_width,
            padx=self._style.button_padx,
            pady=self._style.button_pady,
            command=self.decrement,
        )
        self._txt = TextBox(self, text=str(self._value), width=self._style.value_width)
        self._btn_up = PushButton(
            self,
            text="+",
            width=self._style.button_width,
            padx=self._style.button_padx,
            pady=self._style.button_pady,
            command=self.increment,
        )

        # Text behavior
        self._txt.enabled = (not readonly) or bool(allow_typing)
        if readonly and not allow_typing:
            self._txt.disable()

        if clamp_on_focus_lost:
            self._install_commit_bindings()

        if self._repeat:
            self._install_repeat_bindings()

        self._update_buttons_enabled()

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
        assert self._min is not None and self._max is not None
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
        assert self._min is not None
        return int(self._value) <= self._min  # type: ignore[arg-type]

    def _at_max(self) -> bool:
        if self._mode_is_enum():
            assert self._values is not None
            try:
                return self._values.index(self._value) == (len(self._values) - 1)
            except ValueError:
                return True
        assert self._max is not None
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

            assert self._min is not None and self._max is not None
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
        self._txt.value = str(self._value)

    def _update_buttons_enabled(self) -> None:
        if self._wrap:
            self._btn_down.enable()
            self._btn_up.enable()
            return

        (self._btn_down.disable() if self._at_min() else self._btn_down.enable())
        (self._btn_up.disable() if self._at_max() else self._btn_up.enable())

    def _commit_typed_value(self) -> None:
        typed = self._txt.value
        self.set(typed, fire=True)

    # ----------------------------
    # Tk bindings (focus commit + repeat)
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
        # Fall back to click-only if tk bindings aren't available
        try:
            down_tk = self._btn_down.tk
            up_tk = self._btn_up.tk
        except AttributeError:
            self._repeat = False
            return

        try:
            down_tk.bind("<ButtonPress-1>", lambda _e: self._start_repeat(-1))
            down_tk.bind("<ButtonRelease-1>", lambda _e: self._stop_repeat())
            down_tk.bind("<Leave>", lambda _e: self._stop_repeat())

            up_tk.bind("<ButtonPress-1>", lambda _e: self._start_repeat(+1))
            up_tk.bind("<ButtonRelease-1>", lambda _e: self._stop_repeat())
            up_tk.bind("<Leave>", lambda _e: self._stop_repeat())
        except TclError:
            self._repeat = False

    def _start_repeat(self, direction: int) -> None:
        if not self._repeat:
            return

        self._stop_repeat()
        self._repeat_direction = direction

        # immediate step for responsiveness
        self._step_by(direction)

        try:
            self._repeat_job = self.tk.after(self._repeat_delay_ms, self._repeat_tick)
        except (AttributeError, TclError):
            self._repeat_job = None

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
        if self._repeat_job is None:
            return
        try:
            self.tk.after_cancel(self._repeat_job)
        except (AttributeError, TclError):
            pass
        finally:
            self._repeat_job = None
