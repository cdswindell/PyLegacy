#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
#

from __future__ import annotations

import csv
import logging
import threading
from abc import ABC, ABCMeta, abstractmethod
from collections import defaultdict
from enum import Enum, auto
from threading import Condition, Event, RLock
from time import monotonic
from typing import Any, Dict, List, Self, Set, TextIO, TypeVar

from .comp_data import CompData, CompDataMixin
from ..pdi.asc2_req import Asc2Req
from ..pdi.constants import PdiCommand
from ..pdi.d4_req import D4Req
from ..pdi.irda_req import IrdaReq
from ..pdi.lcs_req import LcsReq
from ..pdi.pdi_req import PdiReq
from ..pdi.stm2_req import Stm2Req
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import (
    BROADCAST_ADDRESS,
    CommandScope,
    CommandSyntax,
    Mixins,
)
from ..protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum, TMCC1SwitchCommandEnum as Switch
from ..utils.text_utils import title

log = logging.getLogger(__name__)

C = TypeVar("C", bound=CommandDefEnum)
E = TypeVar("E", bound=CommandDefEnum)
P = TypeVar("P", bound=PdiReq)
L = TypeVar("L", bound=CommandReq)

BIG_NUMBER = float("inf")


class UpdateResult(Enum):
    UPDATED = auto()
    NO_CHANGE = auto()
    IGNORED = auto()


class LcsComponent(Mixins):
    IRDA = 0
    WIFI = 2
    SER2 = 3
    ASC2 = 4
    BPC2 = 5
    AMC2 = 6
    STM2 = 8


BASE3_SCOPES = {
    CommandScope.TRAIN,
    CommandScope.ENGINE,
    CommandScope.SWITCH,
    CommandScope.ACC,
    CommandScope.SWITCH,
}


