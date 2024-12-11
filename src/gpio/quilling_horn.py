from threading import Thread, Event, Condition
from time import sleep

from src.gpio.ads_1x15 import Ads1115
from src.gpio.gpio_handler import GpioHandler
from src.protocol.command_req import CommandReq
from src.protocol.constants import CommandScope, PROGRAM_NAME, DEFAULT_ADDRESS
from src.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef


class QuillingHorn(Thread):
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
        self._address = address if address and address > 0 else DEFAULT_ADDRESS
        self._scope = scope if scope and scope in {CommandScope.ENGINE, CommandScope.TRAIN} else CommandScope.ENGINE
        self._repeat = repeat if repeat >= 1 else 1
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Quilling Horn Handler {self.scope.label} {self.address}")
        self._adc = Ads1115(channel=channel, address=i2c_address, continuous=False)
        self._cmd = CommandReq(TMCC2EngineCommandDef.QUILLING_HORN, address=address, scope=scope)
        self._action = self._cmd.as_action(repeat=self._repeat)
        self._is_running = True
        self._ev = Event()
        self._cv = Condition()
        self._interp = GpioHandler.make_interpolator(17, 0, 0.0, 3.3)
        self.start()
        if address != 99:
            self.resume()
        GpioHandler.cache_handler(self)

    @property
    def address(self) -> int:
        return self._address

    @property
    def scope(self) -> CommandScope:
        return self._scope

    def update_action(self, address: int, scope: CommandScope = CommandScope.ENGINE) -> None:
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

    def run(self) -> None:
        while self._is_running:
            self._ev.wait()
            if self._is_running:
                value = self._adc.request()
                data = self._interp(value)
                if data > 2:
                    print(f"Data: {data}  Value: {value}")
                    self._action(new_data=data - 2)
                sleep(0.1)
        print("Exiting ", self)

    def reset(self) -> None:
        self._is_running = False
        self._ev.set()
        self._adc.close()
