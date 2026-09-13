"""Toolkit-neutral specs for cab panels opened by long-hold actions.

These are presentation descriptions only; they intentionally contain no Qt or
GuiZero dependencies.  The command names mirror the panels used by ControllerView.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PanelAction:
    section: str
    label: str
    command: str


_PANEL_TITLES = {
    "lights": "Lights",
    "more": "Additional Options",
    "crew": "Engineer & Crew Dialogs",
    "tower": "Tower Dialogs",
    "bell_horn": "Bell/Horn Options",
}

# BellHornPanel is small enough to mirror exactly here.
_BELL_HORN = (
    PanelAction("Bell", "Cycle Tone", "CYCLE_BELL_TONE"),
    PanelAction("Bell", "Ring / Pause", "RING_BELL"),
    PanelAction("Bell", "On", "BELL_ON"),
    PanelAction("Bell", "Off", "BELL_OFF"),
    PanelAction("Horn", "Cycle Tone", "CYCLE_HORN_TONE"),
    PanelAction("Horn", "Blow", "BLOW_HORN_ONE"),
    PanelAction("Horn", "Grade Crossing", "GRADE_CROSSING_SEQ"),
)

# The existing LightingPanel contains many locomotive-specific choices.  Start
# with the controls common enough to be useful on the cab; unsupported commands
# are filtered by the command adapter before they are exposed to QML.
_LIGHTS = (
    PanelAction("Cab", "Auto", "CAB_AUTO"),
    PanelAction("Cab", "On", "CAB_ON"),
    PanelAction("Cab", "Off", "CAB_OFF"),
    PanelAction("Ground", "Auto", "GROUND_AUTO"),
    PanelAction("Ground", "On", "GROUND_ON"),
    PanelAction("Ground", "Off", "GROUND_OFF"),
    PanelAction("Markers", "Auto", "LOCO_MARKER_AUTO"),
    PanelAction("Markers", "On", "LOCO_MARKER_ON"),
    PanelAction("Markers", "Off", "LOCO_MARKER_OFF"),
    PanelAction("Mars", "On", "MARS_ON"),
    PanelAction("Mars", "Off", "MARS_OFF"),
    PanelAction("Rule 17", "Auto", "RULE_17_AUTO"),
    PanelAction("Rule 17", "On", "RULE_17_ON"),
    PanelAction("Rule 17", "Off", "RULE_17_OFF"),
    PanelAction("Steam", "Doghouse On", "DOGHOUSE_ON"),
    PanelAction("Steam", "Doghouse Off", "DOGHOUSE_OFF"),
    PanelAction("Steam", "Tender On", "TENDER_MARKER_ON"),
    PanelAction("Steam", "Tender Off", "TENDER_MARKER_OFF"),
)

_CREW = (
    PanelAction("Acknowledge", "Cleared", "ENGINEER_ACK_CLEARED"),
    PanelAction("Acknowledge", "Clear Ahead", "ENGINEER_ACK_CLEAR_AHEAD"),
    PanelAction("Acknowledge", "Clear Inbound", "ENGINEER_ACK_CLEAR_INBOUND"),
    PanelAction("Acknowledge", "Standby", "ENGINEER_ACK_STAND_BY"),
)

_TOWER = (
    PanelAction("Arrive / Depart", "All Clear", "TOWER_ALL_CLEAR"),
    PanelAction("Arrive / Depart", "Arriving", "TOWER_ARRIVING"),
    PanelAction("Speed", "Restricted", "TOWER_SPEED_RESTRICTED"),
    PanelAction("Speed", "Slow", "TOWER_SPEED_SLOW"),
    PanelAction("Speed", "Medium", "TOWER_SPEED_MEDIUM"),
    PanelAction("Speed", "Limited", "TOWER_SPEED_LIMITED"),
    PanelAction("Speed", "Normal", "TOWER_SPEED_NORMAL"),
    PanelAction("Speed", "Highball", "TOWER_SPEED_HIGHBALL"),
)

_MORE = (
    PanelAction("Engine", "Start Up", "START_UP_IMMEDIATE"),
    PanelAction("Engine", "Shut Down", "SHUTDOWN_IMMEDIATE"),
    PanelAction("Sound", "Volume +", "VOLUME_UP"),
    PanelAction("Sound", "Volume −", "VOLUME_DOWN"),
    PanelAction("Motion", "Speed Roll", "SPEED_ROLL"),
)

_PANEL_ACTIONS = {
    "bell_horn": _BELL_HORN,
    "lights": _LIGHTS,
    "crew": _CREW,
    "tower": _TOWER,
    "more": _MORE,
}


def panel_title(key: str) -> str:
    return _PANEL_TITLES.get(key, key.replace("_", " ").title())


def panel_actions(key: str) -> tuple[PanelAction, ...]:
    return _PANEL_ACTIONS.get(key, ())
