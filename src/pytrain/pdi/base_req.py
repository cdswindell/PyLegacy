#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import logging
from enum import IntEnum, unique
from math import floor
from typing import Dict, List, Tuple

from ..db.comp_data import (
    SCOPE_TO_COMP_MAP,
    CompData,
    CompDataHandler,
    CompDataMixin,
)
from ..db.component_state import ComponentState
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CONTROL_TYPE, LOCO_CLASS, LOCO_TYPE, SOUND_TYPE, CommandScope, Mixins
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from .base3_component import ConsistComponent
from .constants import PDI_EOP, PDI_SOP, D4Action, PdiCommand
from .pdi_req import LIONEL_ENGINE_RECORD_LENGTH, SCOPE_TO_RECORD_LENGTH, PdiReq

log = logging.getLogger(__name__)

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


@unique
class EngineBits(Mixins, IntEnum):
    REVERSE_LINK = 0
    FORWARD_LINK = 1
    ROAD_NAME = 2
    ROAD_NUMBER = 3
    LOCO_TYPE = 4
    CONTROL_TYPE = 5
    SOUND_TYPE = 6
    CLASS_TYPE = 7
    TSDB_LEFT = 8
    TSDB_RIGHT = 9
    SPARE = 10
    SPEED = 11
    RUN_LEVEL = 12
    LABOR_BIAS = 13
    SPEED_LIMIT = 14
    MAX_SPEED = 15
    FUEL_LEVEL = 16
    WATER_LEVEL = 17
    TRAIN_ADDRESS = 18
    TRAIN_POSITION = 19
    SMOKE_LEVEL = 20
    DITCH_LIGHT = 21
    TRAIN_BRAKE = 22
    MOMENTUM = 23


ENGINE_WRITE_MAP = {
    "ABSOLUTE_SPEED": (11, 56, None),
    "STOP_IMMEDIATE": (11, 56, lambda t: 0),
    "RESET": (11, 56, lambda t: 0),
    "DIESEL_RPM": (12, 57, None),
    "ENGINE_LABOR": (13, 58, lambda t: t - 12 if t >= 12 else 20 + t),
    "SMOKE_HIGH": (20, 65, lambda t: 3),
    "SMOKE_MEDIUM": (20, 65, lambda t: 2),
    "SMOKE_LOW": (20, 65, lambda t: 1),
    "SMOKE_OFF": (20, 65, lambda t: 0),
    "DITCH_OFF": (21, 66, lambda t: 0),
    "DITCH_OFF_PULSE_ON_WITH_HORN": (21, 66, lambda t: 1),
    "DITCH_ON_PULSE_OFF_WITH_HORN": (21, 66, lambda t: 2),
    "DITCH_ON": (21, 68, lambda t: 3),
    "TRAIN_BRAKE": (22, 67, lambda t: round(t * 2.143)),
    "MOMENTUM_HIGH": (23, 68, lambda t: 127),
    "MOMENTUM_MEDIUM": (23, 68, lambda t: 63),
    "MOMENTUM_LOW": (23, 68, lambda t: 0),
    "MOMENTUM": (23, 68, lambda t: floor(t * 18.285)),
}


def encode_labor_rpm(rpm: int, labor: int) -> int:
    return rpm | ((labor - 12 if labor >= 12 else 20 + labor) << 3)


def decode_labor_rpm(s: int) -> Tuple[int, int]:
    rpm = s & 0b111
    labor = s >> 3
    labor = labor + 12 if labor <= 19 else labor - 20
    return rpm, labor


RECORD_TYPE_MAP = {
    1: CommandScope.ENGINE,
    2: CommandScope.TRAIN,
    3: CommandScope.ACC,
    5: CommandScope.ROUTE,
    6: CommandScope.SWITCH,
}

SCOPE_TO_RECORD_TYPE_MAP = {s: p for p, s in RECORD_TYPE_MAP.items()}


