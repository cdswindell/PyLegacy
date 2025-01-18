from __future__ import annotations

import abc
import logging
import threading
from abc import ABC
from collections import defaultdict
from time import time
from typing import Tuple, TypeVar, Set, Any


from ..comm.comm_buffer import CommBuffer
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
)
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

STARTUP_SET = {TMCC2EngineCommandEnum.START_UP_IMMEDIATE, TMCC2EngineCommandEnum.START_UP_DELAYED}

SHUTDOWN_SET = {
    TMCC1EngineCommandEnum.SHUTDOWN_DELAYED,
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

BIG_NUMBER = float("inf")


# noinspection PyUnresolvedReferences
class ComponentState(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        self._scope = scope
        self._last_command: CommandReq | None = None
        self._last_command_bytes = None
        self._last_updated: float | None = None
        self._road_name = None
        self._road_number = None
        self._number = None
        self._address: int | None = None
        self._spare_1: int | None = None
        self._ev = threading.Event()
        self._cv = threading.Condition()

        from .component_state_store import DependencyCache

        self._dependencies = DependencyCache.build()

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
    def changed(self) -> threading.Event:
        return self._ev

    @property
    def synchronizer(self) -> threading.Condition:
        return self._cv

    @property
    def road_name(self) -> str | None:
        return self._road_name

    @property
    def road_number(self) -> str | None:
        return self._road_number

    @property
    def name(self) -> str:
        the_name = "#" + self.road_number if self.road_number else ""
        the_name = self.road_name + " " + the_name if self.road_name else "NA"
        return the_name

    @property
    def spare_1(self) -> int:
        return self._spare_1

    @abc.abstractmethod
    def update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq

        self.changed.clear()
        if command and command.command != TMCC1HaltCommandEnum.HALT:
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
            if (isinstance(command, BaseReq) and command.status == 0) or isinstance(command, IrdaReq):
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
        if self._last_updated:
            return time() - self._last_updated

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
            with self._cv:
                super().update(command)
                if command.command == TMCC1HaltCommandEnum.HALT:
                    return
                if isinstance(command, CommandReq):
                    if command.command != Switch.SET_ADDRESS:
                        self._state = command.command
                elif isinstance(command, Asc2Req) or isinstance(command, Stm2Req):
                    self._state = Switch.THROUGH if command.is_thru else Switch.OUT
                elif isinstance(command, BaseReq):
                    pass
                else:
                    log.warning(f"Unhandled Switch State Update received: {command}")
                self.changed.set()
                self._cv.notify_all()

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

    def as_bytes(self) -> bytes:
        from ..pdi.base_req import BaseReq

        byte_str = BaseReq(self.address, PdiCommand.BASE_SWITCH, state=self).as_bytes
        if self.is_known:
            byte_str += CommandReq.build(self.state, self.address).as_bytes
        return byte_str


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
        self._number: int | None = None

    def __repr__(self) -> str:
        aux1 = aux2 = aux_num = ""
        if self._block_power:
            aux = f"Block Power {'ON' if self.aux_state == Aux.AUX1_OPT_ONE else 'OFF'}"
        elif self._sensor_track:
            aux = "Sensor Track"
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
                        if command.action in {Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                            self._block_power = True
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
        elif self._block_power:
            if isinstance(self._first_pdi_command, Asc2Action):
                byte_str += Asc2Req(
                    self.address,
                    self._first_pdi_command,
                    self._first_pdi_action,
                    values=1 if self._aux_state == Aux.AUX1_OPT_ONE else 0,
                ).as_bytes
            else:
                byte_str += Bpc2Req(
                    self.address,
                    self._first_pdi_command,
                    self._first_pdi_action,
                    state=1 if self._aux_state == Aux.AUX1_OPT_ONE else 0,
                ).as_bytes
        else:
            if self._aux_state is not None:
                byte_str += CommandReq.build(self.aux_state, self.address).as_bytes
            if self._aux1_state is not None:
                byte_str += CommandReq.build(self.aux1_state, self.address).as_bytes
            if self._aux2_state is not None:
                byte_str += CommandReq.build(self.aux2_state, self.address).as_bytes
        return byte_str


class EngineState(ComponentState):
    def __init__(self, scope: CommandScope = CommandScope.ENGINE) -> None:
        if scope not in {CommandScope.ENGINE, CommandScope.TRAIN}:
            raise ValueError(f"Invalid scope: {scope}, expected ENGINE or TRAIN")
        super().__init__(scope)
        self._start_stop: CommandDefEnum | None = None
        self._speed: int | None = None
        self._speed_limit: int | None = None
        self._max_speed: int | None = None
        self._direction: CommandDefEnum | None = None
        self._momentum: int | None = None
        self._smoke_level: int | None = None
        self._train_brake: int | None = None
        self._prod_year: int | None = None
        self._rpm: int | None = None
        self._labor: int | None = None
        self._control_type: int | None = None
        self._sound_type: int | None = None
        self._engine_type: int | None = None
        self._engine_class: int | None = None
        self._numeric: int | None = None
        self._numeric_cmd: CommandDefEnum | None = None
        self._aux: CommandDefEnum | None = None
        self._aux1: CommandDefEnum | None = None
        self._aux2: CommandDefEnum | None = None
        self._last_aux1_opt1 = None
        self._last_aux2_opt1 = None
        self._is_legacy: bool | None = None  # assume we are in TMCC mode until/unless we receive a Legacy cmd

    def __repr__(self) -> str:
        sp = dr = ss = name = num = mom = rl = yr = nu = lt = tb = aux = lb = ""
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
        # if self.engine_class is not None:
        #     cl = f" Class: {LOCO_CLASS.get(self.engine_class, 'NA')}"
        ct = f" {CONTROL_TYPE.get(self.control_type, 'NA')}"
        return f"{self.scope.title} {self._address:02}{sp}{rl}{lb}{mom}{tb}{dr}{nu}{aux}{name}{num}{lt}{ct}{yr}{ss}"

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
                    self._start_stop = self._harvest_effect(cmd_effects & STARTUP_SET)
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
                    if command.is_valid(EngineBits.CLASS_TYPE):
                        self._engine_class = command.loco_class_id
                    if command.is_valid(EngineBits.LOCO_TYPE):
                        self._engine_type = command.loco_type_id
                    if command.is_valid(EngineBits.SMOKE_LEVEL):
                        self._smoke_level = command.smoke_level
                    if command.is_valid(EngineBits.TRAIN_BRAKE):
                        self._train_brake = command.train_brake
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
    def speed_max(self) -> int:
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
    def engine_type(self) -> int:
        return self._engine_type

    @property
    def engine_class(self) -> int:
        return self._engine_class

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

    @staticmethod
    def _as_label(prop: Any) -> str:
        return f"{prop if prop is not None else 'NA'}"


class TrainState(EngineState):
    def __init__(self, scope: CommandScope = CommandScope.TRAIN) -> None:
        if scope != CommandScope.TRAIN:
            raise ValueError(f"Invalid scope: {scope}, expected TRAIN")
        super().__init__(scope)
        # hard code TMCC2, for now
        self._is_legacy = True
        self._control_type = 2


class IrdaState(LcsState):
    """
    Maintain the state of a Sensor Track (Irda)
    """

    def __init__(self, scope: CommandScope = CommandScope.IRDA) -> None:
        if scope != CommandScope.IRDA:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._sequence: IrdaSequence | None = None
        self._loco_rl: int | None = 255
        self._loco_lr: int | None = 255

    def __repr__(self) -> str:
        rle = f"{self._loco_rl}" if self._loco_rl and self._loco_rl != 255 else "Any"
        lre = f"{self._loco_lr}" if self._loco_lr and self._loco_lr != 255 else "Any"
        rl = f" When Engine ID (R -> L): {rle}"
        lr = f" When Engine ID (L -> R): {lre}"
        return f"Sensor Track {self.address}: Sequence: {self.sequence_str}{rl}{lr}"

    def update(self, command: P) -> None:
        from .component_state_store import ComponentStateStore

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

    def as_bytes(self) -> bytes:
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


SCOPE_TO_STATE_MAP: [CommandScope, ComponentState] = {
    CommandScope.SWITCH: SwitchState,
    CommandScope.ACC: AccessoryState,
    CommandScope.ENGINE: EngineState,
    CommandScope.TRAIN: TrainState,
    CommandScope.IRDA: IrdaState,
    CommandScope.BASE: BaseState,
    CommandScope.SYNC: SyncState,
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
        self._lock = threading.Lock()

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
