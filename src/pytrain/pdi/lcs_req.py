from __future__ import annotations

import abc
from abc import ABC
from typing import Dict, List, TypeVar

from ..pdi.constants import (
    ALL_FIRMWARE,
    ALL_IDENTIFY,
    ALL_INFO,
    ALL_STATUS,
    ALL_SETs,
    PdiAction,
    PdiCommand,
    Ser2Action,
)
from ..pdi.pdi_req import PdiReq

T = TypeVar("T", bound=PdiAction)

BASE_TYPE_MAP: Dict[int, str] = {
    0: "Unknown",
    1: "Legacy",
    2: "Base1-L",
    3: "No Base",
    4: "No Support",
}

UART_MAP: Dict[int, str] = {
    0: "Unknown",
    1: ">Base<",
    2: "->Base",
    3: "Base->",
}

ERROR_CODE_MAP: Dict[int, str] = {
    1: "PDI command not supported",
    2: "Action not supported",
    3: "Data field with missing parameter(s) - missing bytes before EOP",
    4: "Data field with extra parameter(s) - extra bytes before EOP",
    5: "Data field with invalid contents",
    0xFF: "Undefined error",
}


class LcsReq(PdiReq, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = None,
        action: T = None,
        ident: int | None = None,
        error: bool = False,
    ) -> None:
        super().__init__(data, pdi_command)
        self._board_id = self._num_ids = self._model = self._uart0 = self._uart1 = self._base_type = None
        self._error_code = None
        self._dc_volts: float | None = None
        self._action: T = action
        self._version = self._revision = self._sub_revision = None
        self._error = error
        if isinstance(data, bytes):
            if not self.is_lcs:
                raise AttributeError(f"Invalid PDI LCS Request: {data}")
            self.tmcc_id = self._data[1]
            self._action_byte = self._data[2]
            if self._action_byte & 0x80 == 0x80:
                self._error = True
                self._action_byte &= 0x7F
            self._ident = None
            payload = self._data[3:]
            payload_len = len(payload)
            if self.is_error:
                self._error_code = payload[0] if payload_len > 0 else None
            if self._is_action(ALL_STATUS):
                self._board_id = payload[0] if payload_len > 0 else None
                self._num_ids = payload[1] if payload_len > 1 else None
                self._model = payload[2] if payload_len > 2 else None
                self._uart0 = payload[3] if payload_len > 3 else None
                self._uart1 = payload[4] if payload_len > 4 else None
                self._base_type = payload[5] if payload_len > 5 else None
                self._dc_volts = payload[6] / 10.0 if payload_len > 6 else None
                self._ec0 = payload[7] if payload_len > 7 else None
                self._ec1 = payload[8] if payload_len > 8 else None
                self._ec2 = payload[9] if payload_len > 9 else None
                self._ec3 = payload[10] if payload_len > 10 else None
                self._ec4 = payload[11] if payload_len > 11 else None
                self._ec5 = payload[12] if payload_len > 12 else None
                self._ec6 = payload[13] if payload_len > 13 else None
                self._ec7 = payload[14] if payload_len > 14 else None
                self._ec8 = payload[15] if payload_len > 15 else None
                self._ec9 = payload[16] if payload_len > 16 else None
                self._ec10 = payload[17] if payload_len > 17 else None
                self._ec11 = payload[18] if payload_len > 18 else None
                self._ec12 = payload[19] if payload_len > 19 else None
                self._ec13 = payload[20] if payload_len > 20 else None
                self._ec14 = payload[21] if payload_len > 21 else None
                self._ec15 = payload[22] if payload_len > 22 else None
            if self._is_action(ALL_FIRMWARE):
                self._version = payload[0] if payload_len > 0 else None
                self._revision = payload[1] if payload_len > 1 else None
                self._sub_revision = payload[2] if payload_len > 2 else None
            if self._is_action(ALL_INFO):
                self._board_id = payload[0] if payload_len > 0 else None
                self._num_ids = payload[1] if payload_len > 1 else None
                self._model = payload[2] if payload_len > 2 else None
                self._dc_volts = payload[3] / 10.0 if payload_len > 3 else None
        else:
            self._action_byte = action.bits if action else 0
            self.tmcc_id = int(data) if data else 0
            self._ident = ident

    def _is_action(self, enums: List[T]) -> bool:
        return self.action in enums

    def _is_command(self, enums: List[PdiCommand]) -> bool:
        for enum in enums:
            if enum == self.pdi_command:
                return True
        return False

    @property
    def is_lcs(self) -> bool:
        return True

    @property
    def is_error(self) -> bool:
        return self._error

    @property
    def error(self) -> str:
        if self.is_error and self._error_code in ERROR_CODE_MAP:
            return ERROR_CODE_MAP[self._error_code]
        else:
            return "None"

    @property
    def board_id(self) -> int | None:
        return self._board_id

    @property
    def num_ids(self) -> int | None:
        return self._num_ids

    @property
    def model(self) -> int | None:
        return self._model

    @property
    def uart0(self) -> int | None:
        return self._uart0

    @property
    def uart1(self) -> int | None:
        return self._uart1

    @property
    def dc_volts(self) -> float | None:
        return self._dc_volts

    @property
    def base_type(self) -> str | None:
        if self._base_type in BASE_TYPE_MAP:
            return BASE_TYPE_MAP[self._base_type]
        return "NA"

    @staticmethod
    def uart_mode(uart: int) -> str | None:
        if uart in UART_MAP:
            return UART_MAP[uart]
        return "NA"

    def __repr__(self) -> str:
        if self.payload is not None:
            payload = " " + self.payload
        elif self._data is not None:
            payload = f" (0x{self._data.hex()})" if self._data else ""
        else:
            payload = ""

        if self.is_error:
            error = f" Error: {self.error}"
        else:
            error = ""

        return f"[PDI {self._pdi_command.name} {self.action.name} ID: {self.tmcc_id}{error}{payload}]"

    @property
    def ident(self) -> int:
        return self._ident

    @property
    def payload(self) -> str | None:
        if self.is_error:
            return super().payload
        elif self._is_action(ALL_STATUS) and self.pdi_command.name.endswith("_RX"):
            return (
                f"Board ID: {self.board_id} Num IDs: {self.num_ids} Model: {self.model} DC Volts: {self.dc_volts} "
                f"Base: {self.base_type} UART0: {self.uart_mode(self.uart0)} UART1: {self.uart_mode(self.uart1)} "
                f"\n({self.packet})"
            )
        elif self._is_action(ALL_INFO) and self.pdi_command.name.endswith("_RX"):
            return (
                f"Board ID: {self.board_id} Num IDs: {self.num_ids} Model: {self.model} "
                f"DC Volts: {self.dc_volts} ({self.packet})"
            )
        elif self._is_action(ALL_FIRMWARE) and self.pdi_command.name.endswith("_RX"):
            return f"Firmware {self._version}.{self._revision}.{self._sub_revision}"
        elif self._is_action(ALL_IDENTIFY):
            if self._is_command(ALL_SETs):
                return f"Ident: {self.ident} ({self.packet})"
        return super().payload

    @property
    def action(self) -> T:
        return self._action


class Ser2Req(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.SER2_GET,
        action: Ser2Action = Ser2Action.CONFIG,
        ident: int | None = None,
        error: bool = False,
    ) -> None:
        super().__init__(data, pdi_command, action, ident, error)
        if isinstance(data, bytes):
            self._action = Ser2Action(self._action_byte)
