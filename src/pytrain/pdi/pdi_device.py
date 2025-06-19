from __future__ import annotations

import abc
import logging
from abc import ABC
from collections import defaultdict
from enum import Enum, unique
from typing import List, TypeVar

from ..protocol.constants import CommandScope, Mixins
from .amc2_req import Amc2Req
from .asc2_req import Asc2Req
from .bpc2_req import Bpc2Req
from .constants import (
    Amc2Action,
    Asc2Action,
    Bpc2Action,
    CommonAction,
    D4Action,
    FriendlyMixins,
    IrdaAction,
    PdiAction,
    PdiCommand,
    Ser2Action,
    Stm2Action,
    WiFiAction,
)
from .irda_req import IrdaReq
from .pdi_req import PdiReq
from .stm2_req import Stm2Req

T = TypeVar("T", bound=PdiReq)

log = logging.getLogger(__name__)


class PdiDeviceConfig(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, device: PdiDevice, cmd: T) -> None:
        self._device = device
        self._tmcc_id: int = cmd.tmcc_id if cmd is not None else 0

    @property
    def device(self) -> PdiDevice:
        return self._device

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @property
    @abc.abstractmethod
    def state_requests(self) -> List[T]: ...


class Acs2DeviceConfig(PdiDeviceConfig):
    def __init__(self, cmd: Asc2Req) -> None:
        super().__init__(PdiDevice.ASC2, cmd)
        self._mode = cmd.mode

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def state_requests(self) -> List[T]:
        cmds = []
        if self._mode == 0:
            # Acc mode, 8 TMCC IDs
            for i in range(8):
                cmds.append(Asc2Req(self.tmcc_id + i, action=Asc2Action.CONTROL1))
        elif self._mode == 1:
            # Acc mode, 1 TMCC ID, latching
            cmds.append(Asc2Req(self.tmcc_id, action=Asc2Action.CONTROL2))
        elif self._mode == 2:
            # Switch mode, pulsed, 4 TMCC IDs
            for i in range(4):
                cmds.append(Asc2Req(self.tmcc_id + i, action=Asc2Action.CONTROL4))
        elif self._mode == 3:
            # Switch mode, latched, 4 TMCC IDs
            for i in range(4):
                cmds.append(Asc2Req(self.tmcc_id + i, action=Asc2Action.CONTROL5))
        return cmds


class Amc2DeviceConfig(PdiDeviceConfig):
    def __init__(self, cmd: Amc2Req) -> None:
        super().__init__(PdiDevice.AMC2, cmd)

    @property
    def state_requests(self) -> List[T]:
        return []


class Bpc2DeviceConfig(PdiDeviceConfig):
    def __init__(self, cmd: Bpc2Req) -> None:
        super().__init__(PdiDevice.BPC2, cmd)
        self._mode = cmd.mode

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def state_requests(self) -> List[T]:
        cmds = []
        if self._mode == 0:
            # TR mode, 8 TMCC IDs
            for i in range(8):
                cmds.append(Bpc2Req(self.tmcc_id + i, action=Bpc2Action.CONTROL1))
        elif self._mode == 1:
            # TR mode, 1 TMCC ID
            cmds.append(Bpc2Req(self.tmcc_id, action=Bpc2Action.CONTROL2))
        elif self._mode == 2:
            # Acc mode, 8 TMCC IDs
            for i in range(8):
                cmds.append(Bpc2Req(self.tmcc_id + i, action=Bpc2Action.CONTROL3))
        elif self._mode == 3:
            # Acc mode, 1 TMCC ID
            cmds.append(Bpc2Req(self.tmcc_id, action=Bpc2Action.CONTROL4))
        return cmds


class Stm2DeviceConfig(PdiDeviceConfig):
    def __init__(self, cmd: Stm2Req) -> None:
        super().__init__(PdiDevice.STM2, cmd)
        self._mode = cmd.mode

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def state_requests(self) -> List[T]:
        cmds = []
        if self._mode == 0:
            # 16 inputs, 16 TMCC IDs
            for i in range(16):
                cmds.append(Stm2Req(self.tmcc_id + i, action=Stm2Action.CONTROL1))
        elif self._mode == 2:
            # 8 input pairs, 8 TMCC IDs
            for i in range(8):
                cmds.append(Stm2Req(self.tmcc_id + i, action=Stm2Action.CONTROL1))
        return cmds


class IrdaDeviceConfig(PdiDeviceConfig):
    def __init__(self, cmd: IrdaReq) -> None:
        super().__init__(PdiDevice.IRDA, cmd)

    @property
    def state_requests(self) -> List[T]:
        cmds = [
            IrdaReq(self.tmcc_id, action=IrdaAction.INFO, scope=CommandScope.ACC),
            IrdaReq(self.tmcc_id, action=IrdaAction.CONFIG),
        ]
        return cmds


A = TypeVar("A", bound=PdiAction)


class DeviceWrapper:
    C = TypeVar("C", bound=PdiReq.__class__)
    E = TypeVar("E", bound=Enum)
    T = TypeVar("T", bound=PdiReq)
    DC = TypeVar("DC", bound=PdiDeviceConfig.__class__)

    def __init__(
        self,
        req_class: C,
        *commands: PdiCommand,
        enums: E = None,
        dev_class: DC = None,
        common_actions: bool = True,
    ) -> None:
        self.req_class = req_class
        self.enums = enums
        self.dev_class = dev_class
        self.commands = commands
        self.common_actions = common_actions
        self.get: PdiCommand = self._harvest_command("GET")
        self.set: PdiCommand = self._harvest_command("SET")
        self.rx: PdiCommand = self._harvest_command("RX")

    def __repr__(self) -> str:
        return f"{self.req_class.__class__.__name__}"

    def build(self, data: bytes | int, action: A = None) -> T:
        if isinstance(data, bytes):
            if self.enums is not None:
                action_byte = data[3] if len(data) > 3 else None
                if action_byte & 0x80 == 0x80:
                    error = True
                    action_byte = 0x7FF & action_byte
                else:
                    error = False
                action = self.enums.by_value(action_byte)
                return self.req_class(data, action=action, error=error)
            else:
                return self.req_class(data)
        else:
            return self.req_class(data, action=action)

    def firmware(self, tmcc_id: int) -> T | None:
        if self.get is not None:
            enum = self.enums.by_name("FIRMWARE")
            return self.req_class(tmcc_id, self.get, enum)
        return None

    def status(self, tmcc_id: int) -> T | None:
        if self.get is not None:
            enum = self.enums.by_name("STATUS")
            return self.req_class(tmcc_id, self.get, enum)
        return None

    def info(self, tmcc_id: int) -> T | None:
        if self.get is not None:
            enum = self.enums.by_name("INFO")
            return self.req_class(tmcc_id, self.get, enum)
        return None

    def config(self, tmcc_id: int) -> T | None:
        if self.get is not None:
            enum = self.enums.by_name("CONFIG")
            return self.req_class(tmcc_id, self.get, enum)
        return None

    def clear_errors(self, tmcc_id: int) -> T | None:
        if self.set is not None:
            enum = self.enums.by_name("CLEAR_ERRORS")
            return self.req_class(tmcc_id, self.set, enum)
        return None

    def reset(self, tmcc_id: int) -> T | None:
        if self.set is not None:
            enum = self.enums.by_name("RESET")
            return self.req_class(tmcc_id, self.set, enum)
        return None

    def identify(self, tmcc_id: int, ident: int = 1) -> T | None:
        if self.set is not None:
            enum = self.enums.by_name("IDENTIFY")
            return self.req_class(tmcc_id, self.set, enum, ident=ident)
        return None

    @property
    def is_common_actions(self) -> bool:
        return self.common_actions

    def _harvest_command(self, suffix: str) -> PdiCommand | None:
        suffix = suffix.strip().upper()
        for e in self.commands:
            if e.name.endswith(suffix):
                return e
        return None


D = TypeVar("D", bound=PdiDeviceConfig)


