from __future__ import annotations

import abc
from abc import ABC
from typing import List, TypeVar

from src.pdi.constants import PdiCommand, ALL_STATUS, PDI_SOP, PDI_EOP, Ser2Action, IrdaAction, PdiAction, ALL_INFO
from src.pdi.constants import ALL_SETs, ALL_IDENTIFY, ALL_FIRMWARE
from src.pdi.pdi_req import PdiReq
from src.protocol.constants import CommandScope

T = TypeVar("T", bound=PdiAction)


class LcsReq(PdiReq, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self, data: bytes | int, pdi_command: PdiCommand = None, action: T = None, ident: int | None = None
    ) -> None:
        super().__init__(data, pdi_command)
        self._board_id = self._num_ids = self._model = self._uart0 = self._uart1 = self._base_type = None
        self._dc_volts: float | None = None
        self._action: T = action
        self._version = self._revision = self._sub_revision = None
        if isinstance(data, bytes):
            if self._pdi_command.is_lcs is False:
                raise ValueError(f"Invalid PDI LCS Request: {data}")
            self._tmcc_id = self._data[1]
            self._action_byte = self._data[2]
            self._ident = None
            payload = self._data[3:]
            payload_len = len(payload)
            if self._is_action(ALL_STATUS):
                self._board_id = payload[0] if payload_len > 0 else None
                self._num_ids = payload[1] if payload_len > 1 else None
                self._model = payload[2] if payload_len > 2 else None
                self._uart0 = payload[3] if payload_len > 3 else None
                self._uart1 = payload[4] if payload_len > 4 else None
                self._base_type = payload[5] if payload_len > 5 else None
                self._dc_volts = payload[6] / 10.0 if payload_len > 6 else None
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
            self._tmcc_id = int(data) if data else 0
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

    def __repr__(self) -> str:
        if self.payload is not None:
            payload = " " + self.payload
        elif self._data is not None:
            payload = f" (0x{self._data.hex()})" if self._data else ""
        else:
            payload = ""

        return f"[PDI {self._pdi_command.name} ID: {self._tmcc_id} {self.action.name}{payload}]"

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @property
    def ident(self) -> int:
        return self._ident

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += self.action.as_bytes
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str

    @property
    def payload(self) -> str | None:
        if self._is_action(ALL_STATUS) and self.pdi_command.name.endswith("_RX"):
            return (
                f"Board ID: {self.board_id} Num IDs: {self.num_ids} Model: {self.model} "
                f"DC Volts: {self.dc_volts} ({self.packet})"
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
    @abc.abstractmethod
    def action(self) -> T: ...


class Ser2Req(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.SER2_GET,
        action: Ser2Action = Ser2Action.CONFIG,
        ident: int | None = None,
    ) -> None:
        super().__init__(data, pdi_command, action, ident)
        if isinstance(data, bytes):
            self._action = Ser2Action(self._action_byte)

    @property
    def action(self) -> Ser2Action:
        return self._action

    @property
    def payload(self) -> str | None:
        return super().payload

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM


class IrdaReq(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.IRDA_GET,
        action: IrdaAction = IrdaAction.CONFIG,
        ident: int | None = None,
    ) -> None:
        super().__init__(data, pdi_command, action, ident)
        if isinstance(data, bytes):
            self._action = IrdaAction(self._action_byte)

    @property
    def action(self) -> IrdaAction:
        return self._action

    @property
    def payload(self) -> str | None:
        return super().payload

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM
