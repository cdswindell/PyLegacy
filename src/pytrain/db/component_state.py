from __future__ import annotations

import abc
import logging
import threading
from abc import ABC
from collections import defaultdict
from threading import Event, Lock, RLock, Condition
from time import time
from typing import Dict, Tuple, TypeVar, Set, Any, List

from ..pdi.asc2_req import Asc2Req
from ..pdi.bpc2_req import Bpc2Req
from ..pdi.constants import Asc2Action, PdiCommand, Bpc2Action, IrdaAction
from ..pdi.irda_req import IrdaReq, IrdaSequence
from ..pdi.pdi_req import PdiReq
from ..pdi.stm2_req import Stm2Req
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import (
    CommandScope,
    BROADCAST_ADDRESS,
    CommandSyntax,
    LOCO_TYPE,
    LOCO_TRACK_CRANE,
    TRACK_CRANE_STATE_NUMERICS,
    CONTROL_TYPE,
    LOCO_ACCESSORY,
    PROGRAM_NAME,
    RPM_TYPE,
    STEAM_TYPE,
    Direction,
)
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum as Aux, TMCC1SyncCommandEnum
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum, TMCC1_COMMAND_TO_ALIAS_MAP
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum as TMCC1
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum as Switch, TMCC1HaltCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2_COMMAND_TO_ALIAS_MAP
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as TMCC2
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

BIG_NUMBER = float("inf")


