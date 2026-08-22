#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import glob
import importlib
import json
import logging
import math
import os
import queue
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

log = logging.getLogger(__name__)

Target = Literal["left", "right", "focused", "global"]
SUPPORTED_ACTIONS = {
    "throttle",
    "direction",
    "halt",
    "reset",
    "horn",
    "bell",
    "focus_left",
    "focus_right",
    "focus_toggle",
    "scope_catalog",
    "startup",
    "shutdown",
    "quilling_horn",
    "sequence_control",
    "front_coupler",
    "rear_coupler",
    "volume_up",
    "volume_down",
    "engineer_chatter",
    "tower_chatter",
    "admin_quit",
    "admin_update",
    "admin_reboot",
    "admin_shutdown",
    "show_controls",
}
AXIS_ACTIONS = {"throttle", "direction", "quilling_horn"}
# Discrete navigation actions that may be bound to an analog trigger axis
# (L2/R2). Unlike the analog axis actions above, these fire a single one-shot
# command each time the trigger is squeezed past its dead zone; the trigger
# must be released and squeezed again before it fires anew. They target the
# global panel router, mirroring the same actions when bound to a button.
TRIGGER_BUTTON_ACTIONS = {"focus_left", "focus_right", "focus_toggle"}
# SDL "A" button. While the catalog panel is open it confirms the highlighted
# entry; otherwise it performs whatever action the profile assigns to it.
SELECT_BUTTON = 0
# SDL "X" button. While a popup panel is displayed it closes the popup;
# otherwise it performs whatever action the profile assigns to it.
CLOSE_POPUP_BUTTON = 2
# SDL D-pad (hat). On the Steam Deck the D-pad is reported as an SDL hat rather
# than as buttons, and arrives as hat motion. The Deck's joystick reports 20
# buttons in total: 0-10 are the face/shoulder buttons, View, Menu, Steam and the
# stick clicks; 15 is the "..." button below the right trackpad; and 16-19 are the
# back paddles (16 = R4, 17 = L4, 18 = R5, 19 = L5). None of them is the D-pad.
# Confirmed with ``scripts/deckinfo.py``, which mirrors this module's SDL setup.
# While the catalog panel is open, up/down scroll the highlighted entry in
# the focused pane one at a time (or jump to the first/last entry when the
# ``CATALOG_JUMP_MODIFIER`` button is held), right confirms the highlighted entry, and left
# cancels/closes the catalog panel. Otherwise (no catalog), up/down boost/brake
# the engine or train speed (auto-repeating while held) and left/right
# lower/raise the smoke output (SMOKE_OFF/SMOKE_ON, one-shot per press).
DPAD_UP = "dpad_up"
DPAD_DOWN = "dpad_down"
DPAD_LEFT = "dpad_left"
DPAD_RIGHT = "dpad_right"
# A button assigned the "startup" or "shutdown" action distinguishes a short
# press from a long press: a short press emits the ``*_IMMEDIATE`` action
# (START_UP_IMMEDIATE / SHUTDOWN_IMMEDIATE) while a hold of at least
# ``LONG_PRESS_SECONDS`` emits the ``*_DELAYED`` action (START_UP_DELAYED /
# SHUTDOWN_DELAYED, each falling back to its immediate variant for TMCC engines
# that lack it). The command is emitted once, on release.
STARTUP_IMMEDIATE = "startup_immediate"
STARTUP_DELAYED = "startup_delayed"
SHUTDOWN_IMMEDIATE = "shutdown_immediate"
SHUTDOWN_DELAYED = "shutdown_delayed"
LONG_PRESS_SECONDS = 1.0
# Backwards-compatible alias for the shared long-press threshold.
STARTUP_LONG_PRESS_SECONDS = LONG_PRESS_SECONDS
# Profile actions whose button distinguishes a short press from a long press,
# mapped to the (immediate, delayed) runtime action names they emit.
LONG_PRESS_ACTIONS = {
    "startup": (STARTUP_IMMEDIATE, STARTUP_DELAYED),
    "shutdown": (SHUTDOWN_IMMEDIATE, SHUTDOWN_DELAYED),
}
PANEL_COMMANDS = {
    "reset": "RESET",
    "horn": "BLOW_HORN_ONE",
    "bell": "RING_BELL",
    # The L1/R1 shoulder buttons open the engine's couplers: L1 the rear
    # coupler and R1 the front coupler.
    "front_coupler": "FRONT_COUPLER",
    "rear_coupler": "REAR_COUPLER",
    # Bound to the back paddles in the bundled profile. Each of these resolves for
    # both Legacy (TMCC2) and non-Legacy (TMCC1) engines/trains, so the same command
    # works regardless of control type. Volume is a relative step, so those two are
    # flagged ``repeat`` in the profile and re-send while held; the chatter commands
    # are one-shot.
    "volume_up": "VOLUME_UP",
    "volume_down": "VOLUME_DOWN",
    "engineer_chatter": "ENGINEER_CHATTER",
    "tower_chatter": "TOWER_CHATTER",
}
# The A button runs the engine's "automatic sequence control": it sends the
# AUX1_OPTION_ONE command every ``repeat_interval`` (100 ms) for
# ``SEQUENCE_CONTROL_DURATION`` seconds, mirroring holding the physical AUX1
# button. ``AUX1_OPTION_ONE`` resolves for both Legacy (TMCC2) and non-Legacy
# (TMCC1) engines/trains, so the same command works regardless of control type.
SEQUENCE_CONTROL = "sequence_control"
SEQUENCE_CONTROL_COMMAND = "AUX1_OPTION_ONE"
SEQUENCE_CONTROL_DURATION = 3.1
# While the catalog panel is open, holding the D-pad up/down auto-repeats the
# highlighted-entry scroll. The first scroll fires immediately on press; the
# auto-repeat then only begins after the key has been held for
# ``CATALOG_SCROLL_INITIAL_DELAY`` seconds and thereafter advances one entry
# every ``CATALOG_SCROLL_REPEAT_INTERVAL`` seconds. These are deliberately
# slower than the 100 ms ``repeat_interval`` so catalog selection is not too
# quick to control.
CATALOG_SCROLL_INITIAL_DELAY = 0.5
CATALOG_SCROLL_REPEAT_INTERVAL = 0.2
# Profile ``buttons`` indices are *joystick* numbers (``JOYBUTTONDOWN``/
# ``event.button``), which is the only button numbering this module reads. SDL's game
# controller API numbers the same buttons differently (its fixed
# ``SDL_CONTROLLER_BUTTON_*`` enum: on the Deck, Steam is joystick 8 but controller
# 5) and exposes extras the joystick API may omit -- ``misc1`` = the Deck's "..."
# button, ``paddle1``-``paddle4`` = L4/R4/L5/R5. Those numbers are NOT usable here.
# ``scripts/deckinfo.py`` prints both, labelled, when a physical button's index needs
# identifying.
#
# Being *reported* is not always the same as being *available*: pressing "..." also
# opens Steam's Quick Access overlay, which grabs the whole controller while it is held,
# and no D-pad press reaches the app during that. That still rules "..." out as a chord
# *modifier* -- it cannot be held down while a second button is pressed. It is readable
# as a momentary press though, which is why the bundled profile binds it to
# SHOW_CONTROLS: the help screen only needs the press, not a hold.
# Analog action for the L2/R2 triggers. While a trigger is held past its dead
# zone the router emits ``HORN_COMMAND`` every ``repeat_interval`` (100 ms).
# ``on_engine_command`` resolves the fallback list per engine generation: a
# Legacy engine sounds the Quilling Horn with the supplied intensity while a
# non-Legacy engine (TMCC/Cab-1/R100) falls through to the plain Blow Horn
# (intensity ignored).
QUILLING_HORN = "quilling_horn"
HORN_MAX_INTENSITY = 15
HORN_COMMAND = ["QUILLING_HORN", "BLOW_HORN_ONE"]
# Triggers (L2/R2) rest at one extreme and travel to the other, so they don't
# suffer from the resting jitter that the sticks do. They therefore use their
# own, much smaller dead zone than ``dead_zone`` (which the sticks need) so the
# horn responds almost as soon as the trigger leaves its resting position. It
# is kept just above zero as a guard against a trigger whose idle value drifts
# slightly off its resting extreme. Profiles may override it via
# ``trigger_dead_zone``.
DEFAULT_TRIGGER_DEAD_ZONE = 0.02
# The Steam Deck trackpads surface through SDL's Game Controller *touchpad*
# events (CONTROLLERTOUCHPADDOWN/MOTION/UP), not the joystick API the rest of
# the provider uses, so they are captured through a separate controller-
# subsystem path. Each pad is identified by its ``touch_id`` (index 0 = left,
# 1 = right on the Steam Deck) and reports a finger position whose ``y`` runs
# 0.0 (top) -> 1.0 (bottom). A profile ``touchpads`` section maps a pad index
# to the ``quilling_horn`` action so pulling a finger down the pad sounds the
# horn, mirroring the on-screen vertical horn slider.
TOUCHPAD_ACTIONS = {"quilling_horn"}
# Admin panel operations, reachable as L1 + a face button *only while the admin panel
# is on screen* -- the router drops them otherwise, so no chord can reboot or shut
# down the machine from an operating screen. Each maps to the ``TMCC1SyncCommandEnum``
# member the panel's own buttons send, resolved GUI-side like the PANEL_COMMANDS above.
#
# NOTE: these are destructive, so a chord does not bypass the hold guard the panel's
# on-screen buttons impose. The press starts the matching button's own 3-second hold
# (``hold_threshold``, with its visible "Hold for 3 seconds" progress bar) and the
# command fires only once that completes; releasing either button first cancels it. A
# chord therefore gets the same dwell and the same feedback as a finger, with no second
# copy of the timing logic -- see ``_handle_admin_command``.
ADMIN_COMMANDS = {
    "admin_quit": "QUIT",
    "admin_update": "UPDATE",
    "admin_reboot": "REBOOT",
    "admin_shutdown": "SHUTDOWN",
}
# While the admin panel is open, L1 is the chord modifier and opens no coupler, the
# same way R1 becomes the catalog-jump modifier while the catalog is open. Keyed by
# profile action so it follows whichever button carries the rear coupler.
ADMIN_CHORD_MODIFIER = "rear_coupler"
# Opens the controls help screen. Bound to the Deck's "..." button in the bundled
# profile. Global rather than per-pane: the bindings it lists are the same either side.
SHOW_CONTROLS = "show_controls"
# While the catalog panel is open, holding R1 turns D-pad up/down into a jump to the
# first/last entry instead of a one-entry scroll: R1+up jumps to the top, R1+down to
# the end. The jump only moves the highlight -- the user confirms the entry
# separately, so the catalog stays open.
#
# R1 is the modifier because it is delivered to the app reliably. The Deck's obvious
# modifier candidates are not: Steam consumes "..." (and the whole controller with it)
# for its Quick Access overlay, so neither that button nor any D-pad press reaches the
# app while it is held.
#
# While the catalog is open R1 does not also open its coupler -- browsing a catalog
# and uncoupling cars are never useful at the same moment, and this mirrors how the A
# button confirms the highlighted entry while the catalog is open rather than running
# its assigned action. L1 keeps its coupler throughout.
#
# Keyed by profile action rather than by button index, so the modifier follows
# whichever button a profile assigns the front coupler to.
CATALOG_JUMP_MODIFIER = "front_coupler"
# Fraction of the pad, measured from the top edge, treated as "off" so a finger
# resting at the very top does not sound the horn. Profiles may override it via
# ``touch_dead_zone``.
DEFAULT_TOUCH_DEAD_ZONE = 0.05
DEFAULT_PROFILE = Path(__file__).with_name("steam_deck_default.json")


