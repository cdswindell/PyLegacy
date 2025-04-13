from .constants import PdiCommand, D4Action, PDI_SOP, PDI_EOP
from .pdi_req import PdiReq
from ..protocol.constants import CommandScope


class D4Req(PdiReq):
    def __init__(
        self,
        data: bytes | int = 0,
        pdi_command: PdiCommand = PdiCommand.D4_ENGINE,
        action: D4Action = D4Action.QUERY,
        error: bool = False,
        tmcc_id: int | None = None,
        post_action: int | None = None,
        start: int | None = None,
        data_length: int | None = None,
        data_bytes: bytes | None = None,
    ) -> None:
        super().__init__(data, pdi_command)
        self._scope = CommandScope.ENGINE
        self._record_no = self._tmcc_id = self._count = self._post_action = self._suffix = None
        self._data_length = self._data_bytes = self._start = None
        self._error = error
        if isinstance(data, bytes):
            data_len = len(self._data)
            self._record_no = int.from_bytes(self._data[1:3], byteorder="little") if data_len > 2 else None
            self._action = D4Action(self._data[3]) if data_len > 3 else None
            self._post_action = int.from_bytes(self._data[4:6]) if data_len > 5 else None
            self._suffix = int.from_bytes(self._data[8:10], byteorder="little") if data_len > 9 else None
            if self._action == D4Action.COUNT:
                self._scope = CommandScope.BASE
                self._tmcc_id = 0
                self._count = int.from_bytes(self._data[6:8], byteorder="little") if data_len > 7 else None
            elif self._action == D4Action.MAP:
                self._suffix = None
                if data_len > 9:
                    addr_str = ""
                    for i in range(6, 10):
                        addr_str += chr(self._data[i])
                    self._tmcc_id = int(addr_str)
                else:
                    self._tmcc_id = 0
        else:
            self._action = action
            self._record_no = int(data)
            self._post_action = post_action
            self._start = start
            self._data_length = data_length
            self._data_bytes = data_bytes
            self._tmcc_id = tmcc_id

    @property
    def record_no(self) -> int:
        return self._record_no

    @property
    def action(self) -> D4Action:
        return self._action

    @property
    def post_action(self) -> int:
        return self._post_action

    @property
    def suffix(self) -> int:
        return self._suffix

    @property
    def count(self) -> int:
        return self._count

    @property
    def payload(self) -> str:
        if self.action:
            ct = tmcc = ""
            op = self.action.title
            rn = f" #{self.record_no}" if self.record_no is not None else ""
            if self.action == D4Action.COUNT:
                rn = ""
                ct = f": {self.count}" if self.count is not None else ""
            elif self.action == D4Action.MAP:
                tmcc = f" TMCC ID: {self.tmcc_id}" if self.tmcc_id else ""
            sf = f" {self.suffix}" if self.suffix is not None else ""
            return f"{op}{tmcc}{rn}{ct}{sf} ({self.packet})"
        return super().payload

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.record_no.to_bytes(2, byteorder="little")
        byte_str += self.action.as_bytes
        byte_str += (self.post_action if self.post_action else 0).to_bytes(2, byteorder="little")
        if self.action == D4Action.COUNT:
            byte_str += self.count.to_bytes(2, byteorder="little") if self.count is not None else bytes()
            byte_str += self.suffix.to_bytes(2, byteorder="little") if self.suffix is not None else bytes()
        elif self.action == D4Action.MAP:
            if self.tmcc_id:
                byte_str += str(self.tmcc_id).zfill(4).encode("ascii")
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str