# noinspection PyUnresolvedReferences
class ComponentState(ABC, CompDataMixin):
    __metaclass__ = ABCMeta

    @classmethod
    def get_cvs_dict_writer(
        cls, scope: CommandScope, csvfile: TextIO, *, include_state: bool = False
    ) -> csv.DictWriter:
        state_class = SCOPE_TO_STATE_MAP.get(scope, None)
        if state_class is None:
            raise ValueError(f"Unsupported scope: {scope.name if scope else 'None'}")
        return csv.DictWriter(csvfile, fieldnames=state_class._csv_headers(include_state=include_state))

    @classmethod
    def _csv_headers(cls, include_state: bool = False) -> list[str]:
        return ["address", "road_number", "road_name"]

    @abstractmethod
    def __init__(self, scope: CommandScope = None) -> None:
        from .component_state_store import DependencyCache

        super().__init__()
        self._cv: Condition = Condition(RLock())
        self._ev = Event()
        self._is_known: bool = False
        self._scope = scope
        self._this_command: CommandReq | None = None
        self._last_command: CommandReq | None = None
        self._last_command_bytes = None
        self._last_updated: float | None = None
        self._road_name = None
        self._road_number = None
        self._number = None
        self._address: int | None = None
        self._spare_1: int | None = None
        self._dependencies = DependencyCache.build()
        self._config_requested = False
        self._deleted = False

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

    def as_csv(self, include_state: bool = False) -> dict[str, str | int | None]:
        return {
            "address": self._address,
            "road_number": self.road_number,
            "road_name": self.road_name,
        }

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
    def is_deleted(self) -> bool:
        return self._deleted

    @property
    def is_deletable(self) -> bool:
        """
        LCS device state should override to return False
        """
        return True

    @property
    def road_name(self) -> str | None:
        return self._road_name if self._road_name else self.moniker

    @property
    def is_road_name(self) -> bool:
        return bool(self._road_name)

    @property
    def road_number(self) -> str | None:
        return self._road_number if self._road_number else str(self._address)

    @property
    def is_road_number(self) -> bool:
        return bool(self._road_number)

    @property
    def name(self) -> str:
        if self.is_road_name or self.is_road_number:
            the_name = " #" + self._road_number if self._road_number else ""
            the_name = self._road_name + the_name if self._road_name else "NA"
        else:
            the_name = f"{self.moniker} {self._address}"
        return the_name

    @property
    def is_name(self) -> bool:
        return self.is_road_name or self.is_road_number

    @property
    def payload(self) -> str:
        return ""

    @property
    def moniker(self) -> str:
        return self.scope.title

    @property
    def spare_1(self) -> int:
        return self._spare_1

    @property
    def prev_link(self) -> int:
        if self._comp_data and 1 <= self.tmcc_id <= 101:
            return self._comp_data.prev_link
        return 0xFF

    @property
    def next_link(self) -> int:
        if self._comp_data and 1 <= self.tmcc_id <= 101:
            return self._comp_data.next_link
        return 0xFF

    def is_synchronized(self) -> bool:
        from .component_state_store import ComponentStateStore
        from .sync_state import SyncState

        if isinstance(self, SyncState):
            return self.is_synchronized()
        else:
            return ComponentStateStore.is_state_synchronized()

    def is_synchronizing(self) -> bool:
        from .component_state_store import ComponentStateStore
        from .sync_state import SyncState

        if isinstance(self, SyncState):
            return self.is_synchronizing()
        else:
            return ComponentStateStore.is_state_synchronizing()

    @abstractmethod
    def _update_state(self, command: L | P) -> UpdateResult:
        return UpdateResult.UPDATED

    def update(self, command: L | P) -> None:
        if command is None:
            return

        with self.synchronizer:
            self.changed.clear()
            self._prepare_update(command)  # current base-class validation/setup
            result = self._update_state(command)  # subclass-specific behavior

            if result == UpdateResult.IGNORED:
                return

            self._complete_update(command, notify=result != UpdateResult.NO_CHANGE)

    def _complete_update(self, command: L | P, notify: bool = True) -> None:
        self._last_updated = monotonic()
        self._last_command = command

        if notify:
            self.changed.set()
            self.synchronizer.notify_all()

    # noinspection PyTypeChecker
    def _prepare_update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq
        from ..pdi.block_req import BlockReq
        from ..pdi.d4_req import D4Req

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

            # have we received the initial configuration from Base 3?
            # if we haven't, and this command isn't a configuration record,
            # request configuration
            if self.is_comp_data_empty and self.scope in BASE3_SCOPES:
                # initialize comp data, if it's empty
                if not self.is_comp_data_record:
                    self.initialize(self.scope, self.tmcc_id)
                if not (isinstance(command, BaseReq) and command.is_comp_data_record):
                    self.request_config(command)

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
                            # Persists component state when conditions are satisfied
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

    def request_config(self, command: CommandReq):
        from ..comm.comm_buffer import CommBuffer
        from ..pdi.base_req import BaseReq

        # Only request config if we're synchronized and running on the server
        if self.is_synchronized() and CommBuffer.is_server():
            # print(f"Request config for component {self}? prior: {self._config_requested}")
            if not self._config_requested:
                scope = command.scope
                # if we're synchronized, this component may be new; request initial config
                if not self.is_comp_data_record and scope in BASE3_SCOPES:
                    self.initialize(scope, self.tmcc_id)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"{scope} {command.address} not known, will request config and retry {command}...")
                if 1 <= command.address < 99:
                    BaseReq(command.address, PdiCommand.BASE_MEMORY, scope=scope).send()
                elif 100 <= command.address <= 9999:
                    if self.record_no is not None:
                        cmd = PdiCommand.D4_TRAIN if scope == CommandScope.TRAIN else PdiCommand.D4_ENGINE
                        D4Req(self.record_no, cmd).send()
                self._config_requested = True
                # print("***** Config request sent...")
            else:
                # print("***** Config already requested...")
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Config for {self.scope.title} {self.tmcc_id} already requested")

    def clear(self, notify: bool = True, clear_db: bool = False):
        """
        Deletes the component state from the store. Optionally, clears the
        corresponding Base 3 database record
        """
        from .component_state_store import ComponentStateStore

        with self._cv:
            if not self.is_deletable:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Component state {self} is not deletable")
                return
            ComponentStateStore.delete_state(self)
            self._deleted = True

            # hold lock while we determine if Base 3 record should be cleared as well
            clear_db = clear_db and isinstance(self, CompDataMixin) and self.is_comp_data_record

            if notify:
                self.changed.set()
                self.synchronizer.notify_all()

        if clear_db:
            self.clear_record(self)

    @staticmethod
    def schedule_call(delay_seconds, func, *args, **kwargs):
        """Schedules a function call after a specified delay."""
        timer = threading.Timer(delay_seconds, func, args=args, kwargs=kwargs)
        timer.start()

    @property
    def last_updated_ago(self) -> float:
        if self._last_updated is not None:
            return monotonic() - self._last_updated
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
            req = BaseReq(self.address, PdiCommand.BASE_MEMORY, scope=self.scope, state=self)
            return req.as_bytes if req.data_bytes else bytes()

    def _update_comp_data(self, comp_data: CompData):
        with self._cv:
            self._comp_data = comp_data
            self._comp_data_record = True
            self._empty = False if comp_data and comp_data.is_comp_data_empty else True

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
    def is_lcs(self) -> bool:
        if hasattr(self, "_parent") and self._parent:
            return self._parent.is_lcs
        if hasattr(self, "_pdi_source"):
            return self._pdi_source
        return False

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

    def _update_state(self, command: L | P) -> UpdateResult:
        return super()._update_state(command)

    def as_dict(self) -> Dict[str, Any]:
        return super()._as_dict()


