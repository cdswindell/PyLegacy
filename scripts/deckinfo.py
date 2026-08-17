#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import importlib
import os

# Mirror PyTrain's SDL setup so the axis/button numbers this probe prints match
# what the running app sees. The app runs headless with background joystick
# events enabled, so set those hints before importing pygame.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

# Enable SDL's built-in HIDAPI Steam Controller driver so SDL talks to the
# *native* Steam Deck controller (which exposes the two trackpads) instead of
# the virtual Xbox-style gamepad Steam Input synthesizes (which has none). This
# is the value of the SDL_HINT_JOYSTICK_HIDAPI_STEAM hint; SDL reads hints from
# identically named environment variables, so it must be set before pygame
# initializes the controller subsystem. Only takes effect when Steam Input is
# not itself capturing the pads.
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_STEAM", "1")

# noinspection package-requirements
import pygame

pygame.display.init()
pygame.joystick.init()

# IMPORTANT: PyTrain additionally opens each device as an SDL *game controller*
# (for the trackpad horn). Doing so activates SDL's controller mapping, which
# renumbers the joystick axes to the standard game-controller order the app
# actually reads (e.g. on a Steam Deck L2 = axis 2 and R2 = axis 5). Without
# this step the bare joystick API reports the raw HID axis order instead, which
# is off by one for the right stick and triggers -- exactly the discrepancy you
# saw. Opening it here keeps this probe consistent with the app.
try:
    _controller = importlib.import_module("pygame._sdl2.controller")
    _controller.init()
except (ImportError, RuntimeError, AttributeError) as exc:  # best effort
    _controller = None
    print("game-controller subsystem unavailable (raw axis order will be shown):", exc)

# pygame(-ce)'s Controller wrapper does not expose SDL_GameControllerGetNumTouchpads,
# so reuse PyTrain's SDL fallback to report the real touchpad count each device has.
try:
    # noinspection protected-member
    from pytrain.gui.controller.steam_deck_input import (
        _load_sdl_library,
        _loaded_sdl_paths,
        _sdl_touchpad_count,
    )
except ImportError:  # running the probe outside the installed package
    _sdl_touchpad_count = None
    _load_sdl_library = None
    _loaded_sdl_paths = None

# Report the pygame/SDL build. Controller touchpad support needs SDL >= 2.0.14;
# pygame-ce >= 2.5.x bundles SDL 2.30+, so a modern build is expected here. If
# this shows an old SDL, that alone explains a missing touchpad count.
print("pygame version:", pygame.version.ver, " SDL version:", ".".join(str(v) for v in pygame.get_sdl_version()))

# ``touchpads = None`` (as opposed to ``0``) means the SDL query itself failed,
# not that the device has no pads. The two usual causes are (a) we loaded a
# *different* SDL2 than the one pygame opened the controller with -- so SDL's
# controller registry is empty and ``SDL_GameControllerFromInstanceID`` returns
# NULL -- or (b) SDL2 could not be loaded at all. Surface exactly which SDL2 is
# in play so we can tell those apart.
if _loaded_sdl_paths is not None:
    print("SDL2 mapped into this process:", _loaded_sdl_paths() or "(none found in /proc/self/maps)")
if _load_sdl_library is not None:
    _sdl_lib = _load_sdl_library()
    if _sdl_lib is None:
        print("SDL2 for touchpad query: could NOT load a usable SDL2 (touchpad count will be None)")
    else:
        print("SDL2 for touchpad query loaded from:", getattr(_sdl_lib, "_name", "<unknown>"))


def _touchpad_diag(instance_id):
    # Mirror ``_sdl_touchpad_count`` but explain *why* it fails so ``None`` is
    # no longer ambiguous: report whether SDL found the opened controller for
    # this instance id, then the count it returns.
    if _load_sdl_library is None:
        return "pytrain not importable (cannot query SDL)"
    lib = _load_sdl_library()
    if lib is None:
        return "SDL2 not loadable"
    handle = lib.SDL_GameControllerFromInstanceID(int(instance_id))
    if not handle:
        return "SDL could not find the opened controller for this instance id (NULL handle) -- likely a different SDL2 instance or the pad is not exposed as a game controller"
    return "touchpads = " + str(int(lib.SDL_GameControllerGetNumTouchpads(handle)))


_controllers = []
for _index in range(pygame.joystick.get_count()):
    js = pygame.joystick.Joystick(_index)
    print("name:", js.get_name(), " buttons:", js.get_numbuttons(), " axes:", js.get_numaxes())
    if _controller is not None:
        try:
            _controllers.append(_controller.Controller(_index))
            instance_id = js.get_instance_id()
            touchpads = _sdl_touchpad_count(instance_id) if _sdl_touchpad_count else None
            print("    opened as game controller; instance id =", instance_id, "; touchpads =", touchpads)
            if touchpads is None:
                print("    touchpad diagnostic:", _touchpad_diag(instance_id))
        except (RuntimeError, AttributeError) as exc:
            print("could not open device as game controller:", exc)

# Allow the touchpad events so ``pygame.event.get()`` actually delivers them.
for _name in ("CONTROLLERTOUCHPADDOWN", "CONTROLLERTOUCHPADMOTION", "CONTROLLERTOUCHPADUP"):
    _event_type = getattr(pygame, _name, None)
    if _event_type is not None:
        pygame.event.set_allowed(_event_type)

print("Move sticks/press buttons, then drag a finger on each trackpad...")
while True:
    for e in pygame.event.get():
        if e.type == pygame.JOYBUTTONDOWN:
            print("BUTTON DOWN index =", e.button)
        elif e.type == pygame.JOYAXISMOTION:
            # triggers usually show up here, not as buttons
            if abs(e.value) > 0.5:
                print("AXIS", e.axis, "value =", round(e.value, 2))
        elif e.type == getattr(pygame, "CONTROLLERTOUCHPADDOWN", -1):
            print("TOUCHPAD DOWN pad =", e.touch_id, "finger =", e.finger, "x =", round(e.x, 3), "y =", round(e.y, 3))
        elif e.type == getattr(pygame, "CONTROLLERTOUCHPADMOTION", -1):
            print("TOUCHPAD MOVE pad =", e.touch_id, "finger =", e.finger, "x =", round(e.x, 3), "y =", round(e.y, 3))
        elif e.type == getattr(pygame, "CONTROLLERTOUCHPADUP", -1):
            print("TOUCHPAD UP   pad =", e.touch_id, "finger =", e.finger)
    pygame.time.wait(20)
