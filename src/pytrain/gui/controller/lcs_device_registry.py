#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
Declarative registry of the LCS modules the LCS configuration panel can program.

Each device is described by one :class:`LcsDevice` holding one :class:`LcsMode` per
supported configuration. A mode declares the Cab scope it is addressed in, how many
TMCC IDs (ports) it claims, the ``pdi_device`` mode index it corresponds to, and the
ordered recipe of Cab-remote presses that programs it.

Why the registry, and not the PDI request classes, owns scope and block size
---------------------------------------------------------------------------
The ASC2 supports four configurations (ACC eight-ID, ACC single-ID, SW momentary,
SW latching), but ``asc2_req.py`` L71 validates ``mode`` as 0-2 and rejects mode 3,
and ``num_addressable_ports`` (L126-134) raises for it. Worse, ``asc2_req.py`` L42
computes the scope as ``SWITCH if mode == 2 else ACC``, so a mode-3 (SW latching)
ASC2 is mis-scoped as an accessory. Per the agreed workaround, this module is left
alone: the panel never constructs an ``Asc2Req`` carrying a mode and never calls
``num_addressable_ports``. This registry is the single source of truth for a mode's
scope and block size. Read-back GETs carry no mode, so they are unaffected.

No Tk or guizero symbols are imported at module scope; the registry is pure data and
is unit-testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Mapping, Sequence

from ...pdi.irda_req import IrdaSequence
from ...pdi.pdi_device import PdiDevice
from ...protocol.command_def import CommandDefEnum
from ...protocol.command_req import CommandReq
from ...protocol.constants import CommandScope
from ...protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
    TMCC1SwitchCommandEnum,
)

MAX_TMCC_ID: int = 98

ACC_AUX_NUMBERS: tuple[CommandDefEnum, ...] = (
    TMCC1AuxCommandEnum.AUX_NUMBER_0,
    TMCC1AuxCommandEnum.AUX_NUMBER_1,
    TMCC1AuxCommandEnum.AUX_NUMBER_2,
    TMCC1AuxCommandEnum.AUX_NUMBER_3,
    TMCC1AuxCommandEnum.AUX_NUMBER_4,
    TMCC1AuxCommandEnum.AUX_NUMBER_5,
    TMCC1AuxCommandEnum.AUX_NUMBER_6,
    TMCC1AuxCommandEnum.AUX_NUMBER_7,
    TMCC1AuxCommandEnum.AUX_NUMBER_8,
    TMCC1AuxCommandEnum.AUX_NUMBER_9,
)

ENGINE_AUX_NUMBERS: tuple[CommandDefEnum, ...] = (
    TMCC1EngineCommandEnum.AUX_NUMBER_0,
    TMCC1EngineCommandEnum.AUX_NUMBER_1,
    TMCC1EngineCommandEnum.AUX_NUMBER_2,
    TMCC1EngineCommandEnum.AUX_NUMBER_3,
    TMCC1EngineCommandEnum.AUX_NUMBER_4,
    TMCC1EngineCommandEnum.AUX_NUMBER_5,
    TMCC1EngineCommandEnum.AUX_NUMBER_6,
    TMCC1EngineCommandEnum.AUX_NUMBER_7,
    TMCC1EngineCommandEnum.AUX_NUMBER_8,
    TMCC1EngineCommandEnum.AUX_NUMBER_9,
)


def aux_number(digit: int, scope: CommandScope) -> CommandDefEnum:
    """
    Return the ``AUX1`` + <digit> command for the given scope.
    """
    digit = int(getattr(digit, "value", digit)) if digit is not None else None
    if digit is None or not 0 <= digit <= 9:
        raise ValueError(f"Invalid AUX1 digit: {digit}")
    if scope == CommandScope.ACC:
        return ACC_AUX_NUMBERS[digit]
    elif scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
        return ENGINE_AUX_NUMBERS[digit]
    raise ValueError(f"AUX1-prefixed numerics are not supported for scope: {scope}")


