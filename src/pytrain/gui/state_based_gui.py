#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from __future__ import annotations

import logging
import tkinter as tk
from abc import ABC, ABCMeta, abstractmethod
from threading import Event, Thread
from tkinter import TclError
from typing import Any, Callable, Generic, TypeVar

from guizero import Box, Combo, PushButton, Text
from guizero.base import Container, Widget
from guizero.event import EventData

from .component_state_gui import ComponentStateGui
from .guizero_base import GuiZeroBase
from ..db.component_state import ComponentState
from ..db.state_watcher import StateWatcher
from ..protocol.constants import CommandScope

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)
GUI_CLEANUP_EXCEPTIONS = (AttributeError, RuntimeError, TclError, TypeError)


class _CanvasMaster(Container):
    """
    Minimal guizero container wrapper around a Tk canvas.

    Child guizero widgets use this as their logical master while the canvas
    itself manages geometry via `create_window`.
    """

    def __init__(self, master: Box, canvas: tk.Canvas) -> None:
        super().__init__(master=master, tk=canvas, layout="auto", displayable=False)

    def display_widgets(self) -> None:
        # Canvas-managed children are positioned via canvas window items.
        return


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
        # Collect cyclic garbage on Tk thread during shutdown to avoid tk.Variable
        # finalizers running on non-GUI threads.
        self._collect_gc_on_destroy = True
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

        self.by_name = self.by_number = self.box = self.btn_box = self.y_offset = None
        self.pd_button_height = self.pd_button_width = None
        self.aggregator_combo = None
        self._max_name_len = 0
        self.sort_func = None
        self._screens = self._resolve_screens(screens)
        self._visible_button_cols = max(1, self._screens * self._COLS_PER_SCREEN)
        self._scroll_box: Box | None = None
        self._scroll_canvas: tk.Canvas | None = None
        self._scrollbar: tk.Scrollbar | None = None
        self._scroll_canvas_master: _CanvasMaster | None = None
        self._btn_canvas_window: int | None = None
        self._touch_bindtag = f"StateBasedGuiTouch_{id(self)}"
        self._touch_widget_map: dict[tk.Misc, Widget] = {}
        self._touch_active_widget: Widget | None = None
        self._touch_press_widget: Widget | None = None
        self._touch_start_x_root = 0
        self._touch_start_y_root = 0
        self._touch_tracking = False
        self._touch_dragging = False
        self._touch_press_dispatched = False
        self._touch_press_after_id: str | None = None
        self._touch_release_sent = False
        self._touch_canvas_mark_x = 0
        self._touch_canvas_mark_y = 0
        self._touch_drag_threshold = max(6, int(round(8 * self._scale_by)))

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

        ts = self._text_size
        _ = Text(box, text=" ", grid=[0, 0, 6, 1], size=6, height=1, bold=True)
        _ = Text(box, text="    ", grid=[1, 1], size=ts)
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

        tk_parent = self.by_number.tk.master
        tk_parent.grid_columnconfigure(self.by_number.tk.grid_info()["column"], pad=40)
        tk_parent.grid_columnconfigure(self.by_name.tk.grid_info()["column"], pad=40)
        tk_parent.grid_rowconfigure(self.by_number.tk.grid_info()["row"], pad=10)

        app.update()
        self.y_offset = self.box.tk.winfo_y() + self.box.tk.winfo_height()
        self._build_scrollable_button_area(gui_parent)

        # Order by tmcc_id
        self.sort_by_number()

    def _build_scrollable_button_area(self, gui_parent: Any) -> None:
        available_height = self.height - self.y_offset if self.height and self.y_offset else self.height
        viewport_height = max(1, int(available_height) if available_height is not None else int(self.height or 1))
        self._scroll_box = Box(gui_parent, layout="auto")
        self._scroll_box.bg = "white"
        self._scroll_box.tk.configure(height=viewport_height, width=self.width)
        self._scroll_box.tk.pack_propagate(False)
        self._scroll_canvas = tk.Canvas(self._scroll_box.tk, bg="white", borderwidth=0, highlightthickness=0)
        self._scrollbar = tk.Scrollbar(self._scroll_box.tk, orient="vertical", command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scroll_canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y")

        self._scroll_canvas_master = _CanvasMaster(self._scroll_box, self._scroll_canvas)
        self.btn_box = Box(self._scroll_canvas_master, layout="grid")
        self.btn_box.bg = "white"
        self._btn_canvas_window = self._scroll_canvas.create_window((0, 0), window=self.btn_box.tk, anchor="nw")
        self._bind_touch_gesture_tag()

        self._scroll_canvas.bind("<Configure>", self._on_scroll_canvas_configure, add="+")
        self.btn_box.tk.bind("<Configure>", self._on_button_box_configure, add="+")
        self._wire_widget_scroll(self.btn_box)
        self._wire_widget_scroll(self._scroll_canvas)
        self._on_button_box_configure()

    def _bind_touch_gesture_tag(self) -> None:
        app = self.app
        app.tk.bind_class(self._touch_bindtag, "<ButtonPress-1>", self._on_touch_press, add="+")
        app.tk.bind_class(self._touch_bindtag, "<B1-Motion>", self._on_touch_drag, add="+")
        app.tk.bind_class(self._touch_bindtag, "<ButtonRelease-1>", self._on_touch_release, add="+")

    def _on_scroll_canvas_configure(self, event: Any = None) -> None:
        if self._scroll_canvas is None:
            return
        if self._btn_canvas_window is not None and event is not None:
            self._scroll_canvas.itemconfigure(self._btn_canvas_window, width=event.width)
        self._on_button_box_configure()

    # noinspection PyUnusedLocal
    def _on_button_box_configure(self, event: Any = None) -> None:
        if self._scroll_canvas is None or self._scrollbar is None:
            return
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))
        required_height = self.btn_box.tk.winfo_reqheight() if self.btn_box else 0
        visible_height = self._scroll_canvas.winfo_height()
        should_show_scrollbar = required_height > visible_height + 1
        scrollbar_visible = self._scrollbar.winfo_manager() != ""
        if should_show_scrollbar and not scrollbar_visible:
            self._scrollbar.pack(side="right", fill="y")
        elif not should_show_scrollbar and scrollbar_visible:
            self._scrollbar.pack_forget()
            self._scroll_canvas.yview_moveto(0)

    def _wire_widget_scroll(self, widget: Any) -> None:
        if isinstance(widget, tk.Misc):
            tk_widget = widget
            gui_widget = None
        elif hasattr(widget, "tk"):
            tk_widget = widget.tk
            gui_widget = widget if isinstance(widget, Widget) else None
        else:
            tk_widget = widget
            gui_widget = None
        if tk_widget is None or not hasattr(tk_widget, "bind"):
            return
        if gui_widget is not None:
            self._touch_widget_map[tk_widget] = gui_widget
        if hasattr(tk_widget, "bindtags"):
            tags = list(tk_widget.bindtags())
            if self._touch_bindtag not in tags:
                tk_widget.bindtags((self._touch_bindtag, *tags))
        tk_widget.bind("<MouseWheel>", self._on_scroll_mousewheel, add="+")
        tk_widget.bind("<Button-4>", self._on_scroll_mousewheel, add="+")
        tk_widget.bind("<Button-5>", self._on_scroll_mousewheel, add="+")

    @staticmethod
    def _is_slider_widget(widget: Widget | None) -> bool:
        return widget is not None and widget.__class__.__name__ == "Slider"

    @staticmethod
    def _is_push_button_widget(widget: Widget | None) -> bool:
        return isinstance(widget, PushButton)

    def _is_scrollable(self) -> bool:
        if self._scroll_canvas is None:
            return False
        bbox = self._scroll_canvas.bbox("all")
        if not bbox:
            return False
        return (bbox[3] - bbox[1]) > self._scroll_canvas.winfo_height() + 1

    def _canvas_coords_from_root(self, x_root: int, y_root: int) -> tuple[int, int]:
        if self._scroll_canvas is None:
            return 0, 0
        return x_root - self._scroll_canvas.winfo_rootx(), y_root - self._scroll_canvas.winfo_rooty()

    @staticmethod
    def _invoke_touch_callback(callback: Callable | None, widget: Widget, event: Any) -> None:
        if callback is None:
            return
        try:
            callback(EventData(widget, event))
        except TypeError:
            callback()

    def _invoke_touch_press(self, widget: Widget, event: Any) -> None:
        callback = getattr(widget, "when_left_button_pressed", None)
        self._invoke_touch_callback(callback, widget, event)

    def _invoke_touch_release(self, widget: Widget, event: Any) -> None:
        callback = getattr(widget, "when_left_button_released", None)
        self._invoke_touch_callback(callback, widget, event)

    @staticmethod
    def _invoke_touch_command(widget: Widget) -> None:
        if isinstance(widget, PushButton) and widget.enabled:
            try:
                widget.tk.invoke()
            except GUI_CLEANUP_EXCEPTIONS:
                pass

    def _cancel_pending_touch_press(self) -> None:
        if self._touch_press_after_id is None:
            return
        try:
            self.app.tk.after_cancel(self._touch_press_after_id)
        except GUI_CLEANUP_EXCEPTIONS:
            pass
        self._touch_press_after_id = None

    def _dispatch_touch_press(self, event: Any) -> None:
        self._touch_press_after_id = None
        if (
            self._touch_tracking
            and not self._touch_dragging
            and self._touch_press_widget is not None
            and not self._touch_press_dispatched
        ):
            self._invoke_touch_press(self._touch_press_widget, event)
            self._touch_press_dispatched = True

    def _schedule_touch_press(self, event: Any) -> None:
        self._touch_press_dispatched = False
        # Defer press callbacks slightly so drag gestures do not fire actions.
        self._touch_press_after_id = self.app.tk.after(90, lambda e=event: self._dispatch_touch_press(e))

    def _clear_touch_state(self) -> None:
        self._cancel_pending_touch_press()
        self._touch_active_widget = None
        self._touch_press_widget = None
        self._touch_tracking = False
        self._touch_dragging = False
        self._touch_press_dispatched = False
        self._touch_release_sent = False
        self._touch_start_x_root = 0
        self._touch_start_y_root = 0
        self._touch_canvas_mark_x = 0
        self._touch_canvas_mark_y = 0

    def _on_touch_press(self, event: Any) -> str | None:
        widget = self._touch_widget_map.get(event.widget)
        if self._is_slider_widget(widget):
            self._clear_touch_state()
            return None
        self._touch_active_widget = widget
        self._touch_press_widget = widget if self._is_push_button_widget(widget) else None
        self._touch_start_x_root = event.x_root
        self._touch_start_y_root = event.y_root
        self._touch_tracking = True
        self._touch_dragging = False
        self._touch_press_dispatched = False
        self._touch_release_sent = False
        self._touch_canvas_mark_x, self._touch_canvas_mark_y = self._canvas_coords_from_root(event.x_root, event.y_root)
        if self._touch_press_widget is not None:
            self._schedule_touch_press(event)
            return "break"
        return "break" if self._is_scrollable() else None

    def _on_touch_drag(self, event: Any) -> str | None:
        if not self._touch_tracking:
            return None
        dy_total = event.y_root - self._touch_start_y_root
        if not self._touch_dragging and abs(dy_total) >= self._touch_drag_threshold:
            self._touch_dragging = True
            self._cancel_pending_touch_press()
            if self._scroll_canvas is not None:
                self._scroll_canvas.scan_mark(self._touch_canvas_mark_x, self._touch_canvas_mark_y)
            if self._touch_press_widget is not None and self._touch_press_dispatched and not self._touch_release_sent:
                self._invoke_touch_release(self._touch_press_widget, event)
                self._touch_release_sent = True
        if self._touch_dragging and self._is_scrollable():
            if self._scroll_canvas is not None:
                x, y = self._canvas_coords_from_root(event.x_root, event.y_root)
                self._scroll_canvas.scan_dragto(x, y, gain=1)
            return "break"
        if self._touch_press_widget is not None:
            return "break"
        return None

    def _on_touch_release(self, event: Any) -> str | None:
        if not self._touch_tracking:
            return None
        push_button = self._touch_press_widget
        if push_button is not None:
            if self._touch_dragging:
                if not self._touch_release_sent:
                    if self._touch_press_dispatched:
                        self._invoke_touch_release(push_button, event)
                self._clear_touch_state()
                return "break"
            if not self._touch_press_dispatched:
                self._cancel_pending_touch_press()
                self._dispatch_touch_press(event)
            self._invoke_touch_release(push_button, event)
            self._invoke_touch_command(push_button)
            self._clear_touch_state()
            return "break"
        if self._touch_dragging:
            self._clear_touch_state()
            return "break"
        self._clear_touch_state()
        return None

    def _on_scroll_mousewheel(self, event: Any) -> str | None:
        if self._scroll_canvas is None:
            return None
        delta = 0
        event_num = getattr(event, "num", None)
        if event_num == 4:
            delta = -1
        elif event_num == 5:
            delta = 1
        else:
            event_delta = getattr(event, "delta", 0)
            if event_delta:
                delta = -1 if event_delta > 0 else 1
        if delta:
            self._scroll_canvas.yview_scroll(delta, "units")
            return "break"
        return None

    def destroy_gui(self) -> None:
        def safe_disconnect(widget: Any | None) -> None:
            if widget is None:
                return
            try:
                if hasattr(widget, "update_command"):
                    widget.update_command(None)
            except GUI_CLEANUP_EXCEPTIONS:
                pass
            try:
                if hasattr(widget, "command"):
                    widget.command = None
            except GUI_CLEANUP_EXCEPTIONS:
                pass
            try:
                if hasattr(widget, "when_left_button_pressed"):
                    widget.when_left_button_pressed = None
            except GUI_CLEANUP_EXCEPTIONS:
                pass
            try:
                if hasattr(widget, "when_left_button_released"):
                    widget.when_left_button_released = None
            except GUI_CLEANUP_EXCEPTIONS:
                pass

        def safe_destroy(widget: Any | None) -> None:
            if widget is None:
                return
            try:
                if hasattr(widget, "hide"):
                    widget.hide()
            except GUI_CLEANUP_EXCEPTIONS:
                pass
            try:
                widget.destroy()
            except GUI_CLEANUP_EXCEPTIONS:
                pass

        # Explicitly drop references to tkinter/guizero objects on the Tk thread
        for sw in self._state_watchers.values():
            sw.shutdown()
        self._state_watchers.clear()
        safe_disconnect(self.aggregator_combo)
        safe_disconnect(self.by_name)
        safe_disconnect(self.by_number)
        if self._state_buttons:
            self._reset_state_buttons()
        safe_destroy(self.aggregator_combo)
        safe_destroy(self.by_name)
        safe_destroy(self.by_number)
        safe_destroy(self.btn_box)
        safe_destroy(self._scroll_canvas)
        safe_destroy(self._scrollbar)
        safe_destroy(self._scroll_box)
        safe_destroy(self.box)
        self.clear_cache()
        self.aggregator_combo = None
        self.by_name = None
        self.by_number = None
        self.btn_box = None
        self._scroll_box = None
        self._scroll_canvas = None
        self._scrollbar = None
        self._scroll_canvas_master = None
        self._btn_canvas_window = None
        self._touch_widget_map.clear()
        self._clear_touch_state()
        self.box = None
        self._state_buttons.clear()
        self._state_buttons = None

    def hide_gui(self) -> None:
        if self.box:
            self.box.hide()
        if self._scroll_box:
            self._scroll_box.hide()

    def show_gui(self) -> None:
        if self.box:
            self.box.show()
        if self._scroll_box:
            self._scroll_box.show()

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
                if hasattr(widget, "update_command"):
                    widget.update_command(None)
                if hasattr(widget, "command"):
                    widget.command = None
                if hasattr(widget, "component_state"):
                    widget.component_state = None
                if hasattr(widget, "when_left_button_pressed"):
                    widget.when_left_button_pressed = None
                if hasattr(widget, "when_left_button_released"):
                    widget.when_left_button_released = None
                try:
                    widget.hide()
                except GUI_CLEANUP_EXCEPTIONS:
                    pass
                try:
                    widget.destroy()
                except GUI_CLEANUP_EXCEPTIONS:
                    pass
        self._state_buttons.clear()

    # noinspection PyTypeChecker
    def _make_state_buttons(self, states: list[S] = None) -> None:
        with self._cv:
            if states is None:
                states = []
            if self._state_buttons:
                self._reset_state_buttons()
            self._touch_widget_map.clear()
            self.by_name.show()
            self.by_number.show()
            if self._scroll_canvas:
                self._scroll_canvas.yview_moveto(0)
                self._wire_widget_scroll(self._scroll_canvas)
            self._wire_widget_scroll(self.btn_box)

            state_col_span = 1
            lane_count = max(1, self._visible_button_cols)
            lane_rows = [0 for _ in range(lane_count)]
            self.btn_box.visible = False
            for index, pd in enumerate(states):
                lane = index % lane_count
                row = lane_rows[lane]
                col = lane * state_col_span
                pb, _, _ = self._make_state_button(pd, row, col)
                self._state_buttons[pd] = pb
                created_span = self._widget_column_span(pb)
                if created_span != state_col_span:
                    state_col_span = max(1, created_span)
                    lane_count = max(1, self._visible_button_cols // state_col_span)
                    lane = index % lane_count
                    if len(lane_rows) != lane_count:
                        lane_rows = [0 for _ in range(lane_count)]
                lane_rows[lane] = self._next_grid_row(pb, row + 1)
                for widget in self._as_widget_list(pb):
                    self._wire_widget_scroll(widget)

            # call post process handler
            self._post_process_state_buttons()
            self.btn_box.visible = True
            self._on_button_box_configure()

    @staticmethod
    def _as_widget_list(widgets: Widget | list[Widget]) -> list[Widget]:
        return widgets if isinstance(widgets, list) else [widgets]

    @staticmethod
    def _widget_column_span(widgets: Widget | list[Widget]) -> int:
        min_col = None
        max_col = None
        for widget in StateBasedGui._as_widget_list(widgets):
            try:
                info = widget.tk.grid_info()
                col = int(info.get("column", 0))
                col_span = int(info.get("columnspan", 1))
            except GUI_CLEANUP_EXCEPTIONS:
                continue
            except ValueError:
                continue
            min_col = col if min_col is None else min(min_col, col)
            max_col = (col + col_span - 1) if max_col is None else max(max_col, col + col_span - 1)
        if min_col is None or max_col is None:
            return 1
        return max(1, max_col - min_col + 1)

    def _next_grid_row(self, widgets: Widget | list[Widget], fallback_row: int) -> int:
        next_row = fallback_row
        for widget in self._as_widget_list(widgets):
            try:
                info = widget.tk.grid_info()
                row = int(info.get("row", fallback_row - 1))
                row_span = int(info.get("rowspan", 1))
                next_row = max(next_row, row + row_span)
            except GUI_CLEANUP_EXCEPTIONS:
                continue
            except ValueError:
                continue
        return next_row

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
            width=max(8, int(round(self.width / self._visible_button_cols / (13 * self._scale_by)))),
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
        self._make_state_buttons(states)

    def sort_by_name(self) -> None:
        self.by_name.text_bold = True
        self.by_number.text_bold = False

        self.sort_func = lambda x: x.road_name.lower()
        states = sorted(self._states.values(), key=self.sort_func)
        self._make_state_buttons(states)

    def scroll_left(self) -> None:
        if self._scroll_canvas:
            self._scroll_canvas.yview_scroll(-3, "units")

    def scroll_right(self) -> None:
        if self._scroll_canvas:
            self._scroll_canvas.yview_scroll(3, "units")

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
