from __future__ import annotations

import threading
from typing import TypeVar, List

from ..pdi.pdi_device import SystemDeviceDict
from ..pdi.pdi_req import PdiReq

T = TypeVar("T", bound=PdiReq)


class PdiStateStore:
    _instance: PdiStateStore = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if PdiStateStore._instance is None:
                PdiStateStore._instance = super(PdiStateStore, cls).__new__(cls)
                PdiStateStore._instance._initialized = False
            return PdiStateStore._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        self._pdi_devices = SystemDeviceDict()

    def register_pdi_device(self, cmd: PdiReq) -> List[T] | None:
        return self._pdi_devices.register_pdi_device(cmd)
