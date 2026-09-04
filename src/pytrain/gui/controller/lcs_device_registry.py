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

Each device is described by one LcsDevice holding one LcsMode per supported configuration.
A mode declares the Cab scope it is addressed in, how many TMCC IDs (ports) it claims,
the pdi_device mode index it corresponds to, and the ordered recipe of Cab-remote
presses that programs it.

Why the registry, and not the PDI request classes, owns scope and block size
---------------------------------------------------------------------------
The ASC2 supports four configurations (ACC eight-ID, ACC single-ID, SW pulse,
SW latching), but asc2_req.py L71 validates mode as 0-2 and rejects mode 3,
and num_addressable_ports (L126-134) raises for it. Worse, asc2_req.py L42
computes the scope as SWITCH if mode == 2 else ACC, so a mode-3 (SW latching)
ASC2 is mis-scoped as an accessory. Per the agreed workaround, this module is left
alone: the panel never constructs an Asc2Req carrying a mode and never calls
num_addressable_ports. This registry is the single source of truth for a mode's
scope and block size. Read-back GETs carry no mode, so they are unaffected.

How a mode is named and labeled
-------------------------------
A mode's name opens with the Cab-remote key that begins its programming sequence,
spelled the way the key itself is: ACC, SW, TR. Whatever tells the mode from
the module's other modes on that key follows it in parentheses -- (pulse),
(latching), (single-wire), (uncouple). The key is what the operator presses,
so it stands at the head of the row unadorned, and the qualifier reads as the aside it is;
the footnote below the panel's Mode radios is keyed by those same words. The name alone
says nothing about how many addresses the mode claims, and what is counted is always
TMCC IDs, never bare "IDs" or "ports".

A qualifier is one word wherever one will do, because a radio row is as wide as its label
(see below), so it can rarely say more than *which* mode this is. What the mode is good
for is said by LcsMode.note, which the panel prints below the radios keyed by that same
word -- "uncouple: Uncoupling tracks only ..." -- so the qualifier needs only be the word
the sentence can be looked up under.

Two labels are built from it, both here rather than in the panel, so the wording is
settled in one file and testable without a display:

* LcsMode.ids_label() names the TMCC IDs the mode would claim from an address the
  operator has entered: "ACC TMCC IDs 1 - 8". This is what the panel's Mode radios read.
  Choosing a mode is reserving those addresses on the layout, so the radio says which
  ones rather than leaving a count to be added to the ID on the screen above it.
* LcsMode.ports_label names the count instead: "ACC, 8 TMCC IDs". For the lines
  that name a mode with no address in hand -- the modes a module reserves, and the
  summary of what is about to be programmed.

Either way the mode names what it consumes, because that is what the operator has to set
aside, and a mode that only says "(pulse)" leaves them guessing.

Neither label says anything else, and no name carries more than a key and one qualifier.
A radio row is as wide as its label, and the panel is a portrait pane: the widest row any
module can ask for -- the STM2's "SW (single-wire) TMCC IDs 83 - 98" -- takes 671 px of
the 714 px the pane gives it at the Pi's 1.5x font scale. Whatever a mode does besides
claiming addresses is said on the options page that follows, where it is chosen; see the
Sensor Track's Action Command.

Modules the panel knows without being able to program them
----------------------------------------------------------
A device with configurable=False is listed here so that the rest of the panel can
*recognize* it -- name it and account for the TMCC IDs it holds -- while it is kept off
the device selection page, because no press sequence for it has been written yet. The
AMC2 was the standing example: it answers to a TMCC ID on a real layout, so leaving it out
altogether made lcs_id_map silently blind to it, and the panel reported an address as
free when a module was sitting on it. Its modes and presses have since been filled in and
the flag dropped, which was the whole of what it took -- nothing else had to change -- so
no module carries the flag today. The mechanism stays for the next module that is met on
a layout before its manual has been read.

Modes a module has that the panel will not offer
------------------------------------------------
A mode with enabled=False is recorded but kept off the Mode radios, and there are two
quite different reasons for it. The BPC2's single-ID modes are reserved by its own manual:
the module reports them, but no Cab sequence programs one. The AMC2's TR and ENG modes are
real and the manual documents programming them -- "choose whichever suits your layout
best" -- but nothing else in PyTrain drives an AMC2 addressed as a train or an engine, and
the panel will not put a module somewhere the rest of the program cannot follow it.

