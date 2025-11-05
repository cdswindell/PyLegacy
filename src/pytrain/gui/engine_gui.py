#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
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

from guizero import App, Box, Combo, Picture, PushButton, Text, TitleBox
from guizero.base import Widget
from guizero.event import EventData
from PIL import Image, ImageTk

from ..comm.command_listener import CommandDispatcher
from ..db.accessory_state import AccessoryState
from ..db.base_state import BaseState
from ..db.component_state import ComponentState, RouteState, SwitchState
from ..db.component_state_store import ComponentStateStore
from ..db.prod_info import ProdInfo
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..pdi.asc2_req import Asc2Req
from ..pdi.constants import Asc2Action, PdiCommand
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandEnum
from ..utils.path_utils import find_file

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)

LAYOUT = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["⌫", "0", "↵"],
]

SWITCH_THRU_KEY = "↑"
SWITCH_OUT_KEY = "↖↗"
FIRE_ROUTE_KEY = "⚡"
CLEAR_KEY = "⌫"
ENTER_KEY = "↵"
SET_KEY = "Set"

KEY_TO_COMMAND = {
    FIRE_ROUTE_KEY: CommandReq(TMCC2RouteCommandEnum.FIRE),
    SWITCH_THRU_KEY: CommandReq(TMCC1SwitchCommandEnum.THRU),
    SWITCH_OUT_KEY: CommandReq(TMCC1SwitchCommandEnum.OUT),
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
        self.s_30: int = int(round(30 * scale_by))
        self.s_24: int = int(round(24 * scale_by))
        self.s_22: int = int(round(22 * scale_by))
        self.s_20: int = int(round(20 * scale_by))
        self.s_18: int = int(round(18 * scale_by))
        self.s_16: int = int(round(16 * scale_by))
        self.s_12: int = int(round(12 * scale_by))
        self.button_size = int(round(self.width / 5.5))
        self.scope_size = int(round(self.width / 5))
        self._text_pad_x = 20
        self._text_pad_y = 20
        self.s_72 = self.scale(72, 0.7)
        self.grid_pad_by = 2
        self.avail_image_height = self.avail_image_width = None
        self.scope = CommandScope.ENGINE

        self._enabled_bg = enabled_bg
        self._disabled_bg = disabled_bg
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self._active_bg = active_bg
        self._inactive_bg = inactive_bg
        self.app = self.box = self.acc_box = self.y_offset = None
        self.turn_on_image = find_file("on_button.jpg")
        self.turn_off_image = find_file("off_button.jpg")
        self.alarm_on_image = find_file("Breaking-News-Emoji.gif")
        self.alarm_off_image = find_file("red_light_off.jpg")
        self.left_arrow_image = find_file("left_arrow.jpg")
        self.right_arrow_image = find_file("right_arrow.jpg")
        self.asc2_image = find_file("LCS-ASC2-6-81639.jpg")
        self._app_counter = 0
        self._in_entry_mode = True
        self._message_queue = Queue()
        self._btn_images = []
        self._scope_buttons = {}
        self._scope_tmcc_ids = {}
        self._scope_watchers = {}
        self._engine_cache = {}
        self._engine_image_cache = {}
        self.entry_cells = set()
        self.ops_cells = set()

        # various boxes
        self.emergency_box = self.info_box = self.keypad_box = self.scope_box = self.name_box = self.image_box = None

        # various buttons
        self.halt_btn = self.reset_btn = self.off_btn = self.on_btn = self.set_btn = None
        self.fire_route_btn = self.switch_thru_btn = self.switch_out_btn = None

        # various fields
        self.tmcc_id_box = self.tmcc_id_text = self._nbi = self.header = None
        self.name_text = None
        self.on_key_cell = self.off_key_cell = None
        self.engine_image = None
        self.clear_key_cell = self.enter_key_cell = self.set_key_cell = self.fire_route_cell = None
        self.switch_thru_cell = self.switch_out_cell = None

        # callbacks
        self._scoped_callbacks = {
            CommandScope.ROUTE: self.on_new_route,
            CommandScope.SWITCH: self.on_new_switch,
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
                        app.tk.update_idletasks()
                except Empty:
                    pass
            return None

        app.repeat(20, _poll_shutdown)

        # customize label
        self.header = cb = Combo(
            app,
            options=[self.title],
            selected=self.title,
            align="top",
        )
        cb.text_size = self.s_24
        cb.text_bold = True
        # _ = Text(app, text=" ", align="top", size=6, height=1, bold=True)

        # Make the emergency buttons, including Halt and Reset
        self.make_emergency_buttons(app)
        _ = Text(app, text=" ", align="top", size=3, height=1, bold=True)

        # make selection box and keypad
        self.make_keypad(app)

        # make scope buttons
        self.make_scope(app)

        #
        # self.app.update()
        #
        # # build state buttons
        # self.acc_box = Box(self.app, border=2, align="bottom", layout="grid")

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

    def make_scope(self, app: App):
        button_height = int(round(50 * self._scale_by))
        self.scope_box = scope_box = Box(app, layout="grid", border=2, align="bottom")
        _ = Text(scope_box, text=" ", grid=[0, 0, 5, 1], align="top", size=3, height=1, bold=True)
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
        app.update()

    def on_scope(self, scope: CommandScope) -> None:
        self.scope_box.hide()
        force_entry_mode = False
        for k, v in self._scope_buttons.items():
            if k == scope:
                v.bg = self._enabled_bg
            else:
                v.bg = self._disabled_bg
        if scope != self.scope:
            self.tmcc_id_box.text = f"{scope.title} ID"
            self.scope = scope
            self.update_component_info()
        else:
            self._scope_tmcc_ids[scope] = 0
            force_entry_mode = True
        num_chars = 4 if self.scope in {CommandScope.ENGINE} else 2
        self.tmcc_id_text.value = f"{self._scope_tmcc_ids[scope]:0{num_chars}d}"
        self.scope_box.show()
        self.scope_keypad(force_entry_mode)

    def scope_keypad(self, force_entry_mode: bool = False):
        # if tmcc_id associated with scope is 0, then we are in entry mode;
        # show keypad with appropriate button
        tmcc_id = self._scope_tmcc_ids[self.scope]
        if tmcc_id == 0 or force_entry_mode:
            self.entry_mode()
            if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                self.on_key_cell.show()
                self.off_key_cell.show()
            else:
                self.on_key_cell.hide()
                self.off_key_cell.hide()
            self.keypad_box.show()
        else:
            self.ops_mode()
            if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                self.keypad_box.hide()
            else:
                pass

    # noinspection PyTypeChecker
    def make_keypad(self, app: App):
        self.info_box = info_box = Box(app, border=2, align="top")

        self.tmcc_id_box = tmcc_id_box = TitleBox(info_box, f"{self.scope.title} ID", align="left")
        tmcc_id_box.text_size = self.s_12

        self.tmcc_id_text = tmcc_id = Text(tmcc_id_box, text="0000", align="left", bold=True)
        tmcc_id.text_color = "blue"
        tmcc_id.text_bold = True
        tmcc_id.text_size = self.s_20
        tmcc_id.width = 5
        app.update()  # we want to measure height of the title box

        self.name_box = name_box = TitleBox(
            info_box,
            "Road Name",
            align="right",
            height=tmcc_id_box.tk.winfo_reqheight(),
            width=self.emergency_box.tk.winfo_reqwidth() - tmcc_id_box.tk.winfo_reqwidth(),
        )
        name_box.text_size = self.s_12

        self.name_text = name_text = Text(
            name_box,
            text="",
            align="top",
            bold=True,
            width="fill",
        )
        name_text.text_color = "blue"
        name_text.text_bold = True
        name_text.text_size = self.s_18
        name_text.width = 20
        name_text.tk.config(justify="left", anchor="w")  # ← this does the trick!

        # add a picture placeholder here, we may not use it
        self.image_box = image_box = Box(app, border=2, align="top")
        self.engine_image = Picture(image_box, align="top")
        self.image_box.hide()

        # _ = Text(app, text=" ", align="top", size=3, height=1, bold=True)
        self.keypad_box = keypad_box = Box(app, layout="grid", border=2, align="top")

        row = 0
        for r, kr in enumerate(LAYOUT):
            for c, label in enumerate(kr):
                img = tk.PhotoImage(width=self.button_size, height=self.button_size)
                self._btn_images.append(img)
                cell = Box(keypad_box, layout="auto", grid=[c, row])
                nb = PushButton(
                    cell,
                    text=label,
                    command=self.on_keypress,
                    args=[label],
                )
                nb.text_color = "black"
                nb.tk.config(image=img, compound="center")
                nb.tk.config(width=self.button_size, height=self.button_size)
                nb.text_size = self.s_22 if label.isdigit() else self.s_24
                nb.text_bold = True
                nb.tk.config(padx=0, pady=0, borderwidth=1, highlightthickness=1)
                # spacing between buttons (in pixels)
                nb.tk.grid_configure(padx=self.grid_pad_by, pady=self.grid_pad_by)

                if label == CLEAR_KEY:
                    nb.text_color = "red"
                    nb.text_size = self.s_24
                    nb.text_bold = False
                    self.clear_key_cell = cell
                    self.entry_cells.add(cell)
                elif label == ENTER_KEY:
                    self.enter_key_cell = cell
                    self.entry_cells.add(cell)
            row += 1

        # fill in last row; contents depends on scope
        self.on_key_cell = cell = Box(keypad_box, layout="auto", grid=[0, row])
        self.entry_cells.add(cell)
        self.on_btn = nb = PushButton(
            cell,
            image=self.turn_on_image,
            align="top",
            height=self.button_size,
            width=self.button_size,
            text="on",
            command=self.on_keypress,
            args=["on"],
        )
        nb.tk.config(padx=0, pady=0, borderwidth=1, highlightthickness=1)
        # spacing between buttons (in pixels)
        nb.tk.grid_configure(padx=self.grid_pad_by, pady=self.grid_pad_by)

        # off button
        self.off_key_cell = cell = Box(keypad_box, layout="auto", grid=[1, row])
        self.entry_cells.add(cell)
        self.off_btn = nb = PushButton(
            cell,
            image=self.turn_off_image,
            align="top",
            height=self.button_size,
            width=self.button_size,
            text="off",
            command=self.on_keypress,
            args=["off"],
        )
        nb.tk.config(padx=0, pady=0, borderwidth=1, highlightthickness=1)
        # spacing between buttons (in pixels)
        nb.tk.grid_configure(padx=self.grid_pad_by, pady=self.grid_pad_by)

        # set button
        self.set_key_cell = cell = Box(keypad_box, layout="auto", grid=[2, row])
        self.entry_cells.add(cell)
        img = tk.PhotoImage(width=self.button_size, height=self.button_size)
        self._btn_images.append(img)
        self.set_btn = nb = PushButton(
            cell,
            align="top",
            height=self.button_size,
            width=self.button_size,
            text="Set",
            command=self.on_keypress,
            args=["set"],
        )
        nb.text_color = "black"
        nb.tk.config(image=img, compound="center")
        nb.tk.config(width=self.button_size, height=self.button_size)
        nb.text_size = self.s_16
        nb.text_bold = True
        nb.tk.config(padx=0, pady=0, borderwidth=1, highlightthickness=1)
        # spacing between buttons (in pixels)
        nb.tk.grid_configure(padx=self.grid_pad_by, pady=self.grid_pad_by)

        # fire route button
        self.fire_route_cell, self.fire_route_btn = self.make_keypad_button(
            keypad_box,
            FIRE_ROUTE_KEY,
            row,
            1,
            size=self.s_30,
            visible=False,
            is_ops=True,
        )

        # switch button
        self.switch_thru_cell, self.switch_thru_btn = self.make_keypad_button(
            keypad_box,
            SWITCH_THRU_KEY,
            row,
            0,
            size=self.s_30,
            visible=False,
            is_ops=True,
        )
        self.switch_out_cell, self.switch_out_btn = self.make_keypad_button(
            keypad_box,
            SWITCH_OUT_KEY,
            row,
            2,
            size=self.s_30,
            visible=False,
            is_ops=True,
        )
        app.update()

    def make_keypad_button(
        self,
        keypad_box: Box,
        label: str,
        row: int,
        col: int,
        size: int,
        visible: bool = True,
        bolded: bool = True,
        is_ops: bool = False,
        is_entry: bool = False,
    ):
        cell = Box(keypad_box, layout="auto", grid=[col, row], visible=visible)
        if is_ops:
            self.ops_cells.add(cell)
        if is_entry:
            self.entry_cells.add(cell)
        img = tk.PhotoImage(width=self.button_size, height=self.button_size)
        self._btn_images.append(img)
        nb = PushButton(
            cell,
            align="top",
            height=self.button_size,
            width=self.button_size,
            text=label,
            command=self.on_keypress,
            args=[label],
        )
        nb.text_color = "black"
        nb.tk.config(image=img, compound="center")
        nb.tk.config(width=self.button_size, height=self.button_size)
        nb.text_size = size
        nb.text_bold = bolded
        nb.tk.config(padx=0, pady=0, borderwidth=1, highlightthickness=1)
        # spacing between buttons (in pixels)
        nb.tk.grid_configure(padx=self.grid_pad_by, pady=self.grid_pad_by)
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
            self._scope_tmcc_ids[self.scope] = int(tmcc_id)
            self.ops_mode()
        else:
            self.do_command(key)

        # self.tmcc_id_text.value = tmcc_id
        # update information immediately if not in entry mode
        if not self._in_entry_mode and key.isdigit():
            self.update_component_info(int(tmcc_id), "")

    def do_command(self, key: str) -> None:
        cmd = KEY_TO_COMMAND.get(key, None)
        tmcc_id = self._scope_tmcc_ids[self.scope]
        if cmd and tmcc_id:
            cmd.scope = self.scope
            cmd.address = self._scope_tmcc_ids[self.scope]
            cmd.send(repeat=self.repeat)
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

    def ops_mode(self) -> None:
        print("ops_mode:")
        self._in_entry_mode = False
        for cell in self.entry_cells:
            if cell.visible:
                cell.hide()
        for cell in self.ops_cells:
            if cell.visible:
                cell.hide()
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
            pass
        elif self.scope == CommandScope.ROUTE:
            self.on_new_route()
            self.fire_route_cell.show()
        elif self.scope == CommandScope.SWITCH:
            self.on_new_switch()
            self.switch_thru_cell.show()
            self.switch_out_cell.show()
        self.update_component_info()

    def update_component_info(self, tmcc_id: int = None, not_found_value: str = "Not Defined"):
        print("update_component_info:")
        if tmcc_id is None:
            tmcc_id = self._scope_tmcc_ids.get(self.scope, 0)
        # update the tmcc_id associated with current scope
        self._scope_tmcc_ids[self.scope] = tmcc_id
        if tmcc_id:
            state = self._state_store.get_state(self.scope, tmcc_id, False)
            if state:
                name = state.name
                name = name if name and name != "NA" else not_found_value
            else:
                name = not_found_value
            self.name_text.value = name
        else:
            self.name_text.value = ""
            state = None
        self.monitor_state()
        # use the callback to update ops button state
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ACC}:
            self._scoped_callbacks.get(self.scope, lambda s: print(f"from uci: {s}"))(state)
            self.app.after(0, self.update_component_image, [tmcc_id])

    def make_emergency_buttons(self, app: App):
        self.emergency_box = emergency_box = Box(app, layout="grid", border=2, align="top")
        _ = Text(emergency_box, text=" ", grid=[0, 0, 3, 1], align="top", size=3, height=1, bold=True)

        self.halt_btn = halt_btn = PushButton(
            emergency_box,
            text=">> Halt <<",
            grid=[0, 1],
            align="top",
            width=10,
            padx=self._text_pad_x,
            pady=self._text_pad_y,
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

        _ = Text(emergency_box, text=" ", grid=[0, 2, 3, 1], align="top", size=3, height=1, bold=True)
        app.update()

    def scale(self, value: int, factor: float = None) -> int:
        orig_value = value
        value = max(orig_value, int(value * self.width / 480))
        if factor is not None and self.width > 480:
            value = max(orig_value, int(factor * value))
        return value

    def when_pressed(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            state = pb.component_state
            if state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1).send()

    def when_released(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            state = pb.component_state
            if state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).send()

    def update_component_image(self, tmcc_id: int = None):
        print("update_component_image:")
        if self.scope in {CommandScope.SWITCH, CommandScope.ROUTE}:
            # routes and switches don't use images
            return
        with self._cv:
            self.image_box.hide()
            if tmcc_id is None:
                tmcc_id = self._scope_tmcc_ids[self.scope]
            prod_info = None
            img = pil_img = None
            if self.scope in {CommandScope.ENGINE} and tmcc_id != 0:
                prod_info = self._engine_cache.get(tmcc_id, None)
                if prod_info is None:
                    # Start thread to fetch product info
                    fetch_thread = Thread(target=self._fetch_prod_info_threaded, args=(tmcc_id,), daemon=True)
                    self._engine_cache[tmcc_id] = fetch_thread
                    fetch_thread.start()
                    return
                if isinstance(prod_info, ProdInfo):
                    # Resize image if needed
                    img = self._engine_image_cache.get(tmcc_id, None)
                    if img is None:
                        img = self.get_scaled_image(BytesIO(prod_info.image_content))
                        self._engine_image_cache[tmcc_id] = img
            elif self.scope in {CommandScope.ACC} and tmcc_id != 0:
                state = self._state_store.get_state(self.scope, tmcc_id, False)
                if isinstance(AccessoryState, state):
                    if state.is_asc2:
                        img = self.get_scaled_image(Image.open(self.asc2_image))
            if img:
                available_height, available_width = self.calc_image_box_size()
                self.engine_image.tk.config(image=img)
                self.engine_image.width = available_width
                self.engine_image.height = available_height
                self.image_box.show()

    def get_scaled_image(self, source: str | io.BytesIO) -> PhotoImage:
        available_height, available_width = self.calc_image_box_size()
        pil_img = Image.open(src)
        orig_width, orig_height = pil_img.size

        # Calculate scaling to fit available space
        width_scale = available_width / orig_width
        height_scale = available_height / orig_height
        scale = min(width_scale, height_scale)

        scaled_width = int(orig_width * width_scale)
        scaled_height = int(orig_height * scale)

        img = ImageTk.PhotoImage(pil_img.resize((scaled_width, scaled_height)))
        return img

    def calc_image_box_size(self) -> tuple[int, int | Any]:
        with self._cv:
            if self.avail_image_height is None or self.avail_image_width is None:
                # Calculate available space for the image
                self.app.update()

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

    def request_prod_info(self, tmcc_id: int | None) -> ProdInfo | None:
        state = self._state_store.get_state(self.scope, tmcc_id, False)
        if state and state.bt_id:
            prod_info = ProdInfo.by_btid(state.bt_id)
        else:
            prod_info = "N/A"
        with self._cv:
            self._engine_cache[tmcc_id] = prod_info
        return prod_info

    def _fetch_prod_info_threaded(self, tmcc_id: int) -> None:
        """Fetch product info in a background thread, then schedule UI update."""
        self.request_prod_info(tmcc_id)
        # Schedule the UI update on the main thread
        self.queue_message(self.update_component_image, tmcc_id)
