#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import glob
import importlib
import os
import queue
import struct
import sys
import threading

# When this probe's stdout is a terminal it is line-buffered, so every ``print``
# appears immediately. But when the output is redirected to a file (e.g. a
# Non-Steam launcher doing ``... > deckinfo_out.txt``), Python switches stdout to
# *block* buffering. Because the probe runs an infinite event loop and is
# force-quit (its buffer is never flushed), the redirected file stays empty --
# exactly the "nothing shows up in the log" symptom. Force line buffering so each
# line is written as soon as it is printed, regardless of destination.
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except (AttributeError, ValueError):  # pre-3.7 or already-detached stream
    pass

# This probe imports PyTrain's private SDL helpers to report the real touchpad
# count. PyTrain uses a ``src`` layout, so when it is not pip-installed into the
# interpreter running this script (common on the Steam Deck, where the probe is
# launched directly as ``../bin/python scripts/deckinfo.py``), ``pytrain`` is not
# importable unless the repo's ``src`` directory is on ``sys.path``. Add it so
# the touchpad query works whether or not PyTrain is installed.
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if os.path.isdir(os.path.join(_SRC_DIR, "pytrain")) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

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

# Report the pygame/SDL build for reference.
print("pygame version:", pygame.version.ver, " SDL version:", ".".join(str(v) for v in pygame.get_sdl_version()))


_controllers = []
for _index in range(pygame.joystick.get_count()):
    js = pygame.joystick.Joystick(_index)
    print("name:", js.get_name(), " buttons:", js.get_numbuttons(), " axes:", js.get_numaxes())
    if _controller is not None:
        try:
            _controllers.append(_controller.Controller(_index))
            instance_id = js.get_instance_id()
            print("    opened as game controller; instance id =", instance_id)
        except (RuntimeError, AttributeError) as exc:
            print("could not open device as game controller:", exc)

# Allow the touchpad events so ``pygame.event.get()`` actually delivers them.
for _name in ("CONTROLLERTOUCHPADDOWN", "CONTROLLERTOUCHPADMOTION", "CONTROLLERTOUCHPADUP"):
    _event_type = getattr(pygame, _name, None)
    if _event_type is not None:
        pygame.event.set_allowed(_event_type)

# ---------------------------------------------------------------------------
# Raw hidraw reader for the Steam Deck's built-in controller.
#
# SDL never surfaces the Deck's built-in trackpads as controller touchpads, so
# the CONTROLLERTOUCHPAD* events above never fire on the Deck. As an alternative
# input path we read the controller's raw 64-byte HID input reports directly
# from its ``/dev/hidraw*`` node -- those reports carry absolute trackpad
# coordinates. A dedicated daemon thread performs the blocking reads and hands
# each report to this (single-threaded) event loop through a thread-safe
# ``queue.Queue``, keeping the reader fully decoupled from pygame. Once this is
# proven here it will be ported into ``SteamDeckInput`` as an alternate
# ``quilling_horn`` producer.
# ---------------------------------------------------------------------------
_DECK_VID = 0x28DE
_DECK_PID = 0x1205  # Steam Deck built-in controller

# Byte offsets into the Deck's 64-byte input "state" report. The report begins
# with 0x01 0x00 0x09 0x40 (unReportVersion=0x0001, ucType=0x09, ucLength=0x40).
# These offsets mirror the Linux ``hid-steam`` driver's decode. They are
# best-effort -- if a firmware revision moves them, the raw hex dump printed for
# the first report of each node lets you confirm/adjust them.
_DECK_STATE_TYPE = 0x09
_DECK_TOUCH_BYTE = 10  # bit3 = left pad touched, bit4 = right pad touched
_DECK_LPAD_TOUCH_BIT = 1 << 3
_DECK_RPAD_TOUCH_BIT = 1 << 4
_DECK_LPAD_OFFSET = 16  # s16 LE x immediately followed by s16 LE y
_DECK_RPAD_OFFSET = 20  # s16 LE x immediately followed by s16 LE y


