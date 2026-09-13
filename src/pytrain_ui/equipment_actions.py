"""Type-specific cab operations extracted from ENGINE_OPS_LAYOUT.

This module contains semantic actions only: command, label, icon, and applicability
tag. Grid coordinates and GuiZero widget details intentionally remain presentation
concerns.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EquipmentAction:
    key: str
    label: str
    command: str
    icon: str
    scope_tag: str
    command_kind: str = "engine"


EQUIPMENT_ACTIONS: tuple[EquipmentAction, ...] = (
    # Steam-specific controls.
    EquipmentAction("let_off", "Let Off", "LET_OFF_LONG", "let-off.jpg", "s", "generic"),
    EquipmentAction("water_injector", "Water Injector", "WATER_INJECTOR", "water-inject.jpg", "s", "generic"),
    # Passenger/freight common operations (ENGINE_OPS_LAYOUT tag "pf").
    EquipmentAction("sound_on", "Sounds On", "NUMBER_3", "sound-on.jpg", "pf"),
    EquipmentAction("sound_off", "Sounds Off", "NUMBER_5", "sound-off.jpg", "pf"),
    EquipmentAction("option_one_on", "Option 1 On", "STOCK_OPTION_ONE_ON", "stock-a-on.jpg", "pf", "effects"),
    EquipmentAction("option_one_off", "Option 1 Off", "STOCK_OPTION_ONE_OFF", "stock-a-off.jpg", "pf", "effects"),
    EquipmentAction("option_two_on", "Option 2 On", "STOCK_OPTION_TWO_ON", "stock-b-on.jpg", "pf", "effects"),
    EquipmentAction("option_two_off", "Option 2 Off", "STOCK_OPTION_TWO_OFF", "stock-b-off.jpg", "pf", "effects"),
    # Passenger operations.
    EquipmentAction("next_stop", "Next Stop", "CONDUCTOR_NEXT_STOP", "next-stop.jpg", "p", "generic"),
    EquipmentAction("car_lights_on", "Lights On", "NUMBER_9", "car-lights-on.jpg", "p"),
    EquipmentAction("car_lights_off", "Lights Off", "NUMBER_8", "car-lights-off.jpg", "p"),
    # Freight Sounds operations. NUMBER_3 deliberately appears both as the
    # common Sounds On key and as Load, exactly as it does in ENGINE_OPS_LAYOUT.
    EquipmentAction("freight_load", "Load", "NUMBER_3", "load.jpg", "f"),
    EquipmentAction("freight_unload", "Unload", "NUMBER_6", "unload.jpg", "f"),
    EquipmentAction("freight_tower", "Tower", "TOWER_CHATTER", "tower.jpg", "f"),
    EquipmentAction("flat_wheel", "Wheel Sounds", "STOCK_WHEEL_ON", "flat-wheel-on.jpg", "f", "effects"),
    EquipmentAction("freight_lights_on", "Lights On", "NUMBER_9", "lights-on.jpg", "f"),
    EquipmentAction("freight_lights_off", "Lights Off", "NUMBER_8", "lights-off.jpg", "f"),
)
