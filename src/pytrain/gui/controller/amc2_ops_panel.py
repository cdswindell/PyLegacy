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
from typing import Iterator, TYPE_CHECKING

from guizero import App, Box, Slider, Text

from ..components.hold_button import HoldButton
from ..guizero_base import LIONEL_BLUE, LIONEL_ORANGE
from ...db.accessory_state import AccessoryState
from ...pdi.amc2_req import Amc2Req
from ...pdi.constants import Amc2Action, PdiCommand
from ...protocol.command_req import CommandReq
from ...protocol.constants import CommandScope
from ...protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

OUTPUT_STEP = 5
BUTTON_ON_BG = "green"
BUTTON_OFF_BG = "lightgrey"

PAGE_LAYOUT: list[tuple[str, list[tuple[str, int, str]]]] = [
    ("Motors", [("motor", 1, "Motor #1"), ("motor", 2, "Motor #2")]),
    ("Lights", [("lamp", 1, "Light #1"), ("lamp", 2, "Light #2"), ("lamp", 3, "Light #3"), ("lamp", 4, "Light #4")]),
]


@dataclass(slots=True)
class OutputWidgets:
    page_idx: int
    container: Box
    toggle_btn: HoldButton
    level_box: Text
    slider: Slider
    output_type: str
    output_id: int
    label: str


