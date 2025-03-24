#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from .gpio_device import GpioDevice, P


class SmokeFluidLoader(GpioDevice):
    def __init__(
        self,
        address: int,
        boom_left_pin: P = None,
        boom_right_pin: P = None,
        dispense_pin: P = None,
        lights_on_pin: P = None,
        lights_off_pin: P = None,
        cathode: bool = True,
        command_control: bool = True,
        boom_rotary_encoder: bool = False,
    ) -> None:
        if command_control is True:
            if boom_rotary_encoder is True:
                from .py_rotary_encoder import PyRotaryEncoder

                self.boom_left_btn = self.boom_right_btn = None
                cmd = CommandReq.build(TMCC1AuxCommandEnum.RELATIVE_SPEED, address, data=0, scope=CommandScope.ACC)
                self.boom_re = PyRotaryEncoder(
                    boom_left_pin,
                    boom_right_pin,
                    cmd,
                    wrap=False,
                    initial_step=0,
                    max_steps=180,
                    steps_to_data=self.ramped_speed,
                    pause_for=0.1,
                    reset_after_motion=True,
                )
            else:
                # use momentary contact switch to rotate cab
                self.cab_re = None
                left_cmd, self.boom_left_btn, _ = self.make_button(
                    boom_left_pin,
                    command=TMCC1AuxCommandEnum.RELATIVE_SPEED,
                    address=address,
                    data=-1,
                    scope=CommandScope.ACC,
                    hold_repeat=True,
                    hold_time=0.05,
                )
                self.boom_left_btn.when_pressed = left_cmd.as_action()
                self.boom_left_btn.when_held = left_cmd.as_action()

                right_cmd, self.boom_right_btn, _ = self.make_button(
                    boom_right_pin,
                    command=TMCC1AuxCommandEnum.RELATIVE_SPEED,
                    address=address,
                    data=1,
                    scope=CommandScope.ACC,
                    hold_repeat=True,
                    hold_time=0.05,
                )
                self.boom_right_btn.when_pressed = right_cmd.as_action()
                self.boom_right_btn.when_held = right_cmd.as_action()

            lights_on_req, self.lights_on_btn, self.lights_on_led = self.make_button(
                lights_on_pin,
                TMCC1AuxCommandEnum.NUMERIC,
                address,
                data=9,
                cathode=cathode,
            )
            self.lights_on_btn.when_pressed = lights_on_req.as_action(repeat=2)

            lights_off_req, self.lights_off_btn, self.lights_off_led = self.make_button(
                lights_off_pin,
                TMCC1AuxCommandEnum.NUMERIC,
                address,
                data=8,
                cathode=cathode,
            )
            self.lights_off_btn.when_pressed = lights_off_req.as_action(repeat=2)

            dispense_req, self.dispense_btn, self.dispense_led = self.make_button(
                dispense_pin,
                TMCC1AuxCommandEnum.BRAKE,
                address,
                cathode=cathode,
            )
            self.dispense_btn.when_pressed = dispense_req.as_action(repeat=2)
        else:
            raise NotImplementedError
