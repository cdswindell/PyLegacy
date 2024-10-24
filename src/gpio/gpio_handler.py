import math
import time
from threading import Thread
from typing import Tuple, Callable, Dict

from gpiozero import Button, LED, MCP3008, Device

from ..comm.command_listener import Message
from ..db.component_state_store import DependencyCache
from ..gpio.state_source import SwitchStateSource, AccessoryStateSource
from ..protocol.command_req import CommandReq
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from ..protocol.command_def import CommandDefEnum
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchState, TMCC1AuxCommandDef, TMCC1EngineCommandDef
from ..protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandDef, TMCC2EngineCommandDef

DEFAULT_BOUNCE_TIME: float = 0.05  # button debounce threshold
DEFAULT_VARIANCE: float = 0.001  # pot difference variance


class PotHandler(Thread):
    def __init__(
        self,
        command: CommandReq,
        channel: int = 0,
        data_min: int = None,
        data_max: int = None,
        threshold: float = None,
        delay: float = 0.05,
        baudrate: int = DEFAULT_BAUDRATE,
        port: int | str = DEFAULT_PORT,
        server: str = None,
        scale: Dict[int, int] = None,
        start: bool = True,
    ) -> None:
        super().__init__(daemon=True)
        self._pot = MCP3008(channel=channel)
        self._command = command
        self._last_value = None
        self._action = command.as_action(baudrate=baudrate, port=port, server=server)
        if data_max is None:
            data_max = command.data_max
        if data_min is None:
            data_min = command.data_min
        self._interp = self.make_interpolator(data_max, data_min)
        if threshold is not None:
            self._threshold = threshold
        else:
            self._threshold = 1 if command.num_data_bits < 6 else 2
        self._delay = delay
        self._running = True
        self._scale = scale
        if start is True:
            self.start()

    @property
    def pot(self) -> MCP3008:
        return self._pot

    def run(self) -> None:
        while self._running:
            value = self._interp(self.pot.value)
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
            self._command.data = value
            self._action(new_data=value)
            time.sleep(self._delay)

    def reset(self) -> None:
        self._running = False

    @staticmethod
    def make_interpolator(to_max: int, to_min: int = 0, from_min: float = 0.0, from_max: float = 1.0) -> Callable:
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
        command: CommandReq,
        channel: int = 0,
        data_min: int = None,
        data_max: int = None,
        delay: float = 0.05,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
        scale: Dict[int, int] = None,
    ) -> None:
        super().__init__(
            command,
            channel=channel,
            data_min=data_min,
            data_max=data_max,
            threshold=None,
            delay=delay,
            baudrate=baudrate,
            port=port,
            server=server,
            start=False,
            scale=scale,
        )
        self._threshold = None
        self.start()


