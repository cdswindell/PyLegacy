import logging
import math
import sched
import threading
import time
from threading import Thread
from typing import Tuple, Callable, Dict, TypeVar

from gpiozero import Button, LED, MCP3008, MCP3208, RotaryEncoder, Device, AnalogInputDevice, PingServer

from ..comm.comm_buffer import CommBuffer
from ..comm.command_listener import Message
from ..db.component_state_store import DependencyCache
from ..gpio.state_source import SwitchStateSource, AccessoryStateSource, EngineStateSource
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.constants import DEFAULT_ADDRESS
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchState, TMCC1AuxCommandDef, TMCC1EngineCommandDef
from ..protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandDef, TMCC2EngineCommandDef

log = logging.getLogger(__name__)

DEFAULT_BOUNCE_TIME: float = 0.05  # button debounce threshold
DEFAULT_VARIANCE: float = 0.001  # pot difference variance

T = TypeVar("T", bound=CommandReq)


class GpioDelayHandler(Thread):
    """
    Handle delayed (scheduled) requests. Implementation uses Python's lightweight
    sched module to keep a list of requests to issue in the future. We use
    threading.Event.wait() as the sleep function, as it is interruptable. This
    allows us to schedule requests in any order and still have them fire at the
    appropriate time.
    """

    def __init__(self) -> None:
        super().__init__(daemon=True, name="PyLegacy GPIO Delay Handler")
        self._cv = threading.Condition()
        self._ev = threading.Event()
        self._scheduler = sched.scheduler(time.time, self._ev.wait)
        self._running = True
        self.start()

    def cancel(self, ev: sched.Event) -> None:
        try:
            if ev:
                self._scheduler.cancel(ev)
        except ValueError:
            pass

    def reset(self) -> None:
        self._running = False
        # clear out any scheduled events
        for ev in self._scheduler.queue:
            self.cancel(ev)
        # send shutdown signal
        with self._cv:
            self._ev.set()
            self._cv.notify()

    def run(self) -> None:
        while self._running:
            with self._cv:
                while self._running and self._scheduler.empty():
                    self._cv.wait()
            # run the scheduler outside the cv lock, otherwise,
            #  we couldn't schedule more commands
            self._scheduler.run()
            self._ev.clear()

    def schedule(self, delay: float, command: Callable) -> sched.Event:
        with self._cv:
            ev = self._scheduler.enter(delay, 1, command)
            # this interrupts the running scheduler
            self._ev.set()
            # and this notifies the main thread to restart, as there is a new
            # request in the sched queue
            self._cv.notify()
            return ev


class PotHandler(Thread):
    def __init__(
        self,
        command: CommandReq | None,
        channel: int = 0,
        use_12bit: bool = False,
        data_min: int = None,
        data_max: int = None,
        threshold: float = None,
        delay: float = 0.05,
        scale: Dict[int, int] = None,
        cmds: Dict[int, T] = None,
        start: bool = True,
        prefix: CommandReq = None,
    ) -> None:
        super().__init__(daemon=True)
        if use_12bit is True:
            self._pot = MCP3208(channel=channel, differential=False)
        else:
            self._pot = MCP3008(channel=channel)
        self._command = command
        self._prefix = prefix
        self._prefix_data = prefix.data if prefix else None
        self._prefix_address = prefix.address if prefix else None
        self._last_value = None
        self._action = command.as_action() if command else None
        self._data_max = data_max = data_max if data_max is not None else command.data_max
        self._data_min = data_min = data_min if data_min is not None else command.data_min
        self._interp = self.make_interpolator(data_max, data_min)
        if threshold is not None:
            self._threshold = threshold
        elif command:
            self._threshold = 1 if command.num_data_bits < 6 else 2
        else:
            self._threshold = None
        self._delay = delay
        self._running = True
        self._scale = scale
        self._command_map = cmds
        self._tmcc_command_buffer = CommBuffer.build()
        if start is True:
            self.start()

    @property
    def pot(self) -> AnalogInputDevice:
        return self._pot

    def run(self) -> None:
        if log.isEnabledFor(logging.DEBUG):
            log.debug(
                f"Delay: {self._delay} threshold: {self._threshold} d_min: {self._data_min} d_max: {self._data_max}"
            )
        while self._running:
            raw_value = self.pot.value
            value = self._interp(raw_value)
            if self._scale:
                value = self._scale[value]
            if self._last_value is None:
                self._last_value = value
                continue
            elif self._threshold is not None and math.fabs(self._last_value - value) <= self._threshold and value > 0:
                continue  # pots can take a bit to settle; ignore small changes
            if self._last_value == 0 and value == 0:
                continue
            self._last_value = value
            byte_str = bytes()
            if self._command_map and value in self._command_map:
                cmd = self._command_map[value]
                if cmd:
                    if self._prefix:
                        if GpioHandler.engine_numeric(self._prefix_address) == self._prefix_data:
                            pass
                        else:
                            byte_str += self._prefix.as_bytes * 3
                    # command could be None, indicating no action
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"{cmd} {value} {raw_value}")
                    if cmd.is_data is True:
                        cmd.data = value
                    byte_str += cmd.as_bytes
            elif self._command and self._action:
                if self._prefix:
                    if GpioHandler.engine_numeric(self._prefix_address) == self._prefix_data:
                        pass
                    else:
                        byte_str += self._prefix.as_bytes * 3
                self._command.data = value
                byte_str += self._command.as_bytes
            if byte_str:
                self._tmcc_command_buffer.enqueue_command(byte_str)
            time.sleep(self._delay)

    def reset(self) -> None:
        self._running = False

    @staticmethod
    def make_interpolator(
        to_max: int,
        to_min: int = 0,
        from_min: float = 0.0,
        from_max: float = 1.0,
    ) -> Callable:
        # Figure out how 'wide' each range is
        from_span = from_max - from_min
        to_span = to_max - to_min

        # Compute the scale factor between left and right values
        scale_factor = float(to_span) / float(from_span)

        # create interpolation function using pre-calculated scaleFactor
        def interp_fn(value) -> int:
            scaled_value = int(round(to_min + (value - from_min) * scale_factor))
            return scaled_value

        return interp_fn


