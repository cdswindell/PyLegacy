#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

import sys
from ipaddress import IPv4Address

from ..constants import DEFAULT_ADDRESS, CommandScope
from .dcds_command_req import VariableCommandReq
from .multibyte_constants import TMCC2EngineCommandEnumEx

if sys.version_info >= (3, 11):
    from typing import Self


class RampCommandReq(VariableCommandReq):
    """Synthetic ramp ownership identified by an IPv4 endpoint and a short claim ID.

    The public payload is fourteen bytes: IPv4 (4), port/process nonce (2),
    claim ID (2), and an immutable millisecond Unix epoch timestamp (6).
    The sixteen-byte wire payload prepends the logical address (2); all integers
    use unsigned network byte order. Packets use three-byte words at framing address 1,
    with ENGINE/TRAIN scope in the usual prefixes, regardless of logical address.
    """

    @classmethod
    def build(
        cls,
        command: TMCC2EngineCommandEnumEx,
        address: int = DEFAULT_ADDRESS,
        data_bytes: bytes | bytearray | list[int] = None,
        scope: CommandScope = None,
        *,
        address_bytes: bytes | None = None,
    ) -> Self:
        """Build from endpoint/claim bytes, or a wire payload with its framing address."""
        if address_bytes is not None:
            if len(address_bytes) != 2 or address_bytes[0] != 3:
                raise ValueError(
                    f"Ramp commands require three-byte words at framing address 1: {address_bytes.hex(':')}"
                )
            if not isinstance(data_bytes, (bytes, bytearray, list)) or len(data_bytes) != 16:
                raise ValueError("Ramp wire payload must contain exactly sixteen bytes")
            address = int.from_bytes(bytes(data_bytes[:2]), byteorder="big")
            data_bytes = data_bytes[2:]
        return cls(command, address, data_bytes, scope)

    @classmethod
    def for_endpoint(
        cls,
        command: TMCC2EngineCommandEnumEx,
        address: int,
        host: str,
        port: int,
        claim_id: int,
        scope: CommandScope = None,
        *,
        timestamp_ms: int,
    ) -> Self:
        return cls.build(command, address, cls._endpoint_bytes(host, port, claim_id, timestamp_ms), scope)

    @staticmethod
    def _endpoint_bytes(host: str, port: int, claim_id: int, timestamp_ms: int) -> bytes:
        if not isinstance(host, str):
            raise ValueError("Ramp host must be a unicast IPv4 address")
        ip = IPv4Address(host)
        if ip.packed[0] == 0 or ip.is_multicast or ip.is_reserved:
            raise ValueError(f"Ramp host must be a unicast IPv4 address: {host}")
        for label, value in (("port", port), ("claim_id", claim_id)):
            if type(value) is not int or not 1 <= value <= 65535:
                raise ValueError(f"Ramp {label} must be an integer from 1 to 65535: {value}")
        if type(timestamp_ms) is not int or not 1 <= timestamp_ms < 1 << 48:
            raise ValueError(f"Ramp timestamp_ms must be an integer from 1 to {(1 << 48) - 1}: {timestamp_ms}")
        return ip.packed + port.to_bytes(2, "big") + claim_id.to_bytes(2, "big") + timestamp_ms.to_bytes(6, "big")

    def __init__(
        self,
        command_def_enum: TMCC2EngineCommandEnumEx,
        address: int = DEFAULT_ADDRESS,
        data_bytes: bytes | bytearray | list[int] = None,
        scope: CommandScope = None,
    ) -> None:
        if command_def_enum not in {TMCC2EngineCommandEnumEx.RAMP_CLAIM, TMCC2EngineCommandEnumEx.RAMP_RELEASE}:
            raise ValueError(f"Invalid ramp command: {command_def_enum}")
        if scope not in {None, CommandScope.ENGINE, CommandScope.TRAIN}:
            raise ValueError(f"Invalid ramp scope: {scope}")
        if type(address) is not int or not 1 <= address <= 9999 or address == 99:
            raise ValueError(f"Invalid ramp address: {address}")
        if not isinstance(data_bytes, (bytes, bytearray, list)):
            raise ValueError("Ramp payload must contain exactly fourteen bytes")
        try:
            payload = bytes(data_bytes)
        except (TypeError, ValueError) as exc:
            raise ValueError("Ramp payload must contain exactly fourteen bytes") from exc
        if len(payload) != 14:
            raise ValueError("Ramp payload must contain exactly fourteen bytes")
        self._endpoint_bytes(
            str(IPv4Address(payload[:4])),
            int.from_bytes(payload[4:6], "big"),
            int.from_bytes(payload[6:8], "big"),
            int.from_bytes(payload[8:14], "big"),
        )
        super().__init__(command_def_enum, address, payload, scope)

    def _validate_send(self) -> None:
        raise ValueError(
            f"{self.command.name} is state-only; use CommBuffer.update_state instead of generic send/action APIs"
        )

    @property
    def data_bytes(self) -> bytes:
        return self._data_bytes

    @property
    def num_bytes(self) -> int:
        return (5 + self.command.value.num_data_bytes) * 3

    @property
    def as_bytes(self) -> bytes:
        if type(self.address) is not int or not 1 <= self.address <= 9999 or self.address == 99:
            raise ValueError(f"Invalid ramp address: {self.address}")
        payload = self.address.to_bytes(2, "big") + self.data_bytes
        return VariableCommandReq(self.command, 1, payload, self.scope).as_bytes

    @property
    def is_tmcc4(self) -> bool:
        # CommandReq infers TMCC4 from logical addresses; these packets never use it.
        return False

    @property
    def host(self) -> str:
        return str(IPv4Address(self.data_bytes[:4]))

    @property
    def port(self) -> int:
        return int.from_bytes(self.data_bytes[4:6], "big")

    @property
    def claim_id(self) -> int:
        return int.from_bytes(self.data_bytes[6:8], "big")

    @property
    def timestamp_ms(self) -> int:
        return int.from_bytes(self.data_bytes[8:14], "big")
