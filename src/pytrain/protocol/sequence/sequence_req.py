from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from time import sleep
from typing import List, Callable, TypeVar, Tuple

from ..multibyte.multibyte_constants import TMCC2RailSoundsDialogControl

if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from ..command_def import CommandDefEnum
from ..command_req import CommandReq
from ..constants import (
    DEFAULT_ADDRESS,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    OfficialRRSpeeds,
)
from ..constants import CommandScope
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandEnum, TMCC1RRSpeedsEnum
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2RRSpeedsEnum

from ...comm.comm_buffer import CommBuffer
from ...utils.argument_parser import ArgumentParser

T = TypeVar("T", TMCC1RRSpeedsEnum, TMCC2RRSpeedsEnum)


class SequenceReq(CommandReq, Sequence):
    from .sequence_constants import SequenceCommandEnum

    @classmethod
    def build(
        cls,
        command: SequenceCommandEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
    ) -> Self:
        if command.value.cmd_class is None:
            cls._register_command_class(command)
        cmd_class = command.value.cmd_class
        return cmd_class(address, data, scope)

    @classmethod
    def _register_command_class(cls, command):
        """
        We need this function to avoid Python circular dependencies
        """
        from .sequence_constants import SequenceCommandEnum
        from .speed_req import SpeedReq
        from .abs_speed_rpm import AbsoluteSpeedRpm
        from .grade_crossing_req import GradeCrossingReq
        from .ramped_speed_req import RampedSpeedReq
        from .ramped_speed_req import RampedSpeedDialogReq
        from .labor_effect import LaborEffectUpReq
        from .labor_effect import LaborEffectDownReq

        if command == SequenceCommandEnum.ABSOLUTE_SPEED_SEQ:
            SequenceCommandEnum.ABSOLUTE_SPEED_SEQ.value.register_cmd_class(SpeedReq)
        elif command == SequenceCommandEnum.ABSOLUTE_SPEED_RPM:
            SequenceCommandEnum.ABSOLUTE_SPEED_RPM.value.register_cmd_class(AbsoluteSpeedRpm)
        elif command == SequenceCommandEnum.GRADE_CROSSING_SEQ:
            SequenceCommandEnum.GRADE_CROSSING_SEQ.value.register_cmd_class(GradeCrossingReq)
        elif command == SequenceCommandEnum.RAMPED_SPEED_SEQ:
            SequenceCommandEnum.RAMPED_SPEED_SEQ.value.register_cmd_class(RampedSpeedReq)
        elif command == SequenceCommandEnum.RAMPED_SPEED_DIALOG_SEQ:
            SequenceCommandEnum.RAMPED_SPEED_DIALOG_SEQ.value.register_cmd_class(RampedSpeedDialogReq)
        elif command == SequenceCommandEnum.LABOR_EFFECT_UP_SEQ:
            SequenceCommandEnum.LABOR_EFFECT_UP_SEQ.value.register_cmd_class(LaborEffectUpReq)
        elif command == SequenceCommandEnum.LABOR_EFFECT_DOWN_SEQ:
            SequenceCommandEnum.LABOR_EFFECT_DOWN_SEQ.value.register_cmd_class(LaborEffectDownReq)

    def __init__(
        self,
        command: SequenceCommandEnum,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = None,
        repeat: int = 1,
        delay: float = 0,
        requests: List[CommandReq] = None,
    ) -> None:
        self._requests: List[SequencedReq] = list()  # need to define prior to calling super()
        if requests:
            for request in requests:
                self._requests.append(SequencedReq(request, repeat, delay))
        super().__init__(command, address, 0, scope)
        self._repeat = repeat
        self._delay = delay

    def __getitem__(self, index) -> SequencedReq:
        return self._requests[index]

    @property
    def as_bytes(self) -> bytes:
        self._recalculate()
        cmd_bytes = bytes()
        for req_wrapper in self._requests:
            req = req_wrapper.request
            cmd_bytes += req.as_bytes
        return cmd_bytes

    @property
    def requests(self) -> List[SequencedReq]:
        return self._requests.copy()

    def __len__(self) -> int:
        return len(self._requests)

    def _apply_address(self, new_address: int = None) -> int:
        for req_wrapper in self._requests:
            req = req_wrapper.request
            req.address = self.address
        return 0

    def _apply_data(self, new_data: int = None) -> int:
        for req_wrapper in self._requests:
            req = req_wrapper.request
            if req.is_data:
                req.data = self.data
        return 0

    def add(
        self,
        request: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        repeat: int = 1,
        delay: float = 0,
    ) -> None:
        if isinstance(request, CommandDefEnum):
            request = CommandReq.build(request, address=address, data=data, scope=scope)
        self._requests.append(SequencedReq(request, repeat=repeat, delay=delay))

    def send(
        self,
        repeat: int = None,
        delay: float = None,
        duration: float = None,
        interval: int = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        for sqr in self._requests:
            request = sqr.request
            req_repeat = sqr.repeat if sqr.repeat is not None else repeat
            req_delay = sqr.delay if sqr.delay is not None else delay
            req_duration = sqr.duration if sqr.duration is not None else duration
            req_interval = sqr.interval if sqr.interval is not None else interval
            request.send(
                repeat=req_repeat,
                delay=req_delay,
                duration=req_duration,
                interval=req_interval,
                baudrate=baudrate,
                port=port,
                server=server,
            )
            sleep(0.001)

    def fire(
        self,
        repeat: int = None,
        delay: float = None,
        duration: float = None,
        interval: int = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        self.send(
            repeat=repeat,
            delay=delay,
            duration=duration,
            interval=interval,
            baudrate=baudrate,
            port=port,
            server=server,
        )
        CommBuffer.build().shutdown()

    def as_action(
        self,
        repeat: int = 1,
        delay: float = 0,
        duration: float = 0,
        interval: int = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> Callable:
        buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)

        def send_func(new_address: int = None, new_data: int = None) -> None:
            if new_address and new_address != self.address:
                self.address = new_address
            if new_data != self.data:
                self.data = new_data
            for sq_request in self._requests:
                request = sq_request.request
                request._enqueue_command(
                    request.as_bytes,
                    repeat=sq_request.repeat,
                    delay=sq_request.delay,
                    duration=sq_request.duration,
                    interval=sq_request.interval,
                    baudrate=baudrate,
                    port=port,
                    server=server,
                    buffer=buffer,
                )

        return send_func

    @staticmethod
    def speed_parser(is_tmcc: bool = False) -> ArgumentParser:
        """
        Parse the first token of the user's input
        """
        cde = TMCC1EngineCommandEnum if is_tmcc else TMCC2EngineCommandEnum
        command_parser = ArgumentParser(exit_on_error=False)
        group = command_parser.add_mutually_exclusive_group()
        group.add_argument("-stop", action="store_const", const=cde.SPEED_STOP_HOLD, dest="command")
        group.add_argument("-roll", action="store_const", const=cde.SPEED_ROLL, dest="command")
        group.add_argument("-restricted", action="store_const", const=cde.SPEED_RESTRICTED, dest="command")
        group.add_argument("-slow", action="store_const", const=cde.SPEED_SLOW, dest="command")
        group.add_argument("-medium", action="store_const", const=cde.SPEED_MEDIUM, dest="command")
        group.add_argument("-limited", action="store_const", const=cde.SPEED_LIMITED, dest="command")
        group.add_argument("-normal", action="store_const", const=cde.SPEED_NORMAL, dest="command")
        group.add_argument("-hi", "-high", "-highball", action="store_const", const=cde.SPEED_HIGHBALL, dest="command")
        return command_parser

    def decode_rr_speed(
        self, speed: OfficialRRSpeeds | int | str, is_tmcc: bool
    ) -> Tuple[CommandDefEnum, CommandDefEnum, int, CommandDefEnum]:
        base = None
        speed_enum = None
        speed_int = None
        tower = engr = None
        if isinstance(speed, OfficialRRSpeeds):
            base = f"SPEED_{speed.name}"
            if isinstance(speed, TMCC1RRSpeedsEnum):
                speed_enum = TMCC1EngineCommandEnum.by_name(base)
            else:
                speed_enum = TMCC2EngineCommandEnum.by_name(base)
            if speed_enum is None:
                raise ValueError(f"Unknown speed type: {speed}")
        elif isinstance(speed, int):
            if is_tmcc:
                for rr_speed in TMCC1RRSpeedsEnum:
                    if speed in rr_speed.value:
                        speed_int = rr_speed.value[0]
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC1EngineCommandEnum.by_name(base)
                        break
            else:
                for rr_speed in TMCC2RRSpeedsEnum:
                    if speed in rr_speed.value:
                        speed_int = rr_speed.value[0]
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC2EngineCommandEnum.by_name(base)
                        break
        elif isinstance(speed, str):
            try:
                args = self.speed_parser().parse_args(["-" + speed.strip()])
                speed_enum = args.command
                base = speed_enum.name
                _, speed_int = speed_enum.value.alias
            except argparse.ArgumentError:
                pass

        if base is not None:
            tower = TMCC2RailSoundsDialogControl.by_name(f"TOWER_{base}")
            engr = TMCC2RailSoundsDialogControl.by_name(f"ENGINEER_{base}")
        return tower, speed_enum, speed_int, engr

    def _recalculate(self) -> None:
        """
        Recalculate command state, prior to sending bytes
        """
        pass


class SequencedReq:
    def __init__(
        self,
        request: CommandReq,
        repeat: int = None,
        delay: float = None,
        duration: float = None,
        interval: int = None,
    ) -> None:
        self.request: CommandReq = request
        self.repeat: int = repeat
        self.delay: float = delay
        self.duration: float = duration
        self.interval: int = interval

    def __repr__(self) -> str:
        rtn = f"<{self.request} repeat: {self.repeat} delay: {self.delay} "
        rtn += f"duration: {self.duration} interval: {self.interval}>"
        return rtn

    @property
    def as_bytes(self) -> bytes:
        return self.request.as_bytes
