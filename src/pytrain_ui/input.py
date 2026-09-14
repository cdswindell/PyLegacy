"""Toolkit-neutral primitives for physical cab input devices."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateThrottle:
    """Convert a spring-centered axis into repeated speed deltas.

    Axis values are normalized to -1..1. Positive values mean increase speed;
    negative values mean decrease speed. Returning the stick to the dead zone
    produces no command and preserves the current target speed.
    """

    dead_zone: float = 0.25
    min_step: int = 1
    max_step: int = 5

    def __post_init__(self) -> None:
        if not 0 <= self.dead_zone < 1:
            raise ValueError("dead_zone must be in the range 0 <= value < 1")
        if self.min_step <= 0 or self.max_step < self.min_step:
            raise ValueError("speed steps must be positive and max_step >= min_step")

    def delta(self, axis: float) -> int:
        axis = max(-1.0, min(1.0, float(axis)))
        magnitude = abs(axis)
        if magnitude <= self.dead_zone:
            return 0
        scaled = (magnitude - self.dead_zone) / (1.0 - self.dead_zone)
        step = round(self.min_step + scaled * (self.max_step - self.min_step))
        step = max(self.min_step, min(self.max_step, step))
        return step if axis > 0 else -step


@dataclass(slots=True)
class RepeatGate:
    """Monotonic-time gate used for repeat-while-held physical controls."""

    interval_seconds: float
    next_fire: float = 0.0

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("repeat interval must be positive")

    def reset(self) -> None:
        self.next_fire = 0.0

    def ready(self, now: float) -> bool:
        if now < self.next_fire:
            return False
        self.next_fire = now + self.interval_seconds
        return True


@dataclass(slots=True)
class HoldGesture:
    """Track a physical button that has distinct short- and long-press actions."""

    threshold_seconds: float = 0.75
    pressed_at: float | None = None
    long_fired: bool = False

    def __post_init__(self) -> None:
        if self.threshold_seconds <= 0:
            raise ValueError("hold threshold must be positive")

    def press(self, now: float) -> None:
        self.pressed_at = now
        self.long_fired = False

    def poll(self, now: float) -> bool:
        if self.pressed_at is None or self.long_fired:
            return False
        if now - self.pressed_at < self.threshold_seconds:
            return False
        self.long_fired = True
        return True

    def release(self, now: float) -> bool:
        """Return True when release should trigger the short action."""
        if self.pressed_at is None:
            return False
        short_press = not self.long_fired and now - self.pressed_at < self.threshold_seconds
        self.pressed_at = None
        self.long_fired = False
        return short_press
