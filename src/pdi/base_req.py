from __future__ import annotations

from math import floor
from typing import Dict

from .constants import PdiCommand, PDI_SOP, PDI_EOP
from .pdi_req import PdiReq
from ..db.component_state import ComponentState
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, CONTROL_TYPE, SOUND_TYPE, LOCO_TYPE, LOCO_CLASS

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

ENGINE_WRITE_MAP = {
    "ABSOLUTE_SPEED": (11, 56, None),
    "STOP_IMMEDIATE": (11, 56, lambda t: 0),
    "DIESEL_RPM": (12, 57, None),
    "ENGINE_LABOR": (13, 58, lambda t: t + 12),
    "TRAIN_BRAKE": (21, 67, lambda t: round(t * 2.143)),
    "SMOKE_HIGH": (19, 65, lambda t: 3),
    "SMOKE_MEDIUM": (19, 65, lambda t: 2),
    "SMOKE_LOW": (19, 65, lambda t: 1),
    "SMOKE_OFF": (19, 65, lambda t: 0),
    "MOMENTUM_HIGH": (22, 68, lambda t: 127),
    "MOMENTUM_MEDIUM": (22, 68, lambda t: 63),
    "MOMENTUM_LOW": (22, 68, lambda t: 0),
    "MOMENTUM": (22, 68, lambda t: floor(t * 18.285)),
    "DITCH_OFF": (20, 66, lambda t: 0),
    "DITCH_OFF_PULSE_ON_WITH_HORN": (20, 66, lambda t: 1),
    "DITCH_ON_PULSE_OFF_WITH_HORN": (20, 66, lambda t: 2),
    "DITCH_ON": (20, 68, lambda t: 3),
}