Either way the mode is written down rather than left out, because recognizing a module is
the other half of this file's job: a module already out on a key the panel cannot program
still holds its addresses, and its mode byte still has to be understood to know which key
those addresses are on. Each says why it is not offered in its note.

How a digit is pressed
----------------------
Where a manual says "press AUX1, then 1", two keys are sent: the AUX key, and then the
number key. The TMCC1 enums do carry AUX1-prefixed numeric members -- and those are what
this file used to name -- but they are one command that emits its own prefix, twice, and
there is no AUX2-prefixed member at all. A module whose second output is programmed under
AUX2 could therefore not be spelled here, which is where the AMC2's motor 2 stood. A press
that enters a digit names the AUX key it is entered under and where the digit comes from,
and builds the pair; see Press.

No Tk or guizero symbols are imported at module scope; the registry is pure data and
is unit-testable in isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Mapping, Sequence

from ...pdi.amc2_req import AccessType, OutputType
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

# The two keys a digit is entered with, per remote key namespace: the AUX button, then the
# number. An engine and a train are the same handset keys, which is why they name the same
# pair; see "How a digit is pressed" above for why the AUX1-prefixed numeric commands are
# not used. A scope missing from either map has no such gesture at all -- a switch is
# programmed with THRU and OUT rather than with numbers.
AUX_KEYS: dict[CommandScope, tuple[CommandDefEnum, CommandDefEnum]] = {
    CommandScope.ACC: (TMCC1AuxCommandEnum.AUX1_OPT_ONE, TMCC1AuxCommandEnum.AUX2_OPT_ONE),
    CommandScope.ENGINE: (TMCC1EngineCommandEnum.AUX1_OPTION_ONE, TMCC1EngineCommandEnum.AUX2_OPTION_ONE),
    CommandScope.TRAIN: (TMCC1EngineCommandEnum.AUX1_OPTION_ONE, TMCC1EngineCommandEnum.AUX2_OPTION_ONE),
}

NUMBER_KEYS: dict[CommandScope, CommandDefEnum] = {
    CommandScope.ACC: TMCC1AuxCommandEnum.NUMERIC,
    CommandScope.ENGINE: TMCC1EngineCommandEnum.NUMERIC,
    CommandScope.TRAIN: TMCC1EngineCommandEnum.NUMERIC,
}


def aux_key(key: int, scope: CommandScope) -> CommandDefEnum:
    """
    Return the AUX1 (key 1) or AUX2 (key 2) button as the given scope's handset sends it.
    """
    keys = AUX_KEYS.get(scope)
    if keys is None:
        raise ValueError(f"AUX keys are not supported for scope: {scope}")
    if key not in (1, 2):
        raise ValueError(f"Invalid AUX key: {key}")
    return keys[key - 1]


def number_key(digit: int, scope: CommandScope) -> tuple[CommandDefEnum, int]:
    """Return the number key command for the given scope, with the digit it carries.

    The command is the same for every digit -- a number key is one command carrying the
    number as its data -- so both halves are returned together and neither can be sent
    without the other.
    """
    digit = int(getattr(digit, "value", digit)) if digit is not None else None
    if digit is None or not 0 <= digit <= 9:
        raise ValueError(f"Invalid number key: {digit}")
    command = NUMBER_KEYS.get(scope)
    if command is None:
        raise ValueError(f"Number keys are not supported for scope: {scope}")
    return command, digit


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
    # What the module's own CONFIG record calls this setting, where that is not what the
    # panel calls it. An option's key names what it *sets* -- the press it drives, and the
    # word a press is gated on or takes its digit from -- while a module reports the field
    # in its own terms: the Sensor Track's Action Command is pressed as an AUX1 digit and
    # reported as IrdaReq.sequence. A dotted path where the module reports it one level
    # down, as the AMC2 does on each of its motors. Left None wherever the two words agree,
    # which is the usual case; see reported_as and reported_by.
    reported_key: str | None = None

    @property
    def reported_as(self) -> str:
        """
        The field a module's record reports this option on: its own key unless one is named.
        """
        return self.reported_key or self.key

    def reported_by(self, record: Any) -> Any:
        """What the given record says this option is set to, or None where it says nothing.

        The field is a path rather than a bare name, because a module may report a setting
        one level down from the record it answers with: an AMC2 reports each motor's own
        output type and remember flag on the motor itself -- motor1.output_type -- and does
        so identically on its CONFIG packet and on the AccessoryState built from it, so one
        path reads either. A step that answers nothing ends the walk, which is what a record
        of the wrong flavor, or one built from a GET that carries no motors, does.
        """
        value = record
        for name in self.reported_as.split("."):
            if value is None:
                return None
            value = getattr(value, name, None)
        return value