# ---------------------------------------------------------------------------
# Raw hidraw trackpad reader for the Steam Deck's built-in controller.
#
# SDL never surfaces the Deck's built-in trackpads as controller touchpads, so
# the CONTROLLERTOUCHPAD* events the provider listens for never fire on the
# Deck. As an alternative input path we read the controller's raw 64-byte HID
# input reports directly from its ``/dev/hidraw*`` node -- those reports carry
# absolute trackpad coordinates. A dedicated daemon thread performs the blocking
# reads and hands each report to the (single-threaded) provider through a
# thread-safe ``queue.Queue``, keeping the reader fully decoupled from pygame.
# This mirrors the probe proven out in ``scripts/deckinfo.py``.
# ---------------------------------------------------------------------------
_DECK_VID = 0x28DE
_DECK_PID = 0x1205  # Steam Deck built-in controller
# The same reports also carry every digital button, which is the only way to reach
# the back paddles. Steam Input decides what the SDL layer sees, and in Gaming Mode
# it hands the app a virtual pad on which an unbound paddle emits *nothing at all* --
# not a remapped button, not an unknown index. (Run from a Desktop Mode shell, SDL
# does report the physical device's 20 buttons, paddles included, which is what
# ``scripts/deckinfo.py`` sees. That path is not available to the app under Steam.)
# Reading the raw HID report bypasses Steam Input entirely.
#
# Bits measured with ``scripts/deckinfo.py``, which names the byte and bit of any
# button pressed. The dict is keyed by the button index SDL uses for the same paddle
# on the physical device, so one profile binding covers both routes.
_DECK_PADDLE_BUTTONS = {
    16: (13, 1 << 2),  # R4
    17: (13, 1 << 1),  # L4
    18: (10, 1 << 0),  # R5
    19: (9, 1 << 7),  # L5
}
# Byte offsets into the Deck's 64-byte input "state" report. The report begins
# with 0x01 0x00 0x09 0x40 (unReportVersion=0x0001, ucType=0x09, ucLength=0x40).
# These offsets mirror the Linux ``hid-steam`` driver's decode.
_DECK_STATE_TYPE = 0x09
_DECK_TOUCH_BYTE = 10  # bit3 = left pad touched, bit4 = right pad touched
_DECK_LPAD_TOUCH_BIT = 1 << 3
_DECK_RPAD_TOUCH_BIT = 1 << 4
_DECK_LPAD_OFFSET = 16  # s16 LE x immediately followed by s16 LE y
_DECK_RPAD_OFFSET = 20  # s16 LE x immediately followed by s16 LE y
# The Deck reports each pad coordinate as a signed 16-bit value; the pad's ``y``
# axis runs from ``+32767`` at the top edge to ``-32768`` at the bottom edge.
_DECK_PAD_MIN = -32768
_DECK_PAD_MAX = 32767
_DECK_PAD_RANGE = _DECK_PAD_MAX - _DECK_PAD_MIN
# The provider maps the left pad to ``touch_id`` 0 and the right pad to 1,
# matching the SDL touchpad indices the ``touchpads`` profile section uses.
_DECK_LEFT_TOUCH_ID = 0
_DECK_RIGHT_TOUCH_ID = 1


def _find_deck_hidraw_paths() -> list[str]:
    # Locate every ``/dev/hidraw*`` node that belongs to the Deck controller by
    # matching its VID/PID in the sysfs ``uevent`` (HID_ID=0003:000028DE:00001205).
    # Returns an empty list off the Deck (or anywhere without matching sysfs),
    # so the reader stays inert on non-Deck hardware.
    paths: list[str] = []
    hid_id = f":{_DECK_VID:08X}:{_DECK_PID:08X}".lower()
    for sys_path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        uevent = os.path.join(sys_path, "device", "uevent")
        try:
            with open(uevent, encoding="ascii", errors="replace") as handle:
                text = handle.read().lower()
        except OSError:
            continue
        if hid_id in text:
            paths.append("/dev/" + os.path.basename(sys_path))
    return paths


def _decode_deck_pads(report: bytes) -> tuple[bool, tuple[int, int], bool, tuple[int, int]] | None:
    # Return ``(lpad_touched, (lx, ly), rpad_touched, (rx, ry))`` for a Deck
    # "state" packet, or ``None`` for any other report type / a report too short
    # to decode.
    if len(report) < _DECK_RPAD_OFFSET + 4:
        return None
    if report[0] != 0x01 or report[2] != _DECK_STATE_TYPE:
        return None
    touch = report[_DECK_TOUCH_BYTE]
    lpad_touched = bool(touch & _DECK_LPAD_TOUCH_BIT)
    rpad_touched = bool(touch & _DECK_RPAD_TOUCH_BIT)
    lx, ly = struct.unpack_from("<hh", report, _DECK_LPAD_OFFSET)
    rx, ry = struct.unpack_from("<hh", report, _DECK_RPAD_OFFSET)
    return lpad_touched, (lx, ly), rpad_touched, (rx, ry)


def _decode_deck_paddles(report: bytes) -> dict[int, bool] | None:
    # Return ``{button index: pressed}`` for the back paddles in a state packet, or
    # None for any other report type / a report too short to decode.
    if len(report) <= max(byte for byte, _mask in _DECK_PADDLE_BUTTONS.values()):
        return None
    if report[0] != 0x01 or report[2] != _DECK_STATE_TYPE:
        return None
    return {index: bool(report[byte] & mask) for index, (byte, mask) in _DECK_PADDLE_BUTTONS.items()}


def _deck_pad_y_fraction(raw_y: int) -> float:
    # Convert a raw pad ``y`` (``+32767`` top .. ``-32768`` bottom) into the
    # ``0.0`` (top) .. ``1.0`` (bottom) fraction ``_normalize_touch_y`` expects,
    # so dragging a finger *down* the pad increases the horn -- mirroring the
    # on-screen vertical horn slider.
    fraction = (_DECK_PAD_MAX - raw_y) / _DECK_PAD_RANGE
    return max(0.0, min(1.0, fraction))


class _HidrawTrackpadReader(threading.Thread):
    """Read 64-byte HID reports from one Deck hidraw node and queue them.

    The blocking ``os.read`` runs on its own daemon thread so it never stalls
    the provider's poll loop; each report (or a one-off error) is delivered via
    ``out_queue`` as ``("report", path, bytes)`` or ``("error", path, message)``.
    """

    def __init__(self, path: str, out_queue: "queue.Queue") -> None:
        super().__init__(name=f"hidraw:{path}", daemon=True)
        self._path = path
        self._queue = out_queue
        self._stop = threading.Event()
        self._fd: int | None = None

    def run(self) -> None:
        try:
            self._fd = os.open(self._path, os.O_RDONLY)
        except OSError as exc:
            self._queue.put(("error", self._path, f"cannot open ({exc}); a udev rule or root may be required"))
            return
        while not self._stop.is_set():
            try:
                report = os.read(self._fd, 64)
            except OSError as exc:
                if not self._stop.is_set():
                    self._queue.put(("error", self._path, f"read failed: {exc}"))
                break
            if report:
                self._queue.put(("report", self._path, report))

    def stop(self) -> None:
        self._stop.set()
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None


