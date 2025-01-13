from abc import abstractmethod

from gpiozero import Device
from gpiozero.devices import GPIOMeta


class I2CDevice(Device):
    __metaclass__ = GPIOMeta

    def __init__(self, pin_factory=None) -> None:
        super().__init__(pin_factory=pin_factory)

    @abstractmethod
    def _signal_event(self, active: bool) -> None: ...

    @property
    @abstractmethod
    def bounce_time(self) -> float: ...
