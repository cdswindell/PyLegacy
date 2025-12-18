from __future__ import annotations

import threading
from typing import List, TypeVar

from ..pdi.pdi_device import PdiDevice, SystemDeviceDict
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

    @classmethod
    def get_config(cls, scope: PdiDevice, address: int, create: bool = False) -> T | None:
        if cls._instance is None:
            raise AttributeError("PdiStateStore not built")
        if create:
            return cls._instance._pdi_devices[scope][address]
        else:
            return cls._instance.query(scope, address)

    def __init__(self) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        self._pdi_devices = SystemDeviceDict()

    def register_pdi_device(self, cmd: PdiReq) -> List[T] | None:
        return self._pdi_devices.register_pdi_device(cmd)

    def query(self, scope: PdiDevice, address: int = None) -> T | List[T] | None:
        if scope in self._pdi_devices:
            if address is None:
                return self.get_all(scope)
            elif address in self._pdi_devices[scope]:
                return self._pdi_devices[scope][address]
        return None

    def get_all(self, scope: PdiDevice) -> List[T]:
        if scope in self._pdi_devices:
            # ignore dups where we store an entry for the item's road number
            valids = {v.address for k, v in self._pdi_devices[scope].items()}
            devices = [v for k, v in self._pdi_devices[scope].items() if k in valids]
            devices.sort(key=lambda x: x.address)
            return devices
        else:
            return []