# noinspection PyUnresolvedReferences
class ComponentState(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        from .component_state_store import DependencyCache

        # noinspection PyTypeChecker
        self._lock: Lock = RLock()
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

    def _harvest_effect(self, effects: Set[E]) -> E | Tuple[E, int] | None:
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
                            if rn > 99 and ComponentStateStore.get_state(self.scope, rn, False) is None:
                                ComponentStateStore.set_state(self.scope, rn, self)
                        except ValueError:
                            pass
            if isinstance(command, PdiReq):
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
    @abc.abstractmethod
    def is_known(self) -> bool:
        """
        Returns True if component's state is known, False otherwise.
        """
        ...

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

        Used to synchronizer component state when client attaches to the server.
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


class AccessoryState(TmccState):
    def __init__(self, scope: CommandScope = CommandScope.ACC) -> None:
        if scope != CommandScope.ACC:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._first_pdi_command = None
        self._first_pdi_action = None
        self._last_aux1_opt1 = None
        self._last_aux2_opt1 = None
        self._aux1_state: Aux | None = None
        self._aux2_state: Aux | None = None
        self._aux_state: Aux | None = None
        self._block_power = False
        self._sensor_track = False
        self._pdi_source = False
        self._number: int | None = None

    def __repr__(self) -> str:
        aux1 = aux2 = aux_num = ""
        if self._block_power:
            aux = f"Block Power {'ON' if self.aux_state == Aux.AUX1_OPT_ONE else 'OFF'}"
        elif self._sensor_track:
            aux = "Sensor Track"
        else:
            if self.is_lcs_component:
                aux = "Asc2 " + "ON" if self._aux_state == Aux.AUX1_OPT_ONE else "OFF"
            else:
                if self.aux_state == Aux.AUX1_OPT_ONE:
                    aux = "Aux 1"
                elif self.aux_state == Aux.AUX2_OPT_ONE:
                    aux = "Aux 2"
                else:
                    aux = "Unknown"
                aux1 = f" Aux1: {self.aux1_state.name if self.aux1_state is not None else 'Unknown'}"
                aux2 = f" Aux2: {self.aux2_state.name if self.aux2_state is not None else 'Unknown'}"
                aux_num = f" Aux Num: {self._number if self._number is not None else 'NA'}"
        name = num = ""
        if self.road_name is not None:
            name = f" {self.road_name}"
        if self.road_number is not None:
            num = f" #{self.road_number} "
        return f"{self.scope.title} {self.address}: {aux}{aux1}{aux2}{aux_num}{name}{num}"

    # noinspection DuplicatedCode
    def update(self, command: L | P) -> None:
        if command:
            with self._cv:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(command)
                super().update(command)
                if isinstance(command, CommandReq):
                    if command.command != Aux.SET_ADDRESS:
                        if command.command == TMCC1HaltCommandEnum.HALT:
                            self._aux1_state = Aux.AUX1_OFF
                            self._aux2_state = Aux.AUX2_OFF
                            self._aux_state = Aux.AUX2_OPT_ONE
                            self._number = None
                        else:
                            if self._pdi_source is False:
                                if command.command in {Aux.AUX1_OPT_ONE, Aux.AUX2_OPT_ONE}:
                                    self._aux_state = command.command
                                if command.command == Aux.AUX1_OPT_ONE:
                                    if self.time_delta(self._last_updated, self._last_aux1_opt1) > 1:
                                        self._aux1_state = self.update_aux_state(
                                            self._aux1_state,
                                            Aux.AUX1_ON,
                                            Aux.AUX1_OPT_ONE,
                                            Aux.AUX1_OFF,
                                        )
                                    self._last_aux1_opt1 = self.last_updated
                                elif command.command in {Aux.AUX1_ON, Aux.AUX1_OFF, Aux.AUX1_OPT_TWO}:
                                    self._aux1_state = command.command
                                    self._last_aux1_opt1 = self.last_updated
                                elif command.command == Aux.AUX2_OPT_ONE:
                                    if self.time_delta(self._last_updated, self._last_aux2_opt1) > 1:
                                        self._aux2_state = self.update_aux_state(
                                            self._aux2_state,
                                            Aux.AUX2_ON,
                                            Aux.AUX2_OPT_ONE,
                                            Aux.AUX2_OFF,
                                        )
                                    self._last_aux2_opt1 = self.last_updated
                                elif command.command in {Aux.AUX2_ON, Aux.AUX2_OFF, Aux.AUX2_OPT_TWO}:
                                    self._aux2_state = command.command
                                    self._last_aux2_opt1 = self.last_updated
                            if command.command == Aux.NUMERIC:
                                self._number = command.data
                elif isinstance(command, Asc2Req) or isinstance(command, Bpc2Req):
                    if self._first_pdi_command is None:
                        self._first_pdi_command = command.command
                    if self._first_pdi_action is None:
                        self._first_pdi_action = command.action
                    if command.action in {Asc2Action.CONTROL1, Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                        self._pdi_source = True
                        if command.action in {Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                            self._block_power = True
                        else:
                            self._block_power = False
                        if command.state == 1:
                            self._aux1_state = Aux.AUX1_ON
                            self._aux2_state = Aux.AUX2_ON
                            self._aux_state = Aux.AUX1_OPT_ONE
                        else:
                            self._aux1_state = Aux.AUX1_OFF
                            self._aux2_state = Aux.AUX2_OFF
                            self._aux_state = Aux.AUX2_OPT_ONE
                elif isinstance(command, IrdaReq):
                    if self._first_pdi_command is None:
                        self._first_pdi_command = command.command
                    if self._first_pdi_action is None:
                        self._first_pdi_action = command.action
                    self._sensor_track = True
                self.changed.set()
                self._cv.notify_all()

    @property
    def is_known(self) -> bool:
        return (
            self._aux_state is not None
            or self._aux1_state is not None
            or self._aux2_state is not None
            or self._number is not None
        )

    @property
    def is_power_district(self) -> bool:
        return self._block_power

    @property
    def is_sensor_track(self) -> bool:
        return self._sensor_track

    @property
    def is_lcs_component(self) -> bool:
        return self._pdi_source

    @property
    def aux_state(self) -> Aux:
        return self._aux_state

    @property
    def is_aux_on(self) -> bool:
        return self._aux_state == Aux.AUX1_OPT_ONE

    @property
    def is_aux_off(self) -> bool:
        return self._aux_state == Aux.AUX2_OPT_ONE

    @property
    def aux1_state(self) -> Aux:
        return self._aux1_state

    @property
    def aux2_state(self) -> Aux:
        return self._aux2_state

    @property
    def value(self) -> int:
        return self._number

    def as_bytes(self) -> bytes:
        from ..pdi.base_req import BaseReq

        byte_str = BaseReq(self.address, PdiCommand.BASE_ACC, state=self).as_bytes
        if self._sensor_track:
            byte_str += IrdaReq(self.address, PdiCommand.IRDA_RX, IrdaAction.INFO, scope=CommandScope.ACC).as_bytes
        elif self.is_lcs_component:
            if isinstance(self._first_pdi_action, Asc2Action):
                byte_str += Asc2Req(
                    self.address,
                    self._first_pdi_command,
                    self._first_pdi_action,
                    values=1 if self._aux_state == Aux.AUX1_OPT_ONE else 0,
                ).as_bytes
            elif isinstance(self._first_pdi_action, Bpc2Action):
                byte_str += Bpc2Req(
                    self.address,
                    self._first_pdi_command,
                    self._first_pdi_action,
                    state=1 if self._aux_state == Aux.AUX1_OPT_ONE else 0,
                ).as_bytes
            else:
                log.error(f"State req for lcs device: {self._first_pdi_command.name} {self._first_pdi_action.name}")
        else:
            if self._aux_state is not None:
                byte_str += CommandReq.build(self.aux_state, self.address).as_bytes
            if self._aux1_state is not None:
                byte_str += CommandReq.build(self.aux1_state, self.address).as_bytes
            if self._aux2_state is not None:
                byte_str += CommandReq.build(self.aux2_state, self.address).as_bytes
        return byte_str

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        if self._sensor_track:
            d["type"] = "sensor track"
        elif self._block_power:
            d["type"] = "power district"
            d["block"] = "on" if self._aux_state == Aux.AUX1_OPT_ONE else "off"
        else:
            d["type"] = "accessory"
            d["aux"] = self._aux_state.name.lower() if self._aux_state else None
            d["aux1"] = self.aux1_state.name.lower() if self.aux1_state else None
            d["aux2"] = self.aux2_state.name.lower() if self.aux2_state else None
        return d


class EngineState(ComponentState):
    def __init__(self, scope: CommandScope = CommandScope.ENGINE) -> None:
        from ..pdi.base_req import ConsistComponent

        if scope not in {CommandScope.ENGINE, CommandScope.TRAIN}:
            raise ValueError(f"Invalid scope: {scope}, expected ENGINE or TRAIN")
        super().__init__(scope)
        self._start_stop: CommandDefEnum | None = None
        self._speed: int | None = None
        self._speed_limit: int | None = None
        self._max_speed: int | None = None
        self._direction: CommandDefEnum | None = None
        self._momentum: int | None = None
        self._smoke_level: CommandDefEnum | None = None
        self._train_brake: int | None = None
        self._prod_year: int | None = None
        self._rpm: int | None = None
        self._labor: int | None = None
        self._control_type: int | None = None
        self._sound_type: int | None = None
        self._sound_type_label: str | None = None
        self._engine_type: int | None = None
        self._engine_type_label: str | None = None
        self._engine_class: int | None = None
        self._engine_class_label: str | None = None
        self._numeric: int | None = None
        self._numeric_cmd: CommandDefEnum | None = None
        self._aux: CommandDefEnum | None = None
        self._aux1: CommandDefEnum | None = None
        self._aux2: CommandDefEnum | None = None
        self._last_aux1_opt1 = None
        self._last_aux2_opt1 = None
        self._is_legacy: bool | None = None  # assume we are in TMCC mode until/unless we receive a Legacy cmd
        self._consist_comp: None | List[ConsistComponent] = None
        self._consist_flags: int | None = None

    def __repr__(self) -> str:
        sp = dr = ss = name = num = mom = rl = yr = nu = lt = tb = aux = lb = sm = c = ""
        if self._direction in {TMCC1EngineCommandEnum.FORWARD_DIRECTION, TMCC2EngineCommandEnum.FORWARD_DIRECTION}:
            dr = " FWD"
        elif self._direction in {TMCC1EngineCommandEnum.REVERSE_DIRECTION, TMCC2EngineCommandEnum.REVERSE_DIRECTION}:
            dr = " REV"

        if self._speed is not None:
            sp = f" Speed: {self._speed}"
            if self.speed_limit is not None:
                speed_limit = self.decode_speed_info(self.speed_limit)
                sp += f"/{speed_limit}"
            if self.max_speed is not None:
                max_speed = self.decode_speed_info(self.max_speed)
                sp += f"/{max_speed}"
        if self._start_stop is not None:
            if self._start_stop in STARTUP_SET:
                ss = " Started up"
            elif self._start_stop in SHUTDOWN_SET:
                ss = " Shut down"
        if self._momentum is not None:
            mom = f" Mom: {self.momentum_label}"
        if self._train_brake is not None:
            tb = f" TB: {self.train_brake_label}"
        if self._rpm is not None:
            rl = f" RPM: {self._rpm}"
        if self._labor is not None:
            lb = f" Labor: {self._labor}"
        if self._numeric is not None:
            nu = f" Num: {self._numeric}"
        if self.road_name is not None:
            name = f" {self.road_name}"
        if self.road_number is not None:
            num = f" #{self.road_number}"
        if self.year is not None:
            num = f" Released: {self.year}"
        if self.engine_type is not None:
            lt = f" {LOCO_TYPE.get(self.engine_type, 'NA')}"
        if self._aux2:
            aux = f" Aux2: {self._aux2.name.split('_')[-1]}"
        if self._smoke_level is not None:
            sm = f" Smoke: {self._smoke_level.name.split('_')[-1].lower()}"
        ct = f" {CONTROL_TYPE.get(self.control_type, 'NA')}"
        if self._consist_comp:
            c = "\n"
            for cc in self._consist_comp:
                c += f"{cc} "
        return (
            f"{self.scope.title} {self._address:02}{sp}{rl}{lb}{mom}{tb}{sm}{dr}{nu}{aux}{name}{num}{lt}{ct}{yr}{ss}{c}"
        )

    def decode_speed_info(self, speed_info):
        if speed_info is not None and speed_info == 255:  # not set
            if self.is_legacy:
                speed_info = 195
            else:
                speed_info = 31
        return speed_info

    def is_known(self) -> bool:
        return self._direction is not None or self._start_stop is not None or self._speed is not None

    def update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq

        # suppress duplicate commands that are received within 1 second; dups are common
        # in the lionel ecosystem, as commands are frequently sent twice or even 3 times
        # consecutively.
        if command is None or (command == self._last_command and self.last_updated_ago < 1):
            return
        with self._cv:
            super().update(command)
            if isinstance(command, CommandReq):
                if self.is_legacy is None:
                    self._is_legacy = command.is_tmcc2

                # handle some aspects of halt command
                if command.command == TMCC1HaltCommandEnum.HALT:
                    if self.is_legacy:
                        self._aux1 = TMCC2.AUX1_OFF
                        self._aux2 = TMCC2.AUX2_OFF
                        self._aux = TMCC2.AUX2_OPTION_ONE
                    else:
                        self._aux1 = TMCC1.AUX1_OFF
                        self._aux2 = TMCC1.AUX2_OFF
                        self._aux = TMCC1.AUX2_OPTION_ONE
                    self._speed = 0
                    self._rpm = 0
                    self._labor = 12
                    self._numeric = None
                    self._last_command = command

                # get the downstream effects of this command, as they also impact state
                cmd_effects = self.results_in(command)
                log.debug(f"Update: {command}\nEffects: {cmd_effects}")

                # handle last numeric
                if command.command in NUMERIC_SET:
                    if self.engine_type in {LOCO_TRACK_CRANE, LOCO_ACCESSORY}:
                        if command.data in TRACK_CRANE_STATE_NUMERICS:
                            self._numeric = command.data
                            self._numeric_cmd = command.command
                    else:
                        self._numeric = command.data
                        self._numeric_cmd = command.command
                        # numeric commands can change RPM, Volume, and reset the train
                        # force a state update for this engine/train, if we are connected
                        # to a Base 3
                        from ..pdi.base3_buffer import Base3Buffer

                        if command != self._last_command:
                            Base3Buffer.request_state_update(self.address, self.scope)
                elif cmd_effects & NUMERIC_SET:
                    numeric = self._harvest_effect(cmd_effects & NUMERIC_SET)
                    log.info(f"What to do? {command}: {numeric} {type(numeric)}")

                # Direction changes trigger several other changes; we want to avoid resettling
                # rpm, labor, and speed if direction really didn't change
                if command.command in DIRECTIONS_SET:
                    if self._direction != command.command:
                        self._direction = command.command
                    else:
                        return
                elif cmd_effects & DIRECTIONS_SET:
                    self._direction = self._harvest_effect(cmd_effects & DIRECTIONS_SET)

                # handle train brake
                if command.command in TRAIN_BRAKE_SET:
                    self._train_brake = command.data
                elif cmd_effects & TRAIN_BRAKE_SET:
                    self._train_brake = self._harvest_effect(cmd_effects & TRAIN_BRAKE_SET)

                if command.command in SMOKE_SET or (command.command, command.data) in SMOKE_SET:
                    if isinstance(command.command, TMCC2EffectsControl):
                        self._smoke_level = command.command
                    elif command.is_data and (command.command, command.data) in TMCC1_COMMAND_TO_ALIAS_MAP:
                        self._smoke_level = TMCC1_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]

                # aux commands
                for cmd in {command.command} | (cmd_effects & ENGINE_AUX1_SET):
                    if cmd in ENGINE_AUX1_SET:
                        self._aux = cmd if cmd in {TMCC1.AUX1_OPTION_ONE, TMCC2.AUX1_OPTION_ONE} else self._aux
                        self._aux1 = cmd

                for cmd in {command.command} | (cmd_effects & ENGINE_AUX2_SET):
                    if cmd in ENGINE_AUX2_SET:
                        self._aux = cmd if cmd in {TMCC1.AUX2_OPTION_ONE, TMCC2.AUX2_OPTION_ONE} else self._aux
                        if cmd in {TMCC1.AUX2_OPTION_ONE, TMCC2.AUX2_OPTION_ONE}:
                            if self.time_delta(self._last_updated, self._last_aux2_opt1) > 1:
                                if self.is_legacy:
                                    self._aux2 = self.update_aux_state(
                                        self._aux2,
                                        TMCC2.AUX2_ON,
                                        TMCC2.AUX2_OPTION_ONE,
                                        TMCC2.AUX2_OFF,
                                    )
                                else:
                                    self._aux2 = self.update_aux_state(
                                        self._aux2,
                                        TMCC1.AUX2_ON,
                                        TMCC1.AUX2_OPTION_ONE,
                                        TMCC1.AUX2_OFF,
                                    )
                            self._last_aux2_opt1 = self.last_updated
                        elif cmd in {
                            TMCC1.AUX2_ON,
                            TMCC1.AUX2_OFF,
                            TMCC1.AUX2_OPTION_TWO,
                            TMCC2.AUX2_ON,
                            TMCC2.AUX2_OFF,
                            TMCC2.AUX2_OPTION_TWO,
                        }:
                            self._aux2 = cmd
                            self._last_aux2_opt1 = self.last_updated

                # handle run level/rpm
                if command.command in RPM_SET:
                    self._rpm = command.data
                elif cmd_effects & RPM_SET:
                    rpm = self._harvest_effect(cmd_effects & RPM_SET)
                    if isinstance(rpm, tuple) and len(rpm) == 2:
                        self._rpm = rpm[1]
                    elif isinstance(rpm, CommandDefEnum):
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"{command} {rpm} {type(rpm)} {rpm.command_def} {type(rpm.command_def)}")
                        self._rpm = 0
                    else:
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"{command} {rpm} {type(rpm)} {cmd_effects}")
                        self._rpm = 0

                # handle labor
                if command.command in LABOR_SET:
                    self._labor = command.data
                elif cmd_effects & LABOR_SET:
                    labor = self._harvest_effect(cmd_effects & LABOR_SET)
                    if isinstance(labor, tuple) and len(labor) == 2:
                        self._labor = labor[1]
                    else:
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"{command} {labor} {type(labor)} {cmd_effects}")
                        self._speed = 0

                # handle speed
                if command.command in SPEED_SET:
                    self._speed = command.data
                elif cmd_effects & SPEED_SET:
                    speed = self._harvest_effect(cmd_effects & SPEED_SET)
                    if isinstance(speed, tuple) and len(speed) > 1:
                        self._speed = speed[1]
                    else:
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"{command} {speed} {type(speed)} {cmd_effects}")
                        self._speed = 0

                # handle momentum
                if command.command in MOMENTUM_SET:
                    if command.command in {
                        TMCC1EngineCommandEnum.MOMENTUM_LOW,
                        TMCC2EngineCommandEnum.MOMENTUM_LOW,
                    }:
                        self._momentum = 0
                    if command.command in {
                        TMCC1EngineCommandEnum.MOMENTUM_MEDIUM,
                        TMCC2EngineCommandEnum.MOMENTUM_MEDIUM,
                    }:
                        self._momentum = 3
                    if command.command in {
                        TMCC1EngineCommandEnum.MOMENTUM_HIGH,
                        TMCC2EngineCommandEnum.MOMENTUM_HIGH,
                    }:
                        self._momentum = 7
                    elif command.command == TMCC2EngineCommandEnum.MOMENTUM:
                        self._momentum = command.data

                # handle startup/shutdown
                if command.command in STARTUP_SET:
                    self._start_stop = command.command
                elif command.command in SHUTDOWN_SET:
                    self._start_stop = command.command
                elif cmd_effects & STARTUP_SET:
                    startup = self._harvest_effect(cmd_effects & STARTUP_SET)
                    if isinstance(startup, CommandDefEnum):
                        self._start_stop = startup
                    elif command.is_data and (command.command, command.data) in TMCC2_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC2_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
                    elif command.is_data and (command.command, command.data) in TMCC1_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC1_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
                elif cmd_effects & SHUTDOWN_SET:
                    shutdown = self._harvest_effect(cmd_effects & SHUTDOWN_SET)
                    if isinstance(shutdown, CommandDefEnum):
                        self._start_stop = shutdown
                    elif command.is_data and (command.command, command.data) in TMCC2_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC2_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
                    elif command.is_data and (command.command, command.data) in TMCC1_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC1_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
            elif (
                isinstance(command, BaseReq)
                and command.status == 0
                and command.pdi_command
                in {
                    PdiCommand.BASE_ENGINE,
                    PdiCommand.BASE_TRAIN,
                    PdiCommand.UPDATE_ENGINE_SPEED,
                    PdiCommand.UPDATE_TRAIN_SPEED,
                }
            ):
                from ..pdi.base_req import EngineBits

                if self._speed is None and command.is_valid(EngineBits.SPEED):
                    self._speed = command.speed
                if command.pdi_command in {PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN}:
                    if command.is_valid(EngineBits.MAX_SPEED):
                        self._max_speed = command.max_speed
                    if command.is_valid(EngineBits.SPEED_LIMIT):
                        self._speed_limit = command.speed_limit
                    if command.is_valid(EngineBits.MOMENTUM):
                        self._momentum = command.momentum_tmcc
                    if command.is_valid(EngineBits.RUN_LEVEL):
                        self._rpm = command.run_level
                    if command.is_valid(EngineBits.LABOR_BIAS):
                        self._labor = command.labor_bias_tmcc
                    if command.is_valid(EngineBits.CONTROL_TYPE):
                        self._control_type = command.control_id
                        self._is_legacy = command.is_legacy
                    if command.is_valid(EngineBits.SOUND_TYPE):
                        self._sound_type = command.sound_id
                        self._sound_type_label = command.sound
                    if command.is_valid(EngineBits.CLASS_TYPE):
                        self._engine_class = command.loco_class_id
                        self._engine_class_label = command.loco_class
                    if command.is_valid(EngineBits.LOCO_TYPE):
                        self._engine_type = command.loco_type_id
                        self._engine_type_label = command.loco_type
                    if command.is_valid(EngineBits.SMOKE_LEVEL) and self.is_legacy:
                        self._smoke_level = command.smoke
                    if command.is_valid(EngineBits.TRAIN_BRAKE):
                        self._train_brake = command.train_brake
                    if command.pdi_command == PdiCommand.BASE_TRAIN:
                        self._consist_comp = command.consist_components
                        self._consist_flags = command.consist_flags
            elif isinstance(command, IrdaReq) and command.action == IrdaAction.DATA:
                self._prod_year = command.year
            self.changed.set()
            self._cv.notify_all()

    def as_bytes(self) -> bytes:
        from ..pdi.base_req import BaseReq

        byte_str = bytes()
        # encode name, number, momentum, speed, and rpm using PDI command
        pdi = None
        if self.scope == CommandScope.ENGINE:
            pdi = BaseReq(self.address, PdiCommand.BASE_ENGINE, state=self)
        elif self.scope == CommandScope.TRAIN:
            pdi = BaseReq(self.address, PdiCommand.BASE_TRAIN, state=self)
        if pdi:
            byte_str += pdi.as_bytes
        if self._start_stop is not None:
            byte_str += CommandReq.build(self._start_stop, self.address, scope=self.scope).as_bytes
        if self._smoke_level is not None:
            byte_str += CommandReq.build(self._smoke_level, self.address, scope=self.scope).as_bytes
        if self._direction is not None:
            # the direction state will have encoded in it the syntax (tmcc1 or tmcc2)
            byte_str += CommandReq.build(self._direction, self.address, scope=self.scope).as_bytes
        if self._numeric is not None and self._numeric_cmd is not None:
            if self.engine_type in {LOCO_TRACK_CRANE, LOCO_ACCESSORY}:
                byte_str += CommandReq.build(
                    self._numeric_cmd,
                    self.address,
                    data=self._numeric,
                    scope=self.scope,
                ).as_bytes
        if self._aux is not None:
            byte_str += CommandReq.build(self._aux, self.address).as_bytes
        if self._aux1 is not None:
            byte_str += CommandReq.build(self.aux1, self.address).as_bytes
        if self._aux2 is not None:
            byte_str += CommandReq.build(self.aux2, self.address).as_bytes
        return byte_str

    @property
    def is_rpm(self) -> bool:
        return self.engine_type in RPM_TYPE

    @property
    def is_steam(self) -> bool:
        return self.engine_type in STEAM_TYPE

    @property
    def speed(self) -> int:
        return self._speed

    @property
    def speed_limit(self) -> int:
        return self._speed_limit

    @property
    def max_speed(self) -> int:
        return self._max_speed

    @property
    def speed_max(self) -> int | None:
        if self.max_speed and self.speed_limit:
            return min(self.max_speed, self.speed_limit)
        elif self._speed_limit and self.speed_limit != 255:
            return self._speed_limit
        elif self.max_speed and self.max_speed != 255:
            return 199 if self.is_legacy else 31

    @property
    def speed_label(self) -> str:
        return self._as_label(self._speed)

    @property
    def numeric(self) -> int:
        return self._numeric

    @property
    def momentum(self) -> int:
        return self._momentum

    @property
    def momentum_label(self) -> str:
        return self._as_label(self.momentum)

    @property
    def rpm(self) -> int:
        return self._rpm if self.is_rpm else 0

    @property
    def rpm_label(self) -> str:
        return self._as_label(self.rpm)

    @property
    def labor(self) -> int:
        return self._labor

    @property
    def labor_label(self) -> str:
        return self._as_label(self.labor)

    @property
    def smoke(self) -> CommandDefEnum | None:
        return self._smoke_level

    @property
    def train_brake(self) -> int:
        return self._train_brake

    @property
    def train_brake_label(self) -> str:
        return self._as_label(self.train_brake)

    @property
    def control_type(self) -> int:
        return self._control_type

    @property
    def control_type_label(self) -> str:
        return CONTROL_TYPE.get(self.control_type, "NA")

    @property
    def sound_type(self) -> int:
        return self._sound_type

    @property
    def sound_type_label(self) -> str:
        return self._sound_type_label

    @property
    def engine_type(self) -> int:
        return self._engine_type

    @property
    def engine_type_label(self) -> str:
        return self._engine_type_label

    @property
    def engine_class(self) -> int:
        return self._engine_class

    @property
    def engine_class_label(self) -> str:
        return self._engine_class_label

    @property
    def direction(self) -> CommandDefEnum | None:
        return self._direction

    @property
    def direction_label(self) -> str:
        dr = "NA"
        if self._direction in {TMCC1EngineCommandEnum.FORWARD_DIRECTION, TMCC2EngineCommandEnum.FORWARD_DIRECTION}:
            dr = "FW"
        elif self._direction in {TMCC1EngineCommandEnum.REVERSE_DIRECTION, TMCC2EngineCommandEnum.REVERSE_DIRECTION}:
            dr = "RV"
        return dr

    @property
    def stop_start(self) -> CommandDefEnum | None:
        return self._start_stop

    @property
    def year(self) -> int:
        return self._prod_year

    @property
    def is_aux_on(self) -> bool:
        return self._aux in {TMCC1.AUX1_OPTION_ONE, TMCC2.AUX1_OPTION_ONE}

    @property
    def is_aux_off(self) -> bool:
        return self.is_aux_on is False

    @property
    def aux1(self) -> CommandDefEnum:
        return self._aux1

    @property
    def aux2(self) -> CommandDefEnum:
        return self._aux2

    @property
    def is_aux1(self) -> bool:
        return self._aux2 in {TMCC1.AUX1_ON, TMCC2.AUX1_ON}

    @property
    def is_aux2(self) -> bool:
        return self._aux2 in {TMCC1.AUX2_ON, TMCC2.AUX2_ON}

    @property
    def is_tmcc(self) -> bool:
        return self._is_legacy is False

    @property
    def is_legacy(self) -> bool:
        return self._is_legacy is True

    @property
    def is_lcs(self) -> bool:
        return False

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        for elem in ["speed", "speed_limit", "max_speed", "train_brake", "momentum", "rpm", "labor", "year"]:
            if hasattr(self, elem):
                val = getattr(self, elem)
                d[elem] = val if val is not None and val != 255 else None
        d["direction"] = self.direction.name.lower() if self.direction else None
        d["smoke"] = self.smoke.name.lower() if self.smoke else None
        d["control"] = self.control_type_label.lower() if self.control_type else None
        d["sound_type"] = self.sound_type_label.lower() if self.sound_type else None
        d["engine_type"] = self.engine_type_label.lower() if self.engine_type else None
        d["engine_class"] = self.engine_class_label.lower() if self.engine_class else None
        if isinstance(self, TrainState):
            d["flags"] = self._consist_flags
            d["components"] = {c.tmcc_id: c.info for c in self._consist_comp}
        return d


