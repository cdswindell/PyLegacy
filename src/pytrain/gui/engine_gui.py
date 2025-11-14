#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from __future__ import annotations

import atexit
import io
import logging
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
from PIL import Image, ImageTk

from ..comm.command_listener import CommandDispatcher
from ..db.accessory_state import AccessoryState
from ..db.base_state import BaseState
from ..db.component_state import ComponentState, RouteState, SwitchState
from ..db.component_state_store import ComponentStateStore
from ..db.engine_state import EngineState
from ..db.irda_state import IrdaState
from ..db.prod_info import ProdInfo
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..pdi.asc2_req import Asc2Req
from ..pdi.bpc2_req import Bpc2Req
from ..pdi.constants import Asc2Action, Bpc2Action, IrdaAction, PdiCommand
from ..pdi.irda_req import IrdaReq, IrdaSequence
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum, TMCC1HaltCommandEnum, TMCC1SwitchCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2EngineOpsEnum, TMCC2RouteCommandEnum
from ..utils.path_utils import find_file
from ..utils.unique_deque import UniqueDeque
from .hold_button import HoldButton

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)


HALT_KEY = ">> Halt <<"
SWITCH_THRU_KEY = "↑"
SWITCH_OUT_KEY = "↖↗"
FIRE_ROUTE_KEY = "⚡"
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
SMOKE_ON = "SMOKE ON"
SMOKE_OFF = "SMOKE OFF"
BELL_KEY = "\U0001f514"
FWD_KEY = "Fwd"
REV_KEY = "Rev"
MOM_TB = "MOM_TB"

ENTRY_LAYOUT = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    [(CLEAR_KEY, "delete-key.jpg"), "0", ENTER_KEY],
]

ENGINE_OPS_LAYOUT = [
    [
        ("VOLUME_UP", "vol-up.jpg"),
        ("ENGINEER_CHATTER", "walkie_talkie.png"),
        ("RPM_UP", "rpm-up.jpg"),
        ("BLOW_HORN_ONE", "horn.jpg"),
    ],
    [
        ("VOLUME_DOWN", "vol-down.jpg"),
        ("TOWER_CHATTER", "tower.png"),
        ("RPM_DOWN", "rpm-down.jpg"),
        ("RING_BELL", "bell.jpg"),
    ],
    [
        ("FRONT_COUPLER", "front-coupler.jpg"),
        (SMOKE_ON, "smoke-up.jpg"),
        ("BOOST_SPEED", "boost.jpg"),
        ("FORWARD_DIRECTION", "", FWD_KEY),
    ],
    [
        ("REAR_COUPLER", "rear-coupler.jpg"),
        (SMOKE_OFF, "smoke-down.jpg"),
        ("BRAKE_SPEED", "brake.jpg"),
        ("REVERSE_DIRECTION", "", REV_KEY),
    ],
    [
        ("AUX1_OPTION_ONE", "", AUX1_KEY),
        ("AUX2_OPTION_ONE", "", AUX2_KEY, "Lights"),
        ("AUX3_OPTION_ONE", "", AUX3_KEY),
        (MOM_TB, "", "Mo"),
    ],
]

REPEAT_EXCEPTIONS = {
    TMCC2EngineCommandEnum.AUX2_OPTION_ONE: 1,
}

FONT_SIZE_EXCEPTIONS = {}

SENSOR_TRACK_OPTS = [
    ["No Action", 0],
    ["Sound Horn R➟L/None L➟R", 1],
    ["None R➟L/Sound Horn L➟R", 2],
    ["10sec Bell R➟L/None L➟R", 3],
    ["None L➟R/10sec Bell L➟R", 4],
    ["Begin Run R➟L/End Run L➟R", 5],
    ["End Run R➟L/Begin Run L➟R", 6],
    ["Go Slow R➟L/Go Normal L➟R", 7],
    ["Go Normal R➟L/Go Slow L➟R", 8],
    ["Recorded Sequence", 9],
]


LIONEL_ORANGE = "#FF6600"


