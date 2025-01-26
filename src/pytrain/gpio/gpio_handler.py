import logging
import math
import sched
import threading
import time
from threading import Thread
from typing import Tuple, Callable, Dict, TypeVar, List, Union

from gpiozero import Button, LED, MCP3008, MCP3208, RotaryEncoder, Device, AnalogInputDevice, PingServer

from .controller import Controller, ControllerI2C
from .i2c.ads_1x15 import Ads1115
from .i2c.button_i2c import ButtonI2C
from .i2c.led_i2c import LEDI2C
from .keypad import KEYPAD_PCF8574_ADDRESS
from ..comm.comm_buffer import CommBuffer
from ..comm.command_listener import Message
from ..db.component_state_store import DependencyCache, ComponentStateStore
from ..gpio.state_source import SwitchStateSource, AccessoryStateSource, EngineStateSource
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, PROGRAM_NAME
from ..protocol.constants import DEFAULT_ADDRESS
from ..protocol.tmcc1.tmcc1_constants import (
    TMCC1SwitchCommandEnum,
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
    TMCC1RouteCommandEnum,
    TMCC1SyncCommandEnum,
)
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from ..utils.ip_tools import find_base_address

log = logging.getLogger(__name__)

DEFAULT_BOUNCE_TIME: float = 0.02  # button debounce threshold
DEFAULT_VARIANCE: float = 0.001  # pot difference variance

T = TypeVar("T", bound=CommandReq)

P = TypeVar("P", bound=Union[int, str, Tuple[int], Tuple[int, int], Tuple[int, int, int]])


class PressedHeldDef:
    def __init__(
        self,
        pressed_req: CommandReq,
        held_req: CommandReq = None,
        repeat_action: int = 1,
        held_threshold: float = 0.5,
        hold_repeat: bool = False,
        frequency: float = 0.1,
        data: Callable = None,
    ) -> None:
        self._pressed_req = pressed_req
        self._held_req = held_req if held_req else pressed_req
        self._repeat_action = repeat_action
        self.held_threshold = held_threshold
        self.repeat = hold_repeat
        self.frequency = frequency
        self._data_gen = data

    def update_target(self, address: int = None, data: int = None, scope: CommandScope = None) -> None:
        if address is not None:
            self._pressed_req.address = address
            if self._pressed_req != self._held_req:
                self._held_req.address = address
        if data is not None:
            self._pressed_req.data = data
            if self._pressed_req != self._held_req:
                self._held_req.data = data
        if scope is not None:
            self._pressed_req.scope = scope
            if self._pressed_req != self._held_req:
                self._held_req.scope = scope

    def as_action(self, address: int = None, data: int = None, scope: CommandScope = None):
        self.update_target(address=address, data=data, scope=scope)
        return GpioHandler.when_button_pressed_or_held_action(
            self._pressed_req.as_action(repeat=self._repeat_action),
            self._held_req.as_action(repeat=self._repeat_action),
            held_threshold=self.held_threshold,
            held_repeat=self.repeat,
            frequency=self.frequency,
            data_gen=self._data_gen,
        )


