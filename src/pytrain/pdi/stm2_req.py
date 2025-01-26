from __future__ import annotations

from .constants import PdiCommand, Stm2Action, PDI_SOP, PDI_EOP
from .lcs_req import LcsReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum


class Stm2Req(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.STM2_GET,
        action: Stm2Action = Stm2Action.CONFIG,
        ident: int | None = None,
        error: bool = False,
        mode: int = None,
        debug: int = None,
        state: TMCC1SwitchCommandEnum = None,
    ) -> None:
        super().__init__(data, pdi_command, action, ident, error)
        if isinstance(data, bytes):
            self._action = Stm2Action(self._action_byte)
            data_len = len(self._data)
            if self._action == Stm2Action.CONFIG:
                self._mode = self._data[7] if data_len > 7 else None
                self._debug = self._data[4] if data_len > 4 else None
            else:
                self._mode = self._debug = None

            if self._action == Stm2Action.CONTROL1:
                sw_state = self._data[3] if data_len > 3 else None
                self._state = TMCC1SwitchCommandEnum.OUT if sw_state == 1 else TMCC1SwitchCommandEnum.THRU
                self.scope = CommandScope.SWITCH
            else:
                self._state = None
        else:
            self._action = action
            self._mode = mode
            self._debug = debug
            self._state = state

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def debug(self) -> int | None:
        return self._debug

    @property
    def state(self) -> TMCC1SwitchCommandEnum:
        return self._state

    @property
    def is_thru(self) -> bool | None:
        return self._state == TMCC1SwitchCommandEnum.THRU

    @property
    def is_out(self) -> bool | None:
        return self._state == TMCC1SwitchCommandEnum.OUT

    @property
    def payload(self) -> str | None:
        if self.is_error:
            return super().payload
        if self.pdi_command != PdiCommand.STM2_GET:
            if self.action == Stm2Action.CONFIG:
                return f"Mode: {self.mode} Debug: {self.debug} ({self.packet})"
            elif self._action == Stm2Action.CONTROL1:
                return f"{self.state} ({self.packet})"
        return super().payload

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += self.action.as_bytes

        if self._action == Stm2Action.CONFIG:
            if self.pdi_command != PdiCommand.STM2_GET:
                debug = self.debug if self.debug is not None else 0
                mode = self.mode if self.mode is not None else 0
                byte_str += self.tmcc_id.to_bytes(1, byteorder="big")  # allows board to be renumbered
                byte_str += debug.to_bytes(1, byteorder="big")
                byte_str += (0x0000).to_bytes(2, byteorder="big")
                byte_str += mode.to_bytes(1, byteorder="big")
        elif self._action == Stm2Action.IDENTIFY:
            if self.pdi_command == PdiCommand.STM2_SET:
                byte_str += (self.ident if self.ident is not None else 0).to_bytes(1, byteorder="big")
        elif self._action == Stm2Action.CONTROL1:
            if self.pdi_command != PdiCommand.STM2_GET:
                sw_state = 1 if self.state == TMCC1SwitchCommandEnum.OUT else 0
                byte_str += sw_state.to_bytes(1, byteorder="big")
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str
