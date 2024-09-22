from __future__ import annotations
from collections.abc import Sequence
from typing import List, Callable, Self, Dict, Type, TypeVar

import argparse

from src.protocol.command_def import CommandDefEnum, CommandDef
from src.protocol.command_req import CommandReq
from src.protocol.constants import CommandScope, DEFAULT_ADDRESS, CommandSyntax, DEFAULT_BAUDRATE, DEFAULT_PORT, \
    OfficialRRSpeeds
from src.comm.comm_buffer import CommBuffer
from src.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandDef, TMCC1RRSpeeds
from src.protocol.tmcc2.tmcc2_constants import TMCC2CommandDef, TMCC2EngineCommandDef, TMCC2RRSpeeds
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2RailSoundsDialogControl
from src.utils.argument_parser import ArgumentParser

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
        super().__init__(SequenceCommandEnum.SYSTEM, address, 0, scope)
        self._repeat = repeat
        self._delay = delay
        self._requests: List[SequencedReq] = []
        if requests:
            for request in requests:
                self._requests.append(SequencedReq(request, repeat, delay))

    def __getitem__(self, index) -> SequencedReq:
        return self._requests[index]

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
            req_repeat = sqr.repeat if repeat is None else repeat
            req_delay = sqr.delay if delay is None else delay
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

    @property
    def as_bytes(self) -> bytes:
        raise NotImplementedError

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
                 repeat: int = 1,
                 delay: float = 0) -> None:
        self.request: CommandReq = request
        self.repeat: int = repeat
        self.delay: float = delay

    def __repr__(self) -> str:
        return f"< {self.request} repeat: {self.repeat} delay: {self.delay} >"


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

class SpeedReq(SequenceReq):
    def __init__(self,
                 address: int,
                 speed: int | str | T = None,
                 scope: CommandScope = CommandScope.ENGINE,
                 is_tmcc: bool = False) -> None:
        super().__init__(address, scope)
        t, s, e = self._decode_speed(speed, is_tmcc)
        self.add(t, address)
        self.add(s, address, scope=scope, delay=3)
        self.add(e, address, scope=scope, delay=6)

    def _decode_speed(self, speed, is_tmcc):
        base = None
        speed_enum = None
        if isinstance(speed, OfficialRRSpeeds):
            base = f"SPEED_{speed.name}"
            if isinstance(speed, TMCC1RRSpeeds):
                speed_enum = TMCC1EngineCommandDef.by_name(base)
            else:
                speed_enum = TMCC2EngineCommandDef.by_name(base)
            if speed_enum is None:
                raise ValueError(f"Unknown speed type: {speed}")
        elif isinstance(speed, int):
            if is_tmcc:
                for rr_speed in TMCC1RRSpeeds:
                    if speed in rr_speed.value:
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC1EngineCommandDef.by_name(base)
                        break
            else:
                for rr_speed in TMCC2RRSpeeds:
                    if speed in rr_speed.value:
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC2EngineCommandDef.by_name(base)
                        break
        elif isinstance(speed, str):
            try:
                args = self._speed_parser().parse_args(['-' + speed.strip()])
                speed_enum = args.command
                base = speed_enum.name
            except argparse.ArgumentError:
                pass
        if speed_enum is None:
            raise ValueError(f"Unknown speed type: {speed}")

        tower = TMCC2RailSoundsDialogControl.by_name(f"TOWER_{base}")
        engr = TMCC2RailSoundsDialogControl.by_name(f"ENGINEER_{base}")
        return tower, speed_enum, engr


class TMCC2SequenceDef(TMCC2CommandDef):
    def __init__(self,
                 command_bits: int,
                 scope: CommandScope = CommandScope.ENGINE,
                 is_addressable: bool = True,
                 d_min: int = 0,
                 d_max: int = 0,
                 d_map: Dict[int, int] = None,
                 cmd_class: Type[SequenceReq] = None) -> None:
        super().__init__(command_bits, scope, is_addressable, d_min, d_max, d_map)
        self._cmd_class = cmd_class

    def cmd_class(self) -> Type[SequenceReq]:
        return self._cmd_class


class SequenceCommandEnum(CommandDefEnum):
    SYSTEM = _SequenceCommandDef(0x00)
    ABSOLUTE_SPEED_SEQ = TMCC2SequenceDef(0, d_max=199, cmd_class=SpeedReq)
