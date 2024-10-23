from __future__ import annotations

from typing import Dict

from src.pdi.constants import PdiCommand, PDI_SOP, PDI_EOP
from src.pdi.pdi_req import PdiReq
from src.protocol.constants import CommandScope

ROUTE_THROW_RATE_MAP: Dict[int, float] = {
    1: 0.00,
    2: 0.25,
    3: 0.50,
    4: 0.75,
    5: 1.00,
    6: 1.25,
    7: 1.50,
    8: 1.75,
    9: 2.00,
}


class BaseReq(PdiReq):
    @classmethod
    def update_speed(cls, address: int, speed: int, scope: CommandScope = CommandScope.ENGINE) -> BaseReq:
        if scope == CommandScope.TRAIN:
            return cls(address, PdiCommand.UPDATE_TRAIN_SPEED, speed=speed)
        else:
            return cls(address, PdiCommand.UPDATE_ENGINE_SPEED, speed=speed)

    def __init__(
        self,
        data: bytes | int = 0,
        pdi_command: PdiCommand = PdiCommand.BASE,
        flags: int = 2,
        speed: int = None,
    ) -> None:
        super().__init__(data, pdi_command)
        if self.pdi_command.is_base is False:
            raise ValueError(f"Invalid PDI Base Request: {data}")
        self._status = self._valid1 = self._valid2 = self._firmware_high = self._firmware_low = None
        self._route_throw_rate = self._name = self._number = None
        self._rev_link = self._fwd_link = None
        self._loco_type = self._control_type = self._sound_type = self._engine_class = self._speed_step = None
        self._scope = CommandScope.SYSTEM
        if isinstance(data, bytes):
            data_len = len(self._data)
            self._record_no = self._data[1] if data_len > 1 else None
            self._flags = self._data[2] if data_len > 2 else None
            self._status = self._data[3] if data_len > 3 else None
            self._valid1 = int.from_bytes(self._data[4:6], byteorder="big") if data_len > 5 else None

            if self.pdi_command == PdiCommand.BASE_ENGINE:
                self._scope = CommandScope.ENGINE
                self._valid2 = int.from_bytes(self._data[6:8], byteorder="big") if data_len > 7 else None
                self._rev_link = self._data[8] if data_len > 8 else None
                self._fwd_link = self._data[9] if data_len > 9 else None
                self._name = self.decode_name(self._data[11:]) if data_len > 11 else None
                self._number = self.decode_name(self._data[44:]) if data_len > 44 else None
                self._loco_type = self._data[49] if data_len > 49 else None
                self._control_type = self._data[50] if data_len > 50 else None
                self._sound_type = self._data[51] if data_len > 51 else None
                self._engine_class = self._data[52] if data_len > 52 else None
                self._speed_step = self._data[56] if data_len > 56 else None
                self._run_level = self._data[57] if data_len > 57 else None
                self._labor_bias = self._data[58] if data_len > 58 else None
                self._speed_limit = self._data[59] if data_len > 59 else None
                self._max_speed = self._data[60] if data_len > 60 else None
                self._fuel_level = self._data[61] if data_len > 61 else None
                self._water_level = self._data[62] if data_len > 62 else None
                self._tmcc_id = self._data[63] if data_len > 63 else None
                self._train_pos = self._data[64] if data_len > 64 else None
                self._smoke_level = self._data[65] if data_len > 65 else None
                self._train_brake = self._data[66] if data_len > 66 else None
                self._momentum = self._data[67] if data_len > 67 else None
            elif self.pdi_command == PdiCommand.BASE:
                self._firmware_high = self._data[7] if data_len > 7 else None
                self._firmware_low = self._data[8] if data_len > 8 else None
                self._route_throw_rate = self.decode_throw_rate(self._data[9]) if data_len > 9 else None
                self._name = self.decode_name(self._data[10:]) if data_len > 10 else None
        else:
            self._record_no = int(data)
            self._flags = flags
            self._speed_step = speed

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def record_no(self) -> int:
        return self._record_no

    @property
    def tmcc_id(self) -> int:
        return self.record_no

    @property
    def flags(self) -> int:
        return self._flags

    @property
    def status(self) -> int:
        return self._status

    @property
    def forward_link(self) -> int:
        return self._fwd_link

    @property
    def valid1(self) -> int:
        return self._valid1

    @property
    def name(self) -> str:
        return self._name

    @property
    def number(self) -> str:
        return self._number

    @property
    def speed(self) -> int:
        return self._speed_step

    @property
    def payload(self) -> str:
        f = hex(self.flags) if self.flags is not None else "NA"
        s = self.status if self.status is not None else "NA"
        v = hex(self.valid1) if self.valid1 is not None else "NA"
        if self.pdi_command == PdiCommand.BASE_ENGINE:
            tmcc = self.record_no
            fwl = f" Fwd: {self._fwd_link}" if self._fwd_link is not None else ""
            rvl = f" Rev: {self._rev_link}" if self._rev_link is not None else ""
            na = f" {self._name}" if self._name is not None else ""
            no = f" {self._number}" if self._number is not None else ""
            v2 = f" {hex(self._valid2)}" if self._valid2 is not None else ""
            sp = f" SS: {self._speed_step}" if self._speed_step is not None else ""
            return f"# {tmcc}{na}{no}{sp} flags: {f} status: {s} valid: {v}{v2}{fwl}{rvl}\n{self.packet}"
        elif self.pdi_command == PdiCommand.BASE:
            fw = f" V{self._firmware_high}.{self._firmware_low}" if self._firmware_high is not None else ""
            tr = f" Route Throw Rate: {self._route_throw_rate} sec" if self._route_throw_rate is not None else ""
            n = f"{self._name} " if self._name is not None else ""
            return f"{n}Rec # {self.record_no} flags: {f} status: {s} valid: {v}{fw}{tr}\n{self.packet}"
        elif self.pdi_command in [PdiCommand.UPDATE_ENGINE_SPEED, PdiCommand.UPDATE_TRAIN_SPEED]:
            scope = "Engine" if self.pdi_command == PdiCommand.UPDATE_ENGINE_SPEED else "Train"
            return f"{scope} #{self.tmcc_id} New Speed: {self.speed}"
        return f"Rec # {self.record_no} flags: {f} status: {s} valid: {v}\n{self.packet}"

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.pdi_command.as_bytes
        byte_str += self.record_no.to_bytes(1, byteorder="big")
        if self.pdi_command in [PdiCommand.UPDATE_ENGINE_SPEED, PdiCommand.UPDATE_TRAIN_SPEED]:
            byte_str += self.speed.to_bytes(1, byteorder="big")
        else:
            byte_str += self.flags.to_bytes(1, byteorder="big")
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str

    @staticmethod
    def decode_throw_rate(data: int) -> float | None:
        if data in ROUTE_THROW_RATE_MAP:
            return ROUTE_THROW_RATE_MAP[data]
        else:
            return None

    @staticmethod
    def encode_throw_rate(data: float) -> int | None:
        for key, value in ROUTE_THROW_RATE_MAP.items():
            if value <= data < value + 0.25:
                return key
        return 9

    @staticmethod
    def decode_name(data: bytes) -> str | None:
        name = ""
        for b in data:
            if b == 0:
                break
            name += chr(b)
        return name
