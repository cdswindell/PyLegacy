from __future__ import annotations

from random import randint
from typing import TypeVar, Union, Tuple, Dict

from gpiozero import Button

from ..db.component_state import EngineState
from ..db.component_state_store import ComponentStateStore
from ..pdi.base3_buffer import Base3Buffer
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, ControlType
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.sequence.abs_speed_rpm import AbsoluteSpeedRpm
from ..protocol.sequence.labor_effect import LaborEffectUpReq, LaborEffectDownReq
from ..protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum, TMCC1EngineCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

P = TypeVar("P", bound=Union[int, str, Tuple[int], Tuple[int, int], Tuple[int, int, int]])
R = TypeVar("R", bound=CommandReq)


class EngineController:
    def __init__(
        self,
        speed_pin_1: P = None,
        speed_pin_2: P = None,
        halt_pin: P = None,
        reset_pin: P = None,
        fwd_pin: P = None,
        rev_pin: P = None,
        front_coupler_pin: P = None,
        rear_coupler_pin: P = None,
        start_up_pin: P = None,
        shutdown_pin: P = None,
        boost_pin: P = None,
        brake_pin: P = None,
        bell_pin: P = None,
        horn_pin: P = None,
        rpm_up_pin: P = None,
        rpm_down_pin: P = None,
        labor_up_pin: P = None,
        labor_down_pin: P = None,
        vol_up_pin: P = None,
        vol_down_pin: P = None,
        smoke_on_pin: P = None,
        smoke_off_pin: P = None,
        tower_dialog_pin: P = None,
        engr_dialog_pin: P = None,
        aux1_pin: P = None,
        aux2_pin: P = None,
        aux3_pin: P = None,
        stop_immediate_pin: P = None,
        i2c_adc_address: int = 0x48,
        train_brake_chn: int = None,
        quilling_horn_chn: int = None,
        cmd_repeat: int = 1,
        base_online_pin: P = None,
        base_offline_pin: P = None,
        base_cathode: bool = True,
        base_ping_freq: int = 5,
        held_threshold: float = 0.5,
        held_frequency: float = 0.1,
    ) -> None:
        from .gpio_handler import GpioHandler, PressedHeldDef

        # initial defaults, use update_engine to modify
        self._engine_specified = False
        self._tmcc_id = 1
        self._control_type = ControlType.LEGACY
        self._scope = CommandScope.ENGINE
        self._repeat = cmd_repeat
        self._state = None
        self._held_threshold = held_threshold
        self._held_frequency = held_frequency
        # define a base watcher, if requested
        if base_online_pin is not None or base_offline_pin:
            self._base_watcher = GpioHandler.base_watcher(
                active_pin=base_online_pin,
                inactive_pin=base_offline_pin,
                cathode=base_cathode,
                delay=base_ping_freq,
            )
        # save a reference to the ComponentStateStore; it must be built and initialized
        # (or initializing) prior to creating an EngineController instance
        # we will use this info when switching engines to initialize speed
        self._store = ComponentStateStore.build()

        # set up for numeric commands
        self._tmcc1_numeric_cmd = CommandReq(TMCC1EngineCommandEnum.NUMERIC)
        self._tmcc2_numeric_cmd = CommandReq(TMCC2EngineCommandEnum.NUMERIC)
        self._numeric_cmd = None

        # the Halt command only exists in TMCC1 form, and it doesn't take an engine address modifier
        if halt_pin is not None:
            self._halt_btn = GpioHandler.make_button(halt_pin)
            self._halt_btn.when_pressed = CommandReq(TMCC1HaltCommandEnum.HALT).as_action(repeat=2)
        else:
            self._halt_btn = None

        # construct the commands; make both the TMCC1 and Legacy versions
        self._tmcc1_speed_cmd: R | None = None
        self._tmcc2_speed_cmd: R | None = None
        self._tmcc1_when_pushed: Dict[Button, R | None] = {}
        self._tmcc2_when_pushed: Dict[Button, R | None] = {}
        self._tmcc1_when_held: Dict[Button, R | None] = {}
        self._tmcc2_when_held: Dict[Button, R | None] = {}
        self._tmcc1_when_pushed_or_held = {}
        self._tmcc2_when_pushed_or_held = {}

        if speed_pin_1 is not None and speed_pin_2 is not None:
            from .py_rotary_encoder import PyRotaryEncoder

            ramp = {
                20: 3,
                50: 2,
                100: 1,
                200: 1,
                300: 1,
                500: 1,
            }
            self._speed_re = PyRotaryEncoder(speed_pin_1, speed_pin_2, wrap=False, ramp=ramp, max_steps=100)
            self._tmcc1_speed_cmd = CommandReq(TMCC1EngineCommandEnum.ABSOLUTE_SPEED)
            self._tmcc2_speed_cmd = AbsoluteSpeedRpm()
        else:
            self._speed_re = None

        if reset_pin is not None:
            self._reset_btn = GpioHandler.make_button(reset_pin)
            self._tmcc1_when_pushed_or_held[self._reset_btn] = PressedHeldDef(
                CommandReq(TMCC1EngineCommandEnum.RESET),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
            self._tmcc2_when_pushed_or_held[self._reset_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.RESET),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
        else:
            self._reset_btn = None

        # setup for Aux Commands
        if aux1_pin:
            self._aux1_btn = GpioHandler.make_button(aux1_pin)
            self._tmcc2_when_pushed_or_held[self._aux1_btn] = PressedHeldDef(
                CommandReq(TMCC1EngineCommandEnum.AUX1_OPTION_ONE),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
            self._tmcc2_when_pushed_or_held[self._aux1_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.AUX1_OPTION_ONE),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
        else:
            self._aux1_btn = None

        if aux2_pin:
            self._aux2_btn = GpioHandler.make_button(aux2_pin)
            self._tmcc1_when_pushed[self._aux2_btn] = CommandReq(TMCC1EngineCommandEnum.AUX2_OPTION_ONE)
            self._tmcc2_when_pushed[self._aux2_btn] = CommandReq(TMCC2EngineCommandEnum.AUX2_OPTION_ONE)
        else:
            self._aux2_btn = None

        if aux3_pin:
            self._aux3_btn = GpioHandler.make_button(aux3_pin)
            self._tmcc1_when_pushed[self._aux3_btn] = CommandReq(TMCC1EngineCommandEnum.AUX3_OPTION_ONE)
            self._tmcc2_when_pushed[self._aux3_btn] = CommandReq(TMCC2EngineCommandEnum.AUX3_OPTION_ONE)
        else:
            self._aux3_btn = None

        if stop_immediate_pin:
            self._stop_btn = GpioHandler.make_button(stop_immediate_pin)
            self._tmcc1_when_pushed[self._stop_btn] = CommandReq(TMCC1EngineCommandEnum.SPEED_STOP_HOLD)
            self._tmcc2_when_pushed[self._stop_btn] = CommandReq(TMCC2EngineCommandEnum.STOP_IMMEDIATE)
        else:
            self._stop_btn = None

        if fwd_pin is not None:
            self._fwd_btn = GpioHandler.make_button(fwd_pin)
            self._tmcc1_when_pushed[self._fwd_btn] = CommandReq(TMCC1EngineCommandEnum.FORWARD_DIRECTION)
            self._tmcc2_when_pushed[self._fwd_btn] = CommandReq(TMCC2EngineCommandEnum.FORWARD_DIRECTION)
        else:
            self._fwd_btn = None

        if rev_pin is not None:
            self._rev_btn = GpioHandler.make_button(rev_pin)
            self._tmcc1_when_pushed[self._rev_btn] = CommandReq(TMCC1EngineCommandEnum.REVERSE_DIRECTION)
            self._tmcc2_when_pushed[self._rev_btn] = CommandReq(TMCC2EngineCommandEnum.REVERSE_DIRECTION)
        else:
            self._rev_btn = None

        if front_coupler_pin is not None:
            self._fwd_cplr_btn = GpioHandler.make_button(front_coupler_pin)
            self._tmcc1_when_pushed[self._fwd_cplr_btn] = CommandReq(TMCC1EngineCommandEnum.FRONT_COUPLER)
            self._tmcc2_when_pushed[self._fwd_cplr_btn] = CommandReq(TMCC2EngineCommandEnum.FRONT_COUPLER)
        else:
            self._fwd_cplr_btn = None

        if rear_coupler_pin is not None:
            self._rev_cplr_btn = GpioHandler.make_button(rear_coupler_pin)
            self._tmcc1_when_pushed[self._rev_cplr_btn] = CommandReq(TMCC1EngineCommandEnum.REAR_COUPLER)
            self._tmcc2_when_pushed[self._rev_cplr_btn] = CommandReq(TMCC2EngineCommandEnum.REAR_COUPLER)
        else:
            self._rev_cplr_btn = None

        if start_up_pin is not None:
            self._start_up_btn = GpioHandler.make_button(start_up_pin)
            self._tmcc1_when_pushed[self._start_up_btn] = None
            self._tmcc2_when_pushed_or_held[self._start_up_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.START_UP_IMMEDIATE),
                CommandReq(TMCC2EngineCommandEnum.START_UP_DELAYED),
                held_threshold=self._held_threshold,
            )
        else:
            self._start_up_btn = None

        if shutdown_pin is not None:
            self._shutdown_btn = GpioHandler.make_button(shutdown_pin)
            self._tmcc1_when_pushed[self._shutdown_btn] = CommandReq(TMCC1EngineCommandEnum.SHUTDOWN_IMMEDIATE)
            self._tmcc2_when_pushed_or_held[self._shutdown_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.SHUTDOWN_IMMEDIATE),
                CommandReq(TMCC2EngineCommandEnum.SHUTDOWN_DELAYED),
                held_threshold=self._held_threshold,
            )
        else:
            self._shutdown_btn = None

        if bell_pin is not None:
            self._bell_btn = GpioHandler.make_button(bell_pin)
            self._tmcc1_when_pushed_or_held[self._bell_btn] = PressedHeldDef(
                CommandReq(TMCC1EngineCommandEnum.RING_BELL),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
            self._tmcc2_when_pushed_or_held[self._bell_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.BELL_ONE_SHOT_DING, data=3),
                CommandReq(TMCC2EngineCommandEnum.RING_BELL),
                held_threshold=1.5,
            )
        else:
            self.bell_pin = None

        if horn_pin is not None:
            self._horn_btn = GpioHandler.make_button(horn_pin)
            self._tmcc1_when_pushed_or_held[self._horn_btn] = PressedHeldDef(
                CommandReq(TMCC1EngineCommandEnum.BLOW_HORN_ONE),
                repeat_action=5,
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=0.05,
            )
            self._tmcc2_when_pushed_or_held[self._horn_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.BLOW_HORN_ONE),
                CommandReq(TMCC2EngineCommandEnum.QUILLING_HORN, data=7),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=0.05,
                data=lambda b: randint(0, 15),
            )
        else:
            self._horn_btn = None

        if boost_pin is not None:
            self._boost_btn = GpioHandler.make_button(boost_pin)
            self._tmcc1_when_pushed_or_held[self._boost_btn] = PressedHeldDef(
                CommandReq(TMCC1EngineCommandEnum.BOOST_SPEED),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
            self._tmcc2_when_pushed_or_held[self._boost_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.BOOST_SPEED),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
        else:
            self._boost_btn = None

        if brake_pin is not None:
            self._brake_btn = GpioHandler.make_button(brake_pin)
            self._tmcc1_when_pushed_or_held[self._brake_btn] = PressedHeldDef(
                CommandReq(TMCC1EngineCommandEnum.BRAKE_SPEED),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
            self._tmcc2_when_pushed_or_held[self._brake_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.BRAKE_SPEED),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_frequency,
            )
        else:
            self._brake_btn = None

        if rpm_up_pin is not None:
            self._rpm_up_btn = GpioHandler.make_button(rpm_up_pin)
            self._tmcc1_when_pushed_or_held[self._rpm_up_btn] = PressedHeldDef(
                CommandReq(TMCC1EngineCommandEnum.RPM_UP),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_threshold,
            )
            self._tmcc2_when_pushed_or_held[self._rpm_up_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.RPM_UP),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_threshold,
            )
        else:
            self._rpm_up_btn = None

        if rpm_down_pin is not None:
            self._rpm_down_btn = GpioHandler.make_button(rpm_down_pin)
            self._tmcc1_when_pushed_or_held[self._rpm_down_btn] = PressedHeldDef(
                CommandReq(TMCC1EngineCommandEnum.RPM_DOWN),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_threshold,
            )
            self._tmcc2_when_pushed_or_held[self._rpm_down_btn] = PressedHeldDef(
                CommandReq(TMCC2EngineCommandEnum.RPM_DOWN),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_threshold,
            )
        else:
            self._rpm_down_btn = None

        if labor_up_pin is not None:
            self._labor_up_btn = GpioHandler.make_button(labor_up_pin)
            self._tmcc1_when_pushed[self._labor_up_btn] = None
            self._tmcc2_when_pushed_or_held[self._labor_up_btn] = PressedHeldDef(
                LaborEffectUpReq(),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_threshold,
            )
        else:
            self._labor_up_btn = None

        if labor_down_pin is not None:
            self._labor_down_btn = GpioHandler.make_button(labor_down_pin)
            self._tmcc1_when_pushed[self._labor_down_btn] = None
            self._tmcc2_when_pushed_or_held[self._labor_down_btn] = PressedHeldDef(
                LaborEffectDownReq(),
                held_threshold=self._held_threshold,
                hold_repeat=True,
                frequency=self._held_threshold,
            )
        else:
            self._labor_down_btn = None

        if vol_up_pin is not None:
            self._vol_up_btn = GpioHandler.make_button(vol_up_pin)
            self._tmcc1_when_pushed[self._vol_up_btn] = CommandReq(TMCC1EngineCommandEnum.VOLUME_UP)
            self._tmcc2_when_pushed[self._vol_up_btn] = CommandReq(TMCC2EngineCommandEnum.VOLUME_UP)
        else:
            self._vol_up_btn = None

        if vol_down_pin is not None:
            self._vol_down_btn = GpioHandler.make_button(vol_down_pin)
            self._tmcc1_when_pushed[self._vol_down_btn] = CommandReq(TMCC1EngineCommandEnum.VOLUME_DOWN)
            self._tmcc2_when_pushed[self._vol_down_btn] = CommandReq(TMCC2EngineCommandEnum.VOLUME_DOWN)
        else:
            self._vol_down_btn = None

        if smoke_on_pin is not None:
            self._smoke_on_btn = GpioHandler.make_button(smoke_on_pin)
            self._tmcc1_when_pushed[self._smoke_on_btn] = CommandReq(TMCC1EngineCommandEnum.SMOKE_ON)
            self._tmcc2_when_pushed[self._smoke_on_btn] = CommandReq(TMCC2EffectsControl.SMOKE_MEDIUM)
        else:
            self._smoke_on_btn = None

        if smoke_off_pin is not None:
            self._smoke_off_btn = GpioHandler.make_button(smoke_off_pin)
            self._tmcc1_when_pushed[self._smoke_off_btn] = CommandReq(TMCC1EngineCommandEnum.SMOKE_OFF)
            self._tmcc2_when_pushed[self._smoke_off_btn] = CommandReq(TMCC2EffectsControl.SMOKE_OFF)
        else:
            self._smoke_off_btn = None

        if tower_dialog_pin is not None:
            self.tower_dialog_btn = GpioHandler.make_button(tower_dialog_pin)
            self._tmcc1_when_pushed[self.tower_dialog_btn] = CommandReq(TMCC1EngineCommandEnum.NUMERIC, data=7)
            self._tmcc2_when_pushed[self.tower_dialog_btn] = CommandReq(TMCC2EngineCommandEnum.NUMERIC, data=7)
        else:
            self.tower_dialog_btn = None

        if engr_dialog_pin is not None:
            self._engr_dialog_btn = GpioHandler.make_button(engr_dialog_pin)
            self._tmcc1_when_pushed[self._engr_dialog_btn] = CommandReq(TMCC1EngineCommandEnum.NUMERIC, data=2)
            self._tmcc2_when_pushed[self._engr_dialog_btn] = CommandReq(TMCC2EngineCommandEnum.NUMERIC, data=2)
        else:
            self._engr_dialog_btn = None

        if quilling_horn_chn is not None:
            from ..gpio.i2c.analog_handler_i2c import QuillingHorn

            self._quilling_horn_cmd = QuillingHorn(channel=quilling_horn_chn, i2c_address=i2c_adc_address)
        else:
            self._quilling_horn_cmd = None

        if train_brake_chn is not None:
            from ..gpio.i2c.analog_handler_i2c import TrainBrake

            self._train_brake_cmd = TrainBrake(channel=train_brake_chn, i2c_address=i2c_adc_address)
        else:
            self._train_brake_cmd = None

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @property
    def control_type(self) -> ControlType:
        return self._control_type

    @property
    def is_legacy(self) -> bool:
        return self._control_type and self._control_type.is_legacy

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def halt_btn(self) -> Button:
        return self._halt_btn

    @property
    def reset_btn(self) -> Button:
        return self._reset_btn

    @property
    def fwd_btn(self) -> Button:
        return self._fwd_btn

    @property
    def rev_btn(self) -> Button:
        return self._rev_btn

    @property
    def start_up_btn(self) -> Button:
        return self._start_up_btn

    @property
    def shutdown_btn(self) -> Button:
        return self._shutdown_btn

    @property
    def bell_btn(self) -> Button:
        return self._bell_btn

    @property
    def horn_btn(self) -> Button:
        return self._horn_btn

    @property
    def boost_btn(self) -> Button:
        return self._boost_btn

    @property
    def brake_btn(self) -> Button:
        return self._brake_btn

    @property
    def rpm_up_btn(self) -> Button:
        return self._rpm_up_btn

    @property
    def rpm_down_btn(self) -> Button:
        return self._rpm_down_btn

    @property
    def labor_up_btn(self) -> Button:
        return self._labor_up_btn

    @property
    def labor_down_btn(self) -> Button:
        return self._labor_down_btn

    @property
    def volume_up_btn(self) -> Button:
        return self._vol_up_btn

    @property
    def volume_down_btn(self) -> Button:
        return self._vol_down_btn

    @property
    def smoke_on_btn(self) -> Button:
        return self._smoke_on_btn

    @property
    def smoke_off_btn(self) -> Button:
        return self._smoke_off_btn

    def update(
        self,
        tmcc_id: int,
        scope: CommandScope = CommandScope.ENGINE,
        state: EngineState = None,
    ) -> None:
        from .gpio_handler import GpioHandler

        """
        When a new engine/train is selected, redo the button bindings to
        reflect the new engine/train tmcc_id
        """
        self._engine_specified = True
        self._scope = scope
        self._tmcc_id = tmcc_id
        self._state = cur_state = state
        if cur_state is None or cur_state.control_type is None:
            self._control_type = ControlType.LEGACY
        else:
            self._control_type = ControlType.by_value(cur_state.control_type)
        # request state update from Base, if present
        Base3Buffer.request_state_update(tmcc_id, scope)
        # update buttons
        if self.is_legacy:
            max_speed = 200
            speed_limit = 195
            when_pushed = self._tmcc2_when_pushed
            when_held = self._tmcc2_when_held
            when_pushed_or_held = self._tmcc2_when_pushed_or_held
            speed_cmd = self._tmcc2_speed_cmd
            quilling_horn_cmd = self._quilling_horn_cmd
            train_brake_cmd = self._train_brake_cmd
            numeric_cmd = self._tmcc2_numeric_cmd
        else:
            max_speed = 31
            speed_limit = 27
            when_pushed = self._tmcc1_when_pushed
            when_held = self._tmcc1_when_held
            when_pushed_or_held = self._tmcc1_when_pushed_or_held
            speed_cmd = self._tmcc1_speed_cmd
            quilling_horn_cmd = None
            train_brake_cmd = None
            numeric_cmd = self._tmcc1_numeric_cmd

        # reset the when_pressed button handlers
        for btn, cmd in when_pushed.items():
            if cmd:
                cmd.address = self._tmcc_id
                cmd.scope = scope
                btn.when_pressed = cmd.as_action(repeat=self._repeat)
            else:
                if btn.when_pressed:
                    btn.when_pressed = None

        # reset the when_held button handlers
        for btn, cmd in when_held.items():
            if cmd:
                cmd.address = self._tmcc_id
                cmd.scope = scope
                btn.when_held = cmd.as_action()
            else:
                if btn.when_held:
                    btn.when_held = None

        # reset the when_pushed_or_held button handlers
        for btn, phd in when_pushed_or_held.items():
            if phd:
                phd.update_target(self._tmcc_id, scope=scope)
                btn.when_pressed = phd.as_action()
            else:
                if btn.when_pressed:
                    btn.when_pressed = None

        # reset the rotary encoder handlers
        if speed_cmd:
            speed_cmd.address = self._tmcc_id
            speed_cmd.scope = scope
            max_speed = cur_state.max_speed if cur_state.max_speed and cur_state.max_speed != 255 else max_speed
            speed_limit = (
                cur_state.speed_limit if cur_state.speed_limit and cur_state.speed_limit != 255 else speed_limit
            )
            max_speed = min(max_speed, speed_limit)
            steps_to_speed = GpioHandler.make_interpolator(max_speed, 0, -100, 100)
            speed_to_steps = GpioHandler.make_interpolator(100, -100, 0, max_speed)
            self._speed_re.update_action(speed_cmd, cur_state, steps_to_speed, speed_to_steps)

        # reset the quilling horn
        if quilling_horn_cmd:
            quilling_horn_cmd.update_action(self._tmcc_id, scope)

        # reset the train brake
        if train_brake_cmd:
            train_brake_cmd.update_action(self._tmcc_id, scope)

        # reset the numeric command
        if numeric_cmd:
            numeric_cmd.address = self._tmcc_id
            numeric_cmd.scope = scope
            self._numeric_cmd = numeric_cmd
        else:
            self._numeric_cmd = None

    def on_speed_changed(self, new_speed: int) -> None:
        if self._speed_re and new_speed is not None:
            self._speed_re.update_data(new_speed)

    def on_numeric(self, key: str):
        if self._numeric_cmd:
            self._numeric_cmd.as_action()(new_data=int(key))
