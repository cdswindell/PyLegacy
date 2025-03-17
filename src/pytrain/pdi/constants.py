"""
Lionel PDI Command Protocol Constants
"""

from __future__ import annotations

from enum import IntEnum, Enum, unique

from ..protocol.constants import Mixins

# General constants
PDI_SOP: int = 0xD1
PDI_STF: int = 0xDE
PDI_EOP: int = 0xDF

# Keep-alive message
KEEP_ALIVE_CMD: bytes = bytes([0xD1, 0x29, 0xD7, 0xDF])

# Command Definitions
ALL_GET: int = 0x01
ALL_SET: int = 0x02

BASE_ENGINE: int = 0x20
BASE_TRAIN: int = 0x21
BASE_ACC: int = 0x22
BASE_BASE: int = 0x23
BASE_ROUTE: int = 0x24
BASE_SWITCH: int = 0x25
BASE_MEMORY: int = 0x26

TMCC_TX: int = 0x27
TMCC_RX: int = 0x28

PING: int = 0x29

UPDATE_ENGINE_SPEED: int = 0x2A
UPDATE_TRAIN_SPEED: int = 0x2B

TMCC4_TX: int = 0x2C
TMCC4_RX: int = 0x2D

IRDA_GET: int = 0x30
IRDA_SET: int = 0x31
IRDA_RX: int = 0x32

WIFI_GET: int = 0x34
WIFI_SET: int = 0x35
WIFI_RX: int = 0x36
WIFI_PING: int = 0x37

SER2_GET: int = 0x38
SER2_SET: int = 0x39
SER2_RX: int = 0x3A

ASC2_GET: int = 0x3C
ASC2_SET: int = 0x3D
ASC2_RX: int = 0x3E

BPC2_GET: int = 0x40
BPC2_SET: int = 0x41
BPC2_RX: int = 0x42

AMC2_GET: int = 0x44
AMC2_SET: int = 0x45
AMC2_RX: int = 0x46

STM2_GET: int = 0x4C
STM2_SET: int = 0x4D
STM2_RX: int = 0x4E

RF_RX = 0x72

BLE_RX = 0x76

BLOCK_GET: int = 0x90
BLOCK_SET: int = 0x91
BLOCK_RX: int = 0x92


class FriendlyMixins(Enum):
    @property
    def friendly(self) -> str:
        return self.name.title()


class PdiCommand(IntEnum, Mixins, FriendlyMixins):
    ALL_GET = ALL_GET
    ALL_SET = ALL_SET
    BASE_ENGINE = BASE_ENGINE
    BASE_TRAIN = BASE_TRAIN
    BASE_ACC = BASE_ACC
    BASE = BASE_BASE
    BASE_ROUTE = BASE_ROUTE
    BASE_SWITCH = BASE_SWITCH
    BASE_MEMORY = BASE_MEMORY
    TMCC_TX = TMCC_TX
    TMCC_RX = TMCC_RX
    TMCC4_TX = TMCC4_TX
    TMCC4_RX = TMCC4_RX
    PING = PING
    UPDATE_ENGINE_SPEED = UPDATE_ENGINE_SPEED
    UPDATE_TRAIN_SPEED = UPDATE_TRAIN_SPEED
    IRDA_GET = IRDA_GET
    IRDA_SET = IRDA_SET
    IRDA_RX = IRDA_RX
    WIFI_GET = WIFI_GET
    WIFI_SET = WIFI_SET
    WIFI_RX = WIFI_RX
    WIFI_PING = PING
    ASC2_GET = ASC2_GET
    ASC2_SET = ASC2_SET
    ASC2_RX = ASC2_RX
    SER2_GET = SER2_GET
    SER2_SET = SER2_SET
    SER2_RX = SER2_RX
    BPC2_GET = BPC2_GET
    BPC2_SET = BPC2_SET
    BPC2_RX = BPC2_RX
    STM2_GET = STM2_GET
    STM2_SET = STM2_SET
    STM2_RX = STM2_RX
    RF_RX = RF_RX
    BLE_RX = BLE_RX
    BLOCK_GET = BLOCK_GET
    BLOCK_SET = BLOCK_SET
    BLOCK_RX = BLOCK_RX

    @property
    def is_ping(self) -> bool:
        return self.value == PING

    @property
    def is_tmcc(self) -> bool:
        return self.value in {TMCC_TX, TMCC_RX, TMCC4_TX, TMCC4_RX}

    @property
    def is_base(self) -> bool:
        return self.value in {
            BASE_ENGINE,
            BASE_TRAIN,
            BASE_ACC,
            BASE_BASE,
            BASE_ROUTE,
            BASE_SWITCH,
            BASE_MEMORY,
            UPDATE_ENGINE_SPEED,
            UPDATE_TRAIN_SPEED,
        }

    @property
    def is_get(self) -> bool:
        return self.name.endswith("_GET")

    @property
    def is_set(self) -> bool:
        return self.name.endswith("_SET")

    @property
    def is_receive(self) -> bool:
        return self.name.endswith("_RX")

    @property
    def is_sendable(self) -> bool:
        return self.is_base or self.is_get or self.is_set

    @property
    def is_receivable(self) -> bool:
        return self.is_receive

    @property
    def is_irda(self) -> bool:
        return self.value in {IRDA_GET, IRDA_SET, IRDA_RX}

    @property
    def is_wifi(self) -> bool:
        return self.value in {WIFI_GET, WIFI_SET, WIFI_RX, WIFI_PING}

    @property
    def is_asc2(self) -> bool:
        return self.value in {ASC2_GET, ASC2_SET, ASC2_RX}

    @property
    def is_stm2(self) -> bool:
        return self.value in {STM2_GET, STM2_SET, STM2_RX}

    @property
    def is_ser2(self) -> bool:
        return self.value in {SER2_GET, SER2_SET, SER2_RX}

    @property
    def is_bpc2(self) -> bool:
        return self.value in {BPC2_GET, BPC2_SET, BPC2_RX}

    @property
    def is_block(self) -> bool:
        return self.value in {BLOCK_GET, BLOCK_SET, BLOCK_RX}

    @property
    def is_lcs(self) -> bool:
        return self.is_wifi or self.is_asc2 or self.is_irda or self.is_ser2 or self.is_bpc2 or self.is_stm2

    @property
    def as_bytes(self) -> bytes:
        return self.value.to_bytes(1)


