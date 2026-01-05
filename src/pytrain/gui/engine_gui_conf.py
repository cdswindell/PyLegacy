#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from ..db.accessory_state import AccessoryState
from ..db.engine_state import TrainState
from ..pdi.asc2_req import Asc2Req
from ..pdi.bpc2_req import Bpc2Req
from ..pdi.constants import Asc2Action, Bpc2Action, PdiCommand
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, EngineType
from ..protocol.multibyte.multibyte_constants import TMCC2LightingControl
from ..protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
    TMCC1HaltCommandEnum,
    TMCC1SwitchCommandEnum,
)
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2RouteCommandEnum
from ..utils.path_utils import find_file

HALT_KEY = "Emergency"
SWITCH_THRU_KEY = "↑"
SWITCH_OUT_KEY = "↖↗"
FIRE_ROUTE_KEY = "⚡"
CYCLE_KEY = "↻"
PLAY_KEY = "▶"
PLAY_PAUSE_KEY = "▶/⏸"
PAUSE_KEY = "⏸"
CLEAR_KEY = "clr"
ENTER_KEY = "↵"
SET_KEY = "Set"
ENGINE_ON_KEY = "ENGINE ON"
ENGINE_OFF_KEY = "ENGINE OFF"
AC_ON_KEY = "AC ON"
AC_OFF_KEY = "AC OFF"
AUX1_KEY = "Aux1"
AUX2_KEY = "Aux2"
AUX3_KEY = "Aux3"
CAB_KEY = "Cab"
SMOKE_ON = "SMOKE ON"
SMOKE_OFF = "SMOKE OFF"
BELL_KEY = "\U0001f514"
FWD_KEY = "Fwd"
REV_KEY = "Rev"
MOM_TB = "MOM_TB"
MOMENTUM = "Mome-\nntum"
TRAIN_BRAKE = "Train\nBrake"
ENTRY_LAYOUT = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    [(CLEAR_KEY, "delete-key.jpg"), "0", ENTER_KEY],
]
ENGINE_OPS_LAYOUT = [
    [
        ("VOLUME_UP", "vol-up.jpg"),
        [
            ("ENGINEER_CHATTER", "walkie_talkie.jpg", "", "Crew...", "e"),
            ("NUMBER_3", "sound-on.jpg", "", "", "pf"),
        ],
        [
            ("RPM_UP", "rpm-up.jpg", "", "", "d"),
            ("LET_OFF_LONG", "let-off.jpg", "", "", "s"),
            ("ENGINEER_CHATTER", "conductor.jpg", "", "Conductor...", "p"),
            ("NUMBER_3", "load.jpg", "", "", "f"),
        ],
        [
            ("BLOW_HORN_ONE", "horn.jpg", "", "Horn...", "d"),
            ("BLOW_HORN_ONE", "whistle.jpg", "", "Whistle...", "s"),
            ("CONDUCTOR_NEXT_STOP", "next-stop.jpg", "", "", "p"),
            ("NUMBER_6", "unload.jpg", "", "", "f"),
        ],
    ],
    [
        ("VOLUME_DOWN", "vol-down.jpg"),
        [
            ("TOWER_CHATTER", "tower.jpg", "", "Tower...", "e"),
            ("NUMBER_5", "sound-off.jpg", "", "", "pf"),
        ],
        [
            ("RPM_DOWN", "rpm-down.jpg", "", "", "d"),
            ("WATER_INJECTOR", "water-inject.jpg", "", "", "s"),
            ("TOWER_CHATTER", "station.jpg", "", "Station...", "p"),
            ("TOWER_CHATTER", "tower.jpg", "", "", "f"),
        ],
        [
            ("RING_BELL", "bell.jpg", "", "Bell/Horn...", "e"),
            ("STEWARD_CHATTER", "steward.jpg", "", "Steward...", "p"),
            ("STOCK_WHEEL_ON", "flat-wheel-on.jpg", "", "", "f"),
        ],
    ],
    [
        ("FRONT_COUPLER", "front-coupler.jpg"),
        [
            (SMOKE_ON, "smoke-up.jpg", "", "", "e"),
            ("STOCK_OPTION_ONE_ON", "stock-a-on.jpg", "", "", "pf"),
        ],
        [
            ("BOOST_SPEED", "boost.jpg", "", "Boost", "e"),
            ("STOCK_OPTION_TWO_ON", "stock-b-on.jpg", "", "", "pf"),
        ],
        [
            ("FORWARD_DIRECTION", "", FWD_KEY, "", "e"),
            ("NUMBER_9", "car-lights-on.jpg", "", "", "p"),
            ("NUMBER_9", "lights-on.jpg", "", "", "f"),
        ],
    ],
    [
        ("REAR_COUPLER", "rear-coupler.jpg"),
        [
            (SMOKE_OFF, "smoke-down.jpg", "", "", "e"),
            ("STOCK_OPTION_ONE_OFF", "stock-a-off.jpg", "", "", "pf"),
        ],
        [
            ("BRAKE_SPEED", "brake.jpg", "", "Brake", "e"),
            ("STOCK_OPTION_TWO_OFF", "stock-b-off.jpg", "", "", "pf"),
        ],
        [
            ("REVERSE_DIRECTION", "", REV_KEY, "", "e"),
            ("NUMBER_8", "car-lights-off.jpg", "", "", "p"),
            ("NUMBER_8", "lights-off.jpg", "", "", "f"),
        ],
    ],
    [
        [
            ("AUX1_OPTION_ONE", "", AUX1_KEY, "Sequence", "e"),
            ("AUX1_OPTION_ONE", "", AUX1_KEY, "", "pf"),
        ],
        [
            ("AUX2_OPTION_ONE", "", AUX2_KEY, "Lights...", "e"),
            ("AUX2_OPTION_ONE", "", AUX2_KEY, "", "pf"),
        ],
        ("AUX3_OPTION_ONE", "", AUX3_KEY),
        [
            (MOM_TB, "", MOMENTUM, "", "e"),
            # ("", "", "Etc...", "", "f"),
        ],
    ],
]
RR_SPEED_LAYOUT = [
    [("SPEED_STOP_HOLD", "Normal\nStop"), ("EMERGENCY_STOP", "Emergency\nStop")],
    [("SPEED_RESTRICTED", "Restricted"), ("SPEED_SLOW", "Slow")],
    [("SPEED_MEDIUM", "Medium"), ("SPEED_LIMITED", "Limited")],
    [("SPEED_NORMAL", "Normal"), ("SPEED_HIGHBALL", "High Ball")],
]
DIESEL_LIGHTS = {
    "Cab Lights": [["Auto", "CAB_AUTO"], ["On", "CAB_ON"], ["Off", "CAB_OFF"], ["Toggle", "CAB_TOGGLE"]],
    "Ditch Lights": [
        ["On", "DITCH_ON"],
        ["Pulse On With Horn", "DITCH_ON_PULSE_ON_WITH_HORN"],
        ["Pulse Off With Horn", "DITCH_OFF_PULSE_OFF_WITH_HORN"],
        ["Off", "DITCH_OFF"],
    ],
    "Ground Lights": [["Auto", "GROUND_AUTO"], ["ON", "GROUND_ON"], ["OFF", "GROUND_OFF"]],
    "Marker Lights": [["Auto", "LOCO_MARKER_AUTO"], ["On", "LOCO_MARKER_ON"], ["Off", "LOCO_MARKER_OFF"]],
    "Car Lights": [["Auto", "CAR_AUTO"], ["On", "CAR_ON"], ["Off", "CAR_OFF"]],
    "Mars Lights": [["On", "MARS_ON"], ["Off", "MARS_OFF"]],
    "Rule 17": [["Auto", "RULE_17_AUTO"], ["On", "RULE_17_ON"], ["Off", "RULE_17_OFF"]],
    "Strobe Lights": [["On", "STROBE_LIGHT_ON"], ["Double", "STROBE_LIGHT_ON_DOUBLE"], ["Off", "STROBE_LIGHT_OFF"]],
}
STEAM_LIGHTS = {
    "Doghouse Lts": [["On", "DOGHOUSE_ON"], ["Off", "DOGHOUSE_OFF"]],
    "Ground Lights": [["Auto", "GROUND_AUTO"], ["ON", "GROUND_ON"], ["OFF", "GROUND_OFF"]],
    "Marker Lights": [["Auto", "LOCO_MARKER_AUTO"], ["On", "LOCO_MARKER_ON"], ["Off", "LOCO_MARKER_OFF"]],
    "Tender Lights": [["On", "TENDER_MARKER_ON"], ["Off", "TENDER_MARKER_OFF"]],
    "Mars Lights": [["On", "MARS_ON"], ["Off", "MARS_OFF"]],
    "Rule 17": [["Auto", "RULE_17_AUTO"], ["On", "RULE_17_ON"], ["Off", "RULE_17_OFF"]],
}
PASSENGER_CAR_LIGHTS = {
    "Car Lights": [["Auto", "CAR_AUTO"], ["On", "CAR_ON"], ["Off", "CAR_OFF"]],
}
CREW_DIALOGS = {
    "Acknowledge": [
        ["Cleared", "ENGINEER_ACK_CLEARED"],
        ["Clear Ahead", "ENGINEER_ACK_CLEAR_AHEAD"],
        ["Clear Inbound", "ENGINEER_ACK_CLEAR_INBOUND"],
        ["Standby", "ENGINEER_ACK_STAND_BY"],
        ["Stop/Hold", "ENGINEER_SPEED_STOP_HOLD"],
        ["Restricted", "ENGINEER_SPEED_RESTRICTED"],
        ["Slow", "ENGINEER_SPEED_SLOW"],
        ["Medium", "ENGINEER_SPEED_MEDIUM"],
        ["Limited", "ENGINEER_SPEED_LIMITED"],
        ["Normal", "ENGINEER_SPEED_NORMAL"],
        ["Highball", "ENGINEER_SPEED_HIGHBALL"],
    ],
    "Arrive/Depart": [
        ["All Clear", "ENGINEER_ALL_CLEAR"],
        ["Arriving", "ENGINEER_ARRIVING"],
        ["Arrived", "ENGINEER_ARRIVED"],
        ["Depart Denied", "ENGINEER_DEPARTURE_DENIED"],
        ["Depart Ok", "ENGINEER_DEPARTURE_GRANTED"],
        ["Departed", "ENGINEER_DEPARTED"],
    ],
    "Status": [
        ["Current Speed", "ENGINEER_SPEED"],
        ["Fuel Level", "ENGINEER_FUEL_LEVEL"],
        ["Fuel Refilled", "ENGINEER_FUEL_REFILLED"],
        ["Water Level", "ENGINEER_WATER_LEVEL"],
        ["Water Refilled", "ENGINEER_WATER_REFILLED"],
    ],
    "General": [
        ["Ack", "ENGINEER_ACK"],
        ["Ack ID", "ENGINEER_ACK_ID"],
        ["Contextual", "ENGINEER_CONTEXT_DEPENDENT"],
        ["ID", "ENGINEER_ID"],
        ["Shut Down", "ENGINEER_SHUTDOWN"],
        ["Welcome Back", "ENGINEER_ACK_WELCOME_BACK"],
    ],
    "Conductor": [
        ["All Aboard", "CONDUCTOR_ALL_ABOARD"],
        ["Next Stop", "CONDUCTOR_NEXT_STOP"],
        ["Premature Stop", "CONDUCTOR_PREMATURE_STOP"],
        ["Tickets Please", "CONDUCTOR_TICKETS_PLEASE"],
        ["Watch Your Step", "CONDUCTOR_WATCH_YOUR_STEP"],
    ],
    "Station": [
        ["Arriving", "STATION_ARRIVING"],
        ["Arrived", "STATION_ARRIVED"],
        ["Boarding", "STATION_BOARDING"],
        ["Departing", "STATION_DEPARTING"],
    ],
    "Steward": [
        ["Welcome Aboard", "STEWARD_WELCOME_ABOARD"],
        ["First Seating", "STEWARD_FIRST_SEATING"],
        ["Second Seating", "STEWARD_SECOND_SEATING"],
        ["Lounge Car Open", "STEWARD_LOUNGE_CAR_OPEN"],
    ],
    "Etc": [
        ["Passenger Car Startup", "PASSENGER_CAR_STARTUP"],
        ["Passenger Car Shutdown", "PASSENGER_CAR_SHUTDOWN"],
        ["Special Guest Enabled", "SPECIAL_GUEST_ENABLED"],
        ["Special Guest Disabled", "SPECIAL_GUEST_DISABLED"],
    ],
}
TOWER_DIALOGS = {
    "Arrive/Depart": [
        ["All Clear", "TOWER_ALL_CLEAR"],
        ["Arriving", "TOWER_ARRIVING"],
        ["Arrived", "TOWER_ARRIVED"],
        ["Depart Denied", "TOWER_DEPARTURE_DENIED"],
        ["Depart Ok", "TOWER_DEPARTURE_GRANTED"],
        ["Departed", "TOWER_DEPARTED"],
    ],
    "General": [
        ["Emergency", "EMERGENCY_CONTEXT_DEPENDENT"],
        ["Start Up", "TOWER_STARTUP"],
        ["Shut Down", "TOWER_SHUTDOWN"],
        ["Contextual", "TOWER_CONTEXT_DEPENDENT"],
    ],
    "Speed": [
        ["Stop/Hold", "TOWER_SPEED_STOP_HOLD"],
        ["Restricted", "TOWER_SPEED_RESTRICTED"],
        ["Slow", "TOWER_SPEED_SLOW"],
        ["Medium", "TOWER_SPEED_MEDIUM"],
        ["Limited", "TOWER_SPEED_LIMITED"],
        ["Normal", "TOWER_SPEED_NORMAL"],
        ["Highball", "TOWER_SPEED_HIGHBALL"],
    ],
}
CONDUCTOR_ACTIONS = {
    "Dialogs": [
        ["All Aboard", "CONDUCTOR_ALL_ABOARD"],
        ["Next Stop", "CONDUCTOR_NEXT_STOP"],
        ["Premature Stop", "CONDUCTOR_PREMATURE_STOP"],
        ["Tickets Please", "CONDUCTOR_TICKETS_PLEASE"],
        ["Watch Your Step", "CONDUCTOR_WATCH_YOUR_STEP"],
    ],
    "Actions": [
        ["Passenger Car Startup", "PASSENGER_CAR_STARTUP"],
        ["Passenger Car Shutdown", "PASSENGER_CAR_SHUTDOWN"],
        ["Special Guest Enabled", "SPECIAL_GUEST_ENABLED"],
        ["Special Guest Disabled", "SPECIAL_GUEST_DISABLED"],
    ],
}
STEWARD_DIALOGS = [
    [("STEWARD_WELCOME_ABOARD", "Welcome\nAboard"), ("STEWARD_LOUNGE_CAR_OPEN", "Lounge Car\nOpen")],
    [("STEWARD_FIRST_SEATING", "First\nSeating"), ("STEWARD_SECOND_SEATING", "Second\nSeating")],
]
STATION_DIALOGS = [
    [("STATION_ARRIVING", "Arriving"), ("STATION_ARRIVED", "Arrived")],
    [("STATION_BOARDING", "Boarding"), ("STATION_DEPARTING", "Departing")],
]
REPEAT_EXCEPTIONS = {
    TMCC1EngineCommandEnum.AUX2_OPTION_ONE: 1,
    TMCC2EngineCommandEnum.AUX2_OPTION_ONE: 1,
    TMCC2LightingControl.CAB_AUTO: 1,
}
FONT_SIZE_EXCEPTIONS = {
    CYCLE_KEY,
    PLAY_KEY,
    PLAY_PAUSE_KEY,
    PAUSE_KEY,
}
SENSOR_TRACK_OPTS = [
    ["No Action", 0],
    ["Sound Horn R➟L/None L➟R", 1],
    ["None R➟L/Sound Horn L➟R", 2],
    ["10 sec Bell R➟L/None L➟R", 3],
    ["None L➟R/10 sec Bell L➟R", 4],
    ["Begin Run R➟L/End Run L➟R", 5],
    ["End Run R➟L/Begin Run L➟R", 6],
    ["Go Slow R➟L/Go Normal L➟R", 7],
    ["Go Normal R➟L/Go Slow L➟R", 8],
    ["Recorded Sequence", 9],
]
COMMAND_FALLBACKS = {
    "WATER_INJECTOR": "NUMBER_5",
    "LET_OFF_LONG": "NUMBER_6",
}
LIONEL_ORANGE = "#FF6600"


