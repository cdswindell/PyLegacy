from __future__ import annotations

import logging
from typing import List, Dict, Any


from .component_state import (
    STARTUP_SET,
    SHUTDOWN_SET,
    L,
    P,
    log,
    NUMERIC_SET,
    DIRECTIONS_SET,
    TRAIN_BRAKE_SET,
    SMOKE_SET,
    ENGINE_AUX1_SET,
    ENGINE_AUX2_SET,
    RPM_SET,
    LABOR_SET,
    SPEED_SET,
    MOMENTUM_SET,
    SMOKE_LABEL,
    SCOPE_TO_STATE_MAP,
    ComponentState,
)
from ..pdi.d4_req import D4Req
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.command_req import CommandReq
from ..protocol.command_def import CommandDefEnum
from ..pdi.constants import PdiCommand, IrdaAction, D4Action
from ..pdi.irda_req import IrdaReq
from ..protocol.constants import (
    LOCO_TYPE,
    CONTROL_TYPE,
    LOCO_TRACK_CRANE,
    LOCO_ACCESSORY,
    TRACK_CRANE_STATE_NUMERICS,
    RPM_TYPE,
    STEAM_TYPE,
    CommandScope,
)
from ..protocol.tmcc1.tmcc1_constants import TMCC1_COMMAND_TO_ALIAS_MAP, TMCC1EngineCommandEnum, TMCC1HaltCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2_COMMAND_TO_ALIAS_MAP, TMCC2EngineCommandEnum
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum as TMCC1
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as TMCC2