class ActionDef:
    def __init__(self, bits: int, gettable: bool, settable: bool, responds: bool) -> None:
        self._bits = bits
        self._gettable = gettable
        self._settable = settable
        self._responds = responds

    @property
    def bits(self) -> int:
        return self._bits

    @property
    def is_gettable(self) -> bool:
        return self._gettable

    @property
    def is_settable(self) -> bool:
        return self._settable

    @property
    def is_responses(self) -> bool:
        return self._responds


@unique
class PdiAction(Mixins, FriendlyMixins):
    """
    Marker interface for all Pdi Action enums
    """

    def __repr__(self) -> str:
        opts = ""
        opts += "g" if self.value.is_gettable else "x"
        opts += "s" if self.value.is_settable else "x"
        opts += "r" if self.value.is_responses else "x"
        return f"{self.name.title()} [{opts}]"

    @property
    def bits(self) -> int | None:
        if hasattr(self.value, "bits"):
            return self.value.bits
        else:
            return None

    @property
    def is_config(self) -> bool:
        return self.bits == CommonAction.CONFIG.bits

    @property
    def as_bytes(self) -> bytes:
        return self.bits.to_bytes(1, byteorder="big")


ACTION_FIRMWARE: int = 0x01
ACTION_STATUS: int = 0x02
ACTION_CONFIG: int = 0x03
ACTION_INFO: int = 0x04
ACTION_CLEAR_ERRORS: int = 0x05
ACTION_RESET: int = 0x06
ACTION_IDENTIFY: int = 0x07


@unique
class CommonAction(PdiAction):
    FIRMWARE = ActionDef(ACTION_FIRMWARE, True, False, True)
    STATUS = ActionDef(ACTION_STATUS, True, False, True)
    CONFIG = ActionDef(ACTION_CONFIG, True, True, True)
    INFO = ActionDef(ACTION_INFO, True, False, True)
    CLEAR_ERRORS = ActionDef(ACTION_CLEAR_ERRORS, False, True, False)
    RESET = ActionDef(ACTION_RESET, False, True, False)
    IDENTIFY = ActionDef(ACTION_IDENTIFY, False, True, False)


ACTION_WIFI_CONNECT: int = 0x10
ACTION_WIFI_IP: int = 0x11
ACTION_WIFI_RESPBCASTS: int = 0x12
ACTION_WIFI_UNLOCK: int = 0x13
ACTION_WIFI_PASSCODE: int = 0x14


@unique
class WiFiAction(PdiAction):
    FIRMWARE = ActionDef(ACTION_FIRMWARE, True, False, True)
    STATUS = ActionDef(ACTION_STATUS, True, False, True)
    CONFIG = ActionDef(ACTION_CONFIG, True, True, True)
    INFO = ActionDef(ACTION_INFO, True, False, True)
    CLEAR_ERRORS = ActionDef(ACTION_CLEAR_ERRORS, False, True, False)
    RESET = ActionDef(ACTION_RESET, False, True, False)
    IDENTIFY = ActionDef(ACTION_IDENTIFY, False, True, False)
    CONNECT = ActionDef(ACTION_WIFI_CONNECT, True, False, True)
    IP = ActionDef(ACTION_WIFI_IP, True, False, True)
    RESPBCASTS = ActionDef(ACTION_WIFI_RESPBCASTS, True, True, True)
    UNLOCK = ActionDef(ACTION_WIFI_UNLOCK, False, True, True)
    PASSCODE = ActionDef(ACTION_WIFI_PASSCODE, True, True, True)


ACTION_DATA: int = 0x10
ACTION_SEQUENCE: int = 0x11
ACTION_RECORD: int = 0x12
ACTION_DIAG_DATA: int = 0x13


@unique
class IrdaAction(PdiAction):
    FIRMWARE = ActionDef(ACTION_FIRMWARE, True, False, True)
    STATUS = ActionDef(ACTION_STATUS, True, False, True)
    CONFIG = ActionDef(ACTION_CONFIG, True, True, True)
    INFO = ActionDef(ACTION_INFO, True, False, True)
    CLEAR_ERRORS = ActionDef(ACTION_CLEAR_ERRORS, False, True, False)
    RESET = ActionDef(ACTION_RESET, False, True, False)
    IDENTIFY = ActionDef(ACTION_IDENTIFY, False, True, False)
    DATA = ActionDef(ACTION_DATA, False, False, True)
    SEQUENCE = ActionDef(ACTION_SEQUENCE, True, True, True)
    RECORD = ActionDef(ACTION_RECORD, True, True, True)
    DIAG_DATA = ActionDef(ACTION_DIAG_DATA, True, True, True)


ACTION_CONTROL1: int = 0x10
ACTION_CONTROL2: int = 0x11
ACTION_CONTROL3: int = 0x12
ACTION_CONTROL4: int = 0x14
ACTION_CONTROL5: int = 0x15


@unique
class Asc2Action(PdiAction):
    FIRMWARE = ActionDef(ACTION_FIRMWARE, True, False, True)
    STATUS = ActionDef(ACTION_STATUS, True, False, True)
    CONFIG = ActionDef(ACTION_CONFIG, True, True, True)
    INFO = ActionDef(ACTION_INFO, True, False, True)
    CLEAR_ERRORS = ActionDef(ACTION_CLEAR_ERRORS, False, True, False)
    RESET = ActionDef(ACTION_RESET, False, True, False)
    IDENTIFY = ActionDef(ACTION_IDENTIFY, False, True, False)
    CONTROL1 = ActionDef(ACTION_CONTROL1, True, True, True)
    CONTROL2 = ActionDef(ACTION_CONTROL2, True, True, True)
    CONTROL3 = ActionDef(ACTION_CONTROL3, True, True, True)
    CONTROL4 = ActionDef(ACTION_CONTROL4, True, True, True)
    CONTROL5 = ActionDef(ACTION_CONTROL5, True, True, True)


ACTION_MOTOR: int = 0x10
ACTION_LAMP: int = 0x11
ACTION_MOTOR_CONFIG: int = 0x12


@unique
class Amc2Action(PdiAction):
    FIRMWARE = ActionDef(ACTION_FIRMWARE, True, False, True)
    STATUS = ActionDef(ACTION_STATUS, True, False, True)
    CONFIG = ActionDef(ACTION_CONFIG, True, True, True)
    INFO = ActionDef(ACTION_INFO, True, False, True)
    CLEAR_ERRORS = ActionDef(ACTION_CLEAR_ERRORS, False, True, False)
    RESET = ActionDef(ACTION_RESET, False, True, False)
    IDENTIFY = ActionDef(ACTION_IDENTIFY, False, True, False)
    MOTOR = ActionDef(ACTION_MOTOR, True, True, True)
    LAMP = ActionDef(ACTION_LAMP, True, True, True)
    MOTOR_CONFIG = ActionDef(ACTION_MOTOR_CONFIG, True, True, True)


