import logging
import math
import sched
import threading
import time
from threading import Thread
from typing import Callable, Dict, Tuple, TypeVar, Union

from gpiozero import LED, MCP3008, MCP3208, AnalogInputDevice, Button, Device

from ..comm.comm_buffer import CommBuffer
from ..comm.command_listener import Message
from ..db.component_state_store import DependencyCache
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import DEFAULT_ADDRESS, PROGRAM_NAME, CommandScope
from ..protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
)
from .i2c.ads_1x15 import Ads1115
from .i2c.button_i2c import ButtonI2C
from .i2c.led_i2c import LEDI2C

log = logging.getLogger(__name__)

DEFAULT_BOUNCE_TIME: float = 0.015  # button debounce threshold
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
            # run the scheduler outside the cv lock; otherwise,
            # we couldn't schedule more commands
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
        if use_12bit:
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
        if start:
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
                    if cmd.is_data:
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
        elif use_12bit:
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

        aux1_btn.when_pressed = cls.with_held_action(aux1_action, aux1_btn)
        aux2_btn.when_pressed = aux2_action

        if aux2_led is None:
            return aux1_btn, aux2_btn
        else:
            return aux1_btn, aux2_btn, aux1_led

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
            cls.cache_device(led)
            if bind:
                led.source = button
        else:
            led = None

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
                    if held_repeat:
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
        # Create a LED, if requested. It is turned on by pressing the
        # ON button, and turned off by pressing the OFF button
        if led_pin is not None and led_pin != 0:
            # noinspection PyTypeChecker
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
            off_button.when_pressed = cls.with_off_action(off_action, led)
            on_button.when_pressed = cls.with_on_action(on_action, led)

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
            button.when_pressed = cls.with_toggle_action(action, led, auto_timeout)
            led.source = None  # want led to stay lit when button pressed
            if initial_state:
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
    def reset_all(cls) -> None:
        for handler in cls.GPIO_HANDLER_CACHE:
            if not hasattr(handler, "reset"):
                log.error(f"{handler} has no 'reset' method. Skipping...")
                continue
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
    def with_held_action(cls, action: Callable, button: Button, delay: float = 0.10) -> Callable:
        def held_action() -> None:
            while button.is_active:
                action()
                time.sleep(delay)

        return held_action

    @classmethod
    def with_toggle_action(cls, action: Callable, led: LED, auto_timeout: int = None) -> Callable:
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
    def with_off_action(cls, action: Callable, led: LED = None, *impacted_leds: LED) -> Callable:
        def off_action() -> None:
            action()
            if led is not None:
                led.off()
            if impacted_leds:
                for impacted_led in impacted_leds:
                    impacted_led.on()

        return off_action

    @classmethod
    def with_on_action(cls, action: Callable, led: LED, *impacted_leds: LED) -> Callable:
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
    def with_prefix_action(
        cls,
        prefix: CommandReq,
        command: CommandReq,
    ) -> Callable:
        def func() -> None:
            if prefix:
                prefix.send(repeat=2)
            command.send()

        return func