class BaseReq(PdiReq):
    @classmethod
    def update_speed(cls, address: int, speed: int, scope: CommandScope = CommandScope.ENGINE) -> BaseReq:
        if scope == CommandScope.TRAIN:
            return cls(address, PdiCommand.UPDATE_TRAIN_SPEED, speed=speed)
        else:
            return cls(address, PdiCommand.UPDATE_ENGINE_SPEED, speed=speed)

    @classmethod
    def update_eng(
        cls,
        cmd: CommandDefEnum | CommandReq,
        address: int = None,
        data: int | None = None,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> BaseReq | None:
        if isinstance(cmd, CommandReq):
            state = cmd.command
            address = cmd.address
            data = cmd.data
            scope = cmd.scope
        elif isinstance(cmd, CommandDefEnum):
            state = cmd
        else:
            raise ValueError(f"Invalid option: {cmd}")
        if state.name in ENGINE_WRITE_MAP:
            bit_pos, offset, scaler = ENGINE_WRITE_MAP[state.name]
            # print(f"State: {state} {data} {bit_pos} {offset} {scaler(data)}")
            if bit_pos <= 15:
                value1 = 1 << bit_pos
                value2 = 0
            else:
                value1 = 0
                value2 = 1 << (bit_pos - 15)
            # build data packet
            if scaler:
                data = scaler(data)
            byte_str = bytes()
            pdi_cmd = PdiCommand.BASE_ENGINE if scope == CommandScope.ENGINE else PdiCommand.BASE_TRAIN
            byte_str += pdi_cmd.to_bytes(1, byteorder="big")
            byte_str += address.to_bytes(1, byteorder="big")
            byte_str += (0xC2).to_bytes(1, byteorder="big")
            byte_str += (0x00).to_bytes(2, byteorder="big")  # result byte + spare
            byte_str += value1.to_bytes(2, byteorder="little")
            byte_str += value2.to_bytes(2, byteorder="little")
            # fill the buffer with zeros up to offset point
            byte_str += (0x00).to_bytes(1, byteorder="big") * (offset - len(byte_str))
            # now add data
            byte_str += data.to_bytes(1, byteorder="big")
            # now add SOP, EOP, and Checksum
            byte_str, checksum = cls._calculate_checksum(byte_str)
            byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
            byte_str += checksum
            byte_str += PDI_EOP.to_bytes(1, byteorder="big")
            return cls(byte_str)
        return None

    def __init__(
        self,
        data: bytes | int = 0,
        pdi_command: PdiCommand = PdiCommand.BASE,
        flags: int = 2,
        speed: int = None,
        state: ComponentState = None,
    ) -> None:
        super().__init__(data, pdi_command)
        if self.pdi_command.is_base is False:
            raise ValueError(f"Invalid PDI Base Request: {data}")
        self._status = self._valid1 = self._valid2 = self._firmware_high = self._firmware_low = None
        self._route_throw_rate = self._name = self._number = None
        self._rev_link = self._fwd_link = None
        self._loco_type = self._control_type = self._sound_type = self._loco_class = None
        self._speed_step = self._speed_limit = self._max_speed = self._labor_bias = None
        self._fuel_level = self._water_level = self._last_train_id = self._train_pos = self._train_brake = None
        self._smoke_level = self._ditch_lights = self._momentum = self._momentum_tmcc = None
        self._state = state
        if isinstance(data, bytes):
            data_len = len(self._data)
            self._record_no = self.tmcc_id = self._data[1] if data_len > 1 else None
            self._flags = self._data[2] if data_len > 2 else None
            self._status = self._data[3] if data_len > 3 else None
            _ = self._data[4] if data_len > 4 else None
            self._valid1 = int.from_bytes(self._data[5:7], byteorder="little") if data_len > 5 else None

            if self.pdi_command in [PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN]:
                self.scope = CommandScope.ENGINE if self.pdi_command == PdiCommand.BASE_ENGINE else CommandScope.TRAIN
                self._valid2 = int.from_bytes(self._data[7:9], byteorder="little") if data_len > 7 else None
                self._rev_link = self._data[9] if data_len > 9 else None
                self._fwd_link = self._data[10] if data_len > 10 else None
                self._name = self.decode_text(self._data[11:44]) if data_len > 11 else None
                self._number = self.decode_text(self._data[44:49]) if data_len > 44 else None
                self._loco_type = self._data[49] if data_len > 49 else None
                self._control_type = self._data[50] if data_len > 50 else None
                self._sound_type = self._data[51] if data_len > 51 else None
                self._loco_class = self._data[52] if data_len > 52 else None
                self._tsdb_left = self._data[53] if data_len > 53 else None
                self._tsdb_right = self._data[54] if data_len > 54 else None
                self._spare = self._data[55] if data_len > 55 else None
                self._speed_step = self._data[56] if data_len > 56 else None
                self._run_level = self._data[57] if data_len > 57 else None
                self._labor_bias = self._data[58] if data_len > 58 else None
                self._speed_limit = self._data[59] if data_len > 59 else None
                self._max_speed = self._data[60] if data_len > 60 else None
                self._fuel_level = self._data[61] if data_len > 61 else None
                self._water_level = self._data[62] if data_len > 62 else None
                self._last_train_id = self._data[63] if data_len > 63 else None
                self._train_pos = self._data[64] if data_len > 64 else None
                self._smoke_level = self._data[65] if data_len > 65 else None
                self._ditch_lights = self._data[66] if data_len > 66 else None
                self._train_brake = self._data[67] if data_len > 67 else None
                self._momentum = self._data[68] if data_len > 68 else None
                self._momentum_tmcc = floor(self._data[68] / 16) if data_len > 68 else None
            elif self.pdi_command in [PdiCommand.BASE_ACC, PdiCommand.BASE_SWITCH, PdiCommand.BASE_ROUTE]:
                if self.pdi_command == PdiCommand.BASE_ACC:
                    self.scope = CommandScope.ACC
                elif self.pdi_command == PdiCommand.BASE_SWITCH:
                    self.scope = CommandScope.SWITCH
                elif self.pdi_command == PdiCommand.BASE_ROUTE:
                    self.scope = CommandScope.ROUTE
                self._rev_link = self._data[7] if data_len > 7 else None
                self._fwd_link = self._data[8] if data_len > 8 else None
                self._name = self.decode_text(self._data[9:42]) if data_len > 9 else None
                self._number = self.decode_text(self._data[42:]) if data_len > 42 else None
            elif self.pdi_command == PdiCommand.BASE:
                self._firmware_high = self._data[7] if data_len > 7 else None
                self._firmware_low = self._data[8] if data_len > 8 else None
                self._route_throw_rate = self.decode_throw_rate(self._data[9]) if data_len > 9 else None
                self._name = self.decode_text(self._data[10:]) if data_len > 10 else None
        else:
            self._record_no = int(data)
            self._flags = flags
            self._speed_step = speed
            if state:
                from ..db.component_state import EngineState

                self._name = state.road_name
                self._number = state.road_number
                self._status = 0
                self._valid1 = 0b1100
                if isinstance(state, EngineState):
                    self._valid1 = 0b1100000101100
                    self._valid2 = 0b10000000
                    self._speed_step = state.speed
                    self._momentum_tmcc = state.momentum
                    self._momentum = state.momentum * 16
                    self._run_level = state.rpm
                    self._scope = state.scope
                    self._control_type = state.control_type
                    self._loco_type = state.engine_type
                    self._loco_class = state.engine_class

    @property
    def record_no(self) -> int:
        return self._record_no

    @property
    def last_train_id(self) -> int:
        return self._last_train_id

    @property
    def flags(self) -> int:
        return self._flags

    @property
    def status(self) -> int:
        return self._status

    @property
    def reverse_link(self) -> int:
        return self._rev_link

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
    def max_speed(self) -> int:
        return self._max_speed

    @property
    def momentum(self) -> int:
        return self._momentum

    @property
    def run_level(self) -> int:
        return self._run_level

    @property
    def momentum_tmcc(self) -> int:
        return self._momentum_tmcc

    @property
    def is_legacy(self) -> bool:
        return self._control_type == 2

    @property
    def is_tmcc(self) -> bool:
        return self._control_type == 1

    @property
    def is_cab1(self) -> bool:
        return self._control_type == 0

    @property
    def control(self) -> str:
        return CONTROL_TYPE.get(self._control_type, "NA")

    @property
    def control_id(self) -> int:
        return self._control_type

    @property
    def sound(self) -> str:
        return SOUND_TYPE.get(self._sound_type, "NA")

    @property
    def loco_type(self) -> str:
        return LOCO_TYPE.get(self._loco_type, "NA")

    @property
    def loco_type_id(self) -> int:
        return self._loco_type

    @property
    def loco_class(self) -> str:
        return LOCO_CLASS.get(self._loco_class, "NA")

    @property
    def loco_class_id(self) -> int:
        return self._loco_class

    @property
    def is_active(self) -> bool:
        if self.pdi_command in [
            PdiCommand.BASE_ENGINE,
            PdiCommand.BASE_TRAIN,
            PdiCommand.BASE_ROUTE,
            PdiCommand.BASE_ACC,
            PdiCommand.BASE_SWITCH,
        ]:
            if self.forward_link == 255 and self.reverse_link == 255 and not self.name and not self.number:
                return False
        return True

    @property
    def payload(self) -> str:
        f = hex(self.flags) if self.flags is not None else "NA"
        s = self.status if self.status is not None else "NA"
        v = hex(self.valid1) if self.valid1 is not None else "NA"
        if self.pdi_command in [PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN]:
            tmcc = f"{self.record_no}"
            fwl = f" Fwd: {self._fwd_link}" if self._fwd_link is not None else ""
            rvl = f" Rev: {self._rev_link}" if self._rev_link is not None else ""
            na = f" {self._name}" if self._name is not None else ""
            no = f" {self._number}" if self._number is not None else ""
            ct = f" {self.control}"
            st = f" {self.sound}"
            lt = f" {self.loco_type} ({self._loco_type})"
            lc = f" {self.loco_class} ({self._loco_class})"
            v2 = f" {hex(self._valid2)}" if self._valid2 is not None else ""
            sp = f" SS: {self._speed_step}" if self._speed_step is not None else ""
            sl = f"/{self._speed_limit}" if self._speed_limit is not None else ""
            ms = f"/{self._max_speed}" if self._max_speed is not None else ""
            fl = f" Fuel: {(100. * self._fuel_level/255):.2f}%" if self._fuel_level is not None else ""
            wl = f" Water: {(100 * self._water_level/255):.2f}%" if self._water_level is not None else ""
            rl = f" RL: {self._run_level}" if self._run_level is not None else ""
            el = f" EB: {self._labor_bias}" if self._labor_bias is not None else ""
            sm = f" Smoke: {self._smoke_level}" if self._smoke_level is not None else ""
            m = f" Momentum: {self.momentum} ({self.momentum_tmcc})" if self.momentum is not None else ""
            b = f" Brake: {self._train_brake}" if self._train_brake is not None else ""
            return (
                f"# {tmcc}{na}{no}{ct}{st}{lt}{lc}{sp}{sl}{ms}{fl}{wl}{rl}{el}{sm}{m}{b} "
                f"flags: {f} status: {s} valid: {v}{v2}{fwl}{rvl} "
                f"({self.packet})"
            )
        if self.pdi_command == PdiCommand.BASE_ACC:
            fwl = f" Fwd: {self._fwd_link}" if self._fwd_link is not None else ""
            rvl = f" Rev: {self._rev_link}" if self._rev_link is not None else ""
            na = f" {self._name}" if self._name is not None else ""
            no = f" {self._number}" if self._number is not None else ""
            return f"# {self.record_no}{na}{no} flags: {f} status: {s} valid: {v}{fwl}{rvl}\n({self.packet})"
        elif self.pdi_command == PdiCommand.BASE:
            fw = f" V{self._firmware_high}.{self._firmware_low}" if self._firmware_high is not None else ""
            tr = f" Route Throw Rate: {self._route_throw_rate} sec" if self._route_throw_rate is not None else ""
            n = f"{self._name} " if self._name is not None else ""
            return f"{n}Rec # {self.record_no} flags: {f} status: {s} valid: {v}{fw}{tr}\n({self.packet})"
        elif self.pdi_command in [PdiCommand.UPDATE_ENGINE_SPEED, PdiCommand.UPDATE_TRAIN_SPEED]:
            scope = "Engine" if self.pdi_command == PdiCommand.UPDATE_ENGINE_SPEED else "Train"
            return f"{scope} #{self.tmcc_id} New Speed: {self.speed}"
        return f"Rec # {self.record_no} flags: {f} status: {s} valid: {v}\n({self.packet})"

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.record_no.to_bytes(1, byteorder="big")
        if self.pdi_command in [PdiCommand.UPDATE_ENGINE_SPEED, PdiCommand.UPDATE_TRAIN_SPEED]:
            byte_str += self.speed.to_bytes(1, byteorder="little")
        elif self._state:
            byte_str += self.flags.to_bytes(1, byteorder="little")
            byte_str += self.status.to_bytes(1, byteorder="little")
            byte_str += (0).to_bytes(1, byteorder="big")  # spare
            byte_str += self._valid1.to_bytes(2, byteorder="little")
            if self._valid2 is not None:
                byte_str += self._valid2.to_bytes(2, byteorder="little")
            byte_str += (101).to_bytes(1, byteorder="little")  # rev link
            byte_str += (101).to_bytes(1, byteorder="little")  # fwd link
            byte_str += self.encode_text(self.name, 33)
            byte_str += self.encode_text(self.number, 5)
            if self.pdi_command in [PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN]:
                byte_str += self._loco_type.to_bytes(1, byteorder="little")  # loco type
                byte_str += self._control_type.to_bytes(1, byteorder="little")
                byte_str += (0).to_bytes(1, byteorder="little")  # sount type
                byte_str += self._loco_class.to_bytes(1, byteorder="little")
                byte_str += (0).to_bytes(3, byteorder="little")  # 3 misc fields
                byte_str += self._speed_step.to_bytes(1, byteorder="little")
                byte_str += self._run_level.to_bytes(1, byteorder="little")
                byte_str += (0).to_bytes(10, byteorder="little")  # 5 misc fields
                byte_str += self._momentum.to_bytes(1, byteorder="little")
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
