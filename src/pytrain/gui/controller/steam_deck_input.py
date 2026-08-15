#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import importlib
import json
import logging
import math
import os
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
}
AXIS_ACTIONS = {"throttle", "direction", "quilling_horn"}
# SDL "A" button. While the catalog panel is open it confirms the highlighted
# entry; otherwise it performs whatever action the profile assigns to it.
SELECT_BUTTON = 0
# SDL "X" button. While a popup panel is displayed it closes the popup;
# otherwise it performs whatever action the profile assigns to it.
CLOSE_POPUP_BUTTON = 2
# SDL D-pad (hat). On the Steam Deck the D-pad is reported as an SDL hat (the
# connect log shows every button index 0-10 and axis 0-5 already used by the
# sticks, triggers, and existing controls, leaving no room for it). While the
# catalog panel is open, up/down scroll the highlighted entry in the focused
# pane, right confirms the highlighted entry, and left cancels/closes the
# catalog panel; otherwise the D-pad has no assigned action.
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
}
# The A button runs the engine's "automatic sequence control": it sends the
# AUX1_OPTION_ONE command every ``repeat_interval`` (100 ms) for
# ``SEQUENCE_CONTROL_DURATION`` seconds, mirroring holding the physical AUX1
# button. ``AUX1_OPTION_ONE`` resolves for both Legacy (TMCC2) and non-Legacy
# (TMCC1) engines/trains, so the same command works regardless of control type.
SEQUENCE_CONTROL = "sequence_control"
SEQUENCE_CONTROL_COMMAND = "AUX1_OPTION_ONE"
SEQUENCE_CONTROL_DURATION = 3.1
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
# Fraction of the pad, measured from the top edge, treated as "off" so a finger
# resting at the very top does not sound the horn. Profiles may override it via
# ``touch_dead_zone``.
DEFAULT_TOUCH_DEAD_ZONE = 0.05
DEFAULT_PROFILE = Path(__file__).with_name("steam_deck_default.json")


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
            if action not in AXIS_ACTIONS:
                raise ProfileError(f"Action {action!r} cannot be assigned to an axis")
            if target not in ("left", "right"):
                raise ProfileError(f"Axis {index} requires a fixed panel target")
            axes[index] = AxisBinding(
                action,
                target,
                bool(raw_binding.get("invert", False)),
                bool(raw_binding.get("trigger", False)),
            )

        buttons: dict[int, ButtonBinding] = {}
        for raw_index, raw_binding in cls._mapping(data, "buttons").items():
            index = cls._index(raw_index, "button")
            action, target = cls._binding(raw_binding)
            if action in AXIS_ACTIONS:
                raise ProfileError(f"Action {action!r} cannot be assigned to a button")
            cls._validate_action_target(action, target)
            buttons[index] = ButtonBinding(action, target, bool(raw_binding.get("repeat", False)))

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
        self._held_buttons: set[int] = set()
        self._fired_chords: set[ChordBinding] = set()
        self._hat_y = 0
        self._hat_x = 0
        self._long_press_buttons = {
            index for index, binding in profile.buttons.items() if binding.action in LONG_PRESS_ACTIONS
        }
        self._long_press_pressed_at: dict[int, float] = {}
        self._long_press_chorded: set[int] = set()
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
            for name in ("CONTROLLERTOUCHPADDOWN", "CONTROLLERTOUCHPADMOTION", "CONTROLLERTOUCHPADUP"):
                event_type = getattr(self._pygame, name, None)
                if event_type is not None:
                    controller_events.append(event_type)
            self._pygame.event.set_blocked(None)
            self._pygame.event.set_allowed(controller_events)
            for device_index in range(self._pygame.joystick.get_count()):
                self._add_device(device_index)
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

    def stop(self) -> None:
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
        actions: list[DeckAction] = []
        for event in self._pygame.event.get():
            if event.type == self._pygame.JOYAXISMOTION:
                binding = self.profile.axes.get(event.axis)
                if binding is not None:
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
        if pressed:
            self._held_buttons.add(button)
            for chord in self.profile.chords:
                if chord not in self._fired_chords and chord.buttons.issubset(self._held_buttons):
                    self._fired_chords.add(chord)
                    actions.append(DeckAction(chord.action, chord.target, 1.0, "pressed"))
                    # Remember that a long-press button took part in a chord so
                    # its release does not additionally fire a startup/shutdown
                    # command.
                    self._long_press_chorded.update(self._long_press_buttons & chord.buttons)
        else:
            self._held_buttons.discard(button)
            self._fired_chords = {chord for chord in self._fired_chords if chord.buttons.issubset(self._held_buttons)}
        binding = self.profile.buttons.get(button)
        if binding is None:
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
            self._hat_y = y
            if y > 0:
                actions.append(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
            elif y < 0:
                actions.append(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))
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
        # Additionally open the device as an SDL game controller so its
        # trackpads emit touchpad events (the joystick handle above never sees
        # them). This is best-effort: a device with no touchpad, or a build
        # without game-controller support, simply leaves the trackpad horn
        # unavailable while every joystick control keeps working.
        if self._controller_module is None or instance_id in self._controllers:
            return
        try:
            controller = self._controller_module.Controller(device_index)
            controller.init()
        except (RuntimeError, AttributeError) as exc:
            log.info("Unable to open SDL game controller %s (no trackpad horn): %s", device_index, exc)
            return
        self._controllers[instance_id] = controller
        num_touchpads = getattr(controller, "get_num_touchpads", lambda: None)()
        log.info("SDL game controller opened for touchpads: touchpads=%s", num_touchpads)

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
        self._held_commands: dict[int, tuple[Target, str]] = {}
        self._sequences: dict[Target, int] = {}
        self._direction_latches: set[Target] = set()
        self._last_tick: float | None = None

    def handle(self, action: DeckAction) -> None:
        if action.name == "disconnect":
            self.clear()
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
        if action.name in (DPAD_LEFT, DPAD_RIGHT):
            # D-pad left/right must react to both press and release so ``tick()``
            # can repeat the boost/brake command while the key is held and stop
            # on release; handle it before the ``pressed``-only guard below.
            self._handle_boost_brake(action)
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
        if action.name in (DPAD_UP, DPAD_DOWN):
            # While the catalog panel is open, the D-pad scrolls the highlighted
            # catalog entry (clamped at the ends); otherwise it adjusts the
            # engine/train smoke output. ``SMOKE_ON``/``SMOKE_OFF`` resolve
            # automatically per control type: for a Legacy target they step the
            # smoke level up/down (Off/Low/Medium/High), and for a non-Legacy
            # (TMCC/Cab-1/R100) target they simply turn smoke on/off.
            if getattr(gui, "catalog_visible", False):
                gui.scroll_catalog(-1 if action.name == DPAD_UP else 1)
            else:
                gui.on_engine_command("SMOKE_ON" if action.name == DPAD_UP else "SMOKE_OFF")
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
        for _button, (target, command) in tuple(self._held_commands.items()):
            # Re-send a held panel command (e.g. the X/Y buttons) every
            # ``repeat_interval`` (100 ms) for as long as the button is held.
            gui = self._target_gui(target)
            if gui is None:
                continue
            gui.on_engine_command(command)
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
        # ``tick()`` re-sends it every ``repeat_interval`` (100 ms) until the
        # button is released.
        command = PANEL_COMMANDS[action.name]
        self._held_commands[action.button] = (action.target, command)
        gui.on_engine_command(command)

    def _handle_boost_brake(self, action: DeckAction) -> None:
        if action.phase != "pressed":
            # D-pad released: stop repeating the boost/brake command.
            self._boosts.pop(action.target, None)
            return
        gui = self._target_gui(action.target)
        if gui is None:
            return
        if getattr(gui, "catalog_visible", False):
            # While the catalog panel is open, D-pad right confirms the
            # highlighted entry (mirroring the A button) and D-pad left
            # cancels/closes the panel; neither repeats.
            self._boosts.pop(action.target, None)
            if action.name == DPAD_RIGHT:
                gui.select_catalog_entry()
            else:
                gui.hide_scope_catalog()
            return
        # Otherwise D-pad right boosts and D-pad left brakes the engine/train
        # speed. Fire once immediately for responsiveness, then ``tick()``
        # re-sends the command every ``repeat_interval`` while it is held
        # (``BOOST_SPEED``/``BRAKE_SPEED`` resolve for both Legacy and TMCC).
        command = "BOOST_SPEED" if action.name == DPAD_RIGHT else "BRAKE_SPEED"
        self._boosts[action.target] = command
        gui.on_engine_command(command)

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
