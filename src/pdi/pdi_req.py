from __future__ import annotations

import abc
from abc import ABC
from typing import Tuple, TypeVar

import sys

if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from .constants import PDI_SOP, PDI_EOP, PDI_STF, CommonAction, PdiAction, PdiCommand
from ..protocol.constants import CommandScope

T = TypeVar("T", bound=PdiAction)


class PdiReq(ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        # throws an exception if we can't dereference
        pdi_cmd = PdiCommand(data[1])
        try:
            from .pdi_device import PdiDevice

            dev = PdiDevice.from_pdi_command(pdi_cmd)
            return dev.build_req(data)
        except ValueError:
            raise NotImplementedError(f"PdiCommand {pdi_cmd.name} not implemented")

    def __init__(self, data: bytes | None, pdi_command: PdiCommand = None) -> None:
        if isinstance(data, bytes):
            # first byte should be SOP, last should be EOP, if not, raise exception
            if data[0] != PDI_SOP or data[-1] != PDI_EOP:
                raise ValueError(f"Invalid PDI Request: {data}")
            # process the data to remove SOP, EOP, Checksum, and Stuff Bytes, if any
            self._original = data
            recv_checksum = data[-2]
            self._data, check_sum = self._calculate_checksum(data[1:-2], False)
            if recv_checksum != int.from_bytes(check_sum, byteorder="big"):
                raise ValueError(
                    f"Invalid PDI Request: 0x{data.hex()} {hex(recv_checksum)} != {check_sum.hex()} [BAD CHECKSUM]"
                )
            self._pdi_command: PdiCommand = PdiCommand(data[1])
        else:
            if pdi_command is None or not isinstance(pdi_command, PdiCommand):
                raise ValueError(f"Invalid PDI Request: {pdi_command}")
            self._pdi_command = pdi_command
            self._data = self._original = None
        from .pdi_device import PdiDevice

        self._pdi_device: PdiDevice = PdiDevice.from_pdi_command(self.pdi_command)

    def __repr__(self) -> str:
        data = f" (0x{self._data.hex()})" if self._data is not None else " 0x" + self.as_bytes.hex()
        return f"[PDI {self._pdi_command.friendly}{data}]"

    @staticmethod
    def _calculate_checksum(data: bytes, add_stf=True) -> Tuple[bytes, bytes]:
        """
        Used to calculate checksums on packets we send as well as to strip Stuff bytes
        from packets we receive
        """
        byte_stream = bytes()
        check_sum = 0
        for b in data:
            check_sum += b
            if b in [PDI_SOP, PDI_STF, PDI_EOP]:
                if add_stf is True:
                    # add the stuff byte to the output and account for it in the check sum
                    check_sum += PDI_STF
                    byte_stream += PDI_STF.to_bytes(1, byteorder="big")
                elif b in [PDI_SOP, PDI_EOP]:
                    # we are parsing a received packet; strip stuff byte
                    pass  # we want this byte added to the output stream
                else:
                    # this must be a stuff byte, and we are receiving; strip it
                    continue
            byte_stream += b.to_bytes(1, byteorder="big")
        # do checksum calculation on buffer
        check_sum = 0xFF & (0 - check_sum)
        if check_sum in [PDI_SOP, PDI_STF, PDI_EOP]:
            if add_stf is True:
                byte_stream += PDI_STF.to_bytes(1, byteorder="big")
            check_sum += PDI_STF
            check_sum = 0xFF & (0 - check_sum)
        return byte_stream, check_sum.to_bytes(1, byteorder="big")

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
        byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += CommonAction.CONFIG.as_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
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
    def is_lcs(self) -> bool:
        return False

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
    def scope(self) -> CommandScope: ...


class TmccReq(PdiReq):
    from ..protocol.command_req import CommandReq

    def __init__(self, data: bytes | CommandReq, pdi_command: PdiCommand = None):
        super().__init__(data, pdi_command=pdi_command)
        from ..protocol.command_req import CommandReq

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
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
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
    def __init__(self, data: bytes = None, pdi_command: PdiCommand = PdiCommand.ALL_GET) -> None:
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
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM

    def __repr__(self) -> str:
        return f"[PDI {self._pdi_command.friendly}]"
