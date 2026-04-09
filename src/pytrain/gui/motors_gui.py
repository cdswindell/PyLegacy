#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from tkinter import TclError
from typing import cast

from guizero import Box, Slider, Text
from guizero.base import Widget

from .components.hold_button import HoldButton
from .state_based_gui import S
from ..db.accessory_state import AccessoryState
from ..gui.component_state_gui import ComponentStateGui
from ..gui.guizero_base import LIONEL_BLUE, LIONEL_ORANGE
from ..gui.state_based_gui import StateBasedGui
from ..pdi.amc2_req import Amc2Req
from ..pdi.constants import Amc2Action, PdiCommand
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum

OUTPUT_ORDER: list[tuple[str, int, str]] = [
    ("motor", 1, "Motor #1"),
    ("motor", 2, "Motor #2"),
    ("lamp", 1, "Light #1"),
    ("lamp", 2, "Light #2"),
    ("lamp", 3, "Light #3"),
    ("lamp", 4, "Light #4"),
]
OUTPUT_STEP = 5
BUTTON_ON_BG = "green"
BUTTON_OFF_BG = "lightgrey"
LEVEL_BOX_MIN_SCREEN_HEIGHT = 500


@dataclass(slots=True)
class OutputWidgets:
    container: Box
    toggle_btn: HoldButton
    level_box: Text | None
    slider: Slider
    output_type: str
    output_id: int
    label: str

    def widgets(self) -> list[Widget]:
        widgets: list[Widget] = [self.container, self.toggle_btn, self.slider]
        if self.level_box is not None:
            widgets.append(self.level_box)
        return widgets


class MotorsGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggregator: ComponentStateGui = None,
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
        screens: int | None = None,
        stand_alone: bool = True,
        parent=None,
        full_screen: bool = True,
        x_offset: int = 0,
        y_offset: int = 0,
    ) -> None:
        StateBasedGui.__init__(
            self,
            "Motors",
            label,
            width,
            height,
            aggregator,
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
            screens=screens,
            stand_alone=stand_alone,
            parent=parent,
            full_screen=full_screen,
            x_offset=x_offset,
            y_offset=y_offset,
        )
        self._making_buttons = True
        self._output_by_tmcc: dict[int, dict[tuple[str, int], OutputWidgets]] = {}
        self._last_non_zero_lamp_level: dict[tuple[int, int], int] = {}
        self._suspended_slider_callbacks: set[tuple[int, str, int]] = set()
        self._screen_height: int | None = None

    def build_gui(self) -> None:
        super().build_gui()
        self._hide_nav_controls()
        self.app.tk.update_idletasks()
        self.y_offset = self.box.tk.winfo_y() + self.box.tk.winfo_height()
        self._capture_screen_height()
        # Failsafe: never leave controls non-interactive if post-process callback stalls.
        self.app.after(2000, self.clear_making_buttons)

    def _capture_screen_height(self) -> None:
        try:
            h = int(self.app.tk.winfo_screenheight())
            if h > 0:
                self._screen_height = h
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def _effective_screen_height(self) -> int:
        if isinstance(self._screen_height, int) and self._screen_height > 0:
            return self._screen_height
        try:
            h = int(self.app.tk.winfo_screenheight())
            if h > 0:
                self._screen_height = h
                return h
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        return int(self.height)

    def _show_level_box(self) -> bool:
        return self._effective_screen_height() >= LEVEL_BOX_MIN_SCREEN_HEIGHT

    def _hide_nav_controls(self) -> None:
        for widget in (self.left_scroll_btn, self.right_scroll_btn, self.by_name, self.by_number):
            if widget:
                try:
                    widget.hide()
                except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                    pass

    def _post_process_state_buttons(self) -> None:
        self._hide_nav_controls()
        self.app.after(150, self.clear_making_buttons)

    def clear_making_buttons(self) -> None:
        self._making_buttons = False

    @property
    def is_making_buttons(self) -> bool:
        return self._making_buttons

    def _reset_state_buttons(self) -> None:
        self._output_by_tmcc.clear()
        self._suspended_slider_callbacks.clear()
        super()._reset_state_buttons()

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            if acc.is_amc2:
                pds.append(cast(AccessoryState, acc))
        return pds

    def is_active(self, state: AccessoryState) -> bool:
        _ = state
        return False

    def switch_state(self, pd: AccessoryState) -> None:
        _ = pd

    @staticmethod
    def _normalize_level(value: int | float | str) -> int:
        try:
            raw = int(float(value))
        except (TypeError, ValueError):
            return 0
        clipped = min(100, max(0, raw))
        remainder = clipped % OUTPUT_STEP
        if remainder == 0:
            return clipped
        down = clipped - remainder
        up = down + OUTPUT_STEP
        return min(100, up) if (clipped - down) >= (up - clipped) else down

    @staticmethod
    def _format_level(value: int) -> str:
        return f"{max(0, min(100, value)):03d}"

    @staticmethod
    def is_motor_active(state: AccessoryState, motor: int) -> bool:
        motor_state = state.motor2 if motor == 2 else state.motor1
        return state.is_motor_on(motor_state)

    @staticmethod
    def is_lamp_active(state: AccessoryState, lamp: int) -> bool:
        lamp_state = state.get_lamp(lamp)
        return bool(lamp_state and lamp_state.level > 0)

    def _state_for_tmcc(self, tmcc_id: int) -> AccessoryState | None:
        for state in self._states.values():
            if isinstance(state, AccessoryState) and state.tmcc_id == tmcc_id and state.scope == CommandScope.ACC:
                return state
        return None

    @staticmethod
    def _style_slider(slider: Slider, is_active: bool) -> None:
        trough = LIONEL_BLUE if is_active else "lightgrey"
        try:
            slider.bg = "white"
            slider.tk.config(troughcolor=trough)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    @staticmethod
    def _set_toggle_button_state(output: OutputWidgets, is_active: bool) -> None:
        output.toggle_btn.text = output.label
        output.toggle_btn.bg = BUTTON_ON_BG if is_active else BUTTON_OFF_BG
        output.toggle_btn.text_color = "white" if is_active else "black"

    def _set_level_ui(self, output: OutputWidgets, value: int) -> None:
        normalized = self._normalize_level(value)
        callback_key = (getattr(output.slider, "tmcc_id", 0), output.output_type, output.output_id)
        if self._normalize_level(output.slider.value) != normalized:
            # noinspection PyArgumentList
            with self._suspend_slider_callback(callback_key):
                output.slider.value = normalized
        if output.level_box is not None:
            output.level_box.value = self._format_level(normalized)

    @contextmanager
    def _suspend_slider_callback(self, callback_key: tuple[int, str, int]):
        self._suspended_slider_callbacks.add(callback_key)
        try:
            yield
        finally:
            self._suspended_slider_callbacks.discard(callback_key)

    @staticmethod
    def _is_slider_focused(slider: Slider) -> bool:
        try:
            return slider.tk.focus_displayof() == slider.tk
        except (AttributeError, RuntimeError, TclError):
            return False

    # noinspection PyTypeChecker
    def update_button(self, state: S) -> None:
        with self._cv:
            pd = cast(AccessoryState, state)
            outputs = self._output_by_tmcc.get(pd.tmcc_id, {})
            for (output_type, output_id), output in outputs.items():
                if output_type == "motor":
                    motor_state = pd.get_motor(output_id)
                    level = motor_state.speed if motor_state else 0
                    is_active = self.is_motor_active(pd, output_id)
                else:
                    lamp_state = pd.get_lamp(output_id)
                    level = lamp_state.level if lamp_state else 0
                    is_active = self.is_lamp_active(pd, output_id)
                    if level > 0:
                        self._last_non_zero_lamp_level[(pd.tmcc_id, output_id)] = level

                self._set_toggle_button_state(output, is_active)
                self._style_slider(output.slider, is_active)

                if not self._is_slider_focused(output.slider):
                    self._set_level_ui(output, level)
                else:
                    if output.level_box is not None:
                        output.level_box.value = self._format_level(self._normalize_level(output.slider.value))

    def set_motor_state(self, tmcc_id: int, motor: int, speed: int = None) -> None:
        if self._making_buttons:
            return
        with self._cv:
            pd = self._state_for_tmcc(tmcc_id)
            if pd is None:
                return
            motor_state = pd.get_motor(motor)
            current = motor_state.speed if motor_state else 0
            if speed is None:
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
                if self.is_motor_active(pd, motor):
                    CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()
                else:
                    CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()
                return

            normalized = self._normalize_level(speed)
            if current == normalized:
                return
            Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.MOTOR, motor=motor - 1, speed=normalized).send()
            CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
            if normalized > 0:
                CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()

    def set_lamp_state(self, tmcc_id: int, lamp: int, level: int) -> None:
        if self._making_buttons:
            return
        with self._cv:
            pd = self._state_for_tmcc(tmcc_id)
            if pd is None:
                return
            lamp_state = pd.get_lamp(lamp)
            current = lamp_state.level if lamp_state else 0
            normalized = self._normalize_level(level)
            if normalized == current:
                return
            if normalized > 0:
                self._last_non_zero_lamp_level[(tmcc_id, lamp)] = normalized
            Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.LAMP, lamp=lamp - 1, level=normalized).send()
            CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=lamp + 2).send()

    def toggle_motor_state(self, tmcc_id: int, motor: int) -> None:
        with self._cv:
            pd = self._state_for_tmcc(tmcc_id)
            if pd is None:
                return
            motor_state = pd.get_motor(motor)
            current_level = motor_state.speed if motor_state else 0
            is_active = self.is_motor_active(pd, motor)
            if not is_active and current_level == 0:
                target = 100
                output = self._output_by_tmcc.get(tmcc_id, {}).get(("motor", motor))
                if output is not None:
                    self._set_level_ui(output, target)
                    self._style_slider(output.slider, True)
                    self._set_toggle_button_state(output, True)
            else:
                target = None
        self.set_motor_state(tmcc_id, motor, target)

    def toggle_lamp_state(self, tmcc_id: int, lamp: int) -> None:
        with self._cv:
            pd = self._state_for_tmcc(tmcc_id)
            if pd is None:
                return
            lamp_state = pd.get_lamp(lamp)
            current_level = lamp_state.level if lamp_state else 0
            if current_level > 0:
                self._last_non_zero_lamp_level[(tmcc_id, lamp)] = current_level
                target = 0
            else:
                target = 100
            output = self._output_by_tmcc.get(tmcc_id, {}).get(("lamp", lamp))
            if output is not None:
                self._set_level_ui(output, target)
                self._style_slider(output.slider, target > 0)
                self._set_toggle_button_state(output, target > 0)
        self.set_lamp_state(tmcc_id, lamp, target)

    def _on_slider_change(self, tmcc_id: int, output_type: str, output_id: int, value) -> None:
        if self._making_buttons:
            return
        callback_key = (tmcc_id, output_type, output_id)
        if callback_key in self._suspended_slider_callbacks:
            return
        normalized = self._normalize_level(value)
        output = self._output_by_tmcc.get(tmcc_id, {}).get((output_type, output_id))
        if output is None:
            return
        if output.level_box is not None:
            output.level_box.value = self._format_level(normalized)
        self._style_slider(output.slider, normalized > 0)
        if output_type == "lamp" and normalized > 0:
            self._last_non_zero_lamp_level[(tmcc_id, output_id)] = normalized

    def _on_slider_release(self, tmcc_id: int, output_type: str, output_id: int, _event=None) -> None:
        if self._making_buttons:
            return
        callback_key = (tmcc_id, output_type, output_id)
        if callback_key in self._suspended_slider_callbacks:
            return
        output = self._output_by_tmcc.get(tmcc_id, {}).get((output_type, output_id))
        if output is None:
            return
        value = self._normalize_level(output.slider.value)
        # noinspection PyArgumentList
        with self._suspend_slider_callback(callback_key):
            output.slider.value = value
        if output.level_box is not None:
            output.level_box.value = self._format_level(value)
        if output_type == "motor":
            self.set_motor_state(tmcc_id, output_id, value)
        else:
            self.set_lamp_state(tmcc_id, output_id, value)

    def _slider_change_handler(self, tmcc_id: int, output_type: str, output_id: int):
        def on_change(value):
            self._on_slider_change(tmcc_id, output_type, output_id, value)

        return on_change

    def _calc_slider_height(self) -> int:
        available = max(200, int(self.height - self.y_offset - int(round(16 * self._scale_by))))
        overhead = max(120, int(round(135 * self._scale_by)))
        return max(110, available - overhead)

    def _calc_slider_height_for_controls(self, controls_height: int, show_level_box: bool) -> int:
        sb = self._scale_by
        overhead = max(88, int(round(94 * sb))) if show_level_box else max(64, int(round(68 * sb)))
        return max(120, controls_height - overhead)

    def _hidden_nav_vertical_reclaim(self) -> int:
        heights: list[int] = []
        for widget in (self.by_name, self.by_number, self.left_scroll_btn, self.right_scroll_btn):
            if not widget or not hasattr(widget, "tk"):
                continue
            try:
                h = max(int(widget.tk.winfo_height()), int(widget.tk.winfo_reqheight()))
                if h > 0:
                    heights.append(h)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                continue
        if not heights:
            return 0
        # reclaim the hidden button rows plus a small spacer gap
        return max(heights) + int(round(18 * self._scale_by))

    def _build_output(
        self,
        parent: Box,
        tmcc_id: int,
        output_type: str,
        output_id: int,
        label: str,
        is_active: bool,
        level: int,
        col: int,
        slider_height: int,
        control_width: int,
        controls_height: int,
        show_level_box: bool,
    ) -> OutputWidgets:
        container = Box(parent, layout="grid", grid=[col, 0], align="top")
        sb = self._scale_by
        if show_level_box:
            container_height = max(
                160,
                slider_height + max(72, int(round(88 * sb))),
            )
        else:
            # On short displays, use all control-column height so the slider can run to bottom.
            container_height = max(130, int(controls_height))
        slider_row = 2 if show_level_box else 1
        try:
            container.tk.configure(width=control_width, height=container_height)
            container.tk.grid_propagate(False)
            container.tk.grid_rowconfigure(slider_row, weight=1)
            container.tk.grid_columnconfigure(0, weight=1)
            container.tk.grid_configure(padx=max(2, int(round(4 * self._scale_by))))
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        toggle_btn = HoldButton(
            container,
            text=label,
            grid=[0, 0],
            align="top",
            padx=max(2, int(round(4 * self._scale_by))),
            pady=max(3, int(round(5 * self._scale_by))),
        )
        toggle_btn.text_size = int(round(14 * self._scale_by))
        toggle_btn.text_bold = True
        level_box = None
        if show_level_box:
            level_box = Text(
                container,
                grid=[0, 1],
                text=self._format_level(level),
                color="black",
                align="top",
                bold=True,
                size=self.s_18,
                width=4,
                font="DigitalDream",
            )
            level_box.bg = "black"
            level_box.text_color = "white"
        slider = Slider(
            container,
            grid=[0, slider_row],
            align="top",
            horizontal=False,
            step=OUTPUT_STEP,
            width=max(18, int(round(control_width * 0.30))),
            height=slider_height,
            command=self._slider_change_handler(tmcc_id, output_type, output_id),
        )
        slider.tk.config(
            from_=100,
            to=0,
            takefocus=0,
            activebackground=LIONEL_ORANGE,
            bg="white",
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,
            sliderlength=max(18, int(slider_height / 6)),
        )
        if not show_level_box:
            try:
                toggle_h = max(int(toggle_btn.tk.winfo_reqheight()), int(toggle_btn.tk.winfo_height()))
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                toggle_h = max(36, int(round(40 * sb)))
            fill_height = max(120, container_height - toggle_h - int(round(6 * sb)))
            slider.height = fill_height
            slider.tk.config(length=fill_height, sliderlength=max(18, int(fill_height / 6)))
        slider.tk.bind(
            "<ButtonRelease-1>",
            lambda e, tid=tmcc_id, t=output_type, idx=output_id: self._on_slider_release(tid, t, idx, e),
            add="+",
        )
        slider.tk.bind("<Button-1>", lambda e: slider.tk.focus_set(), add="+")
        slider.tmcc_id = tmcc_id

        if output_type == "motor":
            toggle_btn.update_command(self.toggle_motor_state, args=[tmcc_id, output_id])
        else:
            toggle_btn.update_command(self.toggle_lamp_state, args=[tmcc_id, output_id])

        output = OutputWidgets(
            container=container,
            toggle_btn=toggle_btn,
            level_box=level_box,
            slider=slider,
            output_type=output_type,
            output_id=output_id,
            label=label,
        )
        self._set_level_ui(output, level)
        self._set_toggle_button_state(output, is_active)
        self._style_slider(slider, is_active)
        return output

    def _make_state_button(self, pd: AccessoryState, row: int, col: int, **kwargs) -> tuple[list[Widget], int, int]:
        _ = kwargs
        self._making_buttons = True

        widgets: list[Widget | Box] = []
        panel_width = max(360, int(self.width - int(round(20 * self._scale_by))))
        reclaim = self._hidden_nav_vertical_reclaim()
        panel_height = max(
            260,
            int(self.height - self.y_offset - int(round(8 * self._scale_by)) + reclaim),
        )
        panel_height = min(panel_height, int(self.height - int(round(12 * self._scale_by))))
        card = Box(self.btn_box, layout="grid", grid=[col, row], align="top", border=1)
        card.bg = "white"
        try:
            card.tk.configure(width=panel_width, height=panel_height)
            card.tk.grid_propagate(False)
            card.tk.grid_rowconfigure(0, weight=0)
            card.tk.grid_rowconfigure(1, weight=1)
            card.tk.grid_columnconfigure(0, weight=1)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        widgets.append(card)

        title = Text(card, text=f"#{pd.tmcc_id} {pd.road_name}", grid=[0, 0], align="top", bold=True, size=self.s_20)
        try:
            title.tk.configure(anchor="center", justify="center")
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        widgets.append(title)

        controls = Box(card, layout="grid", grid=[0, 1], align="top")
        widgets.append(controls)

        self.app.tk.update_idletasks()
        title_height = max(int(title.tk.winfo_reqheight()), int(title.tk.winfo_height()))
        controls_height = max(140, panel_height - title_height - int(round(14 * self._scale_by)))
        show_level_box = self._show_level_box()
        control_width = max(
            58,
            int((panel_width - int(round(12 * self._scale_by))) / len(OUTPUT_ORDER)),
        )
        try:
            controls.tk.configure(width=panel_width, height=controls_height)
            controls.tk.grid_propagate(False)
            controls.tk.grid_rowconfigure(0, weight=1)
            for idx in range(len(OUTPUT_ORDER)):
                controls.tk.grid_columnconfigure(idx, weight=1, minsize=control_width)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

        slider_height = self._calc_slider_height_for_controls(controls_height, show_level_box)
        by_output: dict[tuple[str, int], OutputWidgets] = {}

        for idx, (output_type, output_id, label) in enumerate(OUTPUT_ORDER):
            if output_type == "motor":
                motor_state = pd.get_motor(output_id)
                level = motor_state.speed if motor_state else 0
                is_active = self.is_motor_active(pd, output_id)
            else:
                lamp_state = pd.get_lamp(output_id)
                level = lamp_state.level if lamp_state else 0
                is_active = self.is_lamp_active(pd, output_id)
                if level > 0:
                    self._last_non_zero_lamp_level[(pd.tmcc_id, output_id)] = level

            output = self._build_output(
                parent=controls,
                tmcc_id=pd.tmcc_id,
                output_type=output_type,
                output_id=output_id,
                label=label,
                is_active=is_active,
                level=level,
                col=idx,
                slider_height=slider_height,
                control_width=control_width,
                controls_height=controls_height,
                show_level_box=show_level_box,
            )
            by_output[(output_type, output_id)] = output
            widgets.extend(output.widgets())

        self._output_by_tmcc[pd.tmcc_id] = by_output

        self.app.tk.update_idletasks()
        btn_h = max(int(card.tk.winfo_height()), int(card.tk.winfo_reqheight()))
        btn_y = card.tk.winfo_y() + btn_h
        return widgets, btn_h, btn_y
