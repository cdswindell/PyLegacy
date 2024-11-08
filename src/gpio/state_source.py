import abc
from abc import ABC
from threading import Thread
from typing import TypeVar

from gpiozero import LED

from ..db.component_state import ComponentState
from ..db.component_state_store import ComponentStateStore
from ..protocol.command_def import CommandDefEnum
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchState, TMCC1AuxCommandDef

T = TypeVar("T", bound=ComponentState)


# noinspection PyUnresolvedReferences
class StateSource(ABC, Thread):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope, address: int, led: LED) -> None:
        super().__init__(daemon=True, name=f"{scope.friendly} {address} State")
        self._scope = scope
        self._address = address
        self._led = led
        self._component: T = ComponentStateStore.build().component(scope, address)
        self._is_running = True
        self.start()

    def reset(self) -> None:
        self._is_running = False

    def run(self) -> None:
        while self._is_running:
            if self._component.changed.wait(1) is True:
                self._led.value = 1 if self.is_active else 0
                self._component.changed.clear()

    @property
    @abc.abstractmethod
    def is_active(self) -> bool: ...


class SwitchStateSource(StateSource):
    def __init__(self, address: int, led: LED, state: TMCC1SwitchState) -> None:
        self._state = state
        super().__init__(CommandScope.SWITCH, address, led)

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
        aux_state: TMCC1AuxCommandDef = None,
        aux1_state: TMCC1AuxCommandDef = None,
        aux2_state: TMCC1AuxCommandDef = None,
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
        command: CommandDefEnum = None,
        data: int = None,
        scope: CommandScope = CommandScope.ENGINE,
        getter: str = None,
    ) -> None:
        self._command = command
        self._data = data
        self._scope = scope
        self._getter = getter
        super().__init__(scope, address, led)

    def __iter__(self):
        return self

    def __next__(self):
        return self.is_active

    @property
    def is_active(self) -> bool:
        if self._getter and hasattr(self._component, self._getter):
            return self._data == getattr(self._component, self._getter)
        return False
