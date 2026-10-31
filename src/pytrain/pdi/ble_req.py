#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from .constants import PdiCommand
from .pdi_req import PdiReq
from ..protocol.constants import CommandScope


class BleReq(PdiReq):
    """Receive and preserve BLE PDI notifications without interpreting unknown fields."""

    def __init__(self, data: bytes, pdi_command: PdiCommand = PdiCommand.BLE_RX) -> None:
        super().__init__(data, pdi_command)
        if not isinstance(data, bytes):
            raise TypeError("BLE notifications must be decoded from received PDI bytes")
        self._payload_bytes = self._data[1:]
        self._is_programming = len(self._data) >= 5 and self._data[2] == 0x12
        self._tmcc_id = 0
        if self._is_programming:
            # Observed D4 form: 76 00 12 00 00 <ASCII digits>.
            digits = self._data[5:]
            if digits and all(0x30 <= byte <= 0x39 for byte in digits):
                self._tmcc_id = int(digits.decode("ascii"))
            # Observed D2 form: 76 00 12 <binary TMCC ID> FF.
            elif len(self._data) == 5 and self._data[4] == 0xFF:
                self._tmcc_id = self._data[3]
            if 1 <= self._tmcc_id <= 9999:
                self._scope = CommandScope.ENGINE

    @property
    def is_programming(self) -> bool:
        return self._is_programming and 1 <= self.tmcc_id <= 9999

    @property
    def payload_bytes(self) -> bytes:
        return self._payload_bytes

    @property
    def payload(self) -> str:
        address = f" TMCC ID: {self.tmcc_id}" if self.is_programming else ""
        return f"BLE notification{address} data: {self.payload_bytes.hex()}"
