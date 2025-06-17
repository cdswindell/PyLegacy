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
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..utils.validations import Validations
from .gpio_device import GpioDevice, P
from .state_source import EngineStateSource


class CraneCar(GpioDevice):
    def __init__(
        self,
        address: int,
        cab_left_pin: P = None,
        cab_right_pin: P = None,
        bo_down_pin: P = None,
        bo_up_pin: P = None,
        bh_down_pin: P = None,
        bh_up_pin: P = None,
        sh_down_pin: P = None,
        sh_up_pin: P = None,
        bo_pin: P = None,
        bh_pin: P = None,
        sh_pin: P = None,
        fl_pin: P = None,
        rl_pin: P = None,
        or_pin: P = None,
        fc_pin: P = None,
        rc_pin: P = None,
        bo_led_pin: P = None,
        bh_led_pin: P = None,
        sh_led_pin: P = None,
        cathode: bool = True,
        cab_rotary_encoder: bool = False,
        repeat_every: float = 0.02,
    ) -> None:
        Validations.validate_float(repeat_every, 0.005, 1, label="repeat_every")
        if cab_rotary_encoder:
            from .py_rotary_encoder import PyRotaryEncoder

            self.cab_left_btn = self.cab_right_btn = None
            cmd = CommandReq.build(TMCC1EngineCommandEnum.RELATIVE_SPEED, address, data=0, scope=CommandScope.ENGINE)
            self.cab_re = PyRotaryEncoder(
                cab_left_pin,
                cab_right_pin,
                cmd,
                wrap=False,
                initial_step=0,
                max_steps=180,
                steps_to_data=self.std_step_to_data,
                pause_for=repeat_every,
                reset_after_motion=True,
            )
        else:
            # use momentary contact switch to rotate cab
            self.cab_re = None
            left_cmd, self.cab_left_btn, _ = self.make_button(
                cab_left_pin,
                command=TMCC1EngineCommandEnum.RELATIVE_SPEED,
                address=address,
                data=-1,
                scope=CommandScope.ENGINE,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            self.cab_left_btn.when_pressed = left_cmd.as_action()
            self.cab_left_btn.when_held = left_cmd.as_action()

            right_cmd, self.cab_right_btn, _ = self.make_button(
                cab_right_pin,
                command=TMCC1EngineCommandEnum.RELATIVE_SPEED,
                address=address,
                data=1,
                scope=CommandScope.ENGINE,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            self.cab_right_btn.when_pressed = right_cmd.as_action()
            self.cab_right_btn.when_held = right_cmd.as_action()

        # boom control
        boom_sel_cmd = CommandReq.build(TMCC1EngineCommandEnum.NUMERIC, address, data=1, scope=CommandScope.ENGINE)
        self.bo_btn = self.bo_led = None
        if bo_pin is not None:
            cmd, self.bo_btn, self.bo_led = self.when_button_pressed(
                bo_pin,
                boom_sel_cmd,
                led_pin=bo_led_pin,
                cathode=cathode,
            )
            if self.bo_led:
                self.cache_handler(EngineStateSource(address, self.bo_led, lambda x: x.numeric == 1))

        # large hook control
        bh_sel_cmd = CommandReq.build(TMCC1EngineCommandEnum.NUMERIC, address, data=2, scope=CommandScope.ENGINE)
        self.bh_btn = self.bh_led = None
        if bh_pin is not None:
            cmd, self.bh_btn, self.bh_led = self.when_button_pressed(
                bh_pin,
                bh_sel_cmd,
                led_pin=bh_led_pin,
                cathode=cathode,
            )
            if self.bh_led:
                self.cache_handler(EngineStateSource(address, self.bh_led, lambda x: x.numeric == 2))

        # small hook control
        sh_sel_cmd = CommandReq.build(TMCC1EngineCommandEnum.NUMERIC, address, data=3, scope=CommandScope.ENGINE)
        self.sh_btn = self.sh_led = None
        if sh_pin is not None:
            cmd, self.sh_btn, self.sh_led = self.when_button_pressed(
                sh_pin,
                sh_sel_cmd,
                led_pin=sh_led_pin,
                cathode=cathode,
            )
            if self.sh_led:
                self.cache_handler(EngineStateSource(address, self.sh_led, lambda x: x.numeric == 3))

        # set-up for boom lift/lower
        # we can either press a selector button to force crane mode or
        # send the prefix command along with the boom down command
        down_cmd = CommandReq.build(TMCC1EngineCommandEnum.BRAKE_SPEED, address)
        if bo_down_pin:
            _, self.down_btn, _ = self.make_button(
                bo_down_pin,
                down_cmd,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            if bh_down_pin or sh_down_pin:
                self.down_btn.when_pressed = self.with_prefix_action(boom_sel_cmd, down_cmd)
            else:
                self.down_btn.when_pressed = down_cmd.as_action()
            self.down_btn.when_held = down_cmd.as_action()
        else:
            self.down_btn = None

        up_cmd = CommandReq.build(TMCC1EngineCommandEnum.BOOST_SPEED, address)
        if bo_up_pin:
            _, self.up_btn, _ = self.make_button(
                bo_up_pin,
                up_cmd,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            if bh_up_pin or sh_up_pin:
                self.up_btn.when_pressed = self.with_prefix_action(boom_sel_cmd, up_cmd)
            else:
                self.up_btn.when_pressed = up_cmd.as_action()
            self.up_btn.when_held = up_cmd.as_action()
        else:
            self.up_btn = None

        # big hook up/down
        if bh_down_pin:
            _, self.bh_down_btn, _ = self.make_button(
                bh_down_pin,
                down_cmd,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            if bo_down_pin or sh_down_pin:
                self.bh_down_btn.when_pressed = self.with_prefix_action(bh_sel_cmd, down_cmd)
            else:
                self.bh_down_btn.when_pressed = down_cmd.as_action()
            self.bh_down_btn.when_held = down_cmd.as_action()
        else:
            self.bh_down_btn = None

        if bh_up_pin:
            _, self.bh_up_btn, _ = self.make_button(
                bh_up_pin,
                up_cmd,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            if bo_up_pin or sh_up_pin:
                self.bh_up_btn.when_pressed = self.with_prefix_action(bh_sel_cmd, up_cmd)
            else:
                self.bh_up_btn.when_pressed = up_cmd.as_action()
            self.bh_up_btn.when_held = up_cmd.as_action()
        else:
            self.bh_up_btn = None

        # small hook up/down
        if sh_down_pin:
            _, self.sh_down_btn, _ = self.make_button(
                sh_down_pin,
                down_cmd,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            if bo_down_pin or bh_down_pin:
                self.sh_down_btn.when_pressed = self.with_prefix_action(sh_sel_cmd, down_cmd)
            else:
                self.sh_down_btn.when_pressed = down_cmd.as_action()
            self.sh_down_btn.when_held = down_cmd.as_action()
        else:
            self.sh_down_btn = None

        if sh_up_pin:
            _, self.sh_up_btn, _ = self.make_button(
                sh_up_pin,
                up_cmd,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            if bo_up_pin or bh_up_pin:
                self.sh_up_btn.when_pressed = self.with_prefix_action(sh_sel_cmd, up_cmd)
            else:
                self.sh_up_btn.when_pressed = up_cmd.as_action()
            self.sh_up_btn.when_held = up_cmd.as_action()
        else:
            self.sh_up_btn = None

        # front/rear lights
        if fl_pin:
            fl_cmd, self.fl_btn, _ = self.make_button(
                fl_pin,
                command=TMCC1EngineCommandEnum.NUMERIC,
                address=address,
                data=4,
                scope=CommandScope.ENGINE,
            )
            self.fl_btn.when_pressed = fl_cmd.as_action()
        else:
            self.fl_btn = None

        if rl_pin:
            rl_cmd, self.rl_btn, _ = self.make_button(
                rl_pin,
                command=TMCC1EngineCommandEnum.NUMERIC,
                address=address,
                data=5,
                scope=CommandScope.ENGINE,
            )
            self.rl_btn.when_pressed = rl_cmd.as_action()
        else:
            self.rl_btn = None

        if or_pin:
            or_cmd, self.or_btn, _ = self.make_button(
                or_pin,
                command=TMCC1EngineCommandEnum.NUMERIC,
                address=address,
                data=6,
                scope=CommandScope.ENGINE,
            )
            self.or_btn.when_pressed = or_cmd.as_action()
        else:
            self.or_btn = None

        # front/rear coupler
        if fc_pin:
            fc_cmd, self.fc_btn, _ = self.make_button(
                fc_pin,
                command=TMCC1EngineCommandEnum.FRONT_COUPLER,
                address=address,
                scope=CommandScope.ENGINE,
            )
            self.fc_btn.when_pressed = fc_cmd.as_action()
        else:
            self.fc_btn = None

        if rc_pin:
            rc_cmd, self.rc_btn, _ = self.make_button(
                rc_pin,
                command=TMCC1EngineCommandEnum.REAR_COUPLER,
                address=address,
                scope=CommandScope.ENGINE,
            )
            self.rc_btn.when_pressed = rc_cmd.as_action()
        else:
            self.rc_btn = None