def send_lcs_command(state: AccessoryState, value) -> None:
    if state.is_bpc2:
        Bpc2Req(
            state.tmcc_id,
            PdiCommand.BPC2_SET,
            Bpc2Action.CONTROL3,
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
        initial_tmcc_id: int = None,
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
        self.s_12: int = int(round(12 * scale_by))
        self.s_10: int = int(round(10 * scale_by))
        self.s_8: int = int(round(8 * scale_by))
        self.button_size = int(round(self.width / 6))
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
        self._pending_prod_infos = set()
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._message_queue = Queue()
        self.scope = initial_scope
        self.initial_tmcc_id = initial_tmcc_id
        self.active_engine_state = None

        # various boxes
        self.emergency_box = self.info_box = self.keypad_box = self.scope_box = self.name_box = self.image_box = None
        self.controller_box = self.controller_keypad_box = self.controller_throttle_box = None
        self.emergency_box_width = self.emergency_box_height = None

        # various buttons
        self.halt_btn = self.reset_btn = self.off_btn = self.on_btn = self.set_btn = None
        self.fire_route_btn = self.switch_thru_btn = self.switch_out_btn = self.keypad_keys = None

        # various fields
        self.tmcc_id_box = self.tmcc_id_text = self._nbi = self.header = None
        self.name_text = None
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
        self.controller_box = self.controller_keypad_box = self.throttle_box = None
        self.brake_box = self.brake_level = self.focus_widget = None
        self.throttle = self.speed = self.brake = self._rr_speed_btn = None
        self.momentum_box = self.momentum_level = self.momentum = None

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

        app.repeat(20, _poll_shutdown)

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

        if self.initial_tmcc_id:
            app.after(50, self.update_component_info, [self.initial_tmcc_id])

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
        self.controller_box = controller_box = Box(
            app,
            border=2,
            align="top",
            visible=True,
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
            for c, op in enumerate(kr):
                if op is None:
                    continue
                image = label = title_text = None
                if isinstance(op, tuple):
                    if len(op) > 1 and op[1]:
                        image = find_file(op[1])
                    if len(op) > 2 and op[2]:
                        label = str(op[2])
                    if len(op) > 3 and op[3]:
                        title_text = str(op[3])
                    op = op[0]

                cell, nb = self.make_keypad_button(
                    keypad_keys,
                    label,
                    row,
                    c,
                    visible=True,
                    bolded=True,
                    command=self.on_engine_command,
                    args=[op],
                    image=image,
                    titlebox_text=title_text,
                )
                if op in self.engine_ops_cells:
                    print(f"Duplicate engine op: {op}")
                self.engine_ops_cells[op] = (cell, nb)
            row += 1

        # Postprocess some buttons
        _, btn = self.engine_ops_cells[MOM_TB]
        btn.update_command(self.toggle_momentum_train_brake, [btn])

        # set some repeating commands
        for command in ["BOOST_SPEED", "BRAKE_SPEED"]:
            _, btn = self.engine_ops_cells[command]
            btn.on_repeat = btn.on_press
            btn.on_press = None
            btn.hold_threshold = 0.2

        # used to make sure brake and throttle get focus when needed
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
            height=self.button_size * 4,
        )
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
            sliderlength=int((self.button_size * 4) / 6),
        )
        throttle.tk.bind("<Button-1>", lambda e: throttle.tk.focus_set())
        throttle.tk.bind("<ButtonRelease-1>", self.clear_focus, add="+")
        throttle.tk.bind("<ButtonRelease>", self.clear_focus, add="+")

        # brake
        self.brake_box = brake_box = Box(
            sliders,
            border=1,
            grid=[0, 0],
        )

        cell = TitleBox(brake_box, "Brake", align="top", border=1)
        cell.text_size = self.s_10
        self.brake_level = brake_level = Text(
            cell,
            text="00",
            color="black",
            align="top",
            bold=True,
            size=self.s_18,
            width=3,
            font="DigitalDream",
        )
        brake_level.bg = "black"
        brake_level.text_color = "white"

        self.brake = brake = Slider(
            brake_box,
            align="top",
            horizontal=False,
            step=1,
            width=int(self.button_size / 3),
            height=self.button_size * 4,
            command=self.on_train_brake,
        )
        brake.text_color = "black"
        brake.tk.config(
            from_=0,
            to=7,
            takefocus=0,
            troughcolor="#003366",  # deep Lionel blue for the track,
            activebackground=LIONEL_ORANGE,  # bright Lionel orange for the handle
            bg="lightgrey",  # darker navy background
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,  # subtle orange outline
            width=int(self.button_size / 3),
            sliderlength=int((self.button_size * 4) / 6),
        )
        brake.tk.bind("<Button-1>", lambda e: brake.tk.focus_set())
        brake.tk.bind("<ButtonRelease-1>", self.clear_focus, add="+")
        brake.tk.bind("<ButtonRelease>", self.clear_focus, add="+")

        # Allow Tk to compute geometry
        self.app.tk.update_idletasks()

        self.momentum_box = momentum_box = Box(
            sliders,
            border=1,
            grid=[0, 0],
            visible=False,
        )

        cell = TitleBox(momentum_box, "Moment", align="top", border=1)
        cell.text_size = self.s_10
        self.momentum_level = momentum_level = Text(
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

        self.momentum = momentum = Slider(
            momentum_box,
            align="top",
            horizontal=False,
            step=1,
            width=int(self.button_size / 3),
            height=self.button_size * 4,
            command=self.on_momentum,
        )
        momentum.text_color = "black"
        momentum.tk.config(
            from_=0,
            to=7,
            takefocus=0,
            troughcolor="#003366",  # deep Lionel blue for the track,
            activebackground=LIONEL_ORANGE,  # bright Lionel orange for the handle
            bg="lightgrey",  # darker navy background
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,  # subtle orange outline
            width=int(self.button_size / 3),
            sliderlength=int((self.button_size * 4) / 6),
        )
        momentum.tk.bind("<Button-1>", lambda e: momentum.tk.focus_set())
        momentum.tk.bind("<ButtonRelease-1>", self.clear_focus, add="+")
        momentum.tk.bind("<ButtonRelease>", self.clear_focus, add="+")

        # compute rr speed button size
        w = sliders.tk.winfo_width()
        h = (5 * self.button_size) - (brake.tk.winfo_height() + brake_level.tk.winfo_height())

        # RR Speeds button
        rr_box = Box(
            sliders,
            grid=[0, 1, 2, 1],  # spans two columns under sliders
            align="top",
        )

        # RR Speeds button
        self._rr_speed_btn = rr_btn = HoldButton(rr_box, "")
        rr_btn.tk.pack(fill="both", expand=True)

        img = self.get_image(find_file("RR-Speeds.jpg"), size=(w, h))
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

        # --- HIDE IT AGAIN after sizing is complete ---
        self.controller_box.visible = False

    def toggle_momentum_train_brake(self, btn: PushButton) -> None:
        print(btn)
        if btn.text == "Mo":
            btn.text = "Train\nBrake"
            btn.text_size = self.s_16
            self.brake_box.visible = False
            self.momentum_box.visible = True

        else:
            btn.text = "Mo"
            btn.text_size = self.s_18
            self.momentum_box.visible = False
            self.brake_box.visible = True

    # noinspection PyUnusedLocal
    def clear_focus(self, e=None):
        """
        Touchscreen-safe focus clearing for throttle slider.
        Ensures focus moves off the Scale after finger release
        and forces a redraw so the grab handle deactivates.
        """
        if self.app.tk.focus_get() in {self.throttle.tk, self.brake.tk, self.momentum.tk}:
            self.app.tk.after_idle(self._do_clear_focus)

    def _do_clear_focus(self):
        self.focus_widget.focus_set()
        self.throttle.tk.event_generate("<Leave>")
        self.brake.tk.event_generate("<Leave>")
        self.momentum.tk.event_generate("<Leave>")

    def on_train_brake(self, value):
        if self.app.tk.focus_get() == self.brake.tk:
            value = int(value)
            self.brake_level.value = f"{value:02d}"
            self.on_engine_command("TRAIN_BRAKE", data=value)

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
    def active_state(self) -> S:
        return self._state_store.get_state(self.scope, self._scope_tmcc_ids[self.scope], False)

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
        print(f"on_new_engine: {state}")
        self.active_engine_state = state
        if state:
            # only set throttle/brake/momentum value if we are not in the middle of setting it
            self.speed.value = f"{state.speed:03d}"
            if self.throttle.tk.focus_displayof() != self.throttle.tk:
                self.throttle.value = state.speed

            self.brake_level.value = f"{state.train_brake:02d}"
            if self.brake.tk.focus_displayof() != self.brake.tk:
                self.brake.value = state.train_brake

            self.momentum_level.value = f"{state.momentum:02d}"
            if self.momentum.tk.focus_displayof() != self.momentum.tk:
                self.momentum.value = state.momentum

            _, btn = self.engine_ops_cells["FORWARD_DIRECTION"]
            btn.bg = self._active_bg if state.is_forward else self._inactive_bg
            _, btn = self.engine_ops_cells["REVERSE_DIRECTION"]
            btn.bg = self._active_bg if state.is_reverse else self._inactive_bg

        if state is None or state.is_legacy:
            self.throttle.tk.config(from_=195, to=0)
        else:
            self.throttle.tk.config(from_=31, to=0)

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

    def on_new_accessory(self, state: AccessoryState = None):
        tmcc_id = self._scope_tmcc_ids[CommandScope.ACC]
        if state is None:
            tmcc_id = self._scope_tmcc_ids[CommandScope.ACC]
            state = self._state_store.get_state(CommandScope.ACC, tmcc_id, False) if 1 <= tmcc_id < 99 else None
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

    def update_ac_status(self, state: AccessoryState):
        power_on_image = self.get_titled_image(self.power_on_path)
        power_off_image = self.get_titled_image(self.power_off_path)
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
        for i, scope_abbrev in enumerate(["ACC", "SW", "RTE", "TR", "ENG"]):
            scope = CommandScope.by_prefix(scope_abbrev)
            # Create a PhotoImage to enforce button size
            img = tk.PhotoImage(width=self.scope_size, height=button_height)
            self._btn_images.append(img)
            pb = PushButton(
                scope_box,
                text=scope_abbrev,
                grid=[i, 1],
                align="top",
                height=1,
                command=self.on_scope,
                args=[scope],
            )
            pb.scope = scope
            pb.text_size = self.s_18
            pb.text_bold = True
            # Configure the button with the image as background
            pb.tk.config(image=img, compound="center")
            pb.tk.config(width=self.scope_size, height=button_height)
            pb.tk.config(padx=0, pady=0)
            # Make the grid column expand to fill space
            scope_box.tk.grid_columnconfigure(i, weight=1)
            # associate the button with its scope
            self._scope_buttons[scope] = pb
            # don't overwrite initial tmcc id, if one specified
            if scope not in self._scope_tmcc_ids:
                self._scope_tmcc_ids[scope] = 0
        # highlight initial button
        self.on_scope(self.scope)

    # noinspection PyTypeChecker
    def on_scope(self, scope: CommandScope) -> None:
        print(f"On Scope: {scope}")
        self.scope_box.hide()
        force_entry_mode = False
        clear_info = True
        for k, v in self._scope_buttons.items():
            if k == scope:
                v.bg = self._enabled_bg
            else:
                v.bg = self._disabled_bg
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
                force_entry_mode = True
                clear_info = False
        # update display
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
        print(f"Scope Keypad: force={force_entry_mode}")
        # if tmcc_id associated with scope is 0, then we are in entry mode;
        # show keypad with appropriate buttons
        tmcc_id = self._scope_tmcc_ids[self.scope]
        if tmcc_id == 0 or force_entry_mode:
            self.entry_mode(clear_info=clear_info)
            if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                self.on_key_cell.show()
                self.off_key_cell.show()
            else:
                self.on_key_cell.hide()
                self.off_key_cell.hide()
            if not self.keypad_box.visible:
                self.keypad_box.show()

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
        self.ac_off_cell, self.ac_off_btn = self.make_keypad_button(
            keypad_keys,
            AC_OFF_KEY,
            row,
            0,
            0,
            image=self.turn_off_image,
            visible=False,
            is_ops=True,
            titlebox_text="Off",
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
        self.ac_on_cell, self.ac_on_btn = self.make_keypad_button(
            keypad_keys,
            AC_ON_KEY,
            row,
            2,
            0,
            image=self.turn_on_image,
            visible=False,
            is_ops=True,
            titlebox_text="On",
        )

        # Acs2 Momentary Action Button
        self.ac_aux1_cell, self.ac_aux1_btn = self.make_keypad_button(
            keypad_keys,
            AUX1_KEY,
            row - 1,
            2,
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
        self.image_box.hide()

    def on_sensor_track_change(self) -> None:
        tmcc_id = self._scope_tmcc_ids[self.scope]
        st_seq = IrdaSequence.by_value(int(self.sensor_track_buttons.value))
        IrdaReq(tmcc_id, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=st_seq).send(repeat=self.repeat)

    def make_keypad_button(
        self,
        keypad_box: Box,
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
        command: Callable | None = None,
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
            cell = Box(keypad_box, layout="auto", grid=[col, row], align="bottom", visible=True)
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
        )
        nb.on_press = command
        nb.tk.configure(bd=1, relief="solid", highlightthickness=1)

        # ------------------------------------------------------------
        #  Image vs text button behavior
        # ------------------------------------------------------------
        if image:
            nb.image = image
            # load and cache the image to prevent garbage collection
            nb.tk.config(image=self.get_titled_image(image), compound="center")
        else:
            # Make tk.Button fill the entire cell and draw full border
            # only do this for text buttons
            nb.text = label
            nb.text_size = size
            nb.text_bold = bolded
            nb.text_color = "black"
            nb.tk.config(compound="center", anchor="center", padx=0, pady=0)
            self.make_color_changeable(nb, fade=True)
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
            tmcc_id = tmcc_id[1:] + key
            self.tmcc_id_text.value = tmcc_id
        elif key == CLEAR_KEY:
            tmcc_id = "0" * num_chars
            self.tmcc_id_text.value = tmcc_id
            self.entry_mode()
        elif key == "↵":
            # if a valid (existing) entry was entered, go to ops mode, otherwise,
            # stay in entry mode
            if self.make_recent(self.scope, int(tmcc_id)):
                self.ops_mode()
            else:
                self.entry_mode()
        else:
            self.do_command(key)

        # update information immediately if not in entry mode
        if not self._in_entry_mode and key.isdigit():
            log.debug("on_keypress calling update_component_info...")
            self.update_component_info(int(tmcc_id), "")

    def make_color_changeable(
        self,
        button,
        pressed_color=LIONEL_ORANGE,
        flash_ms=150,
        fade=False,
        border=False,
    ):
        """Add a simple flash overlay on button release without freezing the GUI."""
        tkbtn = button.tk
        parent = tkbtn.master

        # Create one reusable overlay per button
        overlay = getattr(button, "_flash_overlay", None)
        if overlay is None:
            overlay = tk.Frame(
                parent,
                bg=pressed_color,
                bd=0,
                highlightthickness=1 if border else 0,
                highlightbackground="white" if border else pressed_color,
            )
            label = tk.Label(
                overlay,
                text=button.text,
                font=(button.font, button.text_size, "bold" if button.text_bold else "normal"),
                fg=button.text_color,
                bg=pressed_color,
            )
            label.place(relx=0.5, rely=0.5, anchor="center")
            overlay.place_forget()
            button._flash_overlay = overlay

        def flash(_=None):
            try:
                w, h = tkbtn.winfo_width(), tkbtn.winfo_height()
                x, y = tkbtn.winfo_x(), tkbtn.winfo_y()

                overlay.place(x=x, y=y, width=w, height=h)
                overlay.lift(tkbtn)

                if fade:
                    steps = 10
                    interval = max(1, flash_ms // steps)

                    def fade_step(step=0):
                        if step >= steps:
                            overlay.place_forget()
                            return
                        try:
                            c1 = overlay.winfo_rgb(pressed_color)
                            c2 = overlay.winfo_rgb(parent.cget("background"))
                            ratio = step / steps
                            r = int((c1[0] * (1 - ratio) + c2[0] * ratio) / 256)
                            g = int((c1[1] * (1 - ratio) + c2[1] * ratio) / 256)
                            b = int((c1[2] * (1 - ratio) + c2[2] * ratio) / 256)
                            overlay.config(bg=f"#{r:02x}{g:02x}{b:02x}")
                            overlay.after(interval, fade_step, step + 1)
                        except (tk.TclError, RuntimeError):
                            overlay.place_forget()

                    fade_step()
                else:
                    self.app.tk.after(flash_ms, overlay.place_forget)
            except (tk.TclError, RuntimeError):
                try:
                    overlay.place_forget()
                except tk.TclError:
                    pass

        # Bind flash to release/keypress events
        tkbtn.bind("<ButtonRelease-1>", flash, add="+")
        tkbtn.bind("<ButtonRelease>", flash, add="+")
        tkbtn.bind("<KeyPress-space>", flash, add="+")
        tkbtn.bind("<KeyPress-Return>", flash, add="+")

    def make_recent(self, scope: CommandScope, tmcc_id: int, state: S = None) -> bool:
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
                    state = self._state_store.get_state(self.scope, tmcc_id)
                    cmd(state)
                elif cmd == send_lcs_off_command:
                    state = self._state_store.get_state(self.scope, tmcc_id)
                    cmd(state)
        else:
            print(f"Unknown key: {key}")

    def entry_mode(self, clear_info: bool = True) -> None:
        print(f"entry_mode  clear_info={clear_info}:")
        if clear_info:
            self.update_component_info(0)
        self._in_entry_mode = True
        for cell in self.entry_cells:
            if not cell.visible:
                cell.show()
        for cell in self.ops_cells:
            if cell.visible:
                cell.hide()
        if not self.keypad_box.visible:
            self.keypad_box.show()
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} and self._scope_tmcc_ids[self.scope]:
            self.reset_btn.enable()
        else:
            self.reset_btn.disable()
        print("Exiting self.entry_mode...")

    def ops_mode(self, update_info: bool = True, state: S = None) -> None:
        print(f"ops_mode: {self.scope} update_info: {update_info}")
        self._in_entry_mode = False
        for cell in self.entry_cells:
            if cell.visible:
                cell.hide()
        for cell in self.ops_cells:
            if cell.visible:
                cell.hide()
        self.reset_btn.disable()
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
            if not isinstance(state, EngineState):
                state = self._state_store.get_state(self.scope, self._scope_tmcc_ids[self.scope], False)
            self.on_new_engine(state, ops_mode_setup=True)
            if not self.controller_box.visible:
                self.controller_box.show()
            if not self.controller_keypad_box.visible:
                self.controller_keypad_box.show()
            if self.keypad_box.visible:
                self.keypad_box.hide()
            if state:
                self.reset_btn.enable()
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
        elif self.scope == CommandScope.ACC:
            if not isinstance(state, AccessoryState):
                state = self._state_store.get_state(CommandScope.ACC, self._scope_tmcc_ids[self.scope], False)
            self.on_new_accessory(state)
            if isinstance(state, AccessoryState):
                if state.is_sensor_track:
                    self.sensor_track_box.show()
                    self.keypad_box.hide()
                elif state.is_bpc2 or state.is_asc2:
                    self.ac_off_cell.show()
                    self.ac_status_cell.show()
                    self.ac_on_cell.show()
                    if state.is_asc2:
                        self.ac_aux1_cell.show()
                    if not self.keypad_box.visible:
                        self.keypad_box.show()
                else:
                    if not self.keypad_box.visible:
                        self.keypad_box.show()
            else:
                if not self.keypad_box.visible:
                    self.keypad_box.show()

        if update_info:
            self.update_component_info(in_ops_mode=True)
        print("Exiting self.ops_mode...")

    def update_component_info(
        self,
        tmcc_id: int = None,
        not_found_value: str = "Not Configured",
        in_ops_mode: bool = False,
    ) -> None:
        print(f"update_component_info: {tmcc_id}")
        if tmcc_id is None:
            tmcc_id = self._scope_tmcc_ids.get(self.scope, 0)
        # update the tmcc_id associated with current scope
        self._scope_tmcc_ids[self.scope] = tmcc_id
        update_button_state = True
        if tmcc_id:
            state = self._state_store.get_state(self.scope, tmcc_id, False)
            if state:
                # Make sure ID field shows TMCC ID, not just road number
                if tmcc_id != state.tmcc_id or tmcc_id != int(self.tmcc_id_text.value):
                    tmcc_id = state.tmcc_id
                    self._scope_tmcc_ids[self.scope] = tmcc_id
                    num_chars = 4 if self.scope in {CommandScope.ENGINE} else 2
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
            self.name_text.value = ""
            state = None
            self.clear_image()
        self.monitor_state()
        # use the callback to update ops button state
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ACC}:
            if update_button_state:
                self._scoped_callbacks.get(self.scope, lambda s: print(f"from uci: {s}"))(state)
            self.update_component_image(tmcc_id)
        else:
            self.image_box.hide()
        print("Exiting update_component_info...")

    def clear_image(self):
        self.image.image = None
        self.image_box.hide()

    def update_component_image(self, tmcc_id: int = None, key: tuple[CommandScope, int] = None) -> None:
        print(f"update_component_image: {tmcc_id}, {key}")
        if key is None and self.scope in {CommandScope.SWITCH, CommandScope.ROUTE}:
            # routes and switches don't use images
            return
        with self._cv:
            if key:
                scope = key[0]
                tmcc_id = key[1]
            else:
                scope = self.scope
                if tmcc_id is None:
                    tmcc_id = self._scope_tmcc_ids[self.scope]
            img = None
            if scope in {CommandScope.ENGINE} and tmcc_id != 0:
                prod_info = self._prod_info_cache.get(tmcc_id, None)

                # If not cached or not a valid Future/ProdInfo, start a background fetch
                if prod_info is None:
                    if (scope, tmcc_id) not in self._pending_prod_infos:
                        # Submit fetch immediately and cache the Future itself
                        future = self._executor.submit(self._fetch_prod_info, scope, tmcc_id)
                        self._prod_info_cache[tmcc_id] = future
                    return

                if isinstance(prod_info, Future) and prod_info.done() and isinstance(prod_info.result(), ProdInfo):
                    prod_info = self._prod_info_cache[tmcc_id] = prod_info.result()
                    self._pending_prod_infos.discard((scope, tmcc_id))

                if isinstance(prod_info, ProdInfo):
                    # Resize image if needed
                    img = self._image_cache.get((CommandScope.ENGINE, tmcc_id), None)
                    if img is None:
                        img = self.get_scaled_image(BytesIO(prod_info.image_content))
                        self._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                else:
                    self.clear_image()
            elif self.scope in {CommandScope.ACC} and tmcc_id != 0:
                state = self._state_store.get_state(self.scope, tmcc_id, False)
                if isinstance(state, AccessoryState):
                    img = self._image_cache.get((CommandScope.ACC, tmcc_id), None)
                    if img is None:
                        if state.is_asc2:
                            img = self.get_scaled_image(self.asc2_image, preserve_height=True)
                        elif state.is_bpc2:
                            img = self.get_scaled_image(self.bpc2_image, preserve_height=True)
                        elif state.is_amc2:
                            img = self.get_scaled_image(self.amc2_image, preserve_height=True)
                        elif state.is_sensor_track:
                            img = self.get_scaled_image(self.sensor_track_image, preserve_height=True)
                        if img:
                            self._image_cache[(CommandScope.ACC, tmcc_id)] = img
                        else:
                            self.clear_image()
            else:
                self.clear_image()
            if img and scope == self.scope and tmcc_id == self._scope_tmcc_ids[self.scope]:
                available_height, available_width = self.calc_image_box_size()
                self.image.tk.config(image=img)
                self.image.width = available_width
                self.image.height = available_height
                self.image_box.show()

    def get_scaled_image(self, source: str | io.BytesIO, preserve_height: bool = False) -> ImageTk.PhotoImage:
        available_height, available_width = self.calc_image_box_size()
        pil_img = Image.open(source)
        orig_width, orig_height = pil_img.size

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
        img = ImageTk.PhotoImage(pil_img.resize((scaled_width, scaled_height)))
        return img

    def calc_image_box_size(self) -> tuple[int, int | Any]:
        with self._cv:
            if self.avail_image_height is None or self.avail_image_width is None:
                # Calculate available space for the image
                self.app.tk.update_idletasks()

                # Get the heights of fixed elements
                header_height = self.header.tk.winfo_reqheight()
                emergency_height = self.emergency_box_height or self.emergency_box.tk.winfo_reqheight()
                info_height = self.info_box.tk.winfo_reqheight()
                keypad_height = self.keypad_box.tk.winfo_reqheight()
                scope_height = self.scope_box.tk.winfo_reqheight()

                # Calculate remaining vertical space
                self.avail_image_height = (
                    self.height - header_height - emergency_height - info_height - keypad_height - scope_height - 20
                )
                # use width of emergency height box as standard
                self.avail_image_width = self.emergency_box_width or self.emergency_box.tk.winfo_reqwidth()
        return self.avail_image_height, self.avail_image_width

    def make_emergency_buttons(self, app: App):
        self.emergency_box = emergency_box = Box(app, layout="grid", border=2, align="top")
        _ = Text(emergency_box, text=" ", grid=[0, 0, 3, 1], align="top", size=2, height=1, bold=True)

        self.halt_btn = halt_btn = PushButton(
            emergency_box,
            text=HALT_KEY,
            grid=[0, 1],
            align="top",
            width=11,
            padx=self._text_pad_x,
            pady=self._text_pad_y,
            command=self.on_keypress,
            args=[HALT_KEY],
        )
        halt_btn.bg = "red"
        halt_btn.text_color = "white"
        halt_btn.text_bold = True
        halt_btn.text_size = self.s_20

        _ = Text(emergency_box, text=" ", grid=[1, 1], align="top", size=6, height=1, bold=True)

        self.reset_btn = reset_btn = PushButton(
            emergency_box,
            text="Reset",
            grid=[2, 1],
            align="top",
            width=11,
            padx=self._text_pad_x,
            pady=self._text_pad_y,
            enabled=False,
            command=self.on_engine_command,
            args=["RESET"],
        )
        reset_btn.bg = "gray"
        reset_btn.text_color = "black"
        reset_btn.text_bold = True
        reset_btn.text_size = self.s_20

        _ = Text(emergency_box, text=" ", grid=[0, 2, 3, 1], align="top", size=2, height=1, bold=True)
        self.app.tk.update_idletasks()
        self.emergency_box_width = emergency_box.tk.winfo_width()
        self.emergency_box_height = emergency_box.tk.winfo_height()

    def on_engine_command(
        self,
        targets: str | list[str],
        data: int = 0,
        repeat: int = None,
        do_ops: bool = False,
        do_entry: bool = False,
    ) -> None:
        repeat = repeat if repeat else self.repeat
        scope = self.scope
        tmcc_id = self._scope_tmcc_ids[scope]
        if tmcc_id == 0:
            tmcc_id = int(self.tmcc_id_text.value)
            self._scope_tmcc_ids[scope] = tmcc_id
        print(f"on_engine_command: {scope} {tmcc_id} {targets}, {data}, {repeat}")
        if scope in {CommandScope.ENGINE, CommandScope.TRAIN} and tmcc_id:
            state = self._state_store.get_state(scope, tmcc_id, False)
            if state:
                if isinstance(targets, str):
                    targets = [targets]
                for target in targets:
                    if state.is_legacy:
                        # there are a few special cases
                        if target in {SMOKE_ON, SMOKE_OFF}:
                            cmd_enum = self.get_tmcc2_smoke_cmd(target, state)
                        else:
                            cmd_enum = TMCC2EngineOpsEnum.look_up(target)
                    else:
                        cmd_enum = TMCC1EngineCommandEnum.by_name(target)
                    if cmd_enum:
                        cmd = CommandReq.build(cmd_enum, tmcc_id, data, scope)
                        repeat = REPEAT_EXCEPTIONS.get(cmd_enum, repeat)
                        cmd.send(repeat=repeat)
                        if do_ops is True and self._in_entry_mode is True:
                            self.ops_mode(update_info=True)
                        elif do_entry and self._in_entry_mode is False:
                            self.entry_mode(clear_info=False)
                        return

    @staticmethod
    def get_tmcc2_smoke_cmd(cmd: str, state: EngineState) -> TMCC2EngineOpsEnum | None:
        cur_smoke = state.smoke_level
        print(f"get_tmcc2_smoke_cmd: {cmd}, {cur_smoke} {state}")
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
        state = self._state_store.get_state(self.scope, tmcc_id, False)
        if state and state.bt_id:
            # TODO: wrap in try/catch as it is likely user won't have API Key
            prod_info = ProdInfo.by_btid(state.bt_id)
        else:
            prod_info = "N/A"
        with self._cv:
            self._prod_info_cache[tmcc_id] = prod_info
            self._pending_prod_infos.discard((scope, tmcc_id))
        return prod_info

    def _fetch_prod_info(self, scope: CommandScope, tmcc_id: int) -> ProdInfo | None:
        """Fetch product info in a background thread, then schedule UI update."""
        with self._cv:
            prod_info = None
            key = (scope, tmcc_id)
            if key not in self._pending_prod_infos:
                self._pending_prod_infos.add(key)
                prod_info = self.request_prod_info(scope, tmcc_id)
        # Schedule the UI update on the main thread
        self.queue_message(self.update_component_image, tmcc_id, key)
        return prod_info

    # Example lazy loader pattern for images
    def get_image(self, path, size=None):
        if path not in self._image_cache:
            img = Image.open(path)
            if size:
                img = img.resize(size)
            self._image_cache[path] = ImageTk.PhotoImage(img)
        return self._image_cache[path]

    def get_titled_image(self, path):
        return self.get_image(path, size=(self.titled_button_size, self.titled_button_size))
