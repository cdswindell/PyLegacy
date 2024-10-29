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

PRODUCT_REV_MAP: Dict[int, str] = {
    0x00: "Switcher",
    0x01: "Road",
}

PRODUCT_ID_MAP: Dict[int, str] = {
    0x02: "Diesel",
    0x03: "Diesel Switcher",
    0x04: "Steam",
    0x05: "Steam Switcher",
    0x06: "Subway",
    0x07: "Electric",
    0x08: "Acela",
    0x09: "Pullmor Diesel",
    0x0A: "Pullmor Steam",
    0x0B: "Breakdown",
    0x0C: "Track Crane",
    0x0D: "Accessory",
    0x0E: "Stock Car",
    0x0F: "Passenger Car",
}

TSDB_MAP: Dict[int, str] = {
    0x01: "Ditch Lights",
    0x02: "Ground Lights",
    0x03: "MARS Lights",
    0x04: "Hazard Lights",
    0x05: "Strobe Lights",
    0x06: "Reserved",
    0x07: "Reserved",
    0x08: "Rule 17",
    0x09: "Loco Marker",
    0x0A: "Tender Marker",
    0x0B: "Doghouse",
    0x0C: "Reserved",
    0x0D: "Reserved",
    0x0E: "Reserved",
    0x0F: "Reserved",
}


class IrdaReq(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.IRDA_GET,
        action: IrdaAction = IrdaAction.CONFIG,
        scope: CommandScope = CommandScope.SYSTEM,
        ident: int | None = None,
        error: bool = False,
    ) -> None:
        self._debug = self._sequence = self._loco_rl = self._loco_lr = None
        self._valid1 = self._valid2 = self._dir = self._engine_id = self._train_id = self._status = None
        self._fuel = self._water = self._burn = self._fwb_mask = None
        super().__init__(data, pdi_command, action, ident, error)
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
                self._runtime = int.from_bytes(self._data[15:16], byteorder="little") if data_len > 15 else None
                self._prod_rev = self._data[17] if data_len > 17 else None
                self._prod_id = self._data[18] if data_len > 18 else None
                self._prod_year = self.decode_text(self._data[21:]) if data_len > 21 else None
                self._name = self.decode_text(self._data[24:58]) if data_len > 24 else None
                self._number = self.decode_text(self._data[57:]) if data_len > 58 else None
                self._tsdb_left = self._data[62] if data_len > 62 else None
                self._tsdb_right = self._data[63] if data_len > 63 else None
                self._max_speed = self._data[64] if data_len > 64 else None
                self._odometer = int.from_bytes(self._data[65:68], byteorder="little") if data_len > 68 else None
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
        return SEQUENCE_MAP[self._sequence] if self._sequence in SEQUENCE_MAP else "NA"

    @property
    def status(self) -> str | None:
        return STATUS_MAP[self._status] if self._status in STATUS_MAP else "NA"

    @property
    def product_rev(self) -> str | None:
        return PRODUCT_REV_MAP[self._prod_rev] if self._prod_rev in PRODUCT_REV_MAP else "NA"

    @property
    def product_id(self) -> str | None:
        return PRODUCT_ID_MAP[self._prod_id] if self._prod_id in PRODUCT_ID_MAP else "NA"

    @staticmethod
    def tsdb(code: int) -> str | None:
        return TSDB_MAP[code] if code in TSDB_MAP else "<Blank>"

    @property
    def name(self) -> str:
        return self._name

    @property
    def number(self) -> str:
        return self._number

    @property
    def payload(self) -> str | None:
        if self.is_error:
            return super().payload
        if self.pdi_command != PdiCommand.IRDA_GET:
            if self.action == IrdaAction.CONFIG:
                rle = f"{self._loco_rl}" if self._loco_rl and self._loco_rl != 255 else "Any"
                lre = f"{self._loco_lr}" if self._loco_lr and self._loco_lr != 255 else "Any"
                rl = f" When Engine ID (R -> L): {rle}"
                lr = f" When Engine ID (L -> R): {lre}"
                return f"Sequence: {self.sequence}{rl}{lr} Debug: {self.debug} ({self.packet})"
            elif self.action == IrdaAction.DATA:
                trav = "R -> L" if self._dir == 0 else "L -> R"
                if self._train_id:
                    eng = f"Train: {self._train_id}"
                elif self._engine_id:
                    eng = f"Engine: {self._engine_id}"
                else:
                    eng = "<Unknown>"
                na = f" {self._name}" if self._name is not None else ""
                no = f" #{self._number}" if self._number is not None else ""
                yr = f" 20{self._prod_year}" if self._prod_year else ""
                ty = f" Type: {self.product_id}"
                ft = f" Od: {self._odometer:,} ft" if self._odometer is not None else ""
                fl = f" Fuel: {(100. * self._fuel / 255):.2f}%" if self._fuel is not None else ""
                wl = f" Water: {(100 * self._water / 255):.2f}%" if self._water is not None else ""

                return f"{trav} {eng}{na}{no}{fl}{wl}{yr}{ty}{ft} Status: {self.status} ({self.packet})"
            elif self.action == IrdaAction.SEQUENCE:
                return f"Sequence: {self.sequence} ({self.packet})"
            elif self.action == IrdaAction.RECORD:
                return f"Status: {self.status} ({self.packet})"
        return super().payload
