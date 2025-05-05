import time
from datetime import datetime

from .constants import PdiCommand, D4Action, PDI_SOP, PDI_EOP
from ..db.comp_data import BASE_MEMORY_ENGINE_READ_MAP, CompData, CompDataMixin, CompDataHandler
from .pdi_req import PdiReq
from ..protocol.constants import CommandScope

LIONEL_EPOCH: int = 1577836800  # Midnight, Jan 1 2020 UTC


class D4Req(PdiReq, CompDataMixin):
    @staticmethod
    def lionel_timestamp(as_bytes: bool = True) -> int | bytes:
        lts = 0xFFFFFFFF & int(time.time() - LIONEL_EPOCH)
        if as_bytes is True:
            return lts.to_bytes(4, byteorder="little")
        else:
            return lts

    def __init__(
        self,
        data: bytes | int = 0,
        pdi_command: PdiCommand = PdiCommand.D4_ENGINE,
        action: D4Action = D4Action.QUERY,
        error: bool = False,
        tmcc_id: int = 0,
        post_action: int = 0,
        start: int = 0,
        data_length: int = 1,
        data_bytes: int | str | bytes | None = None,
        count: int | None = None,
        timestamp: int | None = None,
        state: CompDataMixin = None,
    ) -> None:
        super().__init__(data, pdi_command)
        self._scope = CommandScope.TRAIN if self.pdi_command == PdiCommand.D4_TRAIN else CommandScope.ENGINE
        self._record_no = self._next_record_no = self._tmcc_id = self._count = self._post_action = self._suffix = None
        self._data_length = self._data_bytes = self._start = self._timestamp = None
        self._error = error
        self._tmcc_id = tmcc_id
        if isinstance(data, bytes):
            data_len = len(self._data)
            self._record_no = int.from_bytes(self._data[1:3], byteorder="little") if data_len > 2 else None
            self._action = D4Action(self._data[3]) if data_len > 3 else None
            self._post_action = int.from_bytes(self._data[4:6]) if data_len > 5 else None
            self._suffix = int.from_bytes(self._data[8:10], byteorder="little") if data_len > 9 else None
            if self._action in {D4Action.QUERY, D4Action.UPDATE}:
                self._start = self._data[6] if data_len > 6 else None
                self._data_length = self._data[7] if data_len > 7 else None
                self._timestamp = int.from_bytes(self._data[8:12], byteorder="little") if data_len > 11 else None
                data_bytes = self._data[12:] if data_len > 12 else None
                if isinstance(data_bytes, bytes):
                    self._data_bytes = data_bytes
                    if self.start == 0 and self.data_length == PdiReq.scope_record_length(CommandScope.ENGINE):
                        self._comp_data = CompData.from_bytes(data_bytes, self.scope)
                        self._tmcc_id = self._comp_data.tmcc_id
                        self._comp_data_record = True  # mark this req as containing a complete CompData record
                    elif isinstance(data_bytes, str):
                        self._data_bytes = data_bytes[0:data_length].encode("ascii")
                        if len(data_bytes) < data_length:
                            self._data_bytes += bytes() * (data_length - len(data_bytes))
                    elif isinstance(data_bytes, int):
                        self._data_bytes = data_bytes.to_bytes(data_length, byteorder="little")
            elif self.action == D4Action.COUNT:
                self._scope = CommandScope.BASE
                self._count = int.from_bytes(self._data[6:8], byteorder="little") if data_len > 7 else None
            elif self.action == D4Action.MAP:
                self._suffix = None
                if data_len > 9:
                    addr_str = ""
                    for i in range(6, 10):
                        addr_str += chr(self._data[i])
                    self._tmcc_id = int(addr_str)
            elif self.action in {D4Action.FIRST_REC, D4Action.NEXT_REC}:
                if self._action == D4Action.NEXT_REC:
                    self._post_action = int.from_bytes(self._data[4:6]) if data_len > 5 else None
                    self._start = 0
                    self._data_length = self._data[7] if data_len > 7 else None
                    self._next_record_no = (
                        int.from_bytes(self._data[8:10], byteorder="little") if data_len > 9 else None
                    )
                else:
                    self._next_record_no = self.record_no
                    self._scope = CommandScope.BASE  # send first record information to Base
        else:
            from ..db.engine_state import EngineState

            self._action = action
            self._record_no = int(data)
            self._post_action = post_action
            self._start = start
            self._data_length = data_length
            self._data_bytes = data_bytes
            self._count = count
            self._timestamp = timestamp
            self._state = state
            if state and isinstance(state, EngineState):
                self._tmcc_id = state.tmcc_id
                self._start = 0
                self._data_length = PdiReq.scope_record_length(CommandScope.ENGINE)
                if isinstance(state, CompDataMixin):
                    self._data_bytes = state.comp_data.as_bytes()
            elif self.action in {D4Action.FIRST_REC, D4Action.COUNT}:
                self._scope = CommandScope.BASE

    @property
    def as_key(self):
        return self.record_no, self.pdi_command, self.action, self.scope

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
    def start(self) -> int:
        return self._start

    @property
    def data_length(self) -> int:
        return self._data_length

    @property
    def count(self) -> int:
        return self._count

    @property
    def next_record_no(self) -> int:
        return self._next_record_no

    @property
    def timestamp(self) -> int:
        return self._timestamp

    @property
    def name(self) -> str | None:
        if self.comp_data:
            return self.comp_data.road_name
        else:
            return None

    @property
    def number(self) -> str | None:
        if self.comp_data:
            return self.comp_data.road_number
        else:
            return None

    @property
    def timestamp_str(self) -> str:
        if self.timestamp:
            return datetime.fromtimestamp(self.timestamp + LIONEL_EPOCH).strftime("%Y-%m-%d %H:%M:%S")
        return ""

    @property
    def payload(self) -> str:
        if self.action:
            ct = tmcc = dl = di = db = ts = ""
            op = self.action.title
            rn = f" #{self.record_no}" if self.record_no is not None else ""
            sf = f" {self.suffix}" if self.suffix is not None else ""
            if self.action == D4Action.COUNT:
                rn = ""
                ct = f": {self.count}" if self.count is not None else ""
            elif self.action == D4Action.MAP:
                tmcc = f" TMCC ID: {self.tmcc_id}" if self.tmcc_id else ""
                if self.record_no == 0xFFFF:
                    rn = " Not Found"
            elif self.action in {D4Action.QUERY, D4Action.UPDATE}:
                tmcc = f" TMCC ID: {self.tmcc_id}" if self.tmcc_id else ""
                sf = ""
                ts = f" {self.timestamp_str}"
                di = f" Index: {hex(self.start)}" if self.start is not None else ""
                dl = f" Length: {self.data_length}" if self.data_length is not None else ""
                tpl = BASE_MEMORY_ENGINE_READ_MAP.get(self.start, None)
                if isinstance(tpl, CompDataHandler) and self._data_bytes and (self.data_length == tpl.length):
                    db = f" Data: {tpl.from_bytes(self._data_bytes)}"
                else:
                    db = (
                        f" Data: {self._data_bytes.hex()}"
                        if self._data_bytes is not None and len(self._data_bytes) < 0xC0
                        else " Data: None"
                    )
            return f"{op}{tmcc}{rn}{ct}{sf}{di}{dl}{db}{ts} ({self.packet})"
        return super().payload

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.record_no.to_bytes(2, byteorder="little")
        byte_str += self.action.as_bytes
        if self.action in {D4Action.COUNT, D4Action.MAP, D4Action.NEXT_REC, D4Action.QUERY, D4Action.UPDATE}:
            byte_str += (self.post_action if self.post_action else 0).to_bytes(2, byteorder="little")
        if self.action == D4Action.COUNT:
            byte_str += self.count.to_bytes(2, byteorder="little") if self.count is not None else bytes()
            byte_str += self.suffix.to_bytes(2, byteorder="little") if self.suffix is not None else bytes()
        elif self.action == D4Action.FIRST_REC:
            self._scope = CommandScope.SYSTEM
            byte_str += (0).to_bytes(1, byteorder="big")
        elif self.action == D4Action.NEXT_REC:
            self._scope = CommandScope.SYSTEM
            byte_str += self.start.to_bytes(1, byteorder="big") if self.start is not None else bytes()
            byte_str += self.data_length.to_bytes(1, byteorder="big") if self.data_length is not None else bytes()
            byte_str += (
                self.next_record_no.to_bytes(2, byteorder="little") if self.next_record_no is not None else bytes()
            )
        elif self.action == D4Action.MAP:
            byte_str += str(self.tmcc_id).zfill(4).encode("ascii") if self.tmcc_id else bytes()
        elif self.action in {D4Action.QUERY, D4Action.UPDATE}:
            byte_str += self.start.to_bytes(1, byteorder="big") if self.start is not None else bytes()
            byte_str += self.data_length.to_bytes(1, byteorder="big") if self.data_length is not None else bytes()
            byte_str += (
                self.timestamp.to_bytes(4, byteorder="little")
                if self.timestamp is not None
                else self.lionel_timestamp()
            )
            if self._data_bytes is not None:
                byte_str += self._data_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str
