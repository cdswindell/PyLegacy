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
from queue import Queue, Empty
from threading import Condition, Event, RLock, Thread, get_ident
from tkinter import TclError
from typing import Callable, Generic, TypeVar, cast, Any

from guizero import App, Box, Combo, PushButton, Text, Slider
from guizero.base import Widget
from guizero.event import EventData

from ..comm.command_listener import CommandDispatcher
from ..db.accessory_state import AccessoryState
from ..db.component_state import ComponentState, RouteState, SwitchState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..pdi.asc2_req import Asc2Req
from ..pdi.constants import Asc2Action, PdiCommand
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
        self.label = label
        self._aggrigator = aggrigator
        self._scale_by = scale_by
        self._text_size: int = 24

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
                nl = len(acc.road_name)
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
                self._set_button_active(pb)
            else:
                self._set_button_inactive(pb)

    # noinspection PyTypeChecker
    def _set_button_inactive(self, widget: Widget):
        widget.bg = self._disabled_bg
        widget.text_color = self._disabled_text

    # noinspection PyTypeChecker
    def _set_button_active(self, widget: Widget):
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
        _ = Text(box, text=" ", grid=[0, 0, 6, 1], size=6, height=1, bold=True)
        _ = Text(box, text="    ", grid=[1, 1], size=ts)
        if self._aggrigator:
            txt_lbl = txt_spacer = None
            ats = int(round(23 * self._scale_by))
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
            label = f"{self.label} {self.title}" if self.label else self.title
            _ = Text(box, text=label, grid=[2, 1, 2, 1], size=ts, bold=True)
        _ = Text(box, text="    ", grid=[4, 1], size=ts)
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
        self.by_name.text_size = self.by_number.text_size = int(round(18 * self._scale_by))
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

        self.app.update()
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
            text=f"#{pd.tmcc_id} {pd.road_name}",
            grid=[col, row],
            width=int(round(self.width / 2 / (13 * self._scale_by))),
            command=self.switch_state,
            args=[pd],
            padx=0,
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


class PowerDistrictsGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        scale_by: float = 1.0,
    ) -> None:
        StateBasedGui.__init__(self, "Power Districts", label, width, height, aggrigator, scale_by=scale_by)

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
        scale_by: float = 1.0,
    ) -> None:
        StateBasedGui.__init__(self, "Switches", label, width, height, aggrigator, disabled_bg="red", scale_by=scale_by)

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
        scale_by: float = 1.0,
    ) -> None:
        StateBasedGui.__init__(self, "Routes", label, width, height, aggrigator, disabled_bg="red", scale_by=scale_by)

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


class MotorsGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        scale_by: float = 1.0,
    ) -> None:
        StateBasedGui.__init__(self, "Motors", label, width, height, aggrigator, scale_by=scale_by)

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            acc = cast(AccessoryState, acc)
            if acc.is_amc2 and acc.road_name and acc.road_name.lower() != "unused":
                pds.append(acc)
        return pds

    def is_active(self, state: AccessoryState) -> bool:
        return False

    def switch_state(self, pd: AccessoryState) -> None:
        pass

    # noinspection PyTypeChecker
    def update_button(self, tmcc_id: int) -> None:
        with self._cv:
            pd = self._states[tmcc_id]
            widgets = self._state_buttons[tmcc_id]
            if isinstance(widgets, list):
                for widget in [x for x in widgets if isinstance(x, PushButton)]:
                    motor = getattr(widget, "motor", None)
                    if motor in {1, 2}:
                        if self.is_motor_active(pd, motor):
                            self._set_button_active(widget)
                        else:
                            self._set_button_inactive(widget)

    @staticmethod
    def is_motor_active(state: AccessoryState, motor: int) -> bool:
        motor = state.get_motor(motor)
        return motor.state if motor else False

    def set_state(self, tmcc_id: int, motor: int, speed: int = None) -> None:
        with self._cv:
            pd: AccessoryState = self._states[tmcc_id]
            if speed is not None:
                pass
            else:
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
                if self.is_motor_active(pd, motor):
                    CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()
                else:
                    CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()

    def _make_state_button(
        self,
        pd: AccessoryState,
        row: int,
        col: int,
    ) -> tuple[list[Widget], int, int]:
        ts = int(round(23 * self._scale_by))
        widgets: list[Widget] = []
        # make title label
        title = Text(self.btn_box, text=f"#{pd.tmcc_id} {pd.road_name}", grid=[col, row, 2, 1], size=ts, bold=True)
        widgets.append(title)
        # make motor 1 on/off button
        row += 1
        m1_pwr, btn_h, btn_y = super()._make_state_button(pd, row, col)
        m1_pwr.text = "Motor #1"
        m1_pwr.motor = 1
        m1_pwr.update_command(self.set_state, args=[pd.tmcc_id, 1])
        if pd.motor1.state:
            self._set_button_active(m1_pwr)
        widgets.append(m1_pwr)

        # motor 1 control
        m1_ctl = Slider(self.btn_box, grid=[col, row + 1], height=btn_h, width="fill")
        m1_ctl.value = pd.motor1.speed
        widgets.append(m1_ctl)

        # make motor 2 on/off button
        m2_pwr, btn_h, btn_y = super()._make_state_button(pd, row, col + 1)
        m2_pwr.text = "Motor #2"
        m2_pwr.motor = 2
        m2_pwr.update_command(self.set_state, args=[pd.tmcc_id, 2])
        if pd.motor2.state:
            self._set_button_active(m2_pwr)
        widgets.append(m2_pwr)
        return widgets, btn_h, btn_y


class AccessoriesGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        scale_by: float = 1.0,
    ) -> None:
        self._is_momentary = set()
        self._released_events = dict[int, Event]()
        StateBasedGui.__init__(self, "Accessories", label, width, height, aggrigator, scale_by=scale_by)

    def _post_process_state_buttons(self) -> None:
        for tmcc_id in self._is_momentary:
            if tmcc_id in self._state_buttons:
                pb = self._state_buttons[tmcc_id]
                pb.when_left_button_pressed = self.when_pressed
                pb.when_left_button_released = self.when_released

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            acc = cast(AccessoryState, acc)
            if acc.is_power_district or acc.is_sensor_track or acc.is_amc2:
                continue
            if acc.road_name and acc.road_name.lower().strip() != "unused":
                pds.append(acc)
                name_lc = acc.road_name.lower()
                if "aux1" in name_lc or "ax1" in name_lc or "(a1)" in name_lc or "(m)" in name_lc:
                    self._is_momentary.add(acc.address)
        return pds

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, pd: AccessoryState) -> None:
        with self._cv:
            if pd.tmcc_id in self._is_momentary:
                pass
            elif pd.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()

    def when_pressed(self, event: EventData) -> None:
        pb = event.widget
        state = pb.component_state
        if state.is_asc2:
            Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1).send()
        else:
            if state.tmcc_id in self._released_events:
                event = self._released_events[state.tmcc_id]
                self._released_events[state.tmcc_id].clear()
            else:
                self._released_events[state.tmcc_id] = event = Event()
            _ = MomentaryActionHandler(pb, event, state, 0.2)
        # self.app.after(10, self._set_button_active, [event.widget])

    def when_released(self, event: EventData) -> None:
        state = event.widget.component_state
        if state.is_asc2:
            Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).send()
        else:
            state = event.widget.component_state
            self._released_events[state.tmcc_id].set()
        # self.app.after(10, self._set_button_inactive, [event.widget])


class ComponentStateGui(Thread):
    def __init__(
        self,
        label: str = None,
        initial: str = "Power Districts",
        width: int = None,
        height: int = None,
        scale_by: float = 1.0,
    ) -> None:
        super().__init__(daemon=True)
        self._ev = Event()
        self._guis = {
            "Accessories": AccessoriesGui,
            "Motors": MotorsGui,
            "Power Districts": PowerDistrictsGui,
            "Routes": RoutesGui,
            "Switches": SwitchesGui,
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
        self._scale_by = scale_by
        self._gui = None
        self.requested_gui = initial

        self.start()

    def run(self) -> None:
        # create the initially requested gui
        self._gui = self._guis[self.requested_gui](
            self.label, self.width, self.height, aggrigator=self, scale_by=self._scale_by
        )

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
            self._gui = self._guis[self.requested_gui](
                self.label, self.width, self.height, aggrigator=self, scale_by=self._scale_by
            )

    def cycle_gui(self, gui: str):
        if gui in self._guis:
            self.requested_gui = gui
            self._ev.set()

    @property
    def guis(self) -> list[str]:
        return list(self._guis.keys())


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
