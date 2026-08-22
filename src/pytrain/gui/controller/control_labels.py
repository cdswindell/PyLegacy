#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Human-readable labels for the Steam Deck controller bindings.

Everything here exists to turn a loaded :class:`ControlProfile` into text a person can
read on the controls help screen. It is deliberately free of Tk so the whole mapping can
be tested without a display.

Two rules shape the design:

* **The profile is the source of truth.** A user may pass ``-controller_profile`` to
  ``make_gui`` and bind whatever they like, so nothing here assumes the bundled layout.
  Unknown buttons, axes and actions all degrade to something legible rather than raising.
* **Engine commands name themselves.** ``Mixins.clean_title`` already turns
  ``REAR_COUPLER`` into "Rear Coupler", so the ~8 engine commands the profile can bind
  need no hand-written English. Only the handful whose enum name reads like a protocol
  constant ("Blow Horn One") get an override.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...protocol.sequence.sequence_constants import SequenceCommandEnum
from ...protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ...protocol.tmcc2.tmcc2_constants import TMCC2EngineOpsEnum
from .steam_deck_input import (
    DPAD_DOWN,
    DPAD_LEFT,
    DPAD_RIGHT,
    DPAD_UP,
    PANEL_COMMANDS,
    SEQUENCE_CONTROL,
    SEQUENCE_CONTROL_COMMAND,
    ControlProfile,
)

# Joystick button index -> the glyph printed on the Deck. These are the numbers the
# profile's ``buttons`` section uses (JOYBUTTONDOWN/event.button), not SDL's game
# controller enum -- see the numbering note in steam_deck_input.py. Promoted from a
# comment into data so the help screen can name the button a binding is on.
DECK_BUTTON_LABELS: dict[int, str] = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "L1",
    5: "R1",
    6: "View",
    7: "Menu",
    8: "Steam",
    9: "L3",
    10: "R3",
    15: "...",
    16: "R4",
    17: "L4",
    18: "R5",
    19: "L5",
}

# Axis index -> label. Sticks name their axis of travel; the triggers are just L2/R2.
ARROW_HORIZONTAL = "\u2194\ufe0e"  # left-right arrow
ARROW_VERTICAL = "\u2195\ufe0e"  # up-down arrow

DECK_AXIS_LABELS: dict[int, str] = {
    0: f"Left stick {ARROW_HORIZONTAL}",
    1: f"Left stick {ARROW_VERTICAL}",
    2: "L2",
    3: f"Right stick {ARROW_HORIZONTAL}",
    4: f"Right stick {ARROW_VERTICAL}",
    5: "R2",
}

DECK_TOUCHPAD_LABELS: dict[int, str] = {
    0: "Left trackpad",
    1: "Right trackpad",
}

# Order buttons appear in when rendering a chord. A chord's buttons are stored as a
# frozenset, so the modifier-first reading order ("L1 + X", never "X + L1") has to come
# from somewhere: shoulders and stick clicks lead, face buttons trail. Anything absent
# sorts last, by index.
CHORD_BUTTON_PRECEDENCE: tuple[int, ...] = (4, 5, 9, 10, 6, 7, 15, 16, 17, 18, 19, 0, 1, 2, 3)

# Actions with no command enum behind them, plus overrides for the few whose enum name
# reads badly. Anything not listed here falls through to the enum's clean_title, and
# anything with no enum either falls through to a titleized version of the action name --
# which is what keeps a custom profile's invented action names readable.
ACTION_LABELS: dict[str, str] = {
    # Analog control of the focused pane.
    "throttle": "Throttle",
    "direction": "Direction",
    # App/UI actions: no engine command, so no enum to name them.
    "halt": "HALT - stop everything",
    "focus_left": "Focus left pane",
    "focus_right": "Focus right pane",
    "focus_toggle": "Swap focused pane",
    "scope_catalog": "Open catalog",
    "show_controls": "Show these controls",
    "admin_quit": "Quit PyTrain",
    "admin_update": "Update PyTrain",
    "admin_reboot": "Reboot",
    "admin_shutdown": "Shut down",
    # Phrasing overrides. "horn" resolves to BLOW_HORN_ONE ("Blow Horn One") and the
    # startup/shutdown pair splits into IMMEDIATE/DELAYED variants, none of which is
    # what you want to read on a help screen.
    "horn": "Horn",
    "quilling_horn": "Quilling horn",
    "startup": "Engine startup",
    "shutdown": "Engine shutdown",
    # Deliberately no "quilling_horn" override for the trackpads: they are analog, and
    # "Quilling horn" already reads correctly.
    "sequence_control": "Sequence control",
    # The D-pad is not part of the profile (see FIXED_SECTIONS below), but its action
    # names go through the same resolver.
    DPAD_UP: "Boost speed",
    DPAD_DOWN: "Brake speed",
    DPAD_LEFT: "Smoke down",
    DPAD_RIGHT: "Smoke up",
}