def _find_deck_hidraw_paths():
    # Locate every ``/dev/hidraw*`` node that belongs to the Deck controller by
    # matching its VID/PID in the sysfs ``uevent`` (HID_ID=0003:000028DE:00001205).
    paths = []
    hid_id = f":{_DECK_VID:08X}:{_DECK_PID:08X}".lower()
    for sys_path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        uevent = os.path.join(sys_path, "device", "uevent")
        try:
            with open(uevent, "r", encoding="ascii", errors="replace") as handle:
                text = handle.read().lower()
        except OSError:
            continue
        if hid_id in text:
            paths.append("/dev/" + os.path.basename(sys_path))
    return paths


class _HidrawReader(threading.Thread):
    """Read 64-byte HID reports from one hidraw node and queue them.

    The blocking ``os.read`` runs on its own daemon thread, so it never stalls
    the main event loop; each report (or an error) is delivered via ``out_queue``.
    """

    def __init__(self, path, out_queue):
        super().__init__(name=f"hidraw:{path}", daemon=True)
        self._path = path
        self._queue = out_queue
        self._stop = threading.Event()
        self._fd = None

    def run(self):
        try:
            self._fd = os.open(self._path, os.O_RDONLY)
        except OSError as oe:
            self._queue.put(("error", self._path, f"cannot open ({oe}); a udev rule or root may be required"))
            return
        while not self._stop.is_set():
            try:
                report = os.read(self._fd, 64)
            except OSError as oe:
                self._queue.put(("error", self._path, f"read failed: {oe}"))
                break
            if report:
                self._queue.put(("report", self._path, report))

    def stop(self):
        self._stop.set()
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass


def _decode_deck_pads(report):
    # Return (lpad_touched, (lx, ly), rpad_touched, (rx, ry)) for a state packet,
    # or None for any other report type / a report too short to decode.
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


def _pad_fraction(value):
    # Map a signed 16-bit pad coordinate onto 0.0..1.0 for a quick horn preview.
    return round((value + 32768) / 65535.0, 3)


# Start a reader thread per matching hidraw node.
_hid_queue = queue.Queue()
_hid_readers = []
_deck_paths = _find_deck_hidraw_paths()
if _deck_paths:
    print("Steam Deck controller hidraw nodes:", ", ".join(_deck_paths))
    for _path in _deck_paths:
        _reader = _HidrawReader(_path, _hid_queue)
        _reader.start()
        _hid_readers.append(_reader)
else:
    print(f"no hidraw node for the Steam Deck controller (VID {_DECK_VID:#06x} PID {_DECK_PID:#06x}) was found;")
    print("    raw trackpad reading is unavailable (not a Steam Deck, or the controller is not present)")

# Per-node bookkeeping so the raw dump prints once and pad lines don't flood.
_raw_dumped = set()
_last_pad = {}


def _drain_hidraw():
    while True:
        try:
            kind, path, payload = _hid_queue.get_nowait()
        except queue.Empty:
            return
        if kind == "error":
            print(f"HIDRAW {path}: {payload}")
            continue
        if path not in _raw_dumped:
            _raw_dumped.add(path)
            print(f"HIDRAW {path} first report ({len(payload)} bytes): {payload.hex()}")
        decoded = _decode_deck_pads(payload)
        if decoded is None:
            continue
        lpad_touched, (lx, ly), rpad_touched, (rx, ry) = decoded
        # Coarsen the coordinates (>>8) so we print on real movement, not jitter.
        state = (lpad_touched, rpad_touched, lx >> 8, ly >> 8, rx >> 8, ry >> 8)
        if _last_pad.get(path) == state:
            continue
        _last_pad[path] = state
        if lpad_touched:
            print(f"HIDRAW {path} LEFT  pad x = {lx} y = {ly} (y frac ~ {_pad_fraction(ly)})")
        if rpad_touched:
            print(f"HIDRAW {path} RIGHT pad x = {rx} y = {ry} (y frac ~ {_pad_fraction(ry)})")
        if not lpad_touched and not rpad_touched:
            print(f"HIDRAW {path} pads released")


print("Move sticks/press buttons, then drag a finger on each trackpad...")
while True:
    _drain_hidraw()
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
