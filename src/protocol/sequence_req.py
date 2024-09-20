from __future__ import annotations
from collections.abc import Sequence
from typing import List, Callable

from .command_def import CommandDefEnum, CommandDef
from .command_req import CommandReq
from .constants import CommandScope, DEFAULT_ADDRESS, CommandSyntax, DEFAULT_BAUDRATE, DEFAULT_PORT
from ..comm.comm_buffer import CommBuffer


class SequenceReq(CommandReq, Sequence):
    def __init__(self,
                 address: int = DEFAULT_ADDRESS,
                 scope: CommandScope = None,
                 repeat: int = 1,
                 delay: float = 0,
                 requests: List[CommandReq] = None) -> None:
        super().__init__(_SequenceCommandEnum.SYSTEM, address, 0, scope)
        self._repeat = repeat
        self._delay = delay
        self._requests: List[SequencedRequest] = []
        if requests:
            for request in requests:
                self._requests.append(SequencedRequest(request, repeat, delay))

    def __getitem__(self, index) -> SequencedRequest:
        return self._requests[index]

    def __len__(self) -> int:
        return len(self._requests)

    def add_request(self,
                    request: CommandReq | CommandDefEnum,
                    address: int = DEFAULT_ADDRESS,
                    data: int = 0,
                    scope: CommandScope = None,
                    repeat: int = 1,
                    delay: float = 0) -> None:
        if isinstance(request, CommandDefEnum):
            request = CommandReq.build(request, address=address, data=data, scope=scope)
        self._requests.append(SequencedRequest(request, repeat, delay))

    def send(self,
             repeat: int = None,
             delay: float = None,
             baudrate: int = DEFAULT_BAUDRATE,
             port: str = DEFAULT_PORT,
             server: str = None
             ) -> None:
        for sq_request in self._requests:
            request = sq_request.request
            repeat = repeat if repeat is not None else sq_request.repeat
            delay = delay if delay is not None else sq_request.delay
            request.send(repeat, delay, baudrate, port, server)

    def fire(self) -> None:
        self.send()

    def as_action(self,
                  repeat: int = 1,
                  delay: float = 0,
                  baudrate: int = DEFAULT_BAUDRATE,
                  port: str = DEFAULT_PORT,
                  server: str = None
                  ) -> Callable:
        buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)

        def send_func(new_address: int = None) -> None:
            for sq_request in self._requests:
                request = sq_request.request
                if new_address and new_address != request.address:
                    request.address = new_address
                request._enqueue_command(self.as_bytes,
                                         repeat=sq_request.repeat,
                                         delay=sq_request.delay,
                                         baudrate=baudrate,
                                         port=port,
                                         server=server,
                                         buffer=buffer)
        return send_func

    @property
    def as_bytes(self) -> bytes:
        raise NotImplementedError


class SequencedRequest:
    def __init__(self,
                 request: CommandReq,
                 repeat: int = 1,
                 delay: float = 0) -> None:
        self.request: CommandReq = request
        self.repeat: int = repeat
        self.delay: float = delay


class _SequenceCommandDef(CommandDef):
    @property
    def scope(self) -> CommandScope | None:
        return CommandScope.SYSTEM

    @property
    def syntax(self) -> CommandSyntax:
        return CommandSyntax.TMCC2

    @property
    def is_tmcc1(self) -> bool:
        return self.syntax == CommandSyntax.TMCC1

    @property
    def is_tmcc2(self) -> bool:
        return self.syntax == CommandSyntax.TMCC2

    @property
    def first_byte(self) -> bytes | None:
        raise NotImplementedError

    @property
    def address_mask(self) -> bytes | None:
        raise NotImplementedError


class _SequenceCommandEnum(CommandDefEnum):
    SYSTEM = _SequenceCommandDef(0x00)