class LcsState(ComponentState, ABC):
    __metaclass__ = ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        super().__init__(scope)
        self._config_req_count = 0
        self._config_req = self._status_req = self._info_req = self._firmware_req = self._control_req = None

    def _update_state(self, command: P) -> UpdateResult:
        if isinstance(command, LcsReq):
            if command.is_config_req:
                self._config_req = command
                self._config_req_count += 1
            elif command.is_firmware_req:
                self._firmware_req = command
            elif command.is_info_req:
                self._info_req = command
            elif command.is_status_req:
                self._status_req = command
            elif command.is_control_req:
                self._control_req = command
        return super()._update_state(command)

    def as_bytes(self) -> bytes:
        byte_str = super().as_bytes()
        if self._config_req:
            byte_str += self._config_req.as_bytes
        if self._firmware_req:
            byte_str += self._firmware_req.as_bytes
        if self._info_req:
            byte_str += self._info_req.as_bytes
        return byte_str

    def as_dict(self) -> Dict[str, Any]:
        return super()._as_dict()

    @property
    def is_tmcc(self) -> bool:
        return False

    @property
    def is_legacy(self) -> bool:
        return True

    @property
    def is_deletable(self) -> bool:
        return False

    #
    # @property
    # def is_lcs(self) -> bool:
    #     return True

    @property
    def firmware(self) -> str:
        return self._firmware_req.firmware if self._firmware_req else "NA"

    @property
    def board_id(self) -> int | None:
        return self._info_req.board_id if self._info_req else None

    @property
    def num_ids(self) -> int | None:
        return self._info_req.num_ids if self._info_req else None

    @property
    def model(self) -> int | None:
        return self._info_req.model if self._info_req else None