# Per-action notes the profile cannot express. Kept next to ACTION_LABELS so a new action
# gets both in one place.
ACTION_NOTES: dict[str, str] = {
    # LONG_PRESS_ACTIONS splits these into IMMEDIATE and DELAYED variants.
    "startup": "hold = delayed",
    "shutdown": "hold = delayed",
}

# Chord actions the router drops unless the admin panel is displayed. Split into their
# own section so the caveat is stated once in a heading rather than repeated on every
# row -- four copies of it made the Chords column the widest thing on screen.
ADMIN_CHORD_ACTIONS = frozenset({"admin_quit", "admin_update", "admin_reboot", "admin_shutdown"})
ADMIN_CHORD_TITLE = "Admin panel only, hold 3s"


def _sentence_case(text: str) -> str:
    """ "Rear Coupler" -> "Rear coupler".

    ``clean_title`` is title-cased, which next to the sentence-cased entries in
    ACTION_LABELS reads like two different screens. None of the command names contain a
    proper noun, so lowering everything after the first letter is safe.
    """
    return text[:1].upper() + text[1:].lower() if text else text


def command_label(command: str) -> str | None:
    """Friendly name for a PyTrain command name, or None if it resolves to no enum.

    Tried against the same enums ``EngineGui.do_engine_command`` uses, minus its
    Legacy/TMCC branching: the wording is identical either way, only the wire command
    differs.
    """
    for member in (
        TMCC2EngineOpsEnum.look_up(command),
        SequenceCommandEnum.by_name(command),
        TMCC1EngineCommandEnum.by_name(command),
    ):
        if member is not None:
            return _sentence_case(member.clean_title)
    return None


def action_label(action: str) -> str:
    """Friendly name for a profile action, always returning something printable."""
    if action in ACTION_LABELS:
        return ACTION_LABELS[action]
    command = PANEL_COMMANDS.get(action)
    if command is None and action == SEQUENCE_CONTROL:
        command = SEQUENCE_CONTROL_COMMAND
    if command is not None:
        label = command_label(command)
        if label is not None:
            return label
    # A custom profile can name an action anything; render it rather than blowing up.
    return _sentence_case(action.replace("_", " "))


def button_label(index: int) -> str:
    return DECK_BUTTON_LABELS.get(index, f"Button {index}")


def axis_label(index: int) -> str:
    return DECK_AXIS_LABELS.get(index, f"Axis {index}")


def touchpad_label(index: int) -> str:
    return DECK_TOUCHPAD_LABELS.get(index, f"Touchpad {index}")


def chord_label(buttons: frozenset[int]) -> str:
    """Render a chord's buttons modifier-first, e.g. "L1 + X"."""

    def sort_key(index: int) -> tuple[int, int]:
        try:
            return CHORD_BUTTON_PRECEDENCE.index(index), index
        except ValueError:
            return len(CHORD_BUTTON_PRECEDENCE), index

    return " + ".join(button_label(index) for index in sorted(buttons, key=sort_key))


def target_suffix(target: str) -> str:
    """Pane qualifier for a binding, or "" when it follows the focused pane.

    In landscape mode every analog control is pane-scoped, and which pane a stick drives
    is the thing people get wrong.
    """
    if target == "left":
        return " LEFT"
    if target == "right":
        return " RIGHT"
    return ""


@dataclass(frozen=True)
class ControlEntry:
    input: str
    action: str
    note: str = ""


@dataclass(frozen=True)
class ControlSection:
    title: str
    entries: tuple[ControlEntry, ...]
    # True for sections a custom profile cannot change. Rendered differently so the
    # screen does not imply the D-pad is remappable when it is not.
    fixed: bool = False


