#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import abc
import logging
import threading
from abc import ABC
from collections import defaultdict
from threading import Condition, Event, Lock, RLock
from time import time
from typing import Any, Dict, List, Set, TypeVar

from ..pdi.asc2_req import Asc2Req
from ..pdi.constants import PdiCommand
from ..pdi.irda_req import IrdaReq
from ..pdi.pdi_req import PdiReq
from ..pdi.stm2_req import Stm2Req
from ..pdi.comp_data import CompDataMixin
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import (
    BROADCAST_ADDRESS,
    CommandScope,
    CommandSyntax,
)
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.tmcc1.tmcc1_constants import (
    TMCC1EngineCommandEnum,
    TMCC1HaltCommandEnum,
)
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum as Switch
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from ..utils.text_utils import title

log = logging.getLogger(__name__)

C = TypeVar("C", bound=CommandDefEnum)
E = TypeVar("E", bound=CommandDefEnum)
P = TypeVar("P", bound=PdiReq)
L = TypeVar("L", bound=CommandReq)


DIRECTIONS_SET = {
    TMCC1EngineCommandEnum.FORWARD_DIRECTION,
    TMCC2EngineCommandEnum.FORWARD_DIRECTION,
    TMCC1EngineCommandEnum.REVERSE_DIRECTION,
    TMCC2EngineCommandEnum.REVERSE_DIRECTION,
    TMCC1EngineCommandEnum.TOGGLE_DIRECTION,
    TMCC2EngineCommandEnum.TOGGLE_DIRECTION,
}

MOMENTUM_SET = {
    TMCC1EngineCommandEnum.MOMENTUM_LOW,
    TMCC1EngineCommandEnum.MOMENTUM_MEDIUM,
    TMCC1EngineCommandEnum.MOMENTUM_HIGH,
    TMCC2EngineCommandEnum.MOMENTUM_LOW,
    TMCC2EngineCommandEnum.MOMENTUM_MEDIUM,
    TMCC2EngineCommandEnum.MOMENTUM_HIGH,
    TMCC2EngineCommandEnum.MOMENTUM,
}

SPEED_SET = {
    TMCC1EngineCommandEnum.ABSOLUTE_SPEED,
    TMCC2EngineCommandEnum.ABSOLUTE_SPEED,
    (TMCC1EngineCommandEnum.ABSOLUTE_SPEED, 0),
    (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 0),
}

RPM_SET = {
    TMCC2EngineCommandEnum.DIESEL_RPM,
}

LABOR_SET = {
    TMCC2EngineCommandEnum.ENGINE_LABOR,
}

NUMERIC_SET = {
    TMCC1EngineCommandEnum.NUMERIC,
    TMCC2EngineCommandEnum.NUMERIC,
}


TRAIN_BRAKE_SET = {
    TMCC2EngineCommandEnum.TRAIN_BRAKE,
}

STARTUP_SET = {
    TMCC1EngineCommandEnum.START_UP_IMMEDIATE,
    (TMCC1EngineCommandEnum.NUMERIC, 3),
    TMCC2EngineCommandEnum.START_UP_IMMEDIATE,
    TMCC2EngineCommandEnum.START_UP_DELAYED,
}

SHUTDOWN_SET = {
    TMCC1EngineCommandEnum.SHUTDOWN_IMMEDIATE,
    (TMCC1EngineCommandEnum.NUMERIC, 5),
    TMCC2EngineCommandEnum.SHUTDOWN_DELAYED,
    (TMCC2EngineCommandEnum.NUMERIC, 5),
    TMCC2EngineCommandEnum.SHUTDOWN_IMMEDIATE,
}

ENGINE_AUX1_SET = {
    TMCC1EngineCommandEnum.AUX1_ON,
    TMCC1EngineCommandEnum.AUX1_OFF,
    TMCC1EngineCommandEnum.AUX1_OPTION_ONE,
    TMCC1EngineCommandEnum.AUX1_OPTION_TWO,
    TMCC2EngineCommandEnum.AUX1_ON,
    TMCC2EngineCommandEnum.AUX1_OFF,
    TMCC2EngineCommandEnum.AUX1_OPTION_ONE,
    TMCC2EngineCommandEnum.AUX1_OPTION_TWO,
}

ENGINE_AUX2_SET = {
    TMCC1EngineCommandEnum.AUX2_ON,
    TMCC1EngineCommandEnum.AUX2_OFF,
    TMCC1EngineCommandEnum.AUX2_OPTION_ONE,
    TMCC1EngineCommandEnum.AUX2_OPTION_TWO,
    TMCC2EngineCommandEnum.AUX2_ON,
    TMCC2EngineCommandEnum.AUX2_OFF,
    TMCC2EngineCommandEnum.AUX2_OPTION_ONE,
    TMCC2EngineCommandEnum.AUX2_OPTION_TWO,
}

SMOKE_SET = {
    TMCC1EngineCommandEnum.SMOKE_ON,
    (TMCC1EngineCommandEnum.NUMERIC, 9),
    TMCC1EngineCommandEnum.SMOKE_OFF,
    (TMCC1EngineCommandEnum.NUMERIC, 8),
    TMCC2EffectsControl.SMOKE_OFF,
    TMCC2EffectsControl.SMOKE_LOW,
    TMCC2EffectsControl.SMOKE_MEDIUM,
    TMCC2EffectsControl.SMOKE_HIGH,
}

SMOKE_LABEL = {
    TMCC1EngineCommandEnum.SMOKE_ON: "+",
    TMCC1EngineCommandEnum.SMOKE_OFF: "-",
    TMCC2EffectsControl.SMOKE_OFF: "-",
    TMCC2EffectsControl.SMOKE_LOW: "L",
    TMCC2EffectsControl.SMOKE_MEDIUM: "M",
    TMCC2EffectsControl.SMOKE_HIGH: "H",
}

BIG_NUMBER = float("inf")


