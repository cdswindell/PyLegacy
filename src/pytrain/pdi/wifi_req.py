from __future__ import annotations

from ..pdi.constants import PdiCommand, WiFiAction
from ..pdi.lcs_req import LcsReq

WIFI_MODE_MAP = {0: "AP", 1: "INF", 2: "WPS"}


class WiFiReq(LcsReq):
    def __init__(
        self,
        data: bytes | int,
        pdi_command: PdiCommand = PdiCommand.WIFI_GET,
        action: WiFiAction = WiFiAction.CONFIG,
        ident: int | None = None,
        error: bool = False,
    ) -> None:
        super().__init__(data, pdi_command, action, ident, error)
        if isinstance(data, bytes):
            self._action = WiFiAction(self._action_byte)
        else:
            self._action = action

    @property
    def base_address(self) -> str | None:
        if self._data is not None and self.action == WiFiAction.IP:
            payload = self._data[3:]
            return f"{payload[0]}.{payload[1]}.{payload[2]}.{payload[3]}"
        return None

    @property
    def clients(self) -> list[str]:
        if self._data is not None and self.action == WiFiAction.IP:
            payload = self._data[3:]
            prefix = f"{payload[0]}.{payload[1]}.{payload[2]}."
            the_clients = list()
            for i in range(0, len(payload), 2):
                the_clients.append(f"{prefix}{payload[i + 1]}")
            return the_clients
        return []

    @property
    def payload(self) -> str | None:
        if self.is_error:
            return super().payload
        else:
            payload_bytes = self._data[3:]
            if self.action == WiFiAction.CONNECT:
                return (
                    f"Max Connections: {payload_bytes[0]} Connected: {payload_bytes[1]}"
                    + f" {WIFI_MODE_MAP[payload_bytes[2]]}"
                )
            elif self.action == WiFiAction.IP:
                ip_addr = f"{payload_bytes[0]}.{payload_bytes[1]}.{payload_bytes[2]}.{payload_bytes[3]}"
                payload_bytes = payload_bytes[4:]
                clients = " Clients: "
                for i in range(0, len(payload_bytes), 2):
                    if i > 0:
                        clients += ", "
                    clients += f"{payload_bytes[i + 1]} ({payload_bytes[i]})"
                return f"Base IP: {ip_addr} {clients}"
            elif self.action == WiFiAction.RESPBCASTS:
                return f"Broadcasts {'ENABLED' if payload_bytes[0] == 1 else 'DISABLED'}: {payload_bytes[0]}"
        return super().payload
