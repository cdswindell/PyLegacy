from __future__ import annotations

from ..pdi.constants import PdiCommand, Bpc2Action, PDI_SOP, PDI_EOP
from ..pdi.lcs_req import LcsReq
from ..protocol.constants import CommandScope


class Bpc2Req(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.BPC2_GET,
        action: Bpc2Action = Bpc2Action.CONFIG,
        ident: int | None = None,
        error: bool = False,
        mode: int = None,
        debug: int = None,
        restore: bool = None,
        state: int = None,
        values: int = None,
        valids: int = None,
    ) -> None:
        super().__init__(data, pdi_command, action, ident, error)
        if isinstance(data, bytes):
            self._action = Bpc2Action(self._action_byte)
            data_len = len(self._data)
            if self._action == Bpc2Action.CONFIG:
                self._debug = self._data[4] if data_len > 4 else None
                self._mode = self._data[7] if data_len > 7 else None
                self._restore = (self._mode & 0x80) == 0x80
                if self._restore:
                    self._mode &= 0x7F
            else:
                self._mode = self._debug = self._restore = None

            if self._action in {Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                self._state = self._data[3] if data_len > 3 else None
                self._values = self._valids = None
                if self._action == Bpc2Action.CONTROL3:
                    self.scope = CommandScope.ACC
                else:
                    self.scope = CommandScope.TRAIN
            elif self._action in {Bpc2Action.CONTROL2, Bpc2Action.CONTROL4}:
                self._values = self._data[3] if data_len > 3 else None
                self._valids = self._data[4] if data_len > 4 else None
                self._state = None
                if self._action == Bpc2Action.CONTROL4:
                    self.scope = CommandScope.ACC
                else:
                    self.scope = CommandScope.TRAIN
            else:
                self._state = self._values = self._valids = None
        else:
            self._action = action
            self._mode = mode
            self._debug = debug
            self._restore = restore
            self._state = state
            self._values = values
            self._valids = valids

    @property
    def mode(self) -> int | None:
        return self._mode

    @property
    def restore(self) -> bool:
        return self._restore

    @property
    def debug(self) -> int | None:
        return self._debug

    @property
    def state(self) -> int | None:
        return self._state

    @property
    def values(self) -> int | None:
        return self._values

    @property
    def valids(self) -> int | None:
        return self._valids

    @property
    def payload(self) -> str | None:
        if self.is_error:
            return super().payload
        if self.pdi_command != PdiCommand.BPC2_GET:
            if self.action == Bpc2Action.CONFIG:
                return f"Mode: {self.mode} Debug: Restore: {self.restore} {self.debug} ({self.packet})"
            elif self.action in {Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
                return f"Power {'ON' if self.state == 1 else 'OFF'} ({self.packet})"
        return super().payload

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += self.action.as_bytes

        if self._action == Bpc2Action.CONFIG:
            if self.pdi_command != PdiCommand.BPC2_GET:
                debug = self.debug if self.debug is not None else 0
                mode = self.mode | 0x80 if self.restore else self.mode
                byte_str += self.tmcc_id.to_bytes(1, byteorder="big")  # allows board to be renumbered
                byte_str += debug.to_bytes(1, byteorder="big")
                byte_str += (0x0000).to_bytes(2, byteorder="big")
                byte_str += mode.to_bytes(1, byteorder="big")
        elif self._action == Bpc2Action.IDENTIFY:
            if self.pdi_command == PdiCommand.BPC2_SET:
                byte_str += (self.ident if self.ident is not None else 0).to_bytes(1, byteorder="big")
        elif self._action in {Bpc2Action.CONTROL1, Bpc2Action.CONTROL3}:
            if self.pdi_command != PdiCommand.BPC2_GET:
                byte_str += (self.state if self.state is not None else 0).to_bytes(1, byteorder="big")
        elif self._action in {Bpc2Action.CONTROL2, Bpc2Action.CONTROL4}:
            if self.pdi_command != PdiCommand.BPC2_GET:
                byte_str += (self.state if self.state is not None else 0).to_bytes(1, byteorder="big")
                values = self.values if self.values is not None else 0
                valids = self.values if self.valids is not None else 0
                byte_str += values.to_bytes(1, byteorder="big")
                byte_str += valids.to_bytes(1, byteorder="big")
        elif self._action == Bpc2Action.CONTROL2:
            if self.pdi_command != PdiCommand.BPC2_GET:
                values = self.values if self.values is not None else 0
                valids = self.values if self.valids is not None else 0
                byte_str += values.to_bytes(1, byteorder="big")
                byte_str += valids.to_bytes(1, byteorder="big")
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str
