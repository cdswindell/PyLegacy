#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import abc
import threading
from abc import ABC
from ipaddress import IPv4Address, IPv6Address
from typing import TYPE_CHECKING, Sequence, TypeVar, cast

from ..comm.comm_buffer import CommBuffer
from ..db.state_watcher import StateWatcher
from ..pdi.pdi_req import PdiReq
from ..utils.validations import Validations
from .command_def import CommandDef, CommandDefEnum
from .command_req import CommandReq
from .constants import DEFAULT_BAUDRATE, DEFAULT_PORT, MINIMUM_DURATION_INTERVAL_MSEC, PROGRAM_NAME, CommandScope

if TYPE_CHECKING:  # pragma: no cover
    from ..cli.pytrain import PyTrain

R = TypeVar("R", bound=CommandReq | PdiReq | Sequence[CommandReq | PdiReq])


class CommandBase(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        command: CommandDefEnum | None,
        command_req: R | None,
        address: int = 99,
        data: int = 0,
        scope: CommandScope = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
        client: bool = False,
        base: str = None,
    ) -> None:
        from ..cli.pytrain import PyTrain

        super().__init__()
        self._address = address
        self._command = None  # provided by _build_command method in subclasses
        self._sc = threading.Event()

        # validate baudrate
        if baudrate is None or baudrate < 110 or baudrate > 115200 or not isinstance(baudrate, int):
            raise ValueError("baudrate must be between 110 and 115,200")
        self._baudrate = baudrate
        # validate port
        if port is None:
            raise ValueError("port cannot be None")
        self._port = port
        # validate server ip address
        self._server, self._port = CommBuffer.parse_server(server, port)

        if PyTrain.current(raise_exception=False) is None:
            self._daemon = False
            pt_args = "-api"
            if client:
                pt_args += " -client"
            elif server:
                pt_args += f" -server {server}"
            elif base:
                pt_args += f" -headless -base {base}"
            else:
                raise NotImplementedError("Program can not be run without specifying '-client' or '-base [IP Address]'")

            self._pytrain = PyTrain(pt_args.split())
            if not self._pytrain.is_synchronized():
                self._sync_state = self._pytrain.store.get_state(CommandScope.SYNC, 99)
                self._sync_watcher = StateWatcher(self._sync_state, self._sync_complete)
        else:
            self._pytrain = PyTrain.current()
            self._daemon = True

        assert self._pytrain is not None, f"{PROGRAM_NAME} must be initialized"

        # persist command information
        self._command_def_enum: CommandDefEnum = command
        self._command_def: CommandDef = cast(CommandDefEnum, command).value if command else None
        self._command_req: R = command_req
        self._data: int = data
        self._scope: CommandScope = scope

        # build_req the command
        self._command = self._build_command()

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def bits(self) -> int:
        return self._command_req.bits if isinstance(self._command_req, CommandReq) else 0

    @property
    def address(self) -> int:
        return self._address

    @property
    def port(self) -> str:
        return self._port

    @property
    def server(self) -> IPv4Address | IPv6Address | None:
        return self._server

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def command_bytes(self) -> bytes:
        return self._command

    @property
    def command_prefix(self) -> bytes:
        return self._command_prefix()

    @property
    def command_req(self) -> R:
        return self._command_req

    @property
    def is_daemon(self) -> bool:
        return self._daemon

    def is_synchronized(self) -> bool:
        return self._pytrain.is_synchronized() if self._pytrain else False

    def send(
        self,
        repeat: int = None,
        delay: float = None,
        duration: float = None,
        interval: int = None,
        shutdown: bool = False,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ):
        """
        Send the command to the LCS SER2 and keep comm buffer alive.
        """
        Validations.validate_int(repeat, min_value=1)
        Validations.validate_int(interval, min_value=MINIMUM_DURATION_INTERVAL_MSEC, allow_none=True)
        Validations.validate_float(delay, min_value=0)
        Validations.validate_float(duration, min_value=0, allow_none=True)
        if isinstance(self.command_req, CommandReq) or isinstance(self.command_req, PdiReq):
            reqs = [self.command_req]
        elif isinstance(self.command_req, Sequence):
            reqs = self.command_req
        else:
            raise ValueError(f"Unknown command type: {type(self.command_req)}")
        for req in reqs:
            req.send(
                repeat=repeat,
                delay=delay,
                duration=duration,
                interval=interval,
                baudrate=baudrate,
                port=port,
                server=server,
            )
        if shutdown:
            buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)
            buffer.shutdown()
            buffer.join()

    def fire(
        self,
        repeat: int = 1,
        delay: float = 0,
        duration: float = 0,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        """
        Fire the command immediately and shut down comm buffers, once empty
        """
        self.send(
            repeat=repeat,
            delay=delay,
            duration=duration,
            shutdown=True,
            baudrate=baudrate,
            port=port,
            server=server,
        )

    def wait_for_sync(self) -> None:
        if not self.is_synchronized():
            self._sc.wait()  # wait for initial Base 3 database load
            self._sc.clear()

    def _sync_complete(self):
        if self._sync_state.is_synchronized():
            self._synchronized = True
            self._sync_watcher.shutdown()
            self._sync_watcher = None
            self._sc.set()

    @property
    def pytrain(self) -> "PyTrain":
        return self._pytrain

    @staticmethod
    def _encode_command(command: int, num_bytes: int = 2) -> bytes:
        return command.to_bytes(num_bytes, byteorder="big")

    @abc.abstractmethod
    def _build_command(self) -> bytes | None:
        return None

    @abc.abstractmethod
    def _command_prefix(self) -> bytes | None:
        return None

    @abc.abstractmethod
    def _encode_address(self, command_op: int) -> bytes | None:
        return None
