from threading import Thread, Event
from time import sleep

from src.gpio.i2c.ads_1x15 import Ads1115
from src.gpio.gpio_handler import GpioHandler
from src.protocol.command_req import CommandReq
from src.protocol.constants import CommandScope, PROGRAM_NAME, DEFAULT_ADDRESS
from src.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef


class AnalogHandler(Thread):
    def __init__(
        self,
        cmd: CommandReq,
        channel: int = 0,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
        repeat: int = 2,
        ignore=0,
        min_data: int = 0,
        max_data: int = None,
        send_all: bool = True,
        pause_for: float = 0.20,
        i2c_address: int = 0x48,
    ) -> None:
        self._cmd = cmd
        self._address = address if address and address > 0 else DEFAULT_ADDRESS
        self._scope = scope if scope and scope in {CommandScope.ENGINE, CommandScope.TRAIN} else CommandScope.ENGINE
        self._repeat = repeat if repeat >= 1 else 1
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Analog Handler {self.scope.label} {self.address}")
        self._adc = Ads1115(channel=channel, address=i2c_address, gain=Ads1115.PGA_4_096V, continuous=False)
        self._action = self._cmd.as_action(repeat=self._repeat)
        self._ev = Event()
        self._ignore = ignore if ignore is not None and ignore >= 0 else 0
        self._interp = GpioHandler.make_interpolator(max_data, min_data, 0.0, 3.3)
        self._send_all = send_all
        self._pause_for = pause_for if pause_for is not None and pause_for > 0 else 0.20
        self._last_value = None
        self._is_running = True
        self.start()
        GpioHandler.cache_handler(self)
        if address != 99:
            self.resume()

    @property
    def address(self) -> int:
        return self._address

    @property
    def scope(self) -> CommandScope:
        return self._scope

    def update_action(self, address: int, scope: CommandScope = CommandScope.ENGINE) -> None:
        if self._is_running:
            self._address = address if address and address > 0 else DEFAULT_ADDRESS
            self._scope = scope if scope and scope in {CommandScope.ENGINE, CommandScope.TRAIN} else CommandScope.ENGINE
            self._cmd.address = address
            self._cmd.scope = scope
            self._action = self._cmd.as_action(repeat=self._repeat)
            if address != 99:
                self.resume()
            else:
                self.pause()

    def pause(self) -> None:
        self._ev.clear()

    def resume(self) -> None:
        if self.address and self.address > 0 and self._address != DEFAULT_ADDRESS:
            self._ev.set()

    @property
    def is_active(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return not self._ev.is_set()

    def run(self) -> None:
        while self._is_running:
            self._ev.wait()
            if self._is_running:
                value = self._adc.request()
                data = self._interp(value)
                if data > self._ignore:
                    new_value = data - self._ignore
                    print(f"Scaled: {data} - {self._ignore}: {new_value}")
                    if new_value != self._last_value or self._send_all is True or new_value == 0:
                        self._action(new_data=data - self._ignore)
                        self._last_value = new_value
                sleep(self._pause_for)

    def reset(self) -> None:
        self._is_running = False
        self._ev.set()


class QuillingHorn(AnalogHandler):
    """
    Send TMCC2 Commands for the Quilling Horn Effect supported by Legacy engines.
    This class uses the TI Ads 1115 ADC converter connected to a 3.3V source (not 5.0V).
    """

    def __init__(
        self,
        channel: int = 0,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
        repeat: int = 2,
        i2c_address: int = 0x48,
    ) -> None:
        cmd = CommandReq(TMCC2EngineCommandDef.QUILLING_HORN, address=address, scope=scope)
        super().__init__(
            cmd,
            channel=channel,
            address=address,
            scope=scope,
            repeat=repeat,
            ignore=2,
            max_data=17,
            i2c_address=i2c_address,
        )


class TrainBrake(AnalogHandler):
    """
    Send TMCC2 Commands for the Train Brake supported by Legacy engines.
    This class uses the TI Ads 1115 ADC converter connected to a 3.3V source (not 5.0V).
    """

    def __init__(
        self,
        channel: int = 1,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
        repeat: int = 2,
        i2c_address: int = 0x48,
    ) -> None:
        cmd = CommandReq(TMCC2EngineCommandDef.TRAIN_BRAKE, address=address, scope=scope)
        super().__init__(
            cmd,
            channel=channel,
            address=address,
            scope=scope,
            repeat=repeat,
            ignore=1,
            max_data=8,
            send_all=False,  # only send changes
            i2c_address=i2c_address,
        )
