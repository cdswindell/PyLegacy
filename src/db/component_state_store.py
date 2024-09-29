from typing import List, TypeVar

from src.comm.command_listener import CommandListener, Message, Topic
from src.db.component_state import ComponentStateDict, SystemStateDict, SCOPE_TO_STATE_MAP, ComponentState
from src.protocol.constants import CommandScope, BROADCAST_ADDRESS
from src.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_VALID_BAUDRATES

T = TypeVar("T", bound=ComponentState)


class ComponentStateStore:
    def __init__(self,
                 topics: List[str | CommandScope] = None,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if baudrate not in DEFAULT_VALID_BAUDRATES:
            raise ValueError(f'Baudrate {baudrate} is not valid')
        self._baudrate = baudrate
        self._port = port
        self._state: dict[CommandScope, ComponentStateDict] = SystemStateDict()
        # create command listener and install listeners
        self._listener = CommandListener(baudrate=self._baudrate, port=self._port)
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
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def port(self) -> str:
        return self._port

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