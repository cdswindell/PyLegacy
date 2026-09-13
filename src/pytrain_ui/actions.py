"""Toolkit-neutral description of cab actions exposed by presentation layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CabAction:
    """Describe one operator action without depending on Qt, Tk, or a command enum."""

    key: str
    label: str
    command: str
    icon: str = ""
    group: str = "operations"
    hold: bool = False
    repeat: bool = False
    command_kind: str = "engine"
    legacy_only: bool = False
    engine_types: tuple[str, ...] = ()


# These deliberately mirror the high-value controls already exposed by EngineGui. The
# command name belongs to the adapter layer; presentation code only sees key/label/icon.
# Keeping the artwork filename here also gives us one place to review or replace icons as
# the Qt visual language evolves.
CAB_ACTIONS: tuple[CabAction, ...] = (
    CabAction("startup", "Start Up", "START_UP_IMMEDIATE", "on_button.jpg"),
    CabAction("shutdown", "Shut Down", "SHUTDOWN_IMMEDIATE", "off_button.jpg"),
    CabAction("rear_coupler", "Rear Coupler", "REAR_COUPLER", "rear-coupler.jpg"),
    CabAction("front_coupler", "Front Coupler", "FRONT_COUPLER", "front-coupler.jpg"),
    CabAction("smoke_down", "Smoke −", "SMOKE_OFF", "smoke-down.jpg"),
    CabAction("smoke_up", "Smoke +", "SMOKE_ON", "smoke-up.jpg"),
    CabAction("volume_down", "Volume −", "VOLUME_DOWN", "vol-down.jpg"),
    CabAction("volume_up", "Volume +", "VOLUME_UP", "vol-up.jpg"),
    CabAction("rpm_down", "RPM −", "RPM_DOWN", "rpm-down.jpg"),
    CabAction("rpm_up", "RPM +", "RPM_UP", "rpm-up.jpg"),
    CabAction("labor_down", "Labor −", "LABOR_EFFECT_DOWN", "effort-down.jpg", command_kind="sequence", legacy_only=True),
    CabAction("labor_up", "Labor +", "LABOR_EFFECT_UP", "effort-up.jpg", command_kind="sequence", legacy_only=True),
    CabAction("engineer_chatter", "Crew", "ENGINEER_CHATTER", "walkie_talkie.jpg"),
    CabAction("tower_chatter", "Tower", "TOWER_CHATTER", "tower.jpg"),
    CabAction(
        "pantograph_down",
        "Pantograph Down",
        "PANTO_BOTH_DOWN",
        "panto-down-a.jpg",
        command_kind="effects",
        legacy_only=True,
        engine_types=("ELECTRIC", "ALSTOM"),
    ),
    CabAction(
        "pantograph_up",
        "Pantograph Up",
        "PANTO_BOTH_UP",
        "panto-up-a.jpg",
        command_kind="effects",
        legacy_only=True,
        engine_types=("ELECTRIC", "ALSTOM"),
    ),
)

CAB_ACTIONS_BY_KEY = {action.key: action for action in CAB_ACTIONS}


def cab_actions() -> tuple[CabAction, ...]:
    """Return the ordered actions used by a normal engine/train cab."""

    return CAB_ACTIONS


def cab_action(key: str) -> CabAction | None:
    """Return an action by stable presentation key."""

    return CAB_ACTIONS_BY_KEY.get(key)
