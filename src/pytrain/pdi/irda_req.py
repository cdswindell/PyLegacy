from __future__ import annotations

from typing import Dict

from .constants import PdiCommand, IrdaAction, PDI_SOP, PDI_EOP
from .lcs_req import LcsReq
from ..protocol.constants import CommandScope, Mixins


class IrdaSequence(Mixins):
    NONE = 0
    CROSSING_GATE_NONE = 1
    NONE_CROSSING_GATE = 2
    BELL_NONE = 3
    NONE_BELL = 4
    JOURNEY_BEGIN_JOURNEY_END = 5
    JOURNEY_END_JOURNEY_BEGIN = 6
    SLOW_SPEED_NORMAL_SPEED = 7
    NORMAL_SPEED_SLOW_SPEED = 8
    RECORDING = 9


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
        scope: CommandScope = CommandScope.IRDA,
        ident: int | None = None,
        error: bool = False,
        sequence: IrdaSequence | int = None,
        debug: int = 0,
        loco_rl: int = 255,
        loco_lr: int = 255,
    ) -> None:
        self._debug = self._sequence = self._loco_rl = self._loco_lr = None
        self._valid1 = self._valid2 = self._dir = self._engine_id = self._train_id = self._status = None
        self._fuel = self._water = self._burn = self._fwb_mask = None
        super().__init__(data, pdi_command, action, ident, error)
        self.scope = CommandScope.IRDA
        if isinstance(data, bytes):
            self._action = IrdaAction(self._action_byte)
            data_len = len(self._data)
            if self._action == IrdaAction.INFO:
                self.scope = CommandScope.ACC
            elif self._action == IrdaAction.CONFIG:
                self._debug = self._data[4] if data_len > 4 else None
                self._sequence = IrdaSequence.by_value(self._data[7], True) if data_len > 7 else None
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
                self._bluetooth_id = self._data[19:21] if data_len > 20 else None
                self._prod_year = 2000 + int(self.decode_text(self._data[21:])) if data_len > 21 else None
                self._name = self.decode_text(self._data[24:58]) if data_len > 24 else None
                self._number = self.decode_text(self._data[57:]) if data_len > 58 else None
                self._tsdb_left = self._data[62] if data_len > 62 else None
                self._tsdb_right = self._data[63] if data_len > 63 else None
                self._max_speed = self._data[64] if data_len > 64 else None
                self._odometer = int.from_bytes(self._data[65:68], byteorder="little") if data_len > 68 else None
            elif self._action == IrdaAction.SEQUENCE:
                self._sequence = IrdaSequence.by_value(self._data[3], True) if data_len > 3 else None
            elif self._action == IrdaAction.RECORD:
                self._status = self._data[3] if data_len > 3 else None
        else:
            self.scope = scope if scope is not None else CommandScope.IRDA
            self._debug = debug
            self._sequence = (
                sequence
                if sequence is None or isinstance(sequence, IrdaSequence)
                else IrdaSequence.by_value(sequence, True)
            )
            self._loco_rl = loco_rl
            self._loco_lr = loco_lr

    @property
    def debug(self) -> int | None:
        return self._debug

    @property
    def is_right_to_left(self) -> bool:
        return True if self._dir == 0 else False

    @property
    def is_left_to_right(self) -> bool:
        return True if self._dir == 1 else False

    @property
    def direction(self) -> int:
        return self._dir

    @property
    def sequence(self) -> IrdaSequence:
        return self._sequence

    @property
    def sequence_str(self) -> str | None:
        return self.sequence.name.title() if self._sequence else "NA"

    @property
    def sequence_id(self) -> int:
        return int(self.sequence.value) if self._sequence else None

    @property
    def loco_rl(self) -> int:
        return self._loco_rl

    @property
    def loco_lr(self) -> int:
        return self._loco_lr

    @property
    def train_id(self) -> int:
        return self._train_id

    @property
    def engine_id(self) -> int:
        return self._engine_id

    @property
    def bluetooth_id(self) -> bytes:
        return self._bluetooth_id

    @property
    def year(self) -> int:
        return self._prod_year

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
                return f"Sequence: {self.sequence_str}{rl}{lr} Debug: {self.debug} ({self.packet})"
            elif self.action == IrdaAction.DATA:
                trav = "R -> L" if self._dir == 0 else "L -> R"
                if self.train_id:
                    eng = f"Train: {self.train_id}"
                elif self.engine_id:
                    eng = f"Engine: {self.engine_id}"
                else:
                    eng = "<Unknown>"
                na = f" {self._name}" if self._name is not None else ""
                no = f" #{self._number}" if self._number is not None else ""
                yr = f" {self.year}" if self.year is not None else ""
                bt = f" BT: {self.bluetooth_id.hex(':')}" if self._bluetooth_id else ""
                ty = f" Type: {self.product_id}"
                ft = f" Od: {self._odometer:,} ft" if self._odometer is not None else ""
                fl = f" Fuel: {(100.0 * self._fuel / 255):.2f}%" if self._fuel is not None else ""
                wl = f" Water: {(100.0 * self._water / 255):.2f}%" if self._water is not None else ""
                return f"{trav} {eng}{na}{no}{bt}{yr}{ty}{ft}{fl}{wl} Status: {self.status} ({self.packet})"
            elif self.action == IrdaAction.SEQUENCE:
                return f"Sequence: {self.sequence_str} ({self.packet})"
            elif self.action == IrdaAction.RECORD:
                return f"Status: {self.status} ({self.packet})"
        return super().payload

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += self.action.as_bytes
        bs_len = len(byte_str)
        if self._action == IrdaAction.CONFIG:
            if self.pdi_command == PdiCommand.IRDA_RX:
                debug = self.debug if self.debug is not None else 0
                byte_str += self.tmcc_id.to_bytes(1, byteorder="big")  # allows board to be renumbered
                byte_str += debug.to_bytes(1, byteorder="big")
                byte_str += (0x0000).to_bytes(2, byteorder="big")
                byte_str += self.sequence_id.to_bytes(1, byteorder="big")
                byte_str += self.loco_rl.to_bytes(1, byteorder="big")
                byte_str += self.loco_lr.to_bytes(1, byteorder="big")
        elif self._action == IrdaAction.SEQUENCE:
            if self.pdi_command == PdiCommand.IRDA_SET:
                if self._sequence is not None:
                    byte_str += self._sequence.value.to_bytes(1, byteorder="big")
        elif self._action == IrdaAction.IDENTIFY:
            if self.pdi_command == PdiCommand.IRDA_SET:
                byte_str += (self.ident if self.ident is not None else 0).to_bytes(1, byteorder="big")
        if len(byte_str) > bs_len:
            byte_str, checksum = self._calculate_checksum(byte_str)
            byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
            byte_str += checksum
            byte_str += PDI_EOP.to_bytes(1, byteorder="big")
            return byte_str
        # if byte_str wasn't modified, return the superclass
        return super().as_bytes
