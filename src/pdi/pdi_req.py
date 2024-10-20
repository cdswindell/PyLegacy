from __future__ import annotations

import abc
from abc import ABC
from enum import Enum
from typing import Tuple, TypeVar, List

import sys
if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self
    
from .constants import PDI_SOP, PDI_EOP, PDI_STF, CommonAction, PdiAction, PdiCommand, ALL_STATUS
from .constants import IrdaAction, Ser2Action
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope

T = TypeVar('T', bound=PdiAction)


class PdiReq(ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        # throws an exception if we can't dereference
        pdi_cmd = PdiCommand(data[1])
        try:
            from .constants import PdiDevice
            dev = PdiDevice(pdi_cmd.name.split('_')[0].upper())
            return dev.build(data)
        except ValueError:
            raise NotImplementedError(f"PdiCommand {pdi_cmd.name} not implemented")

    def __init__(self,
                 data: bytes | None,
                 pdi_command: PdiCommand = None) -> None:
        if isinstance(data, bytes):
            # first byte should be SOP, last should be EOP, if not, raise exception
            if data[0] != PDI_SOP or data[-1] != PDI_EOP:
                raise ValueError(f"Invalid PDI Request: {data}")
            # process the data to remove SOP, EOP, Checksum, and Stuff Bytes, if any
            self._original = data
            recv_checksum = data[-2]
            self._data, check_sum = self._calculate_checksum(data[1:-2], False)
            if recv_checksum != int.from_bytes(check_sum):
                raise ValueError(f"Invalid PDI Request: {data}  [BAD CHECKSUM]")
            self._pdi_command: PdiCommand = PdiCommand(data[1])
        else:
            if pdi_command is None or not isinstance(pdi_command, PdiCommand):
                raise ValueError(f"Invalid PDI Request: {pdi_command}")
            self._pdi_command = pdi_command
            self._data = self._original = None

    def __repr__(self) -> str:
        data = f" (0x{self._data.hex()})" if self._data is not None else " 0x" + self.as_bytes.hex()
        return f"[PDI {self._pdi_command.friendly}{data}]"

    @staticmethod
    def _calculate_checksum(data: bytes, add_stf=True) -> Tuple[bytes, bytes]:
        byte_stream = bytes()
        check_sum = 0
        for b in data:
            check_sum += b
            if b in [PDI_SOP, PDI_STF, PDI_EOP]:
                check_sum += PDI_STF
                if add_stf is True:
                    byte_stream += PDI_STF.to_bytes(1, byteorder='big')
                else:
                    continue
            byte_stream += b.to_bytes(1, byteorder='big')
        # do checksum calculation on buffer
        check_sum = 0xff & (0 - check_sum)
        if check_sum in [PDI_SOP, PDI_STF, PDI_EOP]:
            if add_stf is True:
                byte_stream += PDI_STF.to_bytes(1, byteorder='big')
            check_sum += PDI_STF
            check_sum = 0xff & (0 - check_sum)
        return byte_stream, check_sum.to_bytes(1, byteorder='big')

    @property
    def pdi_command(self) -> PdiCommand:
        return self._pdi_command

    @property
    def tmcc_id(self) -> int:
        return 0

    @property
    def address(self) -> int:
        # for compatibility with state management system
        return self.tmcc_id

    @property
    def command(self) -> PdiCommand:
        # for compatibility with state management system
        return self.pdi_command

    @property
    def action(self) -> T | None:
        return None

    @property
    def as_bytes(self) -> bytes:
        """
            Default implementation, should override in more complex requests
        """
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder='big')
        byte_str += CommonAction.CONFIG.as_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder='big') + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder='big')
        return byte_str

    @property
    def checksum(self) -> bytes:
        check_sum = 0
        for b in self._data:
            if b in [PDI_SOP, PDI_EOP]:
                continue
            check_sum += b
        check_sum = 0xFF & (0 - check_sum)
        return check_sum.to_bytes(1)

    @property
    def is_ping(self) -> bool:
        return self._pdi_command == PdiCommand.PING

    @property
    def is_tmcc(self) -> bool:
        return self._pdi_command.is_tmcc

    @property
    def payload(self) -> str | None:
        return f"({self.packet})"

    @property
    def packet(self) -> str:
        if self._data is None:
            return "0x" + self.as_bytes.hex()
        else:
            return "0x" + self._data.hex()

    @property
    @abc.abstractmethod
    def scope(self) -> CommandScope:
        ...