class BaseReq(PdiReq, CompDataMixin):
    # noinspection PyTypeChecker,PyUnusedLocal
    @classmethod
    def request_config(cls, state: ComponentState, cmd: CommandReq) -> BaseReq:
        if state.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
            state_changes = BaseReq.update_eng(cmd)
            for state_change in state_changes:
                state_change.send()
        return cls(state.address, pdi_command=PdiCommand.BASE_MEMORY, scope=state.scope)

    @classmethod
    def update_speed(cls, address: int, speed: int, scope: CommandScope = CommandScope.ENGINE) -> BaseReq:
        if scope == CommandScope.TRAIN:
            return cls(address, PdiCommand.UPDATE_TRAIN_SPEED, flags=0xC2, speed=speed)
        else:
            return cls(address, PdiCommand.UPDATE_ENGINE_SPEED, flags=0xC2, speed=speed)

    @classmethod
    def update_eng(
        cls,
        cmd: CommandDefEnum | CommandReq,
        address: int = None,
        data: int | None = None,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> List[BaseReq] | None:
        #
        # Given a TMCC command, determine how it indirectly impacts engine state and
        # return a list of commands to send to the Base 3 to set that state
        #
        from ..db.component_state_store import ComponentStateStore

        pkgs = []
        if isinstance(cmd, CommandReq):
            state = cmd.command
            address = cmd.address
            data = cmd.data
            scope = cmd.scope
            cur_state = ComponentStateStore.get_state(scope, address, False)

            # special case numeric commands
            if state.name == "NUMERIC":
                if data in {3, 6}:  # RPM up/down
                    if cur_state and cur_state.rpm is not None:
                        cur_rpm = cur_state.rpm
                        cur_labor = cur_state.labor if cur_state.labor else 12
                        if data == 6:  # RPM Down
                            cur_rpm = max(cur_rpm - 1, 0)
                        elif data == 3:  # RPM Up
                            cur_rpm = min(cur_rpm + 1, 7)
                        pkgs.append(CompData.rpm_labor_to_pkg(cur_rpm, cur_labor))
                elif data == 5 and cur_state.speed == 0:  # Shutdown Delayed
                    pkgs.extend(
                        CompData.request_to_updates(
                            CommandReq(
                                TMCC2EngineCommandEnum.SHUTDOWN_DELAYED,
                                address,
                                scope=scope,
                            )
                        )
                    )
                elif data == 0:  # Reset
                    pkgs.extend(
                        CompData.request_to_updates(
                            CommandReq(
                                TMCC2EngineCommandEnum.RESET,
                                address,
                                scope=scope,
                            )
                        )
                    )
        elif isinstance(cmd, CommandDefEnum):
            state = cmd
            cur_state = ComponentStateStore.build().get_state(scope, address, False)
            log.warning("********************** update_eng called with enum not req ***********************")
        else:
            raise ValueError(f"Invalid option: {cmd}")

        # harvest state update pkgs based on command, unless command was numeric 3 or 6
        cmds = []
        pkgs = pkgs if pkgs else CompData.request_to_updates(cmd)
        if pkgs:
            from .d4_req import D4Req

            for pkg in pkgs:
                if 1 <= cmd.address <= 99:
                    cmds.append(
                        BaseReq(
                            cmd.address,
                            pdi_command=PdiCommand.BASE_MEMORY,
                            flags=0xC2,
                            scope=state.scope,
                            start=pkg.offset,
                            data_length=pkg.length,
                            data_bytes=pkg.data_bytes,
                        )
                    )
                else:
                    assert cur_state.record_no != 0xFFFF
                    pdi_cmd = PdiCommand.D4_ENGINE if cmd.scope == CommandScope.ENGINE else PdiCommand.D4_TRAIN
                    cmds.append(
                        D4Req(
                            cur_state.record_no,
                            pdi_cmd,
                            D4Action.UPDATE,
                            start=pkg.offset,
                            data_length=pkg.length,
                            data_bytes=pkg.data_bytes,
                        )
                    )
        elif state.name in ENGINE_WRITE_MAP and cmd.address <= 99:
            bit_pos, offset, scaler = ENGINE_WRITE_MAP[state.name]
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f"State: {state} {data} {bit_pos} {offset} {scaler(data) if scaler else data}")
            value1 = value2 = 0
            if bit_pos <= 15:
                value1 = 1 << bit_pos
            else:
                value2 = 1 << (bit_pos - 16)
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
            cmds.append(cls(byte_str))
            log.info(f"Using old-style {pdi_cmd.name} for updates from {cmd}")
        return cmds

    def __init__(
        self,
        data: bytes | int = 0,
        pdi_command: PdiCommand = PdiCommand.BASE,
        flags: int = 2,
        scope: CommandScope = None,
        speed: int = None,
        base_name: str | None = None,
        state: ComponentState = None,
        start: int = 0,
        data_length: int = 0,
        data_bytes: bytes | None = None,
    ) -> None:
        super().__init__(data, pdi_command)
        if not self.pdi_command.is_base:
            raise ValueError(f"Invalid PDI Base Request: {data}")
        self._status = self._firmware_high = self._firmware_low = None
        self._route_throw_rate = self._name = self._number = None
        self._route_components = None
        self._rev_link = self._fwd_link = None
        self._loco_type = self._control_type = self._sound_type = self._loco_class = None
        self._speed_step = self._speed_limit = self._max_speed = self._labor_bias = None
        self._fuel_level = self._water_level = self._last_train_id = self._train_pos = None
        self._train_brake = None
        self._smoke_level = self._ditch_lights = self._momentum = None
        self._consist_flags = None
        self._consist_comps = []
        self._state = state
        self._valid1 = self._valid2 = None
        self._spare_1 = None
        self._data_length = self._data_bytes = self._start = self._record_type = None
        if isinstance(data, bytes):
            data_len = len(self._data)
            self._record_no = self.tmcc_id = self._data[1] if data_len > 1 else None
            self._flags = self._data[2] if data_len > 2 else None
            self._status = self._data[3] if data_len > 3 else None
            self._spare_1 = self._data[4] if data_len > 4 else None
            self._valid1 = int.from_bytes(self._data[5:7], byteorder="little") if data_len > 5 else None
            self._valid2 = None

            if self.pdi_command in {PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN}:
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
                if self.pdi_command == PdiCommand.BASE_TRAIN:
                    self._consist_flags = self._data[69] if data_len > 69 else None
                    for i in range(70, 102, 2):
                        if data_len > i:
                            if self._data[i] != 0xFF and self._data[i + 1] != 0xFF:
                                self._consist_comps.insert(0, ConsistComponent(self._data[i], self._data[i + 1]))
                        else:
                            break
            elif self.pdi_command in {PdiCommand.BASE_ACC, PdiCommand.BASE_SWITCH, PdiCommand.BASE_ROUTE}:
                if self.pdi_command == PdiCommand.BASE_ACC:
                    self.scope = CommandScope.ACC
                elif self.pdi_command == PdiCommand.BASE_SWITCH:
                    self.scope = CommandScope.SWITCH
                elif self.pdi_command == PdiCommand.BASE_ROUTE:
                    self.scope = CommandScope.ROUTE
                self._rev_link = self._data[7] if data_len > 7 else None
                self._fwd_link = self._data[8] if data_len > 8 else None
                self._name = self.decode_text(self._data[9:42]) if data_len > 9 else None
                self._number = self.decode_text(self._data[42:47]) if data_len > 42 else None
                if self.scope == CommandScope.ROUTE and self.is_active:
                    # grab the switches/routes in this route
                    if data_len > 47:
                        self._route_components: List[int] = list()
                        for i in range(47, 79, 2):
                            if data_len < i + 2:
                                break
                            tmcc_id = int.from_bytes(self._data[i : i + 2], byteorder="big")
                            if tmcc_id != 0xFFFF and tmcc_id != 0:
                                self._route_components.append(tmcc_id)
            elif self.pdi_command == PdiCommand.BASE:
                self._firmware_high = self._data[7] if data_len > 7 else None
                self._firmware_low = self._data[8] if data_len > 8 else None
                self._route_throw_rate = self.decode_throw_rate(self._data[9]) if data_len > 9 else None
                self._name = self.decode_text(self._data[10:]) if data_len > 10 else None
                self.scope = CommandScope.BASE
            elif self.pdi_command == PdiCommand.BASE_MEMORY:
                record_type = self._data[4] if data_len > 4 else None
                self._scope = RECORD_TYPE_MAP.get(record_type, CommandScope.SYSTEM)
                self._start = int.from_bytes(self._data[5:9], byteorder="little") if data_len > 8 else None
                _ = self._data[9] if data_len > 9 else None  # we assume port is always 2; Database EEProm
                self._data_length = self._data[10] if data_len > 10 else None
                self._data_bytes = self._data[11:] if data_len > 11 else None
                base_record_length = PdiReq.scope_record_length(self.scope)
                if self.data_length == base_record_length and self.scope in {
                    CommandScope.ENGINE,
                    CommandScope.TRAIN,
                    CommandScope.ACC,
                    CommandScope.SWITCH,
                    CommandScope.ROUTE,
                }:
                    self._comp_data = CompData.from_bytes(self._data_bytes, scope=self.scope, tmcc_id=self.tmcc_id)
                    self._name = self._comp_data.road_name
                    self._number = self._comp_data.road_number
                    self._comp_data_record = True  # mark this req as containing a complete CompData record
            elif self.pdi_command in {PdiCommand.UPDATE_ENGINE_SPEED, PdiCommand.UPDATE_TRAIN_SPEED}:
                self._speed = self._data[2] if data_len > 2 else None
                self._valid1 = (1 << EngineBits.SPEED) if data_len > 2 else 0
        else:
            self._record_no = int(data)
            self._flags = flags
            self._speed_step = speed
            self._base_name = base_name
            self._valid1 = 0b1111
            if self.pdi_command == PdiCommand.BASE_MEMORY:
                self._tmcc_id = self.record_no
                self.scope = scope if scope else CommandScope.ENGINE
                self._record_type = SCOPE_TO_RECORD_TYPE_MAP.get(self.scope, 1)
                # if the state contains a valid comp_data, use it as the source
                if start == 0 and data_length == 0 and isinstance(state, CompDataMixin) and state.is_comp_data_record:
                    self._start = 0
                    self._data_length = PdiReq.scope_record_length(self.scope)
                    if state.comp_data is not None:
                        self._data_bytes = state.comp_data.as_bytes()
                else:
                    self._start = start
                    data_length = (
                        data_length
                        if data_length and 0 <= data_length <= PdiReq.scope_record_length(self.scope)
                        else PdiReq.scope_record_length(self.scope)
                    )
                    self._data_length = data_length
                    self._data_bytes = data_bytes
            elif state:
                from .. import EngineState, TrainState
                from ..db.base_state import BaseState

                self._status = 0
                self._spare_1 = state.spare_1
                if isinstance(state, BaseState):
                    self._name = state.base_name
                    self._firmware_high = state.firmware_high
                    self._firmware_low = state.firmware_low
                    self._route_throw_rate = state.route_throw_rate
                    self._valid1 = 0b1111
                    self.scope = CommandScope.BASE
                else:
                    self._name = state.road_name
                    self._number = state.road_number
                    self._valid1 = 0b1100
                    self.scope = state.scope
                    if isinstance(state, EngineState):
                        if state.momentum is None:
                            state._momentum = 1
                        if state.train_brake is None:
                            state._train_brake = 0
                        if state.labor is None:
                            state._labor = 12
                        self._valid1 = 0b1111100011111100
                        self._valid2 = 0b11000000
                        self._speed_step = state.speed
                        self._speed_limit = state.speed_limit
                        self._max_speed = state.max_speed
                        self._momentum = min(round(state.momentum * 18.14), 127)
                        self._train_brake = min(round(state.train_brake * 2.143), 15)
                        self._run_level = state.rpm
                        self._labor_bias = state.labor - 12 if state.labor >= 12 else 20 + state.labor
                        self._scope = state.scope
                        self._control_type = state.control_type
                        self._sound_type = state.sound_type
                        self._loco_type = state.engine_type
                        self._loco_class = state.engine_class
                        if isinstance(state, TrainState):
                            self._consist_flags = state.consist_flags
                            self._consist_comps = state.consist_components

    def is_valid(self, field: EngineBits) -> bool:
        if self._valid1 and field.value <= 15:
            return (self._valid1 & (1 << field.value)) != 0
        elif self._valid2 and field.value <= 31:
            return (self._valid2 & (1 << (field.value - 16))) != 0
        return False

    @property
    def as_key(self):
        return self.record_no, self.pdi_command, self.action, self.scope

    @property
    def record_no(self) -> int:
        return self._record_no

    @property
    def last_train_id(self) -> int:
        return self._last_train_id

    @property
    def train_pos(self) -> int:
        return self._train_pos

    @property
    def flags(self) -> int:
        return self._flags

    @property
    def status(self) -> int:
        return self._status

    @property
    def spare_1(self) -> int:
        return self._spare_1

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
    def valid2(self) -> int:
        return self._valid2

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
    def speed_limit(self) -> int:
        return self._speed_limit

    @property
    def smoke(self) -> CommandDefEnum | None:
        from .. import SMOKE_LEVEL_MAP

        return SMOKE_LEVEL_MAP.get(self._smoke_level, None)

    @property
    def smoke_level(self) -> int:
        return self._smoke_level

    @property
    def train_brake(self) -> int:
        return self._train_brake

    @property
    def train_brake_tmcc(self) -> int:
        if self.train_brake:
            return min(round(self._train_brake * 0.4667), 7)
        else:
            return self._train_brake

    @property
    def momentum(self) -> int:
        return self._momentum

    @property
    def momentum_tmcc(self) -> int:
        if self.momentum:
            return min(round(self._momentum * 0.05512), 7)
        else:
            return self._momentum

    @property
    def run_level(self) -> int:
        return self._run_level

    @property
    def labor_bias(self) -> int:
        return self._labor_bias

    @property
    def labor_bias_tmcc(self) -> int:
        return self._labor_bias + 12 if self._labor_bias <= 19 else self._labor_bias - 20

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
    def sound_id(self) -> int:
        return self._sound_type

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
    def consist_components(self) -> List[ConsistComponent]:
        return self._consist_comps

    @property
    def consist_flags(self) -> int:
        return self._consist_flags

    @property
    def components(self) -> List[int]:
        return self._route_components

    @property
    def route_throw_rate(self) -> float:
        return self._route_throw_rate

    @property
    def firmware(self) -> str | None:
        if self._firmware_high and self._firmware_low:
            return f"{self._firmware_high}.{self._firmware_low}"
        return None

    @property
    def is_ack(self) -> bool:
        return self._valid1 is None and self._valid2 is None

    @property
    def is_active(self) -> bool:
        if (
            self.pdi_command == PdiCommand.BASE_MEMORY
            and self.scope in SCOPE_TO_RECORD_LENGTH
            and self.comp_data
            and self.is_comp_data_record is True
        ):
            if (
                self.comp_data.prev_link == 255
                and self.comp_data.next_link == 255
                and not self.name
                and not self.number
            ):
                return False
        if self.pdi_command in {
            PdiCommand.BASE_ENGINE,
            PdiCommand.BASE_TRAIN,
            PdiCommand.BASE_ROUTE,
            PdiCommand.BASE_ACC,
            PdiCommand.BASE_SWITCH,
        }:
            if self.forward_link == 255 and self.reverse_link == 255 and not self.name and not self.number:
                return False
        return True

    @property
    def start(self) -> int:
        return self._start

    @property
    def data_length(self) -> int:
        return self._data_length

    @property
    def data_bytes(self) -> bytes:
        return self._data_bytes

    @property
    def payload(self) -> str:
        f = hex(self.flags) if self.flags is not None else "NA"
        s = self.status if self.status is not None else "NA"
        if self.pdi_command in {PdiCommand.UPDATE_ENGINE_SPEED, PdiCommand.UPDATE_TRAIN_SPEED}:
            scope = "Engine" if self.pdi_command == PdiCommand.UPDATE_ENGINE_SPEED else "Train"
            return f"{scope} #{self.tmcc_id} New Speed: {self.speed}"
        elif self.pdi_command == PdiCommand.BASE_MEMORY and self._start is not None:
            dt = ""
            sc = f"Scope: {self.scope}"
            st = f"Start: {hex(self._start)} Len: {self.data_length}"
            comp_map = SCOPE_TO_COMP_MAP.get(self.scope, None)
            if comp_map:
                tpl = comp_map.get(self.start, None)
                rec_len = SCOPE_TO_RECORD_LENGTH.get(self.scope, None)
            else:
                tpl = None
                rec_len = LIONEL_ENGINE_RECORD_LENGTH
            if self._data_bytes:
                if isinstance(tpl, CompDataHandler) and (tpl.length == self.data_length):
                    dt = f"Data: {tpl.from_bytes(self._data_bytes)}"
                elif self.data_length < rec_len:
                    dt = f"Data: 0x{self._data_bytes.hex(' ')}" if self._data_bytes else "Data: None"
                else:
                    # we have a complete record, don't print it twice
                    pass
            else:
                dt = "Data: None"
            return f"TMCC ID # {self.record_no} {sc} flags: {f} {st} {dt} status: {s} ({self.packet})"
        elif self._valid1 is None and self._valid2 is None:  # ACK received
            return f"Rec # {self.record_no} flags: {f} status: {s} ACK ({self.packet})"
        else:
            v = hex(self.valid1) if self.valid1 is not None else "NA"
            if self.pdi_command in {PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN}:
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
                fl = f" Fuel: {(100.0 * self._fuel_level / 255):.2f}%" if self._fuel_level is not None else ""
                wl = f" Water: {(100.0 * self._water_level / 255):.2f}%" if self._water_level is not None else ""
                rl = f" RL: {self._run_level}" if self._run_level is not None else ""
                el = f" EB: {self._labor_bias}" if self._labor_bias is not None else ""
                sm = f" Smoke: {self._smoke_level}" if self._smoke_level is not None else ""
                m = f" Momentum: {self.momentum} ({self.momentum_tmcc})" if self.momentum is not None else ""
                b = f" Brake: {self._train_brake}" if self._train_brake is not None else ""
                ti = f"Train ID: {self._last_train_id} {self._train_pos} " if self._last_train_id is not None else ""
                if self.pdi_command == PdiCommand.BASE_TRAIN and self._consist_comps:
                    tc = " "
                    for c in self._consist_comps:
                        tc += f"{c} "
                else:
                    tc = ""
                return (
                    f"# {tmcc}{na}{no}{ct}{st}{lt}{lc}{sp}{sl}{ms}{fl}{wl}{rl}{el}{sm}{m}{b}\n"
                    f"{ti}{tc}flags: {f} status: {s} valid: {v}{v2}{fwl}{rvl}\n"
                    f"({self.packet})"
                )
            if self.pdi_command in [PdiCommand.BASE_ACC, PdiCommand.BASE_ROUTE, PdiCommand.BASE_SWITCH]:
                fwl = f" Fwd: {self._fwd_link}" if self._fwd_link is not None else ""
                rvl = f" Rev: {self._rev_link}" if self._rev_link is not None else ""
                na = f" {self._name}" if self._name is not None else ""
                no = f" {self._number}" if self._number is not None else ""
                sw = ""
                if self.pdi_command == PdiCommand.BASE_ROUTE and self._route_components and self.is_active:
                    sw = " Switches:"
                    for comp in self._route_components:
                        state = "out" if (comp & 0x0300) != 0 else "thru"
                        comp &= 0x007F
                        sw += f" {comp} [{state}],"
                return f"# {self.record_no}{na}{no}{sw} flags: {f} status: {s} valid: {v}{fwl}{rvl}\n({self.packet})"
            elif self.pdi_command == PdiCommand.BASE:
                fw = f" V{self._firmware_high}.{self._firmware_low}" if self._firmware_high is not None else ""
                tr = f" Route Throw Rate: {self._route_throw_rate} sec" if self._route_throw_rate is not None else ""
                n = f"{self._name} " if self._name is not None else ""
                return f"{n}Rec # {self.record_no} flags: {f} status: {s} valid: {v}{fw}{tr}\n({self.packet})"
            return f"Rec # {self.record_no} flags: {f} status: {s} valid: {v}\n({self.packet})"

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.record_no.to_bytes(1, byteorder="big")
        if self.pdi_command in {PdiCommand.UPDATE_ENGINE_SPEED, PdiCommand.UPDATE_TRAIN_SPEED}:
            byte_str += self.speed.to_bytes(1, byteorder="little")
        elif self.pdi_command == PdiCommand.BASE_MEMORY:
            byte_str += self.flags.to_bytes(1, byteorder="little")
            byte_str += (0).to_bytes(1, byteorder="little")  # Status
            byte_str += SCOPE_TO_RECORD_TYPE_MAP.get(self.scope, 1).to_bytes(1, byteorder="little")
            byte_str += self._start.to_bytes(4, byteorder="little")
            byte_str += (2).to_bytes(1, byteorder="little")  # database EEProm
            byte_str += self._data_length.to_bytes(1, byteorder="little")
            if self._data_bytes:
                byte_str += self._data_bytes
        elif self._state:
            byte_str += self.flags.to_bytes(1, byteorder="little")
            byte_str += self.status.to_bytes(1, byteorder="little")
            byte_str += (self.spare_1 if self.spare_1 else 0).to_bytes(1, byteorder="big")  # spare
            byte_str += self._valid1.to_bytes(2, byteorder="little")
            if self._valid2 is not None:
                byte_str += self._valid2.to_bytes(2, byteorder="little")
            if self.pdi_command == PdiCommand.BASE:
                byte_str += self._firmware_high.to_bytes(1, byteorder="little")
                byte_str += self._firmware_low.to_bytes(1, byteorder="little")
                byte_str += self.encode_throw_rate(self.route_throw_rate).to_bytes(1, byteorder="little")
                byte_str += self.encode_text(self.name, 33)
            else:
                byte_str += (101).to_bytes(1, byteorder="little")  # rev link
                byte_str += (101).to_bytes(1, byteorder="little")  # fwd link
                byte_str += self.encode_text(self.name, 33)
                byte_str += self.encode_text(self.number, 5)
                if self.pdi_command in {PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN}:
                    byte_str += self._loco_type.to_bytes(1, byteorder="little")  # loco type
                    byte_str += self._control_type.to_bytes(1, byteorder="little")
                    byte_str += self._sound_type.to_bytes(1, byteorder="little")
                    byte_str += self._loco_class.to_bytes(1, byteorder="little")
                    byte_str += (0).to_bytes(3, byteorder="little")  # 3 misc fields
                    byte_str += self._speed_step.to_bytes(1, byteorder="little")
                    byte_str += self._run_level.to_bytes(1, byteorder="little")
                    byte_str += self._labor_bias.to_bytes(1, byteorder="little")  # labor bias
                    byte_str += self._speed_limit.to_bytes(1, byteorder="little")
                    byte_str += self._max_speed.to_bytes(1, byteorder="little")
                    byte_str += (0).to_bytes(6, byteorder="little")
                    byte_str += self._train_brake.to_bytes(1, byteorder="little")
                    byte_str += self._momentum.to_bytes(1, byteorder="little")
                    if self.pdi_command == PdiCommand.BASE_TRAIN and self._consist_comps:
                        ff = (0xFF).to_bytes(1, byteorder="little")
                        cf = self._consist_flags if self._consist_flags else 0
                        byte_str += cf.to_bytes(1, byteorder="little")
                        byte_str += 2 * ff
                        i = 15
                        for c in reversed(self.consist_components):
                            byte_str += c.flags.to_bytes(1, byteorder="little")
                            byte_str += c.tmcc_id.to_bytes(1, byteorder="little")
                            i -= 1
                        byte_str += (max(i, 0) * 2) * ff
                elif self.pdi_command == PdiCommand.BASE_ROUTE:
                    for sw in self._route_components:
                        byte_str += sw.to_bytes(2, byteorder="big")
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
        if data is not None:
            for key, value in ROUTE_THROW_RATE_MAP.items():
                if value <= data < value + 0.25:
                    return key
        return 9