@dataclass(frozen=True)
class Press:
    """One Cab-remote gesture in a programming sequence.

    command is the command sent when the gesture is a single key. A gesture that enters a
    digit names the AUX key it is entered under (aux) and where the digit comes from --
    digit_value for one the mode always sends, digit_from for one taken from an option's
    value -- and is two keys rather than one, which is what build() returns. See "How a
    digit is pressed" in this module's docstring.

    include_if names an option key whose truthy value gates the whole gesture.
    """

    label: str
    command: CommandDefEnum | None = None
    scope: CommandScope = CommandScope.ACC
    note: str | None = None
    include_if: str | None = None
    aux: int | None = None
    digit_value: int | None = None
    digit_from: str | None = None
    # What the handset's own numbering adds to the value the module reports. The AMC2's
    # motor modes are pressed as 1, 2 and 3 and reported as OutputType 0, 1 and 2 -- the
    # same three modes counted from a different end -- so the option holds what the module
    # says and the press spells what the operator taps. Read only with digit_from: a digit
    # the mode always sends is written as the key it is.
    digit_offset: int = 0

    def is_included(self, options: Mapping[str, Any] | None = None) -> bool:
        if self.include_if is None:
            return True
        return bool((options or {}).get(self.include_if))

    def digit(self, options: Mapping[str, Any] | None = None) -> int | None:
        if self.digit_from is None:
            return self.digit_value
        value = (options or {}).get(self.digit_from)
        if value is None:
            raise ValueError(f"Option '{self.digit_from}' is required")
        return int(getattr(value, "value", value)) + self.digit_offset

    def keys(self, options: Mapping[str, Any] | None = None) -> tuple[tuple[CommandDefEnum, int], ...]:
        """
        The keys this gesture presses, in order, each with the data it carries.
        """
        digit = self.digit(options)
        pressed: list[tuple[CommandDefEnum, int]] = []
        # Each half stands on its own, so a gesture that is an AUX key and nothing else
        # presses that key rather than quietly pressing nothing.
        if self.aux is not None:
            pressed.append((aux_key(self.aux, self.scope), 0))
        if digit is not None:
            pressed.append(number_key(digit, self.scope))
        if pressed:
            return tuple(pressed)
        if self.command is None:
            raise ValueError(f"Press '{self.label}' declares no command")
        return ((self.command, 0),)

    def resolved_label(self, options: Mapping[str, Any] | None = None) -> str:
        # The digit alone, by name: a label carries the address as a placeholder too, and
        # that one is the caller's to fill in, so formatting the whole label here would fail
        # on it. See lcs_sequence_builder._press_text.
        if "{digit}" not in self.label:
            return self.label
        return self.label.replace("{digit}", str(self.digit(options)))

    def build(self, base_id: int, options: Mapping[str, Any] | None = None) -> tuple[CommandReq, ...]:
        """
        The requests this gesture sends: one per key, so an AUX key and its digit are two.
        """
        return tuple(
            CommandReq(command, address=base_id, data=data, scope=self.scope) for command, data in self.keys(options)
        )