@unique
class Ser2Action(PdiAction):
    FIRMWARE = ActionDef(ACTION_FIRMWARE, True, False, True)
    STATUS = ActionDef(ACTION_STATUS, True, False, True)
    CONFIG = ActionDef(ACTION_CONFIG, True, True, True)
    INFO = ActionDef(ACTION_INFO, True, False, True)
    CLEAR_ERRORS = ActionDef(ACTION_CLEAR_ERRORS, False, True, False)
    RESET = ActionDef(ACTION_RESET, False, True, False)
    IDENTIFY = ActionDef(ACTION_IDENTIFY, False, True, False)


ACTION_CONTROL4_BPC2: int = 0x13


@unique
class Bpc2Action(PdiAction):
    FIRMWARE = ActionDef(ACTION_FIRMWARE, True, False, True)
    STATUS = ActionDef(ACTION_STATUS, True, False, True)
    CONFIG = ActionDef(ACTION_CONFIG, True, True, True)
    INFO = ActionDef(ACTION_INFO, True, False, True)
    CLEAR_ERRORS = ActionDef(ACTION_CLEAR_ERRORS, False, True, False)
    RESET = ActionDef(ACTION_RESET, False, True, False)
    IDENTIFY = ActionDef(ACTION_IDENTIFY, False, True, False)
    CONTROL1 = ActionDef(ACTION_CONTROL1, True, True, True)
    CONTROL2 = ActionDef(ACTION_CONTROL2, True, True, True)
    CONTROL3 = ActionDef(ACTION_CONTROL3, True, True, True)
    CONTROL4 = ActionDef(ACTION_CONTROL4_BPC2, True, True, True)


@unique
class Stm2Action(PdiAction):
    FIRMWARE = ActionDef(ACTION_FIRMWARE, True, False, True)
    STATUS = ActionDef(ACTION_STATUS, True, False, True)
    CONFIG = ActionDef(ACTION_CONFIG, True, True, True)
    INFO = ActionDef(ACTION_INFO, True, False, True)
    CLEAR_ERRORS = ActionDef(ACTION_CLEAR_ERRORS, False, True, False)
    RESET = ActionDef(ACTION_RESET, False, True, False)
    IDENTIFY = ActionDef(ACTION_IDENTIFY, False, True, False)
    CONTROL1 = ActionDef(ACTION_CONTROL1, True, False, True)


ALL_FIRMWARE = {
    Asc2Action.FIRMWARE,
    Amc2Action.FIRMWARE,
    Bpc2Action.FIRMWARE,
    IrdaAction.FIRMWARE,
    Ser2Action.FIRMWARE,
    Stm2Action.FIRMWARE,
    Stm2Action.FIRMWARE,
    WiFiAction.FIRMWARE,
}

ALL_STATUS = {
    Asc2Action.STATUS,
    Amc2Action.STATUS,
    Bpc2Action.STATUS,
    IrdaAction.STATUS,
    Ser2Action.STATUS,
    Stm2Action.STATUS,
    Stm2Action.STATUS,
    WiFiAction.STATUS,
}

ALL_CONFIG = {
    Asc2Action.CONFIG,
    Amc2Action.CONFIG,
    Bpc2Action.CONFIG,
    IrdaAction.CONFIG,
    Ser2Action.CONFIG,
    Stm2Action.CONFIG,
    Stm2Action.CONFIG,
    WiFiAction.CONFIG,
}

ALL_INFO = {
    Asc2Action.INFO,
    Amc2Action.INFO,
    Bpc2Action.INFO,
    IrdaAction.INFO,
    Ser2Action.INFO,
    Stm2Action.INFO,
    Stm2Action.INFO,
    WiFiAction.INFO,
}

ALL_RESET = {
    Asc2Action.RESET,
    Amc2Action.RESET,
    Bpc2Action.RESET,
    IrdaAction.RESET,
    Ser2Action.RESET,
    Stm2Action.RESET,
    Stm2Action.RESET,
    WiFiAction.RESET,
}

ALL_IDENTIFY = {
    Asc2Action.IDENTIFY,
    Amc2Action.IDENTIFY,
    Bpc2Action.IDENTIFY,
    IrdaAction.IDENTIFY,
    Ser2Action.IDENTIFY,
    Stm2Action.IDENTIFY,
    Stm2Action.IDENTIFY,
    WiFiAction.IDENTIFY,
}

ALL_RXs = {e for e in PdiCommand if e.name.endswith("_RX")}
ALL_SETs = {e for e in PdiCommand if e.name.endswith("_SET")}
ALL_GETs = {e for e in PdiCommand if e.name.endswith("_GET")}