class TrainState(EngineState):
    from ..pdi.base_req import ConsistComponent

    def __init__(self, scope: CommandScope = CommandScope.TRAIN) -> None:
        if scope != CommandScope.TRAIN:
            raise ValueError(f"Invalid scope: {scope}, expected {CommandScope.TRAIN.name}")
        super().__init__(scope)
        # hard code TMCC2, for now
        self._is_legacy = True
        self._control_type = 2

    @property
    def consist_flags(self) -> int:
        return self._consist_flags

    @property
    def consist_components(self) -> List[ConsistComponent]:
        return self._consist_comp


class IrdaState(LcsState):
    """
    Maintain the state of a Sensor Track (Irda)
    """

    def __init__(self, scope: CommandScope = CommandScope.IRDA) -> None:
        if scope != CommandScope.IRDA:
            raise ValueError(f"Invalid scope: {scope}, expected {CommandScope.IRDA.name}")
        super().__init__(scope)
        self._sequence: IrdaSequence | None = None
        self._loco_rl: int | None = 255
        self._loco_lr: int | None = 255
        self._last_train_id = self._last_engine_id = self._last_dir = None

    def __repr__(self) -> str:
        if self.sequence and self.sequence != IrdaSequence.NONE:
            rle = f"{self._loco_rl}" if self._loco_rl and self._loco_rl != 255 else "Any"
            lre = f"{self._loco_lr}" if self._loco_lr and self._loco_lr != 255 else "Any"
            rl = f" When Engine ID (R -> L): {rle}"
            lr = f" When Engine ID (L -> R): {lre}"
        else:
            rl = lr = ""
        le = f" Last Engine ID: {self._last_engine_id}" if self._last_engine_id else ""
        lt = f" Last Train ID: {self._last_train_id}" if self._last_train_id else ""
        if self._last_dir is not None:
            ld = " L --> R" if self._last_dir == 1 else " R --> L"
        else:
            ld = ""
        return f"Sensor Track {self.address}: Sequence: {self.sequence_str}{rl}{lr}{le}{lt}{ld}"

    def update(self, command: P) -> None:
        from .component_state_store import ComponentStateStore
        from ..comm.comm_buffer import CommBuffer

        if command:
            with self._cv:
                super().update(command)
                if isinstance(command, IrdaReq) and command.pdi_command == PdiCommand.IRDA_RX:
                    if command.action == IrdaAction.CONFIG:
                        self._sequence = command.sequence
                        self._loco_rl = command.loco_rl
                        self._loco_lr = command.loco_lr
                    elif command.action == IrdaAction.SEQUENCE:
                        self._sequence = command.sequence
                    elif command.action == IrdaAction.DATA:
                        # change engine/train speed, based on direction of travel
                        self._last_engine_id = command.engine_id
                        self._last_train_id = command.train_id
                        self._last_dir = command.direction
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"IRDA {self.address} Sequence: {self.sequence} Command: {command}")
                        if (
                            self.sequence
                            in {
                                IrdaSequence.SLOW_SPEED_NORMAL_SPEED,
                                IrdaSequence.NORMAL_SPEED_SLOW_SPEED,
                            }
                            and CommBuffer.is_server()
                        ):
                            rr_speed = None
                            if command.is_right_to_left:
                                rr_speed = "slow" if self.sequence == IrdaSequence.SLOW_SPEED_NORMAL_SPEED else "normal"
                            elif command.is_left_to_right:
                                rr_speed = "normal" if self.sequence == IrdaSequence.SLOW_SPEED_NORMAL_SPEED else "slow"
                            if rr_speed:
                                address = None
                                scope = CommandScope.ENGINE
                                if command.train_id:
                                    address = command.train_id
                                    scope = CommandScope.TRAIN
                                elif command.engine_id:
                                    address = command.engine_id
                                state = ComponentStateStore.get_state(scope, address)
                                if state is not None:
                                    from ..protocol.sequence.ramped_speed_req import RampedSpeedReq

                                    # noinspection PyTypeChecker
                                    RampedSpeedReq(address, rr_speed, scope=scope, is_tmcc=state.is_tmcc).send()
                            # send update to Train and component engines as well
                            orig_scope = command.scope
                            orig_tmcc_id = command.tmcc_id
                            try:
                                if command.engine_id:
                                    engine_state = ComponentStateStore.get_state(CommandScope.ENGINE, command.engine_id)
                                    command.scope = CommandScope.ENGINE
                                    command.tmcc_id = command.engine_id
                                    engine_state.update(command)
                            finally:
                                command.scope = orig_scope
                                command.tmcc_id = orig_tmcc_id
                    self.changed.set()
                    self._cv.notify_all()

    @property
    def is_known(self) -> bool:
        return self._sequence is not None

    @property
    def sequence(self) -> IrdaSequence:
        return self._sequence

    @property
    def sequence_str(self) -> str | None:
        return self.sequence.name.title() if self.sequence else "NA"

    @property
    def last_direction(self) -> Direction:
        if self._last_dir == 1:
            return Direction.L2R
        elif self._last_dir == 0:
            return Direction.R2L
        else:
            return Direction.UNKNOWN

    @property
    def is_left_to_right(self) -> bool:
        return self.last_direction == 1

    @property
    def is_right_to_left(self) -> bool:
        return self.last_direction == 0

    @property
    def last_engine_id(self) -> int:
        return self._last_engine_id

    @property
    def last_train_id(self) -> int:
        return self._last_train_id

    @property
    def is_engine(self) -> bool:
        return (self.is_train is False) and (self._last_engine_id is not None) and (self._last_engine_id > 0)

    @property
    def is_train(self) -> bool:
        return (self._last_train_id is not None) and (self._last_train_id > 0)

    def as_bytes(self) -> bytes:
        # TODO: return IrdaAction.DATA
        if self.is_known:
            return IrdaReq(
                self.address,
                PdiCommand.IRDA_RX,
                IrdaAction.CONFIG,
                sequence=self._sequence,
                loco_rl=self._loco_rl,
                loco_lr=self._loco_lr,
            ).as_bytes
        else:
            return bytes()

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        d["last_direction"] = self.last_direction.name.lower()
        d["last_engine_id"] = self.last_engine_id
        d["last_train_id"] = self.last_train_id
        d["sequence"] = self.sequence.name.lower() if self.sequence else "none"
        return d


