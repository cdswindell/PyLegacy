from __future__ import annotations

from dataclasses import dataclass

from ..db.component_state import L, T
from ..protocol.constants import CommandScope, Mixins
from ..utils.validations import Validations
from .constants import PDI_EOP, PDI_SOP, Amc2Action, PdiCommand
from .lcs_req import LcsReq

NULL_BYTE = b"\x00"


class AccessType(Mixins):
    ENGINE = 0
    TRAIN = 1
    ACC = 2


class OutputType(Mixins):
    NORMAL = 0
    DELTA = 1
    AC = 2

    @property
    def is_dc(self) -> bool:
        return self in {OutputType.DELTA, OutputType.NORMAL}

    @property
    def is_ac(self) -> bool:
        return self in {OutputType.AC}

    @property
    def label(self) -> str:
        if self == OutputType.AC:
            return OutputType.AC.name
        return self.name.capitalize()


class Direction(Mixins):
    FORWARD = 1
    REVERSE = 2
    AC = 3

    @property
    def label(self) -> str:
        if self == Direction.AC:
            return Direction.AC.name
        return self.name.capitalize()


@dataclass(slots=True)
class Amc2Motor:
    id: int
    output_type: OutputType
    direction: Direction
    restore: bool
    restore_state: bool
    speed: int

    def __repr__(self) -> str:
        t = f"Output: {self.output_type.label}"
        d = f"Dir: {self.direction.label}"
        r = f"Restore: {self.restore}"
        if self.restore:
            r += f" to {'On' if self.restore_state else 'Off'}"
        return f"Mo #{self.id} {t} {d} Speed: {self.speed} {r}"


@dataclass(slots=True)
class Amc2Lamp:
    id: int
    level: int

    def __repr__(self) -> str:
        return f"Lm #{self.id} level: {self.level}"