class ProfileError(ValueError):
    pass


class ControllerUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DeckAction:
    name: str
    target: Target
    value: float
    phase: str
    button: int | None = None
    # True when the ``CATALOG_JUMP_MODIFIER`` button (R1) was held as this action was
    # produced. Only D-pad up/down presses set it. The provider reports only the
    # physical fact that the modifier was held, so the router keeps sole ownership of
    # what is on screen -- the flag is ignored when the catalog is closed.
    jump_modifier: bool = False


@dataclass(frozen=True)
class AxisBinding:
    action: str
    target: Target
    invert: bool = False
    trigger: bool = False


@dataclass(frozen=True)
class ButtonBinding:
    action: str
    target: Target
    repeat: bool = False
    # Seconds between re-sends while the button is held. ``None`` uses the profile's
    # global ``repeat_interval``; set it per button where that rate is wrong for the
    # command (volume steps, say, want a slower cadence than the horn).
    repeat_interval: float | None = None


@dataclass(frozen=True)
class TouchpadBinding:
    action: str
    target: Target


@dataclass(frozen=True)
class ChordBinding:
    buttons: frozenset[int]
    action: str
    target: Target


@dataclass(frozen=True)
class ControlProfile:
    axes: Mapping[int, AxisBinding]
    buttons: Mapping[int, ButtonBinding]
    chords: tuple[ChordBinding, ...]
    dead_zone: float
    hysteresis: float
    throttle_rate: float
    repeat_interval: float
    direction_threshold: float
    trigger_dead_zone: float = DEFAULT_TRIGGER_DEAD_ZONE
    touchpads: Mapping[int, TouchpadBinding] = field(default_factory=dict)
    touch_dead_zone: float = DEFAULT_TOUCH_DEAD_ZONE

    @property
    def catalog_jump_modifier_buttons(self) -> frozenset[int]:
        # Button indices whose action makes them the catalog-jump modifier (R1 in the
        # bundled profile). Usually one, but a profile may bind several and any of
        # them held enables the jump.
        return frozenset(index for index, binding in self.buttons.items() if binding.action == CATALOG_JUMP_MODIFIER)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ControlProfile":
        dead_zone = cls._number(data, "dead_zone")
        hysteresis = cls._number(data, "hysteresis")
        throttle_rate = cls._number(data, "throttle_rate")
        repeat_interval = cls._number(data, "repeat_interval")
        direction_threshold = cls._number(data, "direction_threshold")
        trigger_dead_zone = (
            cls._number(data, "trigger_dead_zone") if "trigger_dead_zone" in data else DEFAULT_TRIGGER_DEAD_ZONE
        )
        touch_dead_zone = cls._number(data, "touch_dead_zone") if "touch_dead_zone" in data else DEFAULT_TOUCH_DEAD_ZONE
        if not 0.0 <= dead_zone < 1.0:
            raise ProfileError("dead_zone must be between 0 and 1")
        if not 0.0 <= trigger_dead_zone < 1.0:
            raise ProfileError("trigger_dead_zone must be between 0 and 1")
        if not 0.0 <= touch_dead_zone < 1.0:
            raise ProfileError("touch_dead_zone must be between 0 and 1")
        if not 0.0 <= hysteresis < dead_zone:
            raise ProfileError("hysteresis must be non-negative and less than dead_zone")
        if throttle_rate <= 0.0:
            raise ProfileError("throttle_rate must be positive")
        if not 0.02 <= repeat_interval <= 1.0:
            raise ProfileError("repeat_interval must be between 0.02 and 1 second")
        if not dead_zone < direction_threshold <= 1.0:
            raise ProfileError("direction_threshold must be greater than dead_zone and at most 1")

        axes: dict[int, AxisBinding] = {}
        for raw_index, raw_binding in cls._mapping(data, "axes").items():
            index = cls._index(raw_index, "axis")
            action, target = cls._binding(raw_binding)
            trigger = bool(raw_binding.get("trigger", False))
            if action in AXIS_ACTIONS:
                if target not in ("left", "right"):
                    raise ProfileError(f"Axis {index} requires a fixed panel target")
            elif action in TRIGGER_BUTTON_ACTIONS or action in LONG_PRESS_ACTIONS:
                # A discrete action on an axis is only meaningful for a trigger,
                # which rests at one extreme and travels to the other; a stick
                # axis rests centered and cannot cleanly emulate a button. This
                # covers both the one-shot navigation actions and the
                # startup/shutdown actions that distinguish a short press from a
                # long press (L2/R2 acting as buttons rather than analog axes).
                if not trigger:
                    raise ProfileError(f"Axis {index} action {action!r} requires trigger to be true")
                cls._validate_action_target(action, target)
            else:
                raise ProfileError(f"Action {action!r} cannot be assigned to an axis")
            axes[index] = AxisBinding(
                action,
                target,
                bool(raw_binding.get("invert", False)),
                trigger,
            )

        buttons: dict[int, ButtonBinding] = {}
        for raw_index, raw_binding in cls._mapping(data, "buttons").items():
            index = cls._index(raw_index, "button")
            action, target = cls._binding(raw_binding)
            if action in AXIS_ACTIONS:
                raise ProfileError(f"Action {action!r} cannot be assigned to a button")
            cls._validate_action_target(action, target)
            repeat = bool(raw_binding.get("repeat", False))
            button_repeat_interval = None
            if "repeat_interval" in raw_binding:
                button_repeat_interval = cls._number(raw_binding, "repeat_interval")
                if not repeat:
                    raise ProfileError(f"Button {index} sets repeat_interval but is not flagged repeat")
                if not 0.02 <= button_repeat_interval <= 5.0:
                    raise ProfileError(f"Button {index} repeat_interval must be between 0.02 and 5 seconds")
            buttons[index] = ButtonBinding(action, target, repeat, button_repeat_interval)

        touchpads: dict[int, TouchpadBinding] = {}
        for raw_index, raw_binding in cls._mapping(data, "touchpads").items():
            index = cls._index(raw_index, "touchpad")
            action, target = cls._binding(raw_binding)
            if action not in TOUCHPAD_ACTIONS:
                raise ProfileError(f"Action {action!r} cannot be assigned to a touchpad")
            if target not in ("left", "right"):
                raise ProfileError(f"Touchpad {index} requires a fixed panel target")
            touchpads[index] = TouchpadBinding(action, target)

        chords = []
        raw_chords = data.get("chords", [])
        if not isinstance(raw_chords, list):
            raise ProfileError("chords must be a list")
        for raw_chord in raw_chords:
            action, target = cls._binding(raw_chord)
            cls._validate_action_target(action, target)
            raw_buttons = raw_chord.get("buttons")
            if not isinstance(raw_buttons, list) or len(raw_buttons) < 2:
                raise ProfileError("A chord requires at least two buttons")
            buttons_set = frozenset(cls._index(button, "button") for button in raw_buttons)
            chords.append(ChordBinding(buttons_set, action, target))

        return cls(
            axes=axes,
            buttons=buttons,
            chords=tuple(chords),
            dead_zone=dead_zone,
            hysteresis=hysteresis,
            throttle_rate=throttle_rate,
            repeat_interval=repeat_interval,
            direction_threshold=direction_threshold,
            trigger_dead_zone=trigger_dead_zone,
            touchpads=touchpads,
            touch_dead_zone=touch_dead_zone,
        )

    @classmethod
    def load(cls, path: str | Path | None = None, *, fallback: bool = True) -> "ControlProfile":
        profile_path = Path(path).expanduser() if path else DEFAULT_PROFILE
        try:
            with profile_path.open(encoding="utf-8") as profile_file:
                return cls.from_dict(json.load(profile_file))
        except (OSError, json.JSONDecodeError, ProfileError, TypeError) as exc:
            if not fallback or profile_path == DEFAULT_PROFILE:
                raise ProfileError(f"Invalid controller profile {profile_path}: {exc}") from exc
            log.warning("Invalid controller profile %s; using bundled default: %s", profile_path, exc)
            return cls.load(DEFAULT_PROFILE, fallback=False)

    @staticmethod
    def _number(data: Mapping[str, Any], key: str) -> float:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProfileError(f"{key} must be numeric")
        return float(value)

    @staticmethod
    def _mapping(data: Mapping[str, Any], key: str) -> Mapping:
        value = data.get(key, {})
        if not isinstance(value, Mapping):
            raise ProfileError(f"{key} must be an object")
        return value

    @staticmethod
    def _index(value: Any, label: str) -> int:
        try:
            index = int(value)
        except (TypeError, ValueError) as exc:
            raise ProfileError(f"Invalid {label} index: {value!r}") from exc
        if index < 0:
            raise ProfileError(f"Invalid {label} index: {value!r}")
        return index

    @staticmethod
    def _binding(data: Any) -> tuple[str, Target]:
        if not isinstance(data, Mapping):
            raise ProfileError("A control binding must be an object")
        action = data.get("action")
        target = data.get("target")
        if action not in SUPPORTED_ACTIONS:
            raise ProfileError(f"Unknown action: {action!r}")
        if target not in ("left", "right", "focused", "global"):
            raise ProfileError(f"Unknown target: {target!r}")
        return action, target

    @staticmethod
    def _validate_action_target(action: str, target: Target) -> None:
        if action == "halt" and target != "global":
            raise ProfileError("halt must target global")
        if action.startswith("focus_") and target != "global":
            raise ProfileError(f"{action} must target global")
        if action in LONG_PRESS_ACTIONS and target not in ("left", "right", "focused"):
            raise ProfileError(f"{action} must target a panel")
        if action == SHOW_CONTROLS and target != "global":
            raise ProfileError(f"{SHOW_CONTROLS} must target global")


