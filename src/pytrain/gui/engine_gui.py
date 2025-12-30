#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#  All Rights Reserved.
#
#  This work is licensed under the terms of the LPGL license.
#  SPDX-License-Identifier: LPGL
#

from __future__ import annotations

import atexit
import io
import logging
import math
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from queue import Empty, Queue
from threading import Condition, Event, RLock, Thread, get_ident
from tkinter import TclError
from typing import Any, Callable, Generic, TypeVar, cast

from guizero import App, Box, ButtonGroup, Combo, Picture, PushButton, Slider, Text, TitleBox
from guizero.base import Widget
from guizero.event import EventData

# noinspection PyPackageRequirements
from PIL import Image, ImageOps, ImageTk

from ..comm.command_listener import CommandDispatcher
from ..db.accessory_state import AccessoryState
from ..db.base_state import BaseState
from ..db.component_state import ComponentState, LcsProxyState, RouteState, SwitchState
from ..db.component_state_store import ComponentStateStore
from ..db.engine_state import EngineState, TrainState
from ..db.irda_state import IrdaState
from ..db.prod_info import ProdInfo
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..pdi.asc2_req import Asc2Req
from ..pdi.bpc2_req import Bpc2Req
from ..pdi.constants import Asc2Action, Bpc2Action, IrdaAction, PdiCommand
from ..pdi.irda_req import IrdaReq, IrdaSequence
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, EngineType
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl, TMCC2LightingControl
from ..protocol.sequence.ramped_speed_req import RampedSpeedDialogReq, RampedSpeedReq
from ..protocol.sequence.sequence_constants import SequenceCommandEnum
from ..protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
    TMCC1HaltCommandEnum,
    TMCC1RRSpeedsEnum,
    TMCC1SwitchCommandEnum,
)
from ..protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum,
    TMCC2EngineOpsEnum,
    TMCC2RouteCommandEnum,
    TMCC2RRSpeedsEnum,
)
from ..utils.image_utils import center_text_on_image
from ..utils.path_utils import find_file
from ..utils.unique_deque import UniqueDeque
from .hold_button import HoldButton
from .swipe_detector import SwipeDetector

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)

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
            ("", "", "Etc...", "", "f"),
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
    EngineType.STEAM: find_file("generic_steam_santa.jpg"),
    EngineType.STEAM_PULLMOR: find_file("generic_steam_santa.jpg"),
    EngineType.STEAM_SWITCHER: find_file("generic_steam_switcher.jpg"),
}

SCOPE_TO_SET_ENUM: dict[CommandScope, CommandDefEnum] = {
    CommandScope.ENGINE: TMCC1EngineCommandEnum.SET_ADDRESS,
    CommandScope.SWITCH: TMCC1SwitchCommandEnum.SET_ADDRESS,
    CommandScope.ACC: TMCC1AuxCommandEnum.SET_ADDRESS,
}