class BaseState(ComponentState):
    """
    Maintain the state of a Lionel Base
    """

    def __init__(self, scope: CommandScope = CommandScope.BASE) -> None:
        if scope != CommandScope.BASE:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._base_name = None
        self._firmware = None
        self._firmware_high = None
        self._firmware_low = None
        self._route_throw_rate = None

    def __repr__(self) -> str:
        bn = f"Lionel Base 3: {self._base_name if self._base_name else 'NA'}"
        fw = f" Firmware: {self._firmware if self._firmware else 'NA'}"
        return f"{bn}{fw}"

    def update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq

        if isinstance(command, BaseReq):
            with self._cv:
                # Note: super().update is explicitly not called
                self._base_name = command.name.title() if command.name else self._base_name
                self._firmware = command.firmware if command.firmware else self._firmware
                if self.firmware:
                    version_info = self.firmware.split(".")
                    self._firmware_high = int(version_info[0])
                    self._firmware_low = int(version_info[1])
                self._route_throw_rate = command.route_throw_rate
                self.changed.set()
                self._cv.notify_all()

    @property
    def base_name(self) -> str:
        return self._base_name

    @property
    def firmware(self) -> str:
        return self._firmware

    @property
    def firmware_high(self) -> int:
        return self._firmware_high

    @property
    def firmware_low(self) -> int:
        return self._firmware_low

    @property
    def route_throw_rate(self) -> float:
        return self._route_throw_rate

    @property
    def is_known(self) -> bool:
        return self._base_name is not None or self._firmware is not None

    @property
    def is_tmcc(self) -> bool:
        return False

    @property
    def is_legacy(self) -> bool:
        return True

    @property
    def is_lcs(self) -> bool:
        return True

    def as_bytes(self) -> bytes:
        if self.is_known:
            from ..pdi.base_req import BaseReq

            return BaseReq(self.address, PdiCommand.BASE, state=self).as_bytes
        else:
            return bytes()

    def as_dict(self) -> Dict[str, Any]:
        d = dict()
        d["firmware"] = self.firmware
        d["base_name"] = self.base_name
        d["route_throw_rate"] = self.route_throw_rate
        return d


