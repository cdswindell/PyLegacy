#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from typing import Any, Dict

from .comp_data import CompDataMixin
from .component_state import SCOPE_TO_STATE_MAP, L, LcsProxyState, P, TmccState
from ..pdi.amc2_req import Amc2Lamp, Amc2Motor, Amc2Req
from ..pdi.asc2_req import Asc2Req
from ..pdi.bpc2_req import Bpc2Req
from ..pdi.constants import Asc2Action, Bpc2Action
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum as Aux
from ..protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum


class AccessoryState(TmccState, LcsProxyState):
    def __init__(self, scope: CommandScope = CommandScope.ACC) -> None:
        if scope != CommandScope.ACC:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._last_aux1_opt1 = None
        self._last_aux2_opt1 = None
        self._aux1_state: Aux | None = None
        self._aux2_state: Aux | None = None
        self._aux_state: Aux | None = None
        self._number: int | None = None

    @property
    def payload(self) -> str:
        aux1 = aux2 = aux_num = ""
        if self.is_bpc2:
            aux = f"Bpc2 Port {self.port}: {' ON' if self.aux_state == Aux.AUX1_OPT_ONE else 'OFF'}"
        elif self.is_sensor_track:
            aux = "Sensor Track" if self.is_road_name and not self.road_name.startswith("Sensor Track") else ""
        elif self.is_amc2:
            if self._config_req:
                at = f"Type: {self._config_req.access_type.label}"
                m1 = f"{self._config_req.motor1}"
                m2 = f"{self._config_req.motor2}"
                l1 = f"{self._config_req.lamp1}"
                l2 = f"{self._config_req.lamp2}"
                l3 = f"{self._config_req.lamp3}"
                l4 = f"{self._config_req.lamp4}"
                aux, aux1, aux2, aux_num = self._get_aux_state()
                aux = f"Amc2 {at} {m1} {m2} {l1} {l2} {l3} {l4} {aux}"
            else:
                aux = "Amc2"
        else:
            if self.is_asc2:
                aux = f"Asc2 Port {self.port}: {' ON' if self._aux_state == Aux.AUX1_OPT_ONE else 'OFF'}"
            else:
                aux, aux1, aux2, aux_num = self._get_aux_state()
        return f"{aux}{aux1}{aux2}{aux_num}"

    def _get_aux_state(self) -> tuple[str, str, str, str]:
        if self.aux_state == Aux.AUX1_OPT_ONE:
            aux = "Aux: Aux 1"
        elif self.aux_state == Aux.AUX2_OPT_ONE:
            aux = "Aux: Aux 2"
        else:
            aux = "Aux: Unknown"
        aux1 = f" Aux1: {self.aux1_state.name if self.aux1_state is not None else 'Unknown'}"
        aux2 = f" Aux2: {self.aux2_state.name if self.aux2_state is not None else 'Unknown'}"
        aux_num = f" Aux Num: {self._number if self._number is not None else 'NA'}"
        return aux, aux1, aux2, aux_num

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
                            if self.is_amc2:
                                self.extract_state_from_req(command)
                elif isinstance(command, Asc2Req) or isinstance(command, Bpc2Req) or isinstance(command, Amc2Req):
                    if command.action in {Asc2Action.CONTROL1, Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                        if command.state == 1:
                            self._aux1_state = Aux.AUX1_ON
                            self._aux2_state = Aux.AUX2_ON
                            self._aux_state = Aux.AUX1_OPT_ONE
                        else:
                            self._aux1_state = Aux.AUX1_OFF
                            self._aux2_state = Aux.AUX2_OFF
                            self._aux_state = Aux.AUX2_OPT_ONE
                    elif isinstance(command, Amc2Req):
                        self.extract_state_from_req(command)
                self.changed.set()
                self._cv.notify_all()

    @property
    def is_known(self) -> bool:
        return (
            self._aux_state is not None
            or self._aux1_state is not None
            or self._aux2_state is not None
            or self._number is not None
            or self._config_req is not None
        )

    @property
    def aux_state(self) -> Aux:
        return self._aux_state

    @property
    def is_aux_on(self) -> bool:
        return self._aux_state == Aux.AUX1_OPT_ONE

    @property
    def is_aux1_on(self) -> bool:
        return self._aux1_state == Aux.AUX1_ON

    @property
    def is_aux2_on(self) -> bool:
        return self._aux2_state == Aux.AUX2_ON

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

    @property
    def number(self) -> int:
        return self._number

    @property
    def motor1(self) -> Amc2Motor:
        return self.get_motor(1)

    @property
    def motor2(self) -> Amc2Motor:
        return self.get_motor(2)

    def get_motor(self, num: int) -> Amc2Motor | None:
        if self.is_amc2 and self._config_req:
            return self._config_req.get_motor(num)
        return None

    @property
    def lamp1(self) -> Amc2Lamp:
        return self.get_lamp(1)

    @property
    def lamp2(self) -> Amc2Lamp:
        return self.get_lamp(2)

    @property
    def lamp3(self) -> Amc2Lamp:
        return self.get_lamp(3)

    @property
    def lamp4(self) -> Amc2Lamp:
        return self.get_lamp(4)

    def get_lamp(self, num: int) -> Amc2Lamp | None:
        if self.is_amc2 and self._config_req:
            return self._config_req.get_lamp(num)
        return None

    def is_motor_on(self, motor: Amc2Motor) -> bool:
        if motor:
            if self._config_req_count == 1:
                return motor.speed > 0 and motor.restore_state
            else:
                return motor.speed > 0 and motor.state
        return False

    def extract_state_from_req(self, req: L | P):
        if isinstance(req, Amc2Req):
            if isinstance(self._config_req, Amc2Req):
                self._config_req.update_config(req)
                if req.is_config:
                    self._aux1_state = Aux.AUX1_ON if self.is_motor_on(req.motor1) else Aux.AUX1_OFF
                    self._aux2_state = Aux.AUX2_ON if self.is_motor_on(req.motor2) else Aux.AUX2_OFF
                    self._aux_state = (
                        Aux.AUX1_OPT_ONE
                        if self._aux1_state == Aux.AUX1_ON or self._aux2_state == Aux.AUX2_ON
                        else Aux.AUX2_OPT_ONE
                    )
        elif isinstance(req, CommandReq):
            if req.command == Aux.NUMERIC:
                if req.data and 1 <= req.data <= 6:
                    self._number = req.data

    def as_bytes(self) -> bytes:
        if self.comp_data is None:
            self.initialize(self.scope, self.address)
        byte_str = super().as_bytes()
        if self.is_lcs_component:
            if self._config_req:
                byte_str += self._config_req.as_bytes
            if self._control_req:
                byte_str += self._control_req.as_bytes
            if self._firmware_req:
                byte_str += self._firmware_req.as_bytes
            if self._info_req:
                byte_str += self._info_req.as_bytes
            if isinstance(self._config_req, Amc2Req):
                if self.number:
                    byte_str += CommandReq(Aux.NUMERIC, self.address, self.number).as_bytes
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
        if self.is_sensor_track:
            d["type"] = "sensor track"
        elif self.is_bpc2:
            d["type"] = "power district"
            d["block"] = "on" if self._aux_state == Aux.AUX1_OPT_ONE else "off"
        else:
            d["type"] = "accessory"
            d["aux"] = self._aux_state.name.lower() if self._aux_state else None
            d["aux1"] = self.aux1_state.name.lower() if self.aux1_state else None
            d["aux2"] = self.aux2_state.name.lower() if self.aux2_state else None
        return d


SCOPE_TO_STATE_MAP.update({CommandScope.ACC: AccessoryState})
