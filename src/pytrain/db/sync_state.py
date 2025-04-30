#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from typing import Dict, Any

from .component_state import ComponentState, L, P, SCOPE_TO_STATE_MAP
from ..protocol.constants import CommandScope, PROGRAM_NAME
from ..protocol.command_req import CommandReq
from ..protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum


class SyncState(ComponentState):
    """
    Maintain the state of a Lionel Base
    """

    def __init__(self, scope: CommandScope = CommandScope.SYNC) -> None:
        if scope != CommandScope.SYNC:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._state_synchronized: bool | None = None
        self._state_synchronizing: bool | None = None

    def __repr__(self) -> str:
        if self._state_synchronized is not None and not self._state_synchronized:
            msg = "Synchronizing..."
        else:
            msg = f"Synchronized: {self._state_synchronized if self._state_synchronized is not None else 'NA'}"
        return f"{PROGRAM_NAME} {msg}"

    def update(self, command: L | P) -> None:
        if isinstance(command, CommandReq):
            self._ev.clear()
            with self._cv:
                # Note: super().update is explicitly not called
                if command.command in {TMCC1SyncCommandEnum.SYNCHRONIZING, TMCC1SyncCommandEnum.RESYNC}:
                    self._state_synchronized = False
                    self._state_synchronizing = True
                elif command.command == TMCC1SyncCommandEnum.SYNCHRONIZED:
                    self._state_synchronized = True
                    self._state_synchronizing = False
                self.changed.set()
                self._cv.notify_all()

    @property
    def is_synchronized(self) -> bool:
        return self._state_synchronized

    @property
    def is_synchronizing(self) -> bool:
        return self._state_synchronizing

    @property
    def is_known(self) -> bool:
        return self._state_synchronized is not None

    @property
    def is_tmcc(self) -> bool:
        return True

    @property
    def is_legacy(self) -> bool:
        return False

    @property
    def is_lcs(self) -> bool:
        return False

    def as_bytes(self) -> bytes:
        return bytes()

    def as_dict(self) -> Dict[str, Any]:
        state = "synchronized" if self.is_synchronized else "synchronizing" if self.is_synchronizing else None
        return {"state": state}


SCOPE_TO_STATE_MAP.update({CommandScope.SYNC: SyncState})