class GpioDelayHandler(Thread):
    """
    Handle delayed (scheduled) requests. Implementation uses Python's lightweight
    sched module to keep a list of requests to issue in the future. We use
    threading.Event.wait() as the sleep function, as it is interruptable. This
    allows us to schedule requests in any order and still have them fire at the
    appropriate time.
    """

    def __init__(self) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} GPIO Delay Handler")
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
        self._interp = GpioHandler.make_interpolator(data_max, data_min)
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

    @staticmethod
    def make_interpolator(
        to_max: int | float,
        to_min: int | float = 0,
        from_min: int | float = 0.0,
        from_max: int | float = 1.0,
        as_float: bool = False,
    ) -> Callable:
        # Figure out how 'wide' each range is
        from_span = from_max - from_min
        to_span = to_max - to_min

        # Compute the scale factor between left and right values
        scale_factor = float(to_span) / float(from_span)

        # create interpolation function using pre-calculated scaleFactor
        def interp_fn(value) -> int | float:
            if as_float:
                scaled_value = float((to_min + (value - from_min) * scale_factor))
            else:
                scaled_value = int(round(to_min + (value - from_min) * scale_factor))
            scaled_value = min(scaled_value, to_max)
            scaled_value = max(scaled_value, to_min)
            return scaled_value

        return interp_fn

    @classmethod
    def calibrate_joystick(
        cls,
        x_axis_chn: int = 0,
        y_axis_chn: int = 1,
        i2c_addr=None,
        use_12bit: bool = True,
    ) -> None:
        if i2c_addr:
            x_axis = Ads1115(channel=x_axis_chn, address=i2c_addr)
            y_axis = Ads1115(channel=y_axis_chn, address=i2c_addr)
        elif use_12bit is True:
            x_axis = MCP3208(channel=x_axis_chn, differential=False)
            y_axis = MCP3208(channel=y_axis_chn, differential=False)
        else:
            x_axis = MCP3008(channel=x_axis_chn, differential=False)
            y_axis = MCP3008(channel=y_axis_chn, differential=False)

        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        print("Rotate Joystick clockwise, making sure to fully exercise its range...")
        time.sleep(5)
        is_running = True
        start_at = cls.current_milli_time()
        cycle = 0
        while is_running:
            x = x_axis.value
            y = y_axis.value

            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
            cycle += 1

            elapsed = cls.current_milli_time() - start_at
            if cycle % 1000 == 0:
                remaining = (10000 - elapsed) / 1000.0
                print(f"Time remaining: {remaining} seconds", end="\r")
            if elapsed > 10000:
                is_running = False
        print(f" X axis range: {min_x} - {max_x}")
        print(f" Y axis range: {min_y} - {max_y}")

        print("Now take your hands off hit joystick and let it recenter for 10 seconds")
        time.sleep(5)
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
    def controller(
        cls,
        lcd_address: int = 0x27,
        lcd_rows: int = 4,
        lcd_cols: int = 20,
        keypad_address: int | None = KEYPAD_PCF8574_ADDRESS,
        row_pins: List[int | str] = None,
        column_pins: List[int | str] = None,
        base_online_pin: P = None,
        base_offline_pin: P = None,
        base_cathode: bool = True,
        base_ping_freq: int = 5,
        speed_pins: List[int | str] = None,
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
    ) -> Controller:
        if row_pins and column_pins:
            c = Controller(
                lcd_address=lcd_address,
                lcd_rows=lcd_rows,
                lcd_cols=lcd_cols,
                row_pins=row_pins,
                column_pins=column_pins,
                base_online_pin=base_online_pin,
                base_offline_pin=base_offline_pin,
                base_cathode=base_cathode,
                base_ping_freq=base_ping_freq,
                speed_pins=speed_pins,
                halt_pin=halt_pin,
                reset_pin=reset_pin,
                fwd_pin=fwd_pin,
                rev_pin=rev_pin,
                front_coupler_pin=front_coupler_pin,
                rear_coupler_pin=rear_coupler_pin,
                start_up_pin=start_up_pin,
                shutdown_pin=shutdown_pin,
                boost_pin=boost_pin,
                brake_pin=brake_pin,
                bell_pin=bell_pin,
                horn_pin=horn_pin,
                rpm_up_pin=rpm_up_pin,
                rpm_down_pin=rpm_down_pin,
                labor_up_pin=labor_up_pin,
                labor_down_pin=labor_down_pin,
                vol_up_pin=vol_up_pin,
                vol_down_pin=vol_down_pin,
                smoke_on_pin=smoke_on_pin,
                smoke_off_pin=smoke_off_pin,
                tower_dialog_pin=tower_dialog_pin,
                engr_dialog_pin=engr_dialog_pin,
                aux1_pin=aux1_pin,
                aux2_pin=aux2_pin,
                aux3_pin=aux3_pin,
                stop_immediate_pin=stop_immediate_pin,
                i2c_adc_address=i2c_adc_address,
                train_brake_chn=train_brake_chn,
                quilling_horn_chn=quilling_horn_chn,
            )
        else:
            c = ControllerI2C(
                lcd_address=lcd_address,
                lcd_rows=lcd_rows,
                lcd_cols=lcd_cols,
                keypad_address=keypad_address,
                base_online_pin=base_online_pin,
                base_offline_pin=base_offline_pin,
                base_cathode=base_cathode,
                base_ping_freq=base_ping_freq,
                speed_pins=speed_pins,
                halt_pin=halt_pin,
                reset_pin=reset_pin,
                fwd_pin=fwd_pin,
                rev_pin=rev_pin,
                front_coupler_pin=front_coupler_pin,
                rear_coupler_pin=rear_coupler_pin,
                start_up_pin=start_up_pin,
                shutdown_pin=shutdown_pin,
                boost_pin=boost_pin,
                brake_pin=brake_pin,
                bell_pin=bell_pin,
                horn_pin=horn_pin,
                rpm_up_pin=rpm_up_pin,
                rpm_down_pin=rpm_down_pin,
                labor_up_pin=labor_up_pin,
                labor_down_pin=labor_down_pin,
                vol_up_pin=vol_up_pin,
                vol_down_pin=vol_down_pin,
                smoke_on_pin=smoke_on_pin,
                smoke_off_pin=smoke_off_pin,
                tower_dialog_pin=tower_dialog_pin,
                engr_dialog_pin=engr_dialog_pin,
                aux1_pin=aux1_pin,
                aux2_pin=aux2_pin,
                aux3_pin=aux3_pin,
                stop_immediate_pin=stop_immediate_pin,
                i2c_adc_address=i2c_adc_address,
                train_brake_chn=train_brake_chn,
                quilling_horn_chn=quilling_horn_chn,
            )
        cls.cache_handler(c)
        return c

    @classmethod
    def base_watcher(
        cls, server: str = None, active_pin: P = None, inactive_pin: P = None, cathode: bool = True, delay: float = 10
    ) -> Tuple[PingServer, LED, LED]:
        # if server isn't specified, try to figure it out
        if server is None:
            server = CommBuffer().base3_address
        if server is None:
            print("Looking for Base 3 on local network...")
            server = find_base_address()
            if server is None:
                raise ValueError("Could not determine base address")

        # set up a ping server, treat it as a device
        ping_server = PingServer(server, event_delay=delay)
        cls.cache_device(ping_server)

        # set up active led, if any
        active_led = None
        if active_pin:
            active_led = cls.make_led(active_pin, cathode=cathode)
            active_led.value = 1 if ping_server.is_active else 0
            cls.cache_device(active_led)

        inactive_led = None
        if inactive_pin:
            inactive_led = cls.make_led(inactive_pin, cathode=cathode)
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
    def power_watcher(
        cls,
        power_on_pin: P,
        cathode: bool = True,
    ) -> LED:
        """
        Illuminates a LED as long as the attached Pi has power
        """
        power_led = cls.make_led(power_on_pin, cathode=cathode)
        power_led.value = 1
        cls.cache_device(power_led)
        return power_led

    @classmethod
    def system_shutdown(
        cls,
        shutdown_pin: P,
        hold_time: float = 2.5,
    ) -> Button:
        """
        Send the system shutdown command to all nodes
        """
        cmd, shutdown_btn, led = cls.make_button(shutdown_pin, TMCC1SyncCommandEnum.SHUTDOWN, hold_time=hold_time)
        shutdown_btn.when_held = cmd.as_action()
        return shutdown_btn

    @classmethod
    def system_restart(
        cls,
        restart_pin: P,
        hold_time: float = 2.5,
    ) -> Button:
        """
        Send the system restart command to all nodes
        """
        cmd, restart_btn, led = cls.make_button(restart_pin, TMCC1SyncCommandEnum.RESTART, hold_time=hold_time)
        restart_btn.when_held = cmd.as_action()
        return restart_btn

    @classmethod
    def system_update(
        cls,
        update_pin: P,
        hold_time: float = 2.5,
    ) -> Button:
        """
        Send the system update command to all nodes
        """
        cmd, update_btn, led = cls.make_button(update_pin, TMCC1SyncCommandEnum.UPDATE, hold_time=hold_time)
        update_btn.when_held = cmd.as_action()
        return update_btn

    @classmethod
    def route(
        cls,
        address: int,
        btn_pin: P,
        led_pin: P = None,
        cathode: bool = True,
    ) -> Button | Tuple[Button, LED]:
        """
        Fire a TMCC2/Legacy Route, throwing all incorporated turnouts to the correct state
        """
        # make the CommandReq
        req, btn, led = cls.make_button(
            btn_pin,
            TMCC1RouteCommandEnum.FIRE,
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
        thru_pin: P,
        out_pin: P,
        thru_led_pin: P = None,
        out_led_pin: P = None,
        cathode: bool = True,
        initial_state: TMCC1SwitchCommandEnum = None,
    ) -> Tuple[Button, Button] | Tuple[Button, Button, LED, LED]:
        """
        Control a switch/turnout that responds to TMCC1 switch commands, such
        as Lionel Command/Control-equipped turnouts or turnouts connected to
        an LCS ACS 2 configured in "Switch" mode.

        Optionally, manage LEDs to reflect turnout state; thru or out. Also
        supports bi-color LEDs with either common cathode or anode.
        """
        if initial_state is None:
            state = ComponentStateStore.get_state(CommandScope.SWITCH, address, create=False)
            if state:
                initial_state = state.state
            if initial_state is None:
                initial_state = TMCC1SwitchCommandEnum.THRU

        # make the CommandReqs
        thru_req, thru_btn, thru_led = cls.make_button(
            thru_pin,
            TMCC1SwitchCommandEnum.THRU,
            address,
            led_pin=thru_led_pin,
            initially_on=initial_state == TMCC1SwitchCommandEnum.THRU,
            cathode=cathode,
        )
        out_req, out_btn, out_led = cls.make_button(
            out_pin,
            TMCC1SwitchCommandEnum.OUT,
            address,
            led_pin=out_led_pin,
            initially_on=initial_state == TMCC1SwitchCommandEnum.OUT,
            cathode=cathode,
        )
        # bind actions to buttons
        thru_action = thru_req.as_action(repeat=2)
        out_action = out_req.as_action(repeat=2)

        thru_btn.when_pressed = cls._with_on_action(thru_action, thru_led, out_led)
        out_btn.when_pressed = cls._with_on_action(out_action, out_led, thru_led)

        if thru_led is not None and out_led is not None:
            cls.cache_handler(SwitchStateSource(address, thru_led, out_led))
            return thru_btn, out_btn, thru_led, out_led
        else:
            # return created objects
            return thru_btn, out_btn

    @classmethod
    def power_district(
        cls,
        address: int,
        on_pin: P,
        off_pin: P,
        on_led_pin: P = None,
        cathode: bool = True,
        initial_state: TMCC1AuxCommandEnum | bool = None,
    ) -> Tuple[Button, Button] | Tuple[Button, Button, LED]:
        """
        Control a power district that responds to TMCC1 accessory commands, such
        as an LCS BP2 configured in "Acc" mode.
        """
        if initial_state is None:
            # TODO: query initial state
            initial_state = TMCC1AuxCommandEnum.AUX2_OPT_ONE

        # make the CommandReqs
        on_req, on_btn, on_led = cls.make_button(
            on_pin,
            TMCC1AuxCommandEnum.AUX1_OPT_ONE,
            address,
            led_pin=on_led_pin,
            cathode=cathode,
            initially_on=initial_state == TMCC1AuxCommandEnum.AUX1_OPT_ONE,
        )
        off_req, off_btn, off_led = cls.make_button(
            off_pin,
            TMCC1AuxCommandEnum.AUX2_OPT_ONE,
            address,
            cathode=cathode,
            initially_on=initial_state == TMCC1AuxCommandEnum.AUX2_OPT_ONE,
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
            cls.cache_handler(AccessoryStateSource(address, on_led, aux_state=TMCC1AuxCommandEnum.AUX1_OPT_ONE))
            # return created objects
            return on_btn, off_btn, on_led

    @classmethod
    def accessory(
        cls,
        address: int,
        aux1_pin: P,
        aux2_pin: P,
        aux1_led_pin: P = None,
        cathode: bool = True,
    ) -> Tuple[Button, Button] | Tuple[Button, Button, LED]:
        """
        Control an accessory that responds to TMCC1 accessory commands, such as one connected
        to an LCS ASC2 configured in accessory, 8 TMCC IDs mode.

        Press and hold the Aux1 button to operate the accessory for as long as Aux1 is held.
        Press the Aux2 button to turn the accessory on or off.
        """
        # make the CommandReqs
        aux1_req, aux1_btn, aux1_led = cls.make_button(
            aux1_pin,
            TMCC1AuxCommandEnum.AUX1_OPT_ONE,
            address,
            led_pin=aux1_led_pin,
            cathode=cathode,
            bind=True,
        )
        aux2_req, aux2_btn, aux2_led = cls.make_button(
            aux2_pin,
            TMCC1AuxCommandEnum.AUX2_OPT_ONE,
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
        cycle_pin: P,
        # lights_pin: P = None,
        cycle_led_pin: P = None,
        command_control: bool = True,
        cathode: bool = True,
    ) -> Button | Tuple[Button, LED]:
        if command_control is True:
            cycle_req, cycle_btn, cycle_led = cls.make_button(
                cycle_pin,
                TMCC1AuxCommandEnum.AUX2_OPT_ONE,
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
            cls.cache_handler(AccessoryStateSource(address, cycle_led, aux2_state=TMCC1AuxCommandEnum.AUX2_ON))
            return cycle_btn, cycle_led

    @classmethod
    def smoke_fluid_loader(
        cls,
        address: int,
        channel: int,
        dispense_pin: P,
        lights_on_pin: P = None,
        lights_off_pin: P = None,
        command_control: bool = True,
        cathode: bool = True,
    ) -> Tuple[Button, Button]:
        if command_control is True:
            scale = {0: 0} | {x: 1 for x in range(1, 9)} | {x: 2 for x in range(9, 11)}
            scale |= {-x: -1 for x in range(1, 9)} | {-x: -2 for x in range(9, 11)}
            rotate_boom_req = CommandReq.build(TMCC1AuxCommandEnum.RELATIVE_SPEED, address)
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

            lights_on_req, lights_on_btn, lights_on_led = cls.make_button(
                lights_on_pin,
                TMCC1AuxCommandEnum.NUMERIC,
                address,
                data=9,
                cathode=cathode,
            )
            lights_off_req, lights_off_btn, lights_off_led = cls.make_button(
                lights_off_pin,
                TMCC1AuxCommandEnum.NUMERIC,
                address,
                data=8,
                cathode=cathode,
            )
            dispense_req, dispense_btn, dispense_led = cls.make_button(
                dispense_pin,
                TMCC1AuxCommandEnum.BRAKE,
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
        cab_pin_1: P,
        cab_pin_2: P,
        lift_chn: P = 0,
        roll_chn: P = 1,
        mag_pin: P = None,
        led_pin: P = None,
        use_12bit: bool = True,
        cathode: bool = True,
    ) -> Tuple[RotaryEncoder, JoyStickHandler, JoyStickHandler, Button, LED]:
        # use rotary encoder to control crane cab
        cab_prefix = CommandReq.build(TMCC1EngineCommandEnum.NUMERIC, address, 1)
        turn_right = CommandReq.build(TMCC1EngineCommandEnum.RELATIVE_SPEED, address, 2)
        turn_left = CommandReq.build(TMCC1EngineCommandEnum.RELATIVE_SPEED, address, -2)
        cab_ctrl = cls.when_rotary_encoder(
            cab_pin_1,
            cab_pin_2,
            turn_right,
            counterclockwise_cmd=turn_left,
            prefix=cab_prefix,
        )

        # set up joystick for boom lift
        lift_cmd = CommandReq.build(TMCC1EngineCommandEnum.BOOST_SPEED, address)
        drop_cmd = CommandReq.build(TMCC1EngineCommandEnum.BRAKE_SPEED, address)
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
        move_prefix = CommandReq.build(TMCC1EngineCommandEnum.NUMERIC, address, 2)
        move_cmd = CommandReq.build(TMCC1EngineCommandEnum.RELATIVE_SPEED, address)
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
                TMCC1EngineCommandEnum.AUX2_OPTION_ONE,
                address,
                led_pin=led_pin,
                auto_timeout=59,
                cathode=cathode,
            )
            led.blink()
            cls.cache_handler(EngineStateSource(address, led, lambda x: x.is_aux2))

        return cab_ctrl, lift_cntr, move_cntr, btn, led

    @classmethod
    def crane_car(
        cls,
        address: int,
        cab_pin_1: P,
        cab_pin_2: P,
        bo_chn: P = 0,
        bo_pin: P = None,
        bh_pin: P = None,
        sh_pin: P = None,
        bo_led_pin: P = None,
        bh_led_pin: P = None,
        sh_led_pin: P = None,
        use_12bit: bool = True,
        cathode: bool = True,
    ) -> Tuple[RotaryEncoder, JoyStickHandler, Button, LED, Button, LED, Button, LED]:
        # use rotary encoder to control crane cab
        cab_prefix = CommandReq.build(TMCC1EngineCommandEnum.NUMERIC, address, 1)
        turn_right = CommandReq.build(TMCC1EngineCommandEnum.RELATIVE_SPEED, address, 1)
        turn_left = CommandReq.build(TMCC1EngineCommandEnum.RELATIVE_SPEED, address, -1)
        cab_ctrl = cls.when_rotary_encoder(
            cab_pin_1,
            cab_pin_2,
            turn_right,
            counterclockwise_cmd=turn_left,
            prefix=cab_prefix,
        )

        # set up joystick for boom lift
        lift_cmd = CommandReq.build(TMCC1EngineCommandEnum.BOOST_SPEED, address)
        drop_cmd = CommandReq.build(TMCC1EngineCommandEnum.BRAKE_SPEED, address)
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
                TMCC1EngineCommandEnum.NUMERIC,
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
                TMCC1EngineCommandEnum.NUMERIC,
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
                TMCC1EngineCommandEnum.NUMERIC,
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
        gantry_chanel: P = 0,
        launch_seq_pin: P = None,
        launch_now_pin: P = None,
        launch_15_pin: P = None,
        abort_pin: P = None,
        siren_pin: P = None,
        klaxon_pin: P = None,
        ground_crew_pin: P = None,
        mission_control_pin: P = None,
        flicker_on_pin: P = None,
        flicker_off_pin: P = None,
    ):
        pass

    @classmethod
    def engine(
        cls,
        address: int,
        speed_pin_1: P = None,
        speed_pin_2: P = None,
        fwd_pin: P = None,
        rev_pin: P = None,
        is_legacy: bool = True,
        scope: CommandScope = CommandScope.ENGINE,
        cathode: bool = True,
    ) -> Tuple[RotaryEncoder, Button, Button]:
        fwd_btn = rev_btn = None
        fwd_cmd = rev_cmd = None
        if is_legacy is True:
            max_steps = 200
            speed_cmd = CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, address, 0, scope)
            if fwd_pin is not None:
                fwd_cmd, fwd_btn, _ = cls.make_button(
                    fwd_pin,
                    TMCC2EngineCommandEnum.FORWARD_DIRECTION,
                    address,
                    scope=scope,
                    cathode=cathode,
                )
            if rev_pin is not None:
                rev_cmd, rev_btn, _ = cls.make_button(
                    rev_pin,
                    TMCC2EngineCommandEnum.REVERSE_DIRECTION,
                    address,
                    scope=scope,
                    cathode=cathode,
                )
        else:
            max_steps = 32
            speed_cmd = CommandReq.build(TMCC1EngineCommandEnum.ABSOLUTE_SPEED, address, 0, scope)
            if fwd_pin is not None:
                fwd_cmd, fwd_btn, _ = cls.make_button(
                    fwd_pin,
                    TMCC1EngineCommandEnum.FORWARD_DIRECTION,
                    address,
                    scope=scope,
                    cathode=cathode,
                )
            if rev_pin is not None:
                rev_cmd, rev_btn, _ = cls.make_button(
                    rev_pin,
                    TMCC1EngineCommandEnum.REVERSE_DIRECTION,
                    address,
                    scope=scope,
                    cathode=cathode,
                )

        # get the initial speed of the engine/train
        state = ComponentStateStore.get_state(scope, address)
        if state and state.speed:
            initial_step = int(max(state.speed - max_steps, int(-max_steps / 2)))
        else:
            initial_step = int(-max_steps / 2)
        # make a RE to handle speed
        speed_ctrl = cls.when_rotary_encoder(
            speed_pin_1,
            speed_pin_2,
            speed_cmd,
            wrap=False,
            max_steps=int(max_steps / 2),
            initial_step=initial_step,
            scaler=lambda x: int(max(min(x + (max_steps / 2), max_steps - 1), 0)),
            use_steps=True,
        )

        # assign button actions
        if fwd_btn is not None:
            fwd_btn.when_pressed = fwd_cmd.as_action()
        if rev_btn is not None:
            rev_btn.when_pressed = rev_cmd.as_action()
        # return objects
        return speed_ctrl, fwd_btn, rev_btn

    @classmethod
    def when_button_pressed(
        cls,
        pin: P,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        led_pin: P = None,
        cathode: bool = True,
    ) -> Tuple[CommandReq, Button, LED]:
        # Use helper method to construct objects
        command, button, led = cls.make_button(
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
        pin: P,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        frequency: float = 1,
        led_pin: P = None,
        cathode: bool = True,
    ) -> Button:
        # Use helper method to construct objects
        command, button, led = cls.make_button(
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
    def when_button_pressed_or_held_action(
        cls,
        pressed_action,
        held_action,
        held_threshold,
        held_repeat: bool = False,
        frequency: float = 0.1,
        data_gen: Callable = None,
    ) -> Callable:
        def func(btn: Button) -> None:
            # sleep for hold threshold, if button still active, do held_action
            # otherwise do pressed_action
            trigger_effects = True
            time.sleep(held_threshold)
            if btn.is_active is True:
                while btn.is_active:
                    if data_gen is not None:
                        held_action(new_data=data_gen(btn), trigger_effects=trigger_effects)
                    else:
                        held_action(trigger_effects=trigger_effects)
                    # if held_repeat is true, continue sending when_held action
                    # with the given frequency of repeat
                    if held_repeat is True:
                        time.sleep(frequency)
                        trigger_effects = False
                    else:
                        break
            else:
                pressed_action()

        return func

    @classmethod
    def when_toggle_switch(
        cls,
        off_pin: P,
        on_pin: P,
        off_command: CommandReq,
        on_command: CommandReq,
        led_pin: P = None,
        cathode: bool = True,
    ) -> Tuple[Button, Button, LED]:
        # create a LED, if requested. It is turned on by pressing the
        # ON button, and turned off by pressing the OFF button
        if led_pin is not None and led_pin != 0:
            led = cls.make_led(led_pin, cathode=cathode)
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
        pin: P,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        led_pin: P = None,
        initial_state: bool = False,
        auto_timeout: int = None,
        cathode: bool = True,
    ) -> tuple[Button, LED]:
        # Use helper method to construct objects
        command, button, led = cls.make_button(
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
        pin_1: P,
        pin_2: P,
        clockwise_cmd: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = None,
        scope: CommandScope = None,
        initial_step=None,
        counterclockwise_cmd: CommandReq | CommandDefEnum = None,
        cc_data: int = None,
        max_steps: int = 100,
        ramp: Dict[int, int] = None,
        prefix: CommandReq = None,
        scaler: Callable[[int], int] = None,
        use_steps: bool = False,
        wrap: bool = True,
    ) -> RotaryEncoder:
        print(f"Init Steps: {initial_step} max_steps: {max_steps}")
        re = RotaryEncoder(pin_1, pin_2, wrap=wrap, max_steps=max_steps)
        if initial_step is not None:
            re.steps = initial_step
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
            scaler=scaler,
            re=re if use_steps else None,
        )
        re.when_rotated_counter_clockwise = cls._with_re_action(
            clockwise_cmd.address,
            counterclockwise_cmd,
            ramp,
            prefix if prefix else None,
            scaler=scaler,
            re=re if use_steps else None,
        )
        # return rotary encoder
        return re

    @classmethod
    def reset_all(cls) -> None:
        for handler in cls.GPIO_HANDLER_CACHE:
            handler.reset()
            if isinstance(handler, Thread) and handler.is_alive():
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
    def make_button(
        cls,
        pin: P,
        command: CommandReq | CommandDefEnum = None,
        address: int = DEFAULT_ADDRESS,
        data: int = None,
        scope: CommandScope = None,
        led_pin: P = None,
        hold_repeat: bool = False,
        hold_time: float = 1,
        initially_on: bool = False,
        bind: bool = False,
        cathode: bool = True,
    ) -> Button | Tuple[CommandReq, Button, LED]:
        # if command is actually a CommandDefEnum, build_req a CommandReq
        if isinstance(command, CommandDefEnum):
            command = CommandReq.build(command, address=address, data=data, scope=scope)

        # create the button object we will associate an action with
        hold_time = hold_time if hold_time is not None and hold_time > 0 else 1.0
        if isinstance(pin, tuple):
            # noinspection PyTypeChecker
            button = ButtonI2C(pin, bounce_time=DEFAULT_BOUNCE_TIME, hold_repeat=hold_repeat, hold_time=hold_time)
        else:
            button = Button(pin, bounce_time=DEFAULT_BOUNCE_TIME, hold_repeat=hold_repeat, hold_time=hold_time)
        cls.cache_device(button)

        # create a LED, if asked, and tie its source to the button
        if led_pin is not None:
            led = cls.make_led(led_pin, initially_on, cathode)
        else:
            led = None

        if led:
            cls.cache_device(led)
            if bind is True:
                led.source = button

        if command is None:
            return button
        else:
            return command, button, led

    @classmethod
    def make_led(
        cls,
        pin: P,
        initially_on: bool = False,
        cathode: bool = True,
    ) -> LED:
        if isinstance(pin, tuple):
            # noinspection PyTypeChecker
            led = LEDI2C(pin, cathode=cathode, initial_value=initially_on)
        else:
            led = LED(pin, active_high=cathode, initial_value=initially_on)
        return led

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
                    if impacted_led is not None:
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
        scaler: Callable[[int], int] = None,
        re: RotaryEncoder = None,
    ) -> Callable:
        tmcc_command_buffer = CommBuffer.build()
        last_rotation_at = cls.current_milli_time()
        last_steps = None

        def func() -> None:
            nonlocal last_rotation_at
            nonlocal tmcc_command_buffer
            nonlocal last_steps
            nonlocal cc
            last_rotated = cls.current_milli_time() - last_rotation_at
            if re:
                data = re.steps
                if last_steps is not None:
                    cc = data >= last_steps
                last_steps = data
            else:
                data = 1 if cc is False else -1
            adj = 0
            if ramp:
                for ramp_val, data_val in ramp.items():
                    if last_rotated <= ramp_val:
                        adj = data_val if cc is False else -data_val
                        break
            # apply adjustment
            if re:
                data += adj
            else:
                data = adj
            byte_str = bytes()
            if prefix:
                if GpioHandler.engine_numeric(address) == prefix.data:
                    pass
                else:
                    byte_str += prefix.as_bytes * 2
            if scaler:
                print(f"Steps: {data} New speed: {scaler(data)}")
                data = scaler(data)
            command.data = data
            byte_str += command.as_bytes * 2
            tmcc_command_buffer.enqueue_command(byte_str)
            last_rotation_at = cls.current_milli_time()

        return func
