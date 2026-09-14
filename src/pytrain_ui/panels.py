"""Toolkit-neutral specs for cab panels opened by long-hold actions.

The labels and commands mirror the existing ControllerView/engine_gui_conf panels,
but live outside the GuiZero package so alternate presentation layers can reuse them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PanelAction:
    section: str
    label: str
    command: str
    type_keys: frozenset[str] = field(default_factory=frozenset)
    hold_command: str = ""
    hold_threshold_ms: int = 1000

    def __post_init__(self) -> None:
        if self.hold_threshold_ms <= 0:
            raise ValueError(f"Panel action {self.label!r} requires a positive hold threshold")


_PANEL_TITLES = {
    "lights": "Lights",
    "more": "Additional Options",
    "crew": "Engineer & Crew Dialogs",
    "tower": "Tower Dialogs",
    "bell_horn": "Bell/Horn Options",
    "conductor": "Conductor Actions",
    "steward": "Steward Dialogs",
    "station": "Station Dialogs",
}

_BELL_HORN = (
    PanelAction("Bell", "Cycle Tone", "CYCLE_BELL_TONE"),
    PanelAction("Bell", "Ring / Pause", "RING_BELL"),
    PanelAction("Bell", "On", "BELL_ON"),
    PanelAction("Bell", "Off", "BELL_OFF"),
    PanelAction("Horn", "Cycle Tone", "CYCLE_HORN_TONE"),
    PanelAction("Horn", "Blow", "BLOW_HORN_ONE"),
    PanelAction("Horn", "Grade Crossing", "GRADE_CROSSING_SEQ"),
)

_DIESEL_LIGHT_TYPES = frozenset({"a", "d", "l"})
_STEAM_LIGHT_TYPES = frozenset({"s"})

_LIGHTS = (
    # DIESEL_LIGHTS
    PanelAction("Cab Lights", "Auto", "CAB_AUTO", _DIESEL_LIGHT_TYPES),
    PanelAction("Cab Lights", "On", "CAB_ON", _DIESEL_LIGHT_TYPES),
    PanelAction("Cab Lights", "Off", "CAB_OFF", _DIESEL_LIGHT_TYPES),
    PanelAction("Cab Lights", "Toggle", "CAB_TOGGLE", _DIESEL_LIGHT_TYPES),
    PanelAction("Ditch Lights", "On", "DITCH_ON", _DIESEL_LIGHT_TYPES),
    PanelAction("Ditch Lights", "Pulse On With Horn", "DITCH_ON_PULSE_ON_WITH_HORN", _DIESEL_LIGHT_TYPES),
    PanelAction("Ditch Lights", "Pulse Off With Horn", "DITCH_OFF_PULSE_OFF_WITH_HORN", _DIESEL_LIGHT_TYPES),
    PanelAction("Ditch Lights", "Off", "DITCH_OFF", _DIESEL_LIGHT_TYPES),
    PanelAction("Ground Lights", "Auto", "GROUND_AUTO", _DIESEL_LIGHT_TYPES),
    PanelAction("Ground Lights", "On", "GROUND_ON", _DIESEL_LIGHT_TYPES),
    PanelAction("Ground Lights", "Off", "GROUND_OFF", _DIESEL_LIGHT_TYPES),
    PanelAction("Marker Lights", "Auto", "LOCO_MARKER_AUTO", _DIESEL_LIGHT_TYPES),
    PanelAction("Marker Lights", "On", "LOCO_MARKER_ON", _DIESEL_LIGHT_TYPES),
    PanelAction("Marker Lights", "Off", "LOCO_MARKER_OFF", _DIESEL_LIGHT_TYPES),
    PanelAction("Car Lights", "Auto", "CAR_AUTO", _DIESEL_LIGHT_TYPES),
    PanelAction("Car Lights", "On", "CAR_ON", _DIESEL_LIGHT_TYPES),
    PanelAction("Car Lights", "Off", "CAR_OFF", _DIESEL_LIGHT_TYPES),
    PanelAction("Mars Lights", "On", "MARS_ON", _DIESEL_LIGHT_TYPES),
    PanelAction("Mars Lights", "Off", "MARS_OFF", _DIESEL_LIGHT_TYPES),
    PanelAction("Rule 17", "Auto", "RULE_17_AUTO", _DIESEL_LIGHT_TYPES),
    PanelAction("Rule 17", "On", "RULE_17_ON", _DIESEL_LIGHT_TYPES),
    PanelAction("Rule 17", "Off", "RULE_17_OFF", _DIESEL_LIGHT_TYPES),
    PanelAction("Strobe Lights", "On", "STROBE_LIGHT_ON", _DIESEL_LIGHT_TYPES),
    PanelAction("Strobe Lights", "Double", "STROBE_LIGHT_ON_DOUBLE", _DIESEL_LIGHT_TYPES),
    PanelAction("Strobe Lights", "Off", "STROBE_LIGHT_OFF", _DIESEL_LIGHT_TYPES),
    # STEAM_LIGHTS
    PanelAction("Doghouse Lts", "On", "DOGHOUSE_ON", _STEAM_LIGHT_TYPES),
    PanelAction("Doghouse Lts", "Off", "DOGHOUSE_OFF", _STEAM_LIGHT_TYPES),
    PanelAction("Ground Lights", "Auto", "GROUND_AUTO", _STEAM_LIGHT_TYPES),
    PanelAction("Ground Lights", "On", "GROUND_ON", _STEAM_LIGHT_TYPES),
    PanelAction("Ground Lights", "Off", "GROUND_OFF", _STEAM_LIGHT_TYPES),
    PanelAction("Marker Lights", "Auto", "LOCO_MARKER_AUTO", _STEAM_LIGHT_TYPES),
    PanelAction("Marker Lights", "On", "LOCO_MARKER_ON", _STEAM_LIGHT_TYPES),
    PanelAction("Marker Lights", "Off", "LOCO_MARKER_OFF", _STEAM_LIGHT_TYPES),
    PanelAction("Tender Lights", "On", "TENDER_MARKER_ON", _STEAM_LIGHT_TYPES),
    PanelAction("Tender Lights", "Off", "TENDER_MARKER_OFF", _STEAM_LIGHT_TYPES),
    PanelAction("Mars Lights", "On", "MARS_ON", _STEAM_LIGHT_TYPES),
    PanelAction("Mars Lights", "Off", "MARS_OFF", _STEAM_LIGHT_TYPES),
    PanelAction("Rule 17", "Auto", "RULE_17_AUTO", _STEAM_LIGHT_TYPES),
    PanelAction("Rule 17", "On", "RULE_17_ON", _STEAM_LIGHT_TYPES),
    PanelAction("Rule 17", "Off", "RULE_17_OFF", _STEAM_LIGHT_TYPES),
)

_CREW = (
    PanelAction("Acknowledge", "Cleared", "ENGINEER_ACK_CLEARED"),
    PanelAction("Acknowledge", "Clear Ahead", "ENGINEER_ACK_CLEAR_AHEAD"),
    PanelAction("Acknowledge", "Clear Inbound", "ENGINEER_ACK_CLEAR_INBOUND"),
    PanelAction("Acknowledge", "Standby", "ENGINEER_ACK_STAND_BY"),
    PanelAction("Acknowledge", "Stop/Hold", "ENGINEER_SPEED_STOP_HOLD"),
    PanelAction("Acknowledge", "Restricted", "ENGINEER_SPEED_RESTRICTED"),
    PanelAction("Acknowledge", "Slow", "ENGINEER_SPEED_SLOW"),
    PanelAction("Acknowledge", "Medium", "ENGINEER_SPEED_MEDIUM"),
    PanelAction("Acknowledge", "Limited", "ENGINEER_SPEED_LIMITED"),
    PanelAction("Acknowledge", "Normal", "ENGINEER_SPEED_NORMAL"),
    PanelAction("Acknowledge", "Highball", "ENGINEER_SPEED_HIGHBALL"),
    PanelAction("Arrive/Depart", "All Clear", "ENGINEER_ALL_CLEAR"),
    PanelAction("Arrive/Depart", "Arriving", "ENGINEER_ARRIVING"),
    PanelAction("Arrive/Depart", "Arrived", "ENGINEER_ARRIVED"),
    PanelAction("Arrive/Depart", "Depart Denied", "ENGINEER_DEPARTURE_DENIED"),
    PanelAction("Arrive/Depart", "Depart Ok", "ENGINEER_DEPARTURE_GRANTED"),
    PanelAction("Arrive/Depart", "Departed", "ENGINEER_DEPARTED"),
    PanelAction("Status", "Current Speed", "ENGINEER_SPEED"),
    PanelAction("Status", "Fuel Level", "ENGINEER_FUEL_LEVEL"),
    PanelAction("Status", "Fuel Refilled", "ENGINEER_FUEL_REFILLED"),
    PanelAction("Status", "Water Level", "ENGINEER_WATER_LEVEL"),
    PanelAction("Status", "Water Refilled", "ENGINEER_WATER_REFILLED"),
    PanelAction("General", "Ack", "ENGINEER_ACK"),
    PanelAction("General", "Ack ID", "ENGINEER_ACK_ID"),
    PanelAction("General", "Contextual", "ENGINEER_CONTEXT_DEPENDENT"),
    PanelAction("General", "ID", "ENGINEER_ID"),
    PanelAction("General", "Shut Down", "ENGINEER_SHUTDOWN"),
    PanelAction("General", "Welcome Back", "ENGINEER_ACK_WELCOME_BACK"),
    PanelAction("Conductor", "All Aboard", "CONDUCTOR_ALL_ABOARD"),
    PanelAction("Conductor", "Next Stop", "CONDUCTOR_NEXT_STOP"),
    PanelAction("Conductor", "Premature Stop", "CONDUCTOR_PREMATURE_STOP"),
    PanelAction("Conductor", "Tickets Please", "CONDUCTOR_TICKETS_PLEASE"),
    PanelAction("Conductor", "Watch Your Step", "CONDUCTOR_WATCH_YOUR_STEP"),
    PanelAction("Station", "Arriving", "STATION_ARRIVING"),
    PanelAction("Station", "Arrived", "STATION_ARRIVED"),
    PanelAction("Station", "Boarding", "STATION_BOARDING"),
    PanelAction("Station", "Departing", "STATION_DEPARTING"),
    PanelAction("Steward", "Welcome Aboard", "STEWARD_WELCOME_ABOARD"),
    PanelAction("Steward", "First Seating", "STEWARD_FIRST_SEATING"),
    PanelAction("Steward", "Second Seating", "STEWARD_SECOND_SEATING"),
    PanelAction("Steward", "Lounge Car Open", "STEWARD_LOUNGE_CAR_OPEN"),
    PanelAction("Etc", "Passenger Car Startup", "PASSENGER_CAR_STARTUP"),
    PanelAction("Etc", "Passenger Car Shutdown", "PASSENGER_CAR_SHUTDOWN"),
    PanelAction("Etc", "Special Guest Enabled", "SPECIAL_GUEST_ENABLED"),
    PanelAction("Etc", "Special Guest Disabled", "SPECIAL_GUEST_DISABLED"),
)

_TOWER = (
    PanelAction("Arrive/Depart", "All Clear", "TOWER_ALL_CLEAR"),
    PanelAction("Arrive/Depart", "Arriving", "TOWER_ARRIVING"),
    PanelAction("Arrive/Depart", "Arrived", "TOWER_ARRIVED"),
    PanelAction("Arrive/Depart", "Depart Denied", "TOWER_DEPARTURE_DENIED"),
    PanelAction("Arrive/Depart", "Depart Ok", "TOWER_DEPARTURE_GRANTED"),
    PanelAction("Arrive/Depart", "Departed", "TOWER_DEPARTED"),
    PanelAction("General", "Emergency", "EMERGENCY_CONTEXT_DEPENDENT"),
    PanelAction("General", "Start Up", "TOWER_STARTUP"),
    PanelAction("General", "Shut Down", "TOWER_SHUTDOWN"),
    PanelAction("General", "Contextual", "TOWER_CONTEXT_DEPENDENT"),
    PanelAction("Speed", "Stop/Hold", "TOWER_SPEED_STOP_HOLD"),
    PanelAction("Speed", "Restricted", "TOWER_SPEED_RESTRICTED"),
    PanelAction("Speed", "Slow", "TOWER_SPEED_SLOW"),
    PanelAction("Speed", "Medium", "TOWER_SPEED_MEDIUM"),
    PanelAction("Speed", "Limited", "TOWER_SPEED_LIMITED"),
    PanelAction("Speed", "Normal", "TOWER_SPEED_NORMAL"),
    PanelAction("Speed", "Highball", "TOWER_SPEED_HIGHBALL"),
)

_MORE = (
    PanelAction("Engine", "Start Up", "START_UP_IMMEDIATE", hold_command="START_UP_DELAYED"),
    PanelAction("Engine", "Shut Down", "SHUTDOWN_IMMEDIATE", hold_command="SHUTDOWN_DELAYED"),
    PanelAction("Engine", "Fuel", "ENGINEER_FUEL_LEVEL", hold_command="ENGINEER_FUEL_REFILLED"),
    PanelAction("Engine", "Water", "ENGINEER_WATER_LEVEL", hold_command="ENGINEER_WATER_REFILLED"),
    PanelAction("Motion", "Speed Roll", "SPEED_ROLL"),
    PanelAction("Sound", "Master Volume +", "VOLUME_UP"),
    PanelAction("Sound", "Master Volume −", "VOLUME_DOWN"),
    PanelAction("Sound", "Blend / Aux +", "AUX_NUMBER_1"),
    PanelAction("Sound", "Blend / Aux −", "AUX_NUMBER_4"),
    PanelAction("Effort", "Labor +", "LABOR_EFFECT_UP"),
    PanelAction("Effort", "Labor −", "LABOR_EFFECT_DOWN"),
)

_CONDUCTOR = (
    PanelAction("Dialogs", "All Aboard", "CONDUCTOR_ALL_ABOARD"),
    PanelAction("Dialogs", "Next Stop", "CONDUCTOR_NEXT_STOP"),
    PanelAction("Dialogs", "Premature Stop", "CONDUCTOR_PREMATURE_STOP"),
    PanelAction("Dialogs", "Tickets Please", "CONDUCTOR_TICKETS_PLEASE"),
    PanelAction("Dialogs", "Watch Your Step", "CONDUCTOR_WATCH_YOUR_STEP"),
    PanelAction("Actions", "Passenger Car Startup", "PASSENGER_CAR_STARTUP"),
    PanelAction("Actions", "Passenger Car Shutdown", "PASSENGER_CAR_SHUTDOWN"),
    PanelAction("Actions", "Special Guest Enabled", "SPECIAL_GUEST_ENABLED"),
    PanelAction("Actions", "Special Guest Disabled", "SPECIAL_GUEST_DISABLED"),
)

_STEWARD = (
    PanelAction("Dialogs", "Welcome Aboard", "STEWARD_WELCOME_ABOARD"),
    PanelAction("Dialogs", "Lounge Car Open", "STEWARD_LOUNGE_CAR_OPEN"),
    PanelAction("Dialogs", "First Seating", "STEWARD_FIRST_SEATING"),
    PanelAction("Dialogs", "Second Seating", "STEWARD_SECOND_SEATING"),
)

_STATION = (
    PanelAction("Dialogs", "Arriving", "STATION_ARRIVING"),
    PanelAction("Dialogs", "Arrived", "STATION_ARRIVED"),
    PanelAction("Dialogs", "Boarding", "STATION_BOARDING"),
    PanelAction("Dialogs", "Departing", "STATION_DEPARTING"),
)

_PANEL_ACTIONS = {
    "bell_horn": _BELL_HORN,
    "lights": _LIGHTS,
    "crew": _CREW,
    "tower": _TOWER,
    "more": _MORE,
    "conductor": _CONDUCTOR,
    "steward": _STEWARD,
    "station": _STATION,
}


def panel_title(key: str) -> str:
    return _PANEL_TITLES.get(key, key.replace("_", " ").title())


def panel_actions(key: str) -> tuple[PanelAction, ...]:
    return _PANEL_ACTIONS.get(key, ())