def send_lcs_command(state: AccessoryState | TrainState, value) -> None:
    if state.is_bpc2:
        Bpc2Req(
            state.tmcc_id,
            PdiCommand.BPC2_SET,
            Bpc2Action.CONTROL1 if state.scope == CommandScope.TRAIN else Bpc2Action.CONTROL3,
            state=value,
        ).send()
    elif state.is_asc2:
        Asc2Req(
            state.tmcc_id,
            PdiCommand.ASC2_SET,
            Asc2Action.CONTROL1,
            values=value,
            time=0,
        ).send()


def send_lcs_on_command(state: AccessoryState) -> None:
    send_lcs_command(state, 1)


def send_lcs_off_command(state: AccessoryState) -> None:
    send_lcs_command(state, 0)


KEY_TO_COMMAND = {
    AC_OFF_KEY: send_lcs_off_command,
    AC_ON_KEY: send_lcs_on_command,
    FIRE_ROUTE_KEY: CommandReq(TMCC2RouteCommandEnum.FIRE),
    HALT_KEY: CommandReq(TMCC1HaltCommandEnum.HALT),
    SWITCH_OUT_KEY: CommandReq(TMCC1SwitchCommandEnum.OUT),
    SWITCH_THRU_KEY: CommandReq(TMCC1SwitchCommandEnum.THRU),
}
ENGINE_TYPE_TO_IMAGE = {
    EngineType.CRANE: find_file("generic_crane_car.jpg"),
    EngineType.DIESEL: find_file("generic_diesel.jpg"),
    EngineType.DIESEL_PULLMOR: find_file("generic_diesel.jpg"),
    EngineType.DIESEL_SWITCHER: find_file("generic_diesel_switcher.jpg"),
    EngineType.ELECTRIC: find_file("generic_electric.jpg"),
    EngineType.FREIGHT_SOUNDS: find_file("generic_freight.jpg"),
    EngineType.PASSENGER_CAR: find_file("generic_passenger_car.jpg"),
    EngineType.STEAM: find_file("generic_steam.jpg"),
    EngineType.STEAM_PULLMOR: find_file("generic_steam_santa.jpg"),
    EngineType.STEAM_SWITCHER: find_file("generic_steam_switcher.jpg"),
}
SCOPE_TO_SET_ENUM: dict[CommandScope, CommandDefEnum] = {
    CommandScope.ENGINE: TMCC1EngineCommandEnum.SET_ADDRESS,
    CommandScope.SWITCH: TMCC1SwitchCommandEnum.SET_ADDRESS,
    CommandScope.ACC: TMCC1AuxCommandEnum.SET_ADDRESS,
}
