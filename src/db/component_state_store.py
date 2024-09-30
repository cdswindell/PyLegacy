from __future__ import annotations

import threading
from collections import defaultdict
from typing import List, TypeVar, Set

from src.comm.command_listener import CommandListener, Message, Topic, CommandDispatcher
from src.db.component_state import ComponentStateDict, SystemStateDict, SCOPE_TO_STATE_MAP, ComponentState
from src.protocol.command_def import CommandDefEnum
from src.protocol.constants import CommandScope, BROADCAST_ADDRESS

from ..protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandDef as Halt1
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandDef as Engine1
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandDef as Aux
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchState as Switch

from ..protocol.tmcc2.tmcc2_constants import TMCC2HaltCommandDef as Halt2
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef as Engine2

T = TypeVar("T", bound=ComponentState)
C = TypeVar("C", bound=CommandDefEnum)
E = TypeVar("E", bound=CommandDefEnum)


class ComponentStateStore:
    _instance: ComponentStateStore = None
    _lock = threading.RLock()

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_running(cls) -> bool:
        # noinspection PyProtectedMember
        return cls._instance is not None and cls._instance._listener.is_running

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

    def __init__(self,
                 topics: List[str | CommandScope] = None,
                 listener: CommandListener | CommandDispatcher = None) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        self._listener = listener
        self._state: dict[CommandScope, ComponentStateDict] = SystemStateDict()
        if topics:
            for topic in topics:
                if self.is_valid_topic(topic):
                    self._listener.listen_for(self, topic)
                else:
                    raise TypeError(f'Topic {topic} is not valid')

    def __call__(self, command: Message) -> None:
        """
            Callback, per the Subscriber protocol in CommandListener
        """
        if command:
            if command.is_halt:  # send to all known devices
                for scope in self._state:
                    for address in self._state[scope]:
                        self._state[scope][address].update(command)
            elif command.is_system_halt:  # send to all known engines and trains
                for scope in self._state:
                    if scope in [CommandScope.ENGINE, CommandScope.TRAIN]:
                        for address in self._state[scope]:
                            self._state[scope][address].update(command)
            elif command.scope in SCOPE_TO_STATE_MAP:
                if command.address == BROADCAST_ADDRESS:  # broadcast address
                    for address in self._state[command.scope]:
                        self._state[command.scope][address].update(command)
                else:  # update the device state (identified by scope/address)
                    self._state[command.scope][command.address].update(command)

    @property
    def is_empty(self) -> bool:
        return len(self._state) == 0

    @staticmethod
    def is_valid_topic(topic: Topic) -> bool:
        return isinstance(topic, CommandScope) or \
            (isinstance(topic, tuple) and len(topic) > 1 and isinstance(topic[0], CommandScope))

    def listen_for(self, topics: Topic | List[Topic]) -> None:
        if isinstance(topics, list):
            for topic in topics:
                if self.is_valid_topic(topic):
                    self._listener.listen_for(self, topic)
        else:
            if self.is_valid_topic(topics):
                self._listener.listen_for(self, topics)

    def query(self, scope: CommandScope, address: int) -> T | None:
        if scope in self._state:
            if address in self._state[scope]:
                return self._state[scope][address]
        else:
            return None


class CausesCache:
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
    def __init__(self) -> None:
        self._causes: dict[C, set[E]] = defaultdict(set)
        self._caused_bys: dict[E, Set[C]] = defaultdict(set)
        self.initialize()

    def causes(self, cause: C, *causes: E) -> None:
        for result in causes:
            self._causes[cause].add(result)
            self._caused_bys[result].add(cause)

    def is_caused_by(self, command: C) -> List[E]:
        if command in self._caused_bys:
            return list(self._caused_bys[command])
        else:
            return []

    def results_in(self, command: E) -> List[C]:
        if command in self._causes:
            return list(self._causes[command])
        else:
            return []

    def initialize(self) -> None:
        self._causes.clear()
        self._caused_bys.clear()

        # Halt command
        self.causes(Halt1.HALT,
                    Engine1.SPEED_STOP_HOLD,
                    Engine2.SPEED_STOP_HOLD,
                    Aux.AUX2_OFF,
                    Aux.AUX1_OFF)
        # Engine commands, starting with Reset (Number 0)
        self.causes(Engine2.RESET,
                    Engine2.SPEED_STOP_HOLD,
                    Engine2.FORWARD_DIRECTION,
                    Engine2.START_UP_DELAYED,
                    Engine2.BELL_OFF,
                    Engine2.DIESEL_RPM)
        self.causes(Engine2.FORWARD_DIRECTION,
                    Engine2.SPEED_STOP_HOLD,
                    Engine2.FORWARD_DIRECTION)
        self.causes(Engine2.REVERSE_DIRECTION,
                    Engine2.SPEED_STOP_HOLD,
                    Engine2.REVERSE_DIRECTION)
        self.causes(Engine2.TOGGLE_DIRECTION,
                    Engine2.SPEED_STOP_HOLD)
