#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from typing import cast

from guizero import PushButton, Slider, Text
from guizero.base import Widget

from ..db.accessory_state import AccessoryState
from ..gui.component_state_gui import ComponentStateGui
from ..gui.state_based_gui import StateBasedGui
from ..pdi.amc2_req import Amc2Req
from ..pdi.constants import Amc2Action, PdiCommand
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from .state_based_gui import S


class MotorsGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
    ) -> None:
        StateBasedGui.__init__(
            self,
            "Motors",
            label,
            width,
            height,
            aggrigator,
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
        )
        self._making_buttons = True

    def _post_process_state_buttons(self) -> None:
        self.app.after(500, self.clear_making_buttons)

    def clear_making_buttons(self) -> None:
        self._making_buttons = False

    @property
    def is_making_buttons(self) -> bool:
        return self._making_buttons

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            if acc.is_amc2:
                pds.append(cast(AccessoryState, acc))
        return pds

    def is_active(self, state: AccessoryState) -> bool:
        return False

    def switch_state(self, pd: AccessoryState) -> None:
        pass

    # noinspection PyTypeChecker
    def update_button(self, state: S) -> None:
        with self._cv:
            tmcc_id = state.tmcc_id
            pd = cast(AccessoryState, state)
            widgets = self._state_buttons[tmcc_id]
            if isinstance(widgets, list):
                for widget in widgets:
                    motor = getattr(widget, "motor", None)
                    lamp = getattr(widget, "lamp", None)
                    if isinstance(widget, PushButton) and motor in {1, 2}:
                        if self.is_motor_active(pd, motor):
                            self.set_button_active(widget)
                        else:
                            self.set_button_inactive(widget)
                    if isinstance(widget, PushButton) and lamp in {1, 2, 3, 4}:
                        if self.is_lamp_active(pd, lamp):
                            self.set_button_active(widget)
                        else:
                            self.set_button_inactive(widget)
                    if isinstance(widget, Slider) and motor in {1, 2}:
                        motor_state = pd.get_motor(motor)
                        if widget.value != motor_state.speed if motor_state else 0:
                            widget.value = motor_state.speed if motor_state else 0.0
                        widget.bg = self._enabled_bg if self.is_motor_active(pd, motor) else "lightgrey"
                    if isinstance(widget, Slider) and lamp in {1, 2, 3, 4}:
                        lamp_state = pd.get_lamp(lamp)
                        if widget.value != lamp_state.level if lamp_state else 0:
                            widget.value = lamp_state.level if lamp_state else 0.0
                        widget.bg = self._enabled_bg if self.is_lamp_active(pd, lamp) else "lightgrey"

    @staticmethod
    def is_motor_active(state: AccessoryState, motor: int) -> bool:
        return state.is_motor_on(state.motor2 if motor == 2 else state.motor1)

    @staticmethod
    def is_lamp_active(state: AccessoryState, lamp: int) -> bool:
        lamp_state = state.get_lamp(lamp)
        return lamp_state and lamp_state.level > 0

    def set_motor_state(self, tmcc_id: int, motor: int, speed: int = None) -> None:
        if self._making_buttons:
            return
        with self._cv:
            pd: AccessoryState = self._states[tmcc_id]
            if speed is None:
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
                if self.is_motor_active(pd, motor):
                    CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()
                else:
                    CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()
            elif speed != (pd.motor1.speed if motor == 1 else pd.motor2.speed):
                Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.MOTOR, motor=motor - 1, speed=speed).send()
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
                if speed:
                    CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()
                else:
                    CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()

    def set_lamp_state(self, tmcc_id: int, lamp: int, level: int = None) -> None:
        if self._making_buttons:
            return
        with self._cv:
            pd: AccessoryState = self._states[tmcc_id]
            lamp_state = pd.get_lamp(lamp)
            if level is None:
                if self.is_lamp_active(pd, lamp):
                    Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.LAMP, lamp=lamp - 1, level=0).send()
                else:
                    Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.LAMP, lamp=lamp - 1, level=100).send()
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=lamp + 2).send()
            elif level != lamp_state.level:
                Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.LAMP, lamp=lamp - 1, level=level).send()
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=lamp + 2).send()

    def _make_state_button(
        self,
        pd: AccessoryState,
        row: int,
        col: int,
    ) -> tuple[list[Widget], int, int]:
        self._making_buttons = True
        ts = int(round(23 * self._scale_by))
        widgets: list[Widget] = []
        # make title label
        title = Text(self.btn_box, text=f"#{pd.tmcc_id} {pd.road_name}", grid=[col, row, 2, 1], size=ts, bold=True)
        widgets.append(title)

        # make motor 1 on/off button
        row += 1
        m1_pwr, btn_h, btn_y = super()._make_state_button(pd, row, col)
        m1_pwr.text = "Motor #1"
        m1_pwr.motor = 1
        if pd.motor1.state:
            self.set_button_active(m1_pwr)
        m1_pwr.update_command(self.set_motor_state, args=[pd.tmcc_id, 1])
        widgets.append(m1_pwr)

        # motor 1 control
        slider_height = int(round(btn_h * 0.9))
        m1_ctl = Slider(
            self.btn_box,
            grid=[col, row + 1],
            height=slider_height,
            width=self.pd_button_width,
            step=5,
        )
        m1_ctl.value = pd.motor1.speed
        m1_ctl.motor = 1
        m1_ctl.bg = self._enabled_bg if pd.motor1.state else "lightgrey"
        m1_db = DebouncedSlider(self, pd.tmcc_id, 1, is_motor=True)
        m1_ctl.update_command(m1_db.on_change)
        widgets.append(m1_ctl)

        # make motor 2 on/off button
        m2_pwr, btn_h, btn_y = super()._make_state_button(pd, row, col + 1)
        m2_pwr.text = "Motor #2"
        m2_pwr.motor = 2
        if self.is_motor_active(pd, 2):
            self.set_button_active(m2_pwr)
        m2_pwr.update_command(self.set_motor_state, args=[pd.tmcc_id, 2])
        widgets.append(m2_pwr)

        # motor 2 control
        m2_ctl = Slider(
            self.btn_box,
            grid=[col + 1, row + 1],
            height=slider_height,
            width=self.pd_button_width,
            step=5,
        )
        m2_ctl.value = pd.motor2.speed
        m2_ctl.motor = 2
        m2_ctl.bg = self._enabled_bg if self.is_motor_active(pd, 2) else "lightgrey"
        m2_db = DebouncedSlider(self, pd.tmcc_id, 2, is_motor=True)
        m2_ctl.update_command(m2_db.on_change)
        widgets.append(m2_ctl)

        # make Lamp controls
        for lamp_no in range(1, 5):
            lamp = pd.get_lamp(lamp_no)
            if lamp_no % 2 == 1:
                row += 2
                lamp_col = col
            else:
                lamp_col = col + 1
            pwr, btn_h, btn_y = super()._make_state_button(pd, row, lamp_col)
            pwr.text = f"Lamp #{lamp_no}"
            pwr.lamp = lamp_no
            if lamp.level:
                self.set_button_active(pwr)
            pwr.update_command(self.set_lamp_state, args=[pd.tmcc_id, lamp_no])
            widgets.append(pwr)

            slider_height = int(round(btn_h * 0.9))
            ctl = Slider(
                self.btn_box,
                grid=[lamp_col, row + 1],
                height=slider_height,
                width=self.pd_button_width,
                step=5,
            )
            ctl.value = lamp.level
            ctl.lamp = lamp_no
            ctl.bg = self._enabled_bg if lamp.level else "lightgrey"
            dbs = DebouncedSlider(self, pd.tmcc_id, lamp_no, is_lamp=True)
            ctl.update_command(dbs.on_change)
            widgets.append(ctl)

        # noinspection PyTypeChecker
        self._state_buttons[pd.tmcc_id] = widgets
        return widgets, btn_h, btn_y


class DebouncedSlider:
    def __init__(
        self,
        gui: MotorsGui,
        tmcc_id: int,
        device: int,
        delay_ms=500,
        is_motor: bool = False,
        is_lamp: bool = False,
    ) -> None:
        self._is_lamp = is_lamp
        self._is_motor = is_motor
        self._gui = gui
        self._tmcc_id = tmcc_id
        self._device = device
        self._app = gui.app
        self._tk = gui.app.tk
        self._after_id = None
        self._delay = delay_ms
        self._last_value = None

    def on_change(self, value):
        if self._gui.is_making_buttons:
            return
        self._last_value = int(value)
        # Cancel previously scheduled call if any
        if self._after_id is not None:
            self._tk.after_cancel(self._after_id)
            self._after_id = None
        # Schedule new call after user stops moving for delay_ms
        self._after_id = self._tk.after(self._delay, self._fire)

    def _fire(self):
        self._after_id = None
        self.commit(self._last_value)

    def commit(self, value):
        # Do the real work once sliding has paused
        if self._is_motor:
            self._gui.set_motor_state(self._tmcc_id, self._device, value)
        elif self._is_lamp:
            self._gui.set_lamp_state(self._tmcc_id, self._device, value)
