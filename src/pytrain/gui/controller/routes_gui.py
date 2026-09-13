#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Standalone route selection and editing, using the controller's RouteBuilderPanel."""

from __future__ import annotations

from sys import platform
from threading import current_thread, main_thread
from tkinter import TclError

from guizero import Box, ListBox, PushButton, Text

from .popup_manager import PopupManager
from .route_builder_panel import BUTTON_ACTIVE_BG, BUTTON_BG, RouteBuilderPanel
from ..components.editable_text import EditableText, EditorType
from ..components.scroll_input import ScrollAccumulator, precise_scroll_deltas, wheel_scroll_pixels
from ..components.touch_list_box import TouchListBox
from ..guizero_base import GuiZeroBase
from ...db.component_state import RouteState
from ...protocol.constants import PROGRAM_NAME, CommandScope

DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 800
ROUTES_GUI_TITLE = f"{PROGRAM_NAME} Routes"


class RoutesGui(GuiZeroBase):
    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        scale_by: float = 1.0,
        stand_alone: bool = True,
        full_screen: bool = False,
    ) -> None:
        # Explicit dimensions avoid constructing a temporary Tk window before run_window.
        super().__init__(
            title=ROUTES_GUI_TITLE,
            width=width or DEFAULT_WIDTH,
            height=height or DEFAULT_HEIGHT,
            scale_by=scale_by,
            stand_alone=stand_alone,
            full_screen=full_screen,
        )
        self.controller_box = None
        self.keypad_box = self.amc2_ops_box = self.sensor_track_box = None
        self.image_box = self.acc_overlay = None
        self.popup_position = (0, 0)
        self.emergency_box_width = self.width
        self._popup = PopupManager(self)
        self._panel: RouteBuilderPanel | None = None
        self._route_list = self._listbox = None
        self._status = self._edit_btn = self._new_btn = self._create_btn = None
        self._new_box = self._id_field = None
        self._route_rows: list[tuple[int, str]] = []
        self._scroll_pixels = ScrollAccumulator()
        self.init_complete()

    @property
    def root(self):
        return self.app

    @property
    def compact(self) -> bool:
        return False

    @property
    def desktop_controls(self) -> bool:
        return platform in {"darwin", "win32"}

    @property
    def popup_manager(self) -> PopupManager:
        return self._popup

    @property
    def panel(self) -> RouteBuilderPanel | None:
        return self._panel

    @property
    def is_synchronized(self) -> bool:
        return bool(self._synchronized or (self._sync_state is not None and self._sync_state.is_synchronized()))

    def calc_image_box_size(self) -> tuple[int, int]:
        return self.height // 2, self.width

    @staticmethod
    def fit_popup_title_height(base: int, required: int) -> int:
        return max(base, required)

    def show_popup(self, overlay, **kwargs) -> None:
        self._popup.show(overlay, **kwargs)

    def build_gui(self) -> None:
        self.controller_box = page = Box(self.root, width="fill", height="fill")
        page.tk.config(padx=12, pady=12)
        Text(page, text="Routes", size=self.s_20, bold=True, align="top")
        Text(page, text="Choose a route to edit, or click New.", size=self.s_12, align="top")

        footer = Box(page, align="bottom", width="fill")
        self._status = Text(footer, text="", size=self.s_12, width="fill")
        self._status.tk.config(wraplength=self.width - 32)
        actions = Box(footer, width="fill")
        self._edit_btn = self._button(actions, "Edit", self.edit_selected)
        self._new_btn = self._button(actions, "New", self.new_route)
        self._button(actions, "Close", self.request_close)

        self._new_box = Box(footer, width="fill", visible=False)
        row = Box(self._new_box, width="fill", height=56)
        row.tk.pack_propagate(False)
        Text(row, text="TMCC ID (1–99)", size=self.s_14, align="left")
        edit = self._button(row, "Edit ID", lambda: self._id_field.begin_edit(), align="right")
        self._id_field = EditableText(
            row,
            text="",
            editor=EditorType.KEYPAD,
            compact=False,
            field_name="Route TMCC ID",
            max_length=2,
            size=self.s_14,
            align="left",
            width="fill",
            height="fill",
        )
        self._id_field.tk.config(relief="sunken", bd=1, anchor="w", padx=6)
        self._id_field.when_clicked = self._id_field.begin_edit
        edit.text_size = self.s_12
        actions = Box(self._new_box, width="fill")
        self._create_btn = self._button(actions, "Create", self.create_route)
        self._button(actions, "Cancel", self.cancel_new)

        options = dict(width="fill", height="fill", align="top", scrollbar=True)
        if self.desktop_controls:
            self._route_list = ListBox(page, items=[], **options)
        else:
            self._route_list = TouchListBox(
                page, items=[], tap_highlight=True, on_hold_select=lambda *_: self.edit_selected(), **options
            )
        self._route_list.text_size = self.s_16
        self._listbox = self._route_list.children[0].tk
        self._listbox.config(exportselection=False, selectmode="browse", takefocus=True)
        self._listbox.bind("<<ListboxSelect>>", self._selection_changed, add="+")
        if self.desktop_controls:
            self._listbox.bind("<Return>", self._edit_key)
            self._listbox.bind("<Double-Button-1>", self._double_click)
            self._listbox.bind("<MouseWheel>", lambda event: self._scroll(wheel_scroll_pixels(event)))
            if platform == "darwin":
                try:
                    self._listbox.bind("<TouchpadScroll>", lambda event: self._scroll(-precise_scroll_deltas(event)[1]))
                except TclError:
                    pass  # Tk 8.6 reports trackpad motion through MouseWheel.
        self._panel = RouteBuilderPanel(self, post_close=self._on_panel_closed, on_saved=self._on_saved)
        self.app.when_closed = self.request_close
        self.refresh_routes()
        self.app.repeat(500, self.refresh_routes)

    def _button(self, parent, text, command, *, align="left"):
        button = PushButton(parent, text=text, command=command, align=align, width="fill", height=2)
        button.text_size = self.s_14
        button.bg = BUTTON_BG
        button.tk.config(relief="raised", bd=2, activebackground=BUTTON_ACTIVE_BG)
        return button

    @staticmethod
    def _existing_route(state) -> bool:
        return (
            isinstance(state, RouteState)
            and not state.is_deleted
            and state.tmcc_id is not None
            and 1 <= state.tmcc_id <= 99
            and bool(not state.is_comp_data_empty or state.is_user_defined or state.components)
        )

    def _selected_id(self) -> int | None:
        selection = self._listbox.curselection()
        if selection and 0 <= int(selection[0]) < len(self._route_rows):
            return self._route_rows[int(selection[0])][0]
        return None

    def refresh_routes(self) -> None:
        if self._listbox is None or self.is_shutting_down:
            return
        ready = self.is_synchronized
        rows = []
        if ready:
            for state in self.state_store.get_all(CommandScope.ROUTE):
                if self._existing_route(state):
                    name = state.road_name if state.is_road_name else f"Route {state.tmcc_id:02d}"
                    number = f" · {state.road_number}" if state.is_road_number else ""
                    rows.append((state.tmcc_id, f"{state.tmcc_id:02d}   {name}{number}"))
        rows.sort()
        if rows != self._route_rows:
            selected = self._selected_id()
            top = self._listbox.yview()[0]
            self._route_rows = rows
            self._listbox.delete(0, "end")
            for index, (tmcc_id, label) in enumerate(rows):
                self._listbox.insert("end", label)
                if tmcc_id == selected:
                    self._listbox.selection_set(index)
            self._listbox.yview_moveto(top)
        self._new_btn.enabled = self._create_btn.enabled = ready
        self._selection_changed()
        if not self._new_box.visible:
            self._status.value = (
                (f"{len(rows)} routes" if rows else "No routes found. Click New to build one.")
                if ready
                else "Waiting for Base 3 synchronization…"
            )

    def _selection_changed(self, _event=None) -> None:
        self._edit_btn.enabled = self.is_synchronized and self._selected_id() is not None

    def _edit_key(self, _event=None) -> str:
        self.edit_selected()
        return "break"

    def _double_click(self, event) -> str:
        if event.y < 0:
            return "break"
        index = self._listbox.nearest(event.y)
        bounds = self._listbox.bbox(index) if self._route_rows else None
        if bounds and bounds[1] <= event.y < bounds[1] + bounds[3]:
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(index)
            self.edit_selected()
        return "break"

    def _scroll(self, pixels: int) -> str:
        if self._route_rows:
            bounds = self._listbox.bbox(self._listbox.nearest(0))
            first, last = self._listbox.yview()
            if (pixels < 0 and first <= 0) or (pixels > 0 and last >= 1):
                self._scroll_pixels.reset()
            else:
                steps = self._scroll_pixels.consume(pixels, bounds[3] if bounds else 20)
                if steps:
                    self._listbox.yview_scroll(steps, "units")
        return "break"

    def edit_selected(self) -> None:
        if not self.is_synchronized or self._panel.visible:
            return
        tmcc_id = self._selected_id()
        state = self.state_store.get_state(CommandScope.ROUTE, tmcc_id, False) if tmcc_id is not None else None
        if not self._existing_route(state):
            self.refresh_routes()
            self._status.value = "Choose an available route to edit."
            return
        self._open_editor(tmcc_id, state)

    def new_route(self) -> None:
        if not self.is_synchronized or self._panel.visible:
            return
        self._id_field.value = ""
        self._new_box.show()
        self._status.value = "Enter an unused TMCC ID from 1 to 99."
        self._id_field.begin_edit()

    def cancel_new(self) -> None:
        if self._id_field.is_editing:
            self._id_field.cancel_edit()
        self._new_box.hide()
        self.refresh_routes()

    def create_route(self) -> None:
        if not self.is_synchronized or self._panel.visible:
            return
        if self._id_field.is_editing:
            self._id_field.commit_edit()
        value = str(self._id_field.value).strip()
        if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 99:
            self._status.value = "Route ID must be an integer from 1 to 99."
            return
        tmcc_id = int(value)
        state = self.state_store.get_state(CommandScope.ROUTE, tmcc_id, False)
        if self._existing_route(state):
            self._status.value = f"Route {tmcc_id:02d} already exists. Select it and click Edit."
            return
        self._open_editor(tmcc_id)

    def _open_editor(self, tmcc_id: int, state: RouteState | None = None) -> None:
        overlay = self._panel.overlay
        try:
            self._panel.configure(tmcc_id, state)
        except ValueError as exc:
            self._status.value = f"Route could not be opened: {exc}"
            return
        self.cancel_new()
        self.show_popup(overlay)

    def _on_panel_closed(self, _overlay=None) -> None:
        self.refresh_routes()
        if self.desktop_controls:
            self._listbox.after_idle(self._listbox.focus_set)

    def _on_saved(self, _state: RouteState) -> None:
        self.refresh_routes()

    def create_provisional_component(self, scope: CommandScope, tmcc_id: int) -> RouteState:
        if scope != CommandScope.ROUTE or not 1 <= tmcc_id <= 99:
            raise ValueError("Select a route ID from 1 to 99.")
        state = self.state_store.get_state(scope, tmcc_id, False)
        if state is None:
            state = self.state_store.get_state(scope, tmcc_id, True)
            state.initialize(scope, tmcc_id)
        return state

    def clear_record(self, state: RouteState) -> None:
        if isinstance(state, RouteState) and state.is_deletable:
            state.clear(notify=False, clear_db=True)
            self.queue_message(self.refresh_routes)

    def request_close(self) -> None:
        if self._panel is not None and self._panel.visible:
            if not self.popup_manager.close_requested():
                return
        self.close()

    def start(self) -> None:
        # As in LcsGui, the sync watcher queues updates rather than starting Tk on a worker.
        self.queue_message(self._on_synchronized)

    def _on_synchronized(self) -> None:
        if self.app is not None:
            self.app.title = self.title
        self.refresh_routes()

    def run_window(self) -> None:
        if current_thread() is not main_thread():
            raise RuntimeError("RoutesGui.run_window() must be called on the main thread")
        try:
            self.run()
        finally:
            self.close()

    def close(self) -> None:
        if self._sync_watcher is not None:
            self._sync_watcher.shutdown()
            self._sync_watcher = None
        super().close()

    def destroy_gui(self) -> None:
        self._panel = None
        self.controller_box = None
        self._route_list = self._listbox = None
        self._status = self._edit_btn = self._new_btn = self._create_btn = None
        self._new_box = self._id_field = None
