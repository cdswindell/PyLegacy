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
from threading import Condition, Event, RLock, Thread, get_ident
from tkinter import TclError
from typing import Callable, Generic, TypeVar, cast

from guizero import App, Box, Combo, PushButton, Text

from ..comm.command_listener import CommandDispatcher
from ..db.accessory_state import AccessoryState
from ..db.component_state import ComponentState, RouteState, SwitchState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum, TMCC1RouteCommandEnum, TMCC1SwitchCommandEnum
from ..utils.path_utils import find_file

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)


class StateBasedGui(Thread, Generic[S], ABC):
    __metaclass__ = ABCMeta

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
        self._app_active = False

        # States
        self._states = dict[int, S]()
        self._state_buttons = dict[int, PushButton]()
        self._state_watchers = dict[int, StateWatcher]()

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

        self._is_closed = False

        # Thread-aware shutdown signaling
        self._tk_thread_id: int | None = None
        self._shutdown_flag = Event()

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
                nl = len(acc.road_name)
                self._max_name_len = nl if nl > self._max_name_len else self._max_name_len
                self._states[acc.tmcc_id] = acc
                self._state_watchers[acc.tmcc_id] = StateWatcher(acc, self.on_state_change_action(acc))

            # start GUI
            self.start()

    # noinspection PyTypeChecker
    def update_button(self, pd: S) -> None:
        with self._cv:
            if self.is_active(pd):
                self._state_buttons[pd.tmcc_id].bg = self._enabled_bg
                self._state_buttons[pd.tmcc_id].text_color = self._enabled_text
            else:
                self._state_buttons[pd.tmcc_id].bg = self._disabled_bg
                self._state_buttons[pd.tmcc_id].text_color = self._disabled_text

    def on_state_change_action(self, pd: S) -> Callable:
        def upd():
            self.update_button(pd)

        return upd

    def run(self) -> None:
        self._ev.clear()
        self._tk_thread_id = get_ident()
        GpioHandler.cache_handler(self)
        self.app = app = App(title=self.title, width=self.width, height=self.height)
        app.full_screen = True
        app.when_closed = self.close

        # poll for shutdown requests from other threads; this runs on the GuiZero/Tk thread
        def _poll_shutdown():
            if self._shutdown_flag.is_set():
                try:
                    app.destroy()
                except TclError:
                    pass  # ignore, we're shutting down
                return None
            return None

        app.repeat(500, _poll_shutdown)

        self.box = box = Box(app, layout="grid")
        app.bg = box.bg = "white"

        _ = Text(box, text=" ", grid=[0, 0, 6, 1], size=6, height=1, bold=True)
        _ = Text(box, text="    ", grid=[1, 1], size=24)
        if self._aggrigator:
            ag_box = Box(box, grid=[2, 1, 2, 1])
            if self.label:
                _ = Text(ag_box, text=self.label, align="left", size=24, bold=True, height="fill")
            self.aggrigator_combo = Combo(
                ag_box,
                options=self._aggrigator.guis,
                selected=self.title,
                align="right",
                command=self.on_combo_change,
            )
            self.aggrigator_combo.text_size = 24
            self.aggrigator_combo.text_bold = True
        else:
            # customize label
            label = f"{self.label} {self.title}" if self.label else self.title

            _ = Text(box, text=label, grid=[2, 1, 2, 1], size=24, bold=True)
        _ = Text(box, text="    ", grid=[4, 1], size=24)
        self.by_number = PushButton(
            box,
            text="By TMCC ID",
            grid=[2, 2],
            command=self.sort_by_number,
            padx=5,
            pady=5,
        )
        self.by_name = PushButton(
            box,
            text="By Name",
            grid=[3, 2],
            width=len("By TMCC ID"),
            command=self.sort_by_name,
            padx=5,
            pady=5,
        )
        self.by_name.text_size = self.by_number.text_size = 18
        self.by_number.text_bold = True
        _ = Text(box, text=" ", grid=[0, 3, 6, 1], size=4, height=1, bold=True)
        self.app.update()

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

        self.y_offset = self.box.tk.winfo_y() + self.box.tk.winfo_height()

        # put the buttons in a separate box
        self.btn_box = Box(app, layout="grid")

        # define power district push buttons
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
            pdb.hide()
            pdb.destroy()
        self._state_buttons.clear()

    # noinspection PyTypeChecker
    def _make_state_buttons(self, states: list[S] = None) -> None:
        with self._cv:
            if self._app_active:
                self._reset_state_buttons()
            active_cols = {self._first_button_col, self._first_button_col + 1}
            row = 4
            col = 0

            btn_h = self.pd_button_height
            btn_y = 0
            self.right_scroll_btn.disable()
            self.left_scroll_btn.disable()

            self.btn_box.visible = False
            for pd in states:
                if btn_h is not None and btn_y is not None and self.y_offset + btn_y + btn_h > self.height:
                    if self._max_button_rows is None:
                        self._max_button_rows = row - 4
                    btn_y = 0
                    row = 4
                    col += 1
                if col in active_cols:
                    self._state_buttons[pd.tmcc_id] = PushButton(
                        self.btn_box,
                        text=f"#{pd.tmcc_id} {pd.road_name}",
                        grid=[col, row],
                        width=int(self.width / 2 / 13),
                        command=self.switch_state,
                        args=[pd],
                        padx=0,
                    )
                    self._state_buttons[pd.tmcc_id].text_size = 15
                    self._state_buttons[pd.tmcc_id].bg = self._enabled_bg if self.is_active(pd) else self._disabled_bg
                    self._state_buttons[pd.tmcc_id].text_color = (
                        self._enabled_text if self.is_active(pd) else self._disabled_text
                    )

                    # recalculate height
                    self.app.update()
                    if self.pd_button_width is None:
                        self.pd_button_width = self._state_buttons[pd.tmcc_id].tk.winfo_width()
                    if self.pd_button_height is None:
                        btn_h = self.pd_button_height = self._state_buttons[pd.tmcc_id].tk.winfo_height()
                    btn_y = self._state_buttons[pd.tmcc_id].tk.winfo_y() + btn_h
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
            self.btn_box.visible = True

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

    @abstractmethod
    def get_target_states(self) -> list[S]: ...

    @abstractmethod
    def is_active(self, state: S) -> bool: ...

    @abstractmethod
    def switch_state(self, state: S) -> bool: ...


class PowerDistrictsGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
    ) -> None:
        StateBasedGui.__init__(self, "Power Districts", label, width, height, aggrigator)

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            acc = cast(AccessoryState, acc)
            if acc.is_power_district is True and acc.road_name and acc.road_name.lower() != "unused":
                pds.append(acc)
        return pds

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, pd: AccessoryState) -> None:
        with self._cv:
            if pd.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, pd.tmcc_id).send()


class SwitchesGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
    ) -> None:
        StateBasedGui.__init__(self, "Switches", label, width, height, aggrigator, disabled_bg="red")

    def get_target_states(self) -> list[SwitchState]:
        pds: list[SwitchState] = []
        accs = self._state_store.get_all(CommandScope.SWITCH)
        for acc in accs:
            acc = cast(SwitchState, acc)
            if acc.road_name and acc.road_name.lower() != "unused":
                pds.append(acc)
        return pds

    def is_active(self, state: SwitchState) -> bool:
        return state.is_thru

    def switch_state(self, pd: SwitchState) -> None:
        with self._cv:
            if pd.is_thru:
                CommandReq(TMCC1SwitchCommandEnum.OUT, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1SwitchCommandEnum.THRU, pd.tmcc_id).send()


class RoutesGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
    ) -> None:
        StateBasedGui.__init__(self, "Routes", label, width, height, aggrigator, disabled_bg="red")

    def get_target_states(self) -> list[RouteState]:
        pds: list[RouteState] = []
        accs = self._state_store.get_all(CommandScope.ROUTE)
        for acc in accs:
            acc = cast(RouteState, acc)
            if acc.road_name and acc.road_name.lower() != "unused":
                pds.append(acc)
        return pds

    def is_active(self, state: RouteState) -> bool:
        return state.is_active

    def switch_state(self, pd: RouteState) -> None:
        with self._cv:
            if pd.is_active:
                CommandReq(TMCC1RouteCommandEnum.FIRE, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1RouteCommandEnum.FIRE, pd.tmcc_id).send()


class AccessoriesGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
    ) -> None:
        StateBasedGui.__init__(self, "Accessories", label, width, height, aggrigator)

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            acc = cast(AccessoryState, acc)
            if acc.is_power_district or acc.is_sensor_track:
                continue
            if acc.road_name and acc.road_name.lower() != "unused":
                pds.append(acc)
        return pds

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, pd: AccessoryState) -> None:
        with self._cv:
            if pd.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()


class ComponentStateGui(Thread):
    def __init__(
        self,
        label: str = None,
        initial: str = "Power Districts",
        width: int = None,
        height: int = None,
    ) -> None:
        super().__init__(daemon=True)
        self._ev = Event()
        self._guis = {
            # "Accessories": AccessoriesGui,
            "Power Districts": PowerDistrictsGui,
            "Switches": SwitchesGui,
            "Routes": RoutesGui,
        }
        # verify requested GUI exists:
        if initial not in self._guis:
            raise ValueError(f"Invalid initial GUI: {initial}")

        self.label = label
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
        self._gui = None
        self.requested_gui = initial

        self.start()

    def run(self) -> None:
        # create the initially requested gui
        self._gui = self._guis[self.requested_gui](self.label, self.width, self.height, aggrigator=self)

        # wait for user to request a different GUI
        while True:
            # Wait for request to change GUI
            self._ev.wait()
            self._ev.clear()

            # Close/destroy previous GUI
            GpioHandler.release_handler(self._gui)

            # wait for Gui to be destroyed
            self._gui.destroy_complete.wait(10)
            self._gui.join()
            # clean up state
            self._gui = None

            # create and display new gui
            self._gui = self._guis[self.requested_gui](self.label, self.width, self.height, aggrigator=self)

    def cycle_gui(self, gui: str):
        if gui in self._guis:
            self.requested_gui = gui
            self._ev.set()

    @property
    def guis(self) -> list[str]:
        return list(self._guis.keys())
