#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
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

from guizero import App, Box, Combo, PushButton, Text
from guizero.base import Widget

from ..comm.command_listener import CommandDispatcher
from ..db.component_state import ComponentState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.constants import CommandScope
from ..utils.path_utils import find_file
from .component_state_gui import ComponentStateGui

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)


class StateBasedGui(Thread, Generic[S], ABC):
    __metaclass__ = ABCMeta

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @abstractmethod
    def __init__(
        self,
        title: str,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        enabled_bg: str = "green",
        disabled_bg: str = "black",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
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
        self.label = label
        self._aggrigator = aggrigator
        self._scale_by = scale_by
        self._exclude_unnamed = exclude_unnamed
        self._text_size: int = 24
        self._button_pad_x = 20
        self._button_pad_y = 10
        self._button_text_pad_x = 10
        self._button_text_pad_y = 12

        self._enabled_bg = enabled_bg
        self._disabled_bg = disabled_bg
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self.left_arrow = find_file("left_arrow.jpg")
        self.right_arrow = find_file("right_arrow.jpg")
        self.app = self.by_name = self.by_number = self.box = self.btn_box = self.y_offset = None
        self.pd_button_height = self.pd_button_width = self.left_scroll_btn = self.right_scroll_btn = None
        self.aggrigator_combo = None
        self._max_name_len = 0
        self._max_button_rows = self._max_button_cols = None
        self._first_button_col = 0
        self.sort_func = None
        self._app_counter = 0
        self._message_queue = Queue()

        # States
        self._states = dict[tuple[int, CommandScope], S]()
        self._state_buttons = dict[S, PushButton]()
        self._state_watchers = dict[S, StateWatcher]()

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
                if acc is None:
                    continue
                if self._exclude_unnamed and not acc.is_name:
                    continue
                # noinspection PyUnresolvedReferences
                if acc.road_name and "unused" in acc.road_name.lower():
                    continue
                nl = len(acc.road_name)
                self._max_name_len = nl if nl > self._max_name_len else self._max_name_len
                self._states[(acc.tmcc_id, acc.scope)] = acc
                self._state_watchers[acc] = StateWatcher(acc, self.on_state_change_action(acc))

            # start GUI
            self.start()

    # noinspection PyTypeChecker
    def update_button(self, state: S) -> None:
        with self._cv:
            # pd: S = self._states[tmcc_id]
            pb = self._state_buttons[state]
            if self.is_active(state):
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

    def on_state_change_action(self, state: S) -> Callable:
        def upd():
            if not self._shutdown_flag.is_set():
                self._message_queue.put((self.update_button, [state]))

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
        _ = Text(box, text=" ", grid=[0, 0, 6, 1], size=6, height=1, bold=True)
        _ = Text(box, text="    ", grid=[1, 1], size=ts)
        ats = int(round(23 * self._scale_by))
        if self._aggrigator:
            txt_lbl = txt_spacer = None
            ag_box = Box(box, grid=[2, 1, 2, 1], layout="auto")
            if self.label:
                # Wrap the Text in a vertical container so we can insert a spacer above it
                txt_vbox = Box(ag_box, layout="auto", align="left")
                txt_spacer = Box(txt_vbox, height=1, width=1)  # will be set after measuring
                txt_lbl = Text(txt_vbox, text=self.label + ": ", align="top", size=ats, bold=True)
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
            if self.label:
                # After creation, force layout and measure actual heights
                self.app.update()
                txt_h = txt_lbl.tk.winfo_height() if self.label else 0
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
            label = f"{self.label}: {self.title}" if self.label else self.title
            _ = Text(box, text=label, grid=[2, 1, 2, 1], size=ats, bold=True)
        _ = Text(box, text="    ", grid=[4, 1], size=ts)
        self.by_number = PushButton(
            box,
            text="By TMCC ID",
            grid=[2, 2],
            command=self.sort_by_number,
            padx=self._button_text_pad_x,
            pady=self._button_text_pad_y,
        )

        self.by_name = PushButton(
            box,
            text="By Name",
            grid=[3, 2],
            width=len("By TMCC ID"),
            command=self.sort_by_name,
            padx=self._button_text_pad_x,
            pady=self._button_text_pad_y,
        )
        self.by_name.text_size = self.by_number.text_size = int(round(18 * self._scale_by))
        self.by_number.text_bold = True

        _ = Text(box, text=" ", grid=[0, 3, 6, 1], size=4, height=1, bold=True)
        self.app.update()

        parent = self.by_number.tk.master
        parent.grid_columnconfigure(self.by_number.tk.grid_info()["column"], pad=40)
        parent.grid_columnconfigure(self.by_name.tk.grid_info()["column"], pad=40)
        parent.grid_rowconfigure(self.by_number.tk.grid_info()["row"], pad=10)

        # add scroll btns
        sort_btn_height = self.by_number.tk.winfo_height()
        self.left_scroll_btn = PushButton(
            box,
            grid=[0, 1, 1, 2],
            enabled=False,
            image=self.left_arrow,
            height=sort_btn_height * 2,
            width=sort_btn_height * 2,
            align="left",
            command=self.scroll_left,
        )
        self.right_scroll_btn = PushButton(
            box,
            grid=[5, 1, 1, 2],
            enabled=False,
            image=self.right_arrow,
            height=sort_btn_height * 2,
            width=sort_btn_height * 2,
            align="right",
            command=self.scroll_right,
        )

        self.app.update()
        self.y_offset = self.box.tk.winfo_y() + self.box.tk.winfo_height()

        # put the buttons in a separate box
        self.btn_box = Box(app, layout="grid")

        # Order by tmcc_id
        self.sort_by_number()

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
            self.left_scroll_btn = None
            self.right_scroll_btn = None
            self.by_name = None
            self.by_number = None
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
            self.right_scroll_btn.disable()
            self.left_scroll_btn.disable()
            self.by_name.show()
            self.by_number.show()

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
                    self._state_buttons[pd] = pb
                else:
                    btn_y += btn_h
                row += 1
            # logic to hide/disable/enable scroll buttons
            if col <= 1:
                self.right_scroll_btn.hide()
                self.left_scroll_btn.hide()
            else:
                if max(active_cols) < col:
                    self.right_scroll_btn.enable()
                if max(active_cols) > 1:
                    self.left_scroll_btn.enable()

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
            text=f"{pd.tmcc_id}) {pd.road_name}",
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

    def sort_by_number(self) -> None:
        self.by_number.text_bold = True
        self.by_name.text_bold = False

        self.sort_func = lambda x: x.tmcc_id
        states = sorted(self._states.values(), key=self.sort_func)
        self._first_button_col = 0
        self._make_state_buttons(states)

    def sort_by_name(self) -> None:
        self.by_name.text_bold = True
        self.by_number.text_bold = False

        self.sort_func = lambda x: x.road_name.lower()
        states = sorted(self._states.values(), key=self.sort_func)
        self._first_button_col = 0
        self._make_state_buttons(states)

    def scroll_left(self) -> None:
        self._first_button_col -= 1
        states = sorted(self._states.values(), key=self.sort_func)
        self._make_state_buttons(states)

    def scroll_right(self) -> None:
        self._first_button_col += 1
        states = sorted(self._states.values(), key=self.sort_func)
        self._make_state_buttons(states)

    def _post_process_state_buttons(self) -> None:
        pass

    @abstractmethod
    def get_target_states(self) -> list[S]: ...

    @abstractmethod
    def is_active(self, state: S) -> bool: ...

    @abstractmethod
    def switch_state(self, state: S) -> bool: ...


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
