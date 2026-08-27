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

# The stick axes, by the index the profile's ``axes`` section uses. Named because the
# context sections below have to name a particular stick rather than whatever the profile
# happens to bind to it, and a bare 4 in that code says nothing.
LEFT_STICK_HORIZONTAL = 0
LEFT_STICK_VERTICAL = 1
RIGHT_STICK_HORIZONTAL = 3
RIGHT_STICK_VERTICAL = 4

DECK_AXIS_LABELS: dict[int, str] = {
    LEFT_STICK_HORIZONTAL: f"Left stick {ARROW_HORIZONTAL}",
    LEFT_STICK_VERTICAL: f"Left stick {ARROW_VERTICAL}",
    2: "L2",
    RIGHT_STICK_HORIZONTAL: f"Right stick {ARROW_HORIZONTAL}",
    RIGHT_STICK_VERTICAL: f"Right stick {ARROW_VERTICAL}",
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
    "halt": "HALT - emergency stop",
    "focus_left": "Focus left pane",
    "focus_right": "Focus right pane",
    "focus_toggle": "Swap focused pane",
    # Qualified on the row rather than left to a heading: the bundled profile has this on
    # Menu, which GLOBAL_SECTION_BUTTONS files under the global heading, yet the binding
    # targets the focused pane -- so it is the one row up there that the heading cannot
    # speak for. Same words as the focus-scoped section titles below.
    "scope_catalog": "Open catalog (w focus)",
    "show_controls": "Show these controls",
    "admin_quit": "Quit PyTrain **",
    "admin_update": "Update PyTrain **",
    "admin_reboot": "Reboot **",
    "admin_shutdown": "Shut down **",
    # Phrasing overrides. "horn" resolves to BLOW_HORN_ONE ("Blow Horn One") and the
    # startup/shutdown pair splits into IMMEDIATE/DELAYED variants, none of which is
    # what you want to read on a help screen.
    "horn": "Horn",
    "quilling_horn": "Quilling horn",
    "startup": "Startup",
    "shutdown": "Shutdown",
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
    # LONG_PRESS_ACTIONS splits these into IMMEDIATE and DELAYED variants. "w" rather than
    # "with": these two rows live in the middle column, which is the narrow one, and they
    # were the pair that wrapped onto a second line there once the Deck's font came out
    # wider than the one this was measured on. Nothing is lost -- the note is read as a
    # qualifier on the action beside it, not as a sentence.
    "startup": "hold: w dialog",
    "shutdown": "hold: w dialog",
}

# Headings for the sections that describe one kind of panel: the bindings there apply only
# while that panel is the focused one, which is what "(w focus)" says. Panel type first, the
# qualifier trailing in the same words every focus-scoped section uses, so they read as a
# family and sort together in the eye, and so the panel types still to come -- Routes, Aux --
# need no new phrasing invented for them. "w" rather than "with" throughout: these headings
# lead the narrow columns, and the spelt-out word wrapped them.
#
# The popup section is the exception: what it describes is not one kind of panel but any of
# them, which a "<type> (w focus)" heading cannot say.
ADMIN_PANEL_TITLE = "Admin Panel (w focus)"
CATALOG_PANEL_TITLE = "Catalog Panel (w focus)"
SWITCH_PANEL_TITLE = "Switches (w focus)"
POPUP_PANEL_TITLE = "While a panel is open"

# The two sections whose bindings act on whichever pane has focus rather than on a pane of
# their own. Named, like the panel titles above, so the help screen and its tests cannot
# drift apart over a string. Joysticks and Trackpads want no such qualifier: every one of
# their rows already carries LEFT or RIGHT.
BUTTONS_TITLE = "Buttons (w focus)"
DPAD_TITLE = "D-pad (w focus)"

