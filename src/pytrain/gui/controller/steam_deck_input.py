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
from dataclasses import dataclass
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
}
AXIS_ACTIONS = {"throttle", "direction"}
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


@dataclass(frozen=True)
class ButtonBinding:
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

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ControlProfile":
        dead_zone = cls._number(data, "dead_zone")
        hysteresis = cls._number(data, "hysteresis")
        throttle_rate = cls._number(data, "throttle_rate")
        repeat_interval = cls._number(data, "repeat_interval")
        direction_threshold = cls._number(data, "direction_threshold")
        if not 0.0 <= dead_zone < 1.0:
            raise ProfileError("dead_zone must be between 0 and 1")
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
            axes[index] = AxisBinding(action, target, bool(raw_binding.get("invert", False)))

        buttons: dict[int, ButtonBinding] = {}
        for raw_index, raw_binding in cls._mapping(data, "buttons").items():
            index = cls._index(raw_index, "button")
            action, target = cls._binding(raw_binding)
            if action in AXIS_ACTIONS:
                raise ProfileError(f"Action {action!r} cannot be assigned to a button")
            cls._validate_action_target(action, target)
            buttons[index] = ButtonBinding(action, target)

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
            controller_events = (
                self._pygame.JOYAXISMOTION,
                self._pygame.JOYBUTTONDOWN,
                self._pygame.JOYBUTTONUP,
                self._pygame.JOYHATMOTION,
                self._pygame.JOYDEVICEADDED,
                self._pygame.JOYDEVICEREMOVED,
            )
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

    def stop(self) -> None:
        for joystick in self._joysticks.values():
            try:
                joystick.quit()
            except RuntimeError:
                pass
        self._joysticks.clear()
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
        actions: list[DeckAction] = []
        for event in self._pygame.event.get():
            if event.type == self._pygame.JOYAXISMOTION:
                binding = self.profile.axes.get(event.axis)
                if binding is not None:
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
            self._hat_x = x
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
        except RuntimeError as exc:
            log.warning("Unable to open SDL controller %s: %s", device_index, exc)

    def _remove_device(self, instance_id: int) -> None:
        joystick = self._joysticks.pop(instance_id, None)
        if joystick is not None:
            log.info("SDL controller disconnected: name=%s", joystick.get_name())
            try:
                joystick.quit()
            except RuntimeError:
                pass
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
        if action.name == "scope_catalog":
            gui.show_scope_catalog()
            return
        if action.name in (DPAD_UP, DPAD_DOWN):
            # The D-pad scrolls the highlighted catalog entry (clamped at the
            # ends) only while the catalog panel is open; otherwise it is a
            # no-op, since the D-pad has no other assigned action.
            if getattr(gui, "catalog_visible", False):
                gui.scroll_catalog(-1 if action.name == DPAD_UP else 1)
            return
        if action.name == DPAD_RIGHT:
            # While the catalog panel is open, D-pad right confirms the
            # highlighted entry (mirroring the A button); otherwise it is a
            # no-op, since the D-pad has no other assigned action.
            if getattr(gui, "catalog_visible", False):
                gui.select_catalog_entry()
            return
        if action.name == DPAD_LEFT:
            # While the catalog panel is open, D-pad left cancels/closes the
            # catalog panel; otherwise it is a no-op, since the D-pad has no
            # other assigned action.
            if getattr(gui, "catalog_visible", False):
                gui.hide_scope_catalog()
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

    def clear(self) -> None:
        self._throttles.clear()
        self._commanded_speeds.clear()
        self._direction_latches.clear()
        self._last_tick = None

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
