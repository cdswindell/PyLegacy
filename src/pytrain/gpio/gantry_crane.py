#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from ..db.component_state_store import ComponentStateStore
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, CAB1_CONTROL_TYPE
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from .gpio_device import GpioDevice, P
from .state_source import EngineStateSource


class GantryCrane(GpioDevice):
    """
    Represent a Gantry Crane device with multiple configurable controls and states.

    This class extends the functionality of a GPIO-based device to provide a set of commands
    and configurations for controlling various parts of a gantry crane. These include movement
    of the crane's cab, boom, roll, and magnetic operations. The class allows interaction through
    different input pins and can integrate additional features like rotary encoders, LEDs, and
    accessory states for comprehensive control.

    Attributes:
        cab_left_btn (Union[Button, None]): Represents the button control for rotating the cab left.
        cab_right_btn (Union[Button, None]): Represents the button control for rotating the cab right.
        cab_re (Union[PyRotaryEncoder, None]): Represents the rotary encoder for cab rotation
            if enabled, otherwise None.
        ro_left_btn (Union[Button, None]): Represents the button control for rolling left,
            if configured.
        ro_right_btn (Union[Button, None]): Represents the button control for rolling right,
            if configured.
        down_btn (Union[Button, None]): Represents the button control for moving the boom
            downward, if configured.
        up_btn (Union[Button, None]): Represents the button control for lifting the boom,
            if configured.
        mag_btn (Union[Button, None]): Represents the toggle button for magnetic operation,
            if configured.
        mag_led (Union[LED, None]): Represents the LED linked to magnetic operation,
            if configured.

    Args:
        address (int): The unique address of the gantry crane device.
        cab_left_pin (P): GPIO pin assigned for the cab rotation left control.
        cab_right_pin (P): GPIO pin assigned for the cab rotation right control.
        ro_left_pin (P): Optional; GPIO pin assigned for rolling left control. Default is None.
        ro_right_pin (P): Optional; GPIO pin assigned for rolling right control. Default is None.
        bo_down_pin (P): Optional; GPIO pin assigned for moving the boom downward. Default is None.
        bo_up_pin (P): Optional; GPIO pin assigned for lifting the boom. Default is None.
        mag_pin (P): Optional; GPIO pin assigned for the magnetic operation control. Default is None.
        led_pin (P): Optional; GPIO pin assigned for the LED connected to the magnetic operation.
            Default is None.
        cathode (bool): Optional; Specifies whether the LED uses common cathode configuration.
            Default is True.
        cab_rotary_encoder (bool): Optional; Determines if a rotary encoder is used for
            cab rotation. Default is False.

    Raises:
        No raised errors are explicitly documented.
    """

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
        repeat_every: float = 0.02,
    ) -> None:
        # get component state, will need for prefix commands
        self._state = ComponentStateStore.get_state(CommandScope.ENGINE, address, create=False)
        if self._state is None:
            raise AttributeError(f"No gantry crane device found at address {address}")
        if self._state.control_type != CAB1_CONTROL_TYPE:
            raise AttributeError(f"Gantry crane must be configured as Cab-1, not {self._state.control_type_label}")

        cab_sel_cmd = CommandReq.build(TMCC1EngineCommandEnum.NUMERIC, address, data=1, scope=CommandScope.ENGINE)
        # select cab rotate mode
        if self.cab_sel_required():
            cab_sel_cmd.send(repeat=2)

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
                prefix_cmd=cab_sel_cmd,
                prefix_required=self.cab_sel_required,
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
            self.cab_left_btn.when_pressed = self.with_prefix_action(cab_sel_cmd, left_cmd)
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
            self.cab_right_btn.when_pressed = self.with_prefix_action(cab_sel_cmd, right_cmd)
            self.cab_right_btn.when_held = right_cmd.as_action()

        # set up commands for roll
        ro_sel_cmd = CommandReq.build(TMCC1EngineCommandEnum.NUMERIC, address, data=2, scope=CommandScope.ENGINE)
        # roll left
        if ro_left_pin:
            ro_left_cmd, self.ro_left_btn, _ = self.make_button(
                ro_left_pin,
                command=TMCC1EngineCommandEnum.RELATIVE_SPEED,
                address=address,
                data=-1,
                scope=CommandScope.ENGINE,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            self.ro_left_btn.when_pressed = self.with_prefix_action(ro_sel_cmd, ro_left_cmd)
            self.ro_left_btn.when_held = ro_left_cmd.as_action()
        else:
            self.ro_left_btn = None

        # roll right
        if ro_right_pin:
            ro_right_cmd, self.ro_right_btn, _ = self.make_button(
                ro_right_pin,
                command=TMCC1EngineCommandEnum.RELATIVE_SPEED,
                address=address,
                data=1,
                scope=CommandScope.ENGINE,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            self.ro_right_btn.when_pressed = self.with_prefix_action(ro_sel_cmd, ro_right_cmd)
            self.ro_right_btn.when_held = ro_right_cmd.as_action()
        else:
            self.ro_right_btn = None

        # set up commands for boom down
        if bo_down_pin:
            down_cmd, self.down_btn, _ = self.make_button(
                bo_down_pin,
                TMCC1EngineCommandEnum.BRAKE_SPEED,
                address,
                scope=CommandScope.ENGINE,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            self.down_btn.when_pressed = down_cmd.as_action()
            self.down_btn.when_held = down_cmd.as_action()
        else:
            self.down_btn = None

        # boom lift
        if bo_up_pin:
            up_cmd, self.up_btn, _ = self.make_button(
                bo_up_pin,
                TMCC1EngineCommandEnum.BOOST_SPEED,
                address,
                scope=CommandScope.ENGINE,
                hold_repeat=True,
                hold_time=repeat_every,
            )
            self.up_btn.when_pressed = up_cmd.as_action()
            self.up_btn.when_held = up_cmd.as_action()
        else:
            self.up_btn = None

        if mag_pin is not None:
            # turn the magnet off
            CommandReq(TMCC1EngineCommandEnum.AUX2_OFF, address).send(repeat=2)
            self.mag_btn, self.mag_led = self.when_toggle_button_pressed(
                mag_pin,
                TMCC1EngineCommandEnum.AUX2_OPTION_ONE,
                address,
                led_pin=led_pin,
                auto_timeout=55,
                cathode=cathode,
            )
            self.cache_handler(
                EngineStateSource(
                    address,
                    self.mag_led,
                    func=lambda x: x.is_aux2,
                )
            )
        else:
            self.mag_btn = self.mag_led = None

    def cab_sel_required(self) -> bool:
        return self._state.numeric != 1
