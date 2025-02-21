from __future__ import annotations

import collections
import logging
import threading
from collections import defaultdict
from typing import List, TypeVar, Set, Tuple

from .component_state import ComponentStateDict, SystemStateDict, SCOPE_TO_STATE_MAP, ComponentState
from ..comm.comm_buffer import CommBuffer
from ..comm.command_listener import CommandListener, Message, Topic, Subscriber
from ..db.client_state_listener import ClientStateListener
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, BROADCAST_ADDRESS
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl as Effects
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum as Aux
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum as Engine1
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum as Switch
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as Engine2

log = logging.getLogger(__name__)

T = TypeVar("T", bound=ComponentState)
C = TypeVar("C", bound=CommandDefEnum)
E = TypeVar("E", bound=CommandDefEnum)


class ComponentStateStore:
    _instance: ComponentStateStore = None
    _lock = threading.RLock()

    @classmethod
    def build(
        cls,
        topics: List[str | CommandScope] = None,
        listeners: Tuple = None,
        is_base: bool = False,
        is_ser2: bool = False,
    ) -> ComponentStateStore:
        """
        Factory method to create a ComponentStateStore instance
        """
        return ComponentStateStore(topics, listeners, is_base=is_base, is_ser2=is_ser2)

    @classmethod
    def is_built(cls) -> bool:
        return cls._instance is not None

    @classmethod
    def get_state(cls, scope: CommandScope, address: int, create: bool = True) -> T | None:
        if cls._instance is None:
            raise AttributeError("ComponentStateStore not built")
        if create:
            return cls._instance._state[scope][address]
        else:
            return cls._instance.query(scope, address)

    @classmethod
    def set_state(cls, scope: CommandScope, address: int, state: T) -> None:
        if cls._instance is None:
            raise AttributeError("ComponentStateStore not built")
        cls._instance._state[scope][address] = state

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance:
                cls._instance._state.clear()

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if ComponentStateStore._instance is None:
                ComponentStateStore._instance = super(ComponentStateStore, cls).__new__(cls)
                ComponentStateStore._instance._initialized = False
            return ComponentStateStore._instance

    def __init__(
        self,
        topics: List[str | CommandScope] = None,
        listeners: Tuple = None,
        is_base: bool = False,
        is_ser2: bool = False,
    ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        self._dependencies = DependencyCache.build()
        self._listeners = listeners
        self._state: dict[CommandScope, ComponentStateDict] = SystemStateDict()
        self._is_base = is_base
        self._is_ser2 = is_ser2
        self._filter_updates = is_base is True and is_ser2 is True
        if topics:
            for topic in topics:
                if self.is_valid_topic(topic):
                    for listener in self._listeners:
                        listener.listen_for(self, topic)
                else:
                    raise TypeError(f"Topic {topic} is not valid")
        log.debug(self)

    def __repr__(self) -> str:
        return f"<ComponentStateStore Base: {self._is_base} Ser2: {self._is_ser2} Filtering: {self._filter_updates}>"

    def __contains__(self, scope: CommandScope) -> bool:
        return scope in self._state

    def __call__(self, command: Message) -> None:
        """
        Callback, per the Subscriber protocol in CommandListener
        """
        if command:
            if isinstance(command, CommandReq):
                if command.is_halt:  # send to all known devices
                    if self._filter_updates and command.is_filtered:
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"Command {command} is suppressed")
                    else:
                        for scope in self._state:
                            for address in self._state[scope]:
                                self._state[scope][address].update(command)
                        return
                elif command.is_system_halt:  # send to all known engines and trains
                    for scope in self._state:
                        if scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                            for address in self._state[scope]:
                                self._state[scope][address].update(command)
                    return
            if command.scope in SCOPE_TO_STATE_MAP:
                if self._filter_updates and command.is_filtered:
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"Command {command} is suppressed")
                else:
                    if command.address == BROADCAST_ADDRESS and command.scope != CommandScope.SYNC:  # broadcast address
                        for address in self._state[command.scope]:
                            self._state[command.scope][address].update(command)
                    else:  # update the device state (identified by scope/address)
                        self._state[command.scope][command.address].update(command)
            else:
                log.warning(f"Received Unknown State Update: {command.scope} {command}")

    @property
    def is_empty(self) -> bool:
        return len(self._state) == 0

    @property
    def is_base(self) -> bool:
        return self._is_base

    @property
    def is_ser2(self) -> bool:
        return self._is_ser2

    @property
    def is_filter_updates(self) -> bool:
        return self._filter_updates

    @staticmethod
    def is_valid_topic(topic: Topic) -> bool:
        return isinstance(topic, CommandScope) or (
            isinstance(topic, tuple) and len(topic) > 1 and isinstance(topic[0], CommandScope)
        )

    def listen_for(self, topics: Topic | List[Topic]) -> None:
        if isinstance(topics, list):
            for topic in topics:
                if self.is_valid_topic(topic):
                    for listener in self._listeners:
                        listener.listen_for(self, topic)
        else:
            if self.is_valid_topic(topics):
                for listener in self._listeners:
                    listener.listen_for(self, topics)

    def query(self, scope: CommandScope, address: int = None) -> T | List[T] | None:
        if scope in self._state:
            if address is None:
                return self.get_all(scope)
            elif address in self._state[scope]:
                return self._state[scope][address]
        else:
            return None

    def get_all(self, scope: CommandScope) -> List[T]:
        if scope in self._state:
            # ignore dups where we store an entry for the items road number
            valids = {v.address for k, v in self._state[scope].items()}
            states = [v for k, v in self._state[scope].items() if k in valids]
            states.sort(key=lambda x: x.address)
            return states
        else:
            return []

    def keys(self, scope: CommandScope = None) -> List[CommandScope] | List[int]:
        if scope is None:
            li = list(self._state.keys())
            li.sort(key=lambda x: x.label)
        elif scope in self._state:
            states = self.get_all(scope)
            li = list(s.address for s in states)
            li.sort()
        else:
            li = []
        return li

    def component(self, scope: CommandScope, address: int) -> T:
        if (
            (
                scope
                in {CommandScope.ACC, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.IRDA, CommandScope.ROUTE}
                and 1 <= address <= 99
            )
            or (scope == CommandScope.ENGINE and 1 <= address <= 9999)
            or (scope == CommandScope.BASE and address == 0)
        ):
            return self._state[scope][address]
        raise ValueError(f"Invalid scope/address: {scope} {address}")

    def scopes(self) -> Set[CommandScope]:
        return set(self._state.keys())

    def addresses(self, scope: CommandScope) -> collections.Iterable[int]:
        return set(self._state[scope].keys())