class LcsProxyState(LcsState, ABC):
    __metaclass__ = ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        super().__init__(scope)
        self._parent = None
        self._pdi_source = False

    def _update_state(self, command: L | P) -> UpdateResult:
        if isinstance(command, LcsReq):
            self._pdi_source = True
        return super()._update_state(command)

    @property
    def accessory_type(self) -> str:
        if self.is_bpc2:
            return "LCS BPC2"
        elif self.is_amc2:
            return "LCS AMC2"
        elif self.is_asc2:
            return "LCS ASC2"
        elif self.is_stm2:
            return "LCS STM2"
        elif self.is_sensor_track:
            return "LCS Sensor Track"
        return "Accessory"

    @property
    def moniker(self) -> str:
        if self.is_bpc2:
            return "Power District"
        elif self.is_amc2:
            return "Motor Controller"
        elif self.is_stm2:
            return "Switch Sensor"
        elif self.is_sensor_track:
            return "Sensor Track"
        return "Accessory"

    @property
    def is_bpc2(self):
        from ..pdi.bpc2_req import Bpc2Req

        return isinstance(self._control_req, Bpc2Req) or isinstance(self._config_req, Bpc2Req)

    @property
    def is_power_district(self) -> bool:
        return self.is_bpc2

    @property
    def is_amc2(self):
        from ..pdi.amc2_req import Amc2Req

        return isinstance(self._control_req, Amc2Req) or isinstance(self._config_req, Amc2Req)

    @property
    def is_asc2(self):
        from ..pdi.asc2_req import Asc2Req

        return isinstance(self._control_req, Asc2Req) or isinstance(self._config_req, Asc2Req)

    @property
    def is_stm2(self):
        from ..pdi.stm2_req import Stm2Req

        return isinstance(self._control_req, Stm2Req) or isinstance(self._config_req, Stm2Req)

    @property
    def is_sensor_track(self):
        from ..pdi.irda_req import IrdaReq

        if self._parent:
            return (
                isinstance(self.parent._control_req, IrdaReq)
                or isinstance(self.parent._config_req, IrdaReq)
                or isinstance(self.parent._info_req, IrdaReq)
            )
        return (
            isinstance(self._control_req, IrdaReq)
            or isinstance(self._config_req, IrdaReq)
            or isinstance(self._info_req, IrdaReq)
        )

    @property
    def is_lcs_component(self) -> bool:
        return self.is_lcs

    @property
    def parent_id(self) -> int | None:
        if self._config_req:
            return self.address
        elif self._parent:
            return self._parent.address
        return None

    @property
    def parent(self) -> Self:
        return self._parent

    @property
    def is_deletable(self) -> bool:
        return False if self.is_lcs else ComponentState.is_deletable.fget(self)

    @property
    def firmware(self) -> str:
        if self._parent:
            return self._parent.firmware
        return self._firmware_req.firmware if self._firmware_req else "NA"

    @property
    def board_id(self) -> int | None:
        if self._parent:
            return self._parent.board_id
        return self._info_req.board_id if self._info_req else None

    @property
    def num_ids(self) -> int | None:
        if self._parent:
            return self._parent.num_ids
        return self._info_req.num_ids if self._info_req else None

    @property
    def model(self) -> int | None:
        if self._parent:
            return self._parent.model
        return self._info_req.model if self._info_req else None

    @property
    def mode(self) -> int:
        if self._parent:
            return self._parent.mode
        return self._config_req.mode if self._config_req and hasattr(self._config_req, "mode") else "NA"

    @property
    def port(self) -> int:
        if self._parent:
            return self.address - self._parent.address + 1
        else:
            return 1

    def as_bytes(self) -> bytes:
        byte_str = super().as_bytes()
        if self.is_lcs_component:
            if self._control_req:
                byte_str += self._control_req.as_bytes
        return byte_str

    def as_dict(self) -> Dict[str, Any]:
        return super()._as_dict()


