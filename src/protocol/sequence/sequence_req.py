from __future__ import annotations

from collections.abc import Sequence
from typing import List, Callable, Self, TypeVar

from ..command_def import CommandDefEnum
from ..command_req import CommandReq
from ..constants import DEFAULT_ADDRESS, DEFAULT_BAUDRATE, DEFAULT_PORT
from ..constants import CommandScope
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandDef, TMCC1RRSpeeds
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandDef, TMCC2RRSpeeds

from ...comm.comm_buffer import CommBuffer
from ...utils.argument_parser import ArgumentParser

T = TypeVar("T", TMCC1RRSpeeds, TMCC2RRSpeeds)


class SequenceReq(CommandReq, Sequence):
    @classmethod
    def build(cls,
              command: CommandDefEnum | None,
              address: int = DEFAULT_ADDRESS,
              data: int = 0,
              scope: CommandScope = None) -> Self:
        cmd_class = command.value.cmd_class()
        return cmd_class(address, data, scope)

    def __init__(self,
                 address: int = DEFAULT_ADDRESS,
                 scope: CommandScope = None,
                 repeat: int = 1,
                 delay: float = 0,
                 requests: List[CommandReq] = None) -> None:
        from .sequence_constants import SequenceCommandEnum
        super().__init__(SequenceCommandEnum.SYSTEM, address, 0, scope)
        self._repeat = repeat
        self._delay = delay
        self._requests: List[SequencedReq] = []
        if requests:
            for request in requests:
                self._requests.append(SequencedReq(request, repeat, delay))

    def __getitem__(self, index) -> SequencedReq:
        return self._requests[index]

    @property
    def as_bytes(self) -> bytes:
        cmd_bytes = bytes()
        for req in self._requests:
            cmd_bytes += req.as_bytes
        return cmd_bytes

    def __len__(self) -> int:
        return len(self._requests)

    def _apply_address(self, **kwargs) -> int:
        return 0

    def _apply_data(self, **kwargs) -> int:
        return 0

    def add(self,
            request: CommandReq | CommandDefEnum,
            address: int = DEFAULT_ADDRESS,
            data: int = 0,
            scope: CommandScope = None,
            repeat: int = 1,
            delay: float = 0) -> None:
        if isinstance(request, CommandDefEnum):
            request = CommandReq.build(request, address=address, data=data, scope=scope)
        self._requests.append(SequencedReq(request, repeat=repeat, delay=delay))

    def send(self,
             repeat: int = None,
             delay: float = None,
             baudrate: int = DEFAULT_BAUDRATE,
             port: str = DEFAULT_PORT,
             server: str = None
             ) -> None:
        for sqr in self._requests:
            request = sqr.request
            req_repeat = sqr.repeat if sqr.repeat is not None else repeat
            req_delay = sqr.delay if sqr.delay is not None else delay
            request.send(req_repeat, req_delay, baudrate, port, server)

    def fire(self,
             repeat: int = None,
             delay: float = None,
             baudrate: int = DEFAULT_BAUDRATE,
             port: str = DEFAULT_PORT,
             server: str = None
             ) -> None:
        self.send(repeat, delay, baudrate, port, server)
        CommBuffer.build().shutdown()

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

    @staticmethod
    def _speed_parser(is_tmcc: bool = False) -> ArgumentParser:
        """
            Parse the first token of the user's input
        """
        cde = TMCC1EngineCommandDef if is_tmcc else TMCC2EngineCommandDef
        command_parser = ArgumentParser(exit_on_error=False)
        group = command_parser.add_mutually_exclusive_group()
        group.add_argument("-stop",
                           action="store_const",
                           const=cde.SPEED_STOP_HOLD,
                           dest="command")
        group.add_argument("-roll",
                           action="store_const",
                           const=cde.SPEED_ROLL,
                           dest="command")
        group.add_argument("-restricted",
                           action="store_const",
                           const=cde.SPEED_RESTRICTED,
                           dest="command")
        group.add_argument("-slow",
                           action="store_const",
                           const=cde.SPEED_SLOW,
                           dest="command")
        group.add_argument("-medium",
                           action="store_const",
                           const=cde.SPEED_MEDIUM,
                           dest="command")
        group.add_argument("-limited",
                           action="store_const",
                           const=cde.SPEED_LIMITED,
                           dest="command")
        group.add_argument("-normal",
                           action="store_const",
                           const=cde.SPEED_NORMAL,
                           dest="command")
        group.add_argument("-hi", "-high", "-highball",
                           action="store_const",
                           const=cde.SPEED_HIGHBALL,
                           dest="command")
        return command_parser


class SequencedReq:
    def __init__(self,
                 request: CommandReq,
                 repeat: int = None,
                 delay: float = None) -> None:
        self.request: CommandReq = request
        self.repeat: int = repeat
        self.delay: float = delay

    def __repr__(self) -> str:
        return f"< {self.request} repeat: {self.repeat} delay: {self.delay} >"

    @property
    def as_bytes(self) -> bytes:
        return self.request.as_bytes
