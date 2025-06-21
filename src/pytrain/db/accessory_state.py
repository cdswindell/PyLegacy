#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from typing import Any, Dict, cast

from ..pdi.amc2_req import Amc2Req
from ..pdi.asc2_req import Asc2Req
from ..pdi.bpc2_req import Bpc2Req
from ..pdi.constants import Amc2Action, Asc2Action, Bpc2Action, IrdaAction, PdiCommand
from ..pdi.irda_req import IrdaReq
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum as Aux
from ..protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum
from .comp_data import CompDataMixin
from .component_state import SCOPE_TO_STATE_MAP, L, P, TmccState, log


class AccessoryState(TmccState):
    def __init__(self, scope: CommandScope = CommandScope.ACC) -> None:
        if scope != CommandScope.ACC:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._first_pdi_command = None
        self._first_pdi_action = None
        self._pdi_config = None
        self._last_aux1_opt1 = None
        self._last_aux2_opt1 = None
        self._aux1_state: Aux | None = None
        self._aux2_state: Aux | None = None
        self._aux_state: Aux | None = None
        self._block_power = False
        self._sensor_track = False
        self._asc2 = False
        self._amc2 = False
        self._pdi_source = False
        self._number: int | None = None

    @property
    def payload(self) -> str:
        aux1 = aux2 = aux_num = ""
        if self._block_power:
            aux = f"Block Power {'ON' if self.aux_state == Aux.AUX1_OPT_ONE else 'OFF'}"
        elif self._sensor_track:
            aux = "Sensor Track"
        elif self._amc2:
            if self._pdi_config:
                at = f"Type: {self._pdi_config.access_type.label}"
                m1 = f"{self._pdi_config.motor1}"
                m2 = f"{self._pdi_config.motor2}"
                l1 = f"{self._pdi_config.lamp1}"
                aux = f"AMC 2 {at} {m1} {m2} {l1}"
            else:
                aux = "AMC 2"
        else:
            if self.is_lcs_component:
                aux = "Asc2 " + "ON" if self._aux_state == Aux.AUX1_OPT_ONE else "OFF"
            else:
                if self.aux_state == Aux.AUX1_OPT_ONE:
                    aux = "Aux 1"
                elif self.aux_state == Aux.AUX2_OPT_ONE:
                    aux = "Aux 2"
                else:
                    aux = "Unknown"
                aux1 = f" Aux1: {self.aux1_state.name if self.aux1_state is not None else 'Unknown'}"
                aux2 = f" Aux2: {self.aux2_state.name if self.aux2_state is not None else 'Unknown'}"
                aux_num = f" Aux Num: {self._number if self._number is not None else 'NA'}"
        return f"{aux}{aux1}{aux2}{aux_num}"

    # noinspection DuplicatedCode
    def update(self, command: L | P) -> None:
        if command:
            with self._cv:
                super().update(command)
                if isinstance(command, CompDataMixin) and command.is_comp_data_record:
                    self._update_comp_data(command.comp_data)
                elif isinstance(command, CommandReq):
                    if command.command != Aux.SET_ADDRESS:
                        if command.command == TMCC1HaltCommandEnum.HALT:
                            self._aux1_state = Aux.AUX1_OFF
                            self._aux2_state = Aux.AUX2_OFF
                            self._aux_state = Aux.AUX2_OPT_ONE
                            self._number = None
                        else:
                            if not self._pdi_source:
                                if command.command in {Aux.AUX1_OPT_ONE, Aux.AUX2_OPT_ONE}:
                                    self._aux_state = command.command
                                if command.command == Aux.AUX1_OPT_ONE:
                                    if self.time_delta(self._last_updated, self._last_aux1_opt1) > 1:
                                        self._aux1_state = self.update_aux_state(
                                            self._aux1_state,
                                            Aux.AUX1_ON,
                                            Aux.AUX1_OPT_ONE,
                                            Aux.AUX1_OFF,
                                        )
                                    self._last_aux1_opt1 = self.last_updated
                                elif command.command in {Aux.AUX1_ON, Aux.AUX1_OFF, Aux.AUX1_OPT_TWO}:
                                    self._aux1_state = command.command
                                    self._last_aux1_opt1 = self.last_updated
                                elif command.command == Aux.AUX2_OPT_ONE:
                                    if self.time_delta(self._last_updated, self._last_aux2_opt1) > 1:
                                        self._aux2_state = self.update_aux_state(
                                            self._aux2_state,
                                            Aux.AUX2_ON,
                                            Aux.AUX2_OPT_ONE,
                                            Aux.AUX2_OFF,
                                        )
                                    self._last_aux2_opt1 = self.last_updated
                                elif command.command in {Aux.AUX2_ON, Aux.AUX2_OFF, Aux.AUX2_OPT_TWO}:
                                    self._aux2_state = command.command
                                    self._last_aux2_opt1 = self.last_updated
                            if command.command == Aux.NUMERIC:
                                self._number = command.data
                elif isinstance(command, Asc2Req) or isinstance(command, Bpc2Req) or isinstance(command, Amc2Req):
                    if self._first_pdi_command is None:
                        self._first_pdi_command = command.command
                    if self._first_pdi_action is None:
                        self._first_pdi_action = command.action
                    if command.is_config:
                        self._pdi_config = command
                    if command.action in {Asc2Action.CONTROL1, Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                        self._pdi_source = True
                        if command.action in {Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                            self._block_power = True
                            self._asc2 = False
                        else:
                            self._asc2 = True
                            self._block_power = False
                        if command.state == 1:
                            self._aux1_state = Aux.AUX1_ON
                            self._aux2_state = Aux.AUX2_ON
                            self._aux_state = Aux.AUX1_OPT_ONE
                        else:
                            self._aux1_state = Aux.AUX1_OFF
                            self._aux2_state = Aux.AUX2_OFF
                            self._aux_state = Aux.AUX2_OPT_ONE
                    elif isinstance(command, Amc2Req):
                        self._pdi_source = True
                        self._amc2 = True
                elif isinstance(command, IrdaReq):
                    if self._first_pdi_command is None:
                        self._first_pdi_command = command.command
                    if self._first_pdi_action is None:
                        self._first_pdi_action = command.action
                    self._sensor_track = True
                self.changed.set()
                self._cv.notify_all()

    @property
    def is_known(self) -> bool:
        return (
            self._aux_state is not None
            or self._aux1_state is not None
            or self._aux2_state is not None
            or self._number is not None
        )

    @property
    def is_power_district(self) -> bool:
        return self._block_power

    @property
    def is_sensor_track(self) -> bool:
        return self._sensor_track

    @property
    def is_asc2(self) -> bool:
        return self._asc2

    @property
    def is_amc2(self) -> bool:
        return self._amc2

    @property
    def is_lcs_component(self) -> bool:
        return self._pdi_source

    @property
    def aux_state(self) -> Aux:
        return self._aux_state

    @property
    def is_aux_on(self) -> bool:
        return self._aux_state == Aux.AUX1_OPT_ONE

    @property
    def is_aux_off(self) -> bool:
        return self._aux_state == Aux.AUX2_OPT_ONE

    @property
    def aux1_state(self) -> Aux:
        return self._aux1_state

    @property
    def aux2_state(self) -> Aux:
        return self._aux2_state

    @property
    def value(self) -> int:
        return self._number

    def as_bytes(self) -> bytes:
        if self.comp_data is None:
            self.initialize(self.scope, self.address)
        byte_str = super().as_bytes()
        if self._sensor_track:
            byte_str += IrdaReq(self.address, PdiCommand.IRDA_RX, IrdaAction.INFO, scope=CommandScope.ACC).as_bytes
        elif self.is_lcs_component:
            if isinstance(self._first_pdi_action, Asc2Action):
                byte_str += Asc2Req(
                    self.address,
                    self._first_pdi_command,
                    cast(Asc2Action, self._first_pdi_action),
                    values=1 if self._aux_state == Aux.AUX1_OPT_ONE else 0,
                ).as_bytes
            elif isinstance(self._first_pdi_action, Bpc2Action):
                byte_str += Bpc2Req(
                    self.address,
                    self._first_pdi_command,
                    cast(Bpc2Action, self._first_pdi_action),
                    state=1 if self._aux_state == Aux.AUX1_OPT_ONE else 0,
                ).as_bytes
            elif isinstance(self._first_pdi_action, Amc2Action) and isinstance(self._pdi_config, Amc2Req):
                byte_str += self._pdi_config.as_bytes
            else:
                log.error(f"State req for lcs device: {self._first_pdi_command.name} {self._first_pdi_action.name}")
        else:
            if self._aux_state is not None:
                byte_str += CommandReq.build(self.aux_state, self.address).as_bytes
            if self._aux1_state is not None:
                byte_str += CommandReq.build(self.aux1_state, self.address).as_bytes
            if self._aux2_state is not None:
                byte_str += CommandReq.build(self.aux2_state, self.address).as_bytes
        return byte_str

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        if self._sensor_track:
            d["type"] = "sensor track"
        elif self._block_power:
            d["type"] = "power district"
            d["block"] = "on" if self._aux_state == Aux.AUX1_OPT_ONE else "off"
        else:
            d["type"] = "accessory"
            d["aux"] = self._aux_state.name.lower() if self._aux_state else None
            d["aux1"] = self.aux1_state.name.lower() if self.aux1_state else None
            d["aux2"] = self.aux2_state.name.lower() if self.aux2_state else None
        return d


SCOPE_TO_STATE_MAP.update({CommandScope.ACC: AccessoryState})
