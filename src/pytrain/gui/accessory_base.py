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
import logging
from abc import ABC, ABCMeta, abstractmethod
from queue import Empty, Queue
from threading import Condition, Event, RLock, Thread, get_ident
from tkinter import TclError
from typing import Any, Callable, Generic, TypeVar

from guizero import App, Box, Combo, Picture, PushButton, Text
from guizero.base import Widget

from ..comm.command_listener import CommandDispatcher
from ..db.component_state import ComponentState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.constants import CommandScope
from .component_state_gui import ComponentStateGui

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)


class AccessoryBase(Thread, Generic[S], ABC):
    __metaclass__ = ABCMeta

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @abstractmethod
    def __init__(
        self,
        title: str,
        image_file: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        enabled_bg: str = "green",
        disabled_bg: str = "black",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        scale_by: float = 1.0,
    ) -> None:
        Thread.__init__(self, daemon=True, name=f"{title} GUI")
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
        self.title = title
        self.image_file = image_file
        self._aggrigator = aggrigator
        self._scale_by = scale_by
        self._text_size: int = 24
        self._button_pad_x = 20
        self._button_pad_y = 10
        self._button_text_pad_x = 10
        self._button_text_pad_y = 12

        self._enabled_bg = enabled_bg
        self._disabled_bg = disabled_bg
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self.app = self.box = self.btn_box = self.y_offset = None
        self.pd_button_height = self.pd_button_width = None
        self.aggrigator_combo = None
        self._max_name_len = 0
        self._max_button_rows = self._max_button_cols = None
        self._first_button_col = 0
        self.sort_func = None
        self._app_counter = 0
        self._message_queue = Queue()

        # States
        self._states = dict[int, S]()
        self._state_buttons = dict[int, PushButton]()
        self._state_watchers = dict[int, StateWatcher]()

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

            # get all target states; watch for state changes
            accs = self.get_target_states()
            for acc in accs:
                nl = len(acc.road_name) if acc.road_name else 0
                self._max_name_len = nl if nl > self._max_name_len else self._max_name_len
                self._states[acc.tmcc_id] = acc
                self._state_watchers[acc.tmcc_id] = StateWatcher(acc, self.on_state_change_action(acc.tmcc_id))

            # start GUI
            self.start()

    # noinspection PyTypeChecker
    def update_button(self, tmcc_id: int) -> None:
        with self._cv:
            pd: S = self._states[tmcc_id]
            pb = self._state_buttons[tmcc_id]
            if self.is_active(pd):
                self.set_button_active(pb)
            else:
                self.set_button_inactive(pb)

    # noinspection PyTypeChecker
    def set_button_inactive(self, widget: Widget):
        widget.bg = self._disabled_bg
        widget.text_color = self._disabled_text

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget):
        widget.bg = self._enabled_bg
        widget.text_color = self._enabled_text

    def on_state_change_action(self, tmcc_id: int) -> Callable:
        def upd():
            if not self._shutdown_flag.is_set():
                self._message_queue.put((self.update_button, [tmcc_id]))

        return upd

    # noinspection PyTypeChecker
    def run(self) -> None:
        self._shutdown_flag.clear()
        self._ev.clear()
        self._tk_thread_id = get_ident()
        GpioHandler.cache_handler(self)
        self.app = app = App(title=self.title, width=self.width, height=self.height)
        app.full_screen = True
        app.when_closed = self.close

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
                try:
                    message = self._message_queue.get_nowait()
                    if isinstance(message, tuple):
                        message[0](*message[1])
                except Empty:
                    pass
            return None

        app.repeat(25, _poll_shutdown)

        self.box = box = Box(app, layout="grid")
        app.bg = box.bg = "white"

        ts = self._text_size
        row_num = 0
        _ = Text(box, text=" ", grid=[0, row_num, 1, 1], size=6, height=1, bold=True)
        row_num += 1
        ats = int(round(23 * self._scale_by))
        if self._aggrigator:
            txt_lbl = txt_spacer = None
            ag_box = Box(box, grid=[2, 1, 2, 1], layout="auto")
            if self.title:
                # Wrap the Text in a vertical container so we can insert a spacer above it
                txt_vbox = Box(ag_box, layout="auto", align="left")
                txt_spacer = Box(txt_vbox, height=1, width=1)  # will be set after measuring
                txt_lbl = Text(txt_vbox, text=self.title + ": ", align="top", size=ats, bold=True)
            # Wrap the Combo in a vertical container as well
            combo_vbox = Box(ag_box, layout="auto", align="right")
            combo_spacer = Box(combo_vbox)  # will be set after measuring
            self.aggrigator_combo = Combo(
                combo_vbox,
                options=self._aggrigator.guis,
                selected=self.title,
                align="top",
                command=self.on_combo_change,
            )
            self.aggrigator_combo.text_size = ats
            self.aggrigator_combo.text_bold = True

            # Compute center-offset and add top spacer to the shorter control
            if self.title:
                # After creation, force layout and measure actual heights
                self.app.update()
                txt_h = txt_lbl.tk.winfo_height() if self.title else 0
                combo_h = self.aggrigator_combo.tk.winfo_height()
                if txt_h < combo_h:
                    delta = (combo_h - txt_h) // 2
                    txt_spacer.height = max(0, delta)
                    combo_spacer.height = 0
                elif combo_h < txt_h:
                    delta = (txt_h - combo_h) // 2
                    combo_spacer.height = max(0, delta)
                    txt_spacer.height = 0
                else:
                    txt_spacer.height = combo_spacer.height = 0
            else:
                # No label Text; ensure combo is not offset
                combo_spacer.height = 0
        else:
            # customize label
            label = self.title
            _ = Text(box, text=label, grid=[0, row_num], size=ats, bold=True)
            row_num += 1
        _ = Text(box, text="    ", grid=[0, row_num], size=ts)
        row_num += 1

        if self.image_file:
            image_height = int(round(self.height * 0.30))
            _ = Picture(box, image=self.image_file, grid=[0, row_num], height=image_height)
            row_num += 1

        self.app.update()
        self.y_offset = self.box.tk.winfo_y() + self.box.tk.winfo_height()

        # put the buttons in a separate box
        self.btn_box = Box(app, layout="grid")

        # build state buttons
        self.build_accessory_controls()

        # Display GUI and start event loop; call blocks
        try:
            app.display()
        except TclError:
            # If Tcl is already tearing down, ignore
            pass
        finally:
            # Explicitly drop references to tkinter/guizero objects on the Tk thread
            if self._aggrigator:
                for sw in self._state_watchers.values():
                    sw.shutdown()
                self._state_watchers.clear()
            self.aggrigator_combo = None
            self.btn_box = None
            self.box = None
            self._state_buttons.clear()
            self._state_buttons = None
            self.app = None
            self._ev.set()

    def on_combo_change(self, option: str) -> None:
        if option == self.title:
            return  # Noop
        else:
            self._aggrigator.cycle_gui(option)

    # noinspection PyUnusedLocal
    def _reset_state_buttons(self) -> None:
        for pdb in self._state_buttons.values():
            if not isinstance(pdb, list):
                pdb = [pdb]
            for widget in pdb:
                if hasattr(widget, "component_state"):
                    widget.component_state = None
                if hasattr(widget, "when_left_button_pressed"):
                    widget.when_left_button_pressed = None
                if hasattr(widget, "when_left_button_released"):
                    widget.when_left_button_released = None
                widget.hide()
                widget.destroy()
        self._state_buttons.clear()

    # noinspection PyTypeChecker
    def _make_state_buttons(self, states: list[S] = None) -> None:
        with self._cv:
            if self._state_buttons:
                self._reset_state_buttons()
            active_cols = {self._first_button_col, self._first_button_col + 1}
            row = 4
            col = 0

            btn_h = self.pd_button_height
            btn_y = 0

            self.btn_box.visible = False
            for pd in states:
                if btn_h is not None and btn_y is not None and self.y_offset + btn_y + btn_h > self.height:
                    if self._max_button_rows is None:
                        self._max_button_rows = row - 4
                    btn_y = 0
                    row = 4
                    col += 1
                if col in active_cols:
                    pb, btn_h, btn_y = self._make_state_button(pd, row, col)
                    self._state_buttons[pd.tmcc_id] = pb
                else:
                    btn_y += btn_h
                row += 1

            # call post process handler
            self._post_process_state_buttons()
            self.btn_box.visible = True

    def _make_state_button(
        self,
        pd: S | Any,
        row: int,
        col: int,
    ) -> tuple[PushButton | list[Widget], int, int]:
        pb = PushButton(
            self.btn_box,
            text=f"#{pd.tmcc_id} {pd.road_name}",
            grid=[col, row],
            width=int(round(self.width / 2 / (13 * self._scale_by))),
            command=self.switch_state,
            args=[pd],
            padx=0,
            pady=self._button_text_pad_y,
        )
        pb.component_state = pd
        pb.text_size = int(round(15 * self._scale_by))
        pb.bg = self._enabled_bg if self.is_active(pd) else self._disabled_bg
        pb.text_color = self._enabled_text if self.is_active(pd) else self._disabled_text

        # recalculate height
        self.app.update()
        if self.pd_button_width is None:
            self.pd_button_width = pb.tk.winfo_width()
        if self.pd_button_height is None:
            btn_h = self.pd_button_height = pb.tk.winfo_height()
        else:
            btn_h = self.pd_button_height
        btn_y = pb.tk.winfo_y() + btn_h
        return pb, btn_h, btn_y

    def _post_process_state_buttons(self) -> None:
        pass

    @abstractmethod
    def get_target_states(self) -> list[S]: ...

    @abstractmethod
    def is_active(self, state: S) -> bool: ...

    @abstractmethod
    def switch_state(self, state: S) -> bool: ...

    @abstractmethod
    def build_accessory_controls(self) -> None: ...


class MomentaryActionHandler(Thread, Generic[S]):
    def __init__(self, widget: PushButton, event: Event, state: S, timeout: float) -> None:
        super().__init__(daemon=True)
        self._widget = widget
        self._ev = event
        self._state = state
        self._timeout = timeout
        self.start()

    def run(self) -> None:
        while not self._ev.wait(self._timeout):
            if not self._ev.is_set():
                print("still pressed")
            else:
                break