# The D-pad is handled directly by DeckInputRouter (_handle_scroll_boost /
# _handle_select_smoke) and has no profile section, so these entries are static. Same
# for the context-sensitive remaps, which live in module constants rather than the
# profile.
FIXED_DPAD_ENTRIES: tuple[ControlEntry, ...] = (
    ControlEntry("Up / Down", "Boost / brake speed", "repeats"),
    ControlEntry("Left / Right", "Smoke down / up", ""),
)

FIXED_CATALOG_ENTRIES: tuple[ControlEntry, ...] = (
    ControlEntry("Up / Down", "Scroll entries", ""),
    ControlEntry("R1 + Up / Down", "Jump to first / last", ""),
    ControlEntry("Right or A", "Select entry", ""),
    ControlEntry("Left", "Close catalog", ""),
)

FIXED_POPUP_ENTRIES: tuple[ControlEntry, ...] = (ControlEntry("X", "Close the panel on screen", ""),)


# Reading order within the Sticks section: each pane's throttle before its direction,
# left pane before right. Sorting by axis index gave direction first, which is not how
# anyone thinks about a throttle.
_STICK_ACTION_ORDER = ("throttle", "direction")
_STICK_TARGET_ORDER = ("left", "right", "focused", "global")


def _stick_order(binding, index: int) -> tuple[int, int, int]:
    def rank(value: str, order: tuple[str, ...]) -> int:
        return order.index(value) if value in order else len(order)

    return rank(binding.target, _STICK_TARGET_ORDER), rank(binding.action, _STICK_ACTION_ORDER), index


def controls_summary(profile: ControlProfile) -> tuple[ControlSection, ...]:
    """Build the help screen's content from a loaded profile.

    Pure: no Tk, no globals. Sections with no entries are dropped, so a stripped-down
    custom profile does not leave empty headings on screen.
    """
    sticks: list[ControlEntry] = []
    triggers: list[ControlEntry] = []
    for index in sorted(profile.axes, key=lambda i: _stick_order(profile.axes[i], i)):
        binding = profile.axes[index]
        # No "inverted" note: whether the profile inverts the axis is an implementation
        # detail, and the resulting behaviour is what the reader cares about.
        entry = ControlEntry(
            axis_label(index),
            action_label(binding.action) + target_suffix(binding.target),
            ACTION_NOTES.get(binding.action, ""),
        )
        (triggers if binding.trigger else sticks).append(entry)

    pads = [
        ControlEntry(
            touchpad_label(index),
            action_label(profile.touchpads[index].action) + target_suffix(profile.touchpads[index].target),
        )
        for index in sorted(profile.touchpads)
    ]

    buttons = []
    for index in sorted(profile.buttons):
        binding = profile.buttons[index]
        buttons.append(
            ControlEntry(
                button_label(index),
                action_label(binding.action) + target_suffix(binding.target),
                ACTION_NOTES.get(binding.action, "repeats" if binding.repeat else ""),
            )
        )

    chords: list[ControlEntry] = []
    admin_chords: list[ControlEntry] = []
    for chord in profile.chords:
        entry = ControlEntry(
            chord_label(chord.buttons),
            action_label(chord.action) + target_suffix(chord.target),
            ACTION_NOTES.get(chord.action, "anywhere" if chord.target == "global" else ""),
        )
        if chord.action in ADMIN_CHORD_ACTIONS:
            admin_chords.append(ControlEntry(entry.input, entry.action))
        else:
            chords.append(entry)

    sections = (
        ControlSection("Sticks", tuple(sticks)),
        ControlSection("Triggers", tuple(triggers)),
        ControlSection("Trackpads", tuple(pads)),
        ControlSection("Buttons", tuple(buttons)),
        ControlSection("Chords", tuple(chords)),
        ControlSection(ADMIN_CHORD_TITLE, tuple(admin_chords)),
        ControlSection("D-pad", FIXED_DPAD_ENTRIES, fixed=True),
        ControlSection("While the catalog is open", FIXED_CATALOG_ENTRIES, fixed=True),
        ControlSection("While a panel is open", FIXED_POPUP_ENTRIES, fixed=True),
    )
    return tuple(section for section in sections if section.entries)
