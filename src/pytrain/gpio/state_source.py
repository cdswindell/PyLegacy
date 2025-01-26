from __future__ import annotations

import abc
from abc import ABC
from threading import Thread
from time import sleep
from typing import TypeVar, Protocol

from gpiozero import LED, PingServer

from ..db.component_state import ComponentState
from ..db.component_state_store import ComponentStateStore
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum, TMCC1AuxCommandEnum

T = TypeVar("T", bound=ComponentState)


class StateValidator(Protocol):
    def __call__(self, state: StateSource) -> bool: ...


# noinspection PyUnresolvedReferences
class StateSource(ABC, Thread):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope, address: int, active_led: LED, inactive_led: LED = None) -> None:
        super().__init__(daemon=True, name=f"{scope.label} {address} State")
        self._scope = scope
        self._address = address
        self.active_led = active_led
        self.inactive_led = inactive_led
        self._component: T = ComponentStateStore.build().component(scope, address)
        self._is_running = True
        self.start()

    def reset(self) -> None:
        self._is_running = False
        if self._component:
            with self._component.synchronizer:
                self._component.synchronizer.notify_all()

    def run(self) -> None:
        while self._is_running:
            with self._component.synchronizer:
                self._component.synchronizer.wait()
                if self._is_running:
                    self.active_led.value = 1 if self.is_active is True else 0
                    if self.inactive_led:
                        self.inactive_led.value = 0 if self.is_active is True else 1

    @property
    @abc.abstractmethod
    def is_active(self) -> bool: ...


class LionelBaseSource(StateSource):
    def __init__(
        self,
        server: str,
        led: LED,
        delay: float = 10,
    ) -> None:
        self._delay = delay
        self._pieces = server.split(".")
        if len(self._pieces) == 4:
            address = int(self._pieces[3])
        else:
            address = 99
        self._ping = PingServer(server, event_delay=delay)
        super().__init__(CommandScope.SYSTEM, address, led)

    def __iter__(self):
        return self

    def __next__(self):
        return self.is_active

    @property
    def is_active(self) -> bool:
        return self._ping.is_active

    def run(self) -> None:
        while self._is_running:
            self.active_led.value = 1 if self.is_active else 0
            sleep(self._delay)


class SwitchStateSource(StateSource):
    def __init__(self, address: int, thru_led: LED, out_led: LED) -> None:
        self._state = TMCC1SwitchCommandEnum.THRU
        super().__init__(CommandScope.SWITCH, address, thru_led, out_led)

    def __iter__(self):
        return self

    def __next__(self):
        return self.is_active

    @property
    def is_active(self) -> bool:
        return self._component.state == self._state


class AccessoryStateSource(StateSource):
    def __init__(
        self,
        address: int,
        led: LED,
        aux_state: TMCC1AuxCommandEnum = None,
        aux1_state: TMCC1AuxCommandEnum = None,
        aux2_state: TMCC1AuxCommandEnum = None,
    ) -> None:
        self._aux_state = aux_state
        self._aux1_state = aux1_state
        self._aux2_state = aux2_state
        super().__init__(CommandScope.ACC, address, led)

    def __iter__(self):
        return self

    def __next__(self):
        return self.is_active

    @property
    def is_active(self) -> bool:
        return (
            (self._aux_state is not None and self._component.aux_state == self._aux_state)
            or (self._aux1_state is not None and self._component.aux1_state == self._aux1_state)
            or (self._aux2_state is not None and self._component.aux2_state == self._aux2_state)
        )


class EngineStateSource(StateSource):
    def __init__(
        self,
        address: int,
        led: LED,
        func: StateValidator = None,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        self._func = func
        self._scope = scope
        super().__init__(scope, address, led)

    def __iter__(self):
        return self

    def __next__(self):
        return self.is_active

    @property
    def is_active(self) -> bool:
        return self._func(self._component) if self._func else False
