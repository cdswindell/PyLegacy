from __future__ import annotations

from typing import Dict

from src.pdi.constants import PdiCommand, IrdaAction
from src.pdi.lcs_req import LcsReq
from src.protocol.constants import CommandScope

SEQUENCE_MAP: Dict[int, str] = {
    0: "None",
    1: "Crossing gate signal/None",
    2: "None/Crossing gate signal",
    3: "Bell/None",
    4: "None/Bell",
    5: "Journey Begin/Journey End",
    6: "Journey End/Journey Begin",
    7: "Slow Speed/Normal Speed",
    8: "Normal Speed/Slow Speed",
    9: "Recording",
}

STATUS_MAP: Dict[int, str] = {
    0: "No Recording",
    1: "Idle",
    2: "Playback...",
    3: "Armed...",
    4: "Recording...",
}


class IrdaReq(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.IRDA_GET,
        action: IrdaAction = IrdaAction.CONFIG,
        scope: CommandScope = CommandScope.SYSTEM,
        ident: int | None = None,
    ) -> None:
        self._debug = self._sequence = self._loco_rl = self._loco_lr = None
        self._valid1 = self._valid2 = self._dir = self._engine_id = self._train_id = self._status = None
        self._fuel = self._water = self._burn = self._fwb_mask = None

        super().__init__(data, pdi_command, action, ident)
        if isinstance(data, bytes):
            self._action = IrdaAction(self._action_byte)
            data_len = len(self._data)
            if self._action == IrdaAction.INFO:
                self._scope = CommandScope.ACC
            elif self._action == IrdaAction.CONFIG:
                self._debug = self._data[4] if data_len > 4 else None
                self._sequence = self._data[7] if data_len > 7 else None
                self._loco_rl = self._data[8] if data_len > 8 else None
                self._loco_lr = self._data[9] if data_len > 9 else None
            elif self._action == IrdaAction.DATA:
                self._valid1 = int.from_bytes(self._data[3:4], byteorder="little") if data_len > 4 else None
                self._valid2 = int.from_bytes(self._data[5:6], byteorder="little") if data_len > 6 else None
                self._dir = self._data[7] if data_len > 7 else None
                self._engine_id = self._data[8] if data_len > 8 else None
                self._train_id = self._data[9] if data_len > 9 else None
                self._status = self._data[10] if data_len > 10 else None
                self._fuel = self._data[11] if data_len > 11 else None
                self._water = self._data[12] if data_len > 12 else None
                self._burn = self._data[13] if data_len > 13 else None
                self._fwb_mask = self._data[14] if data_len > 14 else None
            elif self._action == IrdaAction.SEQUENCE:
                self._sequence = self._data[3] if data_len > 3 else None
            elif self._action == IrdaAction.RECORD:
                self._status = self._data[3] if data_len > 3 else None
        else:
            self._scope = scope if scope is not None else CommandScope.System

    @property
    def debug(self) -> int | None:
        return self._debug

    @property
    def sequence(self) -> str | None:
        return SEQUENCE_MAP.get(self._sequence, None) if self._sequence in SEQUENCE_MAP else "NA"

    @property
    def status(self) -> str | None:
        return STATUS_MAP.get(self._status, None) if self._status in STATUS_MAP else "NA"

    @property
    def payload(self) -> str | None:
        if self.pdi_command != PdiCommand.ASC2_GET:
            if self.action == IrdaAction.CONFIG:
                rl = f" When Engine ID (R -> L): {self._loco_rl}" if self._loco_rl else ""
                lr = f" When Engine ID (L -> R): {self._loco_lr}" if self._loco_lr else ""
                return f"Request: {self.sequence}{rl}{lr} Debug: {self.debug} ({self.packet})"
            elif self.action == IrdaAction.DATA:
                trav = "R -> L: " if self._dir == 0 else "L -> R: "
                return f"{trav} Engine: {self._engine_id} Train: {self._train_id} Status: {self.status} ({self.packet})"
            elif self.action == IrdaAction.SEQUENCE:
                return f"Sequence: {self.sequence} ({self.packet})"
            elif self.action == IrdaAction.RECORD:
                return f"Status: {self.status} ({self.packet})"
        return super().payload
