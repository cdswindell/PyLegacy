#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import logging
import threading
from abc import ABC, ABCMeta, abstractmethod
from collections import defaultdict
from threading import Condition, Event, RLock
from time import time
from typing import Any, Dict, List, Set, TypeVar

from ..pdi.asc2_req import Asc2Req
from ..pdi.base3_component import RouteComponent
from ..pdi.constants import PdiCommand
from ..pdi.irda_req import IrdaReq
from ..pdi.pdi_req import PdiReq
from ..pdi.stm2_req import Stm2Req
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import (
    BROADCAST_ADDRESS,
    CommandScope,
    CommandSyntax,
)
from ..protocol.tmcc1.tmcc1_constants import (
    TMCC1HaltCommandEnum,
)
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum as Switch
from ..utils.text_utils import title
from .comp_data import CompData, CompDataMixin

log = logging.getLogger(__name__)

C = TypeVar("C", bound=CommandDefEnum)
E = TypeVar("E", bound=CommandDefEnum)
P = TypeVar("P", bound=PdiReq)
L = TypeVar("L", bound=CommandReq)

BIG_NUMBER = float("inf")


# noinspection PyUnresolvedReferences
class ComponentState(ABC, CompDataMixin):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, scope: CommandScope = None) -> None:
        from .component_state_store import DependencyCache

        super().__init__()
        self._cv: Condition = Condition(RLock())
        self._ev = Event()
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

    def __repr__(self) -> str:
        if self.is_comp_data_record is True and not self.payload:
            return str(self.comp_data)
        nm = f" {self.road_name}" if self.road_name else ""
        nu = f" #{self.road_number}" if self.road_number else ""
        pk = f" {self.payload}" if self.payload else ""
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
            return f"{self.scope.title} {self._address:04}:{pk}{nm}{nu}"
        else:
            return f"{self.scope.title} {self._address:>2}:{pk}{nm}{nu}"

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
    def payload(self) -> str:
        return ""

    @property
    def spare_1(self) -> int:
        return self._spare_1

    @abstractmethod
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
        return CommandSyntax.LEGACY if self.is_legacy is True else CommandSyntax.TMCC

    @property
    def is_known(self) -> bool:
        """
        Returns True if the component's state is known, False otherwise.
        """
        return self._is_known

    def as_bytes(self) -> bytes | list[bytes]:
        from ..pdi.base_req import BaseReq

        """
        Returns the component state as a bytes object representative of the TMCC/Legacy
        byte sequence used to trigger the corresponding action(s) when received by the
        component.

        Used to synchronizer component state when client connects to the server.
        """
        with self.synchronizer:
            byte_str = BaseReq(self.address, PdiCommand.BASE_MEMORY, scope=self.scope, state=self).as_bytes
            return byte_str

    def _update_comp_data(self, comp_data: CompData):
        self._comp_data = comp_data
        self._comp_data_record = True

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

    @property
    @abstractmethod
    def is_tmcc(self) -> bool:
        """
        Returns True if the component responds to TMCC protocol, False otherwise.
        """
        ...

    @property
    @abstractmethod
    def is_legacy(self) -> bool:
        """
        Returns True if the component responds to Legacy/TMCC2 protocol, False otherwise.
        """
        ...

    @property
    @abstractmethod
    def is_lcs(self) -> bool:
        """
        Returns True if the component is an LCS device, False otherwise.
        """
        ...

    @abstractmethod
    def as_dict(self) -> Dict[str, Any]:
        """
        Returns the component state as a dict object containing the current state
        of the component
        """
        ...


class TmccState(ComponentState, ABC):
    __metaclass__ = ABCMeta

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
    __metaclass__ = ABCMeta

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
        self._routes: set[RouteState] = set()

    def update(self, command: L | P) -> None:
        if command:
            if command.command == TMCC1HaltCommandEnum.HALT:
                return
            with self.synchronizer:
                super().update(command)
                if isinstance(command, CompDataMixin) and command.is_comp_data_record:
                    self._update_comp_data(command.comp_data)
                elif isinstance(command, CommandReq):
                    if command.command != Switch.SET_ADDRESS:
                        self._state = command.command
                elif isinstance(command, Asc2Req) or isinstance(command, Stm2Req):
                    self._state = Switch.THRU if command.is_thru else Switch.OUT
                else:
                    log.warning(f"Unhandled Switch State Update received: {command}")
                self.changed.set()
                self.synchronizer.notify_all()
            # inform the routes that include this switch of new state
            self.update_route_state()

    @property
    def state(self) -> Switch:
        return self._state

    @property
    def is_known(self) -> bool:
        return self._state is not None

    @property
    def is_thru(self) -> bool:
        return self._state == Switch.THRU

    @property
    def is_through(self) -> bool:
        return self.is_thru

    @property
    def is_out(self) -> bool:
        return self._state == Switch.OUT

    @property
    def payload(self) -> str:
        return f"{self._state.name if self._state is not None else 'Unknown'}"

    def register_route(self, route: RouteState) -> None:
        self._routes.add(route)

    def update_route_state(self) -> None:
        for route in self._routes:
            route.update_switch_state(self)

    def as_bytes(self) -> bytes:
        if self.comp_data is None:
            self.initialize(self.scope, self.address)
        byte_str = super().as_bytes()
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
        self._signature: dict[int, bool] = dict()
        self._current_state: dict[int, bool | None] = dict()

    def update(self, command: L | P) -> None:
        if command:
            if command.command == TMCC1HaltCommandEnum.HALT:
                return
            with self.synchronizer:
                if not self.is_comp_data_record:
                    if isinstance(command, CommandReq):
                        from ..comm.command_listener import CommandDispatcher

                        log.info(f"Still awaiting for initial state, will retry {command}...")
                        CommandDispatcher.get().offer(command)
                        return
                super().update(command)
                if isinstance(command, CompDataMixin) and command.is_comp_data_record:
                    self._update_comp_data(command.comp_data)
                    # set up callbacks so that changes to component switch states
                    # can real-time trigger updates to this route's state
                    comps = self.components
                    if comps:
                        from .component_state_store import ComponentStateStore

                        store = ComponentStateStore.get()
                        for comp in comps:
                            self._signature.update(comp.as_signature)
                            switch = store.get_state(CommandScope.SWITCH, comp.tmcc_id, True)
                            if isinstance(switch, SwitchState):
                                self._current_state.update(
                                    {switch.address: switch.is_thru if switch.is_known else None}
                                )
                                switch.register_route(self)
                elif isinstance(command, CommandReq):
                    pass
                else:
                    log.warning(f"Unhandled Route State Update received: {command}")
                self.changed.set()
                self._cv.notify_all()

    @property
    def components(self) -> List[RouteComponent] | None:
        return self.comp_data.components.copy() if self.comp_data.components else None

    @property
    def payload(self) -> str:
        pl = f"Active: {'True ' if self.is_active else 'False'}"
        pl += f" {self.comp_data.payload()}" if self.comp_data else ""
        return pl

    @property
    def is_active(self) -> bool:
        return self._signature == self._current_state

    @property
    def as_signature(self) -> dict[int, bool]:
        return self._signature

    def update_switch_state(self, switch: SwitchState) -> None:
        with self.synchronizer:
            self._current_state.update({switch.address: switch.is_thru if switch.is_known else None})
            self.changed.set()
            self._cv.notify_all()

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        d["active"] = self.is_active
        if self.components:
            sw = [{"switch": c.tmcc_id, "position": "thru" if c.is_thru is True else "out"} for c in self.components]
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
