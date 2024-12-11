from threading import Thread, Event, Condition
from time import sleep

from src.gpio.ads_1x15 import Ads1115
from src.gpio.gpio_handler import GpioHandler
from src.protocol.command_req import CommandReq
from src.protocol.constants import CommandScope, PROGRAM_NAME
from src.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef


class QuillingHorn(Thread):
    """
    Send TMCC2 Commands for the Quilling Horn Effect supported by Legacy engines.
    This class uses the TI Ads 1115 ADC converter connected to a 3.3V source (not 5.0V).
    """

    def __init__(
        self,
        channel: int = 0,
        address: int = 1,
        scope: CommandScope = CommandScope.ENGINE,
        repeat: int = 2,
        i2c_address: int = 0x48,
    ) -> None:
        self._address = address if address and address > 0 else 1
        self._scope = scope if scope and scope in {CommandScope.ENGINE, CommandScope.TRAIN} else CommandScope.ENGINE
        self._repeat = repeat if repeat >= 1 else 1
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Quilling Horn Handler {self.scope.label}")
        self._adc = Ads1115(channel=channel, address=i2c_address)
        self._cmd = CommandReq(TMCC2EngineCommandDef.QUILLING_HORN, address=address, scope=scope)
        self._action = self._cmd.as_action(repeat=self._repeat)
        self._is_running = True
        self._ev = Event()
        self._cv = Condition()
        self._interp = GpioHandler.make_interpolator(17, 0, 0.0, 3.3)
        self.start()
        GpioHandler.cache_handler(self)

    @property
    def address(self) -> int:
        return self._address

    @property
    def scope(self) -> CommandScope:
        return self._scope

    def update_action(self, address: int, scope: CommandScope) -> None:
        self._address = address
        self._scope = scope
        self._cmd.address = address
        self._cmd.scope = scope
        self._action = self._cmd.as_action(repeat=self._repeat)
        self._ev.set()

    def pause(self) -> None:
        self._ev.clear()

    def resume(self) -> None:
        if self.address and self.address > 0:
            self._ev.set()

    def run(self) -> None:
        while self._is_running:
            self._ev.wait()
            if self._is_running:
                data = self._interp(self._adc.value)
                if data > 2:
                    self._action(new_data=data - 2)
                sleep(0.1)

    def reset(self) -> None:
        self._is_running = False
        self._ev.set()