class Amc2OpsPanel:
    def __init__(self, host: EngineGui) -> None:
        self._host = host
        self._parent: App | None = None
        self._root: Box | None = None
        self._header: Box | None = None
        self._page_label: Text | None = None
        self._controls: Box | None = None
        self._page_index = 0
        self._active_tmcc_id: int | None = None
        self._outputs: dict[tuple[str, int], OutputWidgets] = {}
        self._suspended_slider_callbacks: set[tuple[int, str, int]] = set()

    @property
    def visible(self) -> bool:
        return bool(self._root and self._root.visible)

    def build(self, parent: App) -> Box:
        if self._root is not None:
            return self._root

        self._parent = parent
        host = self._host
        self._root = root = Box(parent, layout="grid", border=2, align="top", visible=False)

        self._header = header = Box(root, layout="grid", grid=[0, 0], align="top")
        prev_btn = HoldButton(header, text="<", grid=[0, 0], align="left", padx=6, pady=6)
        prev_btn.text_size = host.s_22
        prev_btn.text_bold = True
        prev_btn.update_command(self.previous_page)

        self._page_label = Text(header, text="", grid=[1, 0], align="top", bold=True, size=host.s_18)
        try:
            header.tk.grid_columnconfigure(1, weight=1)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

        next_btn = HoldButton(header, text=">", grid=[2, 0], align="right", padx=6, pady=6)
        next_btn.text_size = host.s_22
        next_btn.text_bold = True
        next_btn.update_command(self.next_page)

        self._controls = controls = Box(root, layout="grid", grid=[0, 1], align="top")
        max_cols = max(len(outputs) for _, outputs in PAGE_LAYOUT)
        try:
            for col in range(max_cols):
                controls.tk.grid_columnconfigure(col, weight=1)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

        for page_idx, (_title, outputs) in enumerate(PAGE_LAYOUT):
            for slot, (output_type, output_id, label) in enumerate(outputs):
                output = self._build_output(
                    controls,
                    page_idx=page_idx,
                    col=slot,
                    output_type=output_type,
                    output_id=output_id,
                    label=label,
                )
                self._outputs[(output_type, output_id)] = output

        self._set_page(0)
        return root

    def show(self, state: AccessoryState | None = None) -> None:
        if self._root is None:
            return
        if self._parent is not None and not self._parent.visible:
            self._parent.show()
        if state is not None:
            self.update_from_state(state)
        if not self._root.visible:
            self._root.show()
        self._apply_available_layout()
        try:
            self._host.app.tk.after(30, self._apply_available_layout)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def hide(self) -> None:
        if self._root is not None and self._root.visible:
            self._root.hide()
        if self._parent is not None and self._parent.visible:
            self._parent.hide()

    def next_page(self) -> None:
        self._set_page(self._page_index + 1)

    def previous_page(self) -> None:
        self._set_page(self._page_index - 1)

    def _set_page(self, index: int) -> None:
        total = len(PAGE_LAYOUT)
        self._page_index = index % total
        page_title, _ = PAGE_LAYOUT[self._page_index]
        if self._page_label is not None:
            self._page_label.value = f"{page_title} ({self._page_index + 1}/{total})"
        for output in self._outputs.values():
            should_show = output.page_idx == self._page_index
            if should_show and not output.container.visible:
                output.container.show()
            elif not should_show and output.container.visible:
                output.container.hide()
        self._apply_available_layout()
        try:
            self._host.app.tk.after_idle(self._apply_available_layout)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    @staticmethod
    def _measure_widget_y(widget) -> int | None:
        tk_widget = getattr(widget, "tk", None)
        if tk_widget is None:
            return None
        for method_name in ("winfo_rooty", "winfo_y"):
            method = getattr(tk_widget, method_name, None)
            if method is None:
                continue
            try:
                y = int(method())
                if y >= 0:
                    return y
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _measure_widget_h(widget) -> int | None:
        tk_widget = getattr(widget, "tk", None)
        if tk_widget is None:
            return None
        values: list[int] = []
        for method_name in ("winfo_height", "winfo_reqheight"):
            method = getattr(tk_widget, method_name, None)
            if method is None:
                continue
            try:
                h = int(method())
                if h > 0:
                    values.append(h)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                continue
        return max(values) if values else None

    def _compute_available_panel_height(self) -> int | None:
        host = self._host
        try:
            host.app.tk.update_idletasks()
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            return None

        top = self._measure_widget_y(self._parent) if self._parent is not None else self._measure_widget_y(self._root)
        if top is None:
            return None

        image_box = getattr(host, "image_box", None)
        image_visible = bool(image_box and getattr(image_box, "visible", False))
        if image_visible:
            image_top = self._measure_widget_y(image_box)
            image_h = self._measure_widget_h(image_box)
            if image_top is not None and image_h is not None:
                top = max(top, image_top + image_h)

        app_tk = getattr(host.app, "tk", None)
        if app_tk is None:
            return None
        try:
            app_top = int(app_tk.winfo_rooty())
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            app_top = 0

        app_h = int(getattr(host, "height", 0) or 0)
        for method_name in ("winfo_height", "winfo_reqheight"):
            method = getattr(app_tk, method_name, None)
            if method is None:
                continue
            try:
                measured = int(method())
                if measured > 0:
                    app_h = max(app_h, measured)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                continue
        if app_h <= 0:
            return None

        scope_h = self._measure_widget_h(getattr(host, "scope_box", None))
        if scope_h is None or scope_h <= 0:
            scope_h = max(36, int(round(getattr(host, "button_size", 100) * 0.40)))

        bottom = app_top + app_h - scope_h - int(round(6 * host.scale_by))
        available = bottom - top
        return available if available > 0 else None

    def _apply_available_layout(self) -> None:
        if self._root is None or self._controls is None:
            return
        available = self._compute_available_panel_height()
        if available is None:
            return

        header_h = self._measure_widget_h(self._header) or 0
        controls_h = max(140, available - header_h - 8)
        sb = self._host.scale_by
        chrome = max(92, int(round(102 * sb)))
        slider_h = max(150, controls_h - chrome)

        for output in self._outputs.values():
            output.slider.height = slider_h
            try:
                output.slider.tk.config(
                    length=slider_h,
                    sliderlength=max(16, int(slider_h / 6)),
                )
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                pass

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

    @contextmanager
    def _suspend_slider_callback(self, callback_key: tuple[int, str, int]) -> Iterator[None]:
        self._suspended_slider_callbacks.add(callback_key)
        try:
            yield
        finally:
            self._suspended_slider_callbacks.discard(callback_key)

    # noinspection PyArgumentList
    def _set_output_ui(self, output: OutputWidgets, level: int, is_active: bool) -> None:
        normalized = self._normalize_level(level)
        callback_key = (self._active_tmcc_id or 0, output.output_type, output.output_id)
        if self._normalize_level(output.slider.value) != normalized:
            with self._suspend_slider_callback(callback_key):
                output.slider.value = normalized
        output.level_box.value = self._format_level(normalized)
        self._set_toggle_button_state(output, is_active)
        self._style_slider(output.slider, is_active)

    def _build_output(
        self,
        parent: Box,
        *,
        page_idx: int,
        col: int,
        output_type: str,
        output_id: int,
        label: str,
    ) -> OutputWidgets:
        host = self._host
        container = Box(parent, layout="grid", grid=[col, 0], align="top", visible=(page_idx == 0))
        toggle_btn = HoldButton(
            container,
            text=label,
            grid=[0, 0],
            align="top",
            padx=max(2, int(round(4 * host.scale_by))),
            pady=max(4, int(round(7 * host.scale_by))),
        )
        toggle_btn.text_size = max(host.s_12, int(round(14 * host.scale_by)))
        toggle_btn.text_bold = True

        level_box = Text(
            container,
            grid=[0, 1],
            text="000",
            color="black",
            align="top",
            bold=True,
            size=host.s_18,
            width=4,
            font="DigitalDream",
        )
        level_box.bg = "black"
        level_box.text_color = "white"

        page_cols = len(PAGE_LAYOUT[page_idx][1])
        slider_height = max(int(round(host.button_size * 2.6)), int(round(host.slider_height * 0.72)))
        slider_width = max(16, int(round(host.button_size / 2 if page_cols <= 2 else host.button_size / 3)))
        slider = Slider(
            container,
            grid=[0, 2],
            align="top",
            horizontal=False,
            step=OUTPUT_STEP,
            width=slider_width,
            height=slider_height,
            command=self._slider_change_handler(output_type, output_id),
        )
        slider.tk.config(
            from_=100,
            to=0,
            takefocus=0,
            activebackground=LIONEL_ORANGE,
            bg="white",
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,
            sliderlength=max(16, int(slider_height / 6)),
        )
        slider.tk.bind(
            "<ButtonRelease-1>",
            lambda e, t=output_type, idx=output_id: self._on_slider_release(t, idx, e),
            add="+",
        )
        slider.tk.bind("<Button-1>", lambda e: slider.tk.focus_set(), add="+")
        slider.tmcc_id = 0

        if output_type == "motor":
            toggle_btn.update_command(self.toggle_motor_state, args=[output_id])
        else:
            toggle_btn.update_command(self.toggle_lamp_state, args=[output_id])

        output = OutputWidgets(
            page_idx=page_idx,
            container=container,
            toggle_btn=toggle_btn,
            level_box=level_box,
            slider=slider,
            output_type=output_type,
            output_id=output_id,
            label=label,
        )
        self._set_output_ui(output, 0, False)
        return output

    def _slider_change_handler(self, output_type: str, output_id: int):
        def on_change(value):
            self._on_slider_change(output_type, output_id, value)

        return on_change

    def _on_slider_change(self, output_type: str, output_id: int, value) -> None:
        tmcc_id = self._active_tmcc_id
        if tmcc_id is None:
            return
        callback_key = (tmcc_id, output_type, output_id)
        if callback_key in self._suspended_slider_callbacks:
            return
        output = self._outputs.get((output_type, output_id))
        if output is None:
            return
        output.level_box.value = self._format_level(self._normalize_level(value))

    # noinspection PyArgumentList
    def _on_slider_release(self, output_type: str, output_id: int, _event=None) -> None:
        tmcc_id = self._active_tmcc_id
        if tmcc_id is None:
            return
        callback_key = (tmcc_id, output_type, output_id)
        if callback_key in self._suspended_slider_callbacks:
            return
        output = self._outputs.get((output_type, output_id))
        if output is None:
            return
        value = self._normalize_level(output.slider.value)
        with self._suspend_slider_callback(callback_key):
            output.slider.value = value
        output.level_box.value = self._format_level(value)
        if output_type == "motor":
            self.set_motor_state(tmcc_id, output_id, value)
        else:
            self.set_lamp_state(tmcc_id, output_id, value)

    def update_from_state(self, state: AccessoryState | None) -> None:
        if not isinstance(state, AccessoryState) or not state.is_amc2:
            return
        self._active_tmcc_id = state.tmcc_id
        for (output_type, output_id), output in self._outputs.items():
            output.slider.tmcc_id = state.tmcc_id
            if output_type == "motor":
                motor_state = state.get_motor(output_id)
                level = motor_state.speed if motor_state else 0
                is_active = state.is_motor_on(motor_state) if motor_state else False
            else:
                lamp_state = state.get_lamp(output_id)
                level = lamp_state.level if lamp_state else 0
                is_active = level > 0
            self._set_output_ui(output, level, is_active)

    def _state_for_tmcc(self, tmcc_id: int) -> AccessoryState | None:
        state = self._host.state_store.get_state(CommandScope.ACC, tmcc_id, False)
        if isinstance(state, AccessoryState):
            return state
        active = self._host.active_state
        if isinstance(active, AccessoryState) and active.tmcc_id == tmcc_id:
            return active
        return None

    def set_motor_state(self, tmcc_id: int, motor: int, speed: int | None = None) -> None:
        state = self._state_for_tmcc(tmcc_id)
        if state is None:
            return
        motor_state = state.get_motor(motor)
        current = motor_state.speed if motor_state else 0
        if speed is None:
            CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
            if state.is_motor_on(motor_state):
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()
            return

        normalized = self._normalize_level(speed)
        if normalized == current:
            return
        Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.MOTOR, motor=motor - 1, speed=normalized).send()
        CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
        if normalized > 0:
            CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()
        else:
            CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()

    def set_lamp_state(self, tmcc_id: int, lamp: int, level: int) -> None:
        state = self._state_for_tmcc(tmcc_id)
        if state is None:
            return
        lamp_state = state.get_lamp(lamp)
        current = lamp_state.level if lamp_state else 0
        normalized = self._normalize_level(level)
        if normalized == current:
            return
        Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.LAMP, lamp=lamp - 1, level=normalized).send()
        CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=lamp + 2).send()

    def toggle_motor_state(self, motor: int) -> None:
        tmcc_id = self._active_tmcc_id
        if tmcc_id is None:
            return
        state = self._state_for_tmcc(tmcc_id)
        if state is None:
            return
        motor_state = state.get_motor(motor)
        level = motor_state.speed if motor_state else 0
        is_active = state.is_motor_on(motor_state) if motor_state else False
        target = 100 if (not is_active and level == 0) else None
        self.set_motor_state(tmcc_id, motor, target)

    def toggle_lamp_state(self, lamp: int) -> None:
        tmcc_id = self._active_tmcc_id
        if tmcc_id is None:
            return
        state = self._state_for_tmcc(tmcc_id)
        if state is None:
            return
        lamp_state = state.get_lamp(lamp)
        level = lamp_state.level if lamp_state else 0
        target = 0 if level > 0 else 100
        self.set_lamp_state(tmcc_id, lamp, target)