class JoyStickHandler(PotHandler):
    def __init__(
        self,
        command: CommandReq | None = None,
        channel: int = 0,
        use_12bit: bool = True,
        data_min: int = None,
        data_max: int = None,
        delay: float = 0.05,
        scale: Dict[int, int] = None,
        cmds: Dict[int, T] = None,
        prefix: CommandReq = None,
    ) -> None:
        super().__init__(
            command,
            channel=channel,
            use_12bit=use_12bit,
            data_min=data_min,
            data_max=data_max,
            threshold=None,
            delay=delay,
            scale=scale,
            cmds=cmds,
            start=False,
            prefix=prefix,
        )
        self._threshold = None
        self.start()


# noinspection DuplicatedCode
class GpioHandler:
    GPIO_DEVICE_CACHE = set()
    GPIO_HANDLER_CACHE = set()
    GPIO_DELAY_HANDLER = None

    @staticmethod
    def current_milli_time() -> int:
        """
        Return the current time, in milliseconds past the "epoch"
        """
        return round(time.time() * 1000)

    @staticmethod
    def engine_numeric(address: int) -> int | None:
        if address is not None:
            from ..db.component_state_store import ComponentStateStore

            state = ComponentStateStore.get_state(CommandScope.ENGINE, address, create=False)
            if state:
                return state.numeric
        return None

    @classmethod
    def calibrate_joystick(cls, x_axis_chn: int = 0, y_axis_chn: int = 0, use_12bit: bool = True) -> None:
        if use_12bit is True:
            x_axis = MCP3208(channel=x_axis_chn, differential=False)
            y_axis = MCP3208(channel=y_axis_chn, differential=False)
        else:
            x_axis = MCP3008(channel=x_axis_chn, differential=False)
            y_axis = MCP3008(channel=y_axis_chn, differential=False)

        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        print("Rotate Joystick clockwise, making sure to blah...")
        is_running = True
        num_cycles = 100
        start_at = cls.current_milli_time()
        while is_running:
            x = x_axis.value
            y = y_axis.value

            new_range = False
            if x < min_x:
                new_range = True
                min_x = x
            if x > max_x:
                new_range = True
                max_x = x
            if y < min_y:
                new_range = True
                min_y = y
            if y > max_y:
                new_range = True
                max_y = y

            elapsed = cls.current_milli_time() - start_at
            if new_range is False:
                num_cycles -= 1
                if num_cycles <= 0 and elapsed > 10000:
                    is_running = False
                else:
                    print(elapsed, num_cycles, end="\r")
                    time.sleep(0.1)
        print(f" X axis range: {min_x} - {max_x}")
        print(f" Y axis range: {min_y} - {max_y}")
        print("Now take your hands off hit joystick and let it recenter for 10 seconds")
        time.sleep(2)

        is_running = True
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        start_at = cls.current_milli_time()
        cycle = 0
        sum_x = sum_y = 0.0
        while is_running:
            x = x_axis.value
            y = y_axis.value

            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            sum_x += x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
            sum_y += y
            cycle += 1

            elapsed = cls.current_milli_time() - start_at
            if cycle % 1000 == 0:
                remaining = (10000 - elapsed) / 1000.0
                print(f"Time remaining: {remaining} seconds", end="\r")
            if elapsed >= 10000:
                is_running = False
        print(f" X center range: {min_x} - {max_x}; average: {sum_x / cycle}")
        print(f" Y center range: {min_y} - {max_y}; average: {sum_y / cycle}")

    @classmethod
    def base_watcher(
        cls,
        server: str,
        active_pin: int | str = None,
        inactive_pin: int | str = None,
        cathode: bool = True,
        delay: float = 5,
    ) -> Tuple[PingServer, LED, LED]:
        # set up a ping server, treat it as a device
        ping_server = PingServer(server, event_delay=delay)
        cls.cache_device(ping_server)

        # set up active led, if any
        active_led = None
        if active_pin:
            active_led = LED(active_pin, active_high=cathode)
            active_led.value = 1 if ping_server.is_active else 0
            cls.cache_device(active_led)

        inactive_led = None
        if inactive_pin:
            inactive_led = LED(inactive_pin, active_high=cathode)
            inactive_led.value = 0 if ping_server.is_active else 1
            cls.cache_device(inactive_led)

        # set ping server state change actions
        if active_led and inactive_led:
            # we have to toggle the leds; we need a custom function
            def on_active() -> None:
                active_led.on()
                inactive_led.off()

            ping_server.when_activated = on_active

            def on_inactive() -> None:
                active_led.off()
                inactive_led.on()

            ping_server.when_deactivated = on_inactive
        elif active_led:
            ping_server.when_activated = active_led.on
            ping_server.when_deactivated = active_led.off
        elif inactive_led:
            ping_server.when_activated = inactive_led.off
            ping_server.when_deactivated = inactive_led.on

        return ping_server, active_led, inactive_led

    @classmethod
    def route(
        cls,
        address: int,
        btn_pin: int,
        led_pin: int | str = None,
        cathode: bool = True,
    ) -> Button | Tuple[Button, LED]:
        """
        Fire a TMCC2/Legacy Route, throwing all incorporated turnouts to the correct state
        """
        # make the CommandReq
        req, btn, led = cls._make_button(
            btn_pin,
            TMCC2RouteCommandDef.FIRE,
            address,
            led_pin=led_pin,
            bind=True,
            cathode=cathode,
        )
        # bind actions to buttons
        btn.when_pressed = req.as_action(repeat=2)

        # return created objects
        if led is not None:
            return btn, led
        else:
            return btn

    @classmethod
    def switch(
        cls,
        address: int,
        thru_pin: int,
        out_pin: int,
        thru_led_pin: int | str = None,
        out_led_pin: int | str = None,
        cathode: bool = True,
        initial_state: TMCC1SwitchState = None,
    ) -> Tuple[Button, Button] | Tuple[Button, Button, LED, LED]:
        """
        Control a switch/turnout that responds to TMCC1 switch commands, such
        as Lionel Command/Control-equipped turnouts or turnouts connected to
        an LCS ACS 2 configured in "Switch" mode.

        Optionally, manage LEDs to reflect turnout state; thru or out. Also
        supports bi-color LEDs with either common cathode or anode.
        """
        if initial_state is None:
            # TODO: query initial state
            initial_state = TMCC1SwitchState.THROUGH

        # make the CommandReqs
        thru_req, thru_btn, thru_led = cls._make_button(
            thru_pin,
            TMCC1SwitchState.THROUGH,
            address,
            led_pin=thru_led_pin,
            initially_on=initial_state == TMCC1SwitchState.THROUGH,
            cathode=cathode,
        )
        out_req, out_btn, out_led = cls._make_button(
            out_pin,
            TMCC1SwitchState.OUT,
            address,
            led_pin=out_led_pin,
            initially_on=initial_state == TMCC1SwitchState.OUT,
            cathode=cathode,
        )
        # bind actions to buttons
        thru_action = thru_req.as_action(repeat=2)
        out_action = out_req.as_action(repeat=2)

        thru_btn.when_pressed = cls._with_on_action(thru_action, thru_led, out_led)
        out_btn.when_pressed = cls._with_on_action(out_action, out_led, thru_led)

        if thru_led is not None and out_led is not None:
            cls.cache_handler(SwitchStateSource(address, thru_led, TMCC1SwitchState.THROUGH))
            cls.cache_handler(SwitchStateSource(address, out_led, TMCC1SwitchState.OUT))
            return thru_btn, out_btn, thru_led, out_led
        else:
            # return created objects
            return thru_btn, out_btn

    @classmethod
    def power_district(
        cls,
        address: int,
        on_pin: int,
        off_pin: int,
        on_led_pin: int | str = None,
        cathode: bool = True,
        initial_state: TMCC1AuxCommandDef | bool = None,
    ) -> Tuple[Button, Button] | Tuple[Button, Button, LED]:
        """
        Control a power district that responds to TMCC1 accessory commands, such
        as an LCS BP2 configured in "Acc" mode.
        """
        if initial_state is None:
            # TODO: query initial state
            initial_state = TMCC1AuxCommandDef.AUX2_OPT_ONE

        # make the CommandReqs
        on_req, on_btn, on_led = cls._make_button(
            on_pin,
            TMCC1AuxCommandDef.AUX1_OPT_ONE,
            address,
            led_pin=on_led_pin,
            cathode=cathode,
            initially_on=initial_state == TMCC1AuxCommandDef.AUX1_OPT_ONE,
        )
        off_req, off_btn, off_led = cls._make_button(
            off_pin,
            TMCC1AuxCommandDef.AUX2_OPT_ONE,
            address,
            cathode=cathode,
            initially_on=initial_state == TMCC1AuxCommandDef.AUX2_OPT_ONE,
        )
        # bind actions to buttons
        on_action = on_req.as_action(repeat=2)
        off_action = off_req.as_action(repeat=2)

        on_btn.when_pressed = cls._with_on_action(on_action, on_led)
        off_btn.when_pressed = cls._with_off_action(off_action, on_led)

        if on_led is None:
            # return created objects
            return on_btn, off_btn
        else:
            # listen for external state changes
            cls.cache_handler(AccessoryStateSource(address, on_led, aux_state=TMCC1AuxCommandDef.AUX1_OPT_ONE))
            # return created objects
            return on_btn, off_btn, on_led

    @classmethod
    def accessory(
        cls,
        address: int,
        aux1_pin: int | str,
        aux2_pin: int | str,
        aux1_led_pin: int | str = None,
        cathode: bool = True,
    ) -> Tuple[Button, Button] | Tuple[Button, Button, LED]:
        """
        Control an accessory that responds to TMCC1 accessory commands, such as one connected
        to an LCS ASC2 configured in accessory, 8 TMCC IDs mode.

        Press and hold the Aux1 button to operate the accessory for as long as Aux1 is held.
        Press the Aux2 button to turn the accessory on or off.
        """
        # make the CommandReqs
        aux1_req, aux1_btn, aux1_led = cls._make_button(
            aux1_pin,
            TMCC1AuxCommandDef.AUX1_OPT_ONE,
            address,
            led_pin=aux1_led_pin,
            cathode=cathode,
            bind=True,
        )
        aux2_req, aux2_btn, aux2_led = cls._make_button(
            aux2_pin,
            TMCC1AuxCommandDef.AUX2_OPT_ONE,
            address,
            cathode=cathode,
        )
        # bind actions to buttons
        aux1_action = aux1_req.as_action()
        aux2_action = aux2_req.as_action()

        aux1_btn.when_pressed = cls._with_held_action(aux1_action, aux1_btn)
        aux2_btn.when_pressed = aux2_action

        if aux2_led is None:
            return aux1_btn, aux2_btn
        else:
            return aux1_btn, aux2_btn, aux1_led

    @classmethod
    def culvert_loader(
        cls,
        address: int,
        cycle_pin: int | str,
        # lights_pin: int | str = None,
        cycle_led_pin: int | str = None,
        command_control: bool = True,
        cathode: bool = True,
    ) -> Button | Tuple[Button, LED]:
        if command_control is True:
            cycle_req, cycle_btn, cycle_led = cls._make_button(
                cycle_pin,
                TMCC1AuxCommandDef.AUX2_OPT_ONE,
                address,
                led_pin=cycle_led_pin,
                cathode=cathode,
            )
            cycle_btn.when_pressed = cycle_req.as_action(repeat=2)
        else:
            raise NotImplementedError
        if cycle_led is None:
            return cycle_btn
        else:
            cls.cache_handler(AccessoryStateSource(address, cycle_led, aux2_state=TMCC1AuxCommandDef.AUX2_ON))
            return cycle_btn, cycle_led

    @classmethod
    def smoke_fluid_loader(
        cls,
        address: int,
        channel: int,
        dispense_pin: int | str,
        lights_on_pin: int | str = None,
        lights_off_pin: int | str = None,
        command_control: bool = True,
        cathode: bool = True,
    ) -> Tuple[Button, Button]:
        if command_control is True:
            scale = {0: 0} | {x: 1 for x in range(1, 9)} | {x: 2 for x in range(9, 11)}
            scale |= {-x: -1 for x in range(1, 9)} | {-x: -2 for x in range(9, 11)}
            rotate_boom_req = CommandReq.build(TMCC1AuxCommandDef.RELATIVE_SPEED, address)
            knob = JoyStickHandler(
                rotate_boom_req,
                channel,
                data_min=-10,
                data_max=10,
                delay=0.2,
                scale=scale,
            )
            cls.cache_handler(knob)
            cls.cache_device(knob.pot)

            lights_on_req, lights_on_btn, lights_on_led = cls._make_button(
                lights_on_pin,
                TMCC1AuxCommandDef.NUMERIC,
                address,
                data=9,
                cathode=cathode,
            )
            lights_off_req, lights_off_btn, lights_off_led = cls._make_button(
                lights_off_pin,
                TMCC1AuxCommandDef.NUMERIC,
                address,
                data=8,
                cathode=cathode,
            )
            dispense_req, dispense_btn, dispense_led = cls._make_button(
                dispense_pin,
                TMCC1AuxCommandDef.BRAKE,
                address,
                cathode=cathode,
            )
            dispense_btn.when_pressed = dispense_req.as_action(repeat=2)
            lights_on_btn.when_pressed = lights_on_req.as_action(repeat=2)
            lights_off_btn.when_pressed = lights_off_req.as_action(repeat=2)
        else:
            raise NotImplementedError
        return lights_on_btn, lights_off_btn

    @classmethod
    def gantry_crane(
        cls,
        address: int,
        cab_pin_1: int | str,
        cab_pin_2: int | str,
        lift_chn: int | str = 0,
        roll_chn: int | str = 1,
        mag_pin: int | str = None,
        led_pin: int | str = None,
        use_12bit: bool = True,
        cathode: bool = True,
    ) -> Tuple[RotaryEncoder, JoyStickHandler, JoyStickHandler, Button, LED]:
        # use rotary encoder to control crane cab
        cab_prefix = CommandReq.build(TMCC1EngineCommandDef.NUMERIC, address, 1)
        turn_right = CommandReq.build(TMCC1EngineCommandDef.RELATIVE_SPEED, address, 2)
        turn_left = CommandReq.build(TMCC1EngineCommandDef.RELATIVE_SPEED, address, -2)
        cab_ctrl = cls.when_rotary_encoder(
            cab_pin_1,
            cab_pin_2,
            turn_right,
            counterclockwise_cmd=turn_left,
            prefix=cab_prefix,
        )

        # set up joystick for boom lift
        lift_cmd = CommandReq.build(TMCC1EngineCommandDef.BOOST_SPEED, address)
        drop_cmd = CommandReq.build(TMCC1EngineCommandDef.BRAKE_SPEED, address)
        cmd_map = {}
        for i in range(-20, -2, 1):
            cmd_map[i] = drop_cmd
        cmd_map[-2] = cmd_map[-1] = cmd_map[0] = cmd_map[1] = cmd_map[2] = None  # no action
        for i in range(3, 21, 1):
            cmd_map[i] = lift_cmd
        lift_cntr = cls.when_joystick(
            channel=lift_chn,
            use_12bit=use_12bit,
            data_min=-20,
            data_max=20,
            delay=0.10,
            cmds=cmd_map,
        )

        # set up for crane track motion
        scale = {-x: -2 for x in range(9, 21)} | {-x: -1 for x in range(2, 9)}
        scale |= {-1: 0, 0: 0, 1: 0} | {x: 1 for x in range(2, 9)} | {x: 2 for x in range(9, 21)}
        move_prefix = CommandReq.build(TMCC1EngineCommandDef.NUMERIC, address, 2)
        move_cmd = CommandReq.build(TMCC1EngineCommandDef.RELATIVE_SPEED, address)
        move_cntr = cls.when_joystick(
            move_cmd,
            channel=roll_chn,
            use_12bit=use_12bit,
            data_min=-20,
            data_max=20,
            delay=0.10,
            scale=scale,
            prefix=move_prefix,
        )

        btn = led = None
        if mag_pin is not None:
            btn, led = cls.when_toggle_button_pressed(
                mag_pin,
                TMCC1EngineCommandDef.AUX2_OPTION_ONE,
                address,
                led_pin=led_pin,
                auto_timeout=59,
                cathode=cathode,
            )
            cls.cache_handler(EngineStateSource(address, led, lambda x: x.is_aux2))

        return cab_ctrl, lift_cntr, move_cntr, btn, led

    @classmethod
    def crane_car(
        cls,
        address: int,
        cab_pin_1: int | str,
        cab_pin_2: int | str,
        bo_chn: int | str = 0,
        bo_pin: int | str = None,
        bh_pin: int | str = None,
        sh_pin: int | str = None,
        bo_led_pin: int | str = None,
        bh_led_pin: int | str = None,
        sh_led_pin: int | str = None,
        use_12bit: bool = True,
        cathode: bool = True,
    ) -> Tuple[RotaryEncoder, JoyStickHandler, Button, LED, Button, LED, Button, LED]:
        # use rotary encoder to control crane cab
        cab_prefix = CommandReq.build(TMCC1EngineCommandDef.NUMERIC, address, 1)
        turn_right = CommandReq.build(TMCC1EngineCommandDef.RELATIVE_SPEED, address, 1)
        turn_left = CommandReq.build(TMCC1EngineCommandDef.RELATIVE_SPEED, address, -1)
        cab_ctrl = cls.when_rotary_encoder(
            cab_pin_1,
            cab_pin_2,
            turn_right,
            counterclockwise_cmd=turn_left,
            prefix=cab_prefix,
        )

        # set up joystick for boom lift
        lift_cmd = CommandReq.build(TMCC1EngineCommandDef.BOOST_SPEED, address)
        drop_cmd = CommandReq.build(TMCC1EngineCommandDef.BRAKE_SPEED, address)
        cmd_map = {}
        for i in range(-20, -1, 1):
            cmd_map[i] = drop_cmd
        cmd_map[-1] = cmd_map[0] = cmd_map[1] = None  # no action
        for i in range(2, 21, 1):
            cmd_map[i] = lift_cmd
        bo_cntr = cls.when_joystick(
            channel=bo_chn,
            use_12bit=use_12bit,
            data_min=-20,
            data_max=20,
            delay=0.2,
            cmds=cmd_map,
        )

        # boom control
        bo_btn = bo_led = None
        if bo_pin is not None:
            cmd, bo_btn, bo_led = cls.when_button_pressed(
                bo_pin,
                TMCC1EngineCommandDef.NUMERIC,
                address,
                data=1,
                scope=CommandScope.ENGINE,
                led_pin=bo_led_pin,
                cathode=cathode,
            )
            if bo_led:
                cls.cache_handler(EngineStateSource(address, bo_led, lambda x: x.numeric == 1))

        # large hook control
        bh_btn = bh_led = None
        if bh_pin is not None:
            cmd, bh_btn, bh_led = cls.when_button_pressed(
                bh_pin,
                TMCC1EngineCommandDef.NUMERIC,
                address,
                data=2,
                scope=CommandScope.ENGINE,
                led_pin=bh_led_pin,
                cathode=cathode,
            )
            if bh_led:
                cls.cache_handler(EngineStateSource(address, bh_led, lambda x: x.numeric == 2))

        # small hook control
        sh_btn = sh_led = None
        if sh_pin is not None:
            cmd, sh_btn, sh_led = cls.when_button_pressed(
                sh_pin,
                TMCC1EngineCommandDef.NUMERIC,
                address,
                data=3,
                scope=CommandScope.ENGINE,
                led_pin=sh_led_pin,
                cathode=cathode,
            )
            if sh_led:
                cls.cache_handler(EngineStateSource(address, sh_led, lambda x: x.numeric == 3))

        return cab_ctrl, bo_cntr, bo_btn, bo_led, bh_btn, bh_led, sh_btn, sh_led

    @classmethod
    def rocket_launcher(
        cls,
        address: int,
        gantry_chanel: int | str = 0,
        launch_seq_pin: int | str = None,
        launch_now_pin: int | str = None,
        launch_15_pin: int | str = None,
        abort_pin: int | str = None,
        siren_pin: int | str = None,
        klaxon_pin: int | str = None,
        ground_crew_pin: int | str = None,
        mission_control_pin: int | str = None,
        flicker_on_pin: int | str = None,
        flicker_off_pin: int | str = None,
    ):
        pass

    @classmethod
    def engine(
        cls,
        address: int,
        channel: int = 0,
        fwd_pin: int | str = None,
        rev_pin: int | str = None,
        is_legacy: bool = True,
        use_12bit: bool = True,
        scope: CommandScope = CommandScope.ENGINE,
        cathode: bool = True,
    ) -> Tuple[PotHandler, Button, Button]:
        fwd_btn = rev_btn = None
        fwd_cmd = rev_cmd = None
        if is_legacy is True:
            speed_cmd = CommandReq.build(TMCC2EngineCommandDef.ABSOLUTE_SPEED, address, 0, scope)
            if fwd_pin is not None:
                fwd_cmd, fwd_btn, _ = cls._make_button(
                    fwd_pin,
                    TMCC2EngineCommandDef.FORWARD_DIRECTION,
                    address,
                    scope=scope,
                    cathode=cathode,
                )
            if rev_pin is not None:
                rev_cmd, rev_btn, _ = cls._make_button(
                    rev_pin,
                    TMCC2EngineCommandDef.REVERSE_DIRECTION,
                    address,
                    scope=scope,
                    cathode=cathode,
                )
        else:
            speed_cmd = CommandReq.build(TMCC1EngineCommandDef.ABSOLUTE_SPEED, address, 0, scope)
            if fwd_pin is not None:
                fwd_cmd, fwd_btn, _ = cls._make_button(
                    fwd_pin,
                    TMCC1EngineCommandDef.FORWARD_DIRECTION,
                    address,
                    scope=scope,
                    cathode=cathode,
                )
            if rev_pin is not None:
                rev_cmd, rev_btn, _ = cls._make_button(
                    rev_pin,
                    TMCC1EngineCommandDef.REVERSE_DIRECTION,
                    address,
                    scope=scope,
                    cathode=cathode,
                )
        # make a pot to handle speed
        pot = cls.when_pot(speed_cmd, channel=channel, use_12bit=use_12bit)

        # assign button actions
        if fwd_btn is not None:
            fwd_btn.when_pressed = fwd_cmd.as_action()
        if rev_btn is not None:
            rev_btn.when_pressed = rev_cmd.as_action()
        # return objects
        return pot, fwd_btn, rev_btn

    @classmethod
    def when_button_pressed(
        cls,
        pin: int | str,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        led_pin: int | str = None,
        cathode: bool = True,
    ) -> Tuple[CommandReq, Button, LED]:
        # Use helper method to construct objects
        command, button, led = cls._make_button(
            pin,
            command,
            address,
            data,
            scope,
            led_pin,
            cathode=cathode,
        )

        # create a command function to fire when button pressed
        button.when_pressed = command.as_action()
        return command, button, led

    @classmethod
    def when_button_held(
        cls,
        pin: int | str,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        frequency: float = 1,
        led_pin: int | str = None,
        cathode: bool = True,
    ) -> Button:
        # Use helper method to construct objects
        command, button, led = cls._make_button(
            pin,
            command,
            address,
            data=data,
            scope=scope,
            led_pin=led_pin,
            cathode=cathode,
        )

        # create a command function to fire when button held
        button.when_held = command.as_action()
        button.hold_repeat = True
        button.hold_time = frequency
        return button

    @classmethod
    def when_toggle_switch(
        cls,
        off_pin: int | str,
        on_pin: int | str,
        off_command: CommandReq,
        on_command: CommandReq,
        led_pin: int | str = None,
        cathode: bool = True,
    ) -> Tuple[Button, Button, LED]:
        # create a LED, if requested. It is turned on by pressing the
        # ON button, and turned off by pressing the OFF button
        if led_pin is not None and led_pin != 0:
            led = LED(led_pin, active_high=cathode)
            led.on()
        else:
            led = None

        # create the off and on buttons
        off_button = Button(off_pin, bounce_time=DEFAULT_BOUNCE_TIME)
        on_button = Button(on_pin, bounce_time=DEFAULT_BOUNCE_TIME)

        # bind them to functions; we need to wrap the functions if we're using a LED
        off_action = off_command.as_action()
        on_action = on_command.as_action()
        if led is not None:
            off_button.when_pressed = cls._with_off_action(off_action, led)
            on_button.when_pressed = cls._with_on_action(on_action, led)

            def func_off(_: Message) -> None:
                led.off()

            DependencyCache.listen_for_disablers(on_command, func_off)

            def func_on(_: Message) -> None:
                led.on()

            DependencyCache.listen_for_enablers(on_command, func_on)

        else:
            off_button.when_pressed = off_action
            on_button.when_pressed = on_action

        cls.cache_device(off_button)
        cls.cache_device(on_button)
        if led is not None:
            cls.cache_device(led)
        return off_button, on_button, led

    @classmethod
    def when_toggle_button_pressed(
        cls,
        pin: int | str,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        led_pin: int | str = None,
        initial_state: bool = False,
        auto_timeout: int = None,
        cathode: bool = True,
    ) -> tuple[Button, LED]:
        # Use helper method to construct objects
        command, button, led = cls._make_button(
            pin,
            command,
            address,
            data,
            scope,
            led_pin,
            cathode=cathode,
        )

        # create a command function to fire when button pressed
        action = command.as_action()
        if led_pin is not None and led_pin != 0:
            button.when_pressed = cls._with_toggle_action(action, led, auto_timeout)
            led.source = None  # want led to stay lit when button pressed
            if initial_state is True:
                led.on()
            else:
                led.off()
        else:
            button.when_pressed = action
        return button, led

    @classmethod
    def when_pot(
        cls,
        command: CommandReq | CommandDefEnum | None = None,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = None,
        channel: int = 0,
        use_12bit: bool = True,
        data_min: int = None,
        data_max: int = None,
        threshold: float = None,
        delay: float = 0.05,
        scale: Dict[int, int] = None,
        cmds: Dict[int, T] = None,
    ) -> PotHandler:
        if isinstance(command, CommandDefEnum):
            command = CommandReq.build(command, address, 0, scope)
        if command and command.num_data_bits == 0:
            raise ValueError("Command does not support variable data")
        knob = PotHandler(
            command=command,
            channel=channel,
            use_12bit=use_12bit,
            data_min=data_min,
            data_max=data_max,
            threshold=threshold,
            delay=delay,
            scale=scale,
            cmds=cmds,
        )
        cls.cache_handler(knob)
        cls.cache_device(knob.pot)
        return knob

    @classmethod
    def when_joystick(
        cls,
        command: CommandReq | CommandDefEnum | None = None,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = None,
        channel: int = 0,
        use_12bit: bool = False,
        data_min: int = None,
        data_max: int = None,
        delay: float = 0.05,
        scale: Dict[int, int] = None,
        cmds: Dict[int, T] = None,
        prefix: CommandReq = None,
    ) -> JoyStickHandler:
        if isinstance(command, CommandDefEnum):
            command = CommandReq.build(command, address, 0, scope)
        if command and command.num_data_bits == 0:
            raise ValueError("Command does not support variable data")
        joystick = JoyStickHandler(
            command=command,
            channel=channel,
            use_12bit=use_12bit,
            data_min=data_min,
            data_max=data_max,
            delay=delay,
            scale=scale,
            cmds=cmds,
            prefix=prefix,
        )
        cls.cache_handler(joystick)
        cls.cache_device(joystick.pot)
        return joystick

    @classmethod
    def when_rotary_encoder(
        cls,
        pin_1: int | str,
        pin_2: int | str,
        clockwise_cmd: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = None,
        scope: CommandScope = None,
        counterclockwise_cmd: CommandReq | CommandDefEnum = None,
        cc_data: int = None,
        max_steps: int = 100,
        ramp: Dict[int, int] = None,
        prefix: CommandReq = None,
    ) -> RotaryEncoder:
        re = RotaryEncoder(pin_1, pin_2, wrap=True, max_steps=max_steps)
        cls.cache_device(re)

        # make commands
        if isinstance(clockwise_cmd, CommandDefEnum):
            clockwise_cmd = CommandReq.build(clockwise_cmd, address=address, data=data, scope=scope)
        if counterclockwise_cmd is None:
            counterclockwise_cmd = clockwise_cmd
        elif isinstance(counterclockwise_cmd, CommandDefEnum):
            counterclockwise_cmd = CommandReq.build(counterclockwise_cmd, address=address, data=cc_data, scope=scope)

        # construct ramp
        if ramp is None:
            ramp = {
                50: 3,
                250: 2,
                500: 1,
            }
        # bind commands
        re.when_rotated_clockwise = cls._with_re_action(
            clockwise_cmd.address,
            clockwise_cmd,
            ramp,
            prefix if prefix else None,
        )
        re.when_rotated_counter_clockwise = cls._with_re_action(
            clockwise_cmd.address,
            counterclockwise_cmd,
            ramp,
            prefix if prefix else None,
            True,
        )
        # return rotary encoder
        return re

    @classmethod
    def reset_all(cls) -> None:
        for handler in cls.GPIO_HANDLER_CACHE:
            handler.reset()
            handler.join()  # wait for thread to shut down
        cls.GPIO_HANDLER_CACHE = set()

        for device in cls.GPIO_DEVICE_CACHE:
            device.close()
        cls.GPIO_DEVICE_CACHE = set()

    @classmethod
    def cache_handler(cls, handler: Thread) -> None:
        cls.GPIO_HANDLER_CACHE.add(handler)

    @classmethod
    def cache_device(cls, device: Device) -> None:
        """
        Keep devices around after creation so they remain in scope
        """
        cls.GPIO_DEVICE_CACHE.add(device)

    @classmethod
    def release_device(cls, device: Device) -> None:
        device.close()
        cls.GPIO_DEVICE_CACHE.remove(device)

    @classmethod
    def _make_button(
        cls,
        pin: int | str,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = None,
        scope: CommandScope = None,
        led_pin: int | str = None,
        held: bool = False,
        frequency: float = 0.06,
        initially_on: bool = False,
        bind: bool = False,
        cathode: bool = True,
    ) -> Tuple[CommandReq, Button, LED]:
        # if command is actually a CommandDefEnum, build_req a CommandReq
        if isinstance(command, CommandDefEnum):
            command = CommandReq.build(command, address=address, data=data, scope=scope)

        # create the button object we will associate an action with
        button = Button(pin, bounce_time=DEFAULT_BOUNCE_TIME)
        if held is True:
            button.hold_repeat = held
            button.hold_repeat = frequency
        cls.cache_device(button)

        # create a LED, if asked, and tie its source to the button
        if led_pin is not None and led_pin != 0:
            led = LED(led_pin, active_high=cathode, initial_value=initially_on)
            led.source = None
            if bind:
                led.source = button
            cls.cache_device(led)
        else:
            led = None
        return command, button, led

    @classmethod
    def _with_held_action(cls, action: Callable, button: Button, delay: float = 0.10) -> Callable:
        def held_action() -> None:
            while button.is_active:
                action()
                time.sleep(delay)

        return held_action

    @classmethod
    def _with_toggle_action(cls, action: Callable, led: LED, auto_timeout: int = None) -> Callable:
        if cls.GPIO_DELAY_HANDLER is None:
            cls.GPIO_DELAY_HANDLER = GpioDelayHandler()
            cls.cache_handler(cls.GPIO_DELAY_HANDLER)

        ev: sched.Event | None = None

        def toggle_action() -> None:
            nonlocal ev
            action()
            if led.value:
                if ev is not None:
                    cls.GPIO_DELAY_HANDLER.cancel(ev)
                    ev = None
                led.off()
            else:
                led.on()
                if auto_timeout:
                    ev = cls.GPIO_DELAY_HANDLER.schedule(auto_timeout, led.off)

        return toggle_action

    @classmethod
    def _with_off_action(cls, action: Callable, led: LED = None, *impacted_leds: LED) -> Callable:
        def off_action() -> None:
            action()
            if led is not None:
                led.off()
            if impacted_leds:
                for impacted_led in impacted_leds:
                    impacted_led.on()

        return off_action

    @classmethod
    def _with_on_action(cls, action: Callable, led: LED, *impacted_leds: LED) -> Callable:
        def on_action() -> None:
            action()
            if led is not None:
                led.on()
            if impacted_leds:
                for impacted_led in impacted_leds:
                    impacted_led.off()

        return on_action

    @classmethod
    def _with_re_action(
        cls,
        address: int,
        command: CommandReq,
        ramp: Dict[int, int] = None,
        prefix: CommandReq = None,
        cc: bool = False,
    ) -> Callable:
        last_rotation_at = cls.current_milli_time()

        def func() -> None:
            nonlocal last_rotation_at
            last_rotated = cls.current_milli_time() - last_rotation_at
            data = 1 if cc is False else -1
            if ramp:
                for ramp_val, data_val in ramp.items():
                    if last_rotated <= ramp_val:
                        data = data_val if cc is False else -data_val
                        break
            if prefix:
                if GpioHandler.engine_numeric(address) == prefix.data:
                    pass
                else:
                    prefix.as_action(repeat=3)()
            command.as_action(repeat=2)(new_data=data)
            last_rotation_at = cls.current_milli_time()

        return func