class SyncState(ComponentState):
    """
    Maintain the state of a Lionel Base
    """

    def __init__(self, scope: CommandScope = CommandScope.SYNC) -> None:
        if scope != CommandScope.SYNC:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._state_synchronized: bool | None = None
        self._state_synchronizing: bool | None = None

    def __repr__(self) -> str:
        if self._state_synchronized is not None and not self._state_synchronized:
            msg = "Synchronizing..."
        else:
            msg = f"Synchronized: {self._state_synchronized if self._state_synchronized is not None else 'NA'}"
        return f"{PROGRAM_NAME} {msg}"

    def update(self, command: L | P) -> None:
        if isinstance(command, CommandReq):
            self._ev.clear()
            with self._cv:
                # Note: super().update is explicitly not called
                if command.command == TMCC1SyncCommandEnum.SYNCHRONIZING:
                    self._state_synchronized = False
                    self._state_synchronizing = True
                elif command.command == TMCC1SyncCommandEnum.SYNCHRONIZED:
                    self._state_synchronized = True
                    self._state_synchronizing = False
                self.changed.set()
                self._cv.notify_all()

    @property
    def is_synchronized(self) -> bool:
        return self._state_synchronized

    @property
    def is_synchronizing(self) -> bool:
        return self._state_synchronizing

    @property
    def is_known(self) -> bool:
        return self._state_synchronized is not None

    @property
    def is_tmcc(self) -> bool:
        return True

    @property
    def is_legacy(self) -> bool:
        return False

    @property
    def is_lcs(self) -> bool:
        return False

    def as_bytes(self) -> bytes:
        return bytes()

    def as_dict(self) -> Dict[str, Any]:
        state = "synchronized" if self.is_synchronized else "synchronizing" if self.is_synchronizing else None
        return {"state": state}


