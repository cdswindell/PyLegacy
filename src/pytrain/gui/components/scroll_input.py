#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import time
from sys import platform


def precise_scroll_deltas(event) -> tuple[int, int]:
    """Decode Tk 9's two signed 16-bit pixel deltas, not a wheel-notch count."""
    try:
        packed = int(event.delta)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return 0, 0
    dx, dy = (packed >> 16) & 0xFFFF, packed & 0xFFFF
    return dx if dx < 0x8000 else dx - 0x10000, dy if dy < 0x8000 else dy - 0x10000


def wheel_scroll_pixels(event, step: int = 48) -> int:
    """Positive moves down; retain the small MouseWheel deltas sent by older Aqua Tk."""
    try:
        delta = int(event.delta)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return 0
    if platform == "darwin" and abs(delta) < 120:
        return -delta * 8
    return round(-delta * step / 120)


class ScrollAccumulator:
    """Retain sub-row motion without carrying it into another gesture or direction."""

    def __init__(self):
        self._remainder = 0.0
        self._last_time: float | None = None

    def reset(self) -> None:
        self._remainder = 0.0
        self._last_time = None

    def consume(self, pixels: float, unit: float) -> int:
        if not pixels or unit <= 0:
            return 0
        now = time.monotonic()
        if self._last_time is None or now - self._last_time > 0.3 or pixels * self._remainder < 0:
            self._remainder = 0.0
        self._last_time = now
        self._remainder += pixels
        steps = int(self._remainder / unit)
        self._remainder -= steps * unit
        return steps
