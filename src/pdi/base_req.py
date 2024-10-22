from __future__ import annotations

from src.pdi.constants import PdiCommand, PDI_SOP, PDI_EOP
from src.pdi.pdi_req import PdiReq
from src.protocol.constants import CommandScope


class BaseReq(PdiReq):
    def __init__(
        self,
        data: bytes | int = 0,
        pdi_command: PdiCommand = PdiCommand.BASE,
        flags: int = 2,
    ) -> None:
        super().__init__(data, pdi_command)
        if self.pdi_command.is_base is False:
            raise ValueError(f"Invalid PDI Base Request: {data}")
        if isinstance(data, bytes):
            data_len = len(self._data)
            self._record_no = self._data[1] if data_len > 1 else None
            self._flags = self._data[2] if data_len > 2 else None
            self._status = self._data[3] if data_len > 3 else None
            self._valid1 = int.from_bytes(self._data[5:7], byteorder="big") if data_len > 6 else None
        else:
            self._record_no = int(data)
            self._flags = flags
            self._status = self._valid1 = None

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM

    @property
    def record_no(self) -> int:
        return self._record_no

    @property
    def flags(self) -> int:
        return self._flags

    @property
    def status(self) -> int:
        return self._status

    @property
    def valid1(self) -> int:
        return self._valid1

    @property
    def payload(self) -> str:
        f = hex(self.flags) if self.flags is not None else "NA"
        s = self.status if self.status is not None else "NA"
        v = hex(self.valid1) if self.valid1 is not None else "NA"
        return f"Record: {self.record_no} flags: {f} status: {s} valid: {v} {self.packet}"

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.pdi_command.as_bytes
        byte_str += self.record_no.to_bytes(1, byteorder="big")
        byte_str += self.flags.to_bytes(1, byteorder="big")
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str
