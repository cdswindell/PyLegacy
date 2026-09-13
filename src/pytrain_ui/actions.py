"""Toolkit-neutral description of cab actions exposed by presentation layers."""

from __future__ import annotations

from dataclasses import dataclass

from pytrain_ui.capabilities import operation_tag_applies
from pytrain_ui.equipment_actions import EQUIPMENT_ACTIONS, EquipmentAction


@dataclass(frozen=True, slots=True)
class CabAction:
    key: str
    label: str
    command: str
    icon: str = ""
    scope_tag: str = "e"
    group: str = "operations"
    hold: bool = False
    repeat: bool = False
    repeat_interval_ms: int = 0
    command_kind: str = "engine"
    legacy_only: bool = False
    hold_command: str = ""
    hold_command_kind: str = "engine"
    hold_kind: str = "command"
    hold_target: str = ""
    hold_threshold_ms: int = 1000
    hold_legacy_only: bool = False

    def __post_init__(self) -> None:
        if self.repeat and self.repeat_interval_ms <= 0:
            raise ValueError(f"Repeating action {self.key!r} requires a positive repeat interval")
        if not self.repeat and self.repeat_interval_ms != 0:
            raise ValueError(f"Non-repeating action {self.key!r} cannot define a repeat interval")
        if self.hold_threshold_ms <= 0:
            raise ValueError(f"Action {self.key!r} requires a positive hold threshold")
        if not self.hold:
            if self.hold_command or self.hold_target or self.hold_legacy_only:
                raise ValueError(f"Action {self.key!r} defines hold behavior but hold is disabled")
            return
        if self.hold_kind == "command":
            if not self.hold_command:
                raise ValueError(f"Hold action {self.key!r} requires a hold command")
        elif self.hold_kind in {"panel", "analog"}:
            if not self.hold_target:
                raise ValueError(f"Hold action {self.key!r} requires a hold target")
        else:
            raise ValueError(f"Action {self.key!r} has unsupported hold kind {self.hold_kind!r}")


def action_applies_to_type(action: CabAction, type_key: str) -> bool:
    return operation_tag_applies(action.scope_tag, type_key)


def _equipment_action(action: EquipmentAction) -> CabAction:
    return CabAction(
        action.key,
        action.label,
        action.command,
        action.icon,
        action.scope_tag,
        group=action.group,
        repeat=action.repeat_interval_ms > 0,
        repeat_interval_ms=action.repeat_interval_ms,
        command_kind=action.command_kind,
    )


