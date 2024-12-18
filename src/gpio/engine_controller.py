from gpiozero import Button

from ..db.component_state import EngineState
from ..db.component_state_store import ComponentStateStore
from ..pdi.base3_buffer import Base3Buffer
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, ControlType
from ..protocol.multybyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.sequence.abs_speed_rpm import AbsoluteSpeedRpm
from ..protocol.sequence.labor_effect import LaborEffectUpReq, LaborEffectDownReq
from ..protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandDef, TMCC1EngineCommandDef
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef


class EngineController:
    def __init__(
        self,
        speed_pin_1: int | str = None,
        speed_pin_2: int | str = None,
        halt_pin: int | str = None,
        reset_pin: int | str = None,
        fwd_pin: int | str = None,
        rev_pin: int | str = None,
        front_coupler_pin: int | str = None,
        rear_coupler_pin: int | str = None,
        start_up_pin: int | str = None,
        shutdown_pin: int | str = None,
        boost_pin: int | str = None,
        brake_pin: int | str = None,
        bell_pin: int | str = None,
        horn_pin: int | str = None,
        rpm_up_pin: int | str = None,
        rpm_down_pin: int | str = None,
        labor_up_pin: int | str = None,
        labor_down_pin: int | str = None,
        vol_up_pin: int | str = None,
        vol_down_pin: int | str = None,
        smoke_on_pin: int | str = None,
        smoke_off_pin: int | str = None,
        tower_dialog_pin: int | str = None,
        engr_dialog_pin: int | str = None,
        i2c_adc_address: int = 0x48,
        train_brake_chn: int = None,
        quilling_horn_chn: int = None,
        cmd_repeat: int = 1,
        base_online_pin: int | str = None,
        base_offline_pin: int | str = None,
        base_cathode: bool = True,
        base_ping_freq: int = 5,
    ) -> None:
        from .gpio_handler import GpioHandler

        # initial defaults, use update_engine to modify
        self._tmcc_id = 1
        self._control_type = ControlType.LEGACY
        self._scope = CommandScope.ENGINE
        self._repeat = cmd_repeat
        self._state = None
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

        # the Halt command only exists in TMCC1 form, and it doesn't take an engine address modifier
        if halt_pin is not None:
            self._halt_btn = GpioHandler.make_button(halt_pin)
            self._halt_btn.when_pressed = CommandReq(TMCC1HaltCommandDef.HALT).as_action(repeat=2)
        else:
            self._halt_btn = None

        # construct the commands; make both the TMCC1 and Legacy versions
        self._tmcc1_speed_cmd = None
        self._tmcc2_speed_cmd = None
        self._tmcc1_when_pushed = {}
        self._tmcc2_when_pushed = {}
        self._tmcc1_when_held = {}
        self._tmcc2_when_held = {}
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
            self._tmcc1_speed_cmd = CommandReq(TMCC1EngineCommandDef.ABSOLUTE_SPEED)
            self._tmcc2_speed_cmd = AbsoluteSpeedRpm()
        else:
            self._speed_re = None

        if reset_pin is not None:
            self._reset_btn = GpioHandler.make_button(reset_pin)
            self._tmcc1_when_pushed[self._reset_btn] = CommandReq(TMCC1EngineCommandDef.RESET)
            self._tmcc2_when_pushed[self._reset_btn] = CommandReq(TMCC2EngineCommandDef.RESET)
        else:
            self._reset_btn = None

        if fwd_pin is not None:
            self._fwd_btn = GpioHandler.make_button(fwd_pin)
            self._tmcc1_when_pushed[self._fwd_btn] = CommandReq(TMCC1EngineCommandDef.FORWARD_DIRECTION)
            self._tmcc2_when_pushed[self._fwd_btn] = CommandReq(TMCC2EngineCommandDef.FORWARD_DIRECTION)
        else:
            self._fwd_btn = None

        if rev_pin is not None:
            self._rev_btn = GpioHandler.make_button(rev_pin)
            self._tmcc1_when_pushed[self._rev_btn] = CommandReq(TMCC1EngineCommandDef.REVERSE_DIRECTION)
            self._tmcc2_when_pushed[self._rev_btn] = CommandReq(TMCC2EngineCommandDef.REVERSE_DIRECTION)
        else:
            self._rev_btn = None

        if front_coupler_pin is not None:
            self._fwd_cplr_btn = GpioHandler.make_button(front_coupler_pin)
            self._tmcc1_when_pushed[self._fwd_cplr_btn] = CommandReq(TMCC1EngineCommandDef.FRONT_COUPLER)
            self._tmcc2_when_pushed[self._fwd_cplr_btn] = CommandReq(TMCC2EngineCommandDef.FRONT_COUPLER)
        else:
            self._fwd_cplr_btn = None

        if rear_coupler_pin is not None:
            self._rev_cplr_btn = GpioHandler.make_button(rear_coupler_pin)
            self._tmcc1_when_pushed[self._rev_cplr_btn] = CommandReq(TMCC1EngineCommandDef.REAR_COUPLER)
            self._tmcc2_when_pushed[self._rev_cplr_btn] = CommandReq(TMCC2EngineCommandDef.REAR_COUPLER)
        else:
            self._rev_cplr_btn = None

        if start_up_pin is not None:
            self._start_up_btn = GpioHandler.make_button(start_up_pin)
            self._tmcc2_when_pushed_or_held[self._start_up_btn] = (
                CommandReq(TMCC2EngineCommandDef.START_UP_IMMEDIATE),
                CommandReq(TMCC2EngineCommandDef.START_UP_DELAYED),
            )
        else:
            self._start_up_btn = None

        if shutdown_pin is not None:
            self._shutdown_btn = GpioHandler.make_button(shutdown_pin)
            self._tmcc1_when_pushed[self._shutdown_btn] = CommandReq(TMCC1EngineCommandDef.SHUTDOWN_DELAYED)
            self._tmcc2_when_pushed_or_held[self._shutdown_btn] = (
                CommandReq(TMCC2EngineCommandDef.SHUTDOWN_IMMEDIATE),
                CommandReq(TMCC2EngineCommandDef.SHUTDOWN_DELAYED),
            )
        else:
            self._shutdown_btn = None

        if bell_pin is not None:
            self._bell_btn = GpioHandler.make_button(bell_pin, hold_time=1)
            self._tmcc1_when_pushed[self._bell_btn] = CommandReq(TMCC1EngineCommandDef.RING_BELL)
            self._tmcc2_when_pushed_or_held[self._bell_btn] = (
                CommandReq(TMCC2EngineCommandDef.BELL_ONE_SHOT_DING, data=3),
                CommandReq(TMCC2EngineCommandDef.RING_BELL),
            )
        else:
            self.bell_pin = None

        if horn_pin is not None:
            self._horn_btn = GpioHandler.make_button(horn_pin, hold_repeat=True, hold_time=0.25)
            self._tmcc1_when_pushed[self._horn_btn] = CommandReq(TMCC1EngineCommandDef.BLOW_HORN_ONE)
            self._tmcc2_when_pushed[self._horn_btn] = CommandReq(TMCC2EngineCommandDef.BLOW_HORN_ONE)

            self._horn_btn.hold_repeat = True
            self._horn_btn.hold_time = 0.25
            self._tmcc1_when_held[self._horn_btn] = CommandReq(TMCC1EngineCommandDef.BLOW_HORN_ONE)
            self._tmcc2_when_held[self._horn_btn] = CommandReq(TMCC2EngineCommandDef.QUILLING_HORN, data=7)
        else:
            self._horn_btn = None

        if boost_pin is not None:
            self._boost_btn = GpioHandler.make_button(boost_pin, hold_repeat=True, hold_time=0.2)
            self._tmcc1_when_pushed[self._boost_btn] = CommandReq(TMCC1EngineCommandDef.BOOST_SPEED)
            self._tmcc2_when_pushed[self._boost_btn] = CommandReq(TMCC2EngineCommandDef.BOOST_SPEED)

            self._boost_btn.hold_repeat = True
            self._boost_btn.hold_time = 0.2
            self._tmcc1_when_held[self._boost_btn] = self._tmcc1_when_pushed[self._boost_btn]
            self._tmcc2_when_held[self._boost_btn] = self._tmcc2_when_pushed[self._boost_btn]
        else:
            self._boost_btn = None

        if brake_pin is not None:
            self._brake_btn = GpioHandler.make_button(brake_pin, hold_repeat=True, hold_time=0.2)
            self._tmcc1_when_pushed[self._brake_btn] = CommandReq(TMCC1EngineCommandDef.BRAKE_SPEED)
            self._tmcc2_when_pushed[self._brake_btn] = CommandReq(TMCC2EngineCommandDef.BRAKE_SPEED)

            self._brake_btn.hold_repeat = True
            self._brake_btn.hold_time = 0.2
            self._tmcc1_when_held[self._brake_btn] = self._tmcc1_when_pushed[self._brake_btn]
            self._tmcc2_when_held[self._brake_btn] = self._tmcc2_when_pushed[self._brake_btn]
        else:
            self._brake_btn = None

        if rpm_up_pin is not None:
            self._rpm_up_btn = GpioHandler.make_button(rpm_up_pin)
            self._tmcc1_when_pushed[self._rpm_up_btn] = CommandReq(TMCC1EngineCommandDef.RPM_UP)
            self._tmcc2_when_pushed[self._rpm_up_btn] = CommandReq(TMCC2EngineCommandDef.RPM_UP)

            self._rpm_up_btn.hold_repeat = True
            self._rpm_up_btn.hold_time = 0.75
            self._tmcc1_when_held[self._rpm_up_btn] = CommandReq(TMCC1EngineCommandDef.RPM_UP)
            self._tmcc2_when_held[self._rpm_up_btn] = CommandReq(TMCC2EngineCommandDef.RPM_UP)
        else:
            self._rpm_up_btn = None

        if rpm_down_pin is not None:
            self._rpm_down_btn = GpioHandler.make_button(rpm_down_pin)
            self._tmcc1_when_pushed[self._rpm_down_btn] = CommandReq(TMCC1EngineCommandDef.RPM_DOWN)
            self._tmcc2_when_pushed[self._rpm_down_btn] = CommandReq(TMCC2EngineCommandDef.RPM_DOWN)

            self._rpm_down_btn.hold_repeat = True
            self._rpm_down_btn.hold_time = 0.75
            self._tmcc1_when_held[self._rpm_down_btn] = CommandReq(TMCC1EngineCommandDef.RPM_DOWN)
            self._tmcc2_when_held[self._rpm_down_btn] = CommandReq(TMCC2EngineCommandDef.RPM_DOWN)
        else:
            self._rpm_down_btn = None

        if labor_up_pin is not None:
            self._labor_up_btn = GpioHandler.make_button(labor_up_pin)
            self._tmcc2_when_pushed[self._labor_up_btn] = LaborEffectUpReq()

            self._labor_up_btn.hold_repeat = True
            self._labor_up_btn.hold_time = 0.75
            self._tmcc2_when_held[self._labor_up_btn] = LaborEffectUpReq()
        else:
            self._labor_up_btn = None

        if labor_down_pin is not None:
            self._labor_down_btn = GpioHandler.make_button(labor_down_pin)
            self._tmcc2_when_pushed[self._labor_down_btn] = LaborEffectDownReq()

            self._labor_down_btn.hold_repeat = True
            self._labor_down_btn.hold_time = 0.75
            self._tmcc2_when_held[self._labor_down_btn] = LaborEffectDownReq()
        else:
            self._labor_down_btn = None

        if vol_up_pin is not None:
            self._vol_up_btn = GpioHandler.make_button(vol_up_pin)
            self._tmcc1_when_pushed[self._vol_up_btn] = CommandReq(TMCC1EngineCommandDef.VOLUME_UP)
            self._tmcc2_when_pushed[self._vol_up_btn] = CommandReq(TMCC2EngineCommandDef.VOLUME_UP)
        else:
            self._vol_up_btn = None

        if vol_down_pin is not None:
            self._vol_down_btn = GpioHandler.make_button(vol_down_pin)
            self._tmcc1_when_pushed[self._vol_down_btn] = CommandReq(TMCC1EngineCommandDef.VOLUME_DOWN)
            self._tmcc2_when_pushed[self._vol_down_btn] = CommandReq(TMCC2EngineCommandDef.VOLUME_DOWN)
        else:
            self._vol_down_btn = None

        if smoke_on_pin is not None:
            self._smoke_on_btn = GpioHandler.make_button(smoke_on_pin)
            self._tmcc1_when_pushed[self._smoke_on_btn] = CommandReq(TMCC1EngineCommandDef.SMOKE_ON)
            self._tmcc2_when_pushed[self._smoke_on_btn] = CommandReq(TMCC2EffectsControl.SMOKE_MEDIUM)
        else:
            self._smoke_on_btn = None

        if smoke_off_pin is not None:
            self._smoke_off_btn = GpioHandler.make_button(smoke_off_pin)
            self._tmcc1_when_pushed[self._smoke_off_btn] = CommandReq(TMCC1EngineCommandDef.SMOKE_OFF)
            self._tmcc2_when_pushed[self._smoke_off_btn] = CommandReq(TMCC2EffectsControl.SMOKE_OFF)
        else:
            self._smoke_off_btn = None

        if tower_dialog_pin is not None:
            self.tower_dialog_btn = GpioHandler.make_button(tower_dialog_pin)
            self._tmcc1_when_pushed[self.tower_dialog_btn] = CommandReq(TMCC1EngineCommandDef.NUMERIC, data=7)
            self._tmcc2_when_pushed[self.tower_dialog_btn] = CommandReq(TMCC2EngineCommandDef.NUMERIC, data=7)
        else:
            self.tower_dialog_btn = None

        if engr_dialog_pin is not None:
            self._engr_dialog_btn = GpioHandler.make_button(engr_dialog_pin)
            self._tmcc1_when_pushed[self._engr_dialog_btn] = CommandReq(TMCC1EngineCommandDef.NUMERIC, data=2)
            self._tmcc2_when_pushed[self._engr_dialog_btn] = CommandReq(TMCC2EngineCommandDef.NUMERIC, data=2)
        else:
            self._engr_dialog_btn = None

        if quilling_horn_chn is not None:
            from .quilling_horn import QuillingHorn

            self._quilling_horn_cmd = QuillingHorn(channel=quilling_horn_chn, i2c_address=i2c_adc_address)
        else:
            self._quilling_horn_cmd = None

        if train_brake_chn is not None:
            self._train_brake_cmd = CommandReq(TMCC2EngineCommandDef.TRAIN_BRAKE)
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
        else:
            max_speed = 31
            speed_limit = 27
            when_pushed = self._tmcc1_when_pushed
            when_held = self._tmcc1_when_held
            when_pushed_or_held = self._tmcc1_when_pushed_or_held
            speed_cmd = self._tmcc1_speed_cmd
            quilling_horn_cmd = None

        # reset the when_pressed button handlers
        for btn, cmd in when_pushed.items():
            cmd.address = self._tmcc_id
            cmd.scope = scope
            btn.when_pressed = cmd.as_action(repeat=self._repeat)

        # reset the when_held button handlers
        for btn, cmd in when_held.items():
            cmd.address = self._tmcc_id
            cmd.scope = scope
            btn.when_held = cmd.as_action()

        # reset the when_pushed_or_held button handlers
        for btn, cmds in when_pushed_or_held.items():
            for cmd in cmds:
                cmd.address = self._tmcc_id
                cmd.scope = scope
            btn.when_pressed = GpioHandler.when_button_pressed_or_held_action(
                cmds[0].as_action(),
                cmds[1].as_action(),
                0.2,
            )

        # reset the rotary encoder handlers
        if speed_cmd:
            speed_cmd.address = self._tmcc_id
            speed_cmd.scope = scope
            max_speed = cur_state.max_speed if cur_state.max_speed else max_speed
            speed_limit = cur_state.speed_limit if cur_state.speed_limit else speed_limit
            max_speed = min(max_speed, speed_limit)
            steps_to_speed = GpioHandler.make_interpolator(max_speed, 0, -100, 100)
            speed_to_steps = GpioHandler.make_interpolator(100, -100, 0, max_speed)
            self._speed_re.update_action(speed_cmd, cur_state, steps_to_speed, speed_to_steps)

        # reset the quilling horn
        if quilling_horn_cmd:
            quilling_horn_cmd.update_action(self._tmcc_id, scope)

    def on_speed_changed(self, new_speed: int) -> None:
        if self._speed_re and new_speed is not None:
            self._speed_re.update_data(new_speed)
