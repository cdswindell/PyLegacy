#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#
#

from __future__ import annotations

import logging
import tkinter as tk
from functools import partial
from sys import platform
from tkinter import font as tkfont
from tkinter import simpledialog
from typing import TYPE_CHECKING

from guizero import Box, PushButton, Text, TitleBox

from .overlay_panel import OverlayPanel
from .route_draft import RouteDraft
from ..components.checkbox_group import CheckBoxGroup
from ..components.editable_text import EditableText, EditorType
from ..components.hold_button import HoldButton
from ..components.scroll_box import BAR_ACTIVE_COLOR, BAR_COLOR, BAR_EDGE_COLOR, BAR_EDGE_PX, BAR_TROUGH_COLOR
from ..components.scroll_input import ScrollAccumulator
from ..components.touch_scrollbar import TouchScrollbar
from ..guizero_base import ACTIVE_STATE_BG
from ...db.component_state import RouteState, SwitchState
from ...pdi.base_req import BaseReq
from ...protocol.constants import CommandScope

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

log = logging.getLogger(__name__)
CARD_BG = "#f4f6f8"
BUTTON_BG = "#e7ebef"
BUTTON_ACTIVE_BG = "#cfdeeb"
SELECTED_BG = "#dcefff"
SELECTED_COLOR = "#1266a5"


class RouteDiscardDialog(simpledialog.Dialog):
    def __init__(self, parent, *, width, text_size, button_height):
        self._width = width
        self._text_size = text_size
        self._button_height = button_height
        self._keep_btn: tk.Button | None = None
        self._discard_btn: tk.Button | None = None
        self.initial_focus: tk.Widget | None = None
        self.result: bool | None = None
        super().__init__(parent, "Discard route changes?")

    def body(self, master):
        message = tk.Frame(master, width=self._width, height=self._button_height * 2)
        message.pack_propagate(False)
        message.pack()
        tk.Label(
            message,
            text="Discard unsaved route changes?",
            font=("Helvetica", self._text_size),
            wraplength=self._width - 32,
            justify="center",
        ).pack(fill="both", expand=True, padx=16, pady=16)

    def buttonbox(self):
        row = tk.Frame(self, width=self._width, height=self._button_height)
        row.pack_propagate(False)
        row.pack(fill="x", padx=12, pady=(0, 16))
        self._keep_btn = tk.Button(
            row,
            text="Keep Editing",
            command=self.cancel,
            font=("Helvetica", self._text_size),
            default="active",
        )
        self._discard_btn = tk.Button(row, text="Discard", command=self.ok, font=("Helvetica", self._text_size))
        for button in (self._keep_btn, self._discard_btn):
            button.pack(side="left", fill="both", expand=True, padx=6)
        self.initial_focus = self._keep_btn
        self.bind("<Return>", self._on_return)
        self.bind("<Escape>", self.cancel)

    def _on_return(self, _event=None):
        if self.focus_get() is self._discard_btn:
            self.ok()
        else:
            self.cancel()

    def apply(self):
        self.result = True