class GpioHandler:
    GPIO_DEVICE_CACHE = set()
    GPIO_HANDLER_CACHE = set()

    @classmethod
    def route(
        cls,
        address: int,
        btn_pin: int,
        led_pin: int | str = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> Button | Tuple[Button, LED]:
        """
        Fire a TMCC2/Legacy Route, throwing all incorporated turnouts to the correct state
        """
        # make the CommandReq
        req, btn, led = cls._make_button(btn_pin, TMCC2RouteCommandDef.FIRE, address, led_pin=led_pin, bind=True)
        # bind actions to buttons
        btn.when_pressed = req.as_action(repeat=3, baudrate=baudrate, port=port, server=server)

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
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
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
        thru_action = thru_req.as_action(repeat=3, baudrate=baudrate, port=port, server=server)
        out_action = out_req.as_action(repeat=3, baudrate=baudrate, port=port, server=server)

        thru_btn.when_pressed = cls._with_on_action(thru_action, thru_led, out_led)
        out_btn.when_pressed = cls._with_on_action(out_action, out_led, thru_led)

        if thru_led is not None and out_led is not None:
            cls._cache_handler(SwitchStateSource(address, thru_led, TMCC1SwitchState.THROUGH))
            cls._cache_handler(SwitchStateSource(address, out_led, TMCC1SwitchState.OUT))
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
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
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
            initially_on=initial_state == TMCC1AuxCommandDef.AUX2_OPT_ONE,
        )
        # bind actions to buttons
        on_action = on_req.as_action(repeat=3, baudrate=baudrate, port=port, server=server)
        off_action = off_req.as_action(repeat=3, baudrate=baudrate, port=port, server=server)

        on_btn.when_pressed = cls._with_on_action(on_action, on_led)
        off_btn.when_pressed = cls._with_off_action(off_action, on_led)

        if on_led is None:
            # return created objects
            return on_btn, off_btn
        else:
            # listen for external state changes
            cls._cache_handler(AccessoryStateSource(address, on_led, aux_state=TMCC1AuxCommandDef.AUX1_OPT_ONE))
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
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> Tuple[Button, Button] | Tuple[Button, Button, LED]:
        """
        Control an accessory that responds to TMCC1 accessory commands, such as one connected
        to an LCS ASC2 configured in accessory, 8 TMCC IDs mode.

        Press and hold the Aux1 button to operate the accessory for as long as Aux1 is held.
        Press the Aux2 button to turn the accessory on or off.
        """
        # make the CommandReqs
        aux1_req, aux1_btn, aux1_led = cls._make_button(
            aux1_pin, TMCC1AuxCommandDef.AUX1_OPT_ONE, address, led_pin=aux1_led_pin, cathode=cathode, bind=True
        )
        aux2_req, aux2_btn, aux2_led = cls._make_button(aux2_pin, TMCC1AuxCommandDef.AUX2_OPT_ONE, address)
        # bind actions to buttons
        aux1_action = aux1_req.as_action(baudrate=baudrate, port=port, server=server)
        aux2_action = aux2_req.as_action(repeat=3, baudrate=baudrate, port=port, server=server)

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
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> Button | Tuple[Button, LED]:
        if command_control is True:
            cycle_req, cycle_btn, cycle_led = cls._make_button(
                cycle_pin, TMCC1AuxCommandDef.AUX2_OPT_ONE, address, led_pin=cycle_led_pin, cathode=cathode
            )
            cycle_btn.when_pressed = cycle_req.as_action(repeat=3, baudrate=baudrate, port=port, server=server)
        else:
            raise NotImplementedError
        if cycle_led is None:
            return cycle_btn
        else:
            cls._cache_handler(AccessoryStateSource(address, cycle_led, aux2_state=TMCC1AuxCommandDef.AUX2_ON))
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
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
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
                baudrate=baudrate,
                port=port,
                server=server,
                scale=scale,
            )
            cls._cache_handler(knob)
            cls._cache_device(knob.pot)

            lights_on_req, lights_on_btn, lights_on_led = cls._make_button(
                lights_on_pin, TMCC1AuxCommandDef.NUMERIC, address, data=9
            )
            lights_off_req, lights_off_btn, lights_off_led = cls._make_button(
                lights_off_pin, TMCC1AuxCommandDef.NUMERIC, address, data=8
            )
            dispense_req, dispense_btn, dispense_led = cls._make_button(dispense_pin, TMCC1AuxCommandDef.BRAKE, address)
            dispense_btn.when_pressed = dispense_req.as_action(repeat=2, baudrate=baudrate, port=port, server=server)
            lights_on_btn.when_pressed = lights_on_req.as_action(repeat=2, baudrate=baudrate, port=port, server=server)
            lights_off_btn.when_pressed = lights_off_req.as_action(
                repeat=2, baudrate=baudrate, port=port, server=server
            )
        else:
            raise NotImplementedError
        return lights_on_btn, lights_off_btn

    @classmethod
    def gantry_crane(
        cls,
        address: int,
        cab_pin_1: int | str,
        cab_pin_2: int | str,
        roll_chn: int,
        lift_chn: int,
        mag_pin: int | str,
        mag_led_pin: int | str = None,
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
        scope: CommandScope = CommandScope.ENGINE,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> Tuple[PotHandler, Button, Button]:
        fwd_btn = rev_btn = None
        fwd_cmd = rev_cmd = None
        if is_legacy is True:
            speed_cmd = CommandReq.build(TMCC2EngineCommandDef.ABSOLUTE_SPEED, address, 0, scope)
            if fwd_pin is not None:
                fwd_cmd, fwd_btn, _ = cls._make_button(
                    fwd_pin, TMCC2EngineCommandDef.FORWARD_DIRECTION, address, 0, scope
                )
            if rev_pin is not None:
                rev_cmd, rev_btn, _ = cls._make_button(
                    rev_pin, TMCC2EngineCommandDef.REVERSE_DIRECTION, address, 0, scope
                )
        else:
            speed_cmd = CommandReq.build(TMCC1EngineCommandDef.ABSOLUTE_SPEED, address, 0, scope)
            if fwd_pin is not None:
                fwd_cmd, fwd_btn, _ = cls._make_button(
                    fwd_pin, TMCC1EngineCommandDef.FORWARD_DIRECTION, address, 0, scope
                )
            if rev_pin is not None:
                rev_cmd, rev_btn, _ = cls._make_button(
                    rev_pin, TMCC1EngineCommandDef.REVERSE_DIRECTION, address, 0, scope
                )
        # make a pot to handle speed
        pot = cls.when_pot(speed_cmd, channel=channel)

        # assign button actions
        if fwd_btn is not None:
            fwd_btn.when_pressed = fwd_cmd.as_action(baudrate=baudrate, port=port, server=server)
        if rev_btn is not None:
            rev_btn.when_pressed = rev_cmd.as_action(baudrate=baudrate, port=port, server=server)
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
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> Button:
        # Use helper method to construct objects
        command, button, led = cls._make_button(pin, command, address, data, scope, led_pin)

        # create a command function to fire when button pressed
        button.when_pressed = command.as_action(baudrate=baudrate, port=port, server=server)
        return button

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
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> Button:
        # Use helper method to construct objects
        command, button, led = cls._make_button(pin, command, address, data, scope, led_pin)

        # create a command function to fire when button held
        button.when_held = command.as_action(baudrate=baudrate, port=port, server=server)
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
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> Tuple[Button, Button, LED]:
        # create a LED, if requested. It is turned on by pressing the
        # ON button, and turned off by pressing the OFF button
        if led_pin is not None and led_pin != 0:
            led = LED(led_pin)
            led.on()
        else:
            led = None

        # create the off and on buttons
        off_button = Button(off_pin, bounce_time=DEFAULT_BOUNCE_TIME)
        on_button = Button(on_pin, bounce_time=DEFAULT_BOUNCE_TIME)

        # bind them to functions; we need to wrap the functions if we're using a LED
        off_action = off_command.as_action(baudrate=baudrate, port=port, server=server)
        on_action = on_command.as_action(baudrate=baudrate, port=port, server=server)
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

        cls._cache_device(off_button)
        cls._cache_device(on_button)
        if led is not None:
            cls._cache_device(led)
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
        initial_state: bool = False,  # off
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> Button | tuple[Button, LED]:
        # Use helper method to construct objects
        command, button, led = cls._make_button(pin, command, address, data, scope, led_pin)

        # create a command function to fire when button pressed
        action = command.as_action(baudrate=baudrate, port=port, server=server)
        if led_pin is not None and led_pin != 0:
            button.when_pressed = cls._with_toggle_action(action, led)
            led.source = None  # want led to stay lit when button pressed
            if initial_state:
                led.on()
            else:
                led.off()
            return button, led
        else:
            button.when_pressed = action
            return button

    @classmethod
    def when_pot(
        cls,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = None,
        channel: int = 0,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str | int = DEFAULT_PORT,
        server: str = None,
    ) -> PotHandler:
        if isinstance(command, CommandDefEnum):
            command = CommandReq.build(command, address, 0, scope)
        if command.num_data_bits == 0:
            raise ValueError("Command does not support variable data")
        knob = PotHandler(command, channel, baudrate=baudrate, port=port, server=server)
        cls._cache_handler(knob)
        cls._cache_device(knob.pot)
        return knob

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
    def _cache_handler(cls, handler: Thread) -> None:
        cls.GPIO_HANDLER_CACHE.add(handler)

    @classmethod
    def release_device(cls, device: Device) -> None:
        cls._release_device(device)

    @classmethod
    def _cache_device(cls, device: Device) -> None:
        """
        Keep devices around after creation so they remain in scope
        """
        cls.GPIO_DEVICE_CACHE.add(device)

    @classmethod
    def _release_device(cls, device: Device) -> None:
        device.close()
        cls.GPIO_DEVICE_CACHE.remove(device)

    @classmethod
    def _make_button(
        cls,
        pin: int | str,
        command: CommandReq | CommandDefEnum | CommandDefEnum,
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
        cls._cache_device(button)

        # create a LED, if asked, and tie its source to the button
        if led_pin is not None and led_pin != 0:
            led = LED(led_pin, active_high=cathode, initial_value=initially_on)
            led.source = None
            if bind:
                led.source = button
            cls._cache_device(led)
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
    def _with_toggle_action(cls, action: Callable, led: LED) -> Callable:
        def toggle_action() -> None:
            action()
            if led.value:
                led.off()
            else:
                led.on()

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
    def _create_listeners(cls, req, active_led: LED = None, *inactive_leds: LED) -> None:
        def func_on(msg: Message) -> None:
            if msg.address == req.address:
                if active_led is not None:
                    active_led.on()
                for led in inactive_leds:
                    led.off()

        def func_off(msg: Message) -> None:
            if msg.address == req.address:
                if active_led is not None:
                    active_led.off()
                for led in inactive_leds:
                    led.on()

        DependencyCache.listen_for_enablers(req, func_on)
        DependencyCache.listen_for_disablers(req, func_off)