# Chord actions the router drops unless the admin panel is displayed. Split into their
# own section so that caveat is stated once in the heading rather than repeated on every
# row -- four copies of it made the Chords column the widest thing on screen. The hold is
# the same story one level down: all four take the same three seconds, so it is said once
# under them as the section's note rather than four times as "(hold 3s)" on the rows.
#
# Worded as the admin panel words it: the chord starts that panel's own button hold (see
# ADMIN_COMMANDS in steam_deck_input.py), and the panel labels those buttons "Hold for 3
# seconds" -- so the screen describing it says the same thing rather than an abbreviation
# of it. Three seconds is AdminPanel's hold_threshold default, not a number of its own.
ADMIN_CHORD_ACTIONS = frozenset({"admin_quit", "admin_update", "admin_reboot", "admin_shutdown"})
ADMIN_PANEL_NOTE = "** Hold for 3 seconds"
# Chords that work whatever is on screen get their own heading too. Said per row as
# "(anywhere)" it wrapped both entries onto a second line, which made this column tall
# enough to push the Close button off the bottom of the display.
# Named for the scope rather than the input, because it now heads the first column: what
# these two chords do applies everywhere, which is the first thing worth reading, and
# "Chords - global" spent half its width repeating a word the rows already show. It also
# leaves the heading true of the buttons listed above them, which are no chords at all.
GLOBAL_CHORD_TITLE = "Global"

# Buttons drawn in that section rather than with the rest of the buttons. Named by index
# because no binding says it: in the bundled profile View and the stick clicks are on
# global actions and Menu on a pane-scoped one, so ``target`` sorts them apart. What they
# share is what the heading claims -- none of them does anything to the engine in front of
# you, and all of them keep working whatever is on screen. What they do instead is decide
# which pane the rest of the screen is talking about, which is worth reading before those
# commands rather than as four rows in the middle of them.
#
# Which pane they act on is not shared: Menu's bundled action targets the focused pane, so
# its label says so itself (see "scope_catalog" above) rather than leaning on the heading.
GLOBAL_SECTION_BUTTONS = frozenset({6, 7, 9, 10})

# Where the trigger rows land among the buttons. The triggers are analog and once had a
# section of their own, but with the quilling horn moved to the trackpads they do what a
# button does -- one action on a pull -- and a two-row section spent a heading saying so.
# On the Deck L2/R2 sit directly under L1/R1, so they read directly after them.
TRIGGER_AFTER_BUTTON = 5


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


def stick_label(vertical_axis: int) -> str:
    """Both of one stick's axes on a single row: "Left stick ↕ / ↔".

    Named from DECK_AXIS_LABELS rather than written out, so a row about a stick cannot end
    up calling it something the Joysticks section does not: the vertical label already
    reads "<side> stick ↕", leaving only the other arrow to append.
    """
    return f"{axis_label(vertical_axis)} / {ARROW_HORIZONTAL}"


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
    # True for a section that opens a column rather than filling out the one in progress.
    # Without it a column break is an accident of arithmetic: ControlsPanel packs greedily
    # against a row budget it derives from the display, so the panel sections led the last
    # column at a budget of 20 rows and were pulled up into the bottom of the middle one
    # at 22 -- the budget the Deck itself derives.
    starts_column: bool = False
    # A footnote for the section as a whole, drawn under its rows. For what is true of
    # every row in it: as a per-row note it is the same words two, three, four times over,
    # widening the narrowest thing on the screen to say once what it says repeatedly.
    note: str = ""


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
    # X as well as D-pad left: the catalog is one of the pane's popups, so the router's
    # close-popup button dismisses it too. Stated here rather than left to the popup
    # section further down the column, because a reader looking at the catalog is asking
    # how to get out of the catalog -- and both ways out on one row read as "Right or A"
    # already does for choosing an entry.
    ControlEntry("Left or X", "Close catalog", ""),
)

FIXED_POPUP_ENTRIES: tuple[ControlEntry, ...] = (ControlEntry("X", "Close the panel on screen", ""),)

