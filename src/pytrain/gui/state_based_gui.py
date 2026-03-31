#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from __future__ import annotations

import logging
from abc import ABC, ABCMeta, abstractmethod
from threading import Event, Thread
from tkinter import TclError
from typing import Any, Callable, Generic, TypeVar

from guizero import Box, Combo, PushButton, Text
from guizero.base import Widget

from .component_state_gui import ComponentStateGui
from .components.hold_button import HoldButton
from .guizero_base import GuiZeroBase
from ..db.component_state import ComponentState
from ..db.state_watcher import StateWatcher
from ..protocol.constants import CommandScope
from ..utils.path_utils import find_file

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)
GUI_CLEANUP_EXCEPTIONS = (AttributeError, RuntimeError, TclError, TypeError)


class StateBasedGui(GuiZeroBase, Generic[S], ABC):
    __metaclass__ = ABCMeta
    _MAX_VIRTUAL_SCREENS = 3
    _COLS_PER_SCREEN = 2
    _AUTO_SCREEN_WIDTH = 800

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
        aggregator: ComponentStateGui = None,
        enabled_bg: str = "green",
        disabled_bg: str = "black",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
        screens: int | None = None,
        stand_alone: bool = True,
        parent: Box | None = None,
        full_screen: bool = True,
        x_offset: int = 0,
        y_offset: int = 0,
    ) -> None:
        GuiZeroBase.__init__(
            self,
            title=f"{title if title else 'Component'} GUI",
            width=width,
            height=height,
            enabled_bg=enabled_bg,
            disabled_bg=disabled_bg,
            enabled_text=enabled_text,
            disabled_text=disabled_text,
            scale_by=scale_by,
            stand_alone=stand_alone,
            full_screen=full_screen,
            x_offset=x_offset,
            y_offset=y_offset,
        )
        # State-based screens create/destroy many guizero widgets while switching.
        self.title = title
        self.label = label
        self._aggregator = aggregator
        self._scale_by = scale_by
        self._exclude_unnamed = exclude_unnamed
        self._parent = parent
        self._text_size: int = 24
        self._button_text_pad_x = 10
        self._button_text_pad_y = 12
        self._show_title = True

        self.left_arrow = find_file("left_arrow.jpg")
        self.right_arrow = find_file("right_arrow.jpg")
        self.by_name = self.by_number = self.box = self.btn_box = self.y_offset = None
        self.pd_button_height = self.pd_button_width = self.left_scroll_btn = self.right_scroll_btn = None
        self.aggregator_combo = None
        self._max_name_len = 0
        self._max_button_rows = self._max_button_cols = None
        self._first_button_col = 0
        self.sort_func = None
        self._screens = self._resolve_screens(screens)
        self._visible_button_cols = max(1, self._screens * self._COLS_PER_SCREEN)

        # States
        self._states = dict[tuple[int, CommandScope], S]()
        self._state_buttons = dict[S, PushButton]()
        self._state_watchers = dict[S, StateWatcher]()

        # Signal parent init is complete
        self.init_complete()

    @classmethod
    def _clamp_screens(cls, screens: int) -> int:
        return max(1, min(cls._MAX_VIRTUAL_SCREENS, screens))

    def _resolve_screens(self, screens: int | None) -> int:
        if screens is not None:
            return self._clamp_screens(int(screens))
        if self.width:
            auto = int(self.width // self._AUTO_SCREEN_WIDTH)
            return self._clamp_screens(auto if auto > 0 else 1)
        return 1

    def calc_image_box_size(self) -> tuple[int, int | Any]:
        pass

    # noinspection PyTypeChecker
    def _get_target_states(self) -> None:
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

    # noinspection PyTypeChecker
    def update_button(self, state: S) -> None:
        with self._cv:
            if state in self._state_buttons:
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
            if not self._shutdown_flag.is_set() and state in self._state_buttons:
                self._message_queue.put((self.update_button, [state]))

        return upd

    # noinspection PyTypeChecker
    def build_gui(self) -> None:
        self._get_target_states()

        app = self.app
        gui_parent = self._parent if self._parent is not None else app
        self.box = box = Box(gui_parent, layout="grid")
        if self._parent is None:
            app.bg = "white"
        box.bg = "white"

        show_header_row = self._aggregator is not None or self._show_title
        sort_row = 2 if show_header_row else 0
        below_sort_row = sort_row + 1

        ts = self._text_size
        if show_header_row:
            h1 = Text(box, text=" ", grid=[0, 0, 6, 1], size=6, height=1, bold=True)
            h2 = Text(box, text="    ", grid=[1, 1], size=ts)
            self.cache(h1, h2)
        ats = int(round(23 * self._scale_by))
        if self._aggregator:
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
            self.cache(txt_lbl, txt_spacer, combo_vbox, combo_spacer, ag_box)
            self.aggregator_combo = Combo(
                combo_vbox,
                options=self._aggregator.guis,
                selected=self.title,
                align="top",
                command=self.on_combo_change,
            )
            self.aggregator_combo.text_size = ats
            self.aggregator_combo.text_bold = True

            # Compute center-offset and add top spacer to the shorter control
            if self.label:
                # After creation, force layout and measure actual heights
                self.app.update()
                txt_h = txt_lbl.tk.winfo_height() if self.label else 0
                combo_h = self.aggregator_combo.tk.winfo_height()
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
            if self._show_title:
                # customize label
                label = f"{self.label}: {self.title}" if self.label else self.title
                tb = Text(box, text=label, grid=[2, 1, 2, 1], size=ats, bold=True)
                self.cache(tb)
        if show_header_row:
            sp = Text(box, text="    ", grid=[4, 1], size=ts)
            self.cache(sp)
        self.by_number = PushButton(
            box,
            text="By TMCC ID",
            grid=[2, sort_row],
            command=self.sort_by_number,
            padx=self._button_text_pad_x,
            pady=self._button_text_pad_y,
        )

        self.by_name = PushButton(
            box,
            text="By Name",
            grid=[3, sort_row],
            width=len("By TMCC ID"),
            command=self.sort_by_name,
            padx=self._button_text_pad_x,
            pady=self._button_text_pad_y,
        )
        self.by_name.text_size = self.by_number.text_size = int(round(18 * self._scale_by))
        self.by_number.text_bold = True

        sp = Text(box, text=" ", grid=[0, below_sort_row, 6, 1], size=4, height=1, bold=True)
        self.cache(sp)
        self.app.update()

        tk_parent = self.by_number.tk.master
        tk_parent.grid_columnconfigure(self.by_number.tk.grid_info()["column"], pad=40)
        tk_parent.grid_columnconfigure(self.by_name.tk.grid_info()["column"], pad=40)
        tk_parent.grid_rowconfigure(self.by_number.tk.grid_info()["row"], pad=0)

        # add scroll btns
        sort_btn_height = self.by_number.tk.winfo_height()
        scroll_btn_size = sort_btn_height
        self.left_scroll_btn = PushButton(
            box,
            grid=[0, sort_row] if self.width > 480 else [2, below_sort_row, 1, 1],
            enabled=False,
            image=self.left_arrow,
            height=scroll_btn_size,
            width=scroll_btn_size,
            align="left",
            command=self.scroll_left,
        )
        self.right_scroll_btn = PushButton(
            box,
            grid=[5, sort_row] if self.width > 480 else [3, below_sort_row, 1, 1],
            enabled=False,
            image=self.right_arrow,
            height=scroll_btn_size,
            width=scroll_btn_size,
            align="right",
            command=self.scroll_right,
        )

        app.update()
        self.y_offset = self.box.tk.winfo_y() + self.box.tk.winfo_height()

        # put the buttons in a separate box
        self.btn_box = Box(gui_parent, layout="grid")

        # Order by tmcc_id
        self.sort_by_number()

    def destroy_gui(self) -> None:
        # Explicitly drop references to tkinter/guizero objects on the Tk thread
        for sw in self._state_watchers.values():
            sw.shutdown()
        self._state_watchers.clear()
        if self._state_buttons:
            self._reset_state_buttons()
        self._state_buttons.clear()
        self._states.clear()
        self.sort_func = None
        for widget in [
            self.aggregator_combo,
            self.by_name,
            self.by_number,
            self.left_scroll_btn,
            self.right_scroll_btn,
            self.box,
            self.btn_box,
        ]:
            self.safe_destroy(widget)
        self.aggregator_combo = None
        self.left_scroll_btn = None
        self.right_scroll_btn = None
        self.by_name = None
        self.by_number = None
        self.btn_box = None
        self.box = None
        self._parent = self._app = None

    def hide_gui(self) -> None:
        if self.box:
            self.box.hide()
        if self.btn_box:
            self.btn_box.hide()

    def show_gui(self) -> None:
        if self.box:
            self.box.show()
        if self.btn_box:
            self.btn_box.show()

    def on_combo_change(self, option: str) -> None:
        if option == self.title:
            return  # Noop
        else:
            self._aggregator.cycle_gui(option)

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
            if states is None:
                states = []
            if self._state_buttons:
                self._reset_state_buttons()
            active_col_start = self._first_button_col
            active_col_end = active_col_start + self._visible_button_cols - 1
            active_cols = set(range(active_col_start, active_col_end + 1))
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

            self._max_button_cols = col + 1 if states else 0

            # Show/hide scroll buttons independently based on available pages.
            has_right_page = active_col_end < col
            has_left_page = active_col_start > 0

            if has_right_page:
                self.right_scroll_btn.enable()
            else:
                self.right_scroll_btn.disable()

            if has_left_page:
                self.left_scroll_btn.enable()
            else:
                self.left_scroll_btn.disable()

            # call post process handler
            self._post_process_state_buttons()
            self.btn_box.visible = True

    def _make_state_button(
        self,
        pd: S | Any,
        row: int,
        col: int,
        *,
        hold_threshold: float = 1.0,
        show_hold_progress: bool = False,
        progress_fill_color: str = "darkgrey",
        progress_empty_color: str = "white",
    ) -> tuple[PushButton | list[Widget], int, int]:
        pb = HoldButton(
            self.btn_box,
            grid=[col, row],
            text=f"{pd.tmcc_id}) {pd.road_name}",
            text_size=int(round(15 * self._scale_by)),
            width=max(8, int(round(self.width / self._visible_button_cols / (13 * self._scale_by)))),
            command=self.switch_state,
            args=[pd],
            padx=0,
            pady=self._button_text_pad_y,
            text_color=self._enabled_text if self.is_active(pd) else self._disabled_text,
            bg=self._enabled_bg if self.is_active(pd) else self._disabled_bg,
            hold_threshold=hold_threshold,
            show_hold_progress=show_hold_progress,
            progress_fill_color=progress_fill_color,
            progress_empty_color=progress_empty_color,
        )
        pb.component_state = pd

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
        self._first_button_col = max(0, self._first_button_col - 1)
        states = sorted(self._states.values(), key=self.sort_func)
        self._make_state_buttons(states)

    def scroll_right(self) -> None:
        max_first_col = max(0, self._max_button_cols - self._visible_button_cols) if self._max_button_cols else 0
        self._first_button_col = min(self._first_button_col + 1, max_first_col)
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