class OptionKind(Enum):
    RADIO = auto()  # mutually exclusive -> CheckBoxGroup(style="radio")
    CHECKBOX = auto()  # independent flag


@dataclass(frozen=True)
class LcsOption:
    """
    One operator-settable option on a device's options page.
    """

    key: str
    label: str
    kind: OptionKind
    choices: tuple[tuple[str, Any], ...] = ()
    default: Any = None
    enabled: bool = True
    required: bool = False
    note: str | None = None


@dataclass(frozen=True)
class Press:
    """
    One Cab-remote gesture in a programming sequence.

    ``command`` is the command sent when the press is unconditional; when
    ``digit_from`` names an option key, the command is the ``AUX1`` + <digit>
    member for this press's scope, with the digit taken from that option's value.
    ``include_if`` names an option key whose truthy value gates the press.
    """

    label: str
    command: CommandDefEnum | None = None
    scope: CommandScope = CommandScope.ACC
    note: str | None = None
    include_if: str | None = None
    digit_from: str | None = None

    def is_included(self, options: Mapping[str, Any] | None = None) -> bool:
        if self.include_if is None:
            return True
        return bool((options or {}).get(self.include_if))

    def digit(self, options: Mapping[str, Any] | None = None) -> int | None:
        if self.digit_from is None:
            return None
        value = (options or {}).get(self.digit_from)
        if value is None:
            raise ValueError(f"Option '{self.digit_from}' is required")
        return int(getattr(value, "value", value))

    def resolve(self, options: Mapping[str, Any] | None = None) -> CommandDefEnum:
        if self.digit_from is not None:
            return aux_number(self.digit(options), self.scope)
        if self.command is None:
            raise ValueError(f"Press '{self.label}' declares no command")
        return self.command

    def resolved_label(self, options: Mapping[str, Any] | None = None) -> str:
        if self.digit_from is not None:
            return self.label.format(digit=self.digit(options))
        return self.label

    def build(self, base_id: int, options: Mapping[str, Any] | None = None) -> CommandReq:
        return CommandReq(self.resolve(options), address=base_id, scope=self.scope)


@dataclass(frozen=True)
class LcsMode:
    """
    One configuration (mode) of an LCS device.
    """

    key: str
    label: str
    scope: CommandScope
    ports: int
    pdi_mode: int | None
    presses: tuple[Press, ...]
    enabled: bool = True
    note: str | None = None

    @property
    def max_base(self) -> int:
        return max_base(self)


@dataclass(frozen=True)
class LcsDevice:
    """
    One programmable LCS module.
    """

    key: str
    label: str
    blurb: str
    pdi_device: PdiDevice
    modes: tuple[LcsMode, ...]
    options: tuple[LcsOption, ...] = ()
    program_button: str = "PGM"
    warning: str | None = None
    identifies_state: Callable[[Any], bool] = field(default=lambda _state: False, repr=False, compare=False)

    def mode(self, key: str) -> LcsMode:
        for mode in self.modes:
            if mode.key == key:
                return mode
        raise ValueError(f"No such {self.label} mode: {key}")

    def mode_for_pdi_mode(self, pdi_mode: int | None) -> LcsMode | None:
        for mode in self.modes:
            if mode.pdi_mode == pdi_mode:
                return mode
        return None

    def option(self, key: str) -> LcsOption:
        for option in self.options:
            if option.key == key:
                return option
        raise ValueError(f"No such {self.label} option: {key}")

    @property
    def default_mode(self) -> LcsMode:
        for mode in self.modes:
            if mode.enabled:
                return mode
        return self.modes[0]


def max_base(mode: LcsMode) -> int:
    """
    The highest base TMCC ID at which a module of this mode fits below ID 98.

    Reproduces the ASC2 flowchart exactly: 91 for an 8-port ACC mode, 95 for a
    4-port SW mode.
    """
    return min(MAX_TMCC_ID, (MAX_TMCC_ID + 1) - mode.ports)


