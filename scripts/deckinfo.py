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
    from pytrain.gui.controller.steam_deck_input import _sdl_touchpad_count
except ImportError:  # running the probe outside the installed package
    _sdl_touchpad_count = None

_controllers = []
for _index in range(pygame.joystick.get_count()):
    js = pygame.joystick.Joystick(_index)
    js.init()
    print("name:", js.get_name(), " buttons:", js.get_numbuttons(), " axes:", js.get_numaxes())
    if _controller is not None:
        try:
            _controllers.append(_controller.Controller(_index))
            touchpads = _sdl_touchpad_count(js.get_instance_id()) if _sdl_touchpad_count else None
            print("    opened as game controller; touchpads =", touchpads)
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
