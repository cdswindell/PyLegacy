#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#  All Rights Reserved.
#
#  This work is licensed under the terms of the LPGL license.
#  SPDX-License-Identifier: LPGL
#

from __future__ import annotations

import logging
from time import monotonic
from typing import Any, Dict, List, TypeVar

from .comp_data import CompDataHandler, CompDataMixin, decode_tmcc_speed, encode_tmcc_speed
from .component_state import ComponentState, L, LcsProxyState, P, SCOPE_TO_STATE_MAP, UpdateResult, log
from .prod_info import ProdInfo
from ..pdi.constants import Bpc2Action, D4Action, IrdaAction, PdiCommand
from ..pdi.d4_req import D4Req
from ..pdi.irda_req import IrdaReq
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import (
    ACELA_TYPE,
    CAB1_CONTROL_TYPE,
    CONTROL_TYPE,
    CRANE_TYPE,
    CommandScope,
    DIESEL_TYPE,
    ELECTRIC_TYPE,
    EngineType,
    FREIGHT_TYPE,
    LEGACY_CONTROL_TYPE,
    LOCO_CLASS,
    LOCO_TRACK_CRANE,
    LOCO_TYPE,
    OfficialRRSpeeds,
    PASSENGER_TYPE,
    RPM_TYPE,
    SOUND_TYPE,
    STEAM_TYPE,
    THROTTLE_TYPE,
    TRANSFORMER_TYPE,
)
from ..protocol.multibyte.multibyte_constants import (
    TMCC2EffectsControl,
    TMCC2EngineCommandEnumEx,
    TMCC2R4LCEnum,
    UnitAssignment,
)

# noinspection PyPep8Naming
from ..protocol.tmcc1.tmcc1_constants import (
    TMCC1EngineCommandEnum,
    TMCC1EngineCommandEnum as TMCC1,
    TMCC1HaltCommandEnum,
    TMCC1RRSpeedsEnum,
    TMCC1_COMMAND_TO_ALIAS_MAP,
)

# noinspection PyPep8Naming
from ..protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum,
    TMCC2EngineCommandEnum as TMCC2,
    TMCC2RRSpeedsEnum,
    TMCC2_COMMAND_TO_ALIAS_MAP,
)

DIRECTIONS_SET = {
    TMCC1EngineCommandEnum.FORWARD_DIRECTION,
    TMCC2EngineCommandEnum.FORWARD_DIRECTION,
    TMCC1EngineCommandEnum.REVERSE_DIRECTION,
    TMCC2EngineCommandEnum.REVERSE_DIRECTION,
    TMCC1EngineCommandEnum.TOGGLE_DIRECTION,
    TMCC2EngineCommandEnum.TOGGLE_DIRECTION,
}
MOMENTUM_SET = {
    TMCC1EngineCommandEnum.MOMENTUM_LOW,
    TMCC1EngineCommandEnum.MOMENTUM_MEDIUM,
    TMCC1EngineCommandEnum.MOMENTUM_HIGH,
    TMCC2EngineCommandEnum.MOMENTUM_LOW,
    TMCC2EngineCommandEnum.MOMENTUM_MEDIUM,
    TMCC2EngineCommandEnum.MOMENTUM_HIGH,
    TMCC2EngineCommandEnum.MOMENTUM,
}
SPEED_SET = {
    TMCC1EngineCommandEnum.ABSOLUTE_SPEED,
    TMCC2EngineCommandEnum.ABSOLUTE_SPEED,
    TMCC1EngineCommandEnum.SPEED_HIGHBALL,
    TMCC2EngineCommandEnum.SPEED_HIGHBALL,
    TMCC1EngineCommandEnum.SPEED_LIMITED,
    TMCC2EngineCommandEnum.SPEED_LIMITED,
    TMCC1EngineCommandEnum.SPEED_MEDIUM,
    TMCC2EngineCommandEnum.SPEED_MEDIUM,
    TMCC1EngineCommandEnum.SPEED_NORMAL,
    TMCC2EngineCommandEnum.SPEED_NORMAL,
    TMCC1EngineCommandEnum.SPEED_RESTRICTED,
    TMCC2EngineCommandEnum.SPEED_RESTRICTED,
    TMCC1EngineCommandEnum.SPEED_SLOW,
    TMCC2EngineCommandEnum.SPEED_SLOW,
    (TMCC1EngineCommandEnum.ABSOLUTE_SPEED, 0),
    (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 0),
}
TARGET_SPEED_SET = {
    TMCC1EngineCommandEnum.TARGET_SPEED,
    TMCC2EngineCommandEnumEx.TARGET_SPEED,
}
RPM_SET = {
    TMCC2EngineCommandEnum.DIESEL_RPM,
}
LABOR_SET = {
    TMCC2EngineCommandEnum.ENGINE_LABOR,
}
NUMERIC_SET = {
    TMCC1EngineCommandEnum.NUMERIC,
    TMCC2EngineCommandEnum.NUMERIC,
}
TRAIN_BRAKE_SET = {
    TMCC2EngineCommandEnum.TRAIN_BRAKE,
}
STARTUP_SET = {
    TMCC1EngineCommandEnum.START_UP_IMMEDIATE,
    TMCC2EngineCommandEnum.START_UP_IMMEDIATE,
    TMCC2EngineCommandEnum.START_UP_DELAYED,
}
SHUTDOWN_SET = {
    TMCC1EngineCommandEnum.SHUTDOWN_IMMEDIATE,
    TMCC2EngineCommandEnum.SHUTDOWN_DELAYED,
    (TMCC2EngineCommandEnum.NUMERIC, 5),
    TMCC2EngineCommandEnum.SHUTDOWN_IMMEDIATE,
}
RESET_SET = {
    TMCC1EngineCommandEnum.RESET,
    (TMCC1EngineCommandEnum.NUMERIC, 0),
    TMCC2EngineCommandEnum.RESET,
    (TMCC2EngineCommandEnum.NUMERIC, 0),
}
ENGINE_AUX1_SET = {
    TMCC1EngineCommandEnum.AUX1_ON,
    TMCC1EngineCommandEnum.AUX1_OFF,
    TMCC1EngineCommandEnum.AUX1_OPTION_ONE,
    TMCC1EngineCommandEnum.AUX1_OPTION_TWO,
    TMCC2EngineCommandEnum.AUX1_ON,
    TMCC2EngineCommandEnum.AUX1_OFF,
    TMCC2EngineCommandEnum.AUX1_OPTION_ONE,
    TMCC2EngineCommandEnum.AUX1_OPTION_TWO,
}
ENGINE_AUX2_SET = {
    TMCC1EngineCommandEnum.AUX2_ON,
    TMCC1EngineCommandEnum.AUX2_OFF,
    TMCC1EngineCommandEnum.AUX2_OPTION_ONE,
    TMCC1EngineCommandEnum.AUX2_OPTION_TWO,
    TMCC2EngineCommandEnum.AUX2_ON,
    TMCC2EngineCommandEnum.AUX2_OFF,
    TMCC2EngineCommandEnum.AUX2_OPTION_ONE,
    TMCC2EngineCommandEnum.AUX2_OPTION_TWO,
}
SMOKE_SET = {
    TMCC1EngineCommandEnum.SMOKE_ON,
    (TMCC1EngineCommandEnum.NUMERIC, 9),
    TMCC1EngineCommandEnum.SMOKE_OFF,
    (TMCC1EngineCommandEnum.NUMERIC, 8),
    TMCC2EffectsControl.SMOKE_OFF,
    TMCC2EffectsControl.SMOKE_LOW,
    TMCC2EffectsControl.SMOKE_MEDIUM,
    TMCC2EffectsControl.SMOKE_HIGH,
}
SMOKE_LABEL = {
    TMCC1EngineCommandEnum.SMOKE_ON: "+",
    TMCC1EngineCommandEnum.SMOKE_OFF: "-",
    TMCC2EffectsControl.SMOKE_OFF: "-",
    TMCC2EffectsControl.SMOKE_LOW: "L",
    TMCC2EffectsControl.SMOKE_MEDIUM: "M",
    TMCC2EffectsControl.SMOKE_HIGH: "H",
}

