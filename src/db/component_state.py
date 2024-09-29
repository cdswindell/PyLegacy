from __future__ import annotations

import abc
from abc import ABC
from collections import defaultdict
from datetime import datetime
from typing import Tuple

from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, BROADCAST_ADDRESS
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchState as Switch, TMCC1HaltCommandDef
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandDef as Aux


class ComponentState(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        self._scope = scope
        self._last_command: CommandReq | None = None
        self._last_updated: datetime | None = None
        self._address: int | None = None

    def __repr__(self) -> str:
        return f"{self.scope.name} {self._address}"

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def address(self) -> int:
        return self._address

    @property
    def last_command(self) -> CommandReq:
        return self._last_command

    @property
    def last_updated(self) -> datetime:
        return self._last_updated

    @abc.abstractmethod
    def update(self, command: CommandReq) -> None:
        if command and command.command != TMCC1HaltCommandDef.HALT:
            if self._address is None and command.address != BROADCAST_ADDRESS:
                self._address = command.address
            elif self._address not in [command.address, BROADCAST_ADDRESS]:  # invalid state
                raise ValueError(f"Switch #{self._address} received update for Switch #{command.address}, ignoring")
            if self.scope != command.scope:
                scope = command.scope.name.capitalize()
                raise ValueError(f"Switch {self.address} received update for {scope}, ignoring")
            self._last_updated = datetime.now()
            self._last_command = command


class SwitchState(ComponentState):
    """
        Maintain the perceived state of a Switch
    """
    def __init__(self, scope: CommandScope = CommandScope.SWITCH) -> None:
        if scope != CommandScope.SWITCH:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._state: Switch | None = None

    def __repr__(self) -> str:
        return f"Switch {self.address}: {self._state.name if self._state is not None else 'Unknown'}"

    def update(self, command: CommandReq) -> None:
        if command:
            super().update(command)
            if command.command == TMCC1HaltCommandDef.HALT:
                return  # do nothing on halt
            if command.command != Switch.SET_ADDRESS:
                self._state = command.command

    @property
    def state(self) -> Switch:
        return self._state

    @property
    def is_known(self) -> bool:
        return self._state is not None

    @property
    def is_through(self) -> bool:
        return self._state == Switch.THROUGH

    @property
    def is_out(self) -> bool:
        return self._state == Switch.OUT


class AccessoryState(ComponentState):
    def __init__(self, scope: CommandScope = CommandScope.ACC) -> None:
        if scope != CommandScope.ACC:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._aux1_state: Aux | None = None
        self._aux2_state: Aux | None = None
        self._aux_state: Aux | None = None
        self._number: int | None = None

    def __repr__(self) -> str:
        if self.aux_state == Aux.AUX1_OPTION_ONE:
            aux = "Aux 1"
        elif self.aux_state == Aux.AUX2_OPTION_ONE:
            aux = "Aux 2"
        else:
            aux = "Unknown"
        aux1 = self.aux1_state.name if self.aux1_state is not None else 'Unknown'
        aux2 = self.aux2_state.name if self.aux2_state is not None else 'Unknown'
        return f"Accessory {self.address}: {aux}; {aux1}; {aux2} {self._number}"

    def update(self, command: CommandReq) -> None:
        if command:
            super().update(command)
            if command.command != Aux.SET_ADDRESS:
                if command.command == TMCC1HaltCommandDef.HALT:
                    self._aux1_state = Aux.AUX1_OFF
                    self._aux2_state = Aux.AUX2_OFF
                    self._aux_state = Aux.AUX2_OPTION_ONE
                    self._number = None
                else:
                    if command.command in [Aux.AUX1_OPTION_ONE, Aux.AUX2_OPTION_ONE]:
                        self._aux_state = command.command
                    if command.command in [Aux.AUX1_OPTION_ONE, Aux.AUX1_ON, Aux.AUX1_OFF, Aux.AUX1_OPTION_TWO]:
                        self._aux1_state = command.command
                    elif command.command in [Aux.AUX2_OPTION_ONE, Aux.AUX2_ON, Aux.AUX2_OFF, Aux.AUX2_OPTION_TWO]:
                        self._aux2_state = command.command
                    if command.command == Aux.NUMERIC:
                        self._number = command.data

    @property
    def is_known(self) -> bool:
        return (self._aux_state is not None
                or self._aux1_state is not None
                or self._aux2_state is not None
                or self._number is not None)

    @property
    def aux_state(self) -> Aux:
        return self._aux_state

    @property
    def is_aux_on(self) -> bool:
        return self._aux_state == Aux.AUX1_OPTION_ONE

    @property
    def is_aux_off(self) -> bool:
        return self._aux_state == Aux.AUX2_OPTION_ONE

    @property
    def aux1_state(self) -> Aux:
        return self._aux1_state

    @property
    def aux2_state(self) -> Aux:
        return self._aux2_state

    @property
    def value(self) -> int:
        return self._number


class EngineState(ComponentState):
    def __init__(self, scope: CommandScope = CommandScope.ENGINE) -> None:
        if scope not in [CommandScope.ENGINE, CommandScope.TRAIN]:
            raise ValueError(f"Invalid scope: {scope}, expected ENGINE or TRAIN")
        super().__init__(scope)
        self._number: int | None = None
        self._started = None
        self._speed: int | None = None

    def update(self, command: CommandReq) -> None:
        if command:
            super().update(command)


class TrainState(EngineState):
    def __init__(self, scope: CommandScope = CommandScope.TRAIN) -> None:
        if scope not in [CommandScope.TRAIN]:
            raise ValueError(f"Invalid scope: {scope}, expected TRAIN")
        super().__init__(scope)


SCOPE_TO_STATE_MAP: [CommandScope, ComponentState] = {
    CommandScope.SWITCH: SwitchState,
    CommandScope.ACC: AccessoryState,
    CommandScope.ENGINE: EngineState,
    CommandScope.TRAIN: TrainState,
}


class SystemStateDict(defaultdict):
    """
        Maintains a dictionary of CommandScope to ComponentStateDict
    """
    def __missing__(self, key: CommandScope | Tuple[CommandScope, int]) -> ComponentStateDict:
        """
            generate a ComponentState object for the dictionary, based on the key
        """
        if isinstance(key, CommandScope) and key in SCOPE_TO_STATE_MAP:
            scope = key
        else:
            raise KeyError(f"Invalid scope key: {key}")
        # create the component state dict for this key
        self[key] = ComponentStateDict(scope)
        return self[key]


class ComponentStateDict(defaultdict):
    def __init__(self, scope: CommandScope):
        super().__init__(None)  # base class doesn't get a factory
        if scope not in SCOPE_TO_STATE_MAP:
            raise ValueError(f"Invalid scope: {scope}")
        self._scope = scope

    @property
    def scope(self) -> CommandScope:
        return self._scope

    def __missing__(self, key: int) -> ComponentState:
        """
            generate a ComponentState object for the dictionary, based on the key
        """
        if not isinstance(key, int) or key < 1 or key > 99:
            raise KeyError(f"Invalid ID: {key}")
        value: ComponentState = SCOPE_TO_STATE_MAP[self._scope](self._scope)
        value._address = key
        self[key] = value
        return self[key]