def _sensor_track_choices() -> tuple[tuple[str, Any], ...]:
    """
    Build the Sensor Track Action Command choices from the labels the Sensor Track
    operating group already uses, so the two panels cannot drift apart.
    """
    try:
        from .engine_gui_conf import SENSOR_TRACK_OPTS
    except Exception:  # pragma: no cover - only when guizero is unavailable
        return tuple((seq.name.title().replace("_", " "), seq) for seq in IrdaSequence)
    return tuple((label, IrdaSequence(value)) for label, value in SENSOR_TRACK_OPTS)


#
# ASC2
#
ASC2 = LcsDevice(
    key="asc2",
    label="ASC2",
    blurb="ACC / SW",
    pdi_device=PdiDevice.ASC2,
    modes=(
        LcsMode(
            key="acc_8",
            label="Accessory, Eight ID",
            scope=CommandScope.ACC,
            ports=8,
            pdi_mode=0,
            note="Mixed accessories and lights",
            presses=(
                Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),
                Press("AUX1 then 0", TMCC1AuxCommandEnum.AUX_NUMBER_0, CommandScope.ACC, note="8-ID sub-mode"),
            ),
        ),
        LcsMode(
            key="acc_1",
            label="Accessory, Single ID",
            scope=CommandScope.ACC,
            ports=1,
            pdi_mode=1,
            note="Uncoupling tracks only; always momentary",
            presses=(
                Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),
                Press("AUX1 then 1", TMCC1AuxCommandEnum.AUX_NUMBER_1, CommandScope.ACC, note="1-ID sub-mode"),
            ),
        ),
        LcsMode(
            key="sw_momentary",
            label="Switch, momentary",
            scope=CommandScope.SWITCH,
            ports=4,
            pdi_mode=2,
            note="FasTrack and similar switch motors",
            presses=(
                Press("SW {id} SET", TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH),
                Press("AUX1", TMCC1SwitchCommandEnum.THRU, CommandScope.SWITCH, note="momentary"),
            ),
        ),
        LcsMode(
            key="sw_latching",
            label="Switch, latching",
            scope=CommandScope.SWITCH,
            ports=4,
            pdi_mode=3,
            note="Tortoise-style switch motors, constant power",
            presses=(
                Press("SW {id} SET", TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH),
                Press("AUX2", TMCC1SwitchCommandEnum.OUT, CommandScope.SWITCH, note="latching"),
            ),
        ),
    ),
    identifies_state=lambda state: bool(getattr(state, "is_asc2", False)),
)

#
# BPC2
#
_BPC2_RESTORE = LcsOption(
    key="restore",
    label="Restore last relay settings on power-up",
    kind=OptionKind.CHECKBOX,
    default=False,
)

BPC2 = LcsDevice(
    key="bpc2",
    label="BPC2",
    blurb="TR / ACC",
    pdi_device=PdiDevice.BPC2,
    warning="Configuring a BPC2 switches every track-block relay off; turn them back on afterwards.",
    modes=(
        LcsMode(
            key="tr_8",
            label="Track, 8 TMCC ID",
            scope=CommandScope.TRAIN,
            ports=8,
            pdi_mode=0,
            presses=(
                Press("TR {id} SET", TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN),
                Press(
                    "Coupler R",
                    TMCC1EngineCommandEnum.REAR_COUPLER,
                    CommandScope.TRAIN,
                    note="restore on",
                    include_if="restore",
                ),
                Press("AUX1 then 0", TMCC1EngineCommandEnum.AUX_NUMBER_0, CommandScope.TRAIN, note="8-ID sub-mode"),
            ),
        ),
        LcsMode(
            key="tr_1",
            label="Track, 1 TMCC ID",
            scope=CommandScope.TRAIN,
            ports=1,
            pdi_mode=1,
            enabled=False,
            note="reserved, no Cab support",
            presses=(Press("TR {id} SET", TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN),),
        ),
        LcsMode(
            key="acc_8",
            label="Accessory, 8 TMCC ID",
            scope=CommandScope.ACC,
            ports=8,
            pdi_mode=2,
            presses=(
                Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),
                Press(
                    "Coupler R",
                    TMCC1AuxCommandEnum.REAR_COUPLER,
                    CommandScope.ACC,
                    note="restore on",
                    include_if="restore",
                ),
                Press("AUX1 then 0", TMCC1AuxCommandEnum.AUX_NUMBER_0, CommandScope.ACC, note="8-ID sub-mode"),
            ),
        ),
        LcsMode(
            key="acc_1",
            label="Accessory, 1 TMCC ID",
            scope=CommandScope.ACC,
            ports=1,
            pdi_mode=3,
            enabled=False,
            note="reserved, no Cab support",
            presses=(Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),),
        ),
    ),
    options=(_BPC2_RESTORE,),
    identifies_state=lambda state: bool(getattr(state, "is_bpc2", False)),
)