class Amc2Req(LcsReq):
    # noinspection PyUnusedLocal,PyTypeChecker
    @classmethod
    def request_config(cls, state: T, cmd: L) -> Amc2Req:
        return cls(state.address, pdi_command=PdiCommand.AMC2_GET, action=Amc2Action.CONFIG)

    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.AMC2_GET,
        action: Amc2Action = Amc2Action.CONFIG,
        ident: int | None = None,
        error: bool = False,
        debug: int = None,
        motor: int | None = None,
        speed: int = None,
        direction: Direction | None = None,
        output_type: OutputType | None = None,
        restore_state: bool | None = None,
        lamp: int | None = None,
        level: int = None,
    ) -> None:
        super().__init__(data, pdi_command, action, ident, error)
        self.scope = CommandScope.ACC
        if isinstance(data, bytes):
            # initialize all
            self._debug = False
            self._motor1 = self._motor2 = None
            self._lamp1 = self._lamp2 = self._lamp3 = self._lamp4 = None
            self._option = None
            self._access_type = None
            self._motor = self._speed = self._direction = self._lamp = self._level = None
            self._output_type = self._restore_state = None

            # what is the request type?
            self._action = Amc2Action(self._action_byte)
            data_len = len(self._data)
            if self._action == Amc2Action.CONFIG:
                self._debug = self._data[4] if data_len > 4 else None
                self._option = self._data[5:7] if data_len > 6 else None
                self._access_type = AccessType(self._data[7]) if data_len > 7 else None
                self._motor1, self._motor2 = self._harvest_motors(self._data[8:18]) if data_len > 17 else (None, None)
                self._lamp1 = Amc2Lamp(1, self._data[18]) if data_len > 18 else None
                self._lamp2 = Amc2Lamp(2, self._data[19]) if data_len > 19 else None
                self._lamp3 = Amc2Lamp(3, self._data[20]) if data_len > 20 else None
                self._lamp4 = Amc2Lamp(4, self._data[21]) if data_len > 21 else None
            elif self._action == Amc2Action.MOTOR:
                self._motor = self._data[4] if data_len > 4 else None
                self._speed = self._data[5] if data_len > 5 else None
                self._direction = self._data[6] if data_len > 6 else None
            elif self._action == Amc2Action.LAMP:
                self._lamp = self._data[4] if data_len > 4 else None
                self._level = self._data[5] if data_len > 5 else None
            elif self._action == Amc2Action.MOTOR_CONFIG:
                self._motor = self._data[4] if data_len > 4 else None
                self._output_type = self._data[5] if data_len > 5 else None
                self._restore_state = bool(self._data[6]) if data_len > 6 else None
        else:
            self._action = action
            self._debug = debug
            self._motor = Validations.validate_int(motor, 0, 1, "Motor", True)
            self._speed = Validations.validate_int(speed, 0, 100, "Speed", True)
            self._direction = direction.value if direction else Direction.AC.value
            self._output_type = output_type.value if output_type else OutputType.AC
            self._restore_state = restore_state if restore_state is not None else True
            self._lamp = Validations.validate_int(lamp, 0, 3, "Lamp", True)
            self._level = Validations.validate_int(level, 0, 100, "Level", True)

    @property
    def debug(self) -> int | None:
        return self._debug

    @property
    def access_type(self) -> AccessType:
        return self._access_type

    @property
    def motor(self) -> int:
        return self._motor

    @property
    def speed(self) -> int:
        return self._speed

    @property
    def direction(self) -> Direction:
        return Direction(self._direction) if self._direction is not None else Direction.AC

    @property
    def output_type(self) -> OutputType:
        return OutputType(self._output_type) if self._output_type is not None else OutputType.AC

    @property
    def restore_state(self) -> bool:
        return self._restore_state if self._restore_state is not None else True

    @property
    def motor1(self) -> Amc2Motor:
        return self._motor1

    @property
    def motor2(self) -> Amc2Motor:
        return self._motor2

    @property
    def lamp(self) -> int:
        return self._lamp

    @property
    def level(self) -> int:
        return self._level

    @property
    def lamp1(self) -> Amc2Lamp:
        return self._lamp1

    @property
    def lamp2(self) -> Amc2Lamp:
        return self._lamp2

    @property
    def lamp3(self) -> Amc2Lamp:
        return self._lamp3

    @property
    def lamp4(self) -> Amc2Lamp:
        return self._lamp4

    @property
    def payload(self) -> str | None:
        if self.is_error:
            return super().payload
        if self.pdi_command != PdiCommand.AMC2_GET:
            if self.action == Amc2Action.CONFIG:
                at = f"Type: {self._access_type.label}"
                m1 = f"{self._motor1}"
                m2 = f"{self._motor2}"
                l1 = f"{self._lamp1}"
                return f"{at} {m1} {m2} {l1} Debug: {self.debug} ({self.packet})"
            elif self._action == Amc2Action.MOTOR:
                return f"Motor: {self.motor} Speed: {self.speed} Dir: {self.direction.label} ({self.packet})"
            elif self._action == Amc2Action.LAMP:
                return f"Lamp: {self.lamp} Level: {self.level} ({self.packet})"
            elif self._action == Amc2Action.MOTOR_CONFIG:
                ot = f"Output Type: {self.output_type.label}"
                rs = f"Restore State: {'On' if self._restore_state else 'Off'}"
                return f"Motor: {self.motor} {ot} {rs} ({self.packet})"
        return super().payload

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += self.action.as_bytes
        if self._action == Amc2Action.CONFIG:
            if self.pdi_command != PdiCommand.AMC2_GET:
                byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
                debug = self.debug if self.debug is not None else 0
                byte_str += debug.to_bytes(1, byteorder="big")
                byte_str += self._option if self._option else (0x0000).to_bytes(2, byteorder="big")
                byte_str += self._access_type.value.to_bytes(1, byteorder="big") if self._access_type else NULL_BYTE
                byte_str += self._motors_as_bytes()
                for lamp in [self._lamp1, self._lamp2, self._lamp3, self._lamp4]:
                    byte_str += lamp.level.to_bytes(1, byteorder="big") if lamp else NULL_BYTE
        elif self._action == Amc2Action.MOTOR:
            byte_str += self.motor.to_bytes(1, byteorder="big")
            if self.pdi_command != PdiCommand.AMC2_GET:
                byte_str += self.speed.to_bytes(1, byteorder="big")
                byte_str += self._direction.to_bytes(1, byteorder="big")
        elif self._action == Amc2Action.LAMP:
            byte_str += self.motor.to_bytes(1, byteorder="big")
            if self.pdi_command != PdiCommand.AMC2_GET:
                byte_str += self.level.to_bytes(1, byteorder="big")
        elif self._action == Amc2Action.MOTOR_CONFIG:
            byte_str += self.motor.to_bytes(1, byteorder="big")
            if self.pdi_command != PdiCommand.AMC2_GET:
                byte_str += self.output_type.value.to_bytes(1, byteorder="big")
                byte_str += self.restore_state.to_bytes(1, byteorder="big")
        elif self._action == Amc2Action.IDENTIFY:
            if self.pdi_command == PdiCommand.AMC2_SET:
                byte_str += (self.ident if self.ident is not None else 0).to_bytes(1, byteorder="big")
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str

    @staticmethod
    def _harvest_motors(data: bytes) -> tuple[Amc2Motor, Amc2Motor]:
        motor1 = Amc2Motor(
            1,
            OutputType(data[0]),
            Direction(data[2]),
            bool(data[4]),
            bool(data[6]),
            data[8],
        )
        motor2 = Amc2Motor(
            2,
            OutputType(data[1]),
            Direction(data[3]),
            bool(data[5]),
            bool(data[7]),
            data[9],
        )
        return motor1, motor2

    def _motors_as_bytes(self) -> bytes:
        byte_str = bytes()
        byte_str += self._motor1.output_type.value.to_bytes(1, byteorder="big") if self._motor1 else NULL_BYTE
        byte_str += self._motor2.output_type.value.to_bytes(1, byteorder="big") if self._motor2 else NULL_BYTE

        byte_str += self._motor1.direction.value.to_bytes(1, byteorder="big") if self._motor1 else NULL_BYTE
        byte_str += self._motor2.direction.value.to_bytes(1, byteorder="big") if self._motor2 else NULL_BYTE

        byte_str += self._motor1.restore.to_bytes(1, byteorder="big") if self._motor1 else NULL_BYTE
        byte_str += self._motor2.restore.to_bytes(1, byteorder="big") if self._motor2 else NULL_BYTE

        byte_str += self._motor1.restore_state.to_bytes(1, byteorder="big") if self._motor1 else NULL_BYTE
        byte_str += self._motor2.restore_state.to_bytes(1, byteorder="big") if self._motor2 else NULL_BYTE

        byte_str += self._motor1.speed.to_bytes(1, byteorder="big") if self._motor1 else NULL_BYTE
        byte_str += self._motor2.speed.to_bytes(1, byteorder="big") if self._motor2 else NULL_BYTE
        return byte_str