@unique
class PdiDevice(Mixins, FriendlyMixins):
    """
    All supported LCS/PDI devices should be listed here, along with their
    constructor class wrapped in a DeviceWrapper
    """

    from .asc2_req import Asc2Req
    from .base_req import BaseReq
    from .block_req import BlockReq
    from .bpc2_req import Bpc2Req
    from .d4_req import D4Req
    from .irda_req import IrdaReq
    from .lcs_req import Ser2Req
    from .pdi_req import AllReq, PingReq, TmccReq
    from .stm2_req import Stm2Req
    from .wifi_req import WiFiReq

    BASE = DeviceWrapper(BaseReq)
    D4 = DeviceWrapper(D4Req, enums=D4Action, common_actions=False)
    PING = DeviceWrapper(PingReq)
    ALL = DeviceWrapper(AllReq, PdiCommand.ALL_GET, PdiCommand.ALL_SET)
    TMCC = DeviceWrapper(TmccReq, PdiCommand.TMCC_TX, PdiCommand.TMCC_RX)
    TMCC4 = DeviceWrapper(TmccReq, PdiCommand.TMCC4_TX, PdiCommand.TMCC4_RX)
    WIFI = DeviceWrapper(WiFiReq, PdiCommand.WIFI_GET, PdiCommand.WIFI_SET, PdiCommand.WIFI_RX, enums=WiFiAction)
    SER2 = DeviceWrapper(Ser2Req, PdiCommand.SER2_GET, PdiCommand.SER2_SET, PdiCommand.SER2_RX, enums=Ser2Action)
    BLOCK = DeviceWrapper(BlockReq, PdiCommand.BLOCK_GET, PdiCommand.BLOCK_SET, PdiCommand.BLOCK_RX)
    IRDA = DeviceWrapper(
        IrdaReq,
        PdiCommand.IRDA_GET,
        PdiCommand.IRDA_SET,
        PdiCommand.IRDA_RX,
        enums=IrdaAction,
        dev_class=IrdaDeviceConfig,
    )
    ASC2 = DeviceWrapper(
        Asc2Req,
        PdiCommand.ASC2_GET,
        PdiCommand.ASC2_SET,
        PdiCommand.ASC2_RX,
        enums=Asc2Action,
        dev_class=Acs2DeviceConfig,
    )
    AMC2 = DeviceWrapper(
        Amc2Req,
        PdiCommand.AMC2_GET,
        PdiCommand.AMC2_SET,
        PdiCommand.AMC2_RX,
        enums=Amc2Action,
        dev_class=Amc2DeviceConfig,
    )
    BPC2 = DeviceWrapper(
        Bpc2Req,
        PdiCommand.BPC2_GET,
        PdiCommand.BPC2_SET,
        PdiCommand.BPC2_RX,
        enums=Bpc2Action,
        dev_class=Bpc2DeviceConfig,
    )
    STM2 = DeviceWrapper(
        Stm2Req,
        PdiCommand.STM2_GET,
        PdiCommand.STM2_SET,
        PdiCommand.STM2_RX,
        enums=Stm2Action,
        dev_class=Stm2DeviceConfig,
    )
    UPDATE = DeviceWrapper(BaseReq)

    @classmethod
    def from_pdi_command(cls, cmd: PdiCommand) -> PdiDevice:
        return cls(cmd.name.split("_")[0].upper())

    @classmethod
    def from_data(cls, data: bytes) -> PdiDevice:
        return cls(PdiCommand(data[1]).name.split("_")[0].upper())

    @property
    def can_build_device(self) -> bool:
        return self.value.dev_class is not None

    def build_req(self, data: bytes | int, action: A = None) -> T:
        return self.value.build(data, action)

    def build_device(self, cmd: T) -> D:
        return self.value.dev_class(cmd)

    def firmware(self, tmcc_id: int) -> T:
        return self.value.firmware(tmcc_id)

    def config(self, tmcc_id: int) -> T:
        return self.value.config(tmcc_id)

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
            raise KeyError(f"Invalid device: {key}")
        # create the component state dict for this key
        self[key] = PdiDeviceDict(device)
        return self[key]

    def register_pdi_device(self, cmd: PdiReq) -> List[T] | None:
        if cmd.action.bits == CommonAction.CONFIG.bits:
            tmcc_id = cmd.tmcc_id
            device = cmd.pdi_device
            if device.can_build_device is True:
                dev_config = device.build_device(cmd)
                self[device][tmcc_id] = dev_config
                return dev_config.state_requests
        return None


class PdiDeviceDict(dict):
    def __init__(self, device: PdiDevice):
        super().__init__()  # base class doesn't get a factory
        self._device = device

    @property
    def device(self) -> PdiDevice:
        return self._device