#
# STM2
#
STM2 = LcsDevice(
    key="stm2",
    label="STM2",
    blurb="SW",
    pdi_device=PdiDevice.STM2,
    modes=(
        LcsMode(
            key="single_wire",
            label="Single-wire (up to 16 switches)",
            scope=CommandScope.SWITCH,
            ports=16,
            pdi_mode=0,
            note="Recommended",
            presses=(
                Press("SW {id} SET", TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH),
                Press("AUX1", TMCC1SwitchCommandEnum.THRU, CommandScope.SWITCH, note="single-wire"),
            ),
        ),
        LcsMode(
            key="two_wire",
            label="Two-wire (up to 8 switches)",
            scope=CommandScope.SWITCH,
            ports=8,
            pdi_mode=1,
            note="Atlas-style switch motors; half the switches",
            presses=(
                Press("SW {id} SET", TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH),
                Press("AUX2", TMCC1SwitchCommandEnum.OUT, CommandScope.SWITCH, note="two-wire"),
            ),
        ),
    ),
    identifies_state=lambda state: bool(getattr(state, "is_stm2", False)),
)

#
# Sensor Track
#
SENSOR_TRACK_ACTION = LcsOption(
    key="action",
    label="Action Command",
    kind=OptionKind.RADIO,
    choices=_sensor_track_choices(),
    default=IrdaSequence.NONE,
    required=True,
    note="The R➟L / L➟R engine ID filters are shown from the read-back, but are not written here.",
)

SENSOR_TRACK = LcsDevice(
    key="sensor_track",
    label="Sensor Track",
    blurb="ACC",
    pdi_device=PdiDevice.IRDA,
    program_button="PROGRAM",
    modes=(
        LcsMode(
            key="acc",
            label="Accessory ID and Action Command",
            scope=CommandScope.ACC,
            ports=1,
            pdi_mode=None,
            presses=(
                Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),
                Press(
                    "AUX1 then {digit}",
                    scope=CommandScope.ACC,
                    note="action command",
                    digit_from="action",
                ),
            ),
        ),
    ),
    options=(SENSOR_TRACK_ACTION,),
    identifies_state=lambda state: bool(getattr(state, "is_sensor_track", False)),
)

LCS_DEVICES: tuple[LcsDevice, ...] = (ASC2, BPC2, STM2, SENSOR_TRACK)


def device_for_key(key: str) -> LcsDevice:
    for device in LCS_DEVICES:
        if device.key == key:
            return device
    raise ValueError(f"No such LCS device: {key}")


def device_for_state(state: Any) -> LcsDevice | None:
    """
    Return the registry descriptor matching the given component state, if any.
    """
    if state is None:
        return None
    for device in LCS_DEVICES:
        try:
            if device.identifies_state(state):
                return device
        except Exception:  # pragma: no cover - defensive; states vary widely
            continue
    return None


def device_for_pdi_device(pdi_device: PdiDevice) -> LcsDevice | None:
    for device in LCS_DEVICES:
        if device.pdi_device == pdi_device:
            return device
    return None


def enabled_modes(device: LcsDevice) -> Sequence[LcsMode]:
    return tuple(mode for mode in device.modes if mode.enabled)
