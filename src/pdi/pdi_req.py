from __future__ import annotations

import abc
from abc import ABC
from typing import Self, Tuple

from .constants import PDI_SOP, PDI_EOP, PdiCommand, PDI_STF, WiFiAction, IrdaAction, Asc2Action
from ..protocol.command_req import CommandReq


class PdiReq(ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        # throws an exception if we can't dereference
        pdi_cmd = PdiCommand(data[1])

        dev_type = pdi_cmd.name.split('_')[0].upper()
        if dev_type in DEVICE_TO_REQ_MAP:
            return DEVICE_TO_REQ_MAP[dev_type](data)
        else:
            raise NotImplementedError(f"PdiCommand {pdi_cmd.name} not implemented")

    def __init__(self,
                 data: bytes,
                 pdi_command: PdiCommand = None) -> None:
        if isinstance(data, bytes):
            # first byte should be SOP, last should be EOP, if not, raise exception
            if data[0] != PDI_SOP or data[-1] != PDI_EOP:
                raise ValueError(f"Invalid PDI Request: {data}")
            # process the data to remove SOP, EOP, Checksum, and Stuff Bytes, if any
            self._original = data
            recv_checksum = data[-2]
            self._data = bytes()
            check_sum = 0
            for b in data[1:-2]:
                check_sum += b
                if b == PDI_STF:
                    continue  # include in checksum but not data
                self._data += b.to_bytes(1, byteorder='big')
            check_sum = 0xFF & (0 - check_sum)
            if recv_checksum != check_sum:
                raise ValueError(f"Invalid PDI Request: {data}  [BAD CHECKSUM]")
            self._pdi_command: PdiCommand = PdiCommand(data[1])
        else:
            if pdi_command is None or not isinstance(pdi_command, PdiCommand):
                raise ValueError(f"Invalid PDI Request: {pdi_command}")
            self._pdi_command = pdi_command
            self._data = self._original = None

    def __repr__(self) -> str:
        return f"{self._pdi_command.friendly} {self._data.hex(':')}"

    @staticmethod
    def _calculate_checksum(data: bytes) -> Tuple[bytes, bytes]:
        byte_stream = bytes()
        check_sum = 0
        for b in data:
            if b in [PDI_STF, PDI_EOP]:
                byte_stream += PDI_STF.to_bytes(1, byteorder='big')
                check_sum += PDI_STF
            byte_stream += b.to_bytes(1, byteorder='big')
            check_sum += b
        # do checksum calculation on buffer
        check_sum = 0xff & (0 - check_sum)
        return byte_stream, check_sum.to_bytes(1, byteorder='big')

    @property
    def pdi_command(self) -> PdiCommand:
        return self._pdi_command

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


class LcsReq(PdiReq, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, data: bytes | int,
                 pdi_command: PdiCommand = None,
                 action: int = None) -> None:
        super().__init__(data, pdi_command)
        if isinstance(data, bytes):
            if PdiCommand(data[1]).is_lcs is False:
                raise ValueError(f"Invalid PDI LCS Request: {data}")
            self._tmcc_id = self._data[1]
            self._action_byte = self._data[2]
        else:
            self._action_byte = action
            self._tmcc_id = int(data)

    def __repr__(self) -> str:
        payload = f" {self.payload}" if self.payload is not None else ""
        return f"{self._pdi_command.name} ID#{self._tmcc_id} {self.action.name}{payload}"

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

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
    def action(self) -> WiFiAction | IrdaAction | Asc2Action:
        ...

    @property
    @abc.abstractmethod
    def payload(self) -> str | None:
        ...


class Asc2Req(LcsReq):
    def __init__(self, data: bytes):
        super().__init__(data)
        self._action = Asc2Action(self._action_byte)

    @property
    def action(self) -> Asc2Action:
        return self._action

    @property
    def payload(self) -> str | None:
        return None


class IrdaReq(LcsReq):
    def __init__(self, data: bytes):
        super().__init__(data)
        self._action = IrdaAction(self._action_byte)

    @property
    def action(self) -> IrdaAction:
        return self._action

    @property
    def payload(self) -> str | None:
        return None


class WiFiReq(LcsReq):
    def __init__(self, data: bytes | int,
                 pdi_command: PdiCommand = PdiCommand.WIFI_GET,
                 action: WiFiAction = WiFiAction.CONNECT) -> None:
        super().__init__(data, pdi_command, action.bits)
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
                the_clients.append(f"{prefix}{payload[i+1]}")
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
                    clients += f"{payload_bytes[i+1]} ({payload_bytes[i]})"
                return f"Base IP: {ip_addr} {clients}"
            elif self.action == WiFiAction.RESPBCASTS:
                return f"Broadcasts {'ENABLED' if payload_bytes[0] == 1 else 'DISABLED'}: {payload_bytes[0]}"
            return payload_bytes.hex(':')


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
        return f"{self._pdi_command.friendly} {self.tmcc_command} {self._original.hex(':')}"

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


class PingReq(PdiReq):
    def __init__(self, data: bytes):
        if PdiCommand(data[1]).is_ping is False:
            raise ValueError(f"Invalid PDI Ping Request: {data}")
        super().__init__(data)

    def __repr__(self) -> str:
        return f"{self._pdi_command.friendly}"


class BaseReq(PdiReq):
    def __init__(self, data: bytes):
        if PdiCommand(data[1]).is_base is False:
            raise ValueError(f"Invalid PDI Base Request: {data}")
        super().__init__(data)

    def __repr__(self) -> str:
        return f"{self._pdi_command.friendly}"


DEVICE_TO_REQ_MAP = {
    "BASE": BaseReq,
    "TMCC": TmccReq,
    "PING": PingReq,
    "UPDATE": BaseReq,
    "WIFI": WiFiReq,
    "ASC2": Asc2Req,
    "IRDA": IrdaReq,
}

WIFI_MODE_MAP = {
    0: "AP",
    1: "INF",
    2: "WPS"
}