@dataclass(frozen=True)
class LcsMode:
    """
    One configuration (mode) of an LCS device.
    """

    key: str
    name: str
    scope: CommandScope
    ports: int
    pdi_mode: int | None
    presses: tuple[Press, ...]
    enabled: bool = True
    # What this mode is for, in the operator's terms, said in one line: the panel prints
    # it below the Mode radios once the mode is chosen, keyed by the mode's qualifier, and
    # a mode the panel cannot offer says it in the "Not available:" line instead.
    note: str | None = None

    @property
    def max_base(self) -> int:
        return max_base(self)

    @property
    def qualifier(self) -> str | None:
        """The parenthesized word that tells this mode from the module's others on its key.

        "pulse" from "SW (pulse)"; None for a mode named by its key alone. What the panel's
        footnote keys note by, so the sentence below the radios is looked up under
        the very word the row it explains carries.
        """
        match = re.search(r"\(([^)]+)\)", self.name)
        return match.group(1) if match else None

    @property
    def ports_label(self) -> str:
        """
        The mode and the number of TMCC IDs it claims: "ACC, 8 TMCC IDs".
        """
        return f"{self.name}, {tmcc_id_count(self.ports)}"

    def ids_label(self, base_id: int) -> str:
        """The mode and the TMCC IDs it would claim from base_id.

        base_id is clamped into the range this mode can actually be based at, so the label
        promises a block the mode can hold: an 8-ID mode offered beside the 4-ID one
        currently chosen at 95 reads "91 - 98", which is where selecting it lands.
        """
        base = min(max(int(base_id), 1), self.max_base)
        return f"{self.name} {tmcc_id_text(base, base + self.ports - 1)}"


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
    # False for a module the panel can name but not yet program; it is recognized on the
    # layout and holds TMCC IDs, but it is not offered on the device selection page.
    configurable: bool = True
    # What this module's own records call the byte that says which mode it is in, where
    # that is not "mode". Every module but the AMC2 publishes a bare mode byte; the AMC2
    # reports which of the three address types it answers to as access_type, an AccessType
    # rather than a number. Named here for the same reason an option names its own field:
    # what a module calls a thing is a fact about the module. See reported_mode().
    reported_mode_key: str | None = None
    identifies_state: Callable[[Any], bool] = field(default=lambda _state: False, repr=False, compare=False)

    @property
    def reported_mode_as(self) -> str:
        """
        The field this module reports its mode on: "mode" unless another is named.
        """
        return self.reported_mode_key or "mode"

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
        if not self.modes:
            raise ValueError(f"{self.label} declares no modes; it cannot be programmed here")
        return self.modes[0]


def max_base(mode: LcsMode) -> int:
    """
    The highest base TMCC ID at which a module of this mode fits below ID 98.

    Reproduces the ASC2 flowchart exactly: 91 for an 8-port ACC mode, 95 for a
    4-port SW mode.
    """
    return min(MAX_TMCC_ID, (MAX_TMCC_ID + 1) - mode.ports)


def reported_mode(device: LcsDevice, record: Any) -> int | None:
    """The mode byte a record reports for this module, or None where it reports none.

    Read on the field the module names rather than on "mode", and unwrapped where the module
    reports it as an enum member: an AMC2 answers with an AccessType. What comes back is
    matched against the modes' pdi_mode, so a module is only ever asked what it says about
    itself; see LcsDevice.reported_mode_as.

    A bool is not a mode. It is an int in Python, and a record read for a field that turns
    out to be a flag would otherwise be understood as reporting mode 0 or mode 1.
    """
    value = getattr(record, device.reported_mode_as, None) if record is not None else None
    value = getattr(value, "value", value)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def tmcc_id_span(base_id: int, last_id: int | None = None) -> str:
    """The addresses a block covers, as the numbers alone: "12 - 19", or "12" for one of them.

    What tmcc_id_text says with the words in front of it, and what a line already naming
    the remote key itself says instead -- "ACC 12 - 19" -- so the one place that decides
    when a block collapses to a single address serves both.
    """
    if last_id is None or last_id <= base_id:
        return f"{base_id}"
    return f"{base_id} - {last_id}"


def tmcc_id_text(base_id: int, last_id: int | None = None) -> str:
    """The addresses a block covers: "TMCC IDs 12 - 19", or "TMCC ID 12" for one of them.

    The one spelling of a block in the panel, whether it is a mode being offered or a
    module already out on the layout, so the Mode radios and the Currently Assigned rows
    cannot come to name the same eight addresses two different ways.
    """
    plural = "s" if last_id is not None and last_id > base_id else ""
    return f"TMCC ID{plural} {tmcc_id_span(base_id, last_id)}"