# noinspection PyUnresolvedReferences
class ComponentState(ABC, CompDataMixin):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        from .component_state_store import DependencyCache

        super().__init__()
        # noinspection PyTypeChecker
        self._lock: Lock = RLock()
        self._is_known: bool = False
        self._scope = scope
        self._last_command: CommandReq | None = None
        self._last_command_bytes = None
        self._last_updated: float | None = None
        self._road_name = None
        self._road_number = None
        self._number = None
        self._address: int | None = None
        self._spare_1: int | None = None
        self._dependencies = DependencyCache.build()
        self._ev = Event()
        self._cv: Condition = Condition(self._lock)

    def __repr__(self) -> str:
        return f"{self.scope.name} {self._address}"

    def __lt__(self, other):
        return self.address < other.address

    def results_in(self, command: CommandReq) -> Set[E]:
        effects = self._dependencies.results_in(command.command, dereference_aliases=True, include_aliases=False)
        if command.is_data:
            # noinspection PyTypeChecker
            effects.update(
                self._dependencies.results_in(
                    (command.command, command.data), dereference_aliases=True, include_aliases=False
                )
            )
        return effects

    def _harvest_effect(self, effects: Set[E]) -> E | tuple[E, int] | None:
        for effect in effects:
            if isinstance(effect, tuple):
                effect_enum = effect[0]
                effect_data = effect[1]
            else:
                effect_enum = effect
                effect_data = None
            if effect_enum.syntax == self.syntax:
                if effect_data is None:
                    return effect_enum
                else:
                    return effect_enum, effect_data
        return None

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def friendly_scope(self) -> str:
        return self.scope.name.title()

    @property
    def address(self) -> int:
        return self._address

    @property
    def tmcc_id(self) -> int:
        return self.address

    @property
    def last_command(self) -> CommandReq:
        return self._last_command

    @property
    def last_updated(self) -> float:
        return self._last_updated

    @property
    def synchronizer(self) -> Condition:
        return self._cv

    @property
    def changed(self) -> threading.Event:
        return self._ev

    @property
    def road_name(self) -> str | None:
        return self._road_name

    @property
    def road_number(self) -> str | None:
        return self._road_number

    @property
    def name(self) -> str:
        the_name = " #" + self.road_number if self.road_number else ""
        the_name = self.road_name + the_name if self.road_name else "NA"
        return the_name

    @property
    def spare_1(self) -> int:
        return self._spare_1

    @staticmethod
    def _as_label(prop: Any) -> str:
        return f"{prop if prop is not None else 'NA'}"

    def _as_dict(self) -> Dict[str, Any]:
        return {
            "tmcc_id": self.tmcc_id,
            "road_name": self.road_name,
            "road_number": self.road_number,
            "scope": self.scope.name.lower(),
        }

    @abc.abstractmethod
    def update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq
        from ..pdi.block_req import BlockReq
        from ..pdi.d4_req import D4Req

        self.changed.clear()
        if command and hasattr(command, "command") and command.command == TMCC1HaltCommandEnum.HALT:
            pass
        else:
            if self._address is None and command.address != BROADCAST_ADDRESS:
                self._address = command.address
            # invalid states
            elif self._address is None and command.address == BROADCAST_ADDRESS:
                raise AttributeError(
                    f"Received broadcast address for {self.friendly_scope} but component has not "
                    f"been initialized {self}"
                )
            elif command.address not in {self._address, BROADCAST_ADDRESS}:
                raise AttributeError(
                    f"{self.friendly_scope} #{self._address} received update for "
                    f"{command.scope.name.title()} #{command.address}, ignoring"
                )
            if self.scope != command.scope:
                scope = command.scope.name.title()
                raise AttributeError(f"{self.friendly_scope} {self.address} received update for {scope}, ignoring")
            if (
                (isinstance(command, BaseReq) and command.status == 0)
                or isinstance(command, IrdaReq)
                or isinstance(command, BlockReq)
                or isinstance(command, D4Req)
            ):
                if hasattr(command, "name") and command.name:
                    self._road_name = title(command.name)
                if hasattr(command, "number") and command.number:
                    self._road_number = command.number
                    # support lookup by road number
                    if self.road_number:
                        try:
                            from .component_state_store import ComponentStateStore

                            rn = int(self.road_number)
                            if (
                                rn > 99 >= self.address >= 1
                                and ComponentStateStore.get_state(self.scope, rn, False) is None
                            ):
                                ComponentStateStore.set_state(self.scope, rn, self)
                        except ValueError:
                            pass
            if isinstance(command, PdiReq):
                self._is_known = True
                if hasattr(command, "spare_1"):
                    self._spare_1 = command.spare_1
        self._last_updated = time()
        self._last_command = command

    @property
    def last_updated_ago(self) -> float:
        if self._last_updated is not None:
            return time() - self._last_updated
        else:
            return BIG_NUMBER

    @staticmethod
    def time_delta(last_updated: float, recv_time: float) -> float:
        if last_updated is None or recv_time is None:
            return BIG_NUMBER
        return last_updated - recv_time

    @staticmethod
    def update_aux_state(
        aux: CommandDefEnum,
        on: CommandDefEnum,
        opt1: CommandDefEnum,
        off: CommandDefEnum,
    ):
        return on if aux is None or aux in {opt1, off} else off

    @property
    def syntax(self) -> CommandSyntax:
        return CommandSyntax.LEGACY if self.is_legacy else CommandSyntax.TMCC

    @property
    def is_known(self) -> bool:
        """
        Returns True if component's state is known, False otherwise.
        """
        return self._is_known

    @property
    @abc.abstractmethod
    def is_tmcc(self) -> bool:
        """
        Returns True if component responds to TMCC protocol, False otherwise.
        """
        ...

    @property
    @abc.abstractmethod
    def is_legacy(self) -> bool:
        """
        Returns True if component responds to Legacy/TMCC2 protocol, False otherwise.
        """
        ...

    @property
    @abc.abstractmethod
    def is_lcs(self) -> bool:
        """
        Returns True if component is an LCS device, False otherwise.
        """
        ...

    @abc.abstractmethod
    def as_bytes(self) -> bytes:
        """
        Returns the component state as a bytes object representative of the TMCC/Legacy
        byte sequence used to trigger the corresponding action(s) when received by the
        component.

        Used to synchronizer component state when client connects to the server.
        """
        ...

    @abc.abstractmethod
    def as_dict(self) -> Dict[str, Any]:
        """
        Returns the component state as a dict object containing the current state
        of the component
        """
        ...


