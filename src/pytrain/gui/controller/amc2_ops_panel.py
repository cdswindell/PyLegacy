#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from tkinter import font as tkfont, TclError
from typing import Iterator, TYPE_CHECKING

from guizero import Box, Slider, Text

from ..components.checkbox_group import CheckBoxGroup
from ..components.hold_button import HoldButton
from ..guizero_base import LIONEL_BLUE, LIONEL_ORANGE
from .engine_gui_conf import ACC_PANEL_KEY, INFO_KEY, LCS_PANEL_KEY
from ...db.accessory_state import AccessoryState
from ...pdi.amc2_req import Amc2Req
from ...pdi.constants import Amc2Action, PdiCommand
from ...protocol.command_req import CommandReq
from ...protocol.constants import CommandScope
from ...protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

OUTPUT_STEP = 5
BUTTON_ON_BG = "green"
BUTTON_OFF_BG = "lightgrey"
PAGE_OPTS = [["Motors", 0], ["Lights", 1]]

PAGE_LAYOUT: list[tuple[str, list[tuple[str, int, str]]]] = [
    ("Motors", [("motor", 1, "Motor #1"), ("motor", 2, "Motor #2")]),
    ("Lights", [("lamp", 1, "Light #1"), ("lamp", 2, "Light #2"), ("lamp", 3, "Light #3"), ("lamp", 4, "Light #4")]),
]

# The navigation column that stands to the right of the sliders, top to bottom. These keys used
# to share the header row with the page selector, where the selector's own width left the last
# one clipped by the panel border on both the Steam Deck and the Pi. A column of its own is
# always as wide as its widest label and takes its room from the sliders, which have height to
# spare and can give up a little width. It is a column of the panel rather than of the sliders'
# grid, spanning the header row as well, so the page selector is laid out over the sliders and
# nothing of it is ever drawn above these keys.
NAV_KEYS: tuple[str, ...] = (ACC_PANEL_KEY, INFO_KEY, LCS_PANEL_KEY)

# What the panel and the box it sits in spend on their own borders, left and right. Both are
# built with border=2 -- this panel's root below, its container in KeypadView -- and the width
# the panel measures is the display area's, borders included. A layout that hands all of it to
# the columns is over by this much, and what runs off the right edge is the last column: the
# navigation keys, which is how they came to be clipped on both the Deck and the Pi.
PANEL_BORDER_PX = 2
PANEL_CHROME_PX = PANEL_BORDER_PX * 4

# The two columns the panel itself is laid out in: the header and the sliders under it down one,
# the navigation keys down the other.
SLIDER_COLUMN = 0
NAV_COLUMN = 1

# What a painted selector row adds to the width it is handed: its border and highlight ring,
# either side of it. Six pixels, measured in CheckBoxGroup.stretch_rows -- a row set to 300
# comes out 306 -- and taken off each option's share here, so the two options together are no
# wider than the sliders they are laid out over and neither overhangs the navigation column.
SELECTOR_ROW_CHROME_PX = 6

# The least an output's toggle key is taken to spend around its label: its border and
# highlight ring either side, and a little air so two neighboring labels do not read as one
# word. A platform is free to spend more -- what a button pads its label by is the toolkit's
# business, not the app's -- so this is a floor under a measurement, not the figure itself.
TOGGLE_LABEL_CHROME_PX = 10

# Pixels of label per character per point of font, for the one case where the font itself
# cannot be measured (no display, as under test). Deliberately generous: a point is a pixel on
# a 72dpi display and four thirds of one at 96dpi, which is part of why "Light #1" fits its
# column on the Steam Deck and ran the full width of the Pi's at the same nominal size.
TOGGLE_CHAR_WIDTH_RATIO = 0.9


@dataclass(slots=True)
class OutputWidgets:
    page_idx: int
    container: Box
    toggle_btn: HoldButton
    level_box: Text
    slider: Slider
    output_type: str
    output_id: int
    label: str


