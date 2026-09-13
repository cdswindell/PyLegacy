"""Toolkit-neutral description of cab actions exposed by presentation layers.

The fifth field in EngineGui's ENGINE_OPS_LAYOUT is the source of truth for which
controller types see an operation.  The Qt UI mirrors those scope tags instead of
trying to infer capabilities from command-enum membership.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CabAction:
    """Describe one operator action without depending on Qt, Tk, or a command enum."""

    key: str
    label: str
    command: str
    icon: str = ""
    scope_tag: str = "e"
    group: str = "operations"
    hold: bool = False
    repeat: bool = False
    command_kind: str = "engine"
    legacy_only: bool = False


# These tags intentionally match ControllerView.scope_key()/regen_engine_keys_map().
# A type key is one of: a=Acela, d=Diesel, f=Freight, l=Electric,
# p=Passenger, s=Steam, r=Crane, t=Transformer.
_TYPE_TAGS: dict[str, frozenset[str]] = {
    "a": frozenset({"vo", "e", "bs", "d", "a"}),
    "d": frozenset({"c", "vo", "cp", "e", "bs", "sm", "d"}),
    "f": frozenset({"c", "vo", "cp", "pf", "f"}),
    "l": frozenset({"c", "vo", "cp", "e", "l"}),
    "p": frozenset({"c", "vo", "cp", "pf", "p"}),
    "s": frozenset({"c", "vo", "cp", "e", "bs", "sm", "s"}),
    "r": frozenset({"c", "vo", "cp", "r"}),
    "t": frozenset({"t"}),
}


def action_applies_to_type(action: CabAction, type_key: str) -> bool:
    """Return whether EngineGui would expose this action for ``type_key``."""

    return action.scope_tag in _TYPE_TAGS.get(type_key, frozenset())


# First Qt parity slice. Scope tags come directly from ENGINE_OPS_LAYOUT / EXTRA_FUNCTIONS.
CAB_ACTIONS: tuple[CabAction, ...] = (
    CabAction("startup", "Start Up", "START_UP_IMMEDIATE", "on_button.jpg", "e"),
    CabAction("shutdown", "Shut Down", "SHUTDOWN_IMMEDIATE", "off_button.jpg", "e"),
    CabAction("rear_coupler", "Rear Coupler", "REAR_COUPLER", "rear-coupler.jpg", "cp"),
    CabAction("front_coupler", "Front Coupler", "FRONT_COUPLER", "front-coupler.jpg", "cp"),
    CabAction("smoke_down", "Smoke −", "SMOKE_OFF", "smoke-down.jpg", "sm"),
    CabAction("smoke_up", "Smoke +", "SMOKE_ON", "smoke-up.jpg", "sm"),
    CabAction("volume_down", "Volume −", "VOLUME_DOWN", "vol-down.jpg", "vo"),
    CabAction("volume_up", "Volume +", "VOLUME_UP", "vol-up.jpg", "vo"),
    CabAction("rpm_down", "RPM −", "RPM_DOWN", "rpm-down.jpg", "d"),
    CabAction("rpm_up", "RPM +", "RPM_UP", "rpm-up.jpg", "d"),
    CabAction(
        "labor_down",
        "Labor −",
        "LABOR_EFFECT_DOWN",
        "effort-down.jpg",
        "e",
        command_kind="sequence",
        legacy_only=True,
    ),
    CabAction(
        "labor_up",
        "Labor +",
        "LABOR_EFFECT_UP",
        "effort-up.jpg",
        "e",
        command_kind="sequence",
        legacy_only=True,
    ),
    CabAction("engineer_chatter", "Crew", "ENGINEER_CHATTER", "walkie_talkie.jpg", "e"),
    CabAction("tower_chatter", "Tower", "TOWER_CHATTER", "tower.jpg", "e"),
    # Electric controls in ENGINE_OPS_LAYOUT are front/rear pantographs, tagged "l".
    CabAction(
        "pantograph_front_down",
        "Front Panto Down",
        "PANTO_FRONT_DOWN_CAB2",
        "panto-down-f.jpg",
        "l",
        command_kind="effects",
        legacy_only=True,
    ),
    CabAction(
        "pantograph_front_up",
        "Front Panto Up",
        "PANTO_FRONT_UP_CAB2",
        "panto-up-f.jpg",
        "l",
        command_kind="effects",
        legacy_only=True,
    ),
    CabAction(
        "pantograph_rear_down",
        "Rear Panto Down",
        "PANTO_REAR_DOWN_CAB2",
        "panto-down-r.jpg",
        "l",
        command_kind="effects",
        legacy_only=True,
    ),
    CabAction(
        "pantograph_rear_up",
        "Rear Panto Up",
        "PANTO_REAR_UP_CAB2",
        "panto-up-r.jpg",
        "l",
        command_kind="effects",
        legacy_only=True,
    ),
    # Acela uses the paired pantograph commands, tagged "a" in ENGINE_OPS_LAYOUT.
    CabAction(
        "pantograph_both_down",
        "Pantographs Down",
        "PANTO_BOTH_DOWN",
        "panto-down-a.jpg",
        "a",
        command_kind="effects",
        legacy_only=True,
    ),
    CabAction(
        "pantograph_both_up",
        "Pantographs Up",
        "PANTO_BOTH_UP",
        "panto-up-a.jpg",
        "a",
        command_kind="effects",
        legacy_only=True,
    ),
)

CAB_ACTIONS_BY_KEY = {action.key: action for action in CAB_ACTIONS}


def cab_actions() -> tuple[CabAction, ...]:
    """Return the ordered actions used by a normal engine/train cab."""

    return CAB_ACTIONS


def cab_action(key: str) -> CabAction | None:
    """Return an action by stable presentation key."""

    return CAB_ACTIONS_BY_KEY.get(key)