class SwitchState(TmccState, LcsProxyState):
    """
    Maintain the perceived state of a Switch
    """

    @classmethod
    def _csv_headers(cls, include_state: bool = False) -> list[str]:
        cols = super()._csv_headers(include_state=include_state)
        cols.extend(["lcs", "port"])
        if include_state:
            cols.extend(["state"])
        return cols

    def __init__(self, scope: CommandScope = CommandScope.SWITCH) -> None:
        if scope != CommandScope.SWITCH:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._state: Switch | None = None
        self._routes: set[RouteState] = set()

    def as_csv(self, include_state: bool = False) -> dict[str, str | int | None]:
        data = super().as_csv(include_state=include_state)
        comp = LcsComponent.by_value(self.model)
        data["lcs"] = comp.name if comp else None
        data["port"] = self.port
        if include_state:
            data["state"] = "thru" if self.is_thru else "out" if self.is_out else "unknown"
        return data

    def _update_state(self, command: L | P) -> UpdateResult:
        # Dispatches state updates by command variant; notifies observers
        result = super()._update_state(command)
        handled = False
        if isinstance(command, CompDataMixin) and command.is_comp_data_record:
            self._update_comp_data(command.comp_data)
            handled = True
        elif isinstance(command, CommandReq):
            if command.command == TMCC1HaltCommandEnum.HALT:
                return UpdateResult.IGNORED
            elif command.command == Switch.SET_ADDRESS:
                return UpdateResult.NO_CHANGE
            elif not self._pdi_source:
                handled = True
                self._state = command.command
        elif isinstance(command, Asc2Req) or isinstance(command, Stm2Req):
            self._pdi_source = True
            self._state = Switch.THRU if command.is_thru else Switch.OUT
        else:
            log.warning(f"Unhandled Switch State Update received: {command}")

        # inform the routes that include this switch of new state
        self.update_route_state()
        return UpdateResult.UPDATED if handled else result

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
    def is_unknown(self) -> bool:
        return not self.is_through and not self.is_out

    @property
    def payload(self) -> str:
        sn = f"{self._state.name if self._state is not None else 'Unknown'}"
        if self.is_asc2:
            sn = f"ASC2 Port {self.port}: {sn}"
        if self.is_stm2:
            sn = f"STM2 Port {self.port}: {sn}"
        return sn

    def register_route(self, route: RouteState) -> None:
        self._routes.add(route)

    def update_route_state(self) -> None:
        for route in self._routes:
            route.update_switch_state(self)

    def as_bytes(self) -> bytes:
        """Converts object state to serialized byte representation"""
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
    from .components import RouteComponent

    """
    Maintain Route State
    """

    @classmethod
    def _csv_headers(cls, include_state: bool = False) -> list[str]:
        cols = super()._csv_headers(include_state=include_state)
        cols.extend(["switches", "subroutes"])
        if include_state:
            cols.extend(["aligned"])
        return cols

    def __init__(self, scope: CommandScope = CommandScope.ROUTE) -> None:
        if scope != CommandScope.ROUTE:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._routes: set[RouteState] = set()
        self._signature: dict[str, bool] = dict()
        self._current_state: dict[str, bool | None] = dict()

    def as_csv(self, include_state: bool = False) -> dict[str, str | int | None]:
        data = super().as_csv(include_state=include_state)
        di = self.as_dict()
        data["switches"] = len(di["switches"])
        data["subroutes"] = len(di["routes"])
        if include_state:
            data["aligned"] = self.is_aligned
        return data

    def _update_state(self, command: L | P) -> UpdateResult:
        from .comp_data import CompDataMixin

        if command:
            if command.command == TMCC1HaltCommandEnum.HALT:
                return UpdateResult.IGNORED
            with self.synchronizer:
                if isinstance(command, CompDataMixin) and command.is_comp_data_record:
                    self._update_comp_data(command.comp_data)
                    # set up callbacks so that changes to component switch states
                    # can real-time trigger updates to this route's state
                    comps = self.components
                    if comps:
                        from .component_state_store import ComponentStateStore

                        store = ComponentStateStore.get()
                        # Updates route state from switch and route components via store
                        for comp in comps:
                            self._signature.update(comp.as_signature)
                            if comp.is_switch:
                                switch = store.get_state(CommandScope.SWITCH, comp.tmcc_id, True)
                                if isinstance(switch, SwitchState):
                                    self._current_state.update(
                                        {f"S{switch.address}": switch.is_thru if switch.is_known else None}
                                    )
                                    switch.register_route(self)
                            elif comp.is_route:
                                route = store.get_state(CommandScope.ROUTE, comp.tmcc_id, True)
                                if isinstance(route, RouteState):
                                    self._current_state.update(
                                        {f"R{route.address}": route.is_active if route.is_known else None}
                                    )
                                    route.register_route(self)
                elif isinstance(command, CommandReq):
                    pass
                else:
                    log.warning(f"Unhandled Route State Update received: {command}")
            return UpdateResult.UPDATED
        return UpdateResult.IGNORED

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
    def is_aligned(self) -> bool:
        return self.is_active

    @property
    def is_not_active(self) -> bool:
        return not self.is_active and not self.is_unknown

    @property
    def is_unknown(self) -> bool:
        with self.synchronizer:
            return any(v is None for v in self._current_state.values())

    @property
    def as_signature(self) -> dict[str, bool]:
        return self._signature

    def register_route(self, route: RouteState):
        self._routes.add(route)

    def update_switch_state(self, switch: SwitchState) -> None:
        with self.synchronizer:
            self._current_state.update({f"S{switch.address}": switch.is_thru if switch.is_known else None})
            for route in self._routes:
                route.update_route_state(self)
            self.changed.set()
            self._cv.notify_all()

    def update_route_state(self, route: RouteState) -> None:
        with self.synchronizer:
            self._current_state.update({f"R{route.address}": route.is_active if route.is_known else None})
            self.changed.set()
            self._cv.notify_all()

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        d["active"] = self.is_active
        if self.components:
            sw = [
                {"switch": c.tmcc_id, "position": "thru" if c.is_thru is True else "out"}
                for c in self.components
                if c.is_switch
            ]
            rts = [{"route": c.tmcc_id} for c in self.components if c.is_route]
        else:
            sw = list()
            rts = list()
        d["switches"] = sw
        d["routes"] = rts
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
        elif self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} and (key < 1 or key > 9999):
            raise KeyError(f"Invalid ID: {key}")
        elif self.scope not in {CommandScope.BASE, CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SYNC} and (
            key < 1 or key > 99
        ):
            raise KeyError(f"Invalid ID: {key}")
        with self._lock:
            value: ComponentState = SCOPE_TO_STATE_MAP[self._scope](self._scope)
            value._address = key
            self[key] = value
            return self[key]


class RequestConfigurationException(Exception):
    pass
