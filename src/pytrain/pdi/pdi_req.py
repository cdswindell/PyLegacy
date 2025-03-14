from __future__ import annotations

import abc
import sys
from abc import ABC
from time import sleep
from typing import Tuple, TypeVar, List

from ..utils.validations import Validations

if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from .constants import PDI_SOP, PDI_EOP, PDI_STF, CommonAction, PdiAction, PdiCommand
from ..protocol.constants import CommandScope, MINIMUM_DURATION_INTERVAL_MSEC, DEFAULT_DURATION_INTERVAL_MSEC

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
        except AttributeError as ae:
            raise ae
        except ValueError as ve:
            raise ve

    def __init__(self, data: bytes | None, pdi_command: PdiCommand = None) -> None:
        # default scope is system; override as needed in child classes
        # also change as needed when sending command updates to state handler
        self._scope = CommandScope.SYSTEM
        self._tmcc_id = 0
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
        # TODO: block setter
        from .pdi_device import PdiDevice

        self.pdi_device: PdiDevice = PdiDevice.from_pdi_command(self.pdi_command)

    def __repr__(self) -> str:
        return f"[PDI {self._pdi_command.friendly} {self.payload}]"

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    @staticmethod
    def _calculate_checksum(data: bytes, add_stf=True) -> Tuple[bytes, bytes]:
        """
        Used to calculate checksums on packets we send as well as to strip Stuff bytes
        from packets we receive
        """
        byte_stream = bytes()
        check_sum = 0
        last_byte = None
        for b in data:
            check_sum += b
            if b in {PDI_SOP, PDI_STF, PDI_EOP}:
                if add_stf is True:
                    # add the stuff byte to the output and account for it in the check sum
                    check_sum += PDI_STF
                    byte_stream += PDI_STF.to_bytes(1, byteorder="big")
                elif b in {PDI_SOP, PDI_EOP}:
                    # we are parsing a received packet; strip stuff byte
                    pass  # we want this byte added to the output stream
                else:
                    # this must be a stuff byte, and we are receiving; strip it
                    # unless the previous byte was also a stuff byte
                    if last_byte != PDI_STF:
                        last_byte = b
                        continue
            byte_stream += b.to_bytes(1, byteorder="big")
            last_byte = b
        # do checksum calculation on buffer
        byte_sum = check_sum
        check_sum = 0xFF & (0 - check_sum)
        if check_sum in {PDI_SOP, PDI_STF, PDI_EOP}:
            if add_stf is True:
                byte_stream += PDI_STF.to_bytes(1, byteorder="big")
            byte_sum += PDI_STF
            check_sum = 0xFF & (0 - byte_sum)
        return byte_stream, check_sum.to_bytes(1, byteorder="big")

    @property
    def pdi_command(self) -> PdiCommand:
        return self._pdi_command

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @scope.setter
    def scope(self, scope: CommandScope) -> None:
        if scope is None or not isinstance(scope, CommandScope):
            raise ValueError(f"Invalid CommandScope: {scope}")
        self._scope = scope

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @tmcc_id.setter
    def tmcc_id(self, tmcc_id: int) -> None:
        self._tmcc_id = tmcc_id

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
        # if this request was constructed from a byte stream, return
        # the original stream if we call as_bytes
        if self._original:
            return self._original
        """
        Default implementation, should override in more complex requests
        """
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
        if self.action is None:
            byte_str += CommonAction.CONFIG.as_bytes
        else:
            byte_str += self.action.as_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str

    @property
    def checksum(self) -> bytes:
        check_sum = 0
        for b in self._data:
            if b in {PDI_SOP, PDI_EOP}:
                continue
            check_sum += b
        check_sum = 0xFF & (0 - check_sum)
        return check_sum.to_bytes(1)

    @property
    def is_ping(self) -> bool:
        return self._pdi_command == PdiCommand.PING

    @property
    def is_ack(self) -> bool:
        return False

    @property
    def is_tmcc(self) -> bool:
        return self._pdi_command.is_tmcc

    @property
    def is_lcs(self) -> bool:
        return False

    @property
    def is_tmcc_rx(self) -> bool:
        return False

    @property
    def is_filtered(self) -> bool:
        return False

    @staticmethod
    def decode_text(data: bytes) -> str | None:
        name = ""
        for b in data:
            if b == 0:
                break
            name += chr(b)
        return name

    @staticmethod
    def encode_text(text: str, field_len: int) -> bytes | None:
        if text is None:
            return b"\x00" * field_len
        else:
            return bytes(text, "ascii").ljust(field_len, b"\x00")

    @property
    def payload(self) -> str:
        return f"({self.packet})"

    @property
    def packet(self) -> str:
        if self._data is None:
            return "0x" + self.as_bytes.hex(" ").upper()
        else:
            return "0x" + self._data.hex(" ").upper()

    def send(
        self,
        repeat: int = 1,
        delay: float = 0.0,
        duration: float = 0.0,
        interval: int = None,
        baudrate: int = None,
        port: str | int = None,
        server: str = None,
    ) -> None:
        """
        Send PDI command bytes to TMCC Buffer for dispatch; the TMCC buffer
        will dispatch to the appropriate sender (tmcc or pdi)
        """
        from ..comm.comm_buffer import CommBuffer

        repeat = Validations.validate_int(repeat, min_value=1, label="repeat")
        delay = Validations.validate_float(delay, min_value=0, label="delay")
        duration = Validations.validate_float(duration, min_value=0, label="duration", allow_none=True)
        interval = Validations.validate_int(
            interval,
            min_value=MINIMUM_DURATION_INTERVAL_MSEC,
            label="interval",
            allow_none=True,
        )

        buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)
        for rep_no in range(repeat):
            buffer.enqueue_command(self.as_bytes, delay=delay)
            if duration > 0:
                interval = interval if interval else DEFAULT_DURATION_INTERVAL_MSEC
                # convert duration into milliseconds, then queue a command to fire
                # every 100 msec for the duration
                pause = 0
                for d in range(interval, int(round(duration * 1000)), interval):
                    buffer.enqueue_command(self.as_bytes, delay + (d / 1000.0) - pause)
                    pause += 0.002
                    sleep(0.002)