def tmcc_id_count(ports: int) -> str:
    """
    How many addresses something claims: "8 TMCC IDs", or "1 TMCC ID" for one of them.
    """
    return f"{ports} TMCC ID" if ports == 1 else f"{ports} TMCC IDs"


def _sensor_track_choices() -> tuple[tuple[str, Any], ...]:
    """
    Build the Sensor Track Action Command choices from the labels the Sensor Track
    operating group already uses, so the two panels cannot drift apart.
    """
    # noinspection PyBroadException
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
            name="ACC (mixed)",
            scope=CommandScope.ACC,
            ports=8,
            pdi_mode=0,
            note="Mixed accessories and lights",
            presses=(
                Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),
                Press("AUX1 then {digit}", scope=CommandScope.ACC, aux=1, digit_value=0, note="8-ID sub-mode"),
            ),
        ),
        LcsMode(
            key="acc_1",
            # The two accessory modes are the pair whose purpose the operator cannot guess
            # from the block each claims -- eight addresses for whatever is wired to them,
            # against a single address driving all eight outputs for uncoupling tracks --
            # so each is qualified by what it is *for* rather than by the count. The row's
            # tail already says how many addresses the mode takes, and the note below the
            # radios, keyed by the same word, says the rest.
            name="ACC (uncouple)",
            scope=CommandScope.ACC,
            ports=1,
            pdi_mode=1,
            note="Uncoupling tracks only - pulsed output (fixed)",
            presses=(
                Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),
                Press("AUX1 then {digit}", scope=CommandScope.ACC, aux=1, digit_value=1, note="1-ID sub-mode"),
            ),
        ),
        LcsMode(
            # The key keeps the word the PDI mode is known by -- asc2_req.py scopes mode 2
            # as SWITCH, and the ASC2 flowchart calls it momentary -- while the operator
            # reads "pulse", which is what the switch motor is actually given.
            key="sw_momentary",
            name="SW (pulse)",
            scope=CommandScope.SWITCH,
            ports=4,
            pdi_mode=2,
            note="FasTrack and similar switch motors",
            presses=(
                Press("SW {id} SET", TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH),
                Press("AUX1", TMCC1SwitchCommandEnum.THRU, CommandScope.SWITCH, note="pulse"),
            ),
        ),
        LcsMode(
            key="sw_latching",
            name="SW (latching)",
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
    blurb="ACC / TR",
    pdi_device=PdiDevice.BPC2,
    warning="Configuring a BPC2 switches every track-block relay off; turn them back on afterwards.",
    # ACC before TR, though the manual numbers the modes the other way about: the two
    # addressing modes are identical in what they can do, so the order is a presentation
    # choice, and ACC is the one an operator reaches for -- and, being first, the row the
    # page opens on where the layout has nothing to say. The PDI mode bytes are what tie a
    # row to a mode, not its place here.
    modes=(
        LcsMode(
            key="acc_8",
            name="ACC",
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
                Press("AUX1 then {digit}", scope=CommandScope.ACC, aux=1, digit_value=0, note="8-ID sub-mode"),
            ),
        ),
        LcsMode(
            key="acc_1",
            name="ACC",
            scope=CommandScope.ACC,
            ports=1,
            pdi_mode=3,
            enabled=False,
            note="reserved, no Cab support",
            presses=(Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),),
        ),
        LcsMode(
            key="tr_8",
            name="TR",
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
                Press("AUX1 then {digit}", scope=CommandScope.TRAIN, aux=1, digit_value=0, note="8-ID sub-mode"),
            ),
        ),
        LcsMode(
            key="tr_1",
            name="TR",
            scope=CommandScope.TRAIN,
            ports=1,
            pdi_mode=1,
            enabled=False,
            note="reserved, no Cab support",
            presses=(Press("TR {id} SET", TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN),),
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
            name="SW (single-wire)",
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
            name="SW (two-wire)",
            scope=CommandScope.SWITCH,
            ports=8,
            pdi_mode=1,
            note="Atlas-style switch motors",
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
    # The manual calls it the Action Command, and the presses still say so where the remote
    # is being described; the heading over the rows says the one word. It is read directly
    # under "Sensor Track: Configuring as ACC n" with the ten actions under it, so "Command"
    # names nothing the page has not already said -- and the page is the one place in the
    # panel where every pixel of height is already spoken for; see LONG_OPTION_PAGE.
    label="Action",
    kind=OptionKind.RADIO,
    choices=_sensor_track_choices(),
    default=IrdaSequence.NONE,
    required=True,
    # No note. The one written here said that the R➟L / L➟R engine ID filters are shown from
    # the read-back but not written by this page: true, and about fields that are not on the
    # page and cannot be reached from it, which is nothing the operator can act on. The
    # height it cost is what the rows are set at their full size with; see _build_option.
    #
    # The key is the word the press is built from -- the mode's AUX1 press takes its digit
    # from "action" -- while the module reports the setting as the sequence field of its
    # own IRDA CONFIG record, which is the only place the action it is running with is
    # recorded: the accessory-scope state the panel is handed does not carry it at all.
    # Named here rather than read for in the panel, so what a module calls its settings
    # stays a fact about the module; see LcsOption.reported_as.
    reported_key="sequence",
)