# A panel showing a track switch has no engine to drive, so DeckInputRouter (_handle_switch)
# claims the controls that would drive one. Stated as its own section rather than as notes on
# the joystick and trigger rows above, which describe what those controls do with an engine.
#
# Each stick is named as the Joysticks section names it, and carries the same LEFT/RIGHT pane
# suffix: the reader here is asking what that very same control does once a switch is on
# display, and "Stick" with an "own pane" note named no stick at all. One row per stick
# rather than one per axis, with the arrows pairing off against "thru / out" the way the
# D-pad's "Up / Down" pairs with "Boost / brake speed" -- four rows a column can hold,
# where five sent the whole section onto a second page nobody would think to turn to.
# The heading says "Switch", so the rows do not repeat it; that also keeps every row on
# one line, which the "(own pane)" wording did not manage.
FIXED_SWITCH_ENTRIES: tuple[ControlEntry, ...] = (
    ControlEntry("L2 / R2", "Throw thru / out", ""),
    ControlEntry(stick_label(LEFT_STICK_VERTICAL), "Throw thru / out" + target_suffix("left")),
    ControlEntry(stick_label(RIGHT_STICK_VERTICAL), "Throw thru / out" + target_suffix("right")),
)


# Reading order within the Joysticks section: each pane's throttle before its direction,
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

    buttons: list[ControlEntry] = []
    global_buttons: list[ControlEntry] = []
    for index in sorted(profile.buttons):
        binding = profile.buttons[index]
        entry = ControlEntry(
            button_label(index),
            action_label(binding.action) + target_suffix(binding.target),
            ACTION_NOTES.get(binding.action, "repeats" if binding.repeat else ""),
        )
        (global_buttons if index in GLOBAL_SECTION_BUTTONS else buttons).append(entry)
        if index == TRIGGER_AFTER_BUTTON:
            buttons.extend(triggers)
            triggers = []
    # A profile that binds nothing to the bumper still has to show its triggers.
    buttons.extend(triggers)

    chords: list[ControlEntry] = []
    global_chords: list[ControlEntry] = []
    admin_chords: list[ControlEntry] = []
    for chord in profile.chords:
        entry = ControlEntry(
            chord_label(chord.buttons),
            action_label(chord.action) + target_suffix(chord.target),
            ACTION_NOTES.get(chord.action, ""),
        )
        if chord.action in ADMIN_CHORD_ACTIONS:
            # The hold these all share is the section's note, so the rows say only what
            # differs between them.
            admin_chords.append(entry)
        elif chord.target == "global":
            global_chords.append(entry)
        else:
            # A custom profile may bind a pane-scoped chord; it does not belong under a
            # heading that promises the binding works anywhere.
            chords.append(entry)

    # Reading order, which is also column order: ControlsPanel flows these into columns in
    # sequence, so this tuple is where the layout is decided. The bundled profile lands as
    # three columns -- what works anywhere and the analog controls, then everything you
    # press, then nothing but the per-panel sections. Keeping every panel section together
    # in the last column is the point: a reader asking "what does this do while a panel is
    # up" has one place to look, and the D-pad, which answers a different question, closes
    # the column before rather than sitting in the middle of that list. starts_column says
    # that in the layout instead of leaving it to how the rows happen to add up.
    sections = (
        ControlSection(GLOBAL_CHORD_TITLE, tuple(global_buttons + global_chords)),
        ControlSection("Joysticks", tuple(sticks)),
        ControlSection("Trackpads", tuple(pads)),
        ControlSection(BUTTONS_TITLE, tuple(buttons)),
        ControlSection("Chords", tuple(chords)),
        ControlSection(DPAD_TITLE, FIXED_DPAD_ENTRIES, fixed=True),
        ControlSection(SWITCH_PANEL_TITLE, FIXED_SWITCH_ENTRIES, fixed=True, starts_column=True),
        ControlSection(ADMIN_PANEL_TITLE, tuple(admin_chords), note=ADMIN_PANEL_NOTE),
        ControlSection(CATALOG_PANEL_TITLE, FIXED_CATALOG_ENTRIES, fixed=True),
        ControlSection(POPUP_PANEL_TITLE, FIXED_POPUP_ENTRIES, fixed=True),
    )
    return tuple(section for section in sections if section.entries)