class Amc2OpsPanel:
    def __init__(self, host: EngineGui) -> None:
        self._host = host
        self._parent: Box | None = None
        self._root: Box | None = None
        self._header: Box | None = None
        self._nav_box: Box | None = None
        self._nav_cells: list[Box] = []
        self._nav_buttons: dict[str, HoldButton] = {}
        self._page_selector: CheckBoxGroup | None = None
        self._suspend_page_selector = False
        self._controls: Box | None = None
        self._page_index = 0
        self._active_tmcc_id: int | None = None
        self._outputs: dict[tuple[str, int], OutputWidgets] = {}
        self._suspended_slider_callbacks: set[tuple[int, str, int]] = set()

    @property
    def visible(self) -> bool:
        return bool(self._root and self._root.visible)

    @property
    def panel_toggle_button(self) -> HoldButton | None:
        """The navigation key that leaves this panel for the generic accessory one.

        Exposed rather than wired here so KeypadView keeps the command, as it does for every
        other key; this panel replaces the keypad entirely, so the key has nowhere else to go.
        """
        return self._nav_buttons.get(ACC_PANEL_KEY)

    @property
    def info_button(self) -> HoldButton | None:
        """The navigation key that opens the state info panel. Wired by KeypadView."""
        return self._nav_buttons.get(INFO_KEY)

    @property
    def lcs_panel_button(self) -> HoldButton | None:
        """The navigation key that opens the LCS module configuration panel. Wired by KeypadView."""
        return self._nav_buttons.get(LCS_PANEL_KEY)

    def build(self, parent: Box) -> Box:
        if self._root is not None:
            return self._root

        self._parent = parent
        host = self._host
        self._root = root = Box(parent, layout="grid", border=2, align="top")

        self._header = header = Box(root, layout="grid", grid=[0, 0], align="top")
        host_width = int(getattr(host, "width", 0) or max(240, int(getattr(host, "button_size", 100) * 3)))
        # Half the sliders' width, near enough, until the panel has a display to measure: the
        # navigation column has yet to be built, so what is left for the sliders is a guess.
        # _center_page_selector settles it against the measured panel on the first layout pass.
        selector_width = max(8, int((getattr(host, "emergency_box_width", 0) or host_width) / 2.3))
        self._page_selector = CheckBoxGroup(
            header,
            size=host.s_18,
            grid=[0, 0],
            options=PAGE_OPTS,
            selected=str(self._page_index),
            horizontal=True,
            align="top",
            width=selector_width,
            # Each option centered in its share of the sliders' width rather than drawn from
            # the left edge of it, so "Motors" stands over Motor #1 and "Lights" over Motor #2.
            anchor="center",
            padx=10,
            pady=max(4, int(round(6 * host.scale_by))),
            style="radio",
            command=self._on_page_selected,
        )
        try:
            header.tk.grid_columnconfigure(0, weight=1)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

        self._controls = controls = Box(root, layout="grid", grid=[0, 1], align="top")
        max_cols = max(len(outputs) for _, outputs in PAGE_LAYOUT)
        try:
            for col in range(max_cols):
                controls.tk.grid_columnconfigure(col, weight=1)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

        for page_idx, (_title, outputs) in enumerate(PAGE_LAYOUT):
            for slot, (output_type, output_id, label) in enumerate(outputs):
                output = self._build_output(
                    controls,
                    page_idx=page_idx,
                    col=slot,
                    output_type=output_type,
                    output_id=output_id,
                    label=label,
                )
                self._outputs[(output_type, output_id)] = output

        self._build_nav_column(root)
        self._set_page(0)
        return root

    def _build_nav_column(self, parent: Box) -> None:
        """The Acc.../Info/LCS... keys, in a column of their own beside the sliders.

        A column of the panel rather than of the sliders' grid, spanning the header row and the
        controls row both: the header then reaches only as far as the sliders it names, so the
        page selector cannot be laid over these keys and they cannot be mistaken for something
        the Lights option leads to. Each key is an ops key's square, so the three match every
        other key in the app and each other, and the sliders give up the width they take, which
        is the one dimension they have to spare. Commands are left to KeypadView, as with every
        other key that leaves a panel.
        """
        host = self._host
        self._nav_box = nav_box = Box(parent, layout="grid", grid=[NAV_COLUMN, 0, 1, 2], align="top")
        key_size = self._nav_key_size()
        for row, label in enumerate(NAV_KEYS):
            # Each key in a cell of its own square, and the cell is what holds the size: a
            # text button's own width and height are read by Tk in characters and lines, not
            # pixels, so a button told it is 80 wide comes out 80 characters wide. Every ops
            # key in the app is square for exactly this reason -- a fixed-size cell that does
            # not propagate, with the button filling it; see GuiZeroBase._build_keypad_button.
            cell = Box(nav_box, layout="auto", grid=[0, row], align="top")
            btn = HoldButton(
                cell,
                text=label,
                align="top",
                text_size=host.s_16,
            )
            self._nav_buttons[label] = btn
            self._nav_cells.append(cell)
            try:
                cell.tk.config(width=key_size, height=key_size)
                cell.tk.pack_propagate(False)
                # Stacked from the top of the column rather than spread down it, so the first
                # key is level with the page selector across from it.
                cell.tk.grid_configure(sticky="n", pady=self._nav_key_gap())
                btn.tk.config(
                    compound="center",
                    anchor="center",
                    padx=0,
                    pady=0,
                    borderwidth=1,
                    highlightthickness=1,
                    width=key_size,
                    height=key_size,
                )
                btn.tk.pack_configure(fill="both", expand=True)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                pass
        try:
            nav_box.tk.grid_columnconfigure(0, weight=0, minsize=key_size)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        self._pin_nav_column()

    def _nav_key_size(self) -> int:
        """The side of a navigation key, in pixels: an ops key's, so all of them match."""
        return max(40, int(getattr(self._host, "button_size", 0) or 0))

    def _nav_key_gap(self) -> int:
        """The gap between one navigation key and the next, as the keypad's own grid leaves."""
        return max(2, int(round(3 * self._host.scale_by)))

    def _pin_nav_column(self) -> None:
        """Hold the navigation column against the right edge, from the top of the panel down.

        The keys are stacked from the top rather than spread down the height the column is
        given, so the first of them is level with the page selector across from it and the
        three read as one block of ops keys. Weight 0 on the column and 1 on the sliders'
        beside it means what a narrow display costs comes off the sliders, which have width to
        give, rather than off a key -- which is square, and cannot give up width without giving
        up the same in height.

        Re-applied on every layout pass rather than set once: guizero re-grids a container's
        children whenever one of them is shown or hidden -- which is what turning the page does
        -- and sticky and padding are not among the options it records.
        """
        root_tk = getattr(self._root, "tk", None)
        nav_tk = getattr(self._nav_box, "tk", None)
        if root_tk is None or nav_tk is None:
            return
        try:
            root_tk.grid_columnconfigure(SLIDER_COLUMN, weight=1)
            root_tk.grid_columnconfigure(NAV_COLUMN, weight=0)
            root_tk.grid_rowconfigure(1, weight=1)
            nav_tk.grid_configure(sticky="new", padx=self._nav_column_pad())
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def show(self, state: AccessoryState | None = None) -> None:
        if self._root is None:
            return
        if self._parent is not None and not self._parent.visible:
            self._parent.show()
        if state is not None:
            self.update_from_state(state)
        if not self._root.visible:
            self._root.show()
        self._apply_available_layout()
        try:
            self._host.app.tk.after(30, self._apply_available_layout)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def refresh_layout(self) -> None:
        self._apply_available_layout()
        try:
            self._host.app.tk.after(30, self._apply_available_layout)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def hide(self) -> None:
        if self._root is not None and self._root.visible:
            self._root.hide()
        if self._parent is not None and self._parent.visible:
            self._parent.hide()

    def next_page(self) -> None:
        self._set_page(self._page_index + 1)

    def previous_page(self) -> None:
        self._set_page(self._page_index - 1)

    def _on_page_selected(self) -> None:
        if self._suspend_page_selector or self._page_selector is None:
            return
        try:
            self._set_page(int(self._page_selector.value))
        except (AttributeError, TypeError, ValueError):
            self._set_page(0)

    def _set_page(self, index: int) -> None:
        total = len(PAGE_LAYOUT)
        self._page_index = index % total
        if self._page_selector is not None:
            selected = str(self._page_index)
            if getattr(self._page_selector, "value", None) != selected:
                self._suspend_page_selector = True
                try:
                    self._page_selector.value = selected
                finally:
                    self._suspend_page_selector = False
        for output in self._outputs.values():
            should_show = output.page_idx == self._page_index
            if should_show and not output.container.visible:
                output.container.show()
            elif not should_show and output.container.visible:
                output.container.hide()
        self._apply_available_layout()
        try:
            self._host.app.tk.after_idle(self._apply_available_layout)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    @staticmethod
    def _measure_widget_y(widget) -> int | None:
        tk_widget = getattr(widget, "tk", None)
        if tk_widget is None:
            return None
        for method_name in ("winfo_rooty", "winfo_y"):
            method = getattr(tk_widget, method_name, None)
            if method is None:
                continue
            try:
                y = int(method())
                if y >= 0:
                    return y
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _measure_widget_h(widget) -> int | None:
        tk_widget = getattr(widget, "tk", None)
        if tk_widget is None:
            return None
        values: list[int] = []
        for method_name in ("winfo_height", "winfo_reqheight"):
            method = getattr(tk_widget, method_name, None)
            if method is None:
                continue
            try:
                h = int(method())
                if h > 0:
                    values.append(h)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                continue
        return max(values) if values else None

    @staticmethod
    def _measure_widget_w(widget) -> int | None:
        tk_widget = getattr(widget, "tk", None)
        if tk_widget is None:
            return None
        values: list[int] = []
        for method_name in ("winfo_width", "winfo_reqwidth"):
            method = getattr(tk_widget, method_name, None)
            if method is None:
                continue
            try:
                w = int(method())
                if w > 1:
                    values.append(w)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                continue
        return max(values) if values else None

    @staticmethod
    def _measure_widget_actual_w(widget) -> int | None:
        """The width a widget *has*, never the width it asks for.

        The two are the same thing everywhere except where the asking is this panel's own: a
        box laid out around content too wide for it reports the content's width as the width it
        requests, so a panel that measures itself and then lays itself out in what it measured
        grows by its own overflow on every pass. That is the loop that walked the navigation
        keys off the right edge; see _display_width.
        """
        tk_widget = getattr(widget, "tk", None)
        method = getattr(tk_widget, "winfo_width", None) if tk_widget is not None else None
        if method is None:
            return None
        try:
            value = int(method())
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            return None
        return value if value > 1 else None

    @staticmethod
    def _measure_widget_req_w(widget) -> int | None:
        tk_widget = getattr(widget, "tk", None)
        method = getattr(tk_widget, "winfo_reqwidth", None) if tk_widget is not None else None
        if method is None:
            return None
        try:
            value = int(method())
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            return None
        return value if value > 0 else None

    @staticmethod
    def _measure_widget_req_h(widget) -> int | None:
        tk_widget = getattr(widget, "tk", None)
        if tk_widget is None:
            return None
        method = getattr(tk_widget, "winfo_reqheight", None)
        if method is None:
            return None
        try:
            value = int(method())
            return value if value > 0 else None
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            return None

    def _compute_available_panel_height(self) -> int | None:
        host = self._host
        try:
            host.app.tk.update_idletasks()
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            return None

        top = None
        image_box = getattr(host, "image_box", None)
        image_top = self._measure_widget_y(image_box)
        image_h = self._measure_widget_h(image_box)
        if image_top is not None and image_h is not None:
            top = image_top + image_h
        else:
            info_box = getattr(host, "info_box", None)
            info_top = self._measure_widget_y(info_box)
            info_h = self._measure_widget_h(info_box)
            if info_top is not None and info_h is not None:
                top = info_top + info_h
        if top is None:
            top = self._measure_widget_y(self._root) if self._parent is None else self._measure_widget_y(self._parent)
        if top is None:
            return None

        app_tk = getattr(host.app, "tk", None)
        if app_tk is None:
            return None
        try:
            app_top = int(app_tk.winfo_rooty())
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            app_top = 0

        app_h = int(getattr(host, "height", 0) or 0)
        method = getattr(app_tk, "winfo_height", None)
        if method is not None:
            try:
                measured = int(method())
                if measured > 0:
                    app_h = max(app_h, measured)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                pass
        screen_h_method = getattr(app_tk, "winfo_screenheight", None)
        if screen_h_method is not None:
            try:
                screen_h = int(screen_h_method())
                if screen_h > 0 and app_h > 0:
                    app_h = min(app_h, screen_h)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                pass
        if app_h <= 0:
            return None

        app_bottom = app_top + app_h
        scope_box = getattr(host, "scope_box", None)
        scope_top_actual = self._measure_widget_y(scope_box)
        scope_req_h = self._measure_widget_req_h(scope_box)
        if scope_req_h is None:
            scope_req_h = self._measure_widget_h(scope_box)
        scope_top_expected = (app_bottom - scope_req_h) if scope_req_h else None

        if scope_top_actual is not None and scope_top_expected is not None:
            # Use the more conservative (higher) scope top to avoid feedback loops.
            bottom = min(scope_top_actual, scope_top_expected)
        else:
            bottom = scope_top_actual if scope_top_actual is not None else scope_top_expected
        if bottom is None:
            fallback_scope_h = max(36, int(round(getattr(host, "button_size", 100) * 0.40)))
            bottom = app_bottom - fallback_scope_h

        bottom -= int(round(6 * host.scale_by))
        available = bottom - top
        return available if available > 0 else None

    def _display_width(self) -> int:
        """How much width the panel has to lay itself out in.

        Read off the display rather than off the panel. Neither this panel nor the box it sits
        in is asked, on purpose: what they answer is what their own contents came to, so laying
        the contents out in that again widens them further on every pass -- the loop that drew
        the navigation keys off the right edge. See _measure_widget_actual_w.

        What is asked is the widest of the things laid out beside the panel -- the scope bar,
        the accessory image, the keypad the panel replaces -- because each of them is given the
        room the panel is given, with whatever the display spends on itself already taken off:
        a Deck pane is 639px wide and 627px of that is inside its focus border. The width the
        host was opened at caps that rather than replacing it, so a neighbor that has grown
        wider than the display cannot take the panel with it, and stands in for it entirely
        before there is anything on screen to measure.
        """
        host = self._host
        declared = [
            int(getattr(host, "emergency_box_width", 0) or 0),
            int(getattr(host, "width", 0) or 0),
        ]
        declared = [value for value in declared if value > 1]
        measured = [
            self._measure_widget_actual_w(getattr(host, "scope_box", None)),
            self._measure_widget_actual_w(getattr(host, "image_box", None)),
            self._measure_widget_actual_w(getattr(host, "keypad_box", None)),
        ]
        measured = [value for value in measured if value and value > 1]
        if measured and declared:
            return min(max(measured), max(declared))
        if measured:
            return max(measured)
        return max(declared) if declared else 0

    def _nav_column_pad(self) -> int:
        """The gap either side of the navigation column, holding it off the sliders."""
        return max(2, int(round(4 * self._host.scale_by)))

    def _nav_column_width(self) -> int:
        """How much width the navigation column takes off the sliders.

        Everything it asks for, and the gaps either side of it. Deliberately not held to a
        share of the panel: a column is given the width it requests whatever minsize it was
        configured with, so reserving less than that does not make the keys narrower -- it only
        leaves the sliders holding width the keys are about to take, and the difference is what
        goes off the right edge. Before the first map there is nothing to measure, so a key's
        own square is assumed, which is what the column comes to.
        """
        measured = self._measure_widget_w(self._nav_box)
        if measured is None:
            measured = self._nav_key_size()
        return measured + self._nav_column_pad() * 2

    def _sliders_width(self, panel_w: int, page_cols: int) -> int:
        """How much of the panel the sliders, and the selector over them, are laid out in.

        What is left of the measured width once the borders the panel is drawn inside, the gaps
        at its edges and the navigation column have taken theirs. Dividing the whole measured
        width among the columns is what drew the last of them off the right edge of the display
        on both the Deck and the Pi; see PANEL_CHROME_PX.
        """
        if panel_w <= 0:
            return 0
        side_pad = int(round(8 * self._host.scale_by))
        floor = page_cols * 60
        return max(floor, panel_w - PANEL_CHROME_PX - (side_pad * 2) - self._nav_column_width())

    def _toggle_base_text_size(self) -> int:
        """The size an output's label is drawn at where its column has room for it."""
        host = self._host
        return max(host.s_12, int(round(14 * host.scale_by)))

    def _toggle_min_text_size(self) -> int:
        """The smallest an output's label is allowed to get before it is left to clip."""
        return max(8, int(round(10 * self._host.scale_by)))

    def _toggle_label_chrome(self, output: OutputWidgets) -> int:
        """What the key around the label takes of the column, beyond the label itself.

        Measured as the difference between the width the key asks for and the width its label
        is drawn at, because how much a button pads its label by is the toolkit's and the
        platform's business: the same key wants 42px more than its label on one and half that
        on another. Reckoning it as a constant is how a label that measured as fitting its
        column still came out wider than the column; TOGGLE_LABEL_CHROME_PX is only the floor.
        """
        requested = self._measure_widget_req_w(output.toggle_btn)
        drawn = self._measure_label_width(
            output.toggle_btn,
            output.label,
            int(getattr(output.toggle_btn, "text_size", 0) or self._toggle_base_text_size()),
        )
        if requested and drawn and requested > drawn:
            return max(TOGGLE_LABEL_CHROME_PX, requested - drawn)
        return TOGGLE_LABEL_CHROME_PX

    @staticmethod
    def _measure_label_width(widget, label: str, size: int) -> int | None:
        """How wide the label is actually drawn at that size, or None with no display to ask.

        Measured from the widget's own font rather than reckoned from the label's length: what
        a point comes to in pixels is the display's business, not the app's, and it is the
        difference between "Light #1" fitting its column on the Deck and filling the Pi's at
        the same nominal size.
        """
        tk_widget = getattr(widget, "tk", None)
        if tk_widget is None or not label:
            return None
        try:
            font = tkfont.Font(font=tk_widget.cget("font"))
            font.configure(size=size)
            measured = int(font.measure(label))
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            return None
        return measured if measured > 0 else None

    def _toggle_text_size(self, output: OutputWidgets, col_w: int) -> int:
        """The size an output's label is drawn at in a column that wide.

        The largest that fits, never larger than the size a roomy column gets. Two sliders to a
        page leave a column half the panel and the base size is never in question; four leave a
        quarter of it, and on the Pi -- 480px across, where the Deck's pane has 639 -- "Light
        #1" at the base size came to more than its column and the four labels ran together edge
        to edge with no gap between them.
        """
        base = self._toggle_base_text_size()
        floor = min(base, self._toggle_min_text_size())
        usable = col_w - self._toggle_label_chrome(output)
        if usable <= 0:
            return base
        for size in range(base, floor - 1, -1):
            measured = self._measure_label_width(output.toggle_btn, output.label, size)
            if measured is None:
                # Nothing to measure the font with: fall back on what a character of it comes
                # to, which is all that can be said about a label without a display.
                estimated = int(usable / (len(output.label) or 1) / TOGGLE_CHAR_WIDTH_RATIO)
                return max(floor, min(base, estimated))
            if measured <= usable:
                return size
        return floor

    def _center_page_selector(self, sliders_w: int) -> None:
        """Give each page option an equal share of the sliders' width, centered in it.

        The selector names what is under it, so it is laid out over the same width the sliders
        are and divided the same way -- two options, two halves. On the Motors page a half is
        one slider column, so "Motors" comes to stand over Motor #1 and "Lights" over Motor #2
        rather than both of them starting at the left edge of the panel, one of them over the
        navigation keys. The centering itself is the row's own anchor; see CheckBoxGroup.
        """
        selector = self._page_selector
        if selector is None or sliders_w <= 0:
            return
        share = int(sliders_w / max(1, len(PAGE_OPTS))) - SELECTOR_ROW_CHROME_PX
        try:
            selector.row_width = max(8, share)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def _apply_available_layout(self) -> None:
        if self._root is None or self._controls is None:
            return
        available = self._compute_available_panel_height()
        if available is None:
            return

        sb = self._host.scale_by
        visible_outputs = [output for output in self._outputs.values() if output.page_idx == self._page_index]
        page_cols = max(1, len(visible_outputs))
        max_cols = max(len(outputs) for _, outputs in PAGE_LAYOUT)

        panel_h = max(120, available)
        panel_w = self._display_width()
        nav_w = self._nav_column_width() if panel_w > 0 else 0
        # What is left for the sliders -- and what the page selector is laid out over, so an
        # option stands over the slider it names rather than over the navigation keys.
        sliders_w = self._sliders_width(panel_w, page_cols)
        # Each box inside the border of the one before it, so the panel ends where the display
        # does: the container across the width the display has, the root inside the container's
        # border, and the columns, narrower again by the gaps at the edges, inside the root's.
        for box, box_w in ((self._parent, panel_w), (self._root, panel_w - PANEL_CHROME_PX)):
            tk_widget = getattr(box, "tk", None)
            if tk_widget is None:
                continue
            try:
                cfg = {"height": panel_h}
                if box_w > 0:
                    cfg["width"] = box_w
                tk_widget.config(**cfg)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                pass
            for propagate_name in ("pack_propagate", "grid_propagate"):
                propagate = getattr(tk_widget, propagate_name, None)
                if propagate is None:
                    continue
                try:
                    propagate(False)
                except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                    continue

        header_h = self._measure_widget_h(self._header) or 0
        controls_h = max(140, panel_h - header_h - 8)
        controls_tk = getattr(self._controls, "tk", None)
        if controls_tk is not None:
            try:
                cfg = {"height": controls_h}
                if sliders_w > 0:
                    cfg["width"] = sliders_w
                controls_tk.config(**cfg)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                pass

        if controls_tk is not None and panel_w > 0:
            col_w = max(58, int(sliders_w / page_cols))
            for col in range(max_cols):
                min_size = col_w if col < page_cols else 0
                try:
                    controls_tk.grid_columnconfigure(col, weight=1, minsize=min_size)
                except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                    continue
            root_tk = getattr(self._root, "tk", None)
            try:
                # The sliders share what is left over; the navigation column keeps the width it
                # asked for, so its keys are never the ones that get clipped.
                root_tk.grid_columnconfigure(SLIDER_COLUMN, weight=1, minsize=sliders_w)
                root_tk.grid_columnconfigure(NAV_COLUMN, weight=0, minsize=nav_w)
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                pass
            self._pin_nav_column()
            self._center_page_selector(sliders_w)
        else:
            col_w = max(58, int(round(self._host.button_size * 0.9)))

        sample = next(iter(self._outputs.values()), None)
        if sample is not None:
            toggle_h = self._measure_widget_h(sample.toggle_btn) or int(round(42 * sb))
            level_h = self._measure_widget_h(sample.level_box) or int(round(34 * sb))
        else:
            toggle_h = int(round(42 * sb))
            level_h = int(round(34 * sb))
        chrome = toggle_h + level_h
        slider_h = max(110, controls_h - chrome - int(round(10 * sb)))
        slider_w = max(16, min(46, int(round(col_w * (0.38 if page_cols <= 2 else 0.30)))))

        for output in self._outputs.values():
            # Each page's own column width, not the visible page's: a label is drawn once, and
            # the four on the Lights page have a quarter of the panel each where the two on the
            # Motors page have a half.
            page_cols_here = max(1, len(PAGE_LAYOUT[output.page_idx][1]))
            label_col_w = max(58, int(sliders_w / page_cols_here)) if sliders_w > 0 else col_w
            output.toggle_btn.text_size = self._toggle_text_size(output, label_col_w)
            output.slider.height = slider_h
            output.slider.width = slider_w
            try:
                output.container.tk.config(width=col_w)
                output.slider.tk.config(
                    width=slider_w,
                    length=max(80, slider_h - 4),
                    sliderlength=max(16, int(slider_h / 8)),
                )
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                pass

    @staticmethod
    def _normalize_level(value: int | float | str) -> int:
        try:
            raw = int(float(value))
        except (TypeError, ValueError):
            return 0
        clipped = min(100, max(0, raw))
        remainder = clipped % OUTPUT_STEP
        if remainder == 0:
            return clipped
        down = clipped - remainder
        up = down + OUTPUT_STEP
        return min(100, up) if (clipped - down) >= (up - clipped) else down

    @staticmethod
    def _format_level(value: int) -> str:
        return f"{max(0, min(100, value)):03d}"

    @staticmethod
    def _style_slider(slider: Slider, is_active: bool) -> None:
        trough = LIONEL_BLUE if is_active else "lightgrey"
        try:
            slider.bg = "white"
            slider.tk.config(troughcolor=trough)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    @staticmethod
    def _set_toggle_button_state(output: OutputWidgets, is_active: bool) -> None:
        output.toggle_btn.text = output.label
        output.toggle_btn.bg = BUTTON_ON_BG if is_active else BUTTON_OFF_BG
        output.toggle_btn.text_color = "white" if is_active else "black"

    @contextmanager
    def _suspend_slider_callback(self, callback_key: tuple[int, str, int]) -> Iterator[None]:
        self._suspended_slider_callbacks.add(callback_key)
        try:
            yield
        finally:
            self._suspended_slider_callbacks.discard(callback_key)

    # noinspection PyArgumentList
    def _set_output_ui(self, output: OutputWidgets, level: int, is_active: bool) -> None:
        normalized = self._normalize_level(level)
        callback_key = (self._active_tmcc_id or 0, output.output_type, output.output_id)
        if self._normalize_level(output.slider.value) != normalized:
            with self._suspend_slider_callback(callback_key):
                output.slider.value = normalized
        output.level_box.value = self._format_level(normalized)
        self._set_toggle_button_state(output, is_active)
        self._style_slider(output.slider, is_active)

    def _build_output(
        self,
        parent: Box,
        *,
        page_idx: int,
        col: int,
        output_type: str,
        output_id: int,
        label: str,
    ) -> OutputWidgets:
        host = self._host
        container = Box(parent, layout="grid", grid=[col, 0], align="top", visible=(page_idx == 0))
        toggle_btn = HoldButton(
            container,
            text=label,
            grid=[0, 0],
            align="top",
            padx=max(2, int(round(4 * host.scale_by))),
            pady=max(4, int(round(7 * host.scale_by))),
        )
        toggle_btn.text_size = max(host.s_12, int(round(14 * host.scale_by)))
        toggle_btn.text_bold = True

        level_box = Text(
            container,
            grid=[0, 1],
            text="000",
            color="black",
            align="top",
            bold=True,
            size=host.s_18,
            width=4,
            font=getattr(host, "digital_font", "TkDefaultFont"),
        )
        level_box.bg = "black"
        level_box.text_color = "white"

        page_cols = len(PAGE_LAYOUT[page_idx][1])
        slider_height = max(int(round(host.button_size * 2.6)), int(round(host.slider_height * 0.72)))
        slider_width = max(16, int(round(host.button_size / 2 if page_cols <= 2 else host.button_size / 3)))
        slider = Slider(
            container,
            grid=[0, 2],
            align="top",
            horizontal=False,
            step=OUTPUT_STEP,
            width=slider_width,
            height=slider_height,
            command=self._slider_change_handler(output_type, output_id),
        )
        slider.tk.config(
            from_=100,
            to=0,
            takefocus=0,
            activebackground=LIONEL_ORANGE,
            bg="white",
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,
            sliderlength=max(16, int(slider_height / 6)),
        )
        slider.tk.bind(
            "<ButtonRelease-1>",
            lambda e, t=output_type, idx=output_id: self._on_slider_release(t, idx, e),
            add="+",
        )
        slider.tk.bind("<Button-1>", lambda e: slider.tk.focus_set(), add="+")
        slider.tmcc_id = 0

        if output_type == "motor":
            toggle_btn.update_command(self.toggle_motor_state, args=[output_id])
        else:
            toggle_btn.update_command(self.toggle_lamp_state, args=[output_id])

        output = OutputWidgets(
            page_idx=page_idx,
            container=container,
            toggle_btn=toggle_btn,
            level_box=level_box,
            slider=slider,
            output_type=output_type,
            output_id=output_id,
            label=label,
        )
        self._set_output_ui(output, 0, False)
        return output

    def _slider_change_handler(self, output_type: str, output_id: int):
        def on_change(value):
            self._on_slider_change(output_type, output_id, value)

        return on_change

    def _on_slider_change(self, output_type: str, output_id: int, value) -> None:
        tmcc_id = self._active_tmcc_id
        if tmcc_id is None:
            return
        callback_key = (tmcc_id, output_type, output_id)
        if callback_key in self._suspended_slider_callbacks:
            return
        output = self._outputs.get((output_type, output_id))
        if output is None:
            return
        output.level_box.value = self._format_level(self._normalize_level(value))

    # noinspection PyArgumentList
    def _on_slider_release(self, output_type: str, output_id: int, _event=None) -> None:
        tmcc_id = self._active_tmcc_id
        if tmcc_id is None:
            return
        callback_key = (tmcc_id, output_type, output_id)
        if callback_key in self._suspended_slider_callbacks:
            return
        output = self._outputs.get((output_type, output_id))
        if output is None:
            return
        value = self._normalize_level(output.slider.value)
        with self._suspend_slider_callback(callback_key):
            output.slider.value = value
        output.level_box.value = self._format_level(value)
        if output_type == "motor":
            self.set_motor_state(tmcc_id, output_id, value)
        else:
            self.set_lamp_state(tmcc_id, output_id, value)

    def update_from_state(self, state: AccessoryState | None) -> None:
        if not isinstance(state, AccessoryState) or not state.is_amc2:
            return
        self._active_tmcc_id = state.tmcc_id
        for (output_type, output_id), output in self._outputs.items():
            output.slider.tmcc_id = state.tmcc_id
            if output_type == "motor":
                motor_state = state.get_motor(output_id)
                level = motor_state.speed if motor_state else 0
                is_active = state.is_motor_on(motor_state) if motor_state else False
            else:
                lamp_state = state.get_lamp(output_id)
                level = lamp_state.level if lamp_state else 0
                is_active = level > 0
            self._set_output_ui(output, level, is_active)

    def _state_for_tmcc(self, tmcc_id: int) -> AccessoryState | None:
        state = self._host.state_store.get_state(CommandScope.ACC, tmcc_id, False)
        if isinstance(state, AccessoryState):
            return state
        active = self._host.active_state
        if isinstance(active, AccessoryState) and active.tmcc_id == tmcc_id:
            return active
        return None

    def set_motor_state(self, tmcc_id: int, motor: int, speed: int | None = None) -> None:
        state = self._state_for_tmcc(tmcc_id)
        if state is None:
            return
        motor_state = state.get_motor(motor)
        current = motor_state.speed if motor_state else 0
        if speed is None:
            CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
            if state.is_motor_on(motor_state):
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()
            return

        normalized = self._normalize_level(speed)
        if normalized == current:
            return
        Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.MOTOR, motor=motor - 1, speed=normalized).send()
        CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=motor).send()
        if normalized > 0:
            CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, tmcc_id).send()
        else:
            CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, tmcc_id).send()

    def set_lamp_state(self, tmcc_id: int, lamp: int, level: int) -> None:
        state = self._state_for_tmcc(tmcc_id)
        if state is None:
            return
        lamp_state = state.get_lamp(lamp)
        current = lamp_state.level if lamp_state else 0
        normalized = self._normalize_level(level)
        if normalized == current:
            return
        Amc2Req(tmcc_id, PdiCommand.AMC2_SET, Amc2Action.LAMP, lamp=lamp - 1, level=normalized).send()
        CommandReq(TMCC1AuxCommandEnum.NUMERIC, tmcc_id, data=lamp + 2).send()

    def toggle_motor_state(self, motor: int) -> None:
        tmcc_id = self._active_tmcc_id
        if tmcc_id is None:
            return
        state = self._state_for_tmcc(tmcc_id)
        if state is None:
            return
        motor_state = state.get_motor(motor)
        level = motor_state.speed if motor_state else 0
        is_active = state.is_motor_on(motor_state) if motor_state else False
        target = 100 if (not is_active and level == 0) else None
        self.set_motor_state(tmcc_id, motor, target)

    def toggle_lamp_state(self, lamp: int) -> None:
        tmcc_id = self._active_tmcc_id
        if tmcc_id is None:
            return
        state = self._state_for_tmcc(tmcc_id)
        if state is None:
            return
        lamp_state = state.get_lamp(lamp)
        level = lamp_state.level if lamp_state else 0
        target = 0 if level > 0 else 100
        self.set_lamp_state(tmcc_id, lamp, target)
