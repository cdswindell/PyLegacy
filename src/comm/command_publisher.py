from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol

from src.protocol.command_def import CommandDefEnum
from src.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandDef
from src.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef


class Subscriber[Message](Protocol):
    def __call__(self, message: Message) -> None:
        ...


@dataclass(slots=True, repr=False, kw_only=True)
class Channel[Message]:
    subscribers: set[Subscriber[Message]] = field(default_factory=set)

    def subscribe(self, subscriber: Subscriber[Message]) -> None:
        self.subscribers.add(subscriber)

    def unsubscribe(self, subscriber: Subscriber[Message]) -> None:
        self.subscribers.remove(subscriber)

    def publish(self, message: str) -> None:
        for subscriber in self.subscribers:
            subscriber(message)


@dataclass(slots=True)
class CommandPublisher[Message]:
    channels: dict[CommandDefEnum, Channel[Message]] = field(default_factory=lambda: defaultdict(Channel))

    def publish(self, channel_name: CommandDefEnum, message: Message) -> None:
        self.channels[channel_name].publish(message)

    def publish_all(self, message: Message) -> None:
        for channel in self.channels.values():
            channel.publish(message)

    def subscribe(self, channel_name: CommandDefEnum, subscriber: Subscriber) -> None:
        self.channels[channel_name].subscribe(subscriber)

    def subscribe_all(self, subscriber: Subscriber) -> None:
        for channel in self.channels.values():
            channel.subscribe(subscriber)

    def unsubscribe(self, channel_name: CommandDefEnum, subscriber: Subscriber) -> None:
        self.channels[channel_name].unsubscribe(subscriber)

    def unsubscribe_all(self, subscriber: Subscriber) -> None:
        for channel in self.channels.values():
            channel.unsubscribe(subscriber)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.channels})"


class EmailSubscriber:
    def __init__(self, email: str):
        self.email = email

    def __call__(self, message: str):
        print(f"Sending email to {self.email}: {message}")


def main() -> None:
    publisher = CommandPublisher()
    email_subscriber = EmailSubscriber('arjan@arjancodes.com')

    spam = publisher.channels[TMCC2EngineCommandDef.ABSOLUTE_SPEED]
    eggs = publisher.channels[TMCC1AuxCommandDef.AUX1_OPTION_ONE]
    bacon = publisher.channels[TMCC1AuxCommandDef.AUX2_OPTION_ONE]

    # Subscribing to channels
    spam.subscribe(email_subscriber)
    eggs.subscribe(email_subscriber)

    # Publishing messages
    spam.publish('Hello, spam subscribers!')
    eggs.publish('Hello, eggs subscribers!')
    bacon.publish('Hello, bacon subscribers!')

    # Unsubscribe
    spam.unsubscribe(email_subscriber)

    # Publishing after unsubscription
    spam.publish('Hello again, spam subscribers!')
    eggs.publish('Hello again, spam subscribers!')


if __name__ == '__main__':
    main()