class SteamDeckInputProvider:
    def __init__(
        self,
        profile: ControlProfile,
        *,
        pygame_module=None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.profile = profile
        self._pygame = pygame_module
        self._clock = clock or time.monotonic
        self._joysticks: dict[int, Any] = {}
        # The optional ``pygame._sdl2.controller`` module used to open devices as
        # game controllers (required for touchpad events); ``None`` when SDL's
        # game-controller support is unavailable.
        self._controller_module: Any = None
        # Devices opened as SDL game controllers so their touchpad events fire;
        # kept separate from the joystick handles above.
        self._controllers: dict[int, Any] = {}
        # Per-pad finger tracking: touch_id -> {finger_index: y}. A pad's horn
        # sounds while it has at least one finger and stops when the last lifts.
        self._touch_fingers: dict[int, dict[int, float]] = {}
        self._active_axes: set[int] = set()
        # Discrete actions bound to analog triggers (L2/R2) fire once per
        # squeeze; this tracks which trigger axes are currently engaged so the
        # command is emitted only on the rising edge.
        self._trigger_pressed: set[int] = set()
        # When a trigger carries a startup/shutdown (long-press) action it
        # behaves like the equivalent button: this records when each such
        # trigger was squeezed so the release can tell a short press from a long
        # one.
        self._trigger_long_press_pressed_at: dict[int, float] = {}
        self._held_buttons: set[int] = set()
        # Indices already reported as unbound, so the discovery log names each button
        # once rather than on every press. This runs inside the Tk-driven poll, which
        # is also the thread servicing the touch screen, so it must stay bounded.
        self._logged_unbound: set[int] = set()
        self._fired_chords: set[ChordBinding] = set()
        self._hat_y = 0
        self._hat_x = 0
        self._long_press_buttons = {
            index for index, binding in profile.buttons.items() if binding.action in LONG_PRESS_ACTIONS
        }
        self._long_press_pressed_at: dict[int, float] = {}
        self._long_press_chorded: set[int] = set()
        # Raw hidraw trackpad reader state (Steam Deck built-in pads). On the
        # Deck SDL never delivers the built-in trackpads as controller touchpad
        # events, so their reports are read directly from ``/dev/hidraw*`` on a
        # background thread and translated into the same ``quilling_horn`` touch
        # actions in ``poll()``. All inert off the Deck / when no pad is bound.
        self._hidraw_queue: queue.Queue | None = None
        self._hidraw_readers: list[_HidrawTrackpadReader] = []
        # touch_id -> whether the pad currently has a finger down, so a release
        # is emitted exactly once when the finger lifts.
        self._hidraw_pad_touched: dict[int, bool] = {}
        # Last seen pressed/released state of each back paddle, so only edges are
        # emitted from the stream of HID reports.
        self._hidraw_buttons: dict[int, bool] = {}
        # hidraw nodes whose open/read error has already been logged, so a
        # permission problem is reported once rather than every poll.
        self._hidraw_errors: set[str] = set()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        sdl_environment = {
            "SDL_VIDEODRIVER": os.environ.get("SDL_VIDEODRIVER"),
            "SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS": os.environ.get("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"),
        }
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
        try:
            if self._pygame is None:
                os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
                self._pygame = importlib.import_module("pygame")
            self._pygame.display.init()
            self._pygame.joystick.init()
            # Initialize the SDL game-controller subsystem alongside the
            # joystick subsystem so the Steam Deck trackpads emit touchpad
            # events. It is optional: if the ``pygame._sdl2.controller`` module
            # is unavailable the horn simply loses its trackpad source while all
            # other (joystick) controls keep working.
            self._init_controller_subsystem()
            controller_events = [
                self._pygame.JOYAXISMOTION,
                self._pygame.JOYBUTTONDOWN,
                self._pygame.JOYBUTTONUP,
                self._pygame.JOYHATMOTION,
                self._pygame.JOYDEVICEADDED,
                self._pygame.JOYDEVICEREMOVED,
            ]
            for name in (
                "CONTROLLERTOUCHPADDOWN",
                "CONTROLLERTOUCHPADMOTION",
                "CONTROLLERTOUCHPADUP",
            ):
                event_type = getattr(self._pygame, name, None)
                if event_type is not None:
                    controller_events.append(event_type)
            self._pygame.event.set_blocked(None)
            self._pygame.event.set_allowed(controller_events)
            for device_index in range(self._pygame.joystick.get_count()):
                self._add_device(device_index)
            self._start_hidraw_readers()
            self._started = True
        except ImportError as exc:
            raise ControllerUnavailable("pygame is not installed; touch controls remain available") from exc
        except RuntimeError as exc:
            raise ControllerUnavailable(f"SDL controller initialization failed: {exc}") from exc
        finally:
            for name, value in sdl_environment.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def _init_controller_subsystem(self) -> None:
        # Locate the optional ``pygame._sdl2.controller`` module and initialize
        # it so devices can be opened as game controllers (a prerequisite for
        # touchpad events). Prefer importing the submodule of whatever pygame
        # package we are using; fall back to an already-attached ``_sdl2``
        # attribute (used by the tests' fake pygame). Any failure simply leaves
        # the trackpad horn disabled without affecting the joystick controls.
        self._controller_module = None
        controller = None
        module_name = getattr(self._pygame, "__name__", None)
        if module_name:
            try:
                controller = importlib.import_module(f"{module_name}._sdl2.controller")
            except ImportError:
                controller = None
        if controller is None:
            controller = getattr(getattr(self._pygame, "_sdl2", None), "controller", None)
        if controller is None:
            log.info("SDL game-controller touchpad support unavailable; trackpad horn disabled")
            return
        try:
            controller.init()
        except (RuntimeError, AttributeError) as exc:
            log.warning("Unable to initialize SDL game-controller subsystem: %s", exc)
            return
        self._controller_module = controller

    def _start_hidraw_readers(self) -> None:
        # Start a background reader per Steam Deck hidraw node so the built-in
        # trackpads can drive the horn even though SDL never surfaces them as
        # controller touchpads. This only does anything when a pad is actually
        # bound to an action *and* a Deck controller is present, so it stays
        # completely inert on other hardware (``_find_deck_hidraw_paths`` returns
        # nothing there).
        if not self.profile.touchpads:
            return
        paths = _find_deck_hidraw_paths()
        if not paths:
            return
        self._hidraw_queue = queue.Queue()
        for path in paths:
            reader = _HidrawTrackpadReader(path, self._hidraw_queue)
            reader.start()
            self._hidraw_readers.append(reader)
        log.info("Reading Steam Deck trackpads directly from hidraw: %s", ", ".join(paths))

    def _stop_hidraw_readers(self) -> None:
        for reader in self._hidraw_readers:
            reader.stop()
        self._hidraw_readers.clear()
        self._hidraw_queue = None
        self._hidraw_pad_touched.clear()
        self._hidraw_buttons.clear()
        self._hidraw_errors.clear()

    def _drain_hidraw_pads(self) -> list[DeckAction]:
        # Translate any queued Deck HID reports into the same ``quilling_horn``
        # touch actions the SDL touchpad path produces. Each report carries both
        # pads' current touch state and coordinates, so only the most recent one
        # per node matters: drain the queue, keep the latest, then diff it
        # against the last-known touch state to emit motion while a finger is
        # down and a single release when it lifts.
        if self._hidraw_queue is None:
            return []
        latest: dict[str, bytes] = {}
        while True:
            try:
                kind, path, payload = self._hidraw_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "error":
                if path not in self._hidraw_errors:
                    self._hidraw_errors.add(path)
                    log.warning("Steam Deck trackpad hidraw %s: %s", path, payload)
                continue
            latest[path] = payload
        actions: list[DeckAction] = []
        for payload in latest.values():
            actions.extend(self._hidraw_paddle_actions(payload))
            decoded = _decode_deck_pads(payload)
            if decoded is None:
                continue
            lpad_touched, (_lx, ly), rpad_touched, (_rx, ry) = decoded
            actions.extend(self._hidraw_pad_action(_DECK_LEFT_TOUCH_ID, lpad_touched, ly))
            actions.extend(self._hidraw_pad_action(_DECK_RIGHT_TOUCH_ID, rpad_touched, ry))
        return actions

    def _hidraw_paddle_actions(self, payload: bytes) -> list[DeckAction]:
        # Turn the paddle bits of one report into press/release actions, feeding them
        # through the same ``_button_actions`` path the SDL buttons use so a paddle is
        # bound, repeated and chorded exactly like any other button. Only edges are
        # emitted; a held paddle produces nothing until it changes.
        pressed_by_index = _decode_deck_paddles(payload)
        if pressed_by_index is None:
            return []
        actions: list[DeckAction] = []
        for index, pressed in pressed_by_index.items():
            if self._hidraw_buttons.get(index) == pressed:
                continue
            self._hidraw_buttons[index] = pressed
            actions.extend(self._button_actions(index, pressed))
        return actions

    def _hidraw_pad_action(self, touch_id: int, touched: bool, raw_y: int) -> list[DeckAction]:
        # Bridge one pad's raw HID state into the existing touch handlers so the
        # horn behaves identically to the SDL touchpad path: a bound, touched pad
        # feeds its vertical fraction through ``_touch_moved`` (finger 0), and a
        # lift emits a single ``_touch_up``.
        if self.profile.touchpads.get(touch_id) is None:
            return []
        if touched:
            self._hidraw_pad_touched[touch_id] = True
            return self._touch_moved(touch_id, 0, _deck_pad_y_fraction(raw_y))
        if self._hidraw_pad_touched.get(touch_id):
            self._hidraw_pad_touched[touch_id] = False
            return self._touch_up(touch_id, 0)
        return []

    def stop(self) -> None:
        self._stop_hidraw_readers()
        for joystick in self._joysticks.values():
            try:
                joystick.quit()
            except RuntimeError:
                pass
        self._joysticks.clear()
        for controller in self._controllers.values():
            try:
                controller.quit()
            except (RuntimeError, AttributeError):
                pass
        self._controllers.clear()
        self._touch_fingers.clear()
        self._active_axes.clear()
        self._trigger_pressed.clear()
        self._trigger_long_press_pressed_at.clear()
        self._held_buttons.clear()
        self._fired_chords.clear()
        self._hat_y = 0
        self._hat_x = 0
        self._long_press_pressed_at.clear()
        self._long_press_chorded.clear()
        self._started = False

    def poll(self) -> list[DeckAction]:
        if self._pygame is None:
            return []
        # The Steam Deck trackpads arrive as SDL game-controller touchpad
        # events. Resolve their (optional) type constants once so the decode
        # branches below never touch a missing attribute on an older SDL/pygame
        # build or on the joystick-only test fakes.
        touch_down = getattr(self._pygame, "CONTROLLERTOUCHPADDOWN", None)
        touch_motion = getattr(self._pygame, "CONTROLLERTOUCHPADMOTION", None)
        touch_up = getattr(self._pygame, "CONTROLLERTOUCHPADUP", None)
        # On the Steam Deck the built-in trackpads never arrive as SDL touchpad
        # events, so fold in any pad motion read directly from hidraw first (a
        # no-op on other hardware / when no reader is running).
        actions: list[DeckAction] = self._drain_hidraw_pads()
        for event in self._pygame.event.get():
            if event.type == self._pygame.JOYAXISMOTION:
                binding = self.profile.axes.get(event.axis)
                if binding is not None:
                    if binding.action in TRIGGER_BUTTON_ACTIONS:
                        actions.extend(self._trigger_button_actions(event.axis, binding, float(event.value)))
                    elif binding.action in LONG_PRESS_ACTIONS:
                        actions.extend(self._trigger_long_press_actions(event.axis, binding, float(event.value)))
                    else:
                        if binding.trigger:
                            value = self._normalize_trigger(event.axis, float(event.value))
                            if binding.invert:
                                value = 1.0 - value if value else 0.0
                        else:
                            value = self._normalize_axis(event.axis, float(event.value))
                            if binding.invert:
                                value = -value
                        actions.append(DeckAction(binding.action, binding.target, value, "changed"))
            elif event.type in (self._pygame.JOYBUTTONDOWN, self._pygame.JOYBUTTONUP):
                actions.extend(self._button_actions(event.button, event.type == self._pygame.JOYBUTTONDOWN))
            elif event.type == self._pygame.JOYHATMOTION:
                actions.extend(self._hat_actions(event.value))
            elif event.type == self._pygame.JOYDEVICEADDED:
                self._add_device(event.device_index)
            elif event.type == self._pygame.JOYDEVICEREMOVED:
                self._remove_device(event.instance_id)
                actions.append(DeckAction("disconnect", "global", 0.0, "disconnected"))
            elif touch_up is not None and event.type == touch_up:
                # A finger lifted from a trackpad; the horn keeps sounding while
                # other fingers remain and stops when the last one lifts.
                actions.extend(self._touch_up(event.touch_id, event.finger))
            elif (touch_down is not None and event.type == touch_down) or (
                touch_motion is not None and event.type == touch_motion
            ):
                # A finger touched or moved on a trackpad; the horn fraction
                # tracks its absolute vertical position (top ~ off, bottom ~ full).
                actions.extend(self._touch_moved(event.touch_id, event.finger, float(event.y)))
        return actions

    def capability_warnings(self, *, axis_count: int, button_count: int) -> str:
        warnings = [f"axis {axis}" for axis in self.profile.axes if axis >= axis_count]
        configured_buttons = set(self.profile.buttons)
        for chord in self.profile.chords:
            configured_buttons.update(chord.buttons)
        # The back paddles are served by the raw HID reader, not SDL, so they are
        # available even though Steam Input keeps them out of the button count.
        configured_buttons -= set(_DECK_PADDLE_BUTTONS)
        warnings.extend(f"button {button}" for button in sorted(configured_buttons) if button >= button_count)
        return ", ".join(warnings)

    def _normalize_axis(self, axis: int, value: float) -> float:
        magnitude = abs(value)
        if axis in self._active_axes:
            if magnitude <= self.profile.dead_zone - self.profile.hysteresis:
                self._active_axes.discard(axis)
                return 0.0
        elif magnitude <= self.profile.dead_zone:
            return 0.0
        else:
            self._active_axes.add(axis)
        scaled = max(0.0, (magnitude - self.profile.dead_zone) / (1.0 - self.profile.dead_zone))
        return math.copysign(min(1.0, scaled), value) if scaled else 0.0

    def _normalize_trigger(self, axis: int, value: float) -> float:
        # SDL analog triggers rest at ``-1.0`` and travel to ``+1.0`` when fully
        # depressed, unlike sticks that rest centered at ``0.0``. Map that
        # ``[-1, +1]`` travel onto ``[0, 1]``. Triggers use their own, much
        # smaller ``trigger_dead_zone`` (rather than the stick ``dead_zone``) so
        # the horn responds almost as soon as the trigger leaves its resting
        # position, while still guarding against a released trigger whose idle
        # value drifts slightly off ``-1.0``.
        fraction = (value + 1.0) / 2.0
        fraction = max(0.0, min(1.0, fraction))
        dead_zone = self.profile.trigger_dead_zone
        release = max(0.0, dead_zone - self.profile.hysteresis)
        if axis in self._active_axes:
            if fraction <= release:
                self._active_axes.discard(axis)
                return 0.0
        elif fraction <= dead_zone:
            return 0.0
        else:
            self._active_axes.add(axis)
        scaled = (fraction - dead_zone) / (1.0 - dead_zone)
        return min(1.0, max(0.0, scaled))

    def _trigger_button_actions(self, axis: int, binding: AxisBinding, value: float) -> list[DeckAction]:
        # A discrete action (e.g. focus_left/focus_right) bound to an analog
        # trigger fires once each time the trigger is squeezed past its dead
        # zone. ``_normalize_trigger`` applies the trigger dead zone and
        # hysteresis (returning 0.0 while the trigger rests), so any non-zero
        # fraction means the trigger is engaged. The command is emitted only on
        # the rising edge; the trigger must return to its resting position
        # before it can fire again.
        fraction = self._normalize_trigger(axis, value)
        if fraction > 0.0:
            if axis in self._trigger_pressed:
                return []
            self._trigger_pressed.add(axis)
            return [DeckAction(binding.action, binding.target, 1.0, "pressed")]
        self._trigger_pressed.discard(axis)
        return []

    def _trigger_long_press_actions(self, axis: int, binding: AxisBinding, value: float) -> list[DeckAction]:
        # A startup/shutdown action bound to an analog trigger makes the trigger
        # behave like the equivalent button: squeezing it past the dead zone is
        # a press and letting it return to rest is a release. As with the
        # button, the command is emitted once on release and distinguishes a
        # short press (*_IMMEDIATE) from a hold of at least ``LONG_PRESS_SECONDS``
        # (*_DELAYED). ``_normalize_trigger`` applies the trigger dead zone and
        # hysteresis, so any non-zero fraction means the trigger is engaged.
        fraction = self._normalize_trigger(axis, value)
        immediate, delayed = LONG_PRESS_ACTIONS[binding.action]
        if fraction > 0.0:
            if axis in self._trigger_pressed:
                return []
            self._trigger_pressed.add(axis)
            self._trigger_long_press_pressed_at[axis] = self._clock()
            return []
        if axis not in self._trigger_pressed:
            return []
        self._trigger_pressed.discard(axis)
        pressed_at = self._trigger_long_press_pressed_at.pop(axis, None)
        if pressed_at is None:
            return []
        held = self._clock() - pressed_at
        name = delayed if held >= LONG_PRESS_SECONDS else immediate
        return [DeckAction(name, binding.target, 1.0, "pressed")]

    def _normalize_touch_y(self, y: float) -> float:
        # A trackpad reports a finger position with ``y`` running 0.0 at the top
        # edge to 1.0 at the bottom. Map that onto a horn fraction so the top of
        # the pad is off/soft and the bottom is full, with a small top dead zone
        # so a finger resting near the top does not sound the horn. This mirrors
        # the on-screen vertical horn slider (drag down for more).
        y = max(0.0, min(1.0, y))
        dead_zone = self.profile.touch_dead_zone
        if y <= dead_zone:
            return 0.0
        return (y - dead_zone) / (1.0 - dead_zone)

    def _touch_moved(self, touch_id: int, finger: int, y: float) -> list[DeckAction]:
        binding = self.profile.touchpads.get(touch_id)
        if binding is None:
            return []
        # Track the finger's position so a later lift can tell whether any
        # fingers remain on this pad; the most recently moved finger drives the
        # horn intensity.
        self._touch_fingers.setdefault(touch_id, {})[finger] = y
        fraction = self._normalize_touch_y(y)
        return [DeckAction(binding.action, binding.target, fraction, "changed")]

    def _touch_up(self, touch_id: int, finger: int) -> list[DeckAction]:
        binding = self.profile.touchpads.get(touch_id)
        if binding is None:
            return []
        fingers = self._touch_fingers.get(touch_id)
        if not fingers:
            return []
        fingers.pop(finger, None)
        if fingers:
            # Other fingers remain on the pad, so keep the horn sounding, now
            # tracking a remaining finger's position (last one inserted wins).
            remaining_y = next(reversed(list(fingers.values())))
            return [DeckAction(binding.action, binding.target, self._normalize_touch_y(remaining_y), "changed")]
        # The last finger lifted: stop the horn.
        self._touch_fingers.pop(touch_id, None)
        return [DeckAction(binding.action, binding.target, 0.0, "changed")]

    def _button_actions(self, button: int, pressed: bool) -> list[DeckAction]:
        actions: list[DeckAction] = []
        # A button can reach this from two routes -- SDL, and the raw HID reader for
        # the back paddles -- and in Desktop Mode both see the same paddle. Treat
        # ``_held_buttons`` as the single source of truth so whichever route reports
        # the edge first wins and the other is a no-op, rather than firing twice.
        if pressed == (button in self._held_buttons):
            return actions
        completed_chord = False
        if pressed:
            self._held_buttons.add(button)
            for chord in self.profile.chords:
                if chord not in self._fired_chords and chord.buttons.issubset(self._held_buttons):
                    self._fired_chords.add(chord)
                    actions.append(DeckAction(chord.action, chord.target, 1.0, "pressed"))
                    completed_chord = completed_chord or button in chord.buttons
                    # Remember that a long-press button took part in a chord so
                    # its release does not additionally fire a startup/shutdown
                    # command.
                    self._long_press_chorded.update(self._long_press_buttons & chord.buttons)
        else:
            self._held_buttons.discard(button)
            # Emit a release for any chord that is no longer fully held. A chord that
            # stands in for a press-and-hold (the admin panel chords) needs the
            # release to cancel the hold it started.
            still_held = set()
            for chord in self._fired_chords:
                if chord.buttons.issubset(self._held_buttons):
                    still_held.add(chord)
                else:
                    actions.append(DeckAction(chord.action, chord.target, 0.0, "released"))
            self._fired_chords = still_held
        if completed_chord:
            # This press completed a chord, which is its own gesture: don't also fire
            # the button's individual command. Otherwise L1+A would shut the machine
            # down *and* run sequence control on the engine.
            return actions
        binding = self.profile.buttons.get(button)
        if binding is None:
            if pressed and button not in self._logged_unbound:
                # Log unbound presses so the physical-button-to-index mapping of a
                # particular controller can be discovered from the log when adding a
                # binding for a button whose SDL index is not known up front. Once per
                # index, not per press.
                self._logged_unbound.add(button)
                log.info("Steam Deck button %s pressed but not bound by the profile", button)
            return actions
        if binding.action in LONG_PRESS_ACTIONS:
            actions.extend(self._long_press_button_actions(button, binding, pressed))
            return actions
        actions.append(
            DeckAction(
                binding.action,
                binding.target,
                1.0 if pressed else 0.0,
                "pressed" if pressed else "released",
                button,
            )
        )
        return actions

    def _long_press_button_actions(self, button: int, binding: ButtonBinding, pressed: bool) -> list[DeckAction]:
        # Distinguish a short press (*_IMMEDIATE) from a long press (*_DELAYED);
        # the command is emitted once, on release. If the button also completes
        # a chord while held (e.g. the L1+R1 halt chord), the startup/shutdown
        # command is suppressed so an emergency stop never also starts or shuts
        # down the engine.
        immediate, delayed = LONG_PRESS_ACTIONS[binding.action]
        if pressed:
            self._long_press_pressed_at[button] = self._clock()
            return []
        pressed_at = self._long_press_pressed_at.pop(button, None)
        chorded = button in self._long_press_chorded
        self._long_press_chorded.discard(button)
        if chorded or pressed_at is None:
            return []
        held = self._clock() - pressed_at
        name = delayed if held >= LONG_PRESS_SECONDS else immediate
        return [DeckAction(name, binding.target, 1.0, "pressed", button)]

    def _hat_actions(self, value: Any) -> list[DeckAction]:
        # The D-pad reports as an SDL hat; ``value`` is an ``(x, y)`` tuple with
        # ``y == 1`` up, ``y == -1`` down, ``x == 1`` right, and ``x == -1``
        # left. Emit a single one-shot action each time a direction changes to a
        # non-neutral position so the catalog scrolls/selects one step per press.
        try:
            x, y = value
        except (TypeError, ValueError):
            return []
        x = int(x)
        y = int(y)
        actions: list[DeckAction] = []
        if y != self._hat_y:
            previous_y = self._hat_y
            self._hat_y = y
            # Report whether the catalog-jump modifier (R1) is held as this direction
            # is pressed, so the router can turn the press into a jump to the
            # first/last catalog entry rather than a one-entry scroll.
            jump = bool(self.profile.catalog_jump_modifier_buttons & self._held_buttons)
            # Emit a release for the previously held vertical direction so the
            # router can stop repeating the catalog scroll it fires while the
            # D-pad up/down is held.
            if previous_y > 0:
                actions.append(DeckAction(DPAD_UP, "focused", 0.0, "released"))
            elif previous_y < 0:
                actions.append(DeckAction(DPAD_DOWN, "focused", 0.0, "released"))
            if y > 0:
                actions.append(DeckAction(DPAD_UP, "focused", 1.0, "pressed", jump_modifier=jump))
            elif y < 0:
                actions.append(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed", jump_modifier=jump))
        if x != self._hat_x:
            previous_x = self._hat_x
            self._hat_x = x
            # Emit a release for the previously held horizontal direction so the
            # router can stop repeating the boost/brake command it fires while
            # the D-pad left/right is held.
            if previous_x > 0:
                actions.append(DeckAction(DPAD_RIGHT, "focused", 0.0, "released"))
            elif previous_x < 0:
                actions.append(DeckAction(DPAD_LEFT, "focused", 0.0, "released"))
            if x > 0:
                actions.append(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))
            elif x < 0:
                actions.append(DeckAction(DPAD_LEFT, "focused", 1.0, "pressed"))
        return actions

    def _add_device(self, device_index: int) -> None:
        try:
            joystick = self._pygame.joystick.Joystick(device_index)
            joystick.init()
            instance_id = joystick.get_instance_id()
            current = self._joysticks.get(instance_id)
            if current is not None:
                if joystick is not current:
                    joystick.quit()
                return
            self._joysticks[instance_id] = joystick
            warning = self.capability_warnings(
                axis_count=joystick.get_numaxes(), button_count=joystick.get_numbuttons()
            )
            log.info(
                "SDL controller connected: name=%s guid=%s axes=%s buttons=%s",
                joystick.get_name(),
                joystick.get_guid(),
                joystick.get_numaxes(),
                joystick.get_numbuttons(),
            )
            if warning:
                log.warning("Configured Steam Deck controls unavailable: %s", warning)
            self._open_controller(device_index, instance_id)
        except RuntimeError as exc:
            log.warning("Unable to open SDL controller %s: %s", device_index, exc)

    def _open_controller(self, device_index: int, instance_id: int) -> None:
        # Additionally open the device as an SDL game controller. This activates
        # SDL's controller mapping, which renumbers the joystick axes to the
        # standard game-controller order the profile is calibrated against (e.g.
        # on a Steam Deck L2 = axis 2 and R2 = axis 5). It is best-effort: a
        # build without game-controller support simply leaves the raw axis order
        # in place while every joystick control keeps working. On the Steam Deck
        # the built-in trackpads are read directly from hidraw (see
        # ``_HidrawTrackpadReader``), not through this controller handle.
        if self._controller_module is None or instance_id in self._controllers:
            return
        try:
            controller = self._controller_module.Controller(device_index)
            controller.init()
        except (RuntimeError, AttributeError) as exc:
            log.info("Unable to open SDL game controller %s: %s", device_index, exc)
            return
        self._controllers[instance_id] = controller

    def _remove_device(self, instance_id: int) -> None:
        joystick = self._joysticks.pop(instance_id, None)
        if joystick is not None:
            log.info("SDL controller disconnected: name=%s", joystick.get_name())
            try:
                joystick.quit()
            except RuntimeError:
                pass
        controller = self._controllers.pop(instance_id, None)
        if controller is not None:
            try:
                controller.quit()
            except (RuntimeError, AttributeError):
                pass
        self._touch_fingers.clear()
        self._active_axes.clear()
        self._trigger_pressed.clear()
        self._trigger_long_press_pressed_at.clear()
        self._held_buttons.clear()
        self._fired_chords.clear()
        self._hat_y = 0
        self._hat_x = 0
        self._long_press_pressed_at.clear()
        self._long_press_chorded.clear()


class DeckInputRouter:
    def __init__(
        self,
        profile: ControlProfile,
        *,
        left: Callable[[], Any],
        right: Callable[[], Any],
        focused: Callable[[], Any],
        global_actions: Mapping[str, Callable[[], None]],
    ) -> None:
        self.profile = profile
        self._left = left
        self._right = right
        self._focused = focused
        self._global_actions = global_actions
        self._throttles: dict[Target, float] = {}
        self._commanded_speeds: dict[Target, float] = {}
        self._quills: dict[Target, float] = {}
        self._boosts: dict[Target, str] = {}
        # Maps a target to ``[delta, next_scroll_time]`` for a held catalog
        # scroll. ``next_scroll_time`` is ``None`` until the auto-repeat is armed
        # on the first ``tick()`` after the press (arming it ``tick()``-side keeps
        # the timing on the same clock ``tick()`` uses).
        self._scrolls: dict[Target, list] = {}
        # Maps a held button to ``[target, command, interval, next_send_time]`` so
        # each repeating button keeps its own cadence.
        self._held_commands: dict[int, list] = {}
        self._sequences: dict[Target, int] = {}
        self._direction_latches: set[Target] = set()
        self._last_tick: float | None = None

    def handle(self, action: DeckAction) -> None:
        if action.name == "disconnect":
            self.clear()
            return
        if self._controls_only(action):
            return
        if action.name == "throttle":
            if action.value == 0.0:
                self._throttles.pop(action.target, None)
                self._commanded_speeds.pop(action.target, None)
            else:
                self._throttles[action.target] = max(-1.0, min(1.0, action.value))
            return
        if action.name == "direction":
            self._handle_direction(action)
            return
        if action.name == QUILLING_HORN:
            # Store the current trigger fraction; ``tick()`` re-sends the horn
            # every ``repeat_interval`` while it is held. A fraction of ``0.0``
            # means the trigger returned to its dead zone, so stop sounding.
            if action.value > 0.0:
                self._quills[action.target] = min(1.0, action.value)
            else:
                self._quills.pop(action.target, None)
            return
        if action.name in (DPAD_UP, DPAD_DOWN):
            # D-pad up/down must react to both press and release so ``tick()``
            # can repeat the boost/brake (no catalog) or catalog-scroll (catalog
            # open) command while the key is held and stop on release; handle it
            # before the ``pressed``-only guard below.
            self._handle_scroll_boost(action)
            return
        if action.name in ADMIN_COMMANDS:
            # Both phases matter: the press starts the panel button's hold and the
            # release cancels it, so handle this before the ``pressed``-only guard.
            self._handle_admin_command(action)
            return
        if action.name in (DPAD_LEFT, DPAD_RIGHT):
            # D-pad left/right select/close the catalog (when open) or adjust the
            # smoke output (one-shot); neither repeats, but route it here to keep
            # the D-pad handling together.
            self._handle_select_smoke(action)
            return
        if action.button is not None and action.name in PANEL_COMMANDS:
            binding = self.profile.buttons.get(action.button)
            if binding is not None and binding.repeat:
                # A repeat-flagged panel button (e.g. the X/Y buttons) must react
                # to both press and release so ``tick()`` can re-send its command
                # while it is held and stop on release; handle it before the
                # ``pressed``-only guard below.
                self._handle_repeat_command(action)
                return
        if action.phase != "pressed":
            return
        if action.target == "global":
            callback = self._global_actions.get(action.name)
            if callback is not None:
                callback()
            return
        gui = self._target_gui(action.target)
        if gui is None:
            return
        if action.name == STARTUP_IMMEDIATE:
            # A short press of a startup button starts the engine immediately.
            gui.on_engine_command("START_UP_IMMEDIATE")
            return
        if action.name == STARTUP_DELAYED:
            # A long press requests the delayed start-up sequence, falling back
            # to the immediate start-up for TMCC engines that lack it.
            gui.on_engine_command(["START_UP_DELAYED", "START_UP_IMMEDIATE"])
            return
        if action.name == SHUTDOWN_IMMEDIATE:
            # A short press of a shutdown button shuts the engine down immediately.
            gui.on_engine_command("SHUTDOWN_IMMEDIATE")
            return
        if action.name == SHUTDOWN_DELAYED:
            # A long press requests the delayed shut-down sequence, falling back
            # to the immediate shut-down for TMCC engines that lack it.
            gui.on_engine_command(["SHUTDOWN_DELAYED", "SHUTDOWN_IMMEDIATE"])
            return
        if action.name == SEQUENCE_CONTROL:
            # The A button runs the engine's automatic sequence control. While
            # the catalog panel is open it confirms the highlighted entry
            # (mirroring the A button's catalog behavior); otherwise it sends
            # AUX1_OPTION_ONE every ``repeat_interval`` (100 ms) for
            # ``SEQUENCE_CONTROL_DURATION`` seconds. The command is fired once
            # immediately and ``tick()`` re-sends the remainder of the burst.
            if getattr(gui, "catalog_visible", False):
                gui.select_catalog_entry()
                return
            repeats = max(1, round(SEQUENCE_CONTROL_DURATION / self.profile.repeat_interval))
            gui.on_engine_command(SEQUENCE_CONTROL_COMMAND)
            if repeats > 1:
                self._sequences[action.target] = repeats - 1
            else:
                self._sequences.pop(action.target, None)
            return
        if action.name == "scope_catalog":
            gui.show_scope_catalog()
            return
        if action.button == SELECT_BUTTON and getattr(gui, "catalog_visible", False):
            # While the catalog panel is open, the A button confirms the
            # highlighted entry instead of performing its assigned action.
            gui.select_catalog_entry()
            return
        if action.button == CLOSE_POPUP_BUTTON and getattr(gui, "popup_visible", False):
            # While a popup panel is displayed, the X button closes it instead
            # of performing its assigned action.
            gui.close_popup()
            return
        if action.name == ADMIN_CHORD_MODIFIER and getattr(gui, "admin_visible", False):
            # L1 is the admin chord modifier while that panel is up: no coupler.
            return
        if action.name == CATALOG_JUMP_MODIFIER and getattr(gui, "catalog_visible", False):
            # While the catalog panel is open, R1 is the jump modifier rather than a
            # coupler button: it performs no action of its own, and the D-pad press
            # made while it is held does the jumping.
            return
        command = PANEL_COMMANDS.get(action.name)
        if command is not None:
            gui.on_engine_command(command)

    def tick(self, now: float) -> None:
        if self._last_tick is None:
            self._last_tick = now
            return
        elapsed = now - self._last_tick
        if elapsed + 1e-9 < self.profile.repeat_interval:
            return
        self._last_tick = now
        elapsed = min(elapsed, max(0.25, self.profile.repeat_interval))
        for target, value in tuple(self._throttles.items()):
            gui = self._target_gui(target)
            state = getattr(gui, "throttle_state", None) if gui is not None else None
            if state is None:
                continue
            if getattr(state, "is_cab1", False):
                relative_speed = int(math.copysign(max(1, round(abs(value) * 5)), value))
                gui.on_speed_command(relative_speed)
                continue
            current = self._commanded_speeds.setdefault(target, float(getattr(state, "speed", 0) or 0))
            speed_max = max(0, int(getattr(state, "speed_max", 199) or 199))
            next_speed = max(0.0, min(float(speed_max), current + value * self.profile.throttle_rate * elapsed))
            self._commanded_speeds[target] = next_speed
            command_speed = round(next_speed)
            if command_speed != round(current):
                gui.on_speed_command(command_speed)
        for target, fraction in tuple(self._quills.items()):
            gui = self._target_gui(target)
            if gui is None:
                continue
            # Emit the fallback list with an intensity: a Legacy engine sounds
            # the Quilling Horn scaled to the trigger position (clamped to a
            # minimum of 1 so a light hold is still audible) while a non-Legacy
            # engine falls through to the plain Blow Horn (intensity ignored).
            intensity = max(1, min(HORN_MAX_INTENSITY, round(fraction * HORN_MAX_INTENSITY)))
            gui.on_engine_command(HORN_COMMAND, data=intensity)
        for target, command in tuple(self._boosts.items()):
            # Re-send the boost/brake command every ``repeat_interval`` (100 ms)
            # for as long as the D-pad left/right is held.
            gui = self._target_gui(target)
            if gui is None:
                continue
            gui.on_engine_command(command)
        for target, entry in tuple(self._scrolls.items()):
            # Auto-repeat the catalog scroll while the D-pad up/down is held, but
            # only after an initial ``CATALOG_SCROLL_INITIAL_DELAY`` (500 ms) hold
            # and then only once every ``CATALOG_SCROLL_REPEAT_INTERVAL`` (200 ms)
            # so catalog selection is not too quick. Stop if the catalog panel is
            # no longer open.
            gui = self._target_gui(target)
            if gui is None or not getattr(gui, "catalog_visible", False):
                self._scrolls.pop(target, None)
                continue
            delta, next_scroll_time = entry
            if next_scroll_time is None:
                # First tick after the press: arm the auto-repeat to begin one
                # initial delay from now (the immediate scroll already happened
                # on press).
                entry[1] = now + CATALOG_SCROLL_INITIAL_DELAY
                continue
            if now + 1e-9 >= next_scroll_time:
                gui.scroll_catalog(delta)
                entry[1] = now + CATALOG_SCROLL_REPEAT_INTERVAL
        for _button, entry in tuple(self._held_commands.items()):
            # Re-send a held panel command (e.g. the X/Y buttons) for as long as the
            # button is held, at that button's own cadence. Time is accumulated from
            # the elapsed figure this tick already computed rather than compared
            # against an absolute deadline, so the repeat does not depend on the
            # caller's clock matching any clock read at press time. ``tick()`` itself
            # only runs every ``repeat_interval``, so an interval is honoured to
            # within one tick.
            target, command, interval, waited = entry
            waited += elapsed
            entry[3] = waited
            if waited + 1e-9 < interval:
                continue
            gui = self._target_gui(target)
            if gui is None:
                continue
            gui.on_engine_command(command)
            entry[3] = 0.0
        for target, remaining in tuple(self._sequences.items()):
            # Continue the automatic sequence control started by the A button:
            # emit AUX1_OPTION_ONE once per tick (every ``repeat_interval``)
            # until the ``SEQUENCE_CONTROL_DURATION`` burst has completed.
            gui = self._target_gui(target)
            if gui is None:
                self._sequences.pop(target, None)
                continue
            gui.on_engine_command(SEQUENCE_CONTROL_COMMAND)
            if remaining <= 1:
                self._sequences.pop(target, None)
            else:
                self._sequences[target] = remaining - 1

    def clear(self) -> None:
        self._throttles.clear()
        self._commanded_speeds.clear()
        self._quills.clear()
        self._boosts.clear()
        self._scrolls.clear()
        self._held_commands.clear()
        self._sequences.clear()
        self._direction_latches.clear()
        self._last_tick = None

    def _handle_repeat_command(self, action: DeckAction) -> None:
        if action.phase != "pressed":
            # Button released: stop repeating its command.
            self._held_commands.pop(action.button, None)
            return
        gui = self._target_gui(action.target)
        if gui is None:
            return
        if action.button == CLOSE_POPUP_BUTTON and getattr(gui, "popup_visible", False):
            # While a popup panel is displayed, the X button closes it instead of
            # performing (or repeating) its assigned command.
            self._held_commands.pop(action.button, None)
            gui.close_popup()
            return
        # Fire the panel command once immediately for responsiveness, then
        # ``tick()`` re-sends it until the button is released -- every
        # ``repeat_interval`` from the profile, or the button's own override where it
        # sets one (volume steps want a slower cadence than the horn).
        command = PANEL_COMMANDS[action.name]
        binding = self.profile.buttons.get(action.button)
        interval = self.profile.repeat_interval
        if binding is not None and binding.repeat_interval is not None:
            interval = binding.repeat_interval
        self._held_commands[action.button] = [action.target, command, interval, 0.0]
        gui.on_engine_command(command)

    def _controls_only(self, action: DeckAction) -> bool:
        """True when the controls screen is up and this action must not reach the layout.

        Reading the help screen should not drive the train. Everything analog and every
        engine command is dropped while it is displayed; the D-pad is turned into page
        navigation, and X still closes the panel through the popup handling below.
        """
        if action.name == SHOW_CONTROLS:
            return False
        gui = self._target_gui(action.target)
        if gui is None or not getattr(gui, "controls_visible", False):
            # Global-target actions (HALT, focus) resolve no gui and are never gated:
            # HALT in particular has to work whatever is on screen.
            return False
        if action.name in (DPAD_UP, DPAD_DOWN):
            if action.phase == "pressed":
                gui.page_controls(forward=action.name == DPAD_DOWN)
            return True
        if action.button == CLOSE_POPUP_BUTTON:
            # Let the popup handling close it rather than duplicating that here.
            return False
        return True

    def _handle_admin_command(self, action: DeckAction) -> None:
        # An admin chord stands in for pressing and holding the matching admin panel
        # button: the press starts that button's hold (progress bar and all) and the
        # command fires only once it completes, so a chord cannot reboot or shut down
        # on a momentary fumble. The GUI re-checks that the panel is visible.
        gui = self._target_gui(action.target)
        if gui is None:
            return
        handler = getattr(gui, "on_admin_command", None)
        if handler is None:
            return
        handler(ADMIN_COMMANDS[action.name], action.phase == "pressed")

    def _handle_scroll_boost(self, action: DeckAction) -> None:
        if action.phase != "pressed":
            # D-pad released: stop repeating both the catalog scroll and the
            # boost/brake command.
            self._scrolls.pop(action.target, None)
            self._boosts.pop(action.target, None)
            return
        gui = self._target_gui(action.target)
        if gui is None:
            return
        if getattr(gui, "catalog_visible", False):
            # While the catalog panel is open, D-pad up/down scroll the
            # highlighted catalog entry (never boost/brake).
            self._boosts.pop(action.target, None)
            if action.jump_modifier:
                # R1 is held: jump the highlight to the first (up) or last (down)
                # entry without selecting it (the user confirms the entry
                # separately). Cancel any pending auto-repeat so a still-held D-pad
                # does not scroll away from the entry just jumped to.
                self._scrolls.pop(action.target, None)
                gui.scroll_catalog_to_end(to_top=action.name == DPAD_UP)
                return
            # Single press: scroll one entry immediately for responsiveness, then
            # ``tick()`` arms the auto-repeat only after the key has been held for
            # ``CATALOG_SCROLL_INITIAL_DELAY`` (500 ms) and thereafter re-scrolls
            # every ``CATALOG_SCROLL_REPEAT_INTERVAL`` (200 ms) while held, so
            # catalog selection is not too quick. ``next_scroll_time`` starts as
            # ``None`` (armed on the next tick).
            delta = -1 if action.name == DPAD_UP else 1
            self._scrolls[action.target] = [delta, None]
            gui.scroll_catalog(delta)
            return
        # Otherwise D-pad up boosts and D-pad down brakes the engine/train speed.
        # Fire once immediately for responsiveness, then ``tick()`` re-sends the
        # command every ``repeat_interval`` while it is held (``BOOST_SPEED`` /
        # ``BRAKE_SPEED`` resolve for both Legacy and TMCC).
        self._scrolls.pop(action.target, None)
        command = "BOOST_SPEED" if action.name == DPAD_UP else "BRAKE_SPEED"
        self._boosts[action.target] = command
        gui.on_engine_command(command)

    def _handle_select_smoke(self, action: DeckAction) -> None:
        if action.phase != "pressed":
            # D-pad left/right do not repeat, so only the press matters.
            return
        gui = self._target_gui(action.target)
        if gui is None:
            return
        if getattr(gui, "catalog_visible", False):
            # While the catalog panel is open, D-pad right confirms the
            # highlighted entry (mirroring the A button) and D-pad left
            # cancels/closes the panel; neither repeats.
            if action.name == DPAD_RIGHT:
                gui.select_catalog_entry()
            else:
                gui.hide_scope_catalog()
            return
        # Otherwise the D-pad adjusts the engine/train smoke output as a one-shot
        # (no repeat): right raises it (``SMOKE_ON``) and left lowers it
        # (``SMOKE_OFF``). ``SMOKE_ON``/``SMOKE_OFF`` resolve automatically per
        # control type: for a Legacy target they step the smoke level up/down
        # (Off/Low/Medium/High), and for a non-Legacy (TMCC/Cab-1/R100) target
        # they simply turn smoke on/off.
        gui.on_engine_command("SMOKE_ON" if action.name == DPAD_RIGHT else "SMOKE_OFF")

    def _handle_direction(self, action: DeckAction) -> None:
        release_threshold = self.profile.direction_threshold - self.profile.hysteresis
        if abs(action.value) <= release_threshold:
            self._direction_latches.discard(action.target)
            return
        if abs(action.value) < self.profile.direction_threshold or action.target in self._direction_latches:
            return
        gui = self._target_gui(action.target)
        state = getattr(gui, "throttle_state", None) if gui is not None else None
        if state is None:
            return
        speed = int(getattr(state, "speed", 0) or 0)
        target_speed = int(getattr(state, "target_speed", 0) or 0)
        command = "FORWARD_DIRECTION" if action.value > 0 else "REVERSE_DIRECTION"
        is_current_direction = (
            bool(getattr(state, "is_forward", False))
            if command == "FORWARD_DIRECTION"
            else bool(getattr(state, "is_reverse", False))
        )
        self._direction_latches.add(action.target)
        if (speed != 0 or target_speed != 0) and is_current_direction:
            return
        gui.on_engine_command(command)

    def _target_gui(self, target: Target):
        if target == "left":
            return self._left()
        if target == "right":
            return self._right()
        if target == "focused":
            return self._focused()
        return None
