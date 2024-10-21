from __future__ import annotations

import abc
from abc import ABC
from collections import defaultdict
from datetime import datetime

from enum import unique, Enum
from typing import TypeVar

from .constants import (
    FriendlyMixins,
    PdiCommand,
    Asc2Action,
    Bpc2Action,
    IrdaAction,
    Ser2Action,
    Stm2Action,
    WiFiAction,
    CommonAction,
)
from .pdi_req import PdiReq
from ..protocol.constants import Mixins


class PdiDeviceState(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, device: PdiDeviceState) -> None:
        self._device = device
        self._address: int | None = None

    @property
    def device(self) -> PdiDeviceState:
        return self._device

    @property
    def address(self) -> int:
        return self._address


class ACS2DeviceState(PdiDeviceState):
    def __init__(self, device: ACS2DeviceState) -> None:
        super().__init__(device)


class DeviceWrapper:
    C = TypeVar("C", bound=PdiReq.__class__)
    E = TypeVar("E", bound=Enum)
    T = TypeVar("T", bound=PdiReq)
    D = TypeVar("D", bound=PdiDeviceState.__class__)

    def __init__(self, req_class: C, enums: E = None, dev_class: D = None, *commands: PdiCommand) -> None:
        self.req_class = req_class
        self.enums = enums
        self.dev_class = dev_class
        self.commands = commands
        self.get: PdiCommand = self._harvest_command("GET")
        self.set: PdiCommand = self._harvest_command("SET")
        self.rx: PdiCommand = self._harvest_command("RX")

    def build(self, data: bytes) -> T:
        action_byte = data[2] if len(data) > 2 else None
        action = self.enums.by_value(action_byte)
        return self.req_class(data, action=action)

    def firmware(self, tmcc_id: int) -> T:
        if self.get is not None:
            enum = self.enums.by_name("FIRMWARE")
            return self.req_class(tmcc_id, self.get, enum)

    def status(self, tmcc_id: int) -> T:
        if self.get is not None:
            enum = self.enums.by_name("STATUS")
            return self.req_class(tmcc_id, self.get, enum)

    def info(self, tmcc_id: int) -> T:
        if self.get is not None:
            enum = self.enums.by_name("INFO")
            return self.req_class(tmcc_id, self.get, enum)

    def clear_errors(self, tmcc_id: int) -> T:
        if self.set is not None:
            enum = self.enums.by_name("CLEAR_ERRORS")
            return self.req_class(tmcc_id, self.set, enum)

    def reset(self, tmcc_id: int) -> T:
        if self.set is not None:
            enum = self.enums.by_name("RESET")
            return self.req_class(tmcc_id, self.set, enum)

    def identify(self, tmcc_id: int, ident: int = 1) -> T:
        if self.set is not None:
            enum = self.enums.by_name("IDENTIFY")
            return self.req_class(tmcc_id, self.set, enum, ident)

    def _harvest_command(self, suffix: str) -> PdiCommand | None:
        suffix = suffix.strip().upper()
        for e in self.commands:
            if e.name.endswith(suffix):
                return e
        return None


@unique
class PdiDevice(Mixins, FriendlyMixins):
    """
    All supported LCS/PDI devices should be listed here, along with their
    constructor class wrapped in a DeviceWrapper
    """

    from .asc2_req import Asc2Req
    from .bpc2_req import Bpc2Req
    from .wifi_req import WiFiReq
    from .pdi_req import AllReq, BaseReq, PingReq, TmccReq
    from .lcs_req import Stm2Req
    from .lcs_req import IrdaReq
    from .lcs_req import Ser2Req

    ALL = DeviceWrapper(AllReq, PdiCommand.ALL_GET, PdiCommand.ALL_SET)
    ASC2 = DeviceWrapper(
        Asc2Req, Asc2Action, ACS2DeviceState, PdiCommand.ASC2_GET, PdiCommand.ASC2_SET, PdiCommand.ASC2_RX
    )
    BASE = DeviceWrapper(BaseReq)
    BPC2 = DeviceWrapper(Bpc2Req, Bpc2Action, PdiCommand.BPC2_GET, PdiCommand.BPC2_SET, PdiCommand.BPC2_RX)
    IRDA = DeviceWrapper(IrdaReq, IrdaAction, PdiCommand.IRDA_GET, PdiCommand.IRDA_SET, PdiCommand.IRDA_RX)
    PING = DeviceWrapper(PingReq)
    SER2 = DeviceWrapper(Ser2Req, Ser2Action, PdiCommand.SER2_GET, PdiCommand.SER2_SET, PdiCommand.SER2_RX)
    STM2 = DeviceWrapper(Stm2Req, Stm2Action, PdiCommand.STM2_GET, PdiCommand.STM2_SET, PdiCommand.STM2_RX)
    TMCC = DeviceWrapper(TmccReq, PdiCommand.TMCC_TX, PdiCommand.TMCC_RX)
    WIFI = DeviceWrapper(WiFiReq, WiFiAction, PdiCommand.WIFI_GET, PdiCommand.WIFI_SET, PdiCommand.WIFI_RX)
    UPDATE = DeviceWrapper(BaseReq)

    T = TypeVar("T", bound=PdiReq)

    @classmethod
    def from_pdi_command(cls, cmd: PdiCommand) -> PdiDevice:
        return cls(cmd.name.split("_")[0].upper())

    @classmethod
    def from_data(cls, data: bytes) -> PdiDevice:
        return cls(PdiCommand(data[1]).name.split("_")[0].upper())

    def build_req(self, data: bytes) -> T:
        return self.value.req_class(data)

    def build_device(self) -> T:
        return self.value.dev_class(self)

    def firmware(self, tmcc_id: int) -> T:
        return self.value.firmware(tmcc_id)

    def status(self, tmcc_id: int) -> T:
        return self.value.status(tmcc_id)

    def info(self, tmcc_id: int) -> T:
        return self.value.info(tmcc_id)

    def clear_errors(self, tmcc_id: int) -> T:
        """
        Build a Clear Errors request
        """
        return self.value.clear_errors(tmcc_id)

    def reset(self, tmcc_id: int) -> T:
        """
        Build a Reset request
        """
        return self.value.identify(tmcc_id)

    def identify(self, tmcc_id: int, ident: int = 1) -> T:
        """
        Build an Identify request
        """
        return self.value.identify(tmcc_id, ident)


class SystemDeviceDict(defaultdict):
    """
    Maintains a dictionary of CommandScope to ComponentStateDict
    """

    def __missing__(self, key: PdiDevice) -> PdiDeviceDict:
        """
        generate a ComponentState object for the dictionary, based on the key
        """
        if isinstance(key, PdiDevice):
            device = key
        else:
            raise KeyError(f"Invalid scope key: {key}")
        # create the component state dict for this key
        self[key] = PdiDeviceDict(device)
        return self[key]

    def register_device(self, cmd: PdiReq) -> None:
        if cmd.action.bits == CommonAction.CONFIG.bits:
            tmcc_id = cmd.tmcc_id
            print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {cmd} {tmcc_id}")


class PdiDeviceDict(defaultdict):
    def __init__(self, device: PdiDevice):
        super().__init__(None)  # base class doesn't get a factory
        self._device = device

    @property
    def device(self) -> PdiDevice:
        return self._device

    def __missing__(self, key: int) -> PdiDeviceState:
        """
        generate a ComponentState object for the dictionary, based on the key
        """
        if not isinstance(key, int) or key < 1 or key > 99:
            raise KeyError(f"Invalid ID: {key}")
        value: PdiDeviceState = self.device.build_device()
        value._address = key
        self[key] = value
        return self[key]