class EngineGui(Thread, Generic[S]):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        width: int = None,
        height: int = None,
        enabled_bg: str = "green",
        disabled_bg: str = "white",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        active_bg: str = "green",
        inactive_bg: str = "white",
        scale_by: float = 1.0,
        repeat: int = 2,
        num_recents: int = 5,
        initial: int = None,
        initial_scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        Thread.__init__(self, daemon=True, name="Engine GUI")
        self._cv = Condition(RLock())
        self._ev = Event()
        if width is None or height is None:
            try:
                from tkinter import Tk

                root = Tk()
                self.width = root.winfo_screenwidth()
                self.height = root.winfo_screenheight()
                root.destroy()
            except Exception as e:
                log.exception("Error determining window size", exc_info=e)
        else:
            self.width = width
            self.height = height
        self.title = None
        self.image_file = None
        self._base_state = None
        self._engine_tmcc_id = None
        self._engine_state = None
        self._image = None
        self._scale_by = scale_by
        self.repeat = repeat
        self.num_recents = num_recents
        self.s_30: int = int(round(30 * scale_by))
        self.s_24: int = int(round(24 * scale_by))
        self.s_22: int = int(round(22 * scale_by))
        self.s_20: int = int(round(20 * scale_by))
        self.s_18: int = int(round(18 * scale_by))
        self.s_16: int = int(round(16 * scale_by))
        self.s_14: int = int(round(14 * scale_by))
        self.s_12: int = int(round(12 * scale_by))
        self.s_10: int = int(round(10 * scale_by))
        self.s_8: int = int(round(8 * scale_by))
        self.button_size = int(round(self.width / 6))
        self.slider_height = self.button_size * 4
        self.titled_button_size = int(round((self.width / 6) * 0.80))
        self.scope_size = int(round(self.width / 5))
        self._text_pad_x = 20
        self._text_pad_y = 20
        self.s_72 = self.scale(72, 0.7)
        self.grid_pad_by = 2
        self.avail_image_height = self.avail_image_width = None
        self.options = [self.title]

        self._enabled_bg = enabled_bg
        self._disabled_bg = disabled_bg
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self._active_bg = active_bg
        self._inactive_bg = inactive_bg
        self.app = self.box = self.acc_box = self.y_offset = None
        self.turn_on_image = find_file("on_button.jpg")
        self.turn_off_image = find_file("off_button.jpg")
        self.asc2_image = find_file("LCS-ASC2-6-81639.jpg")
        self.amc2_image = find_file("LCS-AMC2-6-81641.jpg")
        self.bpc2_image = find_file("LCS-BPC2-6-81640.jpg")
        self.sensor_track_image = find_file("LCS-Sensor-Track-6-81294.jpg")
        self.power_off_path = find_file("bulb-power-off.png")
        self.power_on_path = find_file("bulb-power-on.png")
        self._app_counter = 0
        self._in_entry_mode = True
        self._btn_images = []
        self._dim_cache = {}
        self._scope_buttons = {}
        self._scope_tmcc_ids = {}
        self._scope_watchers = {}
        self._recents_queue = {}
        self._options_to_state = {}
        self._prod_info_cache = {}
        self._image_cache = {}
        self.entry_cells = set()
        self.ops_cells = set()
        self._elements = set()
        self._pending_prod_infos = set()
        self._executor = ThreadPoolExecutor(max_workers=3)
        self.size_cache = {}
        self._message_queue = Queue()
        self.scope = initial_scope if initial_scope else CommandScope.ENGINE
        self.initial = initial
        self._active_engine_state = None
        self.reset_on_keystroke = False
        self._current_popup = None

        # various boxes
        self.emergency_box = self.info_box = self.keypad_box = self.scope_box = self.name_box = self.image_box = None
        self.controller_box = self.controller_keypad_box = self.controller_throttle_box = None
        self.emergency_box_width = self.emergency_box_height = None

        # various buttons
        self.halt_btn = self.reset_btn = self.off_btn = self.on_btn = self.set_btn = None
        self.fire_route_btn = self.switch_thru_btn = self.switch_out_btn = self.keypad_keys = None

        # various fields
        self.tmcc_id_box = self.tmcc_id_text = self._nbi = self.header = None
        self.name_text = self.titlebar_height = self.popup_position = None
        self.on_key_cell = self.off_key_cell = None
        self.image = None
        self.clear_key_cell = self.enter_key_cell = self.set_key_cell = self.fire_route_cell = None
        self.switch_thru_cell = self.switch_out_cell = None

        # Sensor Track
        self.sensor_track_box = self.sensor_track_buttons = None

        # BPC2/ASC2
        self.ac_on_cell = self.ac_off_cell = self.ac_status_cell = None
        self.ac_off_btn = self.ac_on_btn = self.ac_status_btn = None
        self.ac_aux1_cell = self.ac_aux1_btn = None

        # controller
        self.controller_box = self.controller_keypad_box = None
        self.brake_box = self.brake_level = self.brake = self.focus_widget = None
        self.throttle_box = self.throttle = self.speed = self._rr_speed_btn = self._rr_speed_box = None
        self._bell_box = self._bell_btn = None
        self.momentum_box = self.momentum_level = self.momentum = None
        self.horn_box = self.horn_title_box = self.horn_level = self.horn = None
        self.rr_speed_overlay = self.lights_overlay = self.horn_overlay = self.info_overlay = None
        self.tower_dialog_overlay = self.crew_dialog_overlay = None
        self.diesel_lights_box = self.steam_lights_box = None
        self.rr_speed_btns = set()
        self._engine_btns = set()
        self._passenger_btns = set()
        self._passenger_freight_btns = set()
        self._diesel_btns = set()
        self._steam_btns = set()
        self._freight_btns = set()
        self._all_engine_btns = set()
        self._engine_type_key_map: dict[str, set[Widget]] = {}
        self._last_engine_type = None
        self._quill_after_id = None
        self.tower_dialog_box = self.crew_dialog_box = None
        self.conductor_actions_box = self.station_dialog_box = self.steward_dialog_box = None
        self.can_hack_combo = False  # don't ask
        self._isd = None  # swipe detector for engine image field
        self._info_details = {}  # manage state details info popup fields
        self.conductor_overlay = self.steward_overlay = self.station_overlay = self.bell_overlay = None
        self._on_close_show = None

        # callbacks
        self._scoped_callbacks = {
            CommandScope.ROUTE: self.on_new_route,
            CommandScope.SWITCH: self.on_new_switch,
            CommandScope.ACC: self.on_new_accessory,
            CommandScope.ENGINE: self.on_new_engine,
            CommandScope.TRAIN: self.on_new_engine,
        }

        self.engine_ops_cells = {}

        # Thread-aware shutdown signaling
        self._tk_thread_id: int | None = None
        self._is_closed = False
        self._shutdown_flag = Event()

        # listen for state changes
        self._dispatcher = CommandDispatcher.get()
        self._state_store = ComponentStateStore.get()
        self._synchronized = False
        self._sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
        if self._sync_state and self._sync_state.is_synchronized is True:
            self._sync_watcher = None
            self.on_sync()
        else:
            self._sync_watcher = StateWatcher(self._sync_state, self.on_sync)

        # Important: don't call tkinter from atexit; only signal
        atexit.register(lambda: self._shutdown_flag.set())

    def close(self) -> None:
        # Only signal shutdown here; actual tkinter destroy happens on the GUI thread
        if not self._is_closed:
            self._is_closed = True
            self._shutdown_flag.set()

    def reset(self) -> None:
        self.close()

    @property
    def destroy_complete(self) -> Event:
        return self._ev

    @property
    def version(self) -> str:
        return self._dispatcher.version

    # noinspection PyTypeChecker
    @property
    def active_engine_state(self) -> EngineState:
        if self.scope in (CommandScope.ENGINE, CommandScope.TRAIN):
            if (
                self._active_engine_state
                and self._active_engine_state.scope == self.scope
                and self._active_engine_state.tmcc_id == self._scope_tmcc_ids[self.scope]
            ):
                return self._active_engine_state
            else:
                self._active_engine_state = self.active_state
                return self._active_engine_state
        else:
            return None

    # noinspection PyTypeChecker
    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            self._base_state = self._state_store.get_state(CommandScope.BASE, 0, False)
            if self._base_state:
                self.title = cast(BaseState, self._base_state).base_name
            else:
                self.title = "My Layout"

            # start GUI
            self.start()

    # noinspection PyTypeChecker
    def set_button_inactive(self, widget: Widget):
        widget.bg = self._disabled_bg
        widget.text_color = self._disabled_text

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget):
        widget.bg = self._enabled_bg
        widget.text_color = self._enabled_text

    def queue_message(self, message: Callable, *args: Any) -> None:
        self._message_queue.put((message, args))

    # noinspection PyTypeChecker
    def run(self) -> None:
        self._shutdown_flag.clear()
        self._ev.clear()
        self._tk_thread_id = get_ident()
        GpioHandler.cache_handler(self)
        self.app = app = App(title=self.title, width=self.width, height=self.height)
        app.full_screen = True
        app.when_closed = self.close
        app.bg = "white"

        # poll for shutdown requests from other threads; this runs on the GuiZero/Tk thread
        def _poll_shutdown():
            self._app_counter += 1
            if self._shutdown_flag.is_set():
                try:
                    app.destroy()
                except TclError:
                    pass  # ignore, we're shutting down
                return None
            else:
                # Process pending messages in the queue
                try:
                    message = self._message_queue.get_nowait()
                    if isinstance(message, tuple):
                        if message[1] and len(message[1]) > 0:
                            message[0](*message[1])
                        else:
                            message[0]()
                        # app.tk.update_idletasks()
                except Empty:
                    pass
            return None

        # customize label
        self.header = cb = Combo(
            app,
            options=self.get_options(),
            selected=self.title,
            align="top",
            command=self.on_recents,
        )
        cb.text_size = self.s_24
        cb.text_bold = True

        # determine if we can set the "selected" value directly;
        # will be used for other combo boxes
        self.can_hack_combo = hasattr(cb, "_selected")

        # Make the emergency buttons, including Halt and Reset
        self.make_emergency_buttons(app)

        # Make info box for TMCC ID and Road Name
        self.make_info_box(app)

        # make selection box and keypad
        self.make_keypad(app)

        # make engine/train make_controller
        self.make_controller(app)

        # make scope buttons
        self.make_scope(app)

        # Finally, resize image box
        available_height, available_width = self.calc_image_box_size()
        self.image_box.tk.config(height=available_height, width=available_width)

        # ONE geometry pass at the end
        app.tk.after_idle(app.tk.update_idletasks)

        # calculate offset for popups
        x = self.info_box.tk.winfo_rootx()
        y = self.info_box.tk.winfo_rooty() + self.info_box.tk.winfo_reqheight()
        self.popup_position = (x, y)

        # start the event watcher
        app.repeat(20, _poll_shutdown)

        if self.initial:
            app.after(50, self.update_component_info, [self.initial])

        # Display GUI and start event loop; call blocks
        try:
            app.display()
        except TclError:
            # If Tcl is already tearing down, ignore
            pass
        finally:
            # Explicitly drop references to tkinter/guizero objects on the Tk thread
            self.box = None
            self.acc_box = None
            self._image = None
            self.app = None
            self._ev.set()

    # noinspection PyTypeChecker
    def make_controller(self, app):
        if self.controller_box is not None:
            return
        self.controller_box = controller_box = Box(
            app,
            border=2,
            align="top",
            visible=False,
        )
        self.ops_cells.add(controller_box)

        # different engine types have different features
        # define the common keys first
        self.controller_keypad_box = keypad_keys = Box(
            controller_box,
            layout="grid",
            border=0,
            align="left",
        )
        row = 0
        for r, kr in enumerate(ENGINE_OPS_LAYOUT):
            for c, button_info in enumerate(kr):
                if button_info is None:
                    continue
                if isinstance(button_info, tuple):
                    ops = [button_info]
                elif isinstance(button_info, list):
                    ops = button_info
                else:
                    raise AttributeError(f"Invalid engine op: {button_info}")
                for op in ops:
                    image = label = title_text = None
                    if len(op) > 1 and op[1]:
                        image = find_file(op[1])
                    if len(op) > 2 and op[2]:
                        label = str(op[2])
                    if len(op) > 3 and op[3]:
                        title_text = str(op[3])
                    cmd = op[0]

                    # make the key button and it's surrounding cell
                    cell, nb = self.make_keypad_button(
                        keypad_keys,
                        label,
                        row,
                        c,
                        visible=True,
                        bolded=True,
                        command=self.on_engine_command,
                        args=[cmd],
                        image=image,
                        titlebox_text=title_text,
                    )

                    # if the key is marked as engine type-specific, save as appropriate
                    if len(op) > 4 and op[4]:
                        if op[4] == "e":
                            self._engine_btns.add(cell)
                        elif op[4] == "d":
                            self._diesel_btns.add(cell)
                        elif op[4] == "s":
                            self._steam_btns.add(cell)
                        elif op[4] == "p":
                            self._passenger_btns.add(cell)
                        elif op[4] == "f":
                            self._freight_btns.add(cell)
                        elif op[4] == "pf":
                            self._passenger_freight_btns.add(cell)

                        key = (cmd, op[4])
                    else:
                        key = cmd

                    if key in self.engine_ops_cells:
                        print(f"Duplicate engine op: {key}: {op}")
                    self.engine_ops_cells[key] = (key, nb)
            row += 1

        # Postprocess some buttons
        _, btn = self.engine_ops_cells[(MOM_TB, "e")]
        btn.text_size = self.s_12
        btn.update_command(self.toggle_momentum_train_brake, [btn])

        _, btn = self.engine_ops_cells[("AUX1_OPTION_ONE", "e")]
        btn.on_repeat = btn.on_press

        _, btn = self.engine_ops_cells[("AUX2_OPTION_ONE", "e")]
        btn.on_hold = self.on_lights

        _, btn = self.engine_ops_cells[("TOWER_CHATTER", "e")]
        btn.on_hold = self.on_tower_dialog

        _, btn = self.engine_ops_cells[("ENGINEER_CHATTER", "e")]
        btn.on_hold = self.on_crew_dialog

        _, btn = self.engine_ops_cells[("ENGINEER_CHATTER", "p")]
        btn.on_hold = self.on_conductor_actions

        _, btn = self.engine_ops_cells[("TOWER_CHATTER", "p")]
        btn.on_hold = self.on_station_dialogs

        _, btn = self.engine_ops_cells[("STEWARD_CHATTER", "p")]
        btn.on_hold = self.on_steward_dialogs

        for loco_type in ["d", "s"]:
            _, btn = self.engine_ops_cells[("BLOW_HORN_ONE", loco_type)]
            btn.on_hold = self.show_horn_control

        for loco_type in ["e"]:
            _, btn = self.engine_ops_cells[("RING_BELL", loco_type)]
            btn.on_hold = self.on_bell_horn_options

        # set some repeating commands
        for command in ["BOOST_SPEED", "BRAKE_SPEED"]:
            _, btn = self.engine_ops_cells[(command, "e")]
            btn.on_repeat = btn.on_press
            btn.repeat_interval = 0.3

        for command in ["WATER_INJECTOR", "LET_OFF_LONG"]:
            _, btn = self.engine_ops_cells[(command, "s")]
            btn.on_repeat = btn.on_press
            btn.repeat_interval = 0.2

        # assemble key maps
        self._all_engine_btns = (
            self._engine_btns
            | self._diesel_btns
            | self._steam_btns
            | self._passenger_btns
            | self._freight_btns
            | self._passenger_freight_btns
        )
        self._engine_type_key_map = {
            "d": self._engine_btns | self._diesel_btns,
            "s": self._engine_btns | self._steam_btns,
            "p": self._passenger_freight_btns | self._passenger_btns,
            "f": self._passenger_freight_btns | self._freight_btns,
        }

        # used to make sure brake and throttle get focus when needed
        self.controller_box.visible = True
        self.focus_widget = focus_sink = tk.Frame(app.tk, takefocus=1)
        focus_sink.place(x=-9999, y=-9999, width=1, height=1)

        sliders = Box(
            controller_box,
            border=1,
            align="right",
            layout="grid",
        )
        sliders.tk.pack(fill="y", expand=True)

        # throttle
        self.throttle_box = throttle_box = Box(
            sliders,
            border=1,
            grid=[1, 0],
        )

        cell = TitleBox(throttle_box, "Speed", align="top", border=1)
        cell.text_size = self.s_10
        self.speed = speed = Text(
            cell,
            text="000",
            color="black",
            align="top",
            bold=True,
            size=self.s_18,
            width=4,
            font="DigitalDream",
        )
        speed.bg = "black"
        speed.text_color = "white"

        self.throttle = throttle = Slider(
            throttle_box,
            align="top",
            horizontal=False,
            step=1,
            width=int(self.button_size / 2),
            height=self.slider_height,
            command=self.on_throttle,
        )
        throttle.after_id = None  # used to debounce slider updates
        throttle.text_color = "black"
        throttle.tk.config(
            from_=195,
            to=0,
            takefocus=0,
            troughcolor="#003366",  # deep Lionel blue for the track,
            activebackground=LIONEL_ORANGE,  # bright Lionel orange for the handle
            bg="lightgrey",  # darker navy background
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,  # subtle orange outline
            width=int(self.button_size / 2),
            sliderlength=int(self.slider_height / 6),
        )
        throttle.tk.bind("<Button-1>", lambda e: throttle.tk.focus_set())
        throttle.tk.bind("<ButtonRelease-1>", self.clear_focus, add="+")
        throttle.tk.bind("<ButtonRelease>", self.clear_focus, add="+")

        # brake
        self.brake_box, _, self.brake_level, self.brake = self.make_slider(
            sliders, "Brake", self.on_train_brake, frm=0, to=7
        )

        # Allow Tk to compute geometry
        self.app.tk.update_idletasks()

        # Momentum
        self.momentum_box, _, self.momentum_level, self.momentum = self.make_slider(
            sliders, "Moment", self.on_momentum, frm=0, to=7, visible=False
        )

        # Horn
        self.horn_box, self.horn_title_box, self.horn_level, self.horn = self.make_slider(
            sliders, "Horn", self.on_horn, frm=0, to=15, visible=False
        )

        # compute rr speed button size
        w = sliders.tk.winfo_width()
        h = (5 * self.button_size) - (self.brake.tk.winfo_height() + self.brake_level.tk.winfo_height()) - 5

        # RR Speeds button
        self._rr_speed_box = rr_box = Box(
            sliders,
            grid=[0, 1, 2, 1],  # spans two columns under sliders
            align="top",
        )

        # RR Speeds button
        self._rr_speed_btn = rr_btn = HoldButton(rr_box, "", command=self.on_rr_speed)
        rr_btn.tk.pack(fill="both", expand=True)

        img, inverted_img = self.get_image(find_file("RR-Speeds.jpg"), size=(w, h))
        rr_btn.tk.config(
            image=img,
            compound="center",
            width=w,
            height=h,
            padx=3,  # small padding
            pady=3,
            borderwidth=2,  # light border
            relief="ridge",  # gives pressable button feel
            highlightthickness=0,
        )
        rr_btn.images = (img, inverted_img)

        # Bell button for freight sounds
        self._bell_box = bell_box = Box(
            sliders,
            grid=[0, 1, 2, 1],  # spans two columns under sliders
            align="top",
        )
        self._bell_btn = bell_btn = HoldButton(
            bell_box,
            BELL_KEY,
            text_size=self.s_24,
            text_bold=True,
            command=self.on_engine_command,
            args=[["BELL_ONE_SHOT_DING", "RING_BELL"]],
        )
        bell_btn.tk.pack(fill="both", expand=True)
        bell_box.hide()

        # --- HIDE IT AGAIN after sizing is complete ---
        self.controller_box.visible = False

    def make_slider(
        self,
        sliders: Box,
        title: str,
        command: Callable,
        frm: int,
        to: int,
        step: int = 1,
        visible: bool = True,
    ) -> tuple[Box, TitleBox, Text, Slider]:
        momentum_box = Box(
            sliders,
            border=1,
            grid=[0, 0],
            visible=visible,
        )

        cell = TitleBox(momentum_box, title, align="top", border=1)
        cell.text_size = self.s_10
        momentum_level = Text(
            cell,
            text="00",
            color="black",
            align="top",
            bold=True,
            size=self.s_18,
            width=3,
            font="DigitalDream",
        )
        momentum_level.bg = "black"
        momentum_level.text_color = "white"

        momentum = Slider(
            momentum_box,
            align="top",
            horizontal=False,
            step=step,
            width=int(self.button_size / 3),
            height=self.slider_height,
            command=command,
        )
        momentum.text_color = "black"
        momentum.tk.config(
            from_=frm,
            to=to,
            takefocus=0,
            troughcolor="#003366",  # deep Lionel blue for the track,
            activebackground=LIONEL_ORANGE,  # bright Lionel orange for the handle
            bg="lightgrey",  # darker navy background
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,  # subtle orange outline
            width=int(self.button_size / 3),
            sliderlength=int(self.slider_height / 6),
        )
        momentum.tk.bind("<Button-1>", lambda e: momentum.tk.focus_set())
        momentum.tk.bind("<ButtonRelease-1>", self.clear_focus, add="+")
        momentum.tk.bind("<ButtonRelease>", self.clear_focus, add="+")

        return momentum_box, cell, momentum_level, momentum

    def create_popup(self, title_text: str, build_body: Callable[[Box], None]):
        """
        Create a top-level overlay popup with a title, custom body, and close button.
        `build_body` receives a Box to populate with popup-specific content.
        Returns the overlay Box.
        """
        overlay = Box(
            self.app,
            align="top",
            border=2,
            visible=False,
        )
        overlay.bg = "white"

        # Title row
        w = self.emergency_box_width
        h = self.button_size // 3
        title_row = Box(overlay, width=w, height=h)
        title_row.bg = "lightgrey"

        title = Text(title_row, text=title_text, bold=True, size=self.s_18)
        title.bg = "lightgrey"

        # Body container (the caller populates this)
        body = Box(overlay, layout="auto")
        build_body(body)

        # Close button
        btn = PushButton(
            overlay,
            text="Close",
            align="bottom",
            command=self.close_popup,
            args=[overlay],
        )
        btn.text_bolded = False
        btn.text_size = self.s_20
        btn.tk.config(
            borderwidth=3,
            relief="raised",
            highlightthickness=1,
            highlightbackground="black",
            padx=6,
            pady=4,
            activebackground="#e0e0e0",
            background="#f7f7f7",
        )
        btn.tk.pack_configure(padx=20, pady=20)
        overlay.hide()

        return overlay

    def build_tower_dialogs_body(self, body: Box):
        self.tower_dialog_box = self.make_combo_panel(body, TOWER_DIALOGS)

    def build_crew_dialogs_body(self, body: Box):
        self.crew_dialog_box = self.make_combo_panel(body, CREW_DIALOGS)

    def build_conductor_actions_body(self, body: Box):
        self.conductor_actions_box = self.make_combo_panel(body, CONDUCTOR_ACTIONS)

    def build_lights_body(self, body: Box):
        # cab light
        master_box = Box(body, layout="grid", border=1)
        cell = Box(master_box, layout="auto", grid=[0, 0], align="bottom", visible=True)
        cell.tk.configure(
            width=self.button_size,
            height=self.button_size,
        )
        cell.tk.pack_propagate(False)
        master_box.tk.grid_columnconfigure(0, weight=1, minsize=self.button_size + 20)

        btn = HoldButton(
            cell,
            text=AUX2_KEY,
            text_size=self.s_18,
            text_bold=True,
            command=self.on_engine_command,
            args=["AUX2_OPTION_ONE"],
        )
        btn.tk.config(
            height=self.button_size,
            width=self.button_size,
            borderwidth=1,
            compound="center",
            anchor="center",
            padx=0,
            pady=0,
            bd=1,
            relief="solid",
            highlightthickness=1,
        )
        self._elements.add(btn)

        cell = Box(master_box, layout="auto", grid=[1, 0], align="bottom", visible=True)
        cell.tk.configure(
            width=self.button_size,
            height=self.button_size,
        )
        cell.tk.pack_propagate(False)
        _ = Text(cell, text=" ")

        cell = Box(master_box, layout="auto", grid=[2, 0], align="bottom", visible=True)
        cell.tk.configure(
            width=self.button_size,
            height=self.button_size,
        )
        cell.tk.pack_propagate(False)
        master_box.tk.grid_columnconfigure(2, weight=1, minsize=self.button_size + 20)

        btn = HoldButton(
            cell,
            text=CAB_KEY,
            text_size=self.s_18,
            text_bold=True,
            command=self.on_engine_command,
            args=[("CAB_AUTO", "AUX2_OPT_ONE")],
        )

        btn.tk.config(
            height=self.button_size,
            width=self.button_size,
            borderwidth=1,
            compound="center",
            anchor="center",
            padx=0,
            pady=0,
            bd=1,
            relief="solid",
            highlightthickness=1,
        )
        self._elements.add(btn)

        # diesel options
        self.diesel_lights_box = self.make_combo_panel(body, DIESEL_LIGHTS)

        # steam options
        self.steam_lights_box = self.make_combo_panel(body, STEAM_LIGHTS)
        self.steam_lights_box.hide()

    def make_combo_panel(self, body: Box, options: dict, min_width: int = 12) -> Box:
        combo_box = Box(body, layout="grid", border=1)

        # How many combo boxes do we have; display them in 2 columns:
        boxes_per_column = int(math.ceil(len(options) / 2))
        width = max(max(map(len, options.keys())) - 1, min_width)

        for idx, (title, values) in enumerate(options.items()):
            # place 4 per column
            row = idx % boxes_per_column
            col = idx // boxes_per_column

            # combo contents and mapping
            if self.can_hack_combo:
                select_ops = [v[0] for v in values]
            else:
                select_ops = [title] + [v[0] for v in values]
            od = {v[0]: v[1] for v in values}

            slot = Box(combo_box, grid=[col, row])
            cb = Combo(slot, options=select_ops, selected=title)
            self.rebuild_combo(cb, od, title)

            cb.update_command(self.make_combo_callback(cb, od, title))
            cb.tk.config(width=width)
            cb.text_size = self.s_20
            cb.tk.pack_configure(padx=6, pady=15)
            # set the hover color of the element the curser is over when selecting an item
            if "menu" in cb.tk.children:
                menu = cb.tk.children["menu"]
                menu.config(activebackground="lightgrey")
            self._elements.add(cb)
        return combo_box

    def make_combo_callback(self, cb: Combo, od: dict, title: str) -> Callable[[str], None]:
        def func(selected: str):
            self.on_combo_select(cb, od, title, selected)

        return func

    def on_combo_select(self, cb: Combo, od: dict, title: str, selected: str) -> None:
        cmd = od.get(selected, None)
        if isinstance(cmd, str):
            self.on_engine_command(cmd)
        # rebuild combo
        self.rebuild_combo(cb, od, title)

    # noinspection PyProtectedMember
    def rebuild_combo(self, cb: Combo, od: dict, title: str):
        cb.clear()
        if not self.can_hack_combo:
            cb.append(title)
        for option in od.keys():
            cb.append(option)
        if self.can_hack_combo:
            cb._selected.set(title)
        else:
            cb.select_default()

    def build_button_panel(
        self,
        body: Box,
        buttons: list[list[tuple]],
    ) -> Box:
        button_box = Box(body, layout="grid", border=1)
        width = int(3 * self.button_size)

        for r, kr in enumerate(buttons):
            for c, button in enumerate(kr):
                if isinstance(button, tuple):
                    op = button[0]
                    label = button[1]
                else:
                    raise ValueError(f"Invalid button: {button} ({type(button)})")
                cell, nb = self.make_keypad_button(
                    button_box,
                    label,
                    r,
                    c,
                    bolded=True,
                    size=self.s_18,
                    command=self.on_engine_command,
                    args=[op],
                )
                cell.tk.config(width=width)
                nb.tk.config(width=width)
                self._elements.add(nb)

        return button_box

    def build_station_dialogs_body(self, body: Box):
        self.station_dialog_box = self.build_button_panel(body, STATION_DIALOGS)

    def build_steward_dialogs_body(self, body: Box):
        self.steward_dialog_box = self.build_button_panel(body, STEWARD_DIALOGS)

    def build_bell_horn_body(self, body: Box):
        cs = self.button_size
        height = int(2.5 * cs)
        opts_box = Box(
            body,
            layout="grid",
            align="top",
            border=1,
            height=height,
            width=6 * cs,
        )

        bt = Text(opts_box, text="Bell: ", grid=[0, 0], align="left")
        bt.text_size = self.s_20
        bt.text_bold = True

        _, bc = self.make_keypad_button(
            opts_box,
            CYCLE_KEY,
            0,
            1,
            align="left",
            command=self.on_engine_command,
            args=["CYCLE_BELL_TONE"],
        )
        _, bp = self.make_keypad_button(
            opts_box,
            PLAY_PAUSE_KEY,
            0,
            2,
            align="left",
            command=self.on_engine_command,
            args=["RING_BELL"],
        )
        _, bon = self.make_keypad_button(
            opts_box,
            "On",
            0,
            3,
            align="left",
            command=self.on_engine_command,
            args=["BELL_ON"],
        )
        _, boff = self.make_keypad_button(
            opts_box,
            "Off",
            0,
            4,
            align="left",
            command=self.on_engine_command,
            args=["BELL_OFF"],
        )
        self._elements.add(bt)
        self._elements.add(bc)
        self._elements.add(bp)
        self._elements.add(bon)
        self._elements.add(boff)

        ht = Text(opts_box, text="Horn: ", grid=[0, 1])
        ht.text_size = self.s_20
        ht.text_bold = True

        _, hc = self.make_keypad_button(
            opts_box,
            CYCLE_KEY,
            1,
            1,
            align="left",
            command=self.on_engine_command,
            args=["CYCLE_HORN_TONE"],
        )
        _, hp = self.make_keypad_button(
            opts_box,
            PLAY_KEY,
            1,
            2,
            align="left",
            command=self.on_engine_command,
            args=["BLOW_HORN_ONE"],
        )
        _, hrc = self.make_keypad_button(
            opts_box,
            "",
            1,
            3,
            image=find_file("rail_crossing.jpg"),
            align="left",
            command=self.on_engine_command,
            args=["GRADE_CROSSING_SEQ"],
        )

        self._elements.add(ht)
        self._elements.add(hc)
        self._elements.add(hp)
        self._elements.add(hrc)

    def build_rr_speed_body(self, body: Box):
        keypad_box = Box(body, layout="grid", border=1)
        width = int(3 * self.button_size)

        for r, kr in enumerate(RR_SPEED_LAYOUT):
            for c, op in enumerate(kr):
                label = ""
                dialog = None

                if isinstance(op, tuple):
                    if op[1].startswith("Emergency"):
                        label = op[1]
                        dialog = "EMERGENCY_CONTEXT_DEPENDENT"
                    else:
                        label = op[1] + ("\nSpeed" if op[0] != "SPEED_STOP_HOLD" else "")
                        dialog = "TOWER_" + op[0]

                cell, nb = self.make_keypad_button(
                    keypad_box,
                    label,
                    r,
                    c,
                    bolded=True,
                    size=self.s_18,
                    command=self.on_speed_command,
                    args=[op[0]],
                )
                nb.hold_threshold = 0.5

                cell.tk.config(width=width)
                nb.tk.config(width=width)

                if label.startswith("Emergency"):
                    nb.text_color = "white"
                    nb.bg = "red"
                else:
                    self.rr_speed_btns.add(nb)
                    nb.rr_speed = op[0]

                if dialog:
                    nb.on_hold = (self.on_speed_command, [f"{dialog}, {op[0]}"])

    def build_info_overlay(self, body: Box):
        # Container for the state info, using a 2-column grid
        info_box = Box(body, layout="grid", border=1)

        # Make both columns share the same width and stretch equally
        info_box.tk.grid_columnconfigure(0, weight=1, uniform="stateinfo")
        info_box.tk.grid_columnconfigure(1, weight=1, uniform="stateinfo")
        info_box.tk.grid_columnconfigure(2, weight=1, uniform="stateinfo")
        info_box.tk.grid_columnconfigure(3, weight=1, uniform="stateinfo")

        aw, _ = self.calc_image_box_size()
        info_box.tk.config(width=aw)

        # ------------------------------------------------------------------
        # Row 0 – two independent columns: "Road Number" | "Type"
        # ------------------------------------------------------------------

        self._info_details["number"] = self.make_info_field(info_box, "Road Number", grid=[0, 0])
        self._info_details["type"] = self.make_info_field(info_box, "Type", grid=[1, 0, 3, 1])

        # ------------------------------------------------------------------
        # Row 1 – one control spanning both columns: "Road Name"
        # ------------------------------------------------------------------
        self._info_details["name"] = self.make_info_field(info_box, "Road Name", grid=[0, 1, 4, 1])

        # ------------------------------------------------------------------
        # Row 2 – two independent columns: "Control Type" | "Sound Type"
        # ------------------------------------------------------------------
        self._info_details["control"] = self.make_engine_field(info_box, "Control", grid=[0, 2, 2, 1])
        self._info_details["sound"] = self.make_engine_field(info_box, "Sound", grid=[2, 2, 2, 1])

        # ------------------------------------------------------------------
        # Row 3: Speed information
        # ------------------------------------------------------------------
        self._info_details["speed"] = self.make_engine_field(info_box, "Speed", grid=[0, 3])
        self._info_details["target"] = self.make_engine_field(info_box, "Target Speed", grid=[1, 3])
        self._info_details["limit"] = self.make_engine_field(info_box, "Speed Limit", grid=[2, 3])
        self._info_details["max"] = self.make_engine_field(info_box, "Max Speed", grid=[3, 3])

        # ------------------------------------------------------------------
        # Row 4: State information
        # ------------------------------------------------------------------
        self._info_details["dir"] = self.make_engine_field(info_box, "Direction", grid=[0, 4])
        self._info_details["smoke"] = self.make_engine_field(info_box, "Smoke Level", grid=[1, 4])
        self._info_details["mom"] = self.make_engine_field(info_box, "Momentum", grid=[2, 4])
        self._info_details["brake"] = self.make_engine_field(info_box, "Train Brake", grid=[3, 4])

        # ------------------------------------------------------------------
        # Row 5: State information
        # ------------------------------------------------------------------
        self._info_details["labor"] = self.make_engine_field(info_box, "Labor", grid=[0, 5])
        self._info_details["rpm"] = self.make_engine_field(info_box, "RPM", grid=[1, 5])
        self._info_details["fuel"] = self.make_engine_field(info_box, "Fuel Level", grid=[2, 5])
        self._info_details["water"] = self.make_engine_field(info_box, "Water Level", grid=[3, 5])

        # ------------------------------------------------------------------
        # Row 6: Train information
        # ------------------------------------------------------------------
        self._info_details["engines"] = self.make_train_field(info_box, "Engines", grid=[0, 6])
        self._info_details["lead"] = self.make_train_field(info_box, "Head TMCC ID", grid=[1, 6])
        self._info_details["cars"] = self.make_train_field(info_box, "Cars", grid=[2, 6])
        self._info_details["accessories"] = self.make_train_field(info_box, "Accessories", grid=[3, 6])

        # ------------------------------------------------------------------
        # Row 2 – Accessories
        # ------------------------------------------------------------------
        self._info_details["mode"] = self.make_acc_field(info_box, "Mode", grid=[0, 2])
        self._info_details["parent"] = self.make_acc_field(info_box, "Parent", grid=[1, 2])
        self._info_details["port"] = self.make_acc_field(info_box, "Port", grid=[2, 2])
        self._info_details["firmware"] = self.make_acc_field(info_box, "Firmware", grid=[3, 2])

    def update_state_info(self) -> None:
        state = self.active_state
        if state:
            p_info = None
            self._info_details["number"][1].value = state.road_number
            self._info_details["name"][1].value = state.road_name
            log.debug(f"Updating details: {state.scope} {state.address}")
            if self.is_engine_or_train:
                if isinstance(state, EngineState):
                    p_info = self._prod_info_cache.get(state.tmcc_id, None)
                elif isinstance(state, TrainState):
                    p_info = self._prod_info_cache.get(state.head_tmcc_id, None)
                etype = state.engine_type_label
                etype = (
                    f"{p_info.engine_type} {etype}" if isinstance(p_info, ProdInfo) and p_info.engine_type else etype
                )
                self._info_details["type"][1].value = etype
                self._info_details["control"][1].value = state.control_type_text
                self._info_details["sound"][1].value = state.sound_type_label
                self._info_details["dir"][1].value = "Fwd" if state.is_forward else "Rwd" if state.is_reverse else ""
                self._info_details["smoke"][1].value = state.smoke_text
                self._info_details["mom"][1].value = state.momentum_text
                self._info_details["brake"][1].value = state.train_brake_label
                self._info_details["labor"][1].value = state.labor_label
                self._info_details["rpm"][1].value = state.rpm_label
                self._info_details["fuel"][1].value = f"{state.fuel_level_pct:>3d} %"
                self._info_details["water"][1].value = f"{state.water_level_pct:>3d} %"

                # handle speeds
                s, ts, sl, ms = state.speeds
                self._info_details["speed"][1].value = f"{s:>3d}"
                self._info_details["target"][1].value = f"{ts:>3d}"
                self._info_details["limit"][1].value = f"{sl:>3d}" if sl is not None else ""
                self._info_details["max"][1].value = f"{ms:>3d}"

                # train-specific
                if isinstance(state, TrainState):
                    self._info_details["engines"][1].value = f"{state.num_engines}"
                    self._info_details["lead"][1].value = f"{state.head_tmcc_id:04d}"
                    self._info_details["cars"][1].value = f"{state.num_train_linked}"
                    self._info_details["accessories"][1].value = f"{state.num_accessories}"
            elif isinstance(state, LcsProxyState):
                self._info_details["type"][1].value = state.accessory_type
                self._info_details["mode"][1].value = state.mode
                self._info_details["parent"][1].value = state.parent_id
                self._info_details["port"][1].value = state.port
                self._info_details["firmware"][1].value = state.firmware

    def make_engine_field(self, parent: Box, title: str, grid: list[int], max_cols: int = 4) -> tuple[TitleBox, Text]:
        return self.make_info_field(parent, title, grid, max_cols, scope=CommandScope.ENGINE)

    def make_acc_field(self, parent: Box, title: str, grid: list[int], max_cols: int = 4) -> tuple[TitleBox, Text]:
        return self.make_info_field(parent, title, grid, max_cols, scope=CommandScope.ACC)

    def make_train_field(self, parent: Box, title: str, grid: list[int], max_cols: int = 4) -> tuple[TitleBox, Text]:
        return self.make_info_field(parent, title, grid, max_cols, scope=CommandScope.TRAIN)

    # noinspection PyTypeChecker
    def make_info_field(
        self,
        parent: Box,
        title: str,
        grid: list[int],
        max_cols: int = 4,
        scope: CommandScope = None,
    ) -> tuple[TitleBox, Text]:
        # grid can be [col, row] or [col, row, colspan, rowspan]
        aw, _ = self.calc_image_box_size()
        if len(grid) >= 4:
            col, row, colspan, rowspan = grid
            aw = colspan * int(aw / max_cols)
        else:
            col, row = grid
            colspan, rowspan = 1, 1
            aw = int(aw / max_cols)

        # TitleBox participates in the parent's grid
        tb = TitleBox(
            parent,
            text=title,
            layout="grid",  # use grid INSIDE the TitleBox
            grid=grid,
            width="fill",
            align="left",
        )
        tb.text_size = self.s_10
        tb.display_scope = scope

        # Now tell Tk this one actually spans columns/rows
        tb.tk.grid_configure(column=col, row=row, columnspan=colspan, rowspan=rowspan, sticky="ew")
        tb.tk.config(width=aw)
        tb.tk.pack_propagate(False)

        # Let the internal grid column stretch so the TextBox can fill
        tb.tk.grid_columnconfigure(0, weight=1)

        # Value field inside the TitleBox
        tf = Text(tb, grid=[0, 0], width="fill", height=1)
        tf.text_size = self.s_18
        tf.tk.config(bd=0, highlightthickness=0, justify="left", anchor="w", width=aw)  # borderless

        return tb, tf

    def on_info(self) -> None:
        if self.info_overlay is None:
            self.info_overlay = self.create_popup(self.version, self.build_info_overlay)
        # show/hide fields in the overlay
        state = self.active_state
        if state is None:
            return  # this should never be the case...
        scope = CommandScope.ACC if isinstance(state, LcsProxyState) and state.is_lcs else state.scope
        for tb, _ in self._info_details.values():
            if tb.display_scope == scope:
                tb.visible = True  # always display fields associated with state.scope
            elif tb.display_scope is None:
                tb.visible = True  # always display fields with no scope specified
            elif scope == CommandScope.TRAIN and tb.display_scope == CommandScope.ENGINE:
                tb.visible = True  # display engine fields for trains
            else:
                tb.visible = False
        self.update_state_info()
        self.show_popup(self.info_overlay)

    def on_rr_speed(self) -> None:
        if self.rr_speed_overlay is None:
            self.rr_speed_overlay = self.create_popup("Official Rail Road Speeds", self.build_rr_speed_body)
        self.show_popup(self.rr_speed_overlay)

    def on_lights(self) -> None:
        if self.lights_overlay is None:
            self.lights_overlay = self.create_popup("Lighting", self.build_lights_body)
        if self.active_engine_state:
            state = self.active_engine_state
        else:
            state = self.active_state
        if state.is_steam:
            self.steam_lights_box.show()
            self.diesel_lights_box.hide()
        else:
            self.steam_lights_box.hide()
            self.diesel_lights_box.show()
        # make sure button is reset, as popup prevents normal handling
        self.show_popup(self.lights_overlay, "AUX2_OPTION_ONE", "e")

    def on_tower_dialog(self) -> None:
        if self.tower_dialog_overlay is None:
            self.tower_dialog_overlay = self.create_popup("Tower Dialogs", self.build_tower_dialogs_body)
        self.show_popup(self.tower_dialog_overlay, "TOWER_CHATTER", "e")

    def on_crew_dialog(self) -> None:
        if self.crew_dialog_overlay is None:
            self.crew_dialog_overlay = self.create_popup("Engineer & Crew Dialogs", self.build_crew_dialogs_body)
        self.show_popup(self.crew_dialog_overlay, "ENGINEER_CHATTER", "e")

    def on_conductor_actions(self) -> None:
        if self.conductor_overlay is None:
            self.conductor_overlay = self.create_popup("Conductor Actions", self.build_conductor_actions_body)
        self.show_popup(self.conductor_overlay, "ENGINEER_CHATTER", "p")

    def on_station_dialogs(self) -> None:
        if self.station_overlay is None:
            self.station_overlay = self.create_popup("Station Dialogs", self.build_station_dialogs_body)
        self.show_popup(self.station_overlay, "TOWER_CHATTER", "p")

    def on_steward_dialogs(self) -> None:
        if self.steward_overlay is None:
            self.steward_overlay = self.create_popup("Steward Dialogs", self.build_steward_dialogs_body)
        self.show_popup(self.steward_overlay, "STEWARD_CHATTER", "p")

    def on_bell_horn_options(self) -> None:
        if self.bell_overlay is None:
            self.bell_overlay = self.create_popup("Bell/Horn Options", self.build_bell_horn_body)
        self.show_popup(self.bell_overlay, "RING_BELL", "e")

    def show_popup(self, overlay, op: str = None, modifier: str = None):
        with self._cv:
            if op:
                key = (op, modifier) if modifier else op
                _, btn = self.engine_ops_cells[key]
                btn.restore_color_state()
            if self.controller_box.visible:
                self.controller_box.hide()
                self._on_close_show = self.controller_box
            if self.keypad_box.visible:
                self.keypad_box.hide()
                self._on_close_show = self.keypad_box
            if self.sensor_track_box.visible:
                self.sensor_track_box.hide()
                self._on_close_show = self.sensor_track_box
            self._current_popup = overlay
            x, y = self.popup_position
            overlay.tk.place(x=x, y=y)
            overlay.show()

    def close_popup(self, overlay: Widget = None):
        overlay = overlay or self._current_popup
        self._current_popup = None
        if overlay:
            overlay.hide()
            overlay.tk.place_forget()
        if self._on_close_show:
            self._on_close_show.show()
            self._on_close_show = None

    def show_horn_control(self) -> None:
        for loco_type in ["d", "s"]:
            _, btn = self.engine_ops_cells[("BLOW_HORN_ONE", loco_type)]
            btn.on_hold = self.toggle_momentum_train_brake
        self.momentum_box.hide()
        self.brake_box.hide()
        self.horn_box.show()

    def toggle_momentum_train_brake(self, btn: PushButton = None) -> None:
        if self.horn_box.visible:
            # hide the horn box
            self.horn_box.hide()

        if btn is None:  # called from horn handler
            # restore what was there before; if the swaped button says "Momentum"
            # then show Train Brake, and vice versa
            _, btn = self.engine_ops_cells[(MOM_TB, "e")]
            if btn.text == MOMENTUM:
                self.momentum_box.visible = False
                self.brake_box.visible = True
            else:
                self.brake_box.visible = False
                self.momentum_box.visible = True
        else:
            if btn.text == MOMENTUM:
                btn.text = TRAIN_BRAKE
                self.brake_box.visible = False
                self.momentum_box.visible = True
            else:
                btn.text = MOMENTUM
                self.momentum_box.visible = False
                self.brake_box.visible = True

        # restore the on_hold handler
        for loco_type in ["d", "s"]:
            _, btn = self.engine_ops_cells[("BLOW_HORN_ONE", loco_type)]
            btn.on_hold = self.show_horn_control

    # noinspection PyUnusedLocal
    def clear_focus(self, e=None):
        """
        Touchscreen-safe focus clearing for throttle slider.
        Ensures focus moves off the Scale after finger release
        and forces a redraw so the grab handle deactivates.
        """
        if self.app.tk.focus_get() in {self.throttle.tk, self.brake.tk, self.momentum.tk, self.horn.tk}:
            if self.app.tk.focus_get() == self.horn.tk:
                self._stop_quill()
            self.app.tk.after_idle(self._do_clear_focus)

    def _stop_quill(self):
        with self._cv:
            # cancel pending after() call if exists
            if self._quill_after_id is not None:
                try:
                    self.app.tk.after_cancel(self._quill_after_id)
                except (TclError, AttributeError):
                    pass
                self._quill_after_id = None
            # reset slider
            self.horn.value = 0

    def _do_clear_focus(self):
        self.focus_widget.focus_set()
        self.throttle.tk.event_generate("<Leave>")
        self.brake.tk.event_generate("<Leave>")
        self.momentum.tk.event_generate("<Leave>")
        self.horn.tk.event_generate("<Leave>")

    def on_throttle(self, value):
        if self.throttle.after_id is not None:
            self.throttle.tk.after_cancel(self.throttle.after_id)
        # schedule new callback in 150 ms
        self.throttle.after_id = self.throttle.tk.after(200, self.on_throttle_released, int(value))

    def on_throttle_released(self, value: int) -> None:
        self.throttle.after_id = None
        if self.app.tk.focus_get() == self.throttle.tk:
            # make sure we're still holding the throttle
            self.throttle.after_id = self.throttle.tk.after(200, self.on_throttle_released, int(value))
        else:
            self.on_speed_command(value)

    def on_train_brake(self, value):
        if self.app.tk.focus_get() == self.brake.tk:
            value = int(value)
            self.brake_level.value = f"{value:02d}"
            self.on_engine_command("TRAIN_BRAKE", data=value)

    def on_horn(self, value: int = None) -> None:
        value = int(value) if value else self.horn.value
        self.horn_level.value = f"{value:02d}"
        with self._cv:
            if self._quill_after_id is not None:
                try:
                    self.app.tk.after_cancel(self._quill_after_id)
                except (TclError, AttributeError):
                    pass
                self._quill_after_id = None
        if value > 0:
            self.do_quilling_horn(value)

    def do_quilling_horn(self, value: int):
        self.on_engine_command(["QUILLING_HORN", "BLOW_HORN_ONE"], data=value)
        # make sure we still have focus
        with self._cv:
            if self.app.tk.focus_get() == self.horn.tk:
                self._quill_after_id = self.app.tk.after(500, self.do_quilling_horn, value)
            else:
                self._stop_quill()

    def on_momentum(self, value):
        if self.app.tk.focus_get() == self.momentum.tk:
            # we need state info for this
            if self.active_engine_state:
                state = self.active_engine_state
            else:
                state = self.active_state
            if isinstance(state, EngineState):
                value = int(value)
                if state.is_legacy:
                    self.on_engine_command("MOMENTUM", data=value)
                else:
                    if value in {0, 1}:
                        value = 0
                        self.on_engine_command("MOMENTUM_LOW", data=value)
                    elif value in {2, 3, 4}:
                        value = 3
                        self.on_engine_command("MOMENTUM_MEDIUM")
                    else:
                        value = 7
                        self.on_engine_command("MOMENTUM_HIGH")
                self.momentum_level.value = f"{value:02d}"

    def on_recents(self, value: str):
        if value != self.title:
            state = self._options_to_state[value]
            self.update_component_info(tmcc_id=state.tmcc_id)
            self.header.select_default()

    @property
    def active_state(self) -> S | None:
        if self.scope and self._scope_tmcc_ids.get(self.scope):
            return self._state_store.get_state(self.scope, self._scope_tmcc_ids[self.scope], False)
        else:
            return None

    def get_options(self) -> list[str]:
        options = [self.title]
        self._options_to_state.clear()
        queue = self._recents_queue.get(self.scope, None)
        if isinstance(queue, UniqueDeque):
            num_chars = 4 if self.scope in {CommandScope.ENGINE} else 2
            for state in queue:
                name = f"{state.tmcc_id:0{num_chars}d}: {state.road_name}"
                road_number = state.road_number
                if road_number and road_number.isnumeric() and int(road_number) != state.tmcc_id:
                    name += f" #{int(road_number)}"
                if name:
                    options.append(name)
                    self._options_to_state[name] = state
        return options

    def monitor_state(self):
        with self._cv:
            tmcc_id = self._scope_tmcc_ids.get(self.scope, 0)
            watcher = self._scope_watchers.get(self.scope, None)
            if isinstance(watcher, StateWatcher) and watcher.tmcc_id == tmcc_id:
                # we're good, return
                return
            if isinstance(watcher, StateWatcher):
                # close existing watcher
                watcher.shutdown()
                self._scope_watchers[self.scope] = None
            if tmcc_id:
                # create a new state watcher to monitor state of scoped entity
                state = self._state_store.get_state(self.scope, tmcc_id, False)
                # state shouldn't be None, but good to check
                if state:
                    action = self.get_scoped_on_change(state)
                    self._scope_watchers[self.scope] = StateWatcher(state, action)

    def get_scoped_on_change(self, state: S) -> Callable:
        action = self._scoped_callbacks.get(self.scope, lambda s: print(s))

        def upd():
            if not self._shutdown_flag.is_set():
                self._message_queue.put((action, [state]))

        return upd

    # noinspection PyUnusedLocal
    def on_new_engine(self, state: EngineState = None, ops_mode_setup: bool = False) -> None:
        self._active_engine_state = state
        if state:
            # special case tain being used as BPC2
            if isinstance(state, TrainState) and state.is_power_district:
                self.ops_mode(update_info=True, state=state)
                return
            # only set throttle/brake/momentum value if we are not in the middle of setting it
            self.speed.value = f"{state.speed:03d}"
            self.update_rr_speed_buttons(state)
            if self.throttle.tk.focus_displayof() != self.throttle.tk:
                self.throttle.value = state.target_speed
            if state.speed != state.target_speed:
                self.throttle.tk.config(
                    troughcolor="#4C96C5",
                )
            else:
                self.throttle.tk.config(
                    troughcolor="#003366",  # deep Lionel blue for the track,
                )

            self.brake_level.value = f"{state.train_brake:02d}"
            if self.brake.tk.focus_displayof() != self.brake.tk:
                self.brake.value = state.train_brake

            self.momentum_level.value = f"{state.momentum:02d}"
            if self.app.tk.focus_get() != self.momentum.tk:
                self.momentum.value = state.momentum

            if state.is_legacy:
                self.momentum.tk.config(resolution=1, showvalue=True)

            else:
                self.momentum.tk.config(resolution=4, showvalue=False)

            _, btn = self.engine_ops_cells[("FORWARD_DIRECTION", "e")]
            btn.bg = self._active_bg if state.is_forward else self._inactive_bg
            _, btn = self.engine_ops_cells[("REVERSE_DIRECTION", "e")]
            btn.bg = self._active_bg if state.is_reverse else self._inactive_bg

        if state and state.is_legacy:
            self.throttle.tk.config(from_=195, to=0)
        else:
            self.throttle.tk.config(from_=31, to=0)
        # update info detail popup, if its visible
        if self.info_overlay and self.info_overlay.visible:
            self.update_state_info()

    def update_rr_speed_buttons(self, state: EngineState) -> None:
        rr_speed = state.rr_speed
        for btn in self.rr_speed_btns:
            if rr_speed and btn.rr_speed.endswith(rr_speed.name):
                btn.bg = "green"
            else:
                btn.bg = "white"

    def on_new_route(self, state: RouteState = None):
        # must be called from app thread!!
        if state is None:
            tmcc_id = self._scope_tmcc_ids[CommandScope.ROUTE]
            state = self._state_store.get_state(CommandScope.ROUTE, tmcc_id, False) if 1 <= tmcc_id < 99 else None
        if state:
            self.fire_route_btn.bg = self._active_bg if state.is_active else self._inactive_bg
        else:
            self.fire_route_btn.bg = self._inactive_bg

    def on_new_switch(self, state: SwitchState = None):
        # must be called from app thread!!
        if state is None:
            tmcc_id = self._scope_tmcc_ids[CommandScope.SWITCH]
            state = self._state_store.get_state(CommandScope.SWITCH, tmcc_id, False) if 1 <= tmcc_id < 99 else None
        if state:
            self.switch_thru_btn.bg = self._active_bg if state.is_thru else self._inactive_bg
            self.switch_out_btn.bg = self._active_bg if state.is_out else self._inactive_bg
        else:
            self.switch_thru_btn.bg = self.switch_out_btn.bg = self._inactive_bg

    def on_new_accessory(self, state: AccessoryState | TrainState = None):
        state = state if state else self.active_state
        tmcc_id = self._scope_tmcc_ids[CommandScope.ACC]
        if isinstance(state, AccessoryState):
            if state.is_sensor_track:
                st_state = self._state_store.get_state(CommandScope.IRDA, tmcc_id, False)
                if isinstance(st_state, IrdaState):
                    self.sensor_track_buttons.value = st_state.sequence.value
                else:
                    self.sensor_track_buttons.value = None
            elif state.is_bpc2 or state.is_asc2:
                self.update_ac_status(state)
            elif state.is_amc2:
                pass
        elif isinstance(state, TrainState) and state.is_power_district:
            self.update_ac_status(state)

    def update_ac_status(self, state: AccessoryState | TrainState):
        power_on_image, _ = self.get_titled_image(self.power_on_path)
        power_off_image, _ = self.get_titled_image(self.power_off_path)
        img = power_on_image if state.is_aux_on else power_off_image
        self.ac_status_btn.tk.config(
            image=img,
            height=self.titled_button_size,
            width=self.titled_button_size,
        )
        self.ac_status_btn.image = img

    def make_scope(self, app: App):
        button_height = int(round(40 * self._scale_by))
        self.scope_box = scope_box = Box(app, layout="grid", border=2, align="bottom")
        img = tk.PhotoImage(width=self.scope_size, height=button_height)
        self._btn_images.append(img)
        for i, scope_abbrev in enumerate(["ACC", "SW", "RTE", "TR", "ENG"]):
            scope = CommandScope.by_prefix(scope_abbrev)
            # Create a PhotoImage to enforce button size
            # img = tk.PhotoImage(width=self.scope_size, height=button_height)
            # self._btn_images.append(img)
            pb = HoldButton(
                scope_box,
                text=scope_abbrev,
                grid=[i, 1],
                align="top",
                height=1,
                text_size=self.s_18,
                text_bold=True,
                command=self.on_scope,
                args=[scope],
            )
            pb.scope = scope
            # Configure the button with the image as background
            pb.tk.config(
                image=img,
                compound="center",
                width=self.scope_size,
                height=button_height,
                padx=0,
                pady=0,
            )
            # Make the grid column expand to fill space
            scope_box.tk.grid_columnconfigure(i, weight=1)
            # associate the button with its scope
            self._scope_buttons[scope] = pb
            # don't overwrite initial tmcc id if one specified
            if scope not in self._scope_tmcc_ids:
                self._scope_tmcc_ids[scope] = 0
        # highlight initial button
        self.on_scope(self.scope)

    # noinspection PyTypeChecker
    def on_scope(self, scope: CommandScope) -> None:
        self.scope_box.hide()
        force_entry_mode = False
        clear_info = True
        self._last_engine_type = None
        for k, v in self._scope_buttons.items():
            if k == scope:
                v.bg = self._enabled_bg
                v.text_color = self._enabled_text
            else:
                v.bg = "white"
                v.text_color = "black"
        # if new scope selected, display most recent scoped component, if one existed
        if scope != self.scope:
            self.tmcc_id_box.text = f"{scope.title} ID"
            self.scope = scope
            # if scoped TMCC_ID is 0, take the first item on the recents queue
            if self._scope_tmcc_ids[scope] == 0:
                self.display_most_recent(scope)
        else:
            # if the pressed scope button is the same as the current scope,
            # return to entry mode or pop an element from the recents queue,
            # based on whether the current scope TMCC_ID is 0 or not
            if self._scope_tmcc_ids[scope] == 0:
                self.display_most_recent(scope)
            else:
                # pressing the same scope button again returns to entry mode with current
                # component active
                if self._in_entry_mode:
                    self.ops_mode(update_info=False)
                else:
                    force_entry_mode = True
                    clear_info = False
        # update display
        self.close_popup()
        self.update_component_info()
        # force entry mode if scoped tmcc_id is 0
        if self._scope_tmcc_ids[scope] == 0:
            force_entry_mode = True
        self.rebuild_options()
        num_chars = 4 if self.scope in {CommandScope.ENGINE} else 2
        self.tmcc_id_text.value = f"{self._scope_tmcc_ids[scope]:0{num_chars}d}"
        self.scope_box.show()
        self.scope_keypad(force_entry_mode, clear_info)

    def display_most_recent(self, scope: CommandScope):
        recents = self._recents_queue.get(scope, None)
        if isinstance(recents, UniqueDeque) and len(recents) > 0:
            state = cast(ComponentState, cast(object, recents[0]))
            self._scope_tmcc_ids[scope] = state.tmcc_id

    def rebuild_options(self):
        self.header.clear()
        for option in self.get_options():
            self.header.append(option)
        self.header.select_default()

    def scope_keypad(self, force_entry_mode: bool = False, clear_info: bool = True):
        # if tmcc_id associated with scope is 0, then we are in entry mode;
        # show keypad with appropriate buttons
        tmcc_id = self._scope_tmcc_ids[self.scope]
        if tmcc_id == 0 or force_entry_mode:
            self.entry_mode(clear_info=clear_info)
            self.scope_power_btns()
            if not self.keypad_box.visible:
                self.keypad_box.show()

    def scope_power_btns(self):
        if self.is_engine_or_train:
            self.on_key_cell.show()
            self.off_key_cell.show()
        else:
            self.on_key_cell.hide()
            self.off_key_cell.hide()

    # noinspection PyTypeChecker
    def make_keypad(self, app: App):
        self.keypad_box = keypad_box = Box(
            app,
            border=2,
            align="top",
        )
        self.keypad_keys = keypad_keys = Box(
            keypad_box,
            layout="grid",
            border=0,
            align="top",
        )

        row = 0
        for r, kr in enumerate(ENTRY_LAYOUT):
            for c, label in enumerate(kr):
                if isinstance(label, tuple):
                    image = find_file(label[1])
                    label = label[0]
                else:
                    image = None

                cell, nb = self.make_keypad_button(
                    keypad_keys,
                    label,
                    row,
                    c,
                    size=self.s_22 if label.isdigit() else self.s_24,
                    visible=True,
                    bolded=True,
                    command=self.on_keypress,
                    args=[label],
                    image=image,
                )

                if label == CLEAR_KEY:
                    self.clear_key_cell = cell
                    self.entry_cells.add(cell)
                elif label == ENTER_KEY:
                    self.entry_cells.add(cell)
                    self.enter_key_cell = cell
                elif label == SET_KEY:
                    self.set_key_cell = cell
            row += 1

        # fill in last row; contents depends on scope
        self.on_key_cell, self.on_btn = self.make_keypad_button(
            keypad_keys,
            None,
            row,
            0,
            visible=True,
            bolded=True,
            is_entry=True,
            image=self.turn_on_image,
            command=False,
        )
        self.on_btn.on_press = (self.on_engine_command, ["START_UP_IMMEDIATE"], {"do_ops": True})
        self.on_btn.on_hold = (self.on_engine_command, [["START_UP_DELAYED", "START_UP_IMMEDIATE"]], {"do_ops": True})

        self.off_key_cell, self.off_btn = self.make_keypad_button(
            keypad_keys,
            ENGINE_OFF_KEY,
            row,
            1,
            visible=True,
            bolded=True,
            is_entry=True,
            image=self.turn_off_image,
        )
        self.off_btn.on_press = (self.on_engine_command, ["SHUTDOWN_IMMEDIATE"])
        self.off_btn.on_hold = (self.on_engine_command, [["SHUTDOWN_DELAYED", "SHUTDOWN_IMMEDIATE"]])

        # set button
        self.set_key_cell, self.set_btn = self.make_keypad_button(
            keypad_keys,
            SET_KEY,
            row,
            2,
            size=self.s_16,
            visible=True,
            bolded=True,
            command=self.on_keypress,
            args=[SET_KEY],
            is_entry=True,
        )
        self.set_key_cell = cell = Box(keypad_keys, layout="auto", grid=[2, row])
        self.entry_cells.add(cell)

        # fire route button
        self.fire_route_cell, self.fire_route_btn = self.make_keypad_button(
            keypad_keys,
            FIRE_ROUTE_KEY,
            row,
            1,
            size=self.s_30,
            visible=False,
            is_ops=True,
        )

        # switch button
        self.switch_thru_cell, self.switch_thru_btn = self.make_keypad_button(
            keypad_keys,
            SWITCH_THRU_KEY,
            row,
            0,
            size=self.s_30,
            visible=False,
            is_ops=True,
        )
        self.switch_out_cell, self.switch_out_btn = self.make_keypad_button(
            keypad_keys,
            SWITCH_OUT_KEY,
            row,
            2,
            size=self.s_30,
            visible=False,
            is_ops=True,
        )

        # Sensor Track Buttons
        self.sensor_track_box = cell = TitleBox(app, "Sequence", layout="auto", align="top", visible=False)
        cell.text_size = self.s_10
        self.ops_cells.add(cell)
        self.sensor_track_buttons = bg = ButtonGroup(
            cell,
            align="top",
            options=SENSOR_TRACK_OPTS,
            width=self.emergency_box_width,
            command=self.on_sensor_track_change,
        )
        bg.text_size = self.s_20

        # Make radio buttons larger and add spacing
        indicator_size = int(22 * self._scale_by)
        for widget in bg.tk.winfo_children():
            widget.config(
                font=("TkDefaultFont", self.s_20),
                padx=18,  # Horizontal padding inside each radio button
                pady=6,  # Vertical padding inside each radio button
                anchor="w",
            )
            # Increase the size of the radio button indicator
            widget.tk.eval(f"""
                image create photo radio_unsel_{id(widget)} -width {indicator_size} -height {indicator_size}
                image create photo radio_sel_{id(widget)} -width {indicator_size} -height {indicator_size}
                radio_unsel_{id(widget)} put white -to 0 0 {indicator_size} {indicator_size}
                radio_sel_{id(widget)} put green -to 0 0 {indicator_size} {indicator_size}
            """)
            widget.config(
                image=f"radio_unsel_{id(widget)}",
                selectimage=f"radio_sel_{id(widget)}",
                compound="left",
                indicatoron=False,
            )

        # BPC2/ASC2 Buttons
        self.ac_on_cell, self.ac_on_btn = self.make_keypad_button(
            keypad_keys,
            AC_ON_KEY,
            row,
            0,
            0,
            image=self.turn_on_image,
            visible=False,
            is_ops=True,
            titlebox_text="On",
        )

        self.ac_status_cell, self.ac_status_btn = self.make_keypad_button(
            keypad_keys,
            None,
            row,
            1,
            image=self.power_off_path,
            visible=False,
            is_ops=True,
            titlebox_text="Status",
            command=False,
        )

        self.ac_off_cell, self.ac_off_btn = self.make_keypad_button(
            keypad_keys,
            AC_OFF_KEY,
            row,
            2,
            0,
            image=self.turn_off_image,
            visible=False,
            is_ops=True,
            titlebox_text="Off",
        )

        # Acs2 Momentary Action Button
        self.ac_aux1_cell, self.ac_aux1_btn = self.make_keypad_button(
            keypad_keys,
            AUX1_KEY,
            row - 1,
            0,
            self.s_18,
            visible=False,
            is_ops=True,
            command=False,
        )
        self.ac_aux1_btn.when_left_button_pressed = self.when_pressed
        self.ac_aux1_btn.when_left_button_released = self.when_released

        # --- set minimum size but allow expansion ---
        # --- Enforce minimum keypad size, but allow expansion ---
        num_rows = 5
        num_cols = 3
        min_cell_height = self.button_size + (2 * self.grid_pad_by)
        min_cell_width = self.button_size + (2 * self.grid_pad_by)

        # Allow dynamic expansion if children exceed minsize
        keypad_box.tk.grid_propagate(True)

        # Apply minsize for each row/column
        for r in range(num_rows):
            keypad_box.tk.grid_rowconfigure(r, weight=1, minsize=min_cell_height)

        for c in range(num_cols):
            keypad_box.tk.grid_columnconfigure(c, weight=1, minsize=min_cell_width)

        # (Optional) overall bounding box minimum size
        min_total_height = num_rows * min_cell_height
        min_total_width = num_cols * min_cell_width
        keypad_box.tk.configure(width=min_total_width, height=min_total_height)

    def make_info_box(self, app: App):
        # self.info_box = info_box = Box(app, border=2, align="top")
        self.info_box = info_box = Box(app, layout="left", border=2, align="top")

        # ───────────────────────────────
        # Left: ID box
        # ───────────────────────────────
        self.tmcc_id_box = tmcc_id_box = TitleBox(info_box, f"{self.scope.title} ID", align="left")
        tmcc_id_box.text_size = self.s_12
        self.tmcc_id_text = Text(tmcc_id_box, text="0000", align="left", bold=True, width=5)
        self.tmcc_id_text.text_color = "blue"
        self.tmcc_id_text.text_size = self.s_20

        # ───────────────────────────────
        # Right: Road Name box
        # ───────────────────────────────
        self.name_box = name_box = TitleBox(info_box, "Road Name", align="right")
        name_box.text_size = self.s_12
        self.name_text = Text(name_box, text="", align="top", bold=True, width="fill")
        self.name_text.text_color = "blue"
        self.name_text.text_size = self.s_18
        self.name_text.tk.config(justify="left", anchor="w")
        name_box.tk.pack_propagate(False)  # prevent pack from shrinking

        # ───────────────────────────────
        # Wait until the ID box is actually realized
        # ───────────────────────────────
        def adjust_road_name_box():
            try:
                # Force the ID box to compute geometry first
                tmcc_id_box.tk.update_idletasks()

                # Determine target width from the emergency box
                total_w = self.emergency_box_width or self.emergency_box.tk.winfo_width()
                if total_w is None or total_w <= 1:
                    app.tk.after(50, adjust_road_name_box)
                    return

                # Fix the overall info_box width permanently
                id_h = tmcc_id_box.tk.winfo_height()
                info_box.tk.config(width=total_w, height=id_h + 2)
                info_box.tk.pack_propagate(False)  # <- prevent any child resizing

                # Compute sub-box dimensions but don’t change the overall width later
                id_w = self.tmcc_id_box.tk.winfo_width()
                id_h = self.tmcc_id_box.tk.winfo_height()
                name_box.tk.config(height=id_h, width=max(0, total_w - id_w))
            except tk.TclError as e:
                log.exception(f"[adjust_road_name_box] failed: {e}", exc_info=e)

        # Schedule width/height fix after geometry update
        app.tk.after(10, adjust_road_name_box)

        # add a picture placeholder here, we may not use it
        self.image_box = image_box = Box(app, border=2, align="top")
        self.image = Picture(image_box, align="top")
        self._isd = SwipeDetector(self.image)
        self._isd.on_long_press = self.on_info
        self._isd.on_swipe_right = self.show_previous_component
        self._isd.on_swipe_left = self.show_next_component
        self.image_box.hide()

    def show_next_component(self) -> None:
        recents = self._recents_queue.get(self.scope, None)
        self.close_popup()
        if isinstance(recents, UniqueDeque) and len(recents) > 0:
            current = recents[0]
            state = cast(ComponentState, cast(object, recents.next()))
            recents.append(current)
            self._scope_tmcc_ids[self.scope] = state.tmcc_id
            self.update_component_info(tmcc_id=state.tmcc_id)
            self.header.select_default()

    def show_previous_component(self) -> None:
        self.close_popup()
        recents = self._recents_queue.get(self.scope, None)
        if isinstance(recents, UniqueDeque) and len(recents) > 0:
            state = cast(ComponentState, cast(object, recents.previous()))
            self._scope_tmcc_ids[self.scope] = state.tmcc_id
            self.update_component_info(tmcc_id=state.tmcc_id)
            self.header.select_default()

    def on_sensor_track_change(self) -> None:
        tmcc_id = self._scope_tmcc_ids[self.scope]
        st_seq = IrdaSequence.by_value(int(self.sensor_track_buttons.value))
        IrdaReq(tmcc_id, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=st_seq).send(repeat=self.repeat)

    def make_keypad_button(
        self,
        keypad_box: Box | TitleBox,
        label: str,
        row: int,
        col: int,
        size: int | None = None,
        image: str = None,
        visible: bool = True,
        bolded: bool = True,
        is_ops: bool = False,
        is_entry: bool = False,
        titlebox_text: str = None,
        align: str = "bottom",
        command: Callable | bool | None = None,
        args: list = None,
    ):
        if args is None:
            args = [label]
        if isinstance(command, bool) and not command:
            command = args = None
        elif command is None or (isinstance(command, bool) and command):
            command = (self.on_keypress, args)
        else:  # custom command
            command = (command, args)

        if size is None and label:
            size = self.s_30 if label in FONT_SIZE_EXCEPTIONS else self.s_18

        # ------------------------------------------------------------
        #  Create cell container (either TitleBox or Box)
        # ------------------------------------------------------------
        if titlebox_text:
            cell = TitleBox(
                keypad_box,
                titlebox_text,
                layout="auto",
                align="bottom",
                grid=[col, row],
                visible=True,
            )
            cell.tk.configure(width=self.button_size, height=self.button_size)
            cell.text_size = self.s_10
            button_size = self.titled_button_size
            grid_pad_by = 0
            # Force TitleBox label to top-left
            try:
                lf = cell.tk  # The underlying tk.LabelFrame inside your TitleBox
                lf.configure(labelanchor="nw", padx=0, pady=0)
                lf.update_idletasks()
            except (tk.TclError, AttributeError) as e:
                log.exception(f"Warning adjusting LabelFrame padding: {e}", exc_info=e)
        else:
            cell = Box(keypad_box, layout="auto", grid=[col, row], align=align, visible=True)
            button_size = self.button_size
            grid_pad_by = self.grid_pad_by

        if is_ops:
            self.ops_cells.add(cell)
        if is_entry:
            self.entry_cells.add(cell)

        # ------------------------------------------------------------
        #  Fix cell size (allowing slight flex for TitleBoxes)
        # ------------------------------------------------------------
        if titlebox_text:
            # Force the cell to standard button size
            cell.tk.configure(
                width=self.button_size,
                height=self.button_size,
            )
        else:
            cell.tk.configure(
                width=self.button_size,
                height=self.button_size,
            )
        # don't let push button grow cell size
        cell.tk.pack_propagate(False)

        # ensure the keypad grid expands uniformly and fills the box height
        extra_pad = max(2, grid_pad_by)
        keypad_box.tk.grid_rowconfigure(row, weight=1, minsize=self.button_size + (2 * extra_pad))
        keypad_box.tk.grid_columnconfigure(col, weight=1, minsize=self.button_size + (2 * extra_pad))

        # ------------------------------------------------------------
        #  Create PushButton
        # ------------------------------------------------------------
        nb = HoldButton(
            cell,
            align="bottom",
            args=args,
            hold_threshold=1.0,
            repeat_interval=0.2,
            on_press=command,
        )
        nb.tk.configure(bd=1, relief="solid", highlightthickness=1)

        # ------------------------------------------------------------
        #  Image vs text button behavior
        # ------------------------------------------------------------
        if image:
            nb.image = image
            nb.images = self.get_titled_image(image)
        else:
            # Make tk.Button fill the entire cell and draw full border
            # only do this for text buttons
            nb.text = label
            nb.text_size = size
            nb.text_bold = bolded
            nb.tk.config(compound="center", anchor="center", padx=0, pady=0)
        # ------------------------------------------------------------
        #  Grid spacing & uniform sizing
        # ------------------------------------------------------------
        nb.tk.config(width=button_size, height=button_size)
        nb.tk.config(padx=0, pady=0, borderwidth=1, highlightthickness=1)

        if titlebox_text and image is None and label:
            nb.tk.config(bd=0, borderwidth=0, highlightthickness=0)
            nb.tk.place_configure(x=0, y=0, relwidth=1, relheight=0.73)

        cell.visible = visible
        return cell, nb

    def on_keypress(self, key: str) -> None:
        num_chars = 4 if self.scope in {CommandScope.ENGINE} else 2
        tmcc_id = self.tmcc_id_text.value
        if key.isdigit():
            if int(tmcc_id) and self.reset_on_keystroke:
                self.update_component_info(0)
                tmcc_id = "0" * num_chars
            tmcc_id = tmcc_id[1:] + key
            self.tmcc_id_text.value = tmcc_id
        elif key == CLEAR_KEY:
            self.reset_on_keystroke = False
            tmcc_id = "0" * num_chars
            self.tmcc_id_text.value = tmcc_id
            self.entry_mode()
        elif key == SET_KEY:
            self.reset_on_keystroke = False
            tmcc_id = int(self.tmcc_id_text.value)
            self.on_set_key(self.scope, tmcc_id)
        elif key == ENTER_KEY:
            # if a valid (existing) entry was entered, go to ops mode,
            # otherwise, stay in entry mode
            self.reset_on_keystroke = False
            if self.make_recent(self.scope, int(tmcc_id)):
                self.ops_mode()
            else:
                self.entry_mode(clear_info=False)
        else:
            self.do_command(key)

        # update information immediately if not in entry mode
        if not self._in_entry_mode and key.isdigit():
            log.debug("on_keypress calling update_component_info...")
            self.update_component_info(int(tmcc_id), "")

    def on_set_key(self, scope: CommandScope, tmcc_id: int) -> None:
        # Fire the set address command; only valid for switches, accessories, and engines
        if scope != CommandScope.TRAIN and tmcc_id:
            cmd_enum = SCOPE_TO_SET_ENUM.get(scope, None)
            if isinstance(cmd_enum, CommandDefEnum):
                if scope == CommandScope.ENGINE and tmcc_id > 99:
                    cmd = TMCC2EngineCommandEnum.SET_ADDRESS
                else:
                    cmd = CommandReq.build(cmd_enum, address=tmcc_id, scope=scope)
                cmd.send(repeat=self.repeat)
        else:
            self.entry_mode(clear_info=False)

    def make_recent(self, scope: CommandScope, tmcc_id: int, state: S = None) -> bool:
        self.close_popup()
        log.debug(f"Pushing current: {scope} {tmcc_id} {self.scope} {self.tmcc_id_text.value}")
        self._scope_tmcc_ids[self.scope] = tmcc_id
        if tmcc_id > 0:
            if state is None:
                state = self._state_store.get_state(self.scope, tmcc_id, False)
            if state:
                # add to scope queue
                queue = self._recents_queue.get(self.scope, None)
                if queue is None:
                    queue = UniqueDeque[S](maxlen=self.num_recents)
                    self._recents_queue[self.scope] = queue
                queue.appendleft(state)
                self.rebuild_options()
                return True
        return False

    def do_command(self, key: str) -> None:
        cmd = KEY_TO_COMMAND.get(key, None)
        tmcc_id = self._scope_tmcc_ids[self.scope]
        if cmd:
            # special case HALT cmd
            if key == HALT_KEY:
                cmd.send()
            elif tmcc_id > 0:
                if isinstance(cmd, CommandReq):
                    cmd.scope = self.scope
                    cmd.address = self._scope_tmcc_ids[self.scope]
                    cmd.send(repeat=self.repeat)
                elif cmd == send_lcs_on_command:
                    state = self._state_store.get_state(self.scope, tmcc_id, False)
                    if state:
                        cmd(state)
                elif cmd == send_lcs_off_command:
                    state = self._state_store.get_state(self.scope, tmcc_id, False)
                    if state:
                        cmd(state)
        else:
            print(f"Unknown key: {key}")

    def entry_mode(self, clear_info: bool = True) -> None:
        if clear_info:
            self.update_component_info(0)
        else:
            self.reset_on_keystroke = True
            self.image_box.hide()
        self._in_entry_mode = True
        for cell in self.entry_cells:
            if not cell.visible:
                cell.show()
        for cell in self.ops_cells:
            if cell.visible:
                cell.hide()
        self.scope_power_btns()
        self.scope_set_btn()
        if not self.keypad_box.visible:
            self.keypad_box.show()
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} and self._scope_tmcc_ids[self.scope]:
            self.reset_btn.enable()
        else:
            self.reset_btn.disable()

    def scope_set_btn(self) -> None:
        if self.scope in {CommandScope.ROUTE}:
            self.set_btn.hide()
        else:
            self.set_btn.show()

    def scope_engine_keys(self, btns: set[Widget]):
        self._bell_box.hide()
        self._rr_speed_box.hide()
        for btn in btns:
            btn.show()
        for btn in self._all_engine_btns - btns:
            btn.hide()

    def show_diesel_keys(self) -> None:
        if self._last_engine_type != "d":
            self.scope_engine_keys(self._engine_type_key_map["d"])
            self._last_engine_type = "d"
        self._rr_speed_box.show()
        self.horn_title_box.text = "Horn"

    def show_steam_keys(self) -> None:
        if self._last_engine_type != "s":
            self.scope_engine_keys(self._engine_type_key_map["s"])
            self._last_engine_type = "s"
        self._rr_speed_box.show()
        self.horn_title_box.text = "Whistle"

    def show_passenger_keys(self) -> None:
        if self._last_engine_type != "p":
            self.scope_engine_keys(self._engine_type_key_map["p"])
            self._last_engine_type = "p"

    def show_freight_keys(self) -> None:
        if self._last_engine_type != "f":
            self.scope_engine_keys(self._engine_type_key_map["f"])
            self._last_engine_type = "f"
        self._bell_box.show()
        self.show_horn_control()

    @property
    def is_engine_or_train(self) -> bool:
        return (
            self.scope == CommandScope.ENGINE
            or (self.scope == CommandScope.TRAIN and self.active_state is None)
            or (self.scope == CommandScope.TRAIN and not self.active_state.is_power_district)
        )

    @property
    def is_accessory_or_bpc2(self) -> bool:
        return self.scope == CommandScope.ACC or (
            isinstance(self.active_state, LcsProxyState) and self.active_state.is_power_district
        )

    def ops_mode(self, update_info: bool = True, state: S = None) -> None:
        self._in_entry_mode = False
        for cell in self.entry_cells:
            if cell.visible:
                cell.hide()
        for cell in self.ops_cells:
            if cell.visible:
                cell.hide()
        self.reset_btn.disable()
        if self.is_engine_or_train:
            if not isinstance(state, EngineState):
                self._active_engine_state = state = self._state_store.get_state(
                    self.scope, self._scope_tmcc_ids[self.scope], False
                )
            self.on_new_engine(state, ops_mode_setup=True)
            if self.keypad_box.visible:
                self.keypad_box.hide()
            self.reset_btn.enable()
            # assume it's a diesel
            self.show_diesel_keys()
            if state:  # Display motive-appropriate control keys
                if state.is_steam:
                    self.show_steam_keys()
                elif state.is_passenger:
                    self.show_passenger_keys()
                elif state.is_freight:
                    self.show_freight_keys()
            if not self.controller_box.visible:
                self.controller_box.show()
            if not self.controller_keypad_box.visible:
                self.controller_keypad_box.show()
        elif self.scope == CommandScope.ROUTE:
            self.on_new_route()
            self.fire_route_cell.show()
            if not self.keypad_box.visible:
                self.keypad_box.show()
        elif self.scope == CommandScope.SWITCH:
            self.on_new_switch()
            self.switch_thru_cell.show()
            self.switch_out_cell.show()
            if not self.keypad_box.visible:
                self.keypad_box.show()
        elif self.is_accessory_or_bpc2:
            if state is None:
                state = self.active_state
            self.on_new_accessory(state)
            show_keypad = True
            if state:
                if isinstance(state, AccessoryState) and state.is_sensor_track:
                    self.sensor_track_box.show()
                    self.keypad_box.hide()
                    show_keypad = False
                elif state.is_bpc2 or (isinstance(state, AccessoryState) and state.is_asc2):
                    self.ac_off_cell.show()
                    self.ac_status_cell.show()
                    self.ac_on_cell.show()
                    if isinstance(state, AccessoryState) and state.is_asc2:
                        self.ac_aux1_cell.show()
            if show_keypad and not self.keypad_box.visible:
                self.keypad_box.show()
        if update_info:
            self.update_component_info(in_ops_mode=True)

    def update_component_info(
        self,
        tmcc_id: int = None,
        not_found_value: str = "Not Configured",
        in_ops_mode: bool = False,
    ) -> None:
        self.close_popup()
        if tmcc_id is None:
            tmcc_id = self._scope_tmcc_ids.get(self.scope, 0)
        # update the tmcc_id associated with current scope
        self._scope_tmcc_ids[self.scope] = tmcc_id
        update_button_state = True
        num_chars = 4 if self.scope in {CommandScope.ENGINE} else 2
        if tmcc_id:
            state = self.active_state
            if state:
                # Make sure ID field shows TMCC ID, not just road number
                if tmcc_id != state.tmcc_id or tmcc_id != int(self.tmcc_id_text.value):
                    tmcc_id = state.tmcc_id
                    self._scope_tmcc_ids[self.scope] = tmcc_id
                    self.tmcc_id_text.value = f"{tmcc_id:0{num_chars}d}"
                name = state.name
                name = name if name and name != "NA" else not_found_value
                update_button_state = False
                # noinspection PyTypeChecker
                self.make_recent(self.scope, tmcc_id, state)
                if not in_ops_mode:
                    self.ops_mode(update_info=False)
            else:
                name = not_found_value
            self.name_text.value = name
        else:
            if self.reset_on_keystroke:
                self._scope_tmcc_ids[self.scope] = 0
                self.reset_on_keystroke = False
            self.tmcc_id_text.value = f"{tmcc_id:0{num_chars}d}"
            self.name_text.value = ""
            state = None
            self.clear_image()
        self.monitor_state()
        # use the callback to update ops button state
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ACC}:
            if update_button_state:
                # noinspection PyTypeChecker
                self._scoped_callbacks.get(self.scope, lambda s: print(f"from uci: {s}"))(state)
            self.update_component_image(tmcc_id)
        else:
            self.image_box.hide()

    def clear_image(self):
        self.image.image = None
        self.image_box.hide()

    def update_component_image(
        self,
        tmcc_id: int = None,
        key: tuple[CommandScope, int] | tuple[CommandScope, int, int] = None,
    ) -> None:
        if key is None and self.scope in {CommandScope.SWITCH, CommandScope.ROUTE}:
            # routes and switches don't use images
            return
        if key:
            scope = key[0]
            tmcc_id = key[1]
            train_id = key[2] if len(key) > 2 else None
        else:
            scope = self.scope
            if tmcc_id is None:
                tmcc_id = self._scope_tmcc_ids[self.scope]
            train_id = None
        img = None

        # for Trains, use the image of the lead engine
        if scope == CommandScope.TRAIN and self.active_state and not self.active_state.is_power_district and tmcc_id:
            img = self._image_cache.get((CommandScope.TRAIN, tmcc_id), None)
            if img is None:
                train_state = self.active_state
                train_id = tmcc_id
                head_id = train_state.head_tmcc_id
                img = self._image_cache.get((CommandScope.ENGINE, head_id), None)
                if img is None:
                    self.update_component_image(key=(CommandScope.ENGINE, head_id, train_id))
                    return
                else:
                    self._image_cache[(CommandScope.TRAIN, train_id)] = img
        elif scope in {CommandScope.ENGINE} and tmcc_id != 0:
            with self._cv:
                state = self._state_store.get_state(scope, tmcc_id, False)
                prod_info = self._prod_info_cache.get(tmcc_id, None)

                # If not cached or not a valid Future/ProdInfo, start a background fetch
                if prod_info is None and state and state.bt_id:
                    if (scope, tmcc_id) not in self._pending_prod_infos:
                        # Submit fetch immediately and cache the Future itself
                        future = self._executor.submit(self._fetch_prod_info, scope, tmcc_id, train_id)
                        self._prod_info_cache[tmcc_id] = future
                    return

                if isinstance(prod_info, Future) and prod_info.done() and isinstance(prod_info.result(), ProdInfo):
                    prod_info = self._prod_info_cache[tmcc_id] = prod_info.result()
                    self._pending_prod_infos.discard((scope, tmcc_id))

                if isinstance(prod_info, ProdInfo):
                    # Image should have been cached by fetch_prod_indo
                    img = self._image_cache.get((CommandScope.ENGINE, tmcc_id), None)
                    if img is None:
                        img = self.get_scaled_image(BytesIO(prod_info.image_content))
                        self._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                    if train_id:
                        self._image_cache[(CommandScope.TRAIN, train_id)] = img
                        tmcc_id = train_id
                        scope = CommandScope.TRAIN
                else:
                    if isinstance(state, EngineState):
                        img = self._image_cache.get((CommandScope.ENGINE, tmcc_id), None)
                        if img is None:
                            source = ENGINE_TYPE_TO_IMAGE.get(
                                state.engine_type_enum, ENGINE_TYPE_TO_IMAGE[EngineType.DIESEL]
                            )
                            img = self._image_cache.get(source, None)
                            if img is None:
                                img = self.get_scaled_image(source, force_lionel=True)
                                img = center_text_on_image(img, state.engine_type_enum.label(), styled=True)
                                self._image_cache[source] = img
                                self._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                                self._image_cache[source] = img
                            self._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                            if train_id:
                                self._image_cache[(CommandScope.ENGINE, train_id)] = img
                                tmcc_id = train_id
                                scope = CommandScope.TRAIN
                    else:
                        self.clear_image()
        elif self.scope in {CommandScope.ACC, CommandScope.TRAIN} and tmcc_id != 0:
            state = self._state_store.get_state(self.scope, tmcc_id, False)
            if state:
                img = self._image_cache.get((self.scope, tmcc_id), None)
                if img is None:
                    if isinstance(state, AccessoryState) and state.is_asc2:
                        img = self.get_image(self.asc2_image, inverse=False, scale=True, preserve_height=True)
                    elif state.is_bpc2:
                        img = self.get_image(self.bpc2_image, inverse=False, scale=True, preserve_height=True)
                    elif isinstance(state, AccessoryState) and state.is_amc2:
                        img = self.get_image(self.amc2_image, inverse=False, scale=True, preserve_height=True)
                    elif isinstance(state, AccessoryState) and state.is_sensor_track:
                        img = self.get_scaled_image(self.sensor_track_image, force_lionel=True)
                    if img:
                        self._image_cache[(self.scope, tmcc_id)] = img
                    else:
                        self.clear_image()
        if img is None:
            self.clear_image()
        if img and scope == self.scope and tmcc_id == self._scope_tmcc_ids[self.scope]:
            available_height, available_width = self.calc_image_box_size()
            self.image_box.tk.config(width=available_width, height=available_height)
            self.image.tk.config(image=img)
            self.image_box.show()

    def calc_image_box_size(self) -> tuple[int, int | Any]:
        # force geometry layout
        self.app.tk.update_idletasks()

        # Get the heights of fixed elements
        if self.header not in self.size_cache:
            _, header_height = self.size_cache[self.header] = (
                self.header.tk.winfo_reqwidth(),
                self.header.tk.winfo_reqheight(),
            )
        else:
            _, header_height = self.size_cache[self.header]

        if self.emergency_box not in self.size_cache:
            emergency_width, emergency_height = self.size_cache[self.emergency_box] = (
                self.emergency_box.tk.winfo_reqwidth(),
                self.emergency_box_height or self.emergency_box.tk.winfo_reqheight(),
            )
        else:
            emergency_width, emergency_height = self.size_cache[self.emergency_box]

        if self.info_box not in self.size_cache:
            _, info_height = self.size_cache[self.info_box] = (
                self.info_box.tk.winfo_reqwidth(),
                self.info_box.tk.winfo_reqheight(),
            )
        else:
            _, info_height = self.size_cache[self.info_box]

        if self.scope_box not in self.size_cache:
            _, scope_height = self.size_cache[self.scope_box] = (
                self.scope_box.tk.winfo_reqwidth(),
                self.scope_box.tk.winfo_reqheight(),
            )
        else:
            _, scope_height = self.size_cache[self.scope_box]

        if self.keypad_box.visible:
            if self.keypad_box not in self.size_cache:
                _, keypad_height = self.size_cache[self.keypad_box] = (
                    self.keypad_box.tk.winfo_reqwidth(),
                    self.keypad_box.tk.winfo_reqheight(),
                )
            else:
                _, keypad_height = self.size_cache[self.keypad_box]
            variable_content = keypad_height
        elif self.controller_box.visible:
            if self.controller_box not in self.size_cache:
                _, controller_height = self.size_cache[self.controller_box] = (
                    self.controller_box.tk.winfo_reqwidth(),
                    self.controller_box.tk.winfo_reqheight(),
                )
            else:
                _, controller_height = self.size_cache[self.controller_box]
            variable_content = controller_height
        elif self.sensor_track_box.visible:
            if self.sensor_track_box not in self.size_cache:
                _, sensor_height = self.size_cache[self.sensor_track_box] = (
                    self.sensor_track_box.tk.winfo_reqwidth(),
                    self.sensor_track_box.tk.winfo_reqheight(),
                )
            else:
                _, sensor_height = self.size_cache[self.sensor_track_box]
            variable_content = sensor_height
        else:
            variable_content = 0
            if self.avail_image_height is None:
                print("*********** No Variable Content *******")

        # Calculate remaining vertical space
        if self.avail_image_height is None:
            avail_image_height = (
                self.height - header_height - emergency_height - info_height - variable_content - scope_height - 20
            )
            self.avail_image_height = avail_image_height
        else:
            avail_image_height = self.avail_image_height

        if self.avail_image_width is None:
            # use width of emergency height box as standard
            self.avail_image_width = avail_image_width = emergency_width
        else:
            avail_image_width = self.avail_image_width
        return avail_image_height, avail_image_width

    def sizeof(self, widget: Widget) -> tuple[int, int]:
        return self.size_cache.get(widget, None) or (widget.tk.winfo_reqwidth(), widget.tk.winfo_reqheight())

    def make_emergency_buttons(self, app: App):
        self.emergency_box = emergency_box = Box(app, layout="grid", border=2, align="top")
        _ = Text(emergency_box, text=" ", grid=[0, 0, 3, 1], align="top", size=2, height=1, bold=True)

        self.halt_btn = HoldButton(
            emergency_box,
            text=HALT_KEY,
            grid=[0, 1],
            align="top",
            width=11,
            padx=self._text_pad_x,
            pady=self._text_pad_y,
            bg="red",
            text_bold=True,
            text_size=self.s_20,
            command=self.on_keypress,
            args=[HALT_KEY],
        )

        _ = Text(emergency_box, text=" ", grid=[1, 1], align="top", size=6, height=1, bold=True)

        self.reset_btn = HoldButton(
            emergency_box,
            text="Reset",
            grid=[2, 1],
            align="top",
            width=11,
            padx=self._text_pad_x,
            pady=self._text_pad_y,
            bg="gray",
            text_size=self.s_20,
            text_color="black",
            text_bold=True,
            enabled=False,
            on_press=(self.on_engine_command, ["RESET"]),
            on_repeat=(self.on_engine_command, ["RESET"]),
            repeat_interval=0.2,
        )

        _ = Text(emergency_box, text=" ", grid=[0, 2, 3, 1], align="top", size=2, height=1, bold=True)
        self.app.tk.update_idletasks()
        self.emergency_box_width = emergency_box.tk.winfo_width()
        self.emergency_box_height = emergency_box.tk.winfo_height()

    def on_speed_command(self, speed_req: str | int) -> None:
        state = self.active_engine_state
        if isinstance(speed_req, str):
            speed = speed_req.split(", ")
            do_dialog = isinstance(speed, list) and len(speed) > 1
            speed = (speed[-1] if isinstance(speed, list) else speed).replace("SPEED_", "")
            if state and state.is_legacy:
                rr_speed = TMCC2RRSpeedsEnum.by_name(speed)
            else:
                rr_speed = TMCC1RRSpeedsEnum.by_name(speed)
            if rr_speed is None and speed == "EMERGENCY_STOP":
                # dispatch directly to on_engine_command for processing
                if state:
                    state.is_ramping = False
                self.on_engine_command(speed_req)
                return
        else:
            do_dialog = False
            rr_speed = speed_req

        if state:
            if do_dialog:
                req = RampedSpeedDialogReq(state.tmcc_id, rr_speed, state.scope)
            else:
                req = RampedSpeedReq(state.tmcc_id, rr_speed, state.scope)
        else:
            tmcc_id = self._scope_tmcc_ids[self.scope]
            req = CommandReq(TMCC1EngineCommandEnum.ABSOLUTE_SPEED, tmcc_id, scope=self.scope, data=rr_speed)

        # dispatch command
        req.send()

    def on_engine_command(
        self,
        targets: str | list[str] | CommandReq,
        data: int = 0,
        repeat: int = None,
        delay: float = 0.0,
        do_ops: bool = False,
        do_entry: bool = False,
    ) -> None:
        """
        Send commands to a TMCC or Legacy Engine or Train.

        To allow for command differences between TMCC and Legacy engines, commands can be sent in as
        lists, with each element being tried in order, until one is found that is appropriate for the
        engine generation.

        TODO: allow for command sequences
        """
        repeat = repeat if repeat else self.repeat
        scope = self.scope
        tmcc_id = self._scope_tmcc_ids[scope]
        if tmcc_id == 0:
            tmcc_id = int(self.tmcc_id_text.value)
            self._scope_tmcc_ids[scope] = tmcc_id
        if scope in {CommandScope.ENGINE, CommandScope.TRAIN} and tmcc_id:
            state = self._state_store.get_state(scope, tmcc_id, False)
            if isinstance(targets, str):
                for ix, target in enumerate(targets.split(",")):
                    target = target.strip()
                    delay = 0.100 if ix else 0.0
                    self.do_engine_command(tmcc_id, target, data, scope, do_entry, do_ops, repeat, state, delay)
            else:
                self.do_engine_command(tmcc_id, targets, data, scope, do_entry, do_ops, repeat, state, delay)

    def do_engine_command(
        self,
        tmcc_id: int | Any,
        targets: str | list[str] | tuple[str],
        data: int,
        scope: CommandScope,
        do_entry: bool,
        do_ops: bool,
        repeat: int,
        state: S,
        delay: float = 0.0,
    ) -> bool:
        sent_command = False
        if isinstance(targets, str):
            targets = [targets]
        for target in targets:
            if state and state.is_legacy:
                # there are a few special cases
                if target in {SMOKE_ON, SMOKE_OFF}:
                    cmd_enum = self.get_tmcc2_smoke_cmd(target, state)
                else:
                    cmd_enum = TMCC2EngineOpsEnum.look_up(target)
                    if cmd_enum is None:
                        cmd_enum = SequenceCommandEnum.by_name(target)
            else:
                cmd_enum = TMCC1EngineCommandEnum.by_name(target)
            if cmd_enum:
                cmd = CommandReq.build(cmd_enum, tmcc_id, data, scope)
                repeat = REPEAT_EXCEPTIONS.get(cmd_enum, repeat)
                cmd.send(repeat=repeat, delay=delay)
                if do_ops is True and self._in_entry_mode is True:
                    self.ops_mode(update_info=True)
                elif do_entry and self._in_entry_mode is False:
                    self.entry_mode(clear_info=False)
                sent_command = True
                break
            else:
                target = COMMAND_FALLBACKS.get(target, None)
                if target:
                    if self.do_engine_command(tmcc_id, target, data, scope, do_entry, do_ops, repeat, state, delay):
                        sent_command = True
                        break
        return sent_command

    @staticmethod
    def get_tmcc2_smoke_cmd(cmd: str, state: EngineState) -> TMCC2EngineOpsEnum | None:
        cur_smoke = state.smoke_level
        if cmd == SMOKE_ON:  # increase smoke
            if cur_smoke == TMCC2EffectsControl.SMOKE_OFF:
                return TMCC2EffectsControl.SMOKE_LOW
            elif cur_smoke == TMCC2EffectsControl.SMOKE_LOW:
                return TMCC2EffectsControl.SMOKE_MEDIUM
            elif cur_smoke == TMCC2EffectsControl.SMOKE_MEDIUM:
                return TMCC2EffectsControl.SMOKE_HIGH
        elif cmd == SMOKE_OFF:  # decrease smoke
            if cur_smoke == TMCC2EffectsControl.SMOKE_LOW:
                return TMCC2EffectsControl.SMOKE_OFF
            elif cur_smoke == TMCC2EffectsControl.SMOKE_MEDIUM:
                return TMCC2EffectsControl.SMOKE_LOW
            elif cur_smoke == TMCC2EffectsControl.SMOKE_HIGH:
                return TMCC2EffectsControl.SMOKE_MEDIUM
        return None

    def scale(self, value: int, factor: float = None) -> int:
        orig_value = value
        value = max(orig_value, int(value * self.width / 480))
        if factor is not None and self.width > 480:
            value = max(orig_value, int(factor * value))
        return value

    def when_pressed(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            scope = self.scope
            tmcc_id = self._scope_tmcc_ids[scope]
            state = self._state_store.get_state(scope, tmcc_id, False)
            if isinstance(state, AccessoryState) and state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1).send()

    def when_released(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            scope = self.scope
            tmcc_id = self._scope_tmcc_ids[scope]
            state = self._state_store.get_state(scope, tmcc_id, False)
            if isinstance(state, AccessoryState) and state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).send()

    def request_prod_info(self, scope: CommandScope, tmcc_id: int | None) -> ProdInfo | None:
        prod_info = "N/A"
        state = self._state_store.get_state(scope, tmcc_id, False)
        if state and state.bt_id:
            try:
                prod_info = ProdInfo.by_btid(state.bt_id)
            except ValueError as ve:
                log.info(f"Product info for engine {state.address} ({state.bt_id}) is unavailable: {ve}")
        return prod_info

    def _fetch_prod_info(self, scope: CommandScope, tmcc_id: int, train_id: int = None) -> ProdInfo | None:
        """Fetch product info in a background thread, then schedule UI update."""
        prod_info = None
        key = (scope, tmcc_id, train_id)
        do_request_prod_info = False
        with self._cv:
            if key not in self._pending_prod_infos:
                self._pending_prod_infos.add(key)
                do_request_prod_info = True  # don't hold lock for long
        if do_request_prod_info:
            prod_info = self.request_prod_info(scope, tmcc_id)
            self._prod_info_cache[tmcc_id] = prod_info
            self._pending_prod_infos.discard((scope, tmcc_id))
            # now get image
            if isinstance(prod_info, ProdInfo):
                img = self.get_scaled_image(BytesIO(prod_info.image_content))
                self._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                if train_id:
                    self._image_cache[(CommandScope.TRAIN, train_id)] = img
        # Schedule the UI update on the main thread
        self.queue_message(self.update_component_image, tmcc_id, key)
        return prod_info

    def get_scaled_image(
        self,
        source: str | io.BytesIO,
        preserve_height: bool = False,
        force_lionel: bool = False,
    ) -> ImageTk.PhotoImage:
        pil_img = Image.open(source)
        orig_width, orig_height = pil_img.size
        scaled_width, scaled_height = self._calc_scaled_image_size(
            orig_width, orig_height, preserve_height, force_lionel
        )
        img = ImageTk.PhotoImage(pil_img.resize((scaled_width, scaled_height)))
        return img

    def _calc_scaled_image_size(
        self,
        orig_width: int,
        orig_height: int,
        preserve_height: bool = False,
        force_lionel: bool = False,
    ) -> tuple[int, int]:
        available_height, available_width = self.calc_image_box_size()
        if force_lionel:
            scaled_width, scaled_height = self._calc_scaled_image_size(300, 100)
        else:
            # Calculate scaling to fit available space
            width_scale = available_width / orig_width
            height_scale = available_height / orig_height
            scale = min(width_scale, height_scale)
            if preserve_height:
                scaled_width = int(orig_width * scale)
                scaled_height = int(orig_height * height_scale)
            else:
                scaled_width = int(orig_width * width_scale)
                scaled_height = int(orig_height * scale)
        return scaled_width, scaled_height

    # Example lazy loader pattern for images
    def get_image(
        self,
        path,
        size=None,
        inverse: bool = True,
        scale: bool = False,
        preserve_height: bool = False,
    ):
        if path not in self._image_cache:
            img = None
            if scale:
                normal_tk = self.get_scaled_image(path, preserve_height=preserve_height)
            else:
                img = Image.open(path)
                if size:
                    img = img.resize(size)
                normal_tk = ImageTk.PhotoImage(img)
            if inverse and img:
                inverted = ImageOps.invert(img.convert("RGB"))
                inverted.putalpha(img.split()[-1])
                inverted_tk = ImageTk.PhotoImage(inverted)
                self._image_cache[path] = (normal_tk, inverted_tk)
            else:
                self._image_cache[path] = normal_tk
        return self._image_cache[path]

    def get_titled_image(self, path):
        return self.get_image(path, size=(self.titled_button_size, self.titled_button_size))
