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
from ..protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum, TMCC1SwitchCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandEnum
from ..utils.path_utils import find_file
from ..utils.unique_deque import UniqueDeque

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)

LAYOUT = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["⌫", "0", "↵"],
]

HALT_KEY = ">> Halt <<"
SWITCH_THRU_KEY = "↑"
SWITCH_OUT_KEY = "↖↗"
FIRE_ROUTE_KEY = "⚡"
CLEAR_KEY = "⌫"
ENTER_KEY = "↵"
SET_KEY = "Set"
ENGINE_ON_KEY = "ENGINE ON"
ENGINE_OFF_KEY = "ENGINE OFF"
AC_ON_KEY = "AC ON"
AC_OFF_KEY = "AC OFF"
AUX1_KEY = "Aux1"
AUX2_KEY = "Aux2"
AUX3_KEY = "Aux3"

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
        self.button_size = int(round(self.width / 5.5))
        self.titled_button_size = int(round((self.width / 5.5) * 0.9))
        self.scope_size = int(round(self.width / 5))
        self._text_pad_x = 20
        self._text_pad_y = 20
        self.s_72 = self.scale(72, 0.7)
        self.grid_pad_by = 2
        self.avail_image_height = self.avail_image_width = None
        self.scope = CommandScope.ENGINE
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
        self.power_off_image = self.power_on_image = None
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
        self._message_queue = Queue()

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
        self.controller_box = self.controller_keypad_box = self.controller_throttle_box = None
        self.throttle = self.speed = self.focus_widget = None

        # callbacks
        self._scoped_callbacks = {
            CommandScope.ROUTE: self.on_new_route,
            CommandScope.SWITCH: self.on_new_switch,
            CommandScope.ACC: self.on_new_accessory,
            CommandScope.ENGINE: self.on_new_engine,
            CommandScope.TRAIN: self.on_new_engine,
        }

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
        app.tk.update_idletasks()

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

    def make_controller(self, app):
        self.controller_box = controller_box = Box(
            app,
            border=2,
            align="top",
            visible=False,
        )
        self.ops_cells.add(controller_box)
        self.controller_keypad_box = keypad_keys = Box(
            controller_box,
            layout="grid",
            border=0,
            align="left",
        )

        self.controller_throttle_box = throttle_box = Box(
            controller_box,
            border=1,
            align="right",
        )

        cell = TitleBox(throttle_box, "Speed", align="top", border=1)
        cell.text_size = self.s_12
        self.speed = speed = Text(
            cell,
            text="000",
            color="black",
            align="top",
            bold=True,
            size=self.s_22,
            font="DigitalDream",
        )
        speed.bg = "black"
        speed.text_color = "white"

        self.focus_widget = focus_sink = tk.Frame(app.tk, takefocus=1)
        focus_sink.place(x=-9999, y=-9999, width=1, height=1)

        self.throttle = throttle = Slider(
            throttle_box,
            align="top",
            horizontal=False,
            step=1,
            width=int(self.button_size / 2),
            height=self.button_size * 4,
        )
        throttle.text_color = "white"
        throttle.tk.config(
            from_=195,
            to=0,
            takefocus=0,
            troughcolor="#003366",  # deep Lionel blue for the track,
            activebackground="#FF6600",  # bright Lionel orange for the handle
            bg="#001A33",  # darker navy background
            highlightthickness=1,
            highlightbackground="#FF6600",  # subtle orange outline
            width=60,
            sliderlength=80,
        )
        throttle.tk.bind("<Button-1>", lambda e: throttle.tk.focus_set())
        throttle.tk.bind("<ButtonRelease-1>", self.clear_focus, add="+")
        throttle.tk.bind("<ButtonRelease>", self.clear_focus, add="+")
        print(keypad_keys)

    # noinspection PyUnusedLocal
    def clear_focus(self, e=None):
        """
        Touchscreen-safe focus clearing for throttle slider.
        Ensures focus moves off the Scale after finger release
        and forces a redraw so the grab handle deactivates.
        """
        if self.app.tk.focus_get() == self.throttle.tk:
            self.app.tk.after_idle(self._do_clear_focus)

    def _do_clear_focus(self):
        self.focus_widget.focus_set()
        self.throttle.tk.event_generate("<Leave>")
        # self.throttle.tk.update_idletasks()

    def on_recents(self, value: str):
        print(f"on_select_component: {value}")
        if value != self.title:
            state = self._options_to_state[value]
            print(state)
            self.update_component_info(tmcc_id=state.tmcc_id)
            self.header.select_default()

    def get_options(self) -> list[str]:
        options = [self.title]
        self._options_to_state.clear()
        queue = self._recents_queue.get(self.scope, None)
        if queue:
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
        if state:
            self.speed.value = f"{state.speed:03d}"
            # only set throttle value if we are not in the middle of setting it
            if self.throttle.tk.focus_displayof() != self.throttle.tk:
                self.throttle.value = state.speed
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
        img = self.power_on_image if state.is_aux_on else self.power_off_image
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
            self._scope_tmcc_ids[scope] = 0
        # highlight initial button
        self.on_scope(self.scope)

    # noinspection PyTypeChecker
    def on_scope(self, scope: CommandScope) -> None:
        print(f"On Scope: {scope}")
        self.scope_box.hide()
        force_entry_mode = False
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
                # pressing the same scope button again returns to entry mode
                self._scope_tmcc_ids[scope] = 0
        # update display
        self.update_component_info()
        # force entry mode if scoped tmcc_id is 0
        if self._scope_tmcc_ids[scope] == 0:
            force_entry_mode = True
        self.rebuild_options()
        num_chars = 4 if self.scope in {CommandScope.ENGINE} else 2
        self.tmcc_id_text.value = f"{self._scope_tmcc_ids[scope]:0{num_chars}d}"
        self.scope_box.show()
        print(f"On Scope: {scope} calling scope_keypad({force_entry_mode})")
        self.scope_keypad(force_entry_mode)

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

    def scope_keypad(self, force_entry_mode: bool = False):
        print(f"Scope Keypad: force={force_entry_mode}")
        # if tmcc_id associated with scope is 0, then we are in entry mode;
        # show keypad with appropriate buttons
        tmcc_id = self._scope_tmcc_ids[self.scope]
        if tmcc_id == 0 or force_entry_mode:
            self.entry_mode()
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
        for r, kr in enumerate(LAYOUT):
            for c, label in enumerate(kr):
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
                )

                if label == CLEAR_KEY:
                    nb.text_color = "red"
                    nb.text_size = self.s_30
                    nb.text_bold = False
                    self.clear_key_cell = cell
                    self.entry_cells.add(cell)
                elif label == ENTER_KEY:
                    self.entry_cells.add(cell)
                    self.enter_key_cell = cell
            row += 1

        # fill in last row; contents depends on scope
        self.on_key_cell, self.on_btn = self.make_keypad_button(
            keypad_keys,
            ENGINE_ON_KEY,
            row,
            0,
            visible=True,
            bolded=True,
            command=self.on_keypress,
            args=[ENGINE_ON_KEY],
            is_entry=True,
            image=self.turn_on_image,
        )

        self.off_key_cell, self.off_btn = self.make_keypad_button(
            keypad_keys,
            ENGINE_OFF_KEY,
            row,
            1,
            visible=True,
            bolded=True,
            command=self.on_keypress,
            args=[ENGINE_OFF_KEY],
            is_entry=True,
            image=self.turn_off_image,
        )

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
        cell.text_size = self.s_12
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
        self.power_off_image = ImageTk.PhotoImage(
            Image.open(self.power_off_path).resize((self.titled_button_size, self.titled_button_size))
        )
        self.power_on_image = ImageTk.PhotoImage(
            Image.open(self.power_on_path).resize((self.titled_button_size, self.titled_button_size))
        )
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
        self.info_box = info_box = Box(app, border=2, align="top")

        # ───────────────────────────────
        # Left: ID box
        # ───────────────────────────────
        self.tmcc_id_box = tmcc_id_box = TitleBox(info_box, f"{self.scope.title} ID", align="left")
        tmcc_id_box.text_size = self.s_12
        self.tmcc_id_text = Text(tmcc_id_box, text="0000", align="left", bold=True)
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

                id_h = tmcc_id_box.tk.winfo_height()
                id_w = tmcc_id_box.tk.winfo_width()

                if id_w <= 1:
                    # still not realized? try again shortly
                    app.tk.after(50, adjust_road_name_box)
                    return

                total_w = self.emergency_box_width or self.emergency_box.tk.winfo_width()
                new_w = max(0, total_w - id_w)
                name_box.tk.config(height=id_h, width=new_w)

                print(f"✅ ID box measured: id_h={id_h}, id_w={id_w}, total_w={total_w}, new_w={new_w}")

            except tk.TclError as e:
                print(f"[adjust_road_name_box] failed: {e}")

        # Schedule width/height fix after geometry update
        app.tk.after(10, adjust_road_name_box)

        # add a picture placeholder here, we may not use it
        self.image_box = image_box = Box(app, border=2, align="top")
        self.image = Picture(image_box, align="top")
        self.image_box.hide()

    def on_sensor_track_change(self) -> None:
        tmcc_id = self._scope_tmcc_ids[self.scope]
        st_seq = IrdaSequence.by_value(int(self.sensor_track_buttons.value))
        print(f"Sensor Track: {tmcc_id} {self.sensor_track_buttons.value} {st_seq.title}")
        IrdaReq(tmcc_id, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=st_seq).send(repeat=self.repeat)

    @staticmethod
    def inspect_titlebox_geometry(titlebox, label_name="TitleBox"):
        """
        Prints detailed geometry info for a guizero.TitleBox and its children.
        Call this AFTER app.update() or update_idletasks().
        """
        try:
            t = titlebox.tk
            print(f"\n📦 Inspecting {label_name}: {t}")
            print(f"  Requested size: {t.winfo_reqwidth()} × {t.winfo_reqheight()}")
            print(f"  Actual size:    {t.winfo_width()} × {t.winfo_height()}")
            print(f"  Propagate:      {t.pack_propagate()}")

            children = t.winfo_children()
            for i, child in enumerate(children):
                cls = child.winfo_class()
                geom = (
                    f"  ↳ Child[{i}]: {cls:<10}"
                    f" | req=({child.winfo_reqwidth()}×{child.winfo_reqheight()})"
                    f" | actual=({child.winfo_width()}×{child.winfo_height()})"
                )
                # If it's a Label, include anchor/justify info
                if isinstance(child, tk.Label):
                    geom += f" | anchor={child.cget('anchor')} justify={child.cget('justify')}"
                print(geom)

                # For nested frames (the TitleBox's content frame)
                if isinstance(child, tk.Frame):
                    subchildren = child.winfo_children()
                    for j, sub in enumerate(subchildren):
                        sub_cls = sub.winfo_class()
                        sub_geom = (
                            f"      ↳ Sub[{j}]: {sub_cls:<10}"
                            f" | req=({sub.winfo_reqwidth()}×{sub.winfo_reqheight()})"
                            f" | actual=({sub.winfo_width()}×{sub.winfo_height()})"
                        )
                        print(sub_geom)

            print("─────────────────────────────────────────────")

        except Exception as e:
            print(f"⚠️ Error inspecting {label_name}: {e}")

    @staticmethod
    def inspect_keypad_grid(keypad_box, label="Keypad Grid"):
        """
        Print actual pixel sizes of each grid row and column
        to help diagnose layout spacing or clipping issues.
        """
        try:
            t = keypad_box.tk
            t.update_idletasks()
            cols, rows = t.grid_size()  # grid_size() returns (cols, rows)

            print(f"\n🧮 Inspecting {label}: {rows} rows × {cols} columns")
            print("─────────────────────────────────────────────")

            # Measure each row’s bounding box height
            for r in range(rows):
                bbox = t.grid_bbox(0, r)
                h = bbox[3] if bbox else "?"
                print(f"  Row {r}: height={h}")

            # Measure each column’s bounding box width
            for c in range(cols):
                bbox = t.grid_bbox(c, 0)
                w = bbox[2] if bbox else "?"
                print(f"  Col {c}: width={w}")

            print("─────────────────────────────────────────────\n")

        except tk.TclError as e:
            print(f"⚠️ Error inspecting {label}: {e}")

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
            command = self.on_keypress

        if size is None and label:
            size = self.s_22 if label.isdigit() else self.s_24

        # ------------------------------------------------------------
        #  Create cell container (either TitleBox or Box)
        # ------------------------------------------------------------
        if titlebox_text:
            cell = TitleBox(
                keypad_box,
                titlebox_text,
                layout="auto",
                grid=[col, row],
                visible=True,
                width=self.button_size,
                height=self.button_size,
            )
            cell.text_size = self.s_12
            button_size = self.titled_button_size
            grid_pad_by = 0

            # Force TitleBox label to top-left
            try:
                lf = cell.tk  # The underlying tk.LabelFrame inside your TitleBox

                # Move title to top-left and reduce reserved caption space
                lf.configure(labelanchor="nw", padx=0, pady=0)

                # Force Tk to recompute geometry after the config change
                lf.update_idletasks()

                # Also adjust the internal child frame (content area)
                children = lf.winfo_children()
                for child in children:
                    if isinstance(child, tk.Frame):
                        # This is the inner content frame that holds your PushButton
                        child.pack_configure(padx=0, pady=0, ipadx=0, ipady=0)
                        child.pack_propagate(False)
            except (tk.TclError, AttributeError) as e:
                log.exception(f"Warning adjusting LabelFrame padding: {e}", exc_info=e)
        else:
            cell = Box(keypad_box, layout="auto", grid=[col, row], visible=True)
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
            # Let the TitleBox grow a bit for its label text
            label_extra = int(self.s_12 * 0.8)  # about one text line of space
            cell.tk.configure(
                width=self.button_size,
                height=self.button_size + label_extra,
            )
            # still disable shrinking, but don’t clip internal content
            cell.tk.pack_propagate(True)
        else:
            cell.tk.configure(
                width=self.button_size,
                height=self.button_size,
            )
            cell.tk.pack_propagate(False)

        # ensure the keypad grid expands uniformly and fills the box height
        extra_pad = max(2, grid_pad_by)
        keypad_box.tk.grid_rowconfigure(row, weight=1, minsize=self.button_size + (2 * extra_pad))
        keypad_box.tk.grid_columnconfigure(col, weight=1, minsize=self.button_size + (2 * extra_pad))

        # ------------------------------------------------------------
        #  Create PushButton
        # ------------------------------------------------------------
        nb = PushButton(
            cell,
            align="top",
            text=label,
            command=command,
            args=args,
        )

        nb.tk.configure(bd=1, relief="solid", highlightthickness=1)

        # ------------------------------------------------------------
        #  Image vs text button behavior
        # ------------------------------------------------------------
        if image:
            nb.image = image
            # load and cache the image to prevent garbage collection
            img = Image.open(image).resize((self.titled_button_size, self.titled_button_size))
            tkimg = ImageTk.PhotoImage(img)
            self._btn_images.append(tkimg)
            nb.tk.config(image=tkimg, compound="center")
        else:
            # Make tk.Button fill the entire cell and draw full border
            # only do this for text buttons
            nb.text_size = size
            nb.text_bold = bolded
            nb.text_color = "black"
            self.make_color_changeable(nb, fade=True)

        # ------------------------------------------------------------
        #  Grid spacing & uniform sizing
        # ------------------------------------------------------------
        nb.tk.config(width=button_size, height=button_size)
        nb.tk.config(padx=0, pady=0, borderwidth=1, highlightthickness=1)

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
            print("on_keypress calling update_component_info...")
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
        print(f"Pushing current: {scope} {tmcc_id} {self.scope} {self.tmcc_id_text.value}")
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
                print(queue)
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

    def entry_mode(self) -> None:
        print("entry_mode:")
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

    def ops_mode(self, update_info: bool = True) -> None:
        print(f"ops_mode: {self.scope}")
        self._in_entry_mode = False
        for cell in self.entry_cells:
            if cell.visible:
                cell.hide()
        for cell in self.ops_cells:
            if cell.visible:
                cell.hide()
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
            state = self._state_store.get_state(self.scope, self._scope_tmcc_ids[self.scope], False)
            self.on_new_engine(state, ops_mode_setup=True)
            if not self.controller_box.visible:
                self.controller_box.show()
            if self.keypad_box.visible:
                self.keypad_box.hide()
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
                    self.inspect_keypad_grid(self.keypad_box, "Acc Keypad")
                else:
                    if not self.keypad_box.visible:
                        self.keypad_box.show()
            else:
                if not self.keypad_box.visible:
                    self.keypad_box.show()

        if update_info:
            print("ops_mode() calling update_component_info()...")
            self.update_component_info(in_ops_mode=True)

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
                print(f"update_component_info: in_ops_mode: {in_ops_mode} in_entry_mode: {self._in_entry_mode}")
                if not in_ops_mode:
                    print(f"Calling ops_mode: {self.scope} {name}")
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
                if prod_info is None:
                    # Start thread to fetch product info
                    fetch_thread = Thread(target=self._fetch_prod_info, args=(self.scope, tmcc_id), daemon=True)
                    self._prod_info_cache[tmcc_id] = fetch_thread
                    fetch_thread.start()
                    return
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
                emergency_height = self.emergency_box.tk.winfo_reqheight()
                info_height = self.info_box.tk.winfo_reqheight()
                keypad_height = self.keypad_box.tk.winfo_reqheight()
                scope_height = self.scope_box.tk.winfo_reqheight()

                # Calculate remaining vertical space
                self.avail_image_height = (
                    self.height - header_height - emergency_height - info_height - keypad_height - scope_height - 20
                )
                # use width of emergency height box as standard
                self.avail_image_width = self.emergency_box.tk.winfo_reqwidth()
        return self.avail_image_height, self.avail_image_width

    def make_emergency_buttons(self, app: App):
        self.emergency_box = emergency_box = Box(app, layout="grid", border=2, align="top")
        _ = Text(emergency_box, text=" ", grid=[0, 0, 3, 1], align="top", size=2, height=1, bold=True)

        self.halt_btn = halt_btn = PushButton(
            emergency_box,
            text=HALT_KEY,
            grid=[0, 1],
            align="top",
            width=10,
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
            width=10,
            padx=self._text_pad_x,
            pady=self._text_pad_y,
            enabled=False,
        )
        reset_btn.bg = "gray"
        reset_btn.text_color = "black"
        reset_btn.text_bold = True
        reset_btn.text_size = self.s_20

        _ = Text(emergency_box, text=" ", grid=[0, 2, 3, 1], align="top", size=2, height=1, bold=True)
        app.tk.update_idletasks()
        self.emergency_box_width = self.emergency_box.tk.winfo_width()
        self.emergency_box_height = self.emergency_box.tk.winfo_height()

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

    def _fetch_prod_info(self, scope: CommandScope, tmcc_id: int) -> None:
        """Fetch product info in a background thread, then schedule UI update."""
        with self._cv:
            key = (scope, tmcc_id)
            if key in self._pending_prod_infos:
                # ProdInfo has already been requested, exit
                return
            else:
                self._pending_prod_infos.add(key)
        self.request_prod_info(scope, tmcc_id)
        # Schedule the UI update on the main thread
        self.queue_message(self.update_component_image, tmcc_id, key)