# noinspection DuplicatedCode
class DependencyCache:
    """
    Manages relationships between TMCC Commands. For example, sending the Reset command
    (number 0) to an engine causes the following results:
        - speed is set to zero
        - direction is set to Fwd
        - bell is disabled
        - engine rpm set to 0
        - engine labor set to 12
        - engine starts up immediately
    The reverse mapping, results to causes, is used to maintain a consistent state on a
    control panel. For example, if an indicator light specifies an engine is set to Rev,
    sending the reset command would turn that light off.
    """

    _instance: DependencyCache = None
    _lock = threading.RLock()

    @classmethod
    def build(cls) -> DependencyCache:
        """
        Factory method to create a ComponentStateStore instance
        """
        return DependencyCache()

    @classmethod
    def listen_for_enablers(cls, request: CommandReq, callback: Subscriber) -> List[E | Tuple[E, int]] | None:
        enablers = None
        if cls._instance is not None:
            if CommBuffer.is_server():
                listener = CommandListener.build()
            elif CommBuffer.is_client():
                listener = ClientStateListener.build()
            else:
                raise AttributeError("CommBuffer must be server or client")
            enablers = cls._instance.enabled_by(request.command, dereference_aliases=True, include_aliases=False)
            for enabler in enablers:
                if isinstance(enabler, tuple):
                    listener.listen_for(callback, request.scope, request.address, enabler[0], enabler[1])
                    listener.listen_for(callback, request.scope, BROADCAST_ADDRESS, enabler[0], enabler[1])
                else:
                    listener.listen_for(callback, request.scope, request.address, enabler)
                    listener.listen_for(callback, request.scope, BROADCAST_ADDRESS, enabler)
        return enablers

    @classmethod
    def listen_for_disablers(cls, request: CommandReq, callback: Subscriber) -> List[E | Tuple[E, int]] | None:
        disablers = None
        if cls._instance is not None:
            if CommBuffer.is_server():
                listener = CommandListener.build()
            elif CommBuffer.is_client():
                listener = ClientStateListener.build()
            else:
                raise AttributeError("CommBuffer must be server or client")
            disablers = cls._instance.disabled_by(request.command, dereference_aliases=True, include_aliases=False)
            for disabler in disablers:
                if isinstance(disabler, tuple):
                    listener.listen_for(callback, request.scope, request.address, disabler[0], disabler[1])
                    listener.listen_for(callback, request.scope, BROADCAST_ADDRESS, disabler[0], disabler[1])
                else:
                    listener.listen_for(callback, request.scope, request.address, disabler)
                    listener.listen_for(callback, request.scope, BROADCAST_ADDRESS, disabler)
        return disablers

    def __init__(self) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        self._causes: dict[C, set[E]] = defaultdict(set)
        self._caused_bys: dict[E, Set[C]] = defaultdict(set)
        self._toggles: dict[C, set[E]] = defaultdict(set)
        self._toggled_by: dict[E, set[C]] = defaultdict(set)
        self.initialize()

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if DependencyCache._instance is None:
                DependencyCache._instance = super(DependencyCache, cls).__new__(cls)
                DependencyCache._instance._initialized = False
            return DependencyCache._instance

    @staticmethod
    def _harvest_commands(commands: Set[E], dereference_aliases: bool, include_aliases: bool) -> Set[E]:
        cmd_set = set()
        for cmd in commands:
            if isinstance(cmd, CommandDefEnum) and cmd.is_alias:
                if include_aliases is True:
                    cmd_set.add(cmd)
                if dereference_aliases is True:
                    cmd_set.add(cmd.alias)
            else:
                cmd_set.add(cmd)
        return cmd_set

    def causes(self, cause: C, *results: E) -> None:
        """
        Define the results that are triggered when a cause command occurs
        """
        for result in results:
            self._causes[cause].add(result)
            self._caused_bys[result].add(cause)
        # if the cause is an aliased command, register the base command
        if isinstance(cause, CommandDefEnum) and cause.is_alias and hasattr(cause, "alias") and cause.alias is not None:
            self.causes(cause.alias, *results)

    def caused_by(self, command: E, dereference_aliases: bool = False, include_aliases: bool = True) -> Set[C]:
        """
        Returns a list of CommandDefEnums that can cause the given command to be issued.
        These commands should be "listened for" to as indicators for this state change
        """
        if command in self._caused_bys:
            causes = self._harvest_commands(self._caused_bys[command], dereference_aliases, include_aliases)
            if command not in causes:
                # noinspection PyTypeChecker
                causes.update(self._harvest_commands({command}, dereference_aliases, include_aliases))
            return causes
        else:
            return {command}

    def results_in(self, command: C, dereference_aliases: bool = False, include_aliases: bool = True) -> Set[E]:
        """
        Returns a list of the CommandDefEnums that result from issuing the given command.
        """
        if command in self._causes:
            results = self._harvest_commands(self._causes[command], dereference_aliases, include_aliases)
            if command not in results:
                # noinspection PyTypeChecker
                results.update(self._harvest_commands({command}, dereference_aliases, include_aliases))
            return results
        elif isinstance(command, CommandDefEnum) and command.is_alias and command.alias in self._causes:
            results = self._harvest_commands(self._causes[command.alias], dereference_aliases, include_aliases)
            if command.is_alias not in results:
                results.update(self._harvest_commands({command.alias}, dereference_aliases, include_aliases))
            return results
        else:
            return {command}

    def enabled_by(
        self, command: C, dereference_aliases: bool = False, include_aliases: bool = True
    ) -> List[E | Tuple[E, int]]:
        return list(self._harvest_commands(self.caused_by(command), dereference_aliases, include_aliases))

    def disabled_by(
        self, command: C, dereference_aliases: bool = False, include_aliases: bool = True
    ) -> List[E | Tuple[E, int]]:
        disabled = set()
        if command in self._toggles:
            disabled.update(self._harvest_commands(self._toggles[command], dereference_aliases, include_aliases))
            for state in list(disabled):  # as we may add items, we need to loop over as copy
                disabled.update(self._harvest_commands(self.caused_by(state), dereference_aliases, include_aliases))
        return list(disabled)

    def toggles(self, actor: C, *toggles: E) -> None:
        for toggled in toggles:
            self._toggles[actor].add(toggled)
            self._toggled_by[toggled].add(actor)

    def initialize(self) -> None:
        self._causes.clear()
        self._caused_bys.clear()

        # define command relationships
        # self.causes(Halt1.HALT, Engine1.SPEED_STOP_HOLD, Engine2.SPEED_STOP_HOLD, Aux.AUX2_OFF, Aux.AUX1_OFF)
        # self.causes(Halt2.HALT, Engine2.SPEED_STOP_HOLD)
        self.causes(Engine2.SYSTEM_HALT, Engine2.SPEED_STOP_HOLD)

        # Engine commands, starting with Reset (Number 0)
        self.causes(
            Engine2.RESET,
            Engine2.STOP_IMMEDIATE,
            Engine2.FORWARD_DIRECTION,
            Engine2.START_UP_IMMEDIATE,
            Engine2.BELL_OFF,
            Engine2.DIESEL_RPM,
            Engine2.ENGINE_LABOR_DEFAULT,
            Engine2.NUMERIC,
        )
        self.causes(
            Engine2.STOP_IMMEDIATE,
            Engine2.SPEED_STOP_HOLD,
            Engine2.DIESEL_RPM,
            Engine2.ENGINE_LABOR_DEFAULT,
        )
        self.causes(
            Engine2.FORWARD_DIRECTION,
            Engine2.STOP_IMMEDIATE,
            Engine2.SPEED_STOP_HOLD,
            Engine2.DIESEL_RPM,
            Engine2.ENGINE_LABOR_DEFAULT,
        )
        self.causes(
            Engine2.REVERSE_DIRECTION,
            Engine2.STOP_IMMEDIATE,
            Engine2.SPEED_STOP_HOLD,
            Engine2.DIESEL_RPM,
            Engine2.ENGINE_LABOR_DEFAULT,
        )
        self.causes(
            Engine2.TOGGLE_DIRECTION,
            Engine2.STOP_IMMEDIATE,
            Engine2.SPEED_STOP_HOLD,
            Engine2.DIESEL_RPM,
            Engine2.ENGINE_LABOR_DEFAULT,
        )

        self.causes(
            Engine2.SHUTDOWN_IMMEDIATE,
            Engine2.SPEED_STOP_HOLD,
            Engine2.STOP_IMMEDIATE,
            Engine2.DIESEL_RPM,
            Engine2.ENGINE_LABOR_DEFAULT,
        )

        # TMCC1 Engine Reset
        self.causes(
            Engine1.RESET,
            Engine1.SPEED_STOP_HOLD,
            Engine1.FORWARD_DIRECTION,
            Engine1.RPM_DOWN,
            Engine1.NUMERIC,
        )
        self.causes(Engine1.FORWARD_DIRECTION, Engine1.SPEED_STOP_HOLD)
        self.causes(Engine1.REVERSE_DIRECTION, Engine1.SPEED_STOP_HOLD)
        self.causes(Engine1.TOGGLE_DIRECTION, Engine1.SPEED_STOP_HOLD)

        # define command toggles; commands that are essentially mutually exclusive
        self.toggles(Switch.OUT, Switch.THRU)
        self.toggles(Switch.THRU, Switch.OUT)

        self.toggles(Aux.AUX1_OPT_ONE, Aux.AUX2_OPT_ONE)
        self.toggles(Aux.AUX2_OPT_ONE, Aux.AUX1_OPT_ONE)

        self.toggles(Engine2.FORWARD_DIRECTION, Engine2.REVERSE_DIRECTION)
        self.toggles(Engine2.REVERSE_DIRECTION, Engine2.FORWARD_DIRECTION)

        self.toggles(Effects.SMOKE_OFF, Effects.SMOKE_LOW, Effects.SMOKE_MEDIUM, Effects.SMOKE_HIGH)
        self.toggles(Effects.SMOKE_LOW, Effects.SMOKE_OFF, Effects.SMOKE_MEDIUM, Effects.SMOKE_HIGH)
        self.toggles(Effects.SMOKE_MEDIUM, Effects.SMOKE_LOW, Effects.SMOKE_OFF, Effects.SMOKE_HIGH)
        self.toggles(Effects.SMOKE_HIGH, Effects.SMOKE_LOW, Effects.SMOKE_MEDIUM, Effects.SMOKE_OFF)