SENSOR_TRACK = LcsDevice(
    key="sensor_track",
    # Named as the module is named on the box it comes in, the sensing being infrared and
    # the word that says so being the one an operator picking the module out of a list of
    # five needs. The key is untouched: it is what a module's settings, presses and the
    # listing's own name for it are filed under, and none of that is a fact about spelling.
    label="IR Sensor Track",
    blurb="ACC",
    pdi_device=PdiDevice.IRDA,
    program_button="PROGRAM",
    modes=(
        LcsMode(
            # Setting the ID and assigning an Action Command are a single programming
            # gesture on a Sensor Track, and the manual describes them together -- but the
            # mode row names the address alone, like every other module's. Saying both asks
            # 751 px of the 714 px the pane gives a row at the Pi's 1.5x font scale -- even
            # with the key abbreviated -- and a row wider than the pane is centered in it
            # and loses both its ends: 18 px off each. The Action Command is the whole of
            # the options page that follows this.
            key="acc",
            name="ACC",
            scope=CommandScope.ACC,
            ports=1,
            pdi_mode=None,
            presses=(
                Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC),
                Press(
                    "AUX1 then {digit}",
                    scope=CommandScope.ACC,
                    aux=1,
                    note="action command",
                    digit_from="action",
                ),
            ),
        ),
    ),
    options=(SENSOR_TRACK_ACTION,),
    identifies_state=lambda state: bool(getattr(state, "is_sensor_track", False)),
)

#
# AMC2
#
# The three motor modes, worded as the manual describes them and valued as the module
# reports them. The manual numbers them 1, 2 and 3 and OutputType counts from zero, which
# is what the motor presses' digit_offset is for: the option holds what the module says
# about itself, and the press spells the key the operator taps.
#
# Which motor a mode is for is not said in the row -- the rows stand under a heading that
# says it -- so the three read as the choice they are: what kind of motor is wired to this
# output, and how it is to answer the throttle.
_AMC2_MOTOR_MODES: tuple[tuple[str, Any], ...] = (
    ("Continuous (DC)", OutputType.NORMAL),
    ("Proportional (DC)", OutputType.DELTA),
    ("AC", OutputType.AC),
)


def _amc2_motor_mode(motor: int) -> LcsOption:
    """
    The mode one of the AMC2's two motor outputs runs in.
    """
    return LcsOption(
        key=f"motor{motor}_mode",
        # Named as the operating panel names the same output, so the module reads the same
        # way on the screen that configures it and the screen that drives it.
        label=f"Motor #{motor}",
        kind=OptionKind.RADIO,
        choices=_AMC2_MOTOR_MODES,
        # Every AMC2 programming sequence sets both motors -- the manual is explicit that
        # the software configuration "is a single operation that sets three distinct
        # features" -- so a mode is always sent, and the default is the one an operator
        # reaches for. What the module is already running with is read off it first; see
        # LcsConfigPanel._seed_options_from_layout.
        default=OutputType.NORMAL,
        required=True,
        # The AMC2 reports each motor on the motor itself, and the same path reads its
        # CONFIG packet and the AccessoryState built from it; see LcsOption.reported_by.
        reported_key=f"motor{motor}.output_type",
    )