TMCC1_AUX_ONE_PREFIX_MAP = {
    (TMCC1EngineCommandEnum.NUMERIC, 3): TMCC1EngineCommandEnum.START_UP_IMMEDIATE,
    (TMCC1EngineCommandEnum.NUMERIC, 5): TMCC1EngineCommandEnum.SHUTDOWN_IMMEDIATE,
}

TMCC1_PREFIX_TO_AUX_ONE_MAP = {v: k for k, v in TMCC1_AUX_ONE_PREFIX_MAP.items()}

CANCEL_PENDINGS_ON_ENQUEUE = RESET_SET | {TMCC2EngineCommandEnum.STOP_IMMEDIATE}

CANCEL_PENDINGS_SET = DIRECTIONS_SET | CANCEL_PENDINGS_ON_ENQUEUE | SHUTDOWN_SET

# the commands a live speed ramp arbitrates for itself. RPM_SET and LABOR_SET are here
# only so that notify_ramp gets to see them; it returns True for them unconditionally,
# so a sound or effort trim can never reach cancel_ramps()
RAMP_ARBITRATED = TARGET_SPEED_SET | SPEED_SET | RPM_SET | LABOR_SET

R = TypeVar("R", bound=OfficialRRSpeeds)


# noinspection string-format,unreachable-code
class EngineState(ComponentState):
    @classmethod
    def _csv_headers(cls, include_state: bool = False) -> list[str]:
        cols = super()._csv_headers(include_state=include_state)
        if ProdInfo.is_capable():
            cols.extend(["sku"])
        cols.extend(["type", "control", "sound"])
        if include_state:
            cols.extend(["target", "speed", "speed_limit", "momentum", "rpm", "effort", "fuel", "water"])
        return cols

    def __init__(self, scope: CommandScope = CommandScope.ENGINE) -> None:
        if scope not in {CommandScope.ENGINE, CommandScope.TRAIN}:
            raise ValueError(f"Invalid scope: {scope}, expected ENGINE or TRAIN")
        super().__init__(scope)
        self._aux1: CommandDefEnum | None = None
        self._aux2: CommandDefEnum | None = None
        self._aux: CommandDefEnum | None = None
        self._direction: CommandDefEnum | None = None
        self._is_legacy: bool | None = None  # assume we are in TMCC mode until/unless we receive a Legacy cmd
        self._last_aux1_opt1 = None
        self._last_aux2_opt1 = None
        self._numeric: int | None = None
        self._numeric_cmd: CommandDefEnum | None = None
        self._prod_year: int | None = None
        self._start_stop: CommandDefEnum | None = None
        self._d4_rec_no: int | None = None
        self._is_d4: bool = False
        self._ramping: bool = False
        self._ramp = None  # SpeedRamp, when this instance owns a live ramp for this engine
        self._prod_info = None
        self._pdi_source: bool = False  # for train is LCS BPC2

    def __repr__(self) -> str:
        try:
            sp = ss = name = num = mom = rl = yr = nu = lt = tb = aux = lb = sm = c = bt = tr = fl = rn = ""
            if self._direction in {TMCC1EngineCommandEnum.FORWARD_DIRECTION, TMCC2EngineCommandEnum.FORWARD_DIRECTION}:
                dr = " FWD"
            elif self._direction in {
                TMCC1EngineCommandEnum.REVERSE_DIRECTION,
                TMCC2EngineCommandEnum.REVERSE_DIRECTION,
            }:
                dr = " REV"
            else:
                dr = " N/A"

            if self.speed is not None:
                sp = f" Speed: {self.speed:03}"
                if self.target_speed is not None:
                    speed_limit = self.decode_speed_info(self.target_speed)
                    sp += f"/{speed_limit:03}"
                if self.speed_limit is not None:
                    speed_limit = self.decode_speed_info(self.speed_limit)
                    sp += f"/{speed_limit:03}"
                elif self.max_speed is not None:
                    max_speed = self.decode_speed_info(self.max_speed)
                    sp += f"/{max_speed:03}"
            if self._start_stop in STARTUP_SET:
                ss = " Started up"
            elif self._start_stop in SHUTDOWN_SET:
                ss = " Shut down"
            if self.momentum is not None:
                mom = f" Mom: {self.momentum_label}"
            if self.train_brake is not None:
                tb = f" TB: {self.train_brake_label}"
            if self.rpm is not None:
                rl = f" RPM: {self.rpm}"
            if self.labor is not None:
                lb = f" Labor: {self.labor:>2d}"
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
            if isinstance(self._aux2, CommandDefEnum):
                aux = f" Aux2: {self._aux2.name.split('_')[-1]}"
            if isinstance(self.smoke_level, CommandDefEnum):
                sm = f" Smoke: {self.smoke_level.name.split('_')[-1].lower():<4}"
            if self.bt_int:
                bt = f" BT: {self.bt_id}"
            if self.fuel_level_pct is not None:
                fl = f" Fuel: {self.fuel_level_pct:>3}%"
            ct = f" {CONTROL_TYPE.get(self.control_type, 'NA')}"
            if self._d4_rec_no is not None:
                rn = f" {self.record_no_label}"
            if isinstance(self, TrainState) and self.consist_components:
                c = "\n"
                for cc in self.consist_components:
                    c += f"{cc} "
            elif self.train_tmcc_id:
                tr = f" Train: {self.train_tmcc_id}"
            return (
                f"{self.scope.title} {self._address:04}{sp}{rl}{lb}{mom}{tb}{fl}{dr}{sm}"
                f"{name}{num}{lt}{ct}{yr}{bt}{rn}{ss}{tr}{nu}{aux}{c}"
            )
        except AttributeError as ae:
            if self.comp_data is None:
                return f"{self.scope.title} {self._address:04}: no information provided from Base 2/3"
            else:
                log.error(f"Exception while processing {self.scope.title} {self._address:04} state: {ae}", exc_info=ae)
            return f"{self.scope.title} {self._address:04}: unavailable"

    def as_csv(self, include_state: bool = False) -> dict[str, str | int | None]:
        data = super().as_csv(include_state=include_state)
        if ProdInfo.is_capable() and self.bt_id:
            data["sku"] = self.sku
        data["type"] = self.engine_type_label
        data["control"] = self.control_type_label
        data["sound"] = self.sound_type_label
        if include_state:
            data["target"] = self.target_speed
            data["speed"] = self.speed
            data["speed_limit"] = self.speed_limit
            data["momentum"] = self.momentum
            if self.is_rpm:
                data["rpm"] = self.rpm
            data["effort"] = self.labor
            data["fuel"] = self.fuel_level_pct
            if self.is_steam:
                data["water"] = self.water_level_pct
        return data

    @property
    def prod_info(self) -> ProdInfo | None:
        if ProdInfo.is_capable() and self.bt_id:
            with self._cv:
                if self._prod_info is None:
                    self._prod_info = ProdInfo.by_btid(self.bt_id)
        return self._prod_info

    @property
    def sku(self) -> str | None:
        return self.prod_info.sku_number if self.prod_info else None

    @property
    def is_ramping(self) -> bool:
        return self._ramping

    @is_ramping.setter
    def is_ramping(self, value: bool):
        with self._cv:
            self._ramping = value

    @property
    def ramp(self):
        """The live speed ramp for this engine, if this instance owns one."""
        return self._ramp

    def ramp_to(self, speed: int, *, dialog: bool = False):
        """
        Ramp this engine toward a target speed, retargeting a ramp that is already
        running rather than cancelling it and starting another.
        """
        from ..protocol.sequence.speed_ramp import RampRegistry

        # the registry is the single owner of the (scope, tmcc_id) -> ramp mapping; the
        # handle is mirrored here so state objects, and _update_state, reach it directly
        ramp = RampRegistry.build().ramp_to(self, speed, dialog=dialog)
        self._ramp = ramp
        return ramp

    def abort_ramp(self, reason: str = None, *, target_speed: int = None, restore_effort: bool = False) -> None:
        """
        Stop this engine's ramp, if any, leaving it at its current speed and its target
        speed reflecting where it is now headed: `target_speed` when the caller knows
        it - 0 for a hard stop, another controller's speed when it takes the throttle -
        and otherwise the speed the ramp had reached.

        `restore_effort` marks the hard stops, which return effort to neutral here in
        state; the ramp that owns the engine sends the matching command so the
        locomotive returns with it.
        """
        from ..protocol.sequence.speed_ramp import RampRegistry

        ramp = self._ramp
        self._ramp = None
        RampRegistry.build().abort(self, reason, target_speed=target_speed, restore_effort=restore_effort)
        if ramp is not None:
            ramp.abort(reason, target_speed=target_speed, restore_effort=restore_effort)
        elif target_speed is not None:
            # no ramp of ours to square up, but the target still has to reflect reality:
            # a hard stop cannot be left advertising the speed something else was chasing
            self.sync_target_speed(target_speed)

    def notify_ramp(self, command: L | P) -> bool:
        """
        Offer a command to the live ramp. Returns True when the pending commands must
        *not* be cancelled: the ramp claimed the command as its own echo, or absorbed
        it as an RPM or effort trim.

        With no ramp of our own the widened arbitration set must not change anything
        for a RampedSpeedReq ramp, so only a TARGET_SPEED still cancels, exactly as
        it did before arbitration existed.
        """
        ramp = self._ramp
        if ramp is None or ramp.is_active is False:
            return command.command not in TARGET_SPEED_SET
        return ramp.on_state_command(command)

    def decode_speed_info(self, speed_info):
        if speed_info is not None and speed_info == 255:  # not set
            if self.is_legacy:
                speed_info = 195
            else:
                speed_info = 31
        return speed_info

    # noinspection PyStringConversionWithoutDunderMethod
    def _update_state(self, command: L | P) -> UpdateResult:
        """Updates engine state transactionally from command or effects; handles duplicates and all controls"""
        from ..pdi.base_req import BaseReq

        # suppress duplicate commands that are received within 1 second; dups are common
        # in the lionel ecosystem, as commands are frequently sent twice or even 3 times
        # consecutively.
        self._is_known = True
        if command is None or (command == self._last_command and self.last_updated_ago < 1):
            return UpdateResult.IGNORED
        # Updates engine state transactionally from command or effects; handles duplicates, aux, speed, rpm, labor,
        # direction, halt, momentum, startup/shutdown
        if isinstance(command, CompDataMixin) and command.is_comp_data_record:
            self._update_comp_data(command.comp_data)
            if isinstance(command, D4Req):
                self._is_legacy = True
                self._d4_rec_no = command.record_no
                self._is_d4 = True
            if self.speed and self.target_speed == 0 and not self.is_ramping:
                self.comp_data.target_speed = encode_tmcc_speed(self.speed, self.comp_data.is_legacy)

        elif isinstance(command, CommandReq):
            if command.is_tmcc2 is True or self.address > 99:
                self._is_legacy = True

            # handle tmcc1 Aux1-prefixed commands
            if self.last_command and self.last_command.command == TMCC1EngineCommandEnum.AUX1_OPTION_ONE:
                if command.command == TMCC1EngineCommandEnum.NUMERIC:
                    aux = TMCC1_AUX_ONE_PREFIX_MAP.get((TMCC1EngineCommandEnum.NUMERIC, command.data), None)
                    if aux:
                        command = CommandReq(aux, command.address, scope=self.scope)

            # handle some aspects of the halt command
            if command.command in {TMCC2EngineCommandEnum.SYSTEM_HALT, TMCC1HaltCommandEnum.HALT}:
                if self.is_legacy:
                    self._aux1 = TMCC2.AUX1_OFF
                    self._aux2 = TMCC2.AUX2_OFF
                    self._aux = TMCC2.AUX2_OPTION_ONE
                else:
                    self._aux1 = TMCC1.AUX1_OFF
                    self._aux2 = TMCC1.AUX2_OFF
                    self._aux = TMCC1.AUX2_OPTION_ONE
                if self.comp_data is not None:
                    self.comp_data.speed = 0
                    self.comp_data.target_speed = 0
                    self.comp_data.rpm_tmcc = 0
                    self.comp_data.labor_tmcc = 12
                self.is_ramping = False
                self.abort_ramp("halt", target_speed=0, restore_effort=True)
                self._numeric = None

            # get the downstream effects of this command, as they also impact state
            cmd_effects = self.results_in(command)
            log.debug(f"Update: {command}\nEffects: {cmd_effects}")

            # Cancel any delayed requests, if impacted
            if command.command in CANCEL_PENDINGS_SET or (self._ramping and command.command in RAMP_ARBITRATED):
                # ignore direction commands if they are the same as the current direction
                if command.command in DIRECTIONS_SET and self.direction == command.command:
                    pass
                elif command.command not in CANCEL_PENDINGS_SET and self.notify_ramp(command) is True:
                    # the live ramp claimed this command as its own echo, or absorbed it
                    # as an RPM or effort trim: either way, the train keeps ramping
                    pass
                else:
                    log.debug(f"Cancelled pending commands TMCC ID: {self.tmcc_id} {command.command}")
                    # a hard stop takes the engine to a standstill; anything else that
                    # gets this far is another controller taking the throttle, and its
                    # effort setting is not ours to override
                    hard_stop = command.command in CANCEL_PENDINGS_SET
                    self.cancel_ramps(
                        self._cancelled_target_speed(command),
                        reason=command.command.name if hard_stop else f"foreign {command.command.name}",
                        restore_effort=hard_stop,
                    )

            # handle last numeric
            if command.command in NUMERIC_SET:
                self._numeric = command.data
                self._numeric_cmd = command.command
            elif cmd_effects & NUMERIC_SET:
                numeric = self._harvest_effect(cmd_effects & NUMERIC_SET)
                log.info(f"What to do? {command}: {numeric} {type(numeric)}")

            # Direction changes trigger several other changes; we want to avoid resettling
            # rpm, labor, and speed if the direction really didn't change
            if command.command in DIRECTIONS_SET:
                if self._direction != command.command:
                    self._direction = self._change_direction(command.command)
                else:
                    return UpdateResult.NO_CHANGE
            elif cmd_effects & DIRECTIONS_SET:
                self._direction = self._change_direction(self._harvest_effect(cmd_effects & DIRECTIONS_SET))

            # handle reset
            if command.command in RESET_SET or cmd_effects & RESET_SET:
                self.is_ramping = False
                self.abort_ramp("reset", target_speed=0, restore_effort=True)

            # handle train brake
            if command.command in TRAIN_BRAKE_SET:
                self.comp_data.train_brake_tmcc = command.data
            elif cmd_effects & TRAIN_BRAKE_SET:
                self.comp_data.train_brake_tmcc = self._harvest_effect(cmd_effects & TRAIN_BRAKE_SET)

            if command.command in SMOKE_SET or (command.command, command.data) in SMOKE_SET:
                if isinstance(command.command, TMCC2EffectsControl):
                    self.comp_data.smoke_tmcc = command.command
                elif command.is_data and (command.command, command.data) in TMCC1_COMMAND_TO_ALIAS_MAP:
                    self.comp_data.smoke_tmcc = TMCC1_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]

            # aux commands
            for cmd in {command.command} | (cmd_effects & ENGINE_AUX1_SET):
                if cmd in ENGINE_AUX1_SET:
                    self._aux = cmd if cmd in {TMCC1.AUX1_OPTION_ONE, TMCC2.AUX1_OPTION_ONE} else self._aux
                    self._aux1 = cmd

            if not self._pdi_source:
                for cmd in {command.command} | (cmd_effects & ENGINE_AUX2_SET):
                    if cmd in ENGINE_AUX2_SET:
                        # Updates aux2 state based on time delta and legacy mode
                        if cmd in {TMCC1.AUX2_OPTION_ONE, TMCC2.AUX2_OPTION_ONE}:
                            self._aux = cmd
                            now = monotonic()
                            if self.time_delta(now, self._last_aux2_opt1) > 1:
                                if self._is_legacy:
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
                                self._last_aux2_opt1 = now
                        elif cmd in {
                            TMCC1.AUX2_ON,
                            TMCC1.AUX2_OFF,
                            TMCC1.AUX2_OPTION_TWO,
                            TMCC2.AUX2_ON,
                            TMCC2.AUX2_OFF,
                            TMCC2.AUX2_OPTION_TWO,
                        }:
                            self._aux2 = cmd

            # handle run level/rpm
            if command.command in RPM_SET:
                self.comp_data.rpm_tmcc = command.data
            elif cmd_effects & RPM_SET:
                rpm = self._harvest_effect(cmd_effects & RPM_SET)
                if isinstance(rpm, tuple) and len(rpm) == 2:
                    self.comp_data.rpm_tmcc = rpm[1]
                elif isinstance(rpm, CommandDefEnum):
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"{command} {rpm} {type(rpm)} {rpm.command_def} {type(rpm.command_def)}")
                    self.comp_data.rpm_tmcc = 0
                else:
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"{command} {rpm} {type(rpm)} {cmd_effects}")
                    self.comp_data.rpm_tmcc = 0

            # handle labor
            if command.command in LABOR_SET:
                self.comp_data.labor_tmcc = command.data
            elif cmd_effects & LABOR_SET:
                labor = self._harvest_effect(cmd_effects & LABOR_SET)
                if isinstance(labor, tuple) and len(labor) == 2:
                    self.comp_data.labor_tmcc = labor[1]
                else:
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"{command} {labor} {type(labor)} {cmd_effects}")
                    self.comp_data.speed = 0

            # handle speed
            if command.command in SPEED_SET:
                if command.command.is_alias:
                    # noinspection PyTypeChecker
                    if command.command.alias and len(command.command.alias) > 1:
                        # noinspection PyUnresolvedReferences
                        data = int(command.command.alias[1])
                    else:
                        raise ValueError(f"Invalid speed alias: {command.command.alias}")
                else:
                    data = command.data
                self.comp_data.speed = encode_tmcc_speed(data, self.is_legacy)
                self.update_target_speed()
            elif self.is_synchronized() and cmd_effects & SPEED_SET:
                # ignore impact of direction command while synchronizing state
                # it is only in command stream to set initial state
                speed = self._harvest_effect(cmd_effects & SPEED_SET)
                if isinstance(speed, tuple) and len(speed) > 1:
                    self.comp_data.speed = encode_tmcc_speed(speed[1], self.is_legacy)
                else:
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"{command} {speed} {type(speed)} {cmd_effects}")
                    self.comp_data.speed = 0
                self.update_target_speed()

            if command.command in TARGET_SPEED_SET:
                self.update_target_speed(target_speed=command.data)

            # handle momentum
            if command.command in MOMENTUM_SET:
                if command.command in {
                    TMCC1EngineCommandEnum.MOMENTUM_LOW,
                    TMCC2EngineCommandEnum.MOMENTUM_LOW,
                }:
                    self.comp_data.momentum_tmcc = 0
                if command.command in {
                    TMCC1EngineCommandEnum.MOMENTUM_MEDIUM,
                    TMCC2EngineCommandEnum.MOMENTUM_MEDIUM,
                }:
                    self.comp_data.momentum_tmcc = 3
                if command.command in {
                    TMCC1EngineCommandEnum.MOMENTUM_HIGH,
                    TMCC2EngineCommandEnum.MOMENTUM_HIGH,
                }:
                    self.comp_data.momentum_tmcc = 7
                elif command.command == TMCC2EngineCommandEnum.MOMENTUM:
                    self.comp_data.momentum_tmcc = command.data

            # handle startup/shutdown
            if command.command in STARTUP_SET:
                self._start_stop = command.command
            elif command.command in SHUTDOWN_SET:
                self._start_stop = command.command
            elif cmd_effects & STARTUP_SET:
                startup = self._harvest_effect(cmd_effects & STARTUP_SET)
                if isinstance(startup, CommandDefEnum):
                    self._start_stop = startup
                elif isinstance(startup, tuple) and len(startup) == 2:
                    if startup in TMCC2_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC2_COMMAND_TO_ALIAS_MAP[startup]
                    elif startup in TMCC1_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC1_COMMAND_TO_ALIAS_MAP[startup]
            elif cmd_effects & SHUTDOWN_SET:
                shutdown = self._harvest_effect(cmd_effects & SHUTDOWN_SET)
                if isinstance(shutdown, CommandDefEnum):
                    self._start_stop = shutdown
                elif isinstance(shutdown, tuple) and len(shutdown) == 2:
                    if shutdown in TMCC2_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC2_COMMAND_TO_ALIAS_MAP[shutdown]
                    elif shutdown in TMCC1_COMMAND_TO_ALIAS_MAP:
                        self._start_stop = TMCC1_COMMAND_TO_ALIAS_MAP[shutdown]
            elif command.command == TMCC2R4LCEnum.TRAIN_ADDRESS and self._comp_data:
                self._comp_data.train_tmcc_id = command.data
            elif command.command == TMCC2R4LCEnum.TRAIN_UNIT and self._comp_data:
                self._comp_data.train_unit = command.data
        elif (
            isinstance(command, BaseReq)
            and command.status == 0
            and command.pdi_command
            in {
                PdiCommand.UPDATE_ENGINE_SPEED,
                PdiCommand.UPDATE_TRAIN_SPEED,
            }
        ):
            from ..pdi.base_req import EngineBits

            # noinspection unbound-local-variable
            if self.speed is None and command.is_valid(EngineBits.SPEED):
                self.comp_data.speed = command.speed
        elif (
            isinstance(command, BaseReq)
            and command.pdi_command == PdiCommand.BASE_MEMORY
            and command.status == 0
            and command.data_bytes is not None
        ):
            # process the field update sent by the Base 3
            from .comp_data import BASE_MEMORY_ENGINE_READ_MAP

            tpl = BASE_MEMORY_ENGINE_READ_MAP.get(command.start, None)
            if isinstance(tpl, CompDataHandler):
                setattr(self.comp_data, tpl.field, tpl.from_bytes(command.data_bytes))
        elif isinstance(command, IrdaReq) and command.action == IrdaAction.DATA:
            self._prod_year = command.year
        elif isinstance(command, D4Req):
            if command.action == D4Action.MAP:
                if command.record_no == 0xFFFF:  # delete record
                    # TODO: delete state record
                    pass
                elif command.record_no is not None:
                    self._d4_rec_no = command.record_no
        return UpdateResult.UPDATED

    def cancel_ramps(self, target_speed: int = None, *, reason: str = None, restore_effort: bool = False) -> None:
        from ..comm.comm_buffer import CommBuffer

        self.abort_ramp(reason, target_speed=target_speed, restore_effort=restore_effort)
        CommBuffer.cancel_delayed_requests(self)
        self.update_target_speed(self.speed if target_speed is None else target_speed)
        self.comp_data.rpm_tmcc = 0
        self.comp_data.labor_tmcc = 12
        self._ramping = False

    def _cancelled_target_speed(self, command: L | P) -> int | None:
        """
        The target speed to leave behind when a command stops a ramp. A hard stop - a
        reset, an emergency stop, a direction change or a shutdown - takes the engine to
        a standstill, so its target becomes 0. Anything else that gets this far is
        another controller taking the throttle, so the speed it asked for is the target.
        """
        if command.command in CANCEL_PENDINGS_SET:
            return 0
        speed = self._speed_requested_by(command)
        return speed if speed is not None else self.speed

    @staticmethod
    def _speed_requested_by(command: L | P) -> int | None:
        """The absolute speed a throttle command asks for, resolving the speed aliases."""
        cmd = command.command
        if cmd in TARGET_SPEED_SET:
            return command.data
        if cmd in SPEED_SET:
            if cmd.is_alias:
                # noinspection PyTypeChecker
                alias = cmd.alias
                return int(alias[1]) if alias and len(alias) > 1 else None
            return command.data
        return None

    def sync_target_speed(self, target_speed: int) -> None:
        """
        Record where this engine is actually headed, without arming the ramping flag.

        Every ramp abort path lands here, so a target speed cannot outlive the ramp that
        announced it: a hard stop leaves 0 behind, a foreign throttle command leaves the
        speed that controller asked for, and an ordinary abort leaves the speed the ramp
        had reached.
        """
        if target_speed is None or self.comp_data is None:
            return
        with self._cv:
            self.comp_data.target_speed = encode_tmcc_speed(target_speed, self.comp_data.is_legacy)

    def update_target_speed(self, target_speed: int = None):
        if target_speed is None:
            if self._ramping:
                if self.speed == self.target_speed:
                    self._ramping = False
                    self.comp_data.speed = encode_tmcc_speed(self.speed, self.comp_data.is_legacy)
                    self.comp_data.target_speed = encode_tmcc_speed(self.speed, self.comp_data.is_legacy)
            else:
                # if this PyTrain instance isn't ramping speed, set the target speed to match
                self.comp_data.target_speed = encode_tmcc_speed(self.speed, self.comp_data.is_legacy)
        else:
            self._ramping = target_speed != self.speed
            self.comp_data.target_speed = encode_tmcc_speed(target_speed, self.comp_data.is_legacy)

    def _change_direction(self, new_dir: CommandDefEnum) -> CommandDefEnum:
        if new_dir in {TMCC1EngineCommandEnum.TOGGLE_DIRECTION, TMCC2EngineCommandEnum.TOGGLE_DIRECTION}:
            if isinstance(self.direction, CommandDefEnum):
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

    def as_bytes(self) -> list[bytes]:
        from ..pdi.base_req import BaseReq

        packets = []
        # Encode the engine state as represented on the Base 3;
        if self.tmcc_id <= 99:
            pdi = BaseReq(self.address, PdiCommand.BASE_MEMORY, scope=self.scope, state=self)
        else:
            pdi_cmd = PdiCommand.D4_ENGINE if self.scope == CommandScope.ENGINE else PdiCommand.D4_TRAIN
            pdi = D4Req(self.record_no, pdi_cmd, state=self)
        packets.append(pdi.as_bytes)

        if not self._pdi_source:
            # now encode state not managed by the Base 3, AFAIK
            if isinstance(self._start_stop, CommandDefEnum):
                cmd = TMCC1_PREFIX_TO_AUX_ONE_MAP.get(self._start_stop, None)
                if cmd and isinstance(cmd, tuple):
                    packets.append(
                        CommandReq.build(
                            TMCC1EngineCommandEnum.AUX1_OPTION_ONE, self.address, scope=self.scope
                        ).as_bytes
                    )
                    packets.append(CommandReq.build(cmd[0], self.address, data=cmd[1], scope=self.scope).as_bytes)
                else:
                    packets.append(CommandReq.build(self._start_stop, self.address, scope=self.scope).as_bytes)
            if isinstance(self.smoke_level, CommandDefEnum):
                packets.append(CommandReq.build(self.smoke_level, self.address, scope=self.scope).as_bytes)
            if isinstance(self._direction, CommandDefEnum):
                # the direction state will have encoded in it the syntax (tmcc1 or tmcc2)
                packets.append(CommandReq.build(self._direction, self.address, scope=self.scope).as_bytes)
            # Encodes numeric command packet for special crane engine type
            if self._numeric is not None and isinstance(self._numeric_cmd, CommandDefEnum):
                if self.engine_type in {
                    LOCO_TRACK_CRANE,
                }:
                    packets.append(
                        CommandReq.build(
                            self._numeric_cmd,
                            self.address,
                            data=self._numeric,
                            scope=self.scope,
                        ).as_bytes
                    )
            # Aux state is inferred from Aux1 and Aux2 state
            # if isinstance(self._aux, CommandDefEnum):
            #     packets.append(CommandReq.build(self._aux, self.address).as_bytes)
            if isinstance(self._aux1, CommandDefEnum):
                packets.append(CommandReq.build(self.aux1, self.address).as_bytes)
            if isinstance(self._aux2, CommandDefEnum):
                packets.append(CommandReq.build(self.aux2, self.address).as_bytes)
        return packets

    @property
    def is_rpm(self) -> bool:
        return self.comp_data.engine_type in RPM_TYPE

    @property
    def is_steam(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in STEAM_TYPE

    @property
    def is_electric(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in ELECTRIC_TYPE

    @property
    def is_diesel(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in DIESEL_TYPE

    @property
    def is_crane(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in CRANE_TYPE

    @property
    def is_passenger(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in PASSENGER_TYPE

    @property
    def is_freight(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in FREIGHT_TYPE

    @property
    def is_transformer(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in TRANSFORMER_TYPE

    @property
    def is_acela(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in ACELA_TYPE

    @property
    def has_throttle(self) -> bool:
        return self.comp_data and self.comp_data.engine_type in THROTTLE_TYPE

    @property
    def has_lights(self) -> bool:
        return self.is_diesel or self.is_electric or self.is_steam

    @property
    def speed(self) -> int | None:
        if self.comp_data:
            return decode_tmcc_speed(self.comp_data.speed, self.comp_data.is_legacy)
        else:
            return None

    @property
    def train_tmcc_id(self) -> int:
        return self.comp_data.train_tmcc_id if self.comp_data and self.comp_data.train_tmcc_id != 255 else None

    # noinspection PyTypeChecker
    @property
    def train_unit(self) -> UnitAssignment:
        if self.comp_data and self.comp_data.train_unit != 255:
            return UnitAssignment(self.comp_data.train_unit)
        return None

    @property
    def target_speed(self) -> int:
        return decode_tmcc_speed(self.comp_data.target_speed, self.comp_data.is_legacy)

    @property
    def speed_limit(self) -> int:
        return decode_tmcc_speed(self.comp_data.speed_limit, self.comp_data.is_legacy)

    @property
    def max_speed(self) -> int:
        return decode_tmcc_speed(self.comp_data.max_speed, self.comp_data.is_legacy)

    @property
    def speed_max(self) -> int | None:
        # Determines effective maximum speed from limits with legacy fallback
        if self.max_speed and self.max_speed != 255 and self.speed_limit and self.speed_limit != 255:
            ms = min(self.max_speed, self.speed_limit)
        elif self.speed_limit and self.speed_limit != 255:
            ms = self.speed_limit
        elif self.max_speed and self.max_speed != 255:
            ms = self.max_speed
        else:
            ms = 199 if self.is_legacy is True else 31
        if self.is_legacy is False and ms > 31:
            ms = 31
        return ms

    @property
    def speed_label(self) -> str:
        return self._as_label(self.speed)

    @property
    def speeds(self) -> tuple[int, int, int, int]:
        if self.max_speed is None or self.max_speed == 255:
            if self.is_legacy:
                max_speed = 199
            else:
                max_speed = 31
        else:
            max_speed = self.max_speed
        if self.speed_limit is None or self.speed_limit == 255:
            speed_limit = None
        else:
            speed_limit = self.speed_limit
        return self.speed, self.target_speed, speed_limit, max_speed

    @property
    def rr_speed(self) -> R | None:
        if self.is_legacy:
            return TMCC2RRSpeedsEnum.to_rr_speed(self.speed)
        return TMCC1RRSpeedsEnum.to_rr_speed(self.speed)

    @property
    def bt_int(self) -> int:
        return self.comp_data.bt_id

    # noinspection PyTypeChecker
    @property
    def bt_id(self) -> str:
        if self.bt_int and self.bt_int != 0xFFFF:
            return int.to_bytes(self.bt_int, 2, "big").hex().upper()
        return None

    @property
    def numeric(self) -> int:
        return self._numeric

    @property
    def momentum(self) -> int:
        return self.comp_data.momentum_tmcc

    @property
    def momentum_label(self) -> str:
        return self._as_label(self.momentum)

    @property
    def momentum_text(self) -> str:
        if self.momentum == 0:
            return "Low"
        elif self.momentum == 7:
            return "High"
        elif self.momentum is not None:
            return f"Med {self.momentum}"
        return self._as_label(self.momentum)

    @property
    def fuel_level(self) -> int:
        return self.comp_data.fuel_level

    @property
    def fuel_level_pct(self) -> int:
        if self.fuel_level is not None:
            return int(round((self.fuel_level / 255.0) * 100.0))
        return self.fuel_level

    @property
    def fuel_level_label(self) -> str:
        return self._as_label(self.fuel_level)

    @property
    def water_level(self) -> int:
        return self.comp_data.water_level

    @property
    def water_level_pct(self) -> int:
        if self.water_level is not None:
            return int(round((self.water_level / 255.0) * 100.0))
        return self.water_level

    @property
    def water_level_label(self) -> str:
        return self._as_label(self.water_level)

    @property
    def rpm(self) -> int:
        return self.comp_data.rpm_tmcc if self.is_rpm else 0

    @property
    def rpm_label(self) -> str:
        return self._as_label(self.rpm) if self.is_rpm else "NA"

    @property
    def labor(self) -> int:
        return self.comp_data.labor_tmcc

    @property
    def labor_label(self) -> str:
        return self._as_label(self.labor)

    @property
    def smoke_level(self) -> CommandDefEnum | None:
        if self.comp_data and self.comp_data.smoke != 255:
            return self.comp_data.smoke_tmcc
        return None

    @property
    def smoke_label(self) -> str:
        return SMOKE_LABEL.get(self.smoke_level, None)

    @property
    def smoke_text(self) -> str:
        if isinstance(self.smoke_level, CommandDefEnum):
            if self.smoke_level == TMCC2EffectsControl.SMOKE_MEDIUM:
                return "Med"
            return self.smoke_level.name.replace("SMOKE_", "").title()
        return ""

    @property
    def train_brake(self) -> int:
        return self.comp_data.train_brake_tmcc

    @property
    def train_brake_label(self) -> str:
        return self._as_label(self.train_brake)

    @property
    def control_type(self) -> int:
        return self.comp_data.control_type

    @property
    def control_type_label(self) -> str:
        return CONTROL_TYPE.get(self.control_type, "NA")

    @property
    def control_type_text(self) -> str:
        ct = CONTROL_TYPE.get(self.control_type, "NA")
        if self._is_d4 and ct != "NA":
            ct += " 4D"
        return ct

    @property
    def sound_type(self) -> int:
        return self.comp_data.sound_type

    @property
    def sound_type_label(self) -> str:
        return SOUND_TYPE.get(self.sound_type, "NA")

    @property
    def engine_type(self) -> int:
        return self.comp_data.engine_type

    @property
    def engine_type_enum(self) -> EngineType:
        return EngineType.by_value(self.engine_type, False)

    @property
    def engine_type_label(self) -> str:
        return LOCO_TYPE.get(self.engine_type, "NA")

    @property
    def engine_class(self) -> int:
        return self.comp_data.engine_class

    @property
    def engine_class_label(self) -> str:
        return LOCO_CLASS.get(self.engine_class, "NA")

    @property
    def direction(self) -> CommandDefEnum | None:
        return self._direction

    @property
    def is_forward(self) -> bool:
        return self._direction in {TMCC1EngineCommandEnum.FORWARD_DIRECTION, TMCC2EngineCommandEnum.FORWARD_DIRECTION}

    @property
    def is_reverse(self) -> bool:
        return self._direction in {TMCC1EngineCommandEnum.REVERSE_DIRECTION, TMCC2EngineCommandEnum.REVERSE_DIRECTION}

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
    def record_no_label(self) -> str:
        return f"ID: {self.record_no}" if self.record_no is not None else ""

    @property
    def is_cab1(self) -> bool:
        return self.comp_data and self.comp_data.control_type == CAB1_CONTROL_TYPE

    @property
    def is_tmcc(self) -> bool:
        if self.comp_data:
            return self.comp_data.is_legacy is False
        return self._is_legacy is False or self._is_legacy is None

    @property
    def is_legacy(self) -> bool:
        # Determines legacy status based on scope and type
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} and self.address > 99:
            self._is_legacy = True
        elif self.control_type is not None and self.control_type != 255:
            if self.control_type == LEGACY_CONTROL_TYPE:
                self._is_legacy = True
            else:
                self._is_legacy = False
        elif self._is_legacy is None:
            return False
        return self._is_legacy is True

    @property
    def is_lcs(self) -> bool:
        return False

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        for elem in [
            "bt_id",
            "fuel_level",
            "labor",
            "max_speed",
            "momentum",
            "record_no",
            "rpm",
            "speed",
            "speed_limit",
            "target_speed",
            "train_brake",
            "water_level",
            "year",
        ]:
            if hasattr(self, elem):
                val = getattr(self, elem)
                d[elem] = val if val is not None and val != 255 else None
            elif self.comp_data and hasattr(self.comp_data, "_" + elem):
                d[elem] = getattr(self.comp_data, elem)
        d["direction"] = self.direction.name.lower() if self.direction else None
        d["smoke"] = self.smoke_level.name.lower() if self.smoke_level else None
        d["control"] = self.control_type_label.lower() if self.control_type is not None else None
        d["sound_type"] = self.sound_type_label.lower() if self.sound_type is not None else None
        d["engine_type"] = self.engine_type_label.lower() if self.engine_type is not None else None
        d["engine_class"] = self.engine_class_label.lower() if self.engine_class is not None else None
        return d


class TrainState(EngineState, LcsProxyState):
    from .components import ConsistComponent

    @classmethod
    def _csv_headers(cls, include_state: bool = False) -> list[str]:
        cols = super()._csv_headers(include_state=include_state)
        cols.extend(["head", "engines", "cars", "accessories"])
        return cols

    def __init__(self, scope: CommandScope = CommandScope.TRAIN) -> None:
        if scope != CommandScope.TRAIN:
            raise ValueError(f"Invalid scope: {scope}, expected {CommandScope.TRAIN.name}")
        super().__init__(scope)
        # TODO: FIXME!!
        # hard code TMCC2, for now
        self._is_legacy: bool = True

    def __repr__(self) -> str:
        if self.is_bpc2:
            return super(EngineState, self).__repr__()
        return super().__repr__()

    def __contains__(self, item: object) -> bool:
        if isinstance(item, EngineState) and item.scope == CommandScope.ENGINE and self.consist_components:
            for comp in self.consist_components:
                if comp.tmcc_id == item.tmcc_id:
                    return True
        return False

    def as_csv(self, include_state: bool = False) -> dict[str, str | int | None]:
        data = super().as_csv(include_state=include_state)
        data["head"] = self.head_tmcc_id
        data["engines"] = self.num_engines
        data["cars"] = self.num_train_linked
        data["accessories"] = self.num_accessories

        return data

    def _update_state(self, command: L | P) -> UpdateResult:
        from ..pdi.bpc2_req import Bpc2Req

        # if isinstance(command, CommandReq) and command.command in {TMCC2EngineCommandEnum.CLEAR_CONSIST}:
        #     from .component_state_store import ComponentStateStore
        #
        #     ComponentStateStore.delete_state(self)
        if isinstance(command, Bpc2Req):
            LcsProxyState._update_state(self, command)
            if command.action in {Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                if command.state:
                    self._aux1 = TMCC2.AUX1_ON
                    self._aux2 = TMCC2.AUX2_OFF
                    self._aux = TMCC2.AUX1_OPTION_ONE
                else:
                    self._aux1 = TMCC2.AUX1_OFF
                    self._aux2 = TMCC2.AUX2_OFF
                    self._aux = TMCC2.AUX2_OPTION_ONE
        return super()._update_state(command)

    @property
    def payload(self) -> str:
        if self.is_bpc2:
            return f"Block Power Port {self.port}: {' ON' if self._aux == TMCC2.AUX1_OPTION_ONE else 'OFF'}"
        return super().payload

    @property
    def consist_flags(self) -> int:
        return self.comp_data.consist_flags

    @property
    def consist_components(self) -> List[ConsistComponent]:
        return self.comp_data.consist_comps

    @property
    def head(self) -> EngineState | None:
        from .component_state_store import ComponentStateStore

        head_id = self.head_tmcc_id
        if head_id:
            return ComponentStateStore.get_state(CommandScope.ENGINE, head_id, False)
        return None

    @property
    def head_tmcc_id(self) -> int | None:
        if self.consist_components:
            for comp in self.consist_components:
                if comp.is_head:
                    return comp.tmcc_id
        return None

    @property
    def link_tmcc_id(self) -> int | None:
        if self.consist_components:
            for comp in self.consist_components:
                if comp.is_train_link:
                    return comp.tmcc_id
        return None

    @property
    def engine_ids(self) -> list[int] | None:
        if self.consist_components:
            ids = []
            for comp in self.consist_components:
                if not comp.is_train_link and not comp.is_accessory:
                    ids.append(comp.tmcc_id)
            return ids
        return None

    @property
    def link_tmcc_ids(self) -> list[int] | None:
        if self.consist_components:
            ids = []
            for comp in self.consist_components:
                if comp.is_train_link:
                    ids.append(comp.tmcc_id)
            return ids
        return None

    @property
    def accessory_ids(self) -> list[int] | None:
        if self.consist_components:
            ids = []
            for comp in self.consist_components:
                if comp.is_accessory:
                    ids.append(comp.tmcc_id)
            return ids
        return None

    @property
    def num_engines(self) -> int:
        return len(self.engine_ids) if self.engine_ids else 0

    @property
    def num_train_linked(self) -> int:
        return len(self.link_tmcc_ids) if self.link_tmcc_ids else 0

    @property
    def num_accessories(self) -> int:
        return len(self.accessory_ids) if self.accessory_ids else 0

    @property
    def is_lcs(self) -> bool:
        return True if self.is_bpc2 else super().is_lcs

    @property
    def moniker(self) -> str:
        if self.is_bpc2:
            return LcsProxyState.moniker.fget(self)
        else:
            return EngineState.moniker.fget(self)

    @property
    def is_rpm(self) -> bool:
        return self.head.is_rpm if self.head else False

    @property
    def is_steam(self) -> bool:
        return self.head.is_steam if self.head else False

    @property
    def is_electric(self) -> bool:
        return self.head.is_electric if self.head else False

    @property
    def is_diesel(self) -> bool:
        return self.head.is_diesel if self.head else False

    @property
    def is_crane(self) -> bool:
        return self.head.is_crane if self.head else False

    @property
    def is_passenger(self) -> bool:
        return self.head.is_passenger if self.head else False

    @property
    def is_freight(self) -> bool:
        return self.head.is_freight if self.head else False

    # Note: we use comp_data to determine Transformer type by
    # deferring to the parent class

    @property
    def is_acela(self) -> bool:
        return self.head.is_acela if self.head else False

    @property
    def has_throttle(self) -> bool:
        return self.head.has_throttle if self.head else False

    @property
    def has_lights(self) -> bool:
        return self.head.has_lights if self.head else False

    def get_consist_component(self, tmcc_id: int) -> ConsistComponent | None:
        if self.consist_components:
            for c in self.consist_components:
                if c.tmcc_id == tmcc_id:
                    return c
        return None

    @property
    def is_legacy(self) -> bool:
        if self.is_lcs_component or self._is_legacy is True:
            return True
        return super().is_legacy

    @property
    def is_tmcc(self) -> bool:
        if self.is_lcs_component:
            return False
        return super().is_tmcc

    def as_bytes(self) -> list[bytes]:
        packets = []
        if self.is_lcs_component:
            return [LcsProxyState.as_bytes(self)]
        packets.extend(super().as_bytes())
        return packets

    def as_dict(self) -> Dict[str, Any]:
        d = super().as_dict()
        d["flags"] = self.consist_flags
        d["components"] = {c.tmcc_id: c.info for c in self.consist_components}
        return d


SCOPE_TO_STATE_MAP.update({CommandScope.ENGINE: EngineState})
SCOPE_TO_STATE_MAP.update({CommandScope.TRAIN: TrainState})
