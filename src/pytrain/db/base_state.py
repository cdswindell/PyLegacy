from __future__ import annotations

from typing import Dict, Any

from .component_state import ComponentState, L, P, SCOPE_TO_STATE_MAP
from ..protocol.constants import CommandScope
from ..pdi.constants import PdiCommand, D4Action


class BaseState(ComponentState):
    """
    Maintain the state of a Lionel Base
    """

    def __init__(self, scope: CommandScope = CommandScope.BASE) -> None:
        if scope != CommandScope.BASE:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._base_name = None
        self._firmware = None
        self._firmware_high = None
        self._firmware_low = None
        self._route_throw_rate = None
        self._d4_engines: int | None = None
        self._d4_trains: int | None = None

    def __repr__(self) -> str:
        bn = f"Lionel Base 3: {self._base_name if self._base_name else 'NA'}"
        fw = f" Firmware: {self._firmware if self._firmware else 'NA'}"
        return f"{bn}{fw}"

    def update(self, command: L | P) -> None:
        from ..pdi.base_req import BaseReq
        from ..pdi.d4_req import D4Req

        if isinstance(command, BaseReq):
            with self._cv:
                # Note: super().update is explicitly not called
                self._base_name = command.name.title() if command.name else self._base_name
                self._firmware = command.firmware if command.firmware else self._firmware
                if self.firmware:
                    version_info = self.firmware.split(".")
                    self._firmware_high = int(version_info[0])
                    self._firmware_low = int(version_info[1])
                self._route_throw_rate = command.route_throw_rate
                self.changed.set()
                self._cv.notify_all()
        elif isinstance(command, D4Req):
            print(command)
            with self._cv:
                if command.action == D4Action.COUNT:
                    if command.pdi_command == PdiCommand.D4_ENGINES:
                        self._d4_engines = command.count
                    elif command.pdi_command == PdiCommand.D4_TRAINS:
                        self._d4_trains = command.count
                self.changed.set()
                self._cv.notify_all()

    @property
    def base_name(self) -> str:
        return self._base_name

    @property
    def firmware(self) -> str:
        return self._firmware

    @property
    def firmware_high(self) -> int:
        return self._firmware_high

    @property
    def firmware_low(self) -> int:
        return self._firmware_low

    @property
    def d4_engines(self) -> int:
        return self._d4_engines

    @property
    def d4_trains(self) -> int:
        return self._d4_trains

    @property
    def route_throw_rate(self) -> float:
        return self._route_throw_rate

    @property
    def is_tmcc(self) -> bool:
        return False

    @property
    def is_legacy(self) -> bool:
        return True

    @property
    def is_lcs(self) -> bool:
        return True

    def as_bytes(self) -> bytes:
        if self.is_known:
            from ..pdi.base_req import BaseReq

            return BaseReq(self.address, PdiCommand.BASE, state=self).as_bytes
        else:
            return bytes()

    def as_dict(self) -> Dict[str, Any]:
        d = dict()
        d["firmware"] = self.firmware
        d["base_name"] = self.base_name
        d["route_throw_rate"] = self.route_throw_rate
        return d


SCOPE_TO_STATE_MAP[CommandScope.BASE] = BaseState