class EngineState(ComponentState):
    def __init__(self, scope: CommandScope = CommandScope.ENGINE) -> None:
        from ..pdi.base_req import ConsistComponent

        if scope not in {CommandScope.ENGINE, CommandScope.TRAIN}:
            raise ValueError(f"Invalid scope: {scope}, expected ENGINE or TRAIN")
        super().__init__(scope)
        self._aux1: CommandDefEnum | None = None
        self._aux2: CommandDefEnum | None = None
        self._aux: CommandDefEnum | None = None
        self._bt_id: int | None = None
        self._consist_comp: None | List[ConsistComponent] = None
        self._consist_flags: int | None = None
        self._control_type: int | None = None
        self._direction: CommandDefEnum | None = None
        self._engine_class: int | None = None
        self._engine_class_label: str | None = None
        self._engine_type: int | None = None
        self._engine_type_label: str | None = None
        self._is_legacy: bool | None = None  # assume we are in TMCC mode until/unless we receive a Legacy cmd
        self._labor: int | None = None
        self._last_aux1_opt1 = None
        self._last_aux2_opt1 = None
        self._max_speed: int | None = None
        self._momentum: int | None = None
        self._numeric: int | None = None
        self._numeric_cmd: CommandDefEnum | None = None
        self._prod_year: int | None = None
        self._rpm: int | None = None
        self._smoke_level: CommandDefEnum | None = None
        self._sound_type: int | None = None
        self._sound_type_label: str | None = None
        self._speed: int | None = None
        self._speed_limit: int | None = None
        self._start_stop: CommandDefEnum | None = None
        self._train_brake: int | None = None
        self._d4_rec_no: int | None = None

    def __repr__(self) -> str:
        sp = ss = name = num = mom = rl = yr = nu = lt = tb = aux = lb = sm = c = bt = ""
        if self._direction in {TMCC1EngineCommandEnum.FORWARD_DIRECTION, TMCC2EngineCommandEnum.FORWARD_DIRECTION}:
            dr = " FWD"
        elif self._direction in {TMCC1EngineCommandEnum.REVERSE_DIRECTION, TMCC2EngineCommandEnum.REVERSE_DIRECTION}:
            dr = " REV"
        else:
            dr = " N/A"

        if self._speed is not None:
            sp = f" Speed: {self._speed:03}"
            if self.speed_limit is not None:
                speed_limit = self.decode_speed_info(self.speed_limit)
                sp += f"/{speed_limit:03}"
            if self.max_speed is not None:
                max_speed = self.decode_speed_info(self.max_speed)
                sp += f"/{max_speed:03}"
        if self._start_stop is not None:
            if self._start_stop in STARTUP_SET:
                ss = " Started up"
            elif self._start_stop in SHUTDOWN_SET:
                ss = " Shut down"
        if self._momentum is not None:
            mom = f" Mom: {self.momentum_label}"
        if self._train_brake is not None:
            tb = f" TB: {self.train_brake_label}"
        if self._rpm is not None:
            rl = f" RPM: {self._rpm}"
        if self._labor is not None:
            lb = f" Labor: {self._labor:>2d}"
        if self._numeric is not None:
            nu = f" Num: {self._numeric}"
        if self.road_name is not None:
            name = f" {self.road_name}"
        if self.road_number is not None:
            num = f" #{self.road_number}"
        if self.year is not None:
            num = f" Released: {self.year}"
        if self.engine_type is not None:
            lt = f" {LOCO_TYPE.get(self.engine_type, 'NA')}"
        if self._aux2:
            aux = f" Aux2: {self._aux2.name.split('_')[-1]}"
        if self._smoke_level is not None:
            sm = f" Smoke: {self._smoke_level.name.split('_')[-1].lower():<4}"
        if self.bt_int:
            bt = f" BT: {self.bt_id}"
        ct = f" {CONTROL_TYPE.get(self.control_type, 'NA')}"
        if self._consist_comp:
            c = "\n"
            for cc in self._consist_comp:
                c += f"{cc} "
        return (
            f"{self.scope.title} {self._address:04}{sp}{rl}{lb}{mom}{tb}{sm}{dr}"
            f"{name}{num}{lt}{ct}{yr}{bt}{ss}{nu}{aux}{c}"
        )

    def decode_speed_info(self, speed_info):
        if speed_info is not None and speed_info == 255:  # not set
            if self.is_legacy:
                speed_info = 195
            else:
                speed_info = 31
        return speed_info

    def update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq

        # suppress duplicate commands that are received within 1 second; dups are common
        # in the lionel ecosystem, as commands are frequently sent twice or even 3 times
        # consecutively.
        self._is_known = True
        if command is None or (command == self._last_command and self.last_updated_ago < 1):
            return
        with self._cv:
            super().update(command)
            if isinstance(command, CommandReq):
                if self.is_legacy is None:
                    self._is_legacy = command.is_tmcc2 is True or self.address > 99

                # handle some aspects of halt command
                if command.command == TMCC1HaltCommandEnum.HALT:
                    if self.is_legacy:
                        self._aux1 = TMCC2.AUX1_OFF
                        self._aux2 = TMCC2.AUX2_OFF
                        self._aux = TMCC2.AUX2_OPTION_ONE
                    else:
                        self._aux1 = TMCC1.AUX1_OFF
                        self._aux2 = TMCC1.AUX2_OFF
                        self._aux = TMCC1.AUX2_OPTION_ONE
                    self._speed = 0
                    self._rpm = 0
                    self._labor = 12
                    self._numeric = None
                    self._last_command = command

                # get the downstream effects of this command, as they also impact state
                cmd_effects = self.results_in(command)
                log.debug(f"Update: {command}\nEffects: {cmd_effects}")

                # handle last numeric
                if command.command in NUMERIC_SET:
                    if self.engine_type in {LOCO_TRACK_CRANE, LOCO_ACCESSORY}:
                        if command.data in TRACK_CRANE_STATE_NUMERICS:
                            self._numeric = command.data
                            self._numeric_cmd = command.command
                    else:
                        self._numeric = command.data
                        self._numeric_cmd = command.command
                        # numeric commands can change RPM, Volume, and reset the train
                        # force a state update for this engine/train, if we are connected
                        # to a Base 3
                        from ..pdi.base3_buffer import Base3Buffer

                        if command != self._last_command:
                            Base3Buffer.request_state_update(self.address, self.scope)
                elif cmd_effects & NUMERIC_SET:
                    numeric = self._harvest_effect(cmd_effects & NUMERIC_SET)
                    log.info(f"What to do? {command}: {numeric} {type(numeric)}")

                # Direction changes trigger several other changes; we want to avoid resettling
                # rpm, labor, and speed if direction really didn't change
                if command.command in DIRECTIONS_SET:
                    if self._direction != command.command:
                        self._direction = self._change_direction(command.command)
                    else:
                        return
                elif cmd_effects & DIRECTIONS_SET:
                    self._direction = self._change_direction(self._harvest_effect(cmd_effects & DIRECTIONS_SET))

                # handle train brake
                if command.command in TRAIN_BRAKE_SET:
                    self._train_brake = command.data
                elif cmd_effects & TRAIN_BRAKE_SET:
                    self._train_brake = self._harvest_effect(cmd_effects & TRAIN_BRAKE_SET)

                if command.command in SMOKE_SET or (command.command, command.data) in SMOKE_SET:
                    if isinstance(command.command, TMCC2EffectsControl):
                        self._smoke_level = command.command
                    elif command.is_data and (command.command, command.data) in TMCC1_COMMAND_TO_ALIAS_MAP:
                        self._smoke_level = TMCC1_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]

                # aux commands
                for cmd in {command.command} | (cmd_effects & ENGINE_AUX1_SET):
                    if cmd in ENGINE_AUX1_SET:
                        self._aux = cmd if cmd in {TMCC1.AUX1_OPTION_ONE, TMCC2.AUX1_OPTION_ONE} else self._aux
                        self._aux1 = cmd

                for cmd in {command.command} | (cmd_effects & ENGINE_AUX2_SET):
                    if cmd in ENGINE_AUX2_SET:
                        self._aux = cmd if cmd in {TMCC1.AUX2_OPTION_ONE, TMCC2.AUX2_OPTION_ONE} else self._aux
                        if cmd in {TMCC1.AUX2_OPTION_ONE, TMCC2.AUX2_OPTION_ONE}:
                            if self.time_delta(self._last_updated, self._last_aux2_opt1) > 1:
                                if self.is_legacy:
                                    self._aux2 = self.update_aux_state(
                                        self._aux2,
                                        TMCC2.AUX2_ON,
                                        TMCC2.AUX2_OPTION_ONE,
                                        TMCC2.AUX2_OFF,
                                    )
                                else:
                                    self._aux2 = self.update_aux_state(
                                        self._aux2,
                                        TMCC1.AUX2_ON,
                                        TMCC1.AUX2_OPTION_ONE,
                                        TMCC1.AUX2_OFF,
                                    )
                            self._last_aux2_opt1 = self.last_updated
                        elif cmd in {
                            TMCC1.AUX2_ON,
                            TMCC1.AUX2_OFF,
                            TMCC1.AUX2_OPTION_TWO,
                            TMCC2.AUX2_ON,
                            TMCC2.AUX2_OFF,
                            TMCC2.AUX2_OPTION_TWO,
                        }:
                            self._aux2 = cmd
                            self._last_aux2_opt1 = self.last_updated

                # handle run level/rpm
                if command.command in RPM_SET:
                    self._rpm = command.data
                elif cmd_effects & RPM_SET:
                    rpm = self._harvest_effect(cmd_effects & RPM_SET)
                    if isinstance(rpm, tuple) and len(rpm) == 2:
                        self._rpm = rpm[1]
                    elif isinstance(rpm, CommandDefEnum):
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"{command} {rpm} {type(rpm)} {rpm.command_def} {type(rpm.command_def)}")
                        self._rpm = 0
                    else:
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"{command} {rpm} {type(rpm)} {cmd_effects}")
                        self._rpm = 0

                # handle labor
                if command.command in LABOR_SET:
                    self._labor = command.data
                elif cmd_effects & LABOR_SET:
                    labor = self._harvest_effect(cmd_effects & LABOR_SET)
                    if isinstance(labor, tuple) and len(labor) == 2:
                        self._labor = labor[1]
                    else:
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"{command} {labor} {type(labor)} {cmd_effects}")
                        self._speed = 0

                # handle speed
                if command.command in SPEED_SET:
                    self._speed = command.data
                elif cmd_effects & SPEED_SET:
                    speed = self._harvest_effect(cmd_effects & SPEED_SET)
                    if isinstance(speed, tuple) and len(speed) > 1:
                        self._speed = speed[1]
                    else:
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"{command} {speed} {type(speed)} {cmd_effects}")
                        self._speed = 0

                # handle momentum
                if command.command in MOMENTUM_SET:
                    if command.command in {
                        TMCC1EngineCommandEnum.MOMENTUM_LOW,
                        TMCC2EngineCommandEnum.MOMENTUM_LOW,
                    }:
                        self._momentum = 0
                    if command.command in {
                        TMCC1EngineCommandEnum.MOMENTUM_MEDIUM,
                        TMCC2EngineCommandEnum.MOMENTUM_MEDIUM,
                    }:
                        self._momentum = 3
                    if command.command in {
                        TMCC1EngineCommandEnum.MOMENTUM_HIGH,
                        TMCC2EngineCommandEnum.MOMENTUM_HIGH,
                    }:
                        self._momentum = 7
                    elif command.command == TMCC2EngineCommandEnum.MOMENTUM:
                        self._momentum = command.data

                # handle startup/shutdown
                if command.command in STARTUP_SET:
                    self._start_stop = command.command
                elif command.command in SHUTDOWN_SET:
                    self._start_stop = command.command
                elif cmd_effects & STARTUP_SET:
                    startup = self._harvest_effect(cmd_effects & STARTUP_SET)
                    if isinstance(startup, CommandDefEnum):
                        self._start_stop = startup
                    elif command.is_data and (command.command, command.data) in TMCC2_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC2_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
                    elif command.is_data and (command.command, command.data) in TMCC1_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC1_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
                elif cmd_effects & SHUTDOWN_SET:
                    shutdown = self._harvest_effect(cmd_effects & SHUTDOWN_SET)
                    if isinstance(shutdown, CommandDefEnum):
                        self._start_stop = shutdown
                    elif command.is_data and (command.command, command.data) in TMCC2_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC2_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
                    elif command.is_data and (command.command, command.data) in TMCC1_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC1_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
            elif (
                isinstance(command, BaseReq)
                and command.status == 0
                and command.pdi_command
                in {
                    PdiCommand.BASE_ENGINE,
                    PdiCommand.BASE_TRAIN,
                    PdiCommand.UPDATE_ENGINE_SPEED,
                    PdiCommand.UPDATE_TRAIN_SPEED,
                }
            ):
                from ..pdi.base_req import EngineBits

                if self._speed is None and command.is_valid(EngineBits.SPEED):
                    self._speed = command.speed
                if command.pdi_command in {PdiCommand.BASE_ENGINE, PdiCommand.BASE_TRAIN}:
                    if command.is_valid(EngineBits.MAX_SPEED):
                        self._max_speed = command.max_speed
                    if command.is_valid(EngineBits.SPEED_LIMIT):
                        self._speed_limit = command.speed_limit
                    if command.is_valid(EngineBits.MOMENTUM):
                        self._momentum = command.momentum_tmcc
                    if command.is_valid(EngineBits.RUN_LEVEL):
                        self._rpm = command.run_level
                    if command.is_valid(EngineBits.LABOR_BIAS):
                        self._labor = command.labor_bias_tmcc
                    if command.is_valid(EngineBits.CONTROL_TYPE):
                        self._control_type = command.control_id
                        self._is_legacy = command.is_legacy
                    if command.is_valid(EngineBits.SOUND_TYPE):
                        self._sound_type = command.sound_id
                        self._sound_type_label = command.sound
                    if command.is_valid(EngineBits.CLASS_TYPE):
                        self._engine_class = command.loco_class_id
                        self._engine_class_label = command.loco_class
                    if command.is_valid(EngineBits.LOCO_TYPE):
                        self._engine_type = command.loco_type_id
                        self._engine_type_label = command.loco_type
                    if command.is_valid(EngineBits.SMOKE_LEVEL) and self.is_legacy:
                        self._smoke_level = command.smoke
                    if command.is_valid(EngineBits.TRAIN_BRAKE):
                        self._train_brake = command.train_brake_tmcc
                        if self._train_brake > 8:
                            print("--- TB ---", command)
                    if command.pdi_command == PdiCommand.BASE_TRAIN:
                        self._consist_comp = command.consist_components
                        self._consist_flags = command.consist_flags
            elif isinstance(command, BaseReq) and command.pdi_command == PdiCommand.BASE_MEMORY and command.data_bytes:
                from ..pdi.base_req import BASE_MEMORY_READ_MAP

                tpl = BASE_MEMORY_READ_MAP.get(command.start, None)
                if isinstance(tpl, tuple):
                    setattr(self, tpl[0], tpl[1](command.data_bytes))
            elif isinstance(command, IrdaReq) and command.action == IrdaAction.DATA:
                self._prod_year = command.year
            elif isinstance(command, D4Req):
                if command.action == D4Action.MAP:
                    if command.record_no == 0xFFFF:  # delete record
                        # TODO: delete state record
                        pass
                    elif command.record_no is not None:
                        self._d4_rec_no = command.record_no
                else:
                    print("--- D4 ---", command)
            else:
                print("---", command)
            self.changed.set()
            self._cv.notify_all()

    def _change_direction(self, new_dir: CommandDefEnum) -> CommandDefEnum:
        if new_dir in {TMCC1EngineCommandEnum.TOGGLE_DIRECTION, TMCC2EngineCommandEnum.TOGGLE_DIRECTION}:
            if self.direction is not None:
                if self.is_legacy is True and self.direction in {
                    TMCC2EngineCommandEnum.FORWARD_DIRECTION,
                    TMCC2EngineCommandEnum.REVERSE_DIRECTION,
                }:
                    new_dir = (
                        TMCC2EngineCommandEnum.FORWARD_DIRECTION
                        if self.direction == TMCC2EngineCommandEnum.REVERSE_DIRECTION
                        else TMCC2EngineCommandEnum.REVERSE_DIRECTION
                    )
                elif self.is_tmcc is True and self.direction in {
                    TMCC1EngineCommandEnum.FORWARD_DIRECTION,
                    TMCC1EngineCommandEnum.REVERSE_DIRECTION,
                }:
                    new_dir = (
                        TMCC1EngineCommandEnum.FORWARD_DIRECTION
                        if self.direction == TMCC1EngineCommandEnum.REVERSE_DIRECTION
                        else TMCC1EngineCommandEnum.REVERSE_DIRECTION
                    )
                else:
                    new_dir = None
        return new_dir

    def as_bytes(self) -> bytes:
        from ..pdi.base_req import BaseReq

        byte_str = bytes()
        # encode name, number, momentum, speed, and rpm using PDI command
        pdi = None
        if self.scope == CommandScope.ENGINE:
            pdi = BaseReq(self.address, PdiCommand.BASE_ENGINE, state=self)
        elif self.scope == CommandScope.TRAIN:
            pdi = BaseReq(self.address, PdiCommand.BASE_TRAIN, state=self)
        if pdi:
            byte_str += pdi.as_bytes
        if self.scope == CommandScope.ENGINE and self.bt_int:
            bts = self.bt_int.to_bytes(length=2, byteorder="little")
            pdi = BaseReq(self.address, PdiCommand.BASE_MEMORY, flags=0, start=4, data_length=2, data_bytes=bts)
            byte_str += pdi.as_bytes
        if self._start_stop is not None:
            byte_str += CommandReq.build(self._start_stop, self.address, scope=self.scope).as_bytes
        if self._smoke_level is not None:
            byte_str += CommandReq.build(self._smoke_level, self.address, scope=self.scope).as_bytes
        if self._direction is not None:
            # the direction state will have encoded in it the syntax (tmcc1 or tmcc2)
            byte_str += CommandReq.build(self._direction, self.address, scope=self.scope).as_bytes
        if self._numeric is not None and self._numeric_cmd is not None:
            if self.engine_type in {LOCO_TRACK_CRANE, LOCO_ACCESSORY}:
                byte_str += CommandReq.build(
                    self._numeric_cmd,
                    self.address,
                    data=self._numeric,
                    scope=self.scope,
                ).as_bytes
        if self._aux is not None:
            byte_str += CommandReq.build(self._aux, self.address).as_bytes
        if self._aux1 is not None:
            byte_str += CommandReq.build(self.aux1, self.address).as_bytes
        if self._aux2 is not None:
            byte_str += CommandReq.build(self.aux2, self.address).as_bytes
        return byte_str

    @property
    def is_rpm(self) -> bool:
        return self.engine_type in RPM_TYPE

    @property
    def is_steam(self) -> bool:
        return self.engine_type in STEAM_TYPE

    @property
    def speed(self) -> int:
        return self._speed

    @property
    def speed_limit(self) -> int:
        return self._speed_limit

    @property
    def max_speed(self) -> int:
        return self._max_speed

    @property
    def speed_max(self) -> int | None:
        if self.max_speed and self.max_speed != 255 and self.speed_limit != 255:
            ms = min(self.max_speed, self.speed_limit)
        elif self._speed_limit and self.speed_limit != 255:
            ms = self._speed_limit
        elif self.max_speed and self.max_speed != 255:
            ms = self.max_speed
        else:
            ms = 199 if self.is_legacy else 31
        if self.is_legacy is False and ms > 31:
            ms = 31
        return ms

    @property
    def speed_label(self) -> str:
        return self._as_label(self._speed)

    @property
    def bt_int(self) -> int:
        return self._bt_id

    # noinspection PyTypeChecker
    @property
    def bt_id(self) -> str:
        if self.bt_int:
            return int.to_bytes(self.bt_int, 2, "big").hex().upper()
        return None

    @property
    def numeric(self) -> int:
        return self._numeric

    @property
    def momentum(self) -> int:
        return self._momentum

    @property
    def momentum_label(self) -> str:
        return self._as_label(self.momentum)

    @property
    def rpm(self) -> int:
        return self._rpm if self.is_rpm else 0

    @property
    def rpm_label(self) -> str:
        return self._as_label(self.rpm)

    @property
    def labor(self) -> int:
        return self._labor

    @property
    def labor_label(self) -> str:
        return self._as_label(self.labor)

    @property
    def smoke(self) -> CommandDefEnum | None:
        return self._smoke_level

    @property
    def smoke_label(self) -> str:
        return SMOKE_LABEL.get(self._smoke_level, None)

    @property
    def train_brake(self) -> int:
        return self._train_brake

    @property
    def train_brake_label(self) -> str:
        return self._as_label(self.train_brake)

    @property
    def control_type(self) -> int:
        return self._control_type

    @property
    def control_type_label(self) -> str:
        return CONTROL_TYPE.get(self.control_type, "NA")

    @property
    def sound_type(self) -> int:
        return self._sound_type

    @property
    def sound_type_label(self) -> str:
        return self._sound_type_label

    @property
    def engine_type(self) -> int:
        return self._engine_type

    @property
    def engine_type_label(self) -> str:
        return self._engine_type_label

    @property
    def engine_class(self) -> int:
        return self._engine_class

    @property
    def engine_class_label(self) -> str:
        return self._engine_class_label

    @property
    def direction(self) -> CommandDefEnum | None:
        return self._direction

    @property
    def direction_label(self) -> str:
        dr = "--"
        if self._direction in {TMCC1EngineCommandEnum.FORWARD_DIRECTION, TMCC2EngineCommandEnum.FORWARD_DIRECTION}:
            dr = "FW"
        elif self._direction in {TMCC1EngineCommandEnum.REVERSE_DIRECTION, TMCC2EngineCommandEnum.REVERSE_DIRECTION}:
            dr = "RV"
        return dr

    @property
    def stop_start(self) -> CommandDefEnum | None:
        return self._start_stop

    @property
    def is_started(self) -> bool:
        return self._start_stop in STARTUP_SET

    @property
    def is_shutdown(self) -> bool:
        return self._start_stop in SHUTDOWN_SET

    @property
    def year(self) -> int:
        return self._prod_year

    @property
    def is_aux_on(self) -> bool:
        return self._aux in {TMCC1.AUX1_OPTION_ONE, TMCC2.AUX1_OPTION_ONE}

    @property
    def is_aux_off(self) -> bool:
        return self.is_aux_on is False

    @property
    def aux1(self) -> CommandDefEnum:
        return self._aux1

    @property
    def aux2(self) -> CommandDefEnum:
        return self._aux2

    @property
    def is_aux1(self) -> bool:
        return self._aux2 in {TMCC1.AUX1_ON, TMCC2.AUX1_ON}

    @property
    def is_aux2(self) -> bool:
        return self._aux2 in {TMCC1.AUX2_ON, TMCC2.AUX2_ON}

    @property
    def record_no(self) -> int:
        return self._d4_rec_no

    @property
    def is_tmcc(self) -> bool:
        return self._is_legacy is False

    @property
    def is_legacy(self) -> bool:
        if self._is_legacy is None:
            if self.scope == CommandScope.ENGINE and self.address > 99:
                self._is_legacy = True
        return self._is_legacy is True

    @property
    def is_lcs(self) -> bool:
        return False

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        for elem in ["speed", "speed_limit", "max_speed", "train_brake", "momentum", "rpm", "labor", "year"]:
            if hasattr(self, elem):
                val = getattr(self, elem)
                d[elem] = val if val is not None and val != 255 else None
        d["direction"] = self.direction.name.lower() if self.direction else None
        d["smoke"] = self.smoke.name.lower() if self.smoke else None
        d["control"] = self.control_type_label.lower() if self.control_type else None
        d["sound_type"] = self.sound_type_label.lower() if self.sound_type else None
        d["engine_type"] = self.engine_type_label.lower() if self.engine_type else None
        d["engine_class"] = self.engine_class_label.lower() if self.engine_class else None
        if isinstance(self, TrainState):
            d["flags"] = self._consist_flags
            d["components"] = {c.tmcc_id: c.info for c in self._consist_comp}
        return d


class TrainState(EngineState):
    from ..pdi.base_req import ConsistComponent

    def __init__(self, scope: CommandScope = CommandScope.TRAIN) -> None:
        if scope != CommandScope.TRAIN:
            raise ValueError(f"Invalid scope: {scope}, expected {CommandScope.TRAIN.name}")
        super().__init__(scope)
        # hard code TMCC2, for now
        self._is_legacy = True
        self._control_type = 2

    @property
    def consist_flags(self) -> int:
        return self._consist_flags

    @property
    def consist_components(self) -> List[ConsistComponent]:
        return self._consist_comp


SCOPE_TO_STATE_MAP[CommandScope.ENGINE] = EngineState
SCOPE_TO_STATE_MAP[CommandScope.TRAIN] = TrainState
