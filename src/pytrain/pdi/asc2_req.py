from __future__ import annotations

from .constants import PdiCommand, Asc2Action, PDI_SOP, PDI_EOP
from .lcs_req import LcsReq
from ..protocol.constants import CommandScope


class Asc2Req(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.ASC2_GET,
        action: Asc2Action = Asc2Action.CONFIG,
        ident: int | None = None,
        error: bool = False,
        mode: int = None,
        debug: int = None,
        delay: float = None,
        values: int = None,
        valids: int = None,
        time: float = None,
        sub_id: int = None,
    ) -> None:
        super().__init__(data, pdi_command, action, ident, error)
        if isinstance(data, bytes):
            self._action = Asc2Action(self._action_byte)
            data_len = len(self._data)
            if self._action == Asc2Action.CONFIG:
                self._debug = self._data[4] if data_len > 4 else None
                self._mode = self._data[7] if data_len > 7 else None
                self._delay = self._data[8] / 100.0 if data_len > 8 else None
            else:
                self._mode = self._debug = self._delay = None

            if self._action == Asc2Action.CONTROL1:
                self._values = self._data[3] if data_len > 3 else None
                self._time = self._data[4] / 100.0 if data_len > 4 else None
                self._valids = self._sub_id = self._thru = None
                self.scope = CommandScope.ACC
            elif self._action in [Asc2Action.CONTROL2, Asc2Action.CONTROL3]:
                self._values = self._data[3] if data_len > 3 else None
                self._valids = self._data[4] if data_len > 4 else None
                self._time = self._sub_id = self._thru = None
                self.scope = CommandScope.ACC
            elif self._action == Asc2Action.CONTROL4:
                self._values = self._data[3] if data_len > 3 else None
                self._time = self._data[4] / 100.0 if data_len > 4 else None
                self._valids = self._sub_id = None
                self._thru = self._values == 0 if self._values is not None else None
                self.scope = CommandScope.SWITCH
            elif self._action == Asc2Action.CONTROL5:
                self._values = self._data[3] if data_len > 3 else None
                self._valids = self._sub_id = self._time = None
                self._thru = self._values == 0 if self._values is not None else None
                self.scope = CommandScope.SWITCH
            else:
                self._values = self._valids = self._time = self._sub_id = self._thru = None
        else:
            self._action = action
            self._mode = mode
            self._debug = debug
            self._delay: float = delay
            self._values = values
            self._valids = valids
            self._time = time
            self._sub_id = sub_id

    @property
    def mode(self) -> int | None:
        return self._mode

    @property
    def debug(self) -> int | None:
        return self._debug

    @property
    def delay(self) -> float | None:
        return self._delay

    @property
    def values(self) -> int | None:
        return self._values

    @property
    def state(self) -> int | None:
        return self._values

    @property
    def valids(self) -> int | None:
        return self._valids

    @property
    def sub_id(self) -> int | None:
        return self._sub_id

    @property
    def time(self) -> float | None:
        return self._time

    @property
    def is_thru(self) -> bool | None:
        return self._thru

    @property
    def is_out(self) -> bool | None:
        return not self._thru if self._thru is not None else None

    @property
    def payload(self) -> str | None:
        if self.is_error:
            return super().payload
        if self.pdi_command != PdiCommand.ASC2_GET:
            if self.action == Asc2Action.CONFIG:
                return f"Mode: {self.mode} Debug: {self.debug} Delay: {self.delay} ({self.packet})"
            elif self.action == Asc2Action.CONTROL1:
                time = f" for {self.time:.2f} s" if self.values == 1 and self.time else ""
                return f"Relay: {'ON' if self.values == 1 else 'OFF'}{time} ({self.packet})"
            elif self.action == Asc2Action.CONTROL2:
                return f"Relays: {self.values} Valids: {self.valids} ({self.packet})"
            elif self.action == Asc2Action.CONTROL3:
                if self.pdi_command == PdiCommand.ASC2_RX:
                    return f"Relays: {self.values} Valids: {self.valids} ({self.packet})"
                elif self.pdi_command == PdiCommand.ASC2_SET:
                    return f"Sub ID: {self.sub_id} Time: {self.time} ({self.packet})"
            elif self.action == Asc2Action.CONTROL4:
                if self.pdi_command == PdiCommand.ASC2_SET:
                    return f"{'THRU' if self.values == 0 else 'OUT'} Time: {self.time} ({self.packet})"
                elif self.pdi_command == PdiCommand.ASC2_RX:
                    return f"{'THRU' if self.values == 0 else 'OUT'} ({self.packet})"
            elif self.action == Asc2Action.CONTROL5:
                return f"{'THRU' if self.values == 0 else 'OUT'} ({self.packet})"
        return super().payload

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += self.action.as_bytes
        if self._action == Asc2Action.CONFIG:
            if self.pdi_command != PdiCommand.ASC2_GET:
                debug = self.debug if self.debug is not None else 0
                delay = int(round((self.delay * 100))) if self.delay is not None else 0
                byte_str += self.tmcc_id.to_bytes(1, byteorder="big")  # allows board to be renumbered
                byte_str += debug.to_bytes(1, byteorder="big")
                byte_str += (0x0000).to_bytes(2, byteorder="big")
                byte_str += self.mode.to_bytes(1, byteorder="big")
                byte_str += delay.to_bytes(1, byteorder="big")
        elif self._action == Asc2Action.CONTROL1:
            if self.pdi_command != PdiCommand.ASC2_GET:
                values = self.values if self.values is not None else 0
                time = min(int(round((self.time * 100))), 255) if self.time is not None else 0
                byte_str += values.to_bytes(1, byteorder="big")
                byte_str += time.to_bytes(1, byteorder="big")
        elif self._action == Asc2Action.CONTROL2:
            if self.pdi_command != PdiCommand.ASC2_GET:
                values = self.values if self.values is not None else 0
                valids = self.values if self.valids is not None else 0
                byte_str += values.to_bytes(1, byteorder="big")
                byte_str += valids.to_bytes(1, byteorder="big")
        elif self._action == Asc2Action.CONTROL3:
            if self.pdi_command != PdiCommand.ASC2_GET:
                if self.pdi_command == PdiCommand.ASC2_SET:
                    values = self.sub_id if self.values is not None else 1
                    time = min(int(round((self.time * 100))), 255) if self.time is not None else 0
                    if time == 1:
                        time = 0
                    valids = time
                else:
                    values = self.values if self.valids is not None else 0
                    valids = self.valids if self.valids is not None else 0
                byte_str += values.to_bytes(1, byteorder="big")
                byte_str += valids.to_bytes(1, byteorder="big")
        elif self._action == Asc2Action.CONTROL4:
            if self.pdi_command != PdiCommand.ASC2_GET:
                values = self.values if self.values is not None else 0
                time = min(int(round((self.time * 100))), 255) if self.time is not None else 0
                if time == 1:
                    time = 0
                byte_str += values.to_bytes(1, byteorder="big")
                byte_str += time.to_bytes(1, byteorder="big")
        elif self._action == Asc2Action.CONTROL5:
            if self.pdi_command != PdiCommand.ASC2_GET:
                values = self.values if self.values is not None else 0
                byte_str += values.to_bytes(1, byteorder="big")
        elif self._action == Asc2Action.IDENTIFY:
            if self.pdi_command == PdiCommand.ASC2_SET:
                byte_str += (self.ident if self.ident is not None else 0).to_bytes(1, byteorder="big")
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str
