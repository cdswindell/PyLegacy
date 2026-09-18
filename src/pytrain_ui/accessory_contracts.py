"""Toolkit-neutral operating contracts for accessory views."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pytrain.gui.accessories.accessory_registry import PortBehavior


class AccessoryPowerState(str, Enum):
    """Deterministic power state presented by every accessory operating view."""

    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "UNKNOWN"


class AnimationPolicy(str, Enum):
    """How an operation's animated artwork is controlled."""

    STATE = "STATE"
    MOMENTARY = "MOMENTARY"
    PULSE = "PULSE"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class AccessoryOperationViewState:
    """Presentation state for one configured accessory operation."""

    key: str
    label: str
    tmcc_id: int
    behavior: PortBehavior
    state: AccessoryPowerState
    state_authoritative: bool
    image: str = ""
    off_image: str = ""
    on_image: str = ""
    animation_policy: AnimationPolicy = AnimationPolicy.NONE
    animation_running: bool = False
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True, slots=True)
class AccessoryOperatingViewState:
    """Common identity and state contract shared by all accessory operating views."""

    key: str
    title: str
    artwork: str
    artwork_aspect_ratio: float
    power_state: AccessoryPowerState
    power_state_authoritative: bool
    operations: tuple[AccessoryOperationViewState, ...] = ()


def animation_policy(behavior: PortBehavior) -> AnimationPolicy:
    """Return the animation lifecycle appropriate to an operation behavior."""

    if behavior == PortBehavior.LATCH:
        return AnimationPolicy.STATE
    if behavior == PortBehavior.MOMENTARY_HOLD:
        return AnimationPolicy.MOMENTARY
    if behavior == PortBehavior.MOMENTARY_PULSE:
        return AnimationPolicy.PULSE
    return AnimationPolicy.NONE