def _amc2_motor_restore(motor: int) -> LcsOption:
    """
    Whether one of the AMC2's motors comes back up at the speed it was turning.
    """
    return LcsOption(
        key=f"motor{motor}_restore",
        # The manual's own word for it is Remember, and the gesture is a tap of the R
        # (rear coupler) key during programming -- the same key the BPC2's restore flag is
        # set with, which is why that one is worded as a restore and this one is not.
        #
        # Which motor is not repeated here: the box stands directly under that motor's own
        # three rows and the heading naming them, and saying it again is what pushes the
        # label onto a second line. Measured on a 480x800 pane at the Pi's 1.5x font scale,
        # where the row has 329px for its words: with the motor named it takes 418px, so it
        # wraps and is drawn a size smaller as well, and the two of them cost the page 54px
        # -- most of what the scrolling window has to hold back there. Without it, 321px on
        # one line at the size every other control is drawn at. The presses on the review
        # page name the motor each tap is for, which is where the two have to be told apart.
        label="Remember speed on power-up",
        kind=OptionKind.CHECKBOX,
        default=False,
        reported_key=f"motor{motor}.restore",
    )


AMC2_MOTOR1_MODE = _amc2_motor_mode(1)
AMC2_MOTOR1_RESTORE = _amc2_motor_restore(1)
AMC2_MOTOR2_MODE = _amc2_motor_mode(2)
AMC2_MOTOR2_RESTORE = _amc2_motor_restore(2)


def _amc2_acc_presses() -> tuple[Press, ...]:
    """The AMC2's accessory-mode sequence, exactly as its flowchart draws it.

    The address, then each motor in turn: the AUX key that names the motor followed by the
    digit for its mode, and a tap of the R key after it where that motor is to remember its
    speed. Motor 1 is entered under AUX1 and motor 2 under AUX2 -- the flowchart is explicit
    about it, and the running text that says AUX1 for both is repeating step 6's wording.
    """
    presses: list[Press] = [Press("ACC {id} SET", TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC)]
    for motor in (1, 2):
        presses.append(
            Press(
                f"AUX{motor} then {{digit}}",
                scope=CommandScope.ACC,
                aux=motor,
                digit_from=f"motor{motor}_mode",
                digit_offset=1,
                note=f"motor #{motor} mode",
            )
        )
        presses.append(
            Press(
                "Coupler R",
                TMCC1AuxCommandEnum.REAR_COUPLER,
                CommandScope.ACC,
                note=f"motor #{motor} remembers",
                include_if=f"motor{motor}_restore",
            )
        )
    return tuple(presses)


AMC2 = LcsDevice(
    key="amc2",
    label="AMC2",
    blurb="ACC",
    pdi_device=PdiDevice.AMC2,
    # An AMC2 says which of the three address types it answers to rather than publishing a
    # mode byte, and the pdi_mode of each mode below is that very AccessType; see
    # reported_mode().
    reported_mode_key="access_type",
    modes=(
        LcsMode(
            key="acc",
            name="ACC",
            scope=CommandScope.ACC,
            # One address for the whole module: "This ID is shared by all motors and
            # lights. They cannot be different." It is also what Amc2Req reports as its
            # num_addressable_ports. Its manual's one prohibition, "Do not use TMCC ID
            # #99", needs nothing said here: MAX_TMCC_ID stops every module at 98.
            ports=1,
            pdi_mode=AccessType.ACC.value,
            presses=_amc2_acc_presses(),
        ),
        # The two addressing modes the module has and the panel will not offer. They are
        # real -- the manual gives the same sequence with TR or ENG pressed in place of ACC
        # -- but nothing else in PyTrain drives an AMC2 addressed as a train or an engine,
        # and an address the rest of the program cannot reach is not one to program a module
        # onto. Recorded so that a module already on one of those keys is understood: the
        # access_type in its own CONFIG record is what says which key it is on, and without
        # these the panel would read an AMC2 on TR 5 as holding ACC 5. Only that record says
        # so -- the component state built from it republishes the motors and not the address
        # type -- so a module known from control traffic alone is still taken to be on the
        # key it was filed under.
        #
        # Each declares the one press that opens its sequence, so that what is not offered
        # is still written down truthfully rather than left as an empty gesture.
        LcsMode(
            key="tr",
            name="TR",
            scope=CommandScope.TRAIN,
            ports=1,
            pdi_mode=AccessType.TRAIN.value,
            enabled=False,
            note="PyTrain does not operate an AMC2 addressed as a train",
            presses=(Press("TR {id} SET", TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN),),
        ),
        LcsMode(
            key="eng",
            name="ENG",
            scope=CommandScope.ENGINE,
            ports=1,
            pdi_mode=AccessType.ENGINE.value,
            enabled=False,
            note="PyTrain does not operate an AMC2 addressed as an engine",
            presses=(Press("ENG {id} SET", TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.ENGINE),),
        ),
    ),
    options=(AMC2_MOTOR1_MODE, AMC2_MOTOR1_RESTORE, AMC2_MOTOR2_MODE, AMC2_MOTOR2_RESTORE),
    identifies_state=lambda state: bool(getattr(state, "is_amc2", False)),
)

