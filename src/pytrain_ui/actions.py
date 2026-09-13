"""Toolkit-neutral description of cab actions exposed by presentation layers.

The fifth field in EngineGui's ENGINE_OPS_LAYOUT is the source of truth for which
controller types see an operation. The Qt UI mirrors those scope tags instead of
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


# Actions are ordered for the modern cab rather than by physical position in the
# Tk keypad. Scope tags and command choices still come directly from
# ENGINE_OPS_LAYOUT / EXTRA_FUNCTIONS.
CAB_ACTIONS: tuple[CabAction, ...] = (
    CabAction("startup", "Start Up", "START_UP_IMMEDIATE", "on_button.jpg", "e"),
    CabAction("shutdown", "Shut Down", "SHUTDOWN_IMMEDIATE", "off_button.jpg", "e"),
    CabAction("rear_coupler", "Rear Coupler", "REAR_COUPLER", "rear-coupler.jpg", "cp"),
    CabAction("front_coupler", "Front Coupler", "FRONT_COUPLER", "front-coupler.jpg", "cp"),
    CabAction("smoke_down", "Smoke −", "SMOKE_OFF", "smoke-down.jpg", "sm", command_kind="smoke"),
    CabAction("smoke_up", "Smoke +", "SMOKE_ON", "smoke-up.jpg", "sm", command_kind="smoke"),
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
    # EXTRA_FUNCTIONS gives electric engines smoke controls even though they are
    # not part of the normal "sm" set used by diesel and steam.
    CabAction(
        "electric_smoke_down",
        "Smoke −",
        "SMOKE_OFF",
        "smoke-down.jpg",
        "l",
        command_kind="smoke",
    ),
    CabAction(
        "electric_smoke_up",
        "Smoke +",
        "SMOKE_ON",
        "smoke-up.jpg",
        "l",
        command_kind="smoke",
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
    # The bottom row of ENGINE_OPS_LAYOUT. In the Tk GUI these are also hold
    # launchers for richer overlays; a click still sends the underlying Aux
    # command, so they are useful immediately while the Qt overlays are built.
    CabAction("sequence", "Aux1 · Sequence", "AUX1_OPTION_ONE", scope_tag="e", group="secondary"),
    CabAction("lights", "Aux2 · Lights", "AUX2_OPTION_ONE", scope_tag="e", group="secondary"),
    CabAction("more", "Aux3 · More", "AUX3_OPTION_ONE", scope_tag="e", group="secondary"),
    # Momentum presets provide the same core function as the Tk momentum control.
    # The Qt view also exposes direct 0-7 adjustment through setMomentum().
    CabAction("momentum_low", "Mom Low", "MOMENTUM_LOW", scope_tag="e", group="tuning"),
    CabAction("momentum_medium", "Mom Med", "MOMENTUM_MEDIUM", scope_tag="e", group="tuning"),
    CabAction("momentum_high", "Mom High", "MOMENTUM_HIGH", scope_tag="e", group="tuning"),
)

CAB_ACTIONS_BY_KEY = {action.key: action for action in CAB_ACTIONS}


def cab_actions(group: str | None = None) -> tuple[CabAction, ...]:
    """Return ordered cab actions, optionally limited to one presentation group."""

    if group is None:
        return CAB_ACTIONS
    return tuple(action for action in CAB_ACTIONS if action.group == group)


def cab_action(key: str) -> CabAction | None:
    """Return an action by stable presentation key."""

    return CAB_ACTIONS_BY_KEY.get(key)
