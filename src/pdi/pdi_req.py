from __future__ import annotations

import abc
from abc import ABC
from typing import Self, Tuple, TypeVar

from .constants import PDI_SOP, PDI_EOP, PdiCommand, PDI_STF, CommonAction, PdiAction
from .constants import WiFiAction, IrdaAction, Ser2Action, Bpc2Action
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope

T = TypeVar('T', bound=PdiAction)


class PdiReq(ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        # throws an exception if we can't dereference
        pdi_cmd = PdiCommand(data[1])

        dev_type = pdi_cmd.name.split('_')[0].upper()
        if dev_type == "ALL":
            return AllReq(data)
        if dev_type == "BASE":
            return BaseReq(data)
        if dev_type == "TMCC":
            return TmccReq(data)
        if dev_type == "PING":
            return PingReq(data)
        if dev_type == "WIFI":
            return WiFiReq(data)
        if dev_type == "ASC2":
            from src.pdi.asc2_req import Asc2Req
            return Asc2Req(data)
        if dev_type == "SER2":
            return Ser2Req(data)
        if dev_type == "IRDA":
            return IrdaReq(data)
        if dev_type == "BPC2":
            return Bpc2Req(data)
        else:
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
        data = f" (0x{self._data.hex()})" if self._data else ""
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
    def payload(self) -> str | None:
        return None

    @property
    @abc.abstractmethod
    def scope(self) -> CommandScope:
        ...


class LcsReq(PdiReq, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, data: bytes | int,
                 pdi_command: PdiCommand = None,
                 action: int = None,
                 ident: int | None = None) -> None:
        super().__init__(data, pdi_command)
        if isinstance(data, bytes):
            if PdiCommand(data[1]).is_lcs is False:
                raise ValueError(f"Invalid PDI LCS Request: {data}")
            self._tmcc_id = self._data[1]
            self._action_byte = self._data[2]
            self._ident = None
        else:
            self._action_byte = action
            self._tmcc_id = int(data)
            self._ident = ident

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
    @abc.abstractmethod
    def action(self) -> T:
        ...


class Ser2Req(LcsReq):
    def __init__(self,
                 data: bytes | int,
                 pdi_command: PdiCommand = PdiCommand.SER2_GET,
                 action: Ser2Action = Ser2Action.CONFIG,
                 ident: int | None = None) -> None:
        super().__init__(data, pdi_command, action.bits, ident)
        if isinstance(data, bytes):
            self._action = Ser2Action(self._action_byte)
        else:
            self._action = action

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
        super().__init__(data, pdi_command, action.bits, ident)
        if isinstance(data, bytes):
            self._action = IrdaAction(self._action_byte)
        else:
            self._action = action

    @property
    def action(self) -> IrdaAction:
        return self._action

    @property
    def payload(self) -> str | None:
        return None

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM


class Bpc2Req(LcsReq):
    def __init__(self,
                 data: bytes | int,
                 pdi_command: PdiCommand = PdiCommand.BPC2_GET,
                 action: Bpc2Action = Bpc2Action.CONFIG,
                 ident: int | None = None,
                 mode: int = None,
                 debug: int = None,
                 restore: bool = None) -> None:
        super().__init__(data, pdi_command, action.bits, ident)
        self._scope = CommandScope.ACC
        if isinstance(data, bytes):
            self._action = Bpc2Action(self._action_byte)
            data_len = len(self._data)
            if self._action == Bpc2Action.CONFIG:
                self._mode = self._data[7] if data_len > 7 else None
                self._restore = (self._mode & 0x80) == 0x80
                if self._restore:
                    self._mode &= 0x7F
                self._debug = self._data[4] if data_len > 4 else None
            else:
                self._mode = self._debug = self._restore = None
        else:
            self._action = action
            self._mode = mode
            self._debug = debug
            self._restore = restore

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def action(self) -> Bpc2Action:
        return self._action

    @property
    def mode(self) -> int | None:
        return self._mode

    @property
    def restore(self) -> bool:
        return self._restore

    @property
    def debug(self) -> int | None:
        return self._debug

    @property
    def payload(self) -> str | None:
        if self._data:
            payload_bytes = self._data[3:]
        else:
            payload_bytes = bytes()
        if self.action == Bpc2Action.CONFIG:
            return f"Mode: {self.mode} Debug: Restore: {self.restore} {self.debug} (0x{payload_bytes.hex()})"

        return f" (0x{payload_bytes.hex()})"

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder='big')
        byte_str += self.action.as_bytes

        if self._action == Bpc2Action.CONFIG:
            if self.pdi_command != PdiCommand.BPC2_GET:
                debug = (self.debug if self.debug is not None else 0)
                mode = self.mode | 0x80 if self.restore else self.mode
                byte_str += self.tmcc_id.to_bytes(1, byteorder='big')  # allows board to be renumbered
                byte_str += debug.to_bytes(1, byteorder='big')
                byte_str += (0x0000).to_bytes(2, byteorder='big')
                byte_str += mode.to_bytes(1, byteorder='big')
        elif self._action == Bpc2Action.IDENTIFY:
            if self.pdi_command == PdiCommand.BPC2_SET:
                byte_str += (self.ident if self.ident is not None else 0).to_bytes(1, byteorder='big')

        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder='big') + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder='big')
        return byte_str


WIFI_MODE_MAP = {
    0: "AP",
    1: "INF",
    2: "WPS"
}


class WiFiReq(LcsReq):
    def __init__(self,
                 data: bytes | int,
                 pdi_command: PdiCommand = PdiCommand.WIFI_GET,
                 action: WiFiAction = WiFiAction.CONFIG,
                 ident: int | None = None) -> None:
        super().__init__(data, pdi_command, action.bits, ident)
        if isinstance(data, bytes):
            self._action = WiFiAction(self._action_byte)
        else:
            self._action = action

    @property
    def action(self) -> WiFiAction:
        return self._action

    @property
    def base_address(self) -> str | None:
        if self._data is not None and self.action == WiFiAction.IP:
            payload = self._data[3:]
            return f"{payload[0]}.{payload[1]}.{payload[2]}.{payload[3]}"
        return None

    @property
    def clients(self) -> list[str]:
        if self._data is not None and self.action == WiFiAction.IP:
            payload = self._data[3:]
            prefix = f"{payload[0]}.{payload[1]}.{payload[2]}."
            the_clients = list()
            for i in range(0, len(payload), 2):
                the_clients.append(f"{prefix}{payload[i + 1]}")
            return the_clients

    @property
    def payload(self) -> str | None:
        if self._data is None:
            return None
        else:
            payload_bytes = self._data[3:]
            if self.action == WiFiAction.CONNECT:
                return (f"Max Connections: {payload_bytes[0]} Connected: {payload_bytes[1]}" +
                        f" {WIFI_MODE_MAP[payload_bytes[2]]}")
            elif self.action == WiFiAction.IP:
                ip_addr = f"{payload_bytes[0]}.{payload_bytes[1]}.{payload_bytes[2]}.{payload_bytes[3]}"
                payload_bytes = payload_bytes[4:]
                clients = " Clients: "
                for i in range(0, len(payload_bytes), 2):
                    if i > 0:
                        clients += ", "
                    clients += f"{payload_bytes[i + 1]} ({payload_bytes[i]})"
                return f"Base IP: {ip_addr} {clients}"
            elif self.action == WiFiAction.RESPBCASTS:
                return f"Broadcasts {'ENABLED' if payload_bytes[0] == 1 else 'DISABLED'}: {payload_bytes[0]}"
            return payload_bytes.hex(':')

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