LCS_DEVICES: tuple[LcsDevice, ...] = (ASC2, BPC2, STM2, SENSOR_TRACK, AMC2)


def configurable_devices() -> tuple[LcsDevice, ...]:
    """
    The modules the panel can actually program, in the order they are offered.

    Sorted by name, so the device page reads as a list an operator can scan, and the first
    row -- the one the panel opens on -- is predictable: AMC2, ASC2, BPC2, IR Sensor Track,
    STM2. LCS_DEVICES keeps its own order, which is a recognition order rather than a
    presentation one: it is walked to identify a module from its state flags, and where one
    component state names two modules the first of them is the one reported.

    Everything that *presents a choice* -- the device radios, the per-device options
    boxes -- reads this; everything that *recognizes* a module already out on the layout
    reads LCS_DEVICES, which would also hold any module this pass could not program.
    """
    return tuple(sorted((device for device in LCS_DEVICES if device.configurable), key=lambda d: d.label.upper()))


def device_for_key(key: str) -> LcsDevice:
    for device in LCS_DEVICES:
        if device.key == key:
            return device
    raise ValueError(f"No such LCS device: {key}")


def devices_for_state(state: Any) -> tuple[LcsDevice, ...]:
    """
    Every registry descriptor the given component state identifies, in registry order.

    Usually one, but a component state is keyed by scope and address alone, so two modules
    sharing an address share a record: an AMC2 and a BPC2 both answering to ACC 1 leave one
    AccessoryState carrying both is_amc2 and is_bpc2 once each has reported. Returning only
    the first would hide the other from the panel's assigned box.
    """
    if state is None:
        return ()
    found: list[LcsDevice] = []
    for device in LCS_DEVICES:
        # noinspection PyBroadException
        try:
            if device.identifies_state(state):
                found.append(device)
        except Exception:  # pragma: no cover - defensive; states vary widely
            continue
    return tuple(found)


def device_for_state(state: Any) -> LcsDevice | None:
    """
    Return the registry descriptor matching the given component state, if any.

    The first of them when a shared record identifies several; devices_for_state() returns
    them all.
    """
    found = devices_for_state(state)
    return found[0] if found else None


def device_for_pdi_device(pdi_device: PdiDevice) -> LcsDevice | None:
    for device in LCS_DEVICES:
        if device.pdi_device == pdi_device:
            return device
    return None


def enabled_modes(device: LcsDevice) -> Sequence[LcsMode]:
    return tuple(mode for mode in device.modes if mode.enabled)


def programmed_options(device: LcsDevice, mode: LcsMode) -> tuple[LcsOption, ...]:
    """The options this mode's sequence actually sets, in the order the module declares them.

    An option reaches the module through a press and no other way, either as the digit a
    gesture enters or as the flag that decides whether a gesture is sent at all, so what a
    mode sets is what its own presses name. Every mode the panel offers today sets all of
    its module's options, and the AMC2's two recorded-but-unoffered modes set none of
    theirs: they are one SET press apiece.

    Written down because it is the difference between a setting that was programmed and one
    that merely stands on the options page. A read-back is judged only on what was sent,
    and a mode that never sent a setting cannot be faulted for the module still holding its
    own; see LcsConfigPanel.verification.
    """
    named = {name for press in mode.presses for name in (press.include_if, press.digit_from) if name}
    return tuple(option for option in device.options if option.key in named)