class LcsReq(PdiReq, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, data: bytes | int,
                 pdi_command: PdiCommand = None,
                 action: T = None,
                 ident: int | None = None) -> None:
        super().__init__(data, pdi_command)
        self._board_id = self._num_ids = self._model = self._uart0 = self._uart1 = self._base_type = None
        self._dc_volts: float = None
        self._action: T = action
        if isinstance(data, bytes):
            if self._pdi_command.is_lcs is False:
                raise ValueError(f"Invalid PDI LCS Request: {data}")
            self._tmcc_id = self._data[1]
            self._action_byte = self._data[2]
            self._ident = None
            payload = self._data[3:]
            payload_len = len(payload)
            if self._is_action(ALL_STATUS):
                self._board_id = payload[0] if payload_len > 0 else None
                self._num_ids = payload[1] if payload_len > 1 else None
                self._model = payload[2] if payload_len > 2 else None
                self._uart0 = payload[3] if payload_len > 3 else None
                self._uart1 = payload[4] if payload_len > 4 else None
                self._base_type = payload[5] if payload_len > 5 else None
                self._dc_volts = payload[6]/10.0 if payload_len > 6 else None
        else:
            self._action_byte = action.bits if action else 0
            self._tmcc_id = int(data) if data else 0
            self._ident = ident

    def _is_action(self, enums: List[T]) -> bool:
        for enum in enums:
            if enum.bits == self._action_byte:
                return True
        return False

    def _is_command(self, enums: List[PdiCommand]) -> bool:
        for enum in enums:
            if enum == self.pdi_command:
                return True
        return False

    @property
    def board_id(self) -> int | None:
        return self._board_id

    @property
    def num_ids(self) -> int | None:
        return self._num_ids

    @property
    def model(self) -> int | None:
        return self._model

    @property
    def uart0(self) -> int | None:
        return self._uart0

    @property
    def uart1(self) -> int | None:
        return self._uart1

    @property
    def dc_volts(self) -> float | None:
        return self._dc_volts

    def __repr__(self) -> str:
        if self.payload is not None:
            payload = " " + self.payload
        elif self._data is not None:
            payload = f" (0x{self._data.hex()})" if self._data else ""
        else:
            payload = ""

        return f"[PDI {self._pdi_command.name} ID: {self._tmcc_id} {self.action.name}{payload}]"

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @property
    def ident(self) -> int:
        return self._ident

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder='big')
        byte_str += self.action.as_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder='big') + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder='big')
        return byte_str

    @property
    def payload(self) -> str | None:
        if self._is_action(ALL_STATUS) and self.pdi_command.name.endswith("_RX"):
            l1 = f"Board ID: {self.board_id} Num IDs: {self.num_ids} Model: {self.model}"
            return l1
        return f" ({self.packet})"

    @property
    @abc.abstractmethod
    def action(self) -> T:
        ...


class Ser2Req(LcsReq):
    def __init__(self,
                 data: bytes | int,
                 pdi_command: PdiCommand = PdiCommand.SER2_GET,
                 action: Ser2Action = Ser2Action.CONFIG,
                 ident: int | None = None) -> None:
        super().__init__(data, pdi_command, action, ident)
        if isinstance(data, bytes):
            self._action = Ser2Action(self._action_byte)

    @property
    def action(self) -> Ser2Action:
        return self._action

    @property
    def payload(self) -> str | None:
        return None

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM


class IrdaReq(LcsReq):
    def __init__(self,
                 data: bytes | int,
                 pdi_command: PdiCommand = PdiCommand.IRDA_GET,
                 action: IrdaAction = IrdaAction.CONFIG,
                 ident: int | None = None) -> None:
        super().__init__(data, pdi_command, action, ident)
        if isinstance(data, bytes):
            self._action = IrdaAction(self._action_byte)

    @property
    def action(self) -> IrdaAction:
        return self._action

    @property
    def payload(self) -> str | None:
        return None

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM


class TmccReq(PdiReq):
    def __init__(self,
                 data: bytes | CommandReq,
                 pdi_command: PdiCommand = None):
        super().__init__(data, pdi_command=pdi_command)
        if isinstance(data, CommandReq):
            if self.pdi_command.is_tmcc is False:
                raise ValueError(f"Invalid PDI TMCC Request: {self.pdi_command}")
            self._tmcc_command: CommandReq = data
        else:
            if PdiCommand(data[1]) not in [PdiCommand.TMCC_TX, PdiCommand.TMCC_RX]:
                raise ValueError(f"Invalid PDI TMCC Request: {data}")
            self._tmcc_command: CommandReq = CommandReq.from_bytes(self._data[1:])

    def __repr__(self) -> str:
        data = f" (0x{self._data.hex()})" if self._data else ""
        return f"[PDI {self._pdi_command.friendly} {self.tmcc_command}{data}]"

    @property
    def tmcc_command(self) -> CommandReq:
        return self._tmcc_command

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.pdi_command.as_bytes + self.tmcc_command.as_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder='big') + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder='big')
        return byte_str

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM


class Stm2Req(PdiReq):
    def __init__(self, data: bytes):
        if PdiCommand(data[1]).is_base is False:
            raise ValueError(f"Invalid PDI Base Request: {data}")
        super().__init__(data)

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SWITCH


class BaseReq(PdiReq):
    def __init__(self, data: bytes):
        if PdiCommand(data[1]).is_base is False:
            raise ValueError(f"Invalid PDI Base Request: {data}")
        super().__init__(data)

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM


class AllReq(PdiReq):
    def __init__(self,
                 data: bytes = None,
                 pdi_command: PdiCommand = PdiCommand.ALL_GET) -> None:
        super().__init__(data, pdi_command)

    @property
    def payload(self) -> str | None:
        return None

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM


class PingReq(PdiReq):
    def __init__(self, data: bytes | None = None):
        super().__init__(data, PdiCommand.PING)
        if data is not None:
            if PdiCommand(data[1]).is_ping is False:
                raise ValueError(f"Invalid PDI Ping Request: {data}")

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.pdi_command.as_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder='big') + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder='big')
        return byte_str

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM

    def __repr__(self) -> str:
        return f"[PDI {self._pdi_command.friendly}]"


class DeviceWrapper:
    C = TypeVar('C', bound=PdiReq.__class__)
    E = TypeVar('E', bound=Enum)
    T = TypeVar('T', bound=PdiReq)

    def __init__(self,
                 req_class: C,
                 enums: E = None,
                 *commands: PdiCommand) -> None:
        self.req_class = req_class
        self.enums = enums
        self.commands = commands
        self.get: PdiCommand = self._harvest_command('GET')
        self.set: PdiCommand = self._harvest_command('SET')
        self.rx: PdiCommand = self._harvest_command('RX')

    def build(self, data: bytes) -> T:
        action_byte = self._data[2]
        action = self.enums.by_value(action_byte)
        return self.req_class(data, action=action)

    def firmware(self, tmcc_id: int) -> T:
        if self.get is not None:
            enum = self.enums.by_name("FIRMWARE")
            return self.req_class(tmcc_id, self.get, enum)

    def status(self, tmcc_id: int) -> T:
        if self.get is not None:
            enum = self.enums.by_name("STATUS")
            return self.req_class(tmcc_id, self.get, enum)

    def info(self, tmcc_id: int) -> T:
        if self.get is not None:
            enum = self.enums.by_name("INFO")
            return self.req_class(tmcc_id, self.get, enum)

    def clear_errors(self, tmcc_id: int) -> T:
        if self.set is not None:
            enum = self.enums.by_name("CLEAR_ERRORS")
            return self.req_class(tmcc_id, self.set, enum)

    def reset(self, tmcc_id: int) -> T:
        if self.set is not None:
            enum = self.enums.by_name("RESET")
            return self.req_class(tmcc_id, self.set, enum)

    def identify(self, tmcc_id: int, ident: int = 1) -> T:
        if self.set is not None:
            enum = self.enums.by_name("IDENTIFY")
            return self.req_class(tmcc_id, self.set, enum, ident)

    def _harvest_command(self, suffix: str) -> PdiCommand | None:
        suffix = suffix.strip().upper()
        for e in self.commands:
            if e.name.endswith(suffix):
                return e
        return None