class TmccState(ComponentState, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        super().__init__(scope)

    @property
    def is_tmcc(self) -> bool:
        return True

    @property
    def is_legacy(self) -> bool:
        return False

    @property
    def is_lcs(self) -> bool:
        return False


class LcsState(ComponentState, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        super().__init__(scope)

    @property
    def is_tmcc(self) -> bool:
        return False

    @property
    def is_legacy(self) -> bool:
        return False

    @property
    def is_lcs(self) -> bool:
        return True


class SwitchState(TmccState):
    """
    Maintain the perceived state of a Switch
    """

    def __init__(self, scope: CommandScope = CommandScope.SWITCH) -> None:
        if scope != CommandScope.SWITCH:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._state: Switch | None = None

    def __repr__(self) -> str:
        nm = nu = ""
        if self.road_name is not None:
            nm = f" {self.road_name}"
        if self.road_number is not None:
            nu = f" #{self.road_number} "
        return (
            f"{self.scope.title} {self.address}: {self._state.name if self._state is not None else 'Unknown'}{nm}{nu}"
        )

    def update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq

        if command:
            with self.synchronizer:
                super().update(command)
                if command.command == TMCC1HaltCommandEnum.HALT:
                    return
                if isinstance(command, CommandReq):
                    if command.command != Switch.SET_ADDRESS:
                        self._state = command.command
                elif isinstance(command, Asc2Req) or isinstance(command, Stm2Req):
                    self._state = Switch.THRU if command.is_thru else Switch.OUT
                elif isinstance(command, BaseReq):
                    pass
                else:
                    log.warning(f"Unhandled Switch State Update received: {command}")
                self.changed.set()
                self.synchronizer.notify_all()

    @property
    def state(self) -> Switch:
        return self._state

    @property
    def is_known(self) -> bool:
        return self._state is not None

    @property
    def is_through(self) -> bool:
        return self._state == Switch.THRU

    @property
    def is_out(self) -> bool:
        return self._state == Switch.OUT

    def as_bytes(self) -> bytes:
        from ..pdi.base_req import BaseReq

        byte_str = BaseReq(self.address, PdiCommand.BASE_SWITCH, state=self).as_bytes
        if self.is_known:
            byte_str += CommandReq.build(self.state, self.address).as_bytes
        return byte_str

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        if self.is_known:
            state = "thru" if self.is_through else "out"
        else:
            state = None
        d["state"] = state
        return d


class RouteState(TmccState):
    """
    Maintain Route State
    """

    def __init__(self, scope: CommandScope = CommandScope.ROUTE) -> None:
        if scope != CommandScope.ROUTE:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._components: List[CommandReq] | None = None
        self._components_raw: List[int] | None = None

    def __repr__(self) -> str:
        nm = nu = sw = ""
        if self.road_name is not None:
            nm = f" {self.road_name}"
        if self.road_number is not None:
            nu = f" #{self.road_number} "
        if self._components:
            sw = " Switches: "
            sep = ""
            for c in self._components:
                state = "thru" if c.command == Switch.THRU else "out"
                sw += f"{sep}{c.address} [{state}]"
                sep = ", "
        return f"{self.scope.title} {self.address}: {nm}{nu}{sw}"

    def update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq

        if command:
            with self._cv:
                super().update(command)
                if command.command == TMCC1HaltCommandEnum.HALT:
                    return
                if isinstance(command, CommandReq):
                    pass
                elif isinstance(command, BaseReq):
                    if command.components:
                        self._components = list()
                        self._components_raw = command.components.copy()
                        for comp in command.components:
                            is_thru = (comp & 0x0300) == 0
                            comp &= 0x007F
                            self._components.append(CommandReq(Switch.THRU if is_thru else Switch.OUT, comp))
                else:
                    log.warning(f"Unhandled Route State Update received: {command}")
                self.changed.set()
                self._cv.notify_all()

    @property
    def is_known(self) -> bool:
        return self._components is not None

    @property
    def components(self) -> List[CommandReq]:
        return self._components.copy() if self._components else None

    @property
    def components_raw(self) -> List[int]:
        return self._components_raw.copy() if self._components_raw else None

    def as_bytes(self) -> bytes:
        from ..pdi.base_req import BaseReq

        byte_str = BaseReq(self.address, PdiCommand.BASE_ROUTE, state=self).as_bytes
        return byte_str

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        if self._components:
            sw = [{"switch": c.address, "position": c.command.name.lower()} for c in self._components]
        else:
            sw = list()
        d["switches"] = sw
        return d


T = TypeVar("T", bound=ComponentState)

# noinspection PyTypeChecker,PyTypeHints
SCOPE_TO_STATE_MAP: dict[CommandScope, T] = {
    CommandScope.ROUTE: RouteState,
    CommandScope.SWITCH: SwitchState,
}


class ThreadSafeDefaultDict(defaultdict):
    def __init__(self) -> None:
        super().__init__(None)
        self._lock = threading.RLock()

    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)

    def __setitem__(self, key, value: Any) -> None:
        with self._lock:
            super().__setitem__(key, value)

    def __delitem__(self, key) -> None:
        with self._lock:
            super().__delitem__(key)

    def __len__(self) -> int:
        with self._lock:
            return super().__len__()

    def __contains__(self, key):
        with self._lock:
            return super().__contains__(key)

    def get(self, key, default=None) -> Any:
        with self._lock:
            return super().get(key, default)


class SystemStateDict(ThreadSafeDefaultDict):
    """
    Maintains a dictionary of CommandScope to ComponentStateDict
    """

    def __missing__(self, key: CommandScope | tuple[CommandScope, int]) -> ComponentStateDict:
        """
        generate a ComponentState object for the dictionary, based on the key
        """
        if isinstance(key, CommandScope) and key in SCOPE_TO_STATE_MAP:
            scope = key
        else:
            raise KeyError(f"Invalid scope key: {key}")
        # create the component state dict for this key
        with self._lock:
            self[key] = ComponentStateDict(scope)
            return self[key]


class ComponentStateDict(ThreadSafeDefaultDict):
    from .accessory_state import AccessoryState  # noqa: F401
    from .base_state import BaseState  # noqa: F401
    from .block_state import BlockState  # noqa: F401
    from .engine_state import EngineState, TrainState  # noqa: F401
    from .irda_state import IrdaState  # noqa: F401
    from .sync_state import SyncState  # noqa: F401

    def __init__(self, scope: CommandScope):
        super().__init__()  # base class doesn't get a factory
        if scope not in SCOPE_TO_STATE_MAP:
            raise ValueError(f"Invalid scope: {scope}")
        self._scope = scope

    @property
    def scope(self) -> CommandScope:
        return self._scope

    # noinspection PyCallingNonCallable
    def __missing__(self, key: int) -> ComponentState:
        """
        generate a ComponentState object for the dictionary, based on the key
        """
        if not isinstance(key, int):
            raise KeyError(f"Invalid ID: {key}")
        elif self.scope == CommandScope.BASE and key != 0:
            raise KeyError(f"Invalid ID: {key}")
        elif self.scope == CommandScope.SYNC and key != 99:
            raise KeyError(f"Invalid ID: {key}")
        elif self.scope == CommandScope.ENGINE and (key < 1 or key > 9999):
            raise KeyError(f"Invalid ID: {key}")
        elif self.scope not in {CommandScope.BASE, CommandScope.ENGINE, CommandScope.SYNC} and (key < 1 or key > 99):
            raise KeyError(f"Invalid ID: {key}")
        with self._lock:
            value: ComponentState = SCOPE_TO_STATE_MAP[self._scope](self._scope)
            value._address = key
            self[key] = value
            return self[key]