class RouteBuilderPanel(OverlayPanel):
    def __init__(self, gui: EngineGui):
        super().__init__(gui, "Route Builder", post_close=self._on_closed)
        self.draft: RouteDraft | None = None
        self._state: RouteState | None = None
        self._tmcc_id = 0
        self._selected: int | None = None
        self._picking = False
        self._filter = "Switches"
        self._sort = "Name"
        self._descending = False
        self._candidates = []
        self._candidate: tuple[CommandScope, int] | None = None
        self._picker_cursor: tuple[CommandScope, int] | None = None
        self._main_page = self._picker_page = None
        self._cards = self._picker = None
        self._picker_rows = 1
        self._picker_resize_pending = False
        self._picker_scroll_pixels = ScrollAccumulator()
        self._name_field = self._number_field = self._search_field = None
        self._search_btn = None
        self._tmcc_id_field: Text | None = None
        self._status = self._save_btn = self._cancel_btn = None
        self._clear_route_btn = None
        self._gesture = None
        self._metadata_box = None
        self._route_label = self._count = self._selection = self._picker_count = None
        self._previous_btn = self._next_btn = None
        self._earlier_btn = self._later_btn = None
        self._add_btn = self._remove_btn = self._clear_btn = None
        self._positions = self._position = None
        self._radios = []
        self._filter_btns = self._sort_btns = ()
        self._picker_scrollbar = None

    @property
    def has_close(self) -> bool:
        return False

    @property
    def has_footer(self) -> bool:
        return True

    @property
    def closes_on_request_only(self) -> bool:
        return True

    @property
    def footer_pad_px(self) -> int:
        return self.section_gap or 4

    @property
    def section_gap(self) -> int:
        if not self.gui.compact and not self.desktop_controls and self.gui.height >= 1000:
            return max(12, round(self.row_height * 0.3))
        return 0

    @property
    def content_width(self) -> int:
        return max(1, int(self.gui.emergency_box_width) - 16)

    @property
    def row_height(self) -> int:
        return max(44, int(44 * self.gui.width / 639))

    @property
    def button_pad_x(self) -> int:
        return max(4, round(self.gui.width / 160))

    @property
    def button_pad_y(self) -> int:
        return max(3, round(self.gui.width / 210))

    @property
    def control_row_height(self) -> int:
        return self.row_height + 2 * self.button_pad_y

    @property
    def indicator_size(self) -> int:
        return max(24, round(self.row_height * 0.55))

    @property
    def card_width(self) -> int:
        return self.card_view_width // 3

    @property
    def card_view_width(self) -> int:
        return self.content_width - 2 * self.row_height

    @property
    def card_height(self) -> int:
        return int(int(self.row_height * 3.5) * 0.75)

    @property
    def desktop_controls(self) -> bool:
        return not self.gui.compact and platform in {"darwin", "win32"}

    @property
    def picker_inline_details(self) -> bool:
        return self.gui.compact and self.content_width >= 600

    @property
    def picker_rows(self) -> int:
        return self._picker_rows

    @property
    def picker_row_height(self) -> int:
        if self.picker_inline_details:
            return max(48, int(self.row_height * 1.1))
        if self.desktop_controls:
            return max(44, int(50 * self.gui.width / 639))
        return max(70, int(self.row_height * 1.3))

    @property
    def picker_bar_width(self) -> int:
        width = max(30, round(30 * self.gui.width / 639))
        return width if self.desktop_controls else round(width * 1.25)

    @property
    def picker_view_width(self) -> int:
        return self.content_width - self.picker_bar_width

    @property
    def picking(self) -> bool:
        return self._picking

    @property
    def pad_ready(self) -> bool:
        return self._picking and not self._search_field.is_editing

    @property
    def scroll_view(self) -> tk.Canvas | None:
        if self.draft is None or any(
            field is not None and field.is_editing
            for field in (self._name_field, self._number_field, self._search_field)
        ):
            return None
        return self._picker if self._picking else self._cards

    def _button(
        self, parent, text, command, *, column=None, columns=1, width=None, height=None, align=None, hold=False
    ):
        slot = Box(
            parent,
            grid=[column, 0] if column is not None else None,
            align=align or ("top" if column is None else None),
            width=width or self.content_width // columns,
            height=height or self.control_row_height,
        )
        slot.tk.pack_propagate(False)
        slot.tk.config(padx=self.button_pad_x, pady=self.button_pad_y)
        if hold:
            button = HoldButton(
                slot,
                text=text,
                on_hold=command,
                hold_threshold=3.0,
                show_hold_progress=True,
                critical_fill_color="red",
                cancel_on_leave=True,
                width="fill",
                height="fill",
            )
        else:
            button = PushButton(slot, text=text, command=command, width="fill", height="fill")
        button.text_size = self.gui.s_14
        button.bg = BUTTON_BG
        button.tk.config(relief="raised", bd=2, activebackground=BUTTON_ACTIVE_BG, disabledforeground="#727b84")
        return button

    def _buttons(self, parent, *buttons):
        row = Box(parent, align="top", layout="grid")
        return tuple(
            self._button(row, text, command, column=i, columns=len(buttons))
            for i, (text, command) in enumerate(buttons)
        )

    def _field(
        self,
        parent,
        label,
        editor=None,
        max_length=None,
        on_commit=None,
        *,
        width=None,
        label_width=12,
        commit_label="Save",
    ):
        row = Box(parent, align="top", width=width or self.content_width, height=self.control_row_height)
        row.tk.pack_propagate(False)
        caption = Text(row, text=label, align="left", size=self.gui.s_12, width=label_width)
        caption.tk.config(anchor="e", justify="right", padx=6)
        edit = None
        if editor is not None:
            edit = self._button(row, "Edit", None, align="right", width=int(self.row_height * 1.6))
            edit.text_size = self.gui.s_12
        field_slot = Box(row, align="left", width="fill", height="fill")
        field_slot.tk.config(pady=self.button_pad_y)
        if edit is None:
            field = Text(field_slot, text="", size=self.gui.s_14, align="left", width="fill", height="fill")
            field.tk.config(bd=1, anchor="w", padx=6)
            return field, None
        field = EditableText(
            field_slot,
            text="",
            editor=editor,
            compact=bool(self.gui.compact),
            field_name=label,
            commit_label=commit_label,
            max_length=max_length,
            size=self.gui.s_14,
            align="left",
            width="fill",
            height="fill",
            on_commit=on_commit,
        )
        field.tk.config(relief="sunken", bd=1, anchor="w", padx=6)
        field.when_clicked = field.begin_edit
        edit.update_command(field.begin_edit)
        return field, edit

    def _canvas(self, parent, height, horizontal):
        width = self.card_view_width if horizontal else self.content_width
        slot = Box(parent, align="left" if horizontal else "top", width=width, height=height)
        slot.tk.pack_propagate(False)
        canvas = tk.Canvas(
            slot.tk,
            width=width if horizontal else self.picker_view_width,
            height=height,
            highlightthickness=0,
            background="white",
            cursor="hand2",
            takefocus=self.desktop_controls,
        )
        canvas.pack(fill="both", expand=True, padx=0 if horizontal else (0, self.picker_bar_width))
        canvas.bind("<ButtonPress-1>", lambda event: self._scroll_start(canvas, event))
        canvas.bind("<B1-Motion>", lambda event: self._scroll_drag(canvas, event, horizontal))
        canvas.bind("<ButtonRelease-1>", lambda event: self._scroll_end(canvas, event, horizontal))
        canvas.bind("<MouseWheel>", lambda event: self._wheel(canvas, event, horizontal))
        canvas.bind("<Button-4>", lambda event: self._wheel(canvas, event, horizontal))
        canvas.bind("<Button-5>", lambda event: self._wheel(canvas, event, horizontal))
        if self.desktop_controls:
            canvas.bind("<Map>", lambda _event: self._focus_list(canvas))
            canvas.bind("<Enter>", lambda _event: self._focus_list(canvas))
            for key, delta in (("Left", -1), ("Right", 1)) if horizontal else (("Up", -1), ("Down", 1)):
                canvas.bind(f"<{key}>", lambda _event, step=delta: self._navigate_list(step, horizontal))
            if horizontal:
                canvas.bind("<Shift-MouseWheel>", lambda event: self._wheel(canvas, event, True))
            if platform == "darwin":
                try:
                    canvas.bind("<TouchpadScroll>", lambda event: self._touchpad_scroll(canvas, event, horizontal))
                except tk.TclError:
                    # Tk 8.6 reports touch-surface gestures as MouseWheel instead.
                    pass
        return canvas

    def build(self, body: Box):
        self._picker_rows = 1
        self._main_page = Box(body, align="top")
        summary = Box(self._main_page, align="top")
        self._route_label = Text(summary, text="", size=self.gui.s_14, align="left")
        Text(summary, text="   ·   ", size=self.gui.s_14, align="left")
        self._count = Text(summary, text="", size=self.gui.s_14, align="left")
        Text(
            self._main_page,
            text=(
                "Select a card to modify; scroll or use ← / → to browse."
                if self.desktop_controls
                else "Tap a card to change it; swipe to browse."
            ),
            size=self.gui.s_12,
        )
        strip = Box(self._main_page, align="top")
        self._previous_btn = self._button(
            strip,
            "‹",
            lambda: self.select_relative(-1),
            width=self.row_height,
            height=self.card_height,
            align="left",
        )
        self._cards = self._canvas(strip, self.card_height, True)
        self._next_btn = self._button(
            strip,
            "›",
            lambda: self.select_relative(1),
            width=self.row_height,
            height=self.card_height,
            align="left",
        )
        self._selection = Text(self._main_page, text="", size=self.gui.s_12, width="fill", height=1)
        self._selection.tk.config(wraplength=self.content_width)
        self._positions = Box(self._main_page, align="top", width=self.content_width, height=self.control_row_height)
        self._positions.tk.grid_propagate(False)
        self._positions.tk.grid_rowconfigure(0, weight=1)
        self._position = tk.StringVar(master=self._positions.tk, value="")
        self._radios = []
        for column, (label, value) in enumerate((("THRU — straight", "thru"), ("OUT — diverging", "out"))):
            self._positions.tk.grid_columnconfigure(column, weight=1, uniform="route_positions")
            radio = tk.Radiobutton(
                self._positions.tk,
                text=label,
                variable=self._position,
                value=value,
                command=lambda: self.set_position(0 if self._position.get() == "thru" else 1),
                font=("Helvetica", self.gui.s_14),
                anchor="w",
                background=BUTTON_BG,
                activebackground=BUTTON_ACTIVE_BG,
                selectcolor=SELECTED_BG,
                relief="raised",
                offrelief="raised",
                bd=2,
                padx=8,
                pady=0,
            )
            unselected, _ = CheckBoxGroup.indicator_images(
                radio, self.indicator_size, style="radio", background=BUTTON_BG, check_color=SELECTED_COLOR
            )
            _, selected = CheckBoxGroup.indicator_images(
                radio, self.indicator_size, style="radio", background=SELECTED_BG, check_color=SELECTED_COLOR
            )
            radio.config(image=unselected, selectimage=selected, compound="left", indicatoron=False)
            radio.grid(row=0, column=column, sticky="nsew", padx=self.button_pad_x, pady=self.button_pad_y)
            self._radios.append(radio)
        self._earlier_btn, self._later_btn = self._buttons(
            self._main_page,
            ("Move Left", lambda: self.move_selected(-1)),
            ("Move Right", lambda: self.move_selected(1)),
        )
        if self.section_gap:
            Box(self._main_page, align="top", width=1, height=self.section_gap)
        self._add_btn, self._remove_btn, self._clear_btn = self._buttons(
            self._main_page,
            ("Add…", self.open_picker),
            ("Remove", self.remove_selected),
            ("Clear All", self.clear_components),
        )
        if self.section_gap:
            Box(self._main_page, align="top", width=1, height=self.section_gap)
        self._metadata_box = TitleBox(self._main_page, text="Info", align="top")
        self._metadata_box.tk.config(bd=1, relief="groove", padx=self.button_pad_x, pady=self.button_pad_y)
        field_width = self.content_width - 2 * (self.button_pad_x + 1)
        self._name_field, _ = self._field(
            self._metadata_box, "Route Name", EditorType.KEYBOARD, 31, self._on_metadata, width=field_width
        )
        self._number_field, _ = self._field(
            self._metadata_box, "Route #", EditorType.KEYPAD, 4, self._on_metadata, width=field_width
        )
        self._tmcc_id_field, _ = (
            self._field(self._metadata_box, "TMCC ID", width=field_width) if not self.gui.compact else (None, None)
        )
        if self.section_gap:
            Box(self._main_page, align="top", width=1, height=self.section_gap)

        self._picker_page = Box(body, align="top", visible=False)
        Text(self._picker_page, text="ADD TO ROUTE", size=self.gui.s_14)
        self._filter_btns = self._buttons(
            self._picker_page,
            *((name, partial(self.set_filter, name)) for name in ("Switches", "Routes", "All")),
        )
        self._sort_btns = self._buttons(
            self._picker_page,
            ("Name", lambda: self.set_sort("Name")),
            ("TMCC ID", lambda: self.set_sort("TMCC ID")),
            ("Ascending ↑", self.toggle_sort_direction),
        )
        self._search_field, self._search_btn = self._field(
            self._picker_page, "Search", EditorType.KEYBOARD, 31, self._on_search, label_width=6, commit_label="Search"
        )
        self._search_btn.text = "Clear"
        self._search_btn.tk.master.config(
            width=max(int(self.row_height * 1.6), self._search_btn.tk.winfo_reqwidth() + 2 * self.button_pad_x)
        )
        self._search_btn.text = "Edit"
        self._search_btn.update_command(self._edit_search)
        self._picker_count = Text(self._picker_page, text="", size=self.gui.s_12)
        self._picker = self._canvas(self._picker_page, self.picker_row_height * self.picker_rows, False)
        if self.gui.compact:
            self._picker_scrollbar = TouchScrollbar(
                self._picker.master, command=self.scroll_picker, width=self.picker_bar_width, min_thumb_length=32
            )
        else:
            self._picker_scrollbar = tk.Scrollbar(
                self._picker.master,
                orient="vertical",
                command=self.scroll_picker,
                width=self.picker_bar_width,
                troughcolor=BAR_TROUGH_COLOR,
                bg=BAR_COLOR,
                activebackground=BAR_ACTIVE_COLOR,
                highlightthickness=BAR_EDGE_PX,
                highlightbackground=BAR_EDGE_COLOR,
                takefocus=0,
            )
        self._picker_scrollbar.place(
            relx=1.0, x=-self.picker_bar_width, y=0, width=self.picker_bar_width, relheight=1.0
        )
        self._picker.config(
            yscrollincrement=1 if self.desktop_controls else self.picker_row_height,
            yscrollcommand=self._picker_scrollbar.set,
        )
        self._status = Text(body, text="", size=self.gui.s_12, width="fill", height=2)
        self._status.tk.config(wraplength=self.content_width)
        for widget in (body.tk.master, body.tk, self._picker_page.tk):
            widget.bind("<Configure>", self._schedule_picker_resize, add="+")
        self._picker_page.tk.bind("<Map>", self._schedule_picker_resize, add="+")

    def build_footer(self, footer: Box) -> None:
        row = Box(footer, align="top", layout="grid")
        self._cancel_btn = self._button(row, "Cancel", self.cancel, column=0, columns=3)
        self._clear_route_btn = self._button(row, "Clear", self.clear_route, column=1, columns=3, hold=True)
        self._save_btn = self._button(row, "Save Route", self.save, column=2, columns=3)
        footer.tk.bind("<Configure>", self._schedule_picker_resize, add="+")

    def _schedule_picker_resize(self, _event=None):
        if self._picking and not self._picker_resize_pending:
            self._picker_resize_pending = True
            self._picker_page.tk.master.master.after_idle(self._resize_picker)

    def _resize_picker(self):
        self._picker_resize_pending = True
        try:
            page = self._picker_page.tk
            if not self._picking or not page.winfo_exists():
                return
            overlay = page.master.master
            overlay.update_idletasks()
            if not self._picking or not page.winfo_exists() or not page.winfo_ismapped():
                return
            available = overlay.winfo_height()
            if available <= 1:
                return
            slot = self._picker.master
            # Subtract everything but the list: banner, controls, notes, footer, and spacing.
            available -= overlay.winfo_reqheight() - slot.winfo_reqheight()
            rows = max(0, available // self.picker_row_height)
            height = max(1, rows * self.picker_row_height)
            if rows == self._picker_rows and height == slot.winfo_reqheight():
                return
            top = self._picker.canvasy(0)
            self._picker_rows = rows
            slot.config(height=height)
            self._picker.config(height=height)
            self._draw_picker()
            total = max(1, max(rows, len(self._candidates)) * self.picker_row_height)
            self._picker.yview_moveto(max(0, min(top, total - height)) / total)
        finally:
            self._picker_resize_pending = False

    def configure(self, tmcc_id: int, state: RouteState | None = None) -> None:
        self._clear_route_btn.cancel_interaction()
        self._end_inline_edits()
        self._tmcc_id = tmcc_id
        self._state = state
        self.draft = RouteDraft(
            tmcc_id,
            (state.components or ()) if state else (),
            road_name=state.road_name if state and state.is_road_name else "",
            road_number=state.road_number if state and state.is_road_number else "",
        )
        self._name_field.value = self.draft.road_name
        self._number_field.value = self.draft.road_number
        if self._tmcc_id_field is not None:
            self._tmcc_id_field.value = f"{tmcc_id:02d}"
        self._selected = 0 if self.draft.components else None
        self._picking = False
        self._refresh()
        self._cards.xview_moveto(0)

    def _lookup_route(self, tmcc_id: int):
        return self.gui.state_store.get_state(CommandScope.ROUTE, tmcc_id, False)

    def _component_label(self, component):
        scope = CommandScope.ROUTE if component.is_route else CommandScope.SWITCH
        state = self.gui.state_store.get_state(scope, component.tmcc_id, False)
        return self._state_name(state, scope, component.tmcc_id)

    @staticmethod
    def _state_name(state, scope, tmcc_id):
        return (state.road_name if state and state.is_road_name else None) or (
            state.name if state else f"{scope.title} {tmcc_id:02d}"
        )

    def _refresh(self, message: str = "") -> None:
        if self.draft is None or self._main_page is None:
            return
        if self._picking:
            self._main_page.hide()
            self._picker_page.show()
        else:
            self._picker_page.hide()
            self._main_page.show()
        components = self.draft.components
        self._route_label.value = f"Route {self._tmcc_id:02d}"
        self._count.value = f"{len(components)} of 16 cards used"
        self._draw_cards()
        selected = self._selected is not None
        component = components[self._selected] if selected else None
        self._previous_btn.enabled = selected and self._selected > 0
        self._next_btn.enabled = selected and self._selected < len(components) - 1
        self._earlier_btn.enabled = self._previous_btn.enabled
        self._later_btn.enabled = self._next_btn.enabled
        self._remove_btn.enabled = selected
        self._clear_btn.enabled = bool(components)
        self._add_btn.enabled = len(components) < 16
        self._position.set("" if component is None or component.is_route else "thru" if component.is_thru else "out")
        for value, radio in zip(("thru", "out"), self._radios):
            radio.config(
                state="normal" if component and component.is_switch else "disabled",
                background=SELECTED_BG if self._position.get() == value else BUTTON_BG,
            )
        if component:
            self._selection.value = f"Card {self._selected + 1}: {self._component_label(component)}"
        else:
            self._selection.value = "No components yet. Tap Add to choose a switch or route."
        self._save_btn.text = "Add to Route" if self._picking else "Save Route"
        self._save_btn.enabled = self._candidate is not None and len(components) < 16 if self._picking else True
        state = self._lookup_route(self._tmcc_id)
        self._clear_route_btn.enabled = (
            not self._picking and isinstance(state, RouteState) and not state.is_deleted and state.is_deletable
        )
        self._status.value = message or (
            "Choose a component, then tap Add to Route."
            if self._picking
            else ("Unsaved changes · " if self.draft.dirty else "") + "Editing does not operate the layout."
        )
        if not message and self._clear_route_btn.enabled:
            self._status.value += "\nHold Clear for 3 seconds to delete from Base 3."
        self._schedule_picker_resize()

    def _draw_cards(self):
        canvas = self._cards
        canvas.delete("all")
        components = self.draft.components
        canvas.config(
            scrollregion=(0, 0, max(self.card_view_width, len(components) * self.card_width), self.card_height)
        )
        if not components:
            canvas.create_text(
                self.card_view_width / 2,
                self.card_height / 2,
                text="No components yet\nTap Add to get started",
                font=("Helvetica", self.gui.s_14),
                justify="center",
            )
        for index, component in enumerate(components):
            x = index * self.card_width
            selected = index == self._selected
            canvas.create_rectangle(
                x + 4,
                4,
                x + self.card_width - 4,
                self.card_height - 4,
                fill=SELECTED_BG if selected else CARD_BG,
                outline=SELECTED_COLOR if selected else "#8b949e",
                width=3 if selected else 1,
            )
            canvas.create_text(
                x + 12,
                8,
                text=f"{index + 1}   {'ROUTE' if component.is_route else 'SWITCH'}",
                anchor="nw",
                font=("Helvetica", self.gui.s_12, "bold"),
            )
            self._draw_track(canvas, x, component)
            name = self._component_label(component)
            name_item = canvas.create_text(
                x + self.card_width / 2,
                self.card_height * (0.57 if self.desktop_controls else 0.60),
                text=name,
                width=self.card_width - 24,
                font=("Helvetica", min(self.gui.s_12, int(self.card_height * 0.105)), "bold"),
                justify="center",
            )
            bounds = canvas.bbox(name_item)
            while name and bounds[3] - bounds[1] > self.card_height * 0.35:
                name = name[:-1].rstrip()
                canvas.itemconfigure(name_item, text=f"{name}…")
                bounds = canvas.bbox(name_item)
            mode = "" if component.is_route else "THRU · " if component.is_thru else "OUT · "
            canvas.create_text(
                x + self.card_width / 2,
                self.card_height - 17,
                text=f"{mode}ID {component.tmcc_id:02d}",
                font=("Helvetica", self.gui.s_12),
            )

    def _draw_track(self, canvas, x, component):
        left, middle, right = x + 24, x + self.card_width / 2, x + self.card_width - 24
        y = self.card_height * 0.29
        divergence = self.card_height * 0.08
        if component.is_route:
            canvas.create_line(
                left,
                y,
                middle,
                y,
                middle,
                y + divergence,
                right,
                y + divergence,
                arrow="last",
                width=4,
                fill=SELECTED_COLOR,
            )
            return
        canvas.create_line(left, y, right, y, fill="#9aa4ae", width=6)
        canvas.create_line(middle, y, right, y + divergence, fill="#9aa4ae", width=6)
        path = (left, y, right, y) if component.is_thru else (left, y, middle, y, right, y + divergence)
        canvas.create_line(*path, fill=SELECTED_COLOR, width=6)

    def select_row(self, index: int) -> None:
        if self.draft is not None and 0 <= index < len(self.draft.components):
            self._selected = index
            self._refresh()
            self._reveal_selected()

    def select_relative(self, delta: int) -> None:
        if self.draft and self.draft.components:
            self.select_row(max(0, min((self._selected or 0) + delta, len(self.draft.components) - 1)))

    def _reveal_selected(self):
        if self._selected is None:
            return
        total = max(self.card_view_width, len(self.draft.components) * self.card_width)
        left = self._cards.xview()[0] * total
        start = self._selected * self.card_width
        if start < left:
            self._cards.xview_moveto(start / total)
        elif start + self.card_width > left + self.card_view_width:
            self._cards.xview_moveto((start + self.card_width - self.card_view_width) / total)

    def set_position(self, flags: int) -> None:
        if self.draft is None or self._selected is None or flags not in (0, 1):
            return
        component = self.draft.components[self._selected]
        if component.is_route:
            return
        try:
            self.draft.set_component(self._selected, component.tmcc_id, flags, self._lookup_route)
        except ValueError as exc:
            self._refresh(str(exc))
            return
        self._refresh()

    def move_selected(self, delta: int) -> None:
        if self.draft is not None and self._selected is not None:
            self._selected = self.draft.move(self._selected, delta)
            self._refresh()
            self._reveal_selected()

    def remove_selected(self) -> None:
        if self.draft is not None and self._selected is not None:
            self.draft.remove(self._selected)
            self._selected = min(self._selected, len(self.draft.components) - 1) if self.draft.components else None
            self._refresh()
            self._reveal_selected()

    def clear_components(self) -> None:
        if (
            self.draft
            and self.draft.components
            and self.gui.app.yesno("Clear route?", "Remove all components from this route draft?")
        ):
            self.draft.clear()
            self._selected = None
            self._refresh()

    def open_picker(self) -> None:
        if self.draft is None or len(self.draft.components) >= 16:
            return
        self._end_inline_edits(commit=True)
        self._picking = True
        self._candidate = None
        self._picker_cursor = None
        self._refresh_picker()

    def set_filter(self, value: str) -> None:
        self._filter = value
        self._refresh_picker()

    def set_sort(self, value: str) -> None:
        self._sort = value
        self._refresh_picker()

    def toggle_sort_direction(self) -> None:
        self._descending = not self._descending
        self._refresh_picker()

    def _on_search(self, _field, _new, _old) -> None:
        self._refresh_picker()

    def _edit_search(self) -> None:
        if self._search_field.value:
            self._search_field.cancel_edit()
            self._search_field.value = ""
            self._refresh_picker()
        else:
            self._search_field.begin_edit()

    def _refresh_picker(self) -> None:
        self._picker_scroll_pixels.reset()
        self._search_btn.text = "Clear" if self._search_field.value else "Edit"
        scopes = (
            (CommandScope.SWITCH, CommandScope.ROUTE)
            if self._filter == "All"
            else (CommandScope.SWITCH if self._filter == "Switches" else CommandScope.ROUTE,)
        )
        search = str(self._search_field.value).strip().casefold()
        self._candidates = [
            (scope, state)
            for scope in scopes
            for state in self.gui.state_store.get_all(scope)
            if not state.is_deleted
            and 1 <= state.tmcc_id <= 99
            and search in self._state_name(state, scope, state.tmcc_id).casefold()
        ]
        self._candidates.sort(
            key=lambda item: (
                (self._state_name(item[1], item[0], item[1].tmcc_id).casefold(), item[1].tmcc_id, item[0].name)
                if self._sort == "Name"
                else (item[1].tmcc_id, item[0].name)
            ),
            reverse=self._descending,
        )
        keys = {(scope, state.tmcc_id) for scope, state in self._candidates}
        if self._candidate not in keys:
            self._candidate = None
        if self._picker_cursor not in keys:
            self._picker_cursor = None
        for name, button in zip(("Switches", "Routes", "All"), self._filter_btns):
            button.text = f"{'● ' if self._filter == name else ''}{name}"
        for name, button in zip(("Name", "TMCC ID"), self._sort_btns):
            button.text = f"{'● ' if self._sort == name else ''}{name}"
        self._sort_btns[2].text = "Descending ↓" if self._descending else "Ascending ↑"
        hint = "Click to select; scroll or use ↑ / ↓" if self.desktop_controls else "Tap to select; swipe to browse"
        self._picker_count.value = f"{len(self._candidates)} available · {hint}"
        self._draw_picker()
        self._picker.yview_moveto(0)
        self._refresh()

    def _draw_picker(self):
        canvas = self._picker
        canvas.delete("all")
        columns = None
        if self.picker_inline_details:
            detail_font = tkfont.Font(root=canvas, font=("Helvetica", self.gui.s_12))
            id_x = self.picker_view_width - 14 - detail_font.measure("· ID 99")
            number_x = id_x - 12 - detail_font.measure("· Road #0000")
            scope_x = number_x - 12 - detail_font.measure("Switch")
            columns = (scope_x, number_x, id_x)
        canvas.config(
            scrollregion=(
                0,
                0,
                self.picker_view_width,
                max(1, max(self.picker_rows, len(self._candidates)) * self.picker_row_height),
            )
        )
        if not self._candidates:
            canvas.create_text(
                self.picker_view_width / 2,
                min(self.picker_row_height, self.picker_rows * self.picker_row_height / 2),
                text="No matching components.\nTry another filter or clear the search.",
                font=("Helvetica", self.gui.s_14),
                justify="center",
            )
        for index, (scope, state) in enumerate(self._candidates):
            y = index * self.picker_row_height
            selected = self._candidate == (scope, state.tmcc_id)
            focused = self.gui.compact and self._picker_cursor == (scope, state.tmcc_id)
            active = (isinstance(state, SwitchState) and state.is_thru) or (
                isinstance(state, RouteState) and state.is_aligned
            )
            canvas.create_rectangle(
                2,
                y + 2,
                self.picker_view_width - 2,
                y + self.picker_row_height - 2,
                fill=ACTIVE_STATE_BG if active else SELECTED_BG if selected else CARD_BG,
                outline=SELECTED_COLOR if selected or focused else "#c1c8d0",
                width=3 if focused else 1,
            )
            radius = self.indicator_size / 2
            center_x, center_y = radius + 12, y + self.picker_row_height / 2
            canvas.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                outline=SELECTED_COLOR if selected else "#586574",
                width=2,
                fill="white",
            )
            if selected:
                dot = radius * 0.55
                canvas.create_oval(
                    center_x - dot,
                    center_y - dot,
                    center_x + dot,
                    center_y + dot,
                    outline=SELECTED_COLOR,
                    fill=SELECTED_COLOR,
                )
            text_x = self.indicator_size + 24
            name = self._state_name(state, scope, state.tmcc_id)
            name_width = (columns[0] if columns else self.picker_view_width) - text_x - 14
            name_item = canvas.create_text(
                text_x,
                center_y if columns else y + 8,
                text=name,
                anchor="w" if columns else "nw",
                width=0 if columns else name_width,
                font=(
                    "Helvetica",
                    self.gui.s_14 if columns else min(self.gui.s_14, int(self.picker_row_height * 0.26)),
                    "bold",
                ),
            )
            bounds = canvas.bbox(name_item)
            while name and (
                bounds[2] - bounds[0] > name_width if columns else bounds[3] - bounds[1] > self.picker_row_height * 0.45
            ):
                name = name[:-1].rstrip()
                canvas.itemconfigure(name_item, text=f"{name}…")
                bounds = canvas.bbox(name_item)
            number = state.road_number if state.is_road_number else "—"
            if columns:
                for x, text in zip(columns, (scope.title, f"· Road #{number}", f"· ID {state.tmcc_id:02d}")):
                    canvas.create_text(x, center_y, text=text, anchor="w", font=("Helvetica", self.gui.s_12))
            else:
                canvas.create_text(
                    text_x,
                    y + self.picker_row_height - (12 if self.desktop_controls else 18),
                    text=f"{scope.title} · Road #{number} · ID {state.tmcc_id:02d}",
                    anchor="w",
                    font=("Helvetica", min(self.gui.s_12, int(self.picker_row_height * 0.22))),
                )

    def choose_candidate(self, index: int) -> None:
        if 0 <= index < len(self._candidates):
            scope, state = self._candidates[index]
            self._candidate = (scope, state.tmcc_id)
            self._picker_cursor = self._candidate
            self._draw_picker()
            self._refresh()

    def pad_step(self, delta: int) -> bool:
        if not self.pad_ready or not self._candidates:
            return False
        index = next(
            (i for i, (scope, state) in enumerate(self._candidates) if self._picker_cursor == (scope, state.tmcc_id)),
            None,
        )
        index = int(self._picker.canvasy(0) // self.picker_row_height) if index is None else index + delta
        index = max(0, min(index, len(self._candidates) - 1))
        scope, state = self._candidates[index]
        self._picker_cursor = (scope, state.tmcc_id)
        self._draw_picker()
        self._reveal_picker_index(index)
        return True

    def pad_mark(self) -> bool:
        if not self.pad_step(0):
            return False
        self._candidate = self._picker_cursor
        self._draw_picker()
        self._refresh()
        return True

    def pad_clear(self) -> None:
        if self.pad_ready:
            self._candidate = None
            self._draw_picker()
            self._refresh()

    def pad_add(self) -> None:
        if self.pad_mark():
            self.add_selected()

    def _reveal_picker_index(self, index: int) -> None:
        total = max(self.picker_rows, len(self._candidates)) * self.picker_row_height
        top = self._picker.yview()[0] * total
        start = index * self.picker_row_height
        height = self.picker_rows * self.picker_row_height
        if start < top:
            self._picker.yview_moveto(start / total)
        elif start + self.picker_row_height > top + height:
            self._picker.yview_moveto((start + self.picker_row_height - height) / total)

    def _focus_list(self, canvas) -> None:
        if self.desktop_controls and not any(
            field is not None and field.is_editing
            for field in (self._name_field, self._number_field, self._search_field)
        ):
            canvas.focus_set()

    def _navigate_list(self, delta: int, horizontal: bool):
        if horizontal:
            self.select_relative(delta)
        elif self._candidates:
            index = next(
                (i for i, (scope, state) in enumerate(self._candidates) if self._candidate == (scope, state.tmcc_id)),
                None,
            )
            if index is None:
                index = int(self._picker.canvasy(0) // self.picker_row_height)
            else:
                index += delta
            index = max(0, min(index, len(self._candidates) - 1))
            self.choose_candidate(index)
            self._reveal_picker_index(index)
        return "break"

    def add_selected(self) -> None:
        if not self._picking or self._candidate is None:
            return
        scope, tmcc_id = self._candidate
        state = self.gui.state_store.get_state(scope, tmcc_id, False)
        if state is None or state.is_deleted:
            self._candidate = None
            self._refresh_picker()
            self._status.value = "That component is no longer available. Choose another."
            return
        try:
            self.draft.set_component(None, tmcc_id, 3 if scope == CommandScope.ROUTE else 0, self._lookup_route)
        except ValueError as exc:
            self._status.value = str(exc)
            return
        self._selected = len(self.draft.components) - 1
        self._picking = False
        self._refresh()
        self._reveal_selected()

    def scroll_by_pixels(self, pixels: int) -> None:
        canvas = self.scroll_view
        if canvas is None or not pixels:
            return
        self._gesture = None
        if self._picking:
            first, last = canvas.yview()
            if (pixels < 0 and first <= 0) or (pixels > 0 and last >= 1):
                self._picker_scroll_pixels.reset()
                return
            unit = 1 if self.desktop_controls else self.picker_row_height
            steps = self._picker_scroll_pixels.consume(pixels, unit)
            if steps:
                canvas.yview_scroll(steps, "units")
        elif self.draft.components:
            total = max(3, len(self.draft.components)) * self.card_width
            canvas.xview_moveto(canvas.xview()[0] + pixels / total)

    def scroll_picker(self, *args) -> None:
        if len(args) == 3 and args[0] == "scroll" and args[2] == "units":
            units = self.picker_row_height if self.desktop_controls else 1
            self._picker.yview_scroll(int(args[1]) * units, "units")
        else:
            self._picker.yview(*args)

    def _scroll_start(self, canvas, event):
        self._focus_list(canvas)
        self._gesture = (canvas, event.x, event.y, False)
        canvas.scan_mark(event.x, event.y)

    def _scroll_drag(self, canvas, event, horizontal):
        if self._gesture is None or self._gesture[0] is not canvas:
            return
        _, x, y, moved = self._gesture
        moved = moved or abs(event.x - x if horizontal else event.y - y) > 8
        self._gesture = (canvas, x, y, moved)
        if moved:
            canvas.scan_dragto(event.x if horizontal else x, y if horizontal else event.y, gain=1)

    def _scroll_end(self, canvas, event, horizontal):
        gesture, self._gesture = self._gesture, None
        if gesture is None or gesture[0] is not canvas:
            return
        if gesture[3] or abs(event.x - gesture[1]) > 8 or abs(event.y - gesture[2]) > 8:
            return
        if horizontal:
            self.select_row(int(canvas.canvasx(event.x) // self.card_width))
        else:
            self.choose_candidate(int(canvas.canvasy(event.y) // self.picker_row_height))

    def _wheel(self, canvas, event, horizontal):
        delta = getattr(event, "delta", 0)
        number = getattr(event, "num", None)
        if number in (4, 5):
            direction = -1 if number == 4 else 1
        elif delta:
            units = max(1, int(abs(delta))) if platform == "darwin" else max(1, int(abs(delta) / 120))
            direction = -units if delta > 0 else units
        else:
            return "break"
        if not horizontal and self.desktop_controls:
            direction *= self.picker_row_height
        (canvas.xview_scroll if horizontal else canvas.yview_scroll)(direction, "units")
        return "break"

    def _touchpad_scroll(self, canvas, event, horizontal):
        # Tk 9 packs signed 16-bit horizontal/vertical pixel deltas into %D.
        dx, dy = (event.delta >> 16) & 0xFFFF, event.delta & 0xFFFF
        dx = dx if dx < 0x8000 else dx - 0x10000
        dy = dy if dy < 0x8000 else dy - 0x10000
        if horizontal:
            delta = dx if abs(dx) > abs(dy) else dy
            if delta and self.draft is not None and self.draft.components:
                total = max(3, len(self.draft.components)) * self.card_width
                canvas.xview_moveto(canvas.xview()[0] - delta / total)
        elif dy and self._candidates:
            canvas.yview_scroll(-dy, "units")
        return "break"

    def _on_metadata(self, _field, _new, _old) -> None:
        try:
            self.draft.set_metadata(str(self._name_field.value), str(self._number_field.value))
        except ValueError as exc:
            self._refresh(str(exc))
            return
        self._refresh()

    def _metadata_dirty(self) -> bool:
        return self.draft is not None and (
            (self._name_field.value, self._number_field.value) != (self.draft.road_name, self.draft.road_number)
            or any(field.is_editing and field.is_changed for field in (self._name_field, self._number_field))
        )

    def cancel(self) -> None:
        if self._picking:
            self._end_inline_edits()
            self._picking = False
            self._refresh()
        else:
            self._close()

    def confirm_close(self) -> bool:
        if (self.draft is not None and self.draft.dirty) or self._metadata_dirty():
            if self.desktop_controls:
                return self.gui.app.yesno("Discard route changes?", "Discard unsaved route changes?")
            dialog = RouteDiscardDialog(
                getattr(self.gui, "root", self.gui.app).tk,
                width=min(self.content_width - 24, max(420, round(self.gui.width * 0.85))),
                text_size=max(18, self.gui.s_14),
                button_height=max(64, self.row_height + 16),
            )
            return bool(dialog.result)
        return True

    def _end_inline_edits(self, *, commit: bool = False) -> None:
        for field in (self._name_field, self._number_field, self._search_field):
            if field is not None and field.is_editing:
                field.commit_edit() if commit else field.cancel_edit()

    def _on_closed(self, _overlay=None) -> None:
        if self._clear_route_btn is not None:
            self._clear_route_btn.cancel_interaction()
        self._end_inline_edits()
        self._picking = False
        self._gesture = None

    def clear_route(self) -> None:
        if self.draft is None or self._picking:
            return
        self._clear_route_btn.cancel_interaction()
        state = self._lookup_route(self._tmcc_id)
        if not isinstance(state, RouteState) or state.is_deleted or not state.is_deletable:
            self._refresh("Route not cleared: it is no longer available to clear.")
            return
        try:
            self.gui.clear_record(state)
        except Exception as exc:
            log.warning("Unable to clear route %s: %s", self._tmcc_id, exc)
            self._status.value = f"Route not cleared: {exc}"
            return
        if not state.is_deleted:
            self._refresh("Route not cleared: the record could not be deleted.")
            return
        self._end_inline_edits()
        self.draft = None
        self._state = None
        self._selected = None
        self._clear_route_btn.enabled = False
        self._save_btn.enabled = False
        self._close()

    def save(self) -> None:
        if self.draft is None:
            return
        if self._picking:
            self.add_selected()
            return
        self._end_inline_edits(commit=True)
        try:
            self.draft.set_metadata(str(self._name_field.value), str(self._number_field.value))
            self.draft.validate(self._lookup_route)
            state = self._lookup_route(self._tmcc_id)
            if state is None:
                state = self.gui.create_provisional_component(CommandScope.ROUTE, self._tmcc_id)
            reqs = self.draft.build_requests(state, self._lookup_route)
            BaseReq.process_sync_reqs([*reqs, state], do_async=True)
        except Exception as exc:
            log.warning("Unable to save route %s: %s", self._tmcc_id, exc)
            self._status.value = f"Route not saved: {exc}"
            return
        self.draft.mark_saved()
        self._state = state
        self._close()
        # noinspection protected-member
        self.gui._scope_tmcc_ids[CommandScope.ROUTE] = self._tmcc_id
        self.gui.ops_mode(update_info=True, state=state)
