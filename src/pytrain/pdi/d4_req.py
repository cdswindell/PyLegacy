from .constants import PdiCommand, D4Op, PDI_SOP, PDI_EOP
from .pdi_req import PdiReq
from ..protocol.constants import CommandScope


class D4Req(PdiReq):
    def __init__(
        self,
        data: bytes | int = 0,
        pdi_command: PdiCommand = PdiCommand.D4_ENGINE,
        op: D4Op = D4Op.QUERY,
        start: int | None = None,
        data_length: int | None = None,
        data_bytes: bytes | None = None,
    ) -> None:
        super().__init__(data, pdi_command)
        self._scope = CommandScope.ENGINE
        self._record_no = self._tmcc_id = self._count = self._suffix = None
        self._data_length = self._data_bytes = self._start = None
        if isinstance(data, bytes):
            print("***", self._data.hex())
            data_len = len(self._data)
            self._record_no = int.from_bytes(self._data[1:3], byteorder="little") if data_len > 2 else None
            self._op = D4Op(self._data[3]) if data_len > 3 else None
            if self._op == D4Op.COUNT:
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
    def op(self) -> D4Op:
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
            print(self.op)
            ct = ""
            op = self.op.name.lower()
            rn = f" {self.record_no} " if self.record_no is not None else ""
            if self.op == D4Op.COUNT:
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
        if self.op == D4Op.COUNT:
            byte_str += self.count.to_bytes(2, byteorder="little") if self.count is not None else bytes()
            byte_str += self.suffix.to_bytes(2, byteorder="little") if self.suffix is not None else bytes()
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str