class BlockState(ComponentState):
    """
    Maintain the state of a Block section
    """

    def __init__(self, scope: CommandScope = CommandScope.BLOCK) -> None:
        if scope != CommandScope.BLOCK:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._block_req = None
        self._block_id = None
        self._prev_block = None
        self._next_block = None
        self._occupied_by: EngineState | TrainState | None = None
        self._direction = None
        self._occupied: bool = False
        self._flags: int = 0
        self._sensor_track: IrdaState | None = None
        self._switch: SwitchState | None = None

    def __repr__(self) -> str:
        msg = f"{self.block_id if self.block_id else 'NA'}"
        msg += f" Occupied: {'Yes' if self.is_occupied is True else 'No'}"
        msg += f" {self.occupied_by.scope.label} {self.occupied_by.address}" if self.occupied_by else ""
        msg += f" {self.direction.name.lower()}" if self.direction else ""
        return f"Block {msg}"

    def update(self, command: L | P) -> None:
        from ..pdi.block_req import BlockReq
        from .component_state_store import ComponentStateStore

        if command:
            with self._cv:
                super().update(command)
                if isinstance(command, BlockReq):
                    self._block_req = command
                    self._block_id = command.block_id
                    self._flags = command.flags
                    self._occupied = command.is_occupied
                    self._direction = command.motive_direction
                    if self._sensor_track is None and command.sensor_track_id:
                        self._sensor_track = ComponentStateStore.get_state(CommandScope.IRDA, command.sensor_track_id)
                    if self._switch is None and command.switch_id:
                        self._switch = ComponentStateStore.get_state(CommandScope.SWITCH, command.switch_id)
                    if command.motive_id:
                        self._occupied_by = ComponentStateStore.get_state(command.motive_scope, command.motive_id)
                    else:
                        self._occupied_by = None
                    self.changed.set()
                    self._cv.notify_all()

    @property
    def is_known(self) -> bool:
        return self._block_req is not None

    @property
    def is_tmcc(self) -> bool:
        return False

    @property
    def is_legacy(self) -> bool:
        return False

    @property
    def is_lcs(self) -> bool:
        return False

    @property
    def block_id(self) -> int:
        return self._block_id

    @property
    def flags(self) -> int:
        return self._flags

    @property
    def is_occupied(self) -> bool:
        return self._occupied

    @property
    def occupied_by(self) -> TrainState | EngineState:
        return self._occupied_by

    @property
    def direction(self) -> Direction:
        return self._direction

    @property
    def sensor_track(self) -> IrdaState:
        return self._sensor_track

    @property
    def switch(self) -> SwitchState:
        return self._switch

    @property
    def prev_block(self) -> BlockState:
        return self._prev_block

    @property
    def next_block(self) -> BlockState:
        return self._next_block

    def as_bytes(self) -> bytes:
        from ..pdi.block_req import BlockReq

        return BlockReq(self).as_bytes

    def as_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "name": self.road_name,
            "is_occupied": self.is_occupied,
        }


SCOPE_TO_STATE_MAP: [CommandScope, ComponentState] = {
    CommandScope.ACC: AccessoryState,
    CommandScope.BASE: BaseState,
    CommandScope.BLOCK: BlockState,
    CommandScope.ENGINE: EngineState,
    CommandScope.IRDA: IrdaState,
    CommandScope.ROUTE: RouteState,
    CommandScope.SWITCH: SwitchState,
    CommandScope.SYNC: SyncState,
    CommandScope.TRAIN: TrainState,
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

    def __missing__(self, key: CommandScope | Tuple[CommandScope, int]) -> ComponentStateDict:
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
    def __init__(self, scope: CommandScope):
        super().__init__()  # base class doesn't get a factory
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
