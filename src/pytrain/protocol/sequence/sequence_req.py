from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from time import sleep
from typing import Callable, List, Tuple, TypeVar

from ...pdi.pdi_req import PdiReq
from ..multibyte.multibyte_constants import TMCC2RailSoundsDialogControl

if sys.version_info >= (3, 11):
    from typing import Self

from ...comm.comm_buffer import CommBuffer
from ...db.component_state_store import ComponentStateStore
from ...db.engine_state import EngineState, TrainState
from ...utils.argument_parser import ArgumentParser
from ..command_def import CommandDefEnum
from ..command_req import CommandReq
from ..constants import (
    DEFAULT_ADDRESS,
    DEFAULT_BAUDRATE,
    DEFAULT_DURATION_INTERVAL_MSEC,
    DEFAULT_PORT,
    CommandScope,
    OfficialRRSpeeds,
)
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandEnum, TMCC1RRSpeedsEnum
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2RRSpeedsEnum

T = TypeVar("T", TMCC1RRSpeedsEnum, TMCC2RRSpeedsEnum)


class SequenceReq(CommandReq, Sequence):
    from .sequence_constants import SequenceCommandEnum

    @classmethod
    def build(
        cls,
        command: SequenceCommandEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> Self:
        if command.value.cmd_class is None:
            raise ValueError(f"Sequence Command {command} does not have a command class registered")
        return command.value.cmd_class(address, data, scope)

    def __init__(
        self,
        command: SequenceCommandEnum,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
        repeat: int = 1,
        delay: float = 0,
        requests: List[CommandReq] = None,
    ) -> None:
        self._requests: List[SequencedReq] = list()  # need to define prior to calling super()
        if requests:
            for request in requests:
                self._requests.append(SequencedReq(request, repeat, delay))
        # have to get state before calling parent constructor
        self._state = ComponentStateStore.get_state(scope, address, create=False)
        super().__init__(command, address, 0, scope)
        self._repeat = repeat
        self._delay = delay

    def __getitem__(self, index) -> SequencedReq:
        return self._requests[index]

    def __setitem__(self, index: int, value: SequencedReq | CommandReq) -> None:
        if isinstance(value, SequencedReq):
            pass
        elif isinstance(value, CommandReq):
            value = SequencedReq(value)
        else:
            raise ValueError(f"Invalid value type: {type(value)}")
        self._requests[index] = value

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

    def _apply_scope(self, new_scope: CommandScope = None) -> int:
        for req_wrapper in self._requests:
            req = req_wrapper.request
            req.scope = self.scope
        return 0

    def add(
        self,
        request: CommandReq | CommandDefEnum | PdiReq,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        repeat: int = 1,
        delay: float = 0,
        index: int = None,
    ) -> None:
        if isinstance(request, CommandDefEnum):
            request = CommandReq.build(request, address=address, data=data, scope=scope)
        elif isinstance(request, CommandReq) or isinstance(request, PdiReq):
            pass
        elif request is None:
            return  # don't add a None request
        else:
            raise ValueError(f"Invalid request type: {type(request) if request else 'None'}")
        if index is None:
            self._requests.append(SequencedReq(request, repeat=repeat, delay=delay))
        else:
            self._requests.insert(index, SequencedReq(request, repeat=repeat, delay=delay))

    def send(
        self,
        repeat: int = 1,
        delay: float = 0.0,
        duration: float = 0.0,
        interval: int = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        self._on_before_send()
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
        interval: int = DEFAULT_DURATION_INTERVAL_MSEC,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
        address: int = None,
        data: int = None,
    ) -> Callable:
        buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)

        def send_func(new_address: int = None, new_data: int = None) -> None:
            if new_address and new_address != self.address:
                self.address = new_address
            if new_data != self.data:
                self.data = new_data
            elif address and address != self.address:
                self.address = address
            if self.num_data_bits:
                if new_data is not None and new_data != self.data:
                    self.data = new_data
                elif data is not None and data != self.data:
                    self.data = data
            self._on_before_send()
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
                    request=request,
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
                raise ValueError(f"Unknown speed: {speed}")
            speed_int = speed.value[0]
        elif isinstance(speed, int):
            if is_tmcc:
                for rr_speed in TMCC1RRSpeedsEnum:
                    if speed in rr_speed.value:
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC1EngineCommandEnum.by_name(base)
                        break
            else:
                for rr_speed in TMCC2RRSpeedsEnum:
                    if speed in rr_speed.value:
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC2EngineCommandEnum.by_name(base)
                        break
            speed_int = speed  # preserve requested speed, speed_int is normalized
        elif isinstance(speed, str):
            try:
                args = self.speed_parser(is_tmcc).parse_args(["-" + speed.strip()])
                speed_enum = args.command
                base = speed_enum.name
                _, speed_int = speed_enum.value.alias
            except argparse.ArgumentError:
                pass

        # sanitize speed
        if self.is_tmcc1 and speed_int > 31:
            speed_int = 31
        elif self.is_tmcc2 and speed_int > 199:
            if isinstance(self.state, EngineState):
                speed_int = self.state.speed_max
            else:
                speed_int = 199

        if base is not None:
            tower = TMCC2RailSoundsDialogControl.by_name(f"TOWER_{base}")
            engr = TMCC2RailSoundsDialogControl.by_name(f"ENGINEER_{base}")
        return tower, speed_enum, speed_int, engr

    def _recalculate(self) -> None:
        """
        Recalculate command state before sending bytes
        """
        pass

    @property
    def state(self) -> EngineState | TrainState:
        return self._state

    @property
    def is_tmcc1(self) -> bool:
        if isinstance(self._state, EngineState):
            return not self._state.is_legacy
        return True

    @property
    def is_tmcc2(self) -> bool:
        if isinstance(self._state, EngineState):
            return self._state.is_legacy
        return False

    def _on_before_send(self) -> None:
        """
        Override in subclasses to perform actions before sending bytes
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
