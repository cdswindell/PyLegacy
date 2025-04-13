from .constants import PdiCommand, Base4DOp, PDI_SOP, PDI_EOP
from .pdi_req import PdiReq
from ..protocol.constants import CommandScope


class Base4DReq(PdiReq):
    def __init__(
        self,
        data: bytes | int = 0,
        pdi_command: PdiCommand = PdiCommand.BASE_ENGINE_4D,
        op: Base4DOp = Base4DOp.QUERY,
        start: int | None = None,
        data_length: int | None = None,
        data_bytes: bytes | None = None,
    ) -> None:
        super().__init__(data, pdi_command)
        self._scope = CommandScope.ENGINE
        self._record_no = self._tmcc_id = self._count = self._suffix = None
        self._data_length = self._data_bytes = self._start = None
        if isinstance(data, bytes):
            data_len = len(self._data)
            self._record_no = int.from_bytes(self._data[1:3], byteorder="little") if data_len > 2 else None
            self._op = Base4DOp(self._data[3]) if data_len > 3 else None
            if self._op == Base4DOp.COUNT:
                self._count = int.from_bytes(self._data[4:6], byteorder="little") if data_len > 5 else None
                self._suffix = int.from_bytes(self._data[6:8], byteorder="little") if data_len > 7 else None
        else:
            self._op = op
            self._record_no = int(data)
            self._start = start
            self._data_length = data_length
            self._data_bytes = data_bytes

    @property
    def record_no(self) -> int:
        return self._record_no

    @property
    def op(self) -> Base4DOp:
        return self._op

    @property
    def count(self) -> int:
        return self._count

    @property
    def suffix(self) -> int:
        return self._suffix

    @property
    def payload(self) -> str:
        if self.op:
            op = self.op.name.lower()
            rn = f" {self.record_no} " if self.record_no is not None else ""
            ct = f" {self.count} " if self.count is not None else ""
            sf = f" {self.suffix} " if self.suffix is not None else ""
            return f"{op}{rn}{ct}{sf} ({self.packet})"
        return super().payload

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.record_no.to_bytes(2, byteorder="little")
        byte_str += self.op.as_bytes
        byte_str += (0).to_bytes(2, byteorder="little")
        if self.op == Base4DOp.COUNT:
            byte_str += self.count.to_bytes(2, byteorder="little") if self.count is not None else bytes()
            byte_str += self.suffix.to_bytes(2, byteorder="little") if self.suffix is not None else bytes()
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str