CAB_ACTIONS: tuple[CabAction, ...] = (
    CabAction(
        "bell", "Bell", "RING_BELL", scope_tag="*", group="primary", hold=True,
        hold_kind="panel", hold_target="bell_horn",
    ),
    CabAction(
        "horn", "Horn", "BLOW_HORN_ONE", scope_tag="*", group="primary", hold=True,
        hold_kind="analog", hold_target="Horn", hold_legacy_only=True,
    ),
    CabAction(
        "brake", "Brake", "BRAKE_SPEED", scope_tag="*", group="primary", repeat=True,
        repeat_interval_ms=300,
    ),
    CabAction(
        "boost", "Boost", "BOOST_SPEED", scope_tag="*", group="primary", repeat=True,
        repeat_interval_ms=300,
    ),
    CabAction(
        "startup", "Start Up", "START_UP_IMMEDIATE", "on_button.jpg", "e", hold=True,
        hold_command="START_UP_DELAYED",
    ),
    CabAction(
        "shutdown", "Shut Down", "SHUTDOWN_IMMEDIATE", "off_button.jpg", "e", hold=True,
        hold_command="SHUTDOWN_DELAYED",
    ),
    CabAction("rear_coupler", "Rear Coupler", "REAR_COUPLER", "rear-coupler.jpg", "cp"),
    CabAction("front_coupler", "Front Coupler", "FRONT_COUPLER", "front-coupler.jpg", "cp"),
    CabAction("smoke_down", "Smoke −", "SMOKE_OFF", "smoke-down.jpg", "sm", command_kind="smoke"),
    CabAction("smoke_up", "Smoke +", "SMOKE_ON", "smoke-up.jpg", "sm", command_kind="smoke"),
    CabAction("volume_down", "Volume −", "VOLUME_DOWN", "vol-down.jpg", "vo"),
    CabAction("volume_up", "Volume +", "VOLUME_UP", "vol-up.jpg", "vo"),
    CabAction("rpm_down", "RPM −", "RPM_DOWN", "rpm-down.jpg", "d"),
    CabAction("rpm_up", "RPM +", "RPM_UP", "rpm-up.jpg", "d"),
    CabAction(
        "labor_down", "Labor −", "LABOR_EFFECT_DOWN", "effort-down.jpg", "e",
        command_kind="sequence", legacy_only=True,
    ),
    CabAction(
        "labor_up", "Labor +", "LABOR_EFFECT_UP", "effort-up.jpg", "e",
        command_kind="sequence", legacy_only=True,
    ),
    CabAction(
        "engineer_chatter", "Crew", "ENGINEER_CHATTER", "walkie_talkie.jpg", "e",
        hold=True, hold_kind="panel", hold_target="crew",
    ),
    CabAction(
        "tower_chatter", "Tower", "TOWER_CHATTER", "tower.jpg", "e", hold=True,
        hold_kind="panel", hold_target="tower",
    ),
    CabAction(
        "conductor", "Conductor", "ENGINEER_CHATTER", "conductor.jpg", "p", hold=True,
        hold_kind="panel", hold_target="conductor",
    ),
    CabAction(
        "station", "Station", "TOWER_CHATTER", "station.jpg", "p", hold=True,
        hold_kind="panel", hold_target="station",
    ),
    CabAction(
        "steward", "Steward", "STEWARD_CHATTER", "steward.jpg", "p", command_kind="generic",
        hold=True, hold_kind="panel", hold_target="steward",
    ),
    CabAction(
        "pantograph_front_down", "Front Panto Down", "PANTO_FRONT_DOWN_CAB2", "panto-down-f.jpg", "l",
        command_kind="effects", legacy_only=True,
    ),
    CabAction(
        "pantograph_front_up", "Front Panto Up", "PANTO_FRONT_UP_CAB2", "panto-up-f.jpg", "l",
        command_kind="effects", legacy_only=True,
    ),
    CabAction(
        "pantograph_rear_down", "Rear Panto Down", "PANTO_REAR_DOWN_CAB2", "panto-down-r.jpg", "l",
        command_kind="effects", legacy_only=True,
    ),
    CabAction(
        "pantograph_rear_up", "Rear Panto Up", "PANTO_REAR_UP_CAB2", "panto-up-r.jpg", "l",
        command_kind="effects", legacy_only=True,
    ),
    CabAction("electric_smoke_down", "Smoke −", "SMOKE_OFF", "smoke-down.jpg", "l", command_kind="smoke"),
    CabAction("electric_smoke_up", "Smoke +", "SMOKE_ON", "smoke-up.jpg", "l", command_kind="smoke"),
    CabAction(
        "pantograph_both_down", "Pantographs Down", "PANTO_BOTH_DOWN", "panto-down-a.jpg", "a",
        command_kind="effects", legacy_only=True,
    ),
    CabAction(
        "pantograph_both_up", "Pantographs Up", "PANTO_BOTH_UP", "panto-up-a.jpg", "a",
        command_kind="effects", legacy_only=True,
    ),
    *(_equipment_action(action) for action in EQUIPMENT_ACTIONS),
    CabAction(
        "sequence", "Aux1 · Sequence", "AUX1_OPTION_ONE", scope_tag="e", group="secondary",
        repeat=True, repeat_interval_ms=200,
    ),
    CabAction(
        "lights", "Aux2 · Lights", "AUX2_OPTION_ONE", scope_tag="e", group="secondary",
        hold=True, hold_kind="panel", hold_target="lights",
    ),
    CabAction(
        "more", "Aux3 · More", "AUX3_OPTION_ONE", scope_tag="e", group="secondary",
        hold=True, hold_kind="panel", hold_target="more",
    ),
    CabAction("momentum_low", "Mom Low", "MOMENTUM_LOW", scope_tag="e", group="tuning"),
    CabAction("momentum_medium", "Mom Med", "MOMENTUM_MEDIUM", scope_tag="e", group="tuning"),
    CabAction("momentum_high", "Mom High", "MOMENTUM_HIGH", scope_tag="e", group="tuning"),
)

CAB_ACTIONS_BY_KEY = {action.key: action for action in CAB_ACTIONS}


def cab_actions(group: str | None = None) -> tuple[CabAction, ...]:
    if group is None:
        return CAB_ACTIONS
    return tuple(action for action in CAB_ACTIONS if action.group == group)


def cab_action(key: str) -> CabAction | None:
    return CAB_ACTIONS_BY_KEY.get(key)