class TmccReq(PdiReq):
    from ..protocol.command_req import CommandReq

    @classmethod
    def as_packets(cls, tmcc_cmd: CommandReq) -> List[bytes]:
        """
        Used to decompose multibyte TMCC commands into 3-byte packets, sending each
        as a PdiCommand.TMCC_TX packet
        """
        byte_str = tmcc_cmd.as_bytes
        packets = []
        for i in range(0, len(byte_str), 3):
            packet = PdiCommand.TMCC_TX.to_bytes(1, byteorder="big") + byte_str[i : i + 3]
            packet, checksum = cls._calculate_checksum(packet)
            packet = PDI_SOP.to_bytes(1, byteorder="big") + packet
            packet += checksum
            packet += PDI_EOP.to_bytes(1, byteorder="big")
            packets.append(packet)
        return packets

    def __init__(self, data: bytes | CommandReq, pdi_command: PdiCommand = None):
        super().__init__(data, pdi_command=pdi_command)
        from ..protocol.command_req import CommandReq

        if isinstance(data, CommandReq):
            if self.pdi_command.is_tmcc is False:
                raise ValueError(f"Invalid PDI TMCC Request: {self.pdi_command}")
            self._tmcc_command: CommandReq = data
        else:
            pdi_command = PdiCommand(data[1])
            if pdi_command in {PdiCommand.TMCC4_TX, PdiCommand.TMCC4_RX}:
                self._tmcc_command: CommandReq = CommandReq.from_bytes(
                    self._data[1:],
                    from_tmcc_rx=True if pdi_command == PdiCommand.TMCC4_RX else False,
                    is_tmcc4=True,
                )
            elif pdi_command in {PdiCommand.TMCC_TX, PdiCommand.TMCC_RX}:
                self._tmcc_command: CommandReq = CommandReq.from_bytes(
                    self._data[1:], from_tmcc_rx=True if pdi_command == PdiCommand.TMCC_RX else False
                )
            else:
                raise ValueError(f"Invalid PDI TMCC Request: {data}")

    def __repr__(self) -> str:
        data = f" (0x{self._data.hex()})" if self._data else ""
        return f"[PDI {self._pdi_command.friendly} {self.tmcc_command}{data}]"

    @property
    def tmcc_command(self) -> CommandReq:
        return self._tmcc_command

    @property
    def is_tmcc_rx(self) -> bool:
        return self._pdi_command == PdiCommand.TMCC_RX

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes + self.tmcc_command.as_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str

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
