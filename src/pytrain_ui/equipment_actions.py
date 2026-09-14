"""Type-specific cab operations extracted from ENGINE_OPS_LAYOUT.

This module contains semantic actions only: command, label, icon, applicability,
and interaction cadence. Grid coordinates and GuiZero widget details remain
presentation concerns.
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
    group: str = "operations"
    repeat_interval_ms: int = 0
    hold_command: str = ""


EQUIPMENT_ACTIONS: tuple[EquipmentAction, ...] = (
    # Steam-specific controls.
    EquipmentAction("let_off", "Let Off", "LET_OFF_LONG", "let-off.jpg", "s", "generic", repeat_interval_ms=200),
    EquipmentAction(
        "water_injector",
        "Water Injector",
        "WATER_INJECTOR",
        "water-inject.jpg",
        "s",
        "generic",
        repeat_interval_ms=200,
    ),
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
    # Acela-specific variants from cells that also contain ordinary engine variants.
    # Acela uses the same immediate/delayed startup and shutdown interaction as other
    # Legacy engines, but keeps its own Aux2/Aux3 behavior.
    EquipmentAction(
        "acela_startup",
        "Start Up",
        "START_UP_IMMEDIATE",
        "on_button.jpg",
        "a",
        hold_command="START_UP_DELAYED",
    ),
    EquipmentAction(
        "acela_shutdown",
        "Shut Down",
        "SHUTDOWN_IMMEDIATE",
        "off_button.jpg",
        "a",
        hold_command="SHUTDOWN_DELAYED",
    ),
    # Crane operations.
    EquipmentAction("crane_sound_on", "Sounds On", "NUMBER_9", "sound-on.jpg", "r"),
    EquipmentAction("crane_sound_off", "Sounds Off", "NUMBER_8", "sound-off.jpg", "r"),
    EquipmentAction("crane_radio", "Radio", "NUMBER_7", "walkie_talkie.jpg", "r"),
    EquipmentAction("crane_boom", "Boom/Cab", "NUMBER_1", "boom.jpg", "r"),
    EquipmentAction("crane_outriggers", "Outriggers", "NUMBER_6", "outriggers.jpg", "r"),
    EquipmentAction("crane_main_hook", "Main/Roll", "NUMBER_2", "main-hook.jpg", "r"),
    EquipmentAction("crane_front_lamp", "Front Lamp", "NUMBER_4", "front-lamp.jpg", "r"),
    EquipmentAction("crane_aux_hook", "Aux/Hook", "NUMBER_3", "aux-hook.jpg", "r"),
    EquipmentAction("crane_rear_lamp", "Rear Lamp", "NUMBER_5", "rear-lamp.jpg", "r"),
    EquipmentAction("crane_toggle", "Direction", "TOGGLE_DIRECTION", "toggle.jpg", "r"),
    # Transformer/PowerMaster operations. Brake/boost are already represented by
    # the primary cab controls, so only transformer-specific operation keys live here.
    EquipmentAction("transformer_horn", "Horn", "BLOW_HORN_ONE", "horn.jpg", "t"),
    EquipmentAction("transformer_bell", "Bell", "RING_BELL", "bell.jpg", "t"),
    EquipmentAction("transformer_front_coupler", "Front Coupler", "FRONT_COUPLER", "front-coupler.jpg", "t"),
    EquipmentAction("transformer_rear_coupler", "Rear Coupler", "REAR_COUPLER", "rear-coupler.jpg", "t"),
    EquipmentAction("transformer_direction", "Direction", "TOGGLE_DIRECTION", "", "t"),
    EquipmentAction("transformer_on", "Power On", "POWERMASTER_ON", "on_button.jpg", "t"),
    EquipmentAction("transformer_off", "Power Off", "POWERMASTER_OFF", "off_button.jpg", "t"),
    # Aux variants that ENGINE_OPS_LAYOUT exposes outside the standard engine
    # layout. These deliberately have no long-hold panel semantics.
    EquipmentAction("car_aux1", "Aux1", "AUX1_OPTION_ONE", "", "pf", group="secondary", repeat_interval_ms=200),
    EquipmentAction("car_aux2", "Aux2", "AUX2_OPTION_ONE", "", "pf", group="secondary"),
    EquipmentAction("car_aux3", "Aux3", "AUX3_OPTION_ONE", "", "pf", group="secondary"),
    EquipmentAction("acela_aux2", "Aux2", "AUX2_OPTION_ONE", "", "a", group="secondary"),
    EquipmentAction("acela_aux3", "Aux3 · Arcing", "AUX3_OPTION_ONE", "", "a", group="secondary"),
    EquipmentAction("crane_aux1", "Aux1", "AUX1_OPTION_ONE", "", "r", group="secondary", repeat_interval_ms=200),
    EquipmentAction("crane_aux2", "Aux2", "AUX2_OPTION_ONE", "", "r", group="secondary"),
    EquipmentAction("crane_aux3", "Aux3", "AUX3_OPTION_ONE", "", "r", group="secondary"),
)
