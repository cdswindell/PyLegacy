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
from .state_source import AccessoryStateSource


class GantryCrane(GpioDevice):
    def __init__(
        self,
        address: int,
        cab_left_pin: P,
        cab_right_pin: P,
        ro_left_pin: P = None,
        ro_right_pin: P = None,
        bo_down_pin: P = None,
        bo_up_pin: P = None,
        mag_pin: P = None,
        led_pin: P = None,
        cathode: bool = True,
        cab_rotary_encoder: bool = False,
    ) -> None:
        cab_sel_cmd = CommandReq.build(TMCC1AuxCommandEnum.NUMERIC, address, data=1, scope=CommandScope.ACC)
        if cab_rotary_encoder is True:
            from .py_rotary_encoder import PyRotaryEncoder

            self.cab_left_btn = self.cab_right_btn = None
            cmd = CommandReq.build(TMCC1AuxCommandEnum.RELATIVE_SPEED, address, data=0, scope=CommandScope.ACC)
            self.cab_re = PyRotaryEncoder(
                cab_left_pin,
                cab_right_pin,
                cmd,
                wrap=False,
                initial_step=0,
                max_steps=180,
                steps_to_data=self.std_step_to_data,
                pause_for=0.05,
                reset_after_motion=True,
            )
        else:
            # use momentary contact switch to rotate cab
            self.cab_re = None
            left_cmd, self.cab_left_btn, _ = self.make_button(
                cab_left_pin,
                command=TMCC1AuxCommandEnum.RELATIVE_SPEED,
                address=address,
                data=-1,
                scope=CommandScope.ACC,
                hold_repeat=True,
                hold_time=0.05,
            )
            self.cab_left_btn.when_pressed = self.with_prefix_action(cab_sel_cmd, left_cmd)
            self.cab_left_btn.when_held = left_cmd.as_action()

            right_cmd, self.cab_right_btn, _ = self.make_button(
                cab_right_pin,
                command=TMCC1AuxCommandEnum.RELATIVE_SPEED,
                address=address,
                data=1,
                scope=CommandScope.ACC,
                hold_repeat=True,
                hold_time=0.05,
            )
            self.cab_right_btn.when_pressed = self.with_prefix_action(cab_sel_cmd, right_cmd)
            self.cab_right_btn.when_held = right_cmd.as_action()

        # set up commands for roll
        ro_sel_cmd = CommandReq.build(TMCC1AuxCommandEnum.NUMERIC, address, data=2, scope=CommandScope.ACC)
        # roll left
        if ro_left_pin:
            ro_left_cmd, self.ro_left_btn, _ = self.make_button(
                ro_left_pin,
                command=TMCC1AuxCommandEnum.RELATIVE_SPEED,
                address=address,
                data=-1,
                scope=CommandScope.ACC,
                hold_repeat=True,
                hold_time=0.05,
            )
            self.ro_left_btn.when_pressed = self.with_prefix_action(ro_sel_cmd, ro_left_cmd)
            self.ro_left_btn.when_held = ro_left_cmd.as_action()
        else:
            self.ro_left_btn = None

        # roll right
        if ro_right_pin:
            ro_right_cmd, self.ro_right_btn, _ = self.make_button(
                ro_right_pin,
                command=TMCC1AuxCommandEnum.RELATIVE_SPEED,
                address=address,
                data=1,
                scope=CommandScope.ACC,
                hold_repeat=True,
                hold_time=0.05,
            )
            self.ro_right_btn.when_pressed = self.with_prefix_action(ro_sel_cmd, ro_right_cmd)
            self.ro_right_btn.when_held = ro_right_cmd.as_action()
        else:
            self.ro_right_btn = None

        # set up commands for boom down
        if bo_down_pin:
            down_cmd, self.down_btn, _ = self.make_button(
                bo_down_pin,
                TMCC1AuxCommandEnum.BRAKE_SPEED,
                address,
                hold_repeat=True,
                hold_time=0.05,
            )
            self.down_btn.when_pressed = down_cmd.as_action()
            self.down_btn.when_held = down_cmd.as_action()
        else:
            self.down_btn = None

        # boom lift
        if bo_up_pin:
            up_cmd, self.up_btn, _ = self.make_button(
                bo_up_pin,
                TMCC1AuxCommandEnum.BOOST_SPEED,
                address,
                hold_repeat=True,
                hold_time=0.05,
            )
            self.up_btn.when_pressed = up_cmd.as_action()
            self.up_btn.when_held = up_cmd.as_action()
        else:
            self.up_btn = None

        if mag_pin is not None:
            self.mag_btn, self.mag_led = self.when_toggle_button_pressed(
                mag_pin,
                TMCC1AuxCommandEnum.AUX2_OPTION_ONE,
                address,
                led_pin=led_pin,
                auto_timeout=59,
                cathode=cathode,
            )
            self.mag_led.blink()
            self.cache_handler(
                AccessoryStateSource(
                    address,
                    self.mag_led,
                    aux2_state=TMCC1AuxCommandEnum.AUX2_OPTION_ONE,
                )
            )
        else:
            self.mag_btn = self.mag_led = None
