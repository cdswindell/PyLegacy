#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
import time
from pathlib import Path
from tkinter import messagebox, TclError
from typing import Any, Callable, Literal

from guizero import Box, PushButton, Text

from .controls_panel import CONTROLS_TITLE, ControlsPanel
from .engine_gui import EngineGui
from .engine_gui_conf import HALT_KEY, KEY_TO_COMMAND
from .steam_deck_input import (
    ControllerUnavailable,
    ControlProfile,
    DeckInputRouter,
    SteamDeckInputProvider,
)
from ..guizero_base import GuiZeroBase
from ...db.engine_state import EngineState
from ...protocol.constants import CommandScope

STEAM_DECK_WIDTH = 1280
STEAM_DECK_HEIGHT = 800
# No outside margin: FOCUS_BORDER is set as `border=` on the pane Box itself, and Tk draws
# a frame's border and highlight ring inside the widget's own allocation -- so the focus
# indicator never needed room reserved beyond it. The 12px this used to hold back was
# visible as white space down each outer edge.
HORIZONTAL_MARGIN = 0
# Just enough to separate two panes that each already carry a FOCUS_BORDER of their own.
DIVIDER_WIDTH = 2
FOCUS_BORDER = 3
FOCUS_COLOR = "#3B82F6"
UNFOCUSED_COLOR = "#555555"
# Append the text-presentation variation selector (U+FE0E) to the triangle
# heads so the OS renders them as monochrome text honoring ``FOCUS_COLOR``
# instead of as black color-emoji (the ``▬`` shaft is not emoji-eligible).
FOCUS_ARROW_LEFT = "◀\ufe0e▬"
FOCUS_ARROW_RIGHT = "▬▶\ufe0e"
FOCUS_ARROW_SIZE = 26
# Controls-screen chrome. The header band reuses FOCUS_COLOR, the accent this GUI
# already uses for the focused pane and the focus arrow.
CONTROLS_BG = "white"
CONTROLS_HEADER_BG = FOCUS_COLOR
CONTROLS_HEADER_FG = "white"
CONTROLS_TITLE_SIZE = 24
CONTROLS_CLOSE_TEXT = "Close"
# The overlay's raised border, counted twice: it is drawn inside the widget's own
# allocation, top and bottom.
CONTROLS_BORDER_PX = 3
# Height to assume for the title band when Tk will not say what it came out at -- one line
# of CONTROLS_TITLE_SIZE text plus the Close button's padding, which measures ~56px on the
# Deck. Used as a floor, not an override: assuming the band is taller than it is only
# leaves the columns a row of slack, while assuming it is shorter would cost them a row
# they had already been promised.
CONTROLS_HEADER_FALLBACK_PX = 56
LANDSCAPE_FONT_SCALE = 0.9
LANDSCAPE_BUTTON_DIVISOR = 8.0
COMPACT_SCALE = LANDSCAPE_FONT_SCALE
CONTROLLER_POLL_MS = 20

PanelName = Literal["left", "right"]
log = logging.getLogger(__name__)


class SteamDeckGui(GuiZeroBase):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        width: int = STEAM_DECK_WIDTH,
        height: int = STEAM_DECK_HEIGHT,
        *,
        full_screen: bool = True,
        x_offset: int = 0,
        y_offset: int = 0,
        left_options: dict[str, Any] | None = None,
        right_options: dict[str, Any] | None = None,
        controller_profile: str | Path | None = None,
        enable_controller: bool = True,
        confirm_replace: Callable[[str], bool] | None = None,
    ) -> None:
        GuiZeroBase.__init__(
            self,
            title="PyTrain Landscape Controller",
            width=width,
            height=height,
            scale_by=1.0,
            full_screen=full_screen,
            x_offset=x_offset,
            y_offset=y_offset,
        )
        self._pane_width = max(1, (self.width - HORIZONTAL_MARGIN - DIVIDER_WIDTH) // 2)
        self._pane_height = self.height
        self._focused_panel: PanelName = "right"
        self._left_options = dict(left_options or {})
        self._right_options = dict(right_options or {})
        self._confirm_replace = confirm_replace or self._confirm_panel_replace
        self._enable_controller = enable_controller
        self._controller_profile = ControlProfile.load(controller_profile)
        self._input_provider: SteamDeckInputProvider | None = None
        self._input_router: DeckInputRouter | None = None
        self._controller_poll_id = None

        self.body = None
        self.left_pane = self.right_pane = self.divider = None
        self.focus_arrow = None
        self.left_root = self.right_root = None
        self.left_gui: EngineGui | None = None
        self.right_gui: EngineGui | None = None
        # The controls help screen. Owned here rather than by a pane because it spans
        # both of them (see _build_controls_overlay).
        self._controls_panel: ControlsPanel | None = None
        self._controls_overlay: Box | None = None
        self.init_complete()

    @property
    def controller_profile(self) -> ControlProfile:
        """The loaded profile, so the controls help screen can describe the real bindings."""
        return self._controller_profile

    @property
    def pane_width(self) -> int:
        return self._pane_width

    @property
    def pane_height(self) -> int:
        return self._pane_height

    @property
    def focused_panel(self) -> PanelName:
        return self._focused_panel

    @property
    def focused_gui(self) -> EngineGui | None:
        return self.left_gui if self._focused_panel == "left" else self.right_gui

    def build_gui(self) -> None:
        app = self.app
        self.body = Box(app, align="top", layout="grid", width=self.width, height=self.height)
        self.body.tk.pack_propagate(False)
        self.left_pane = self.left_root = self._build_pane("left", 0)
        self.divider = Box(
            self.body,
            grid=[1, 0],
            width=DIVIDER_WIDTH,
            height=self.height,
            border=1,
        )
        self.divider.bg = "#555555"
        self.right_pane = self.right_root = self._build_pane("right", 2)

        self.left_gui = self._build_controller("left", self.left_root, self._left_options)
        self.right_gui = self._build_controller("right", self.right_root, self._right_options)
        self._build_focus_arrow()
        self._refresh_focus_indicator()
        self._start_controller_input()

    def _build_pane(self, side: PanelName, column: int) -> Box:
        pane = Box(
            self.body,
            grid=[column, 0],
            layout="auto",
            width=self._pane_width,
            height=self._pane_height,
            border=FOCUS_BORDER,
        )
        pane.tk.pack_propagate(False)
        pane.tk.bind("<Button-1>", lambda _event, target=side: self.focus_panel(target))
        return pane

    # noinspection unused-parameter
    def _build_controller(self, side: PanelName, root: Box, options: dict[str, Any]) -> EngineGui:
        child_options = {
            **options,
            "width": self._pane_width,
            "height": self._pane_height,
            "scale_by": LANDSCAPE_FONT_SCALE,
            "button_divisor": LANDSCAPE_BUTTON_DIVISOR,
            "full_screen": False,
            "stand_alone": False,
            "parent": root,
            "parent_gui": self,
            "compact": True,
            "show_halt": True,
        }
        gui = EngineGui(**child_options)
        gui.title = self.title
        gui.build_gui()
        return gui

    def focus_panel(self, panel: PanelName) -> None:
        if panel not in ("left", "right"):
            raise ValueError(f"Unknown panel: {panel}")
        self._focused_panel = panel
        self._refresh_focus_indicator()

    def toggle_focus(self) -> None:
        self.focus_panel("right" if self._focused_panel == "left" else "left")

    def on_show_controls(self) -> None:
        """Show the controls help screen across both panes."""
        if self._controls_overlay is None:
            self._controls_overlay = self._build_controls_overlay()
        self._controls_overlay.show()
        # show()/hide() run body.display_widgets(), which re-grids every child of body --
        # including the focus arrow, cancelling the place() that tucks it into the
        # divider. Without this it drops back into its full-height grid cell and floats
        # at mid-screen.
        self._position_focus_arrow()

    def close_controls(self) -> bool:
        """Hide the controls help screen. Returns whether it was open."""
        if not self.controls_visible:
            return False
        self._controls_overlay.hide()
        self._position_focus_arrow()  # see the note in on_show_controls
        return True

    @property
    def controls_visible(self) -> bool:
        return bool(self._controls_overlay is not None and self._controls_overlay.visible)

    def page_controls(self, forward: bool = True) -> bool:
        """Page the controls screen, for the D-pad while it is displayed."""
        if not self.controls_visible or self._controls_panel is None:
            return False
        self._controls_panel.turn_page(forward)
        return True

    def _build_controls_overlay(self) -> Box:
        """A full-width overlay gridded across every column of ``body``.

        Gridded rather than placed: guizero's Widget.show() re-runs the master's
        display_widgets(), which re-grids (or re-packs) its children -- so a place() is
        cancelled the moment the overlay is shown. Spanning the three columns that hold
        the left pane, the divider and the right pane is therefore the way to cover both
        panes, and it costs no layout change because 632 + 4 + 632 is already the full
        width. Created last, so it stacks above the panes it covers.
        """
        # No width/height and no align: the Box sizes to its content and, with no sticky,
        # grid centres it in the cell -- so it is as short as it can be and centred on the
        # display rather than a full-height panel with a void under the text.
        overlay = Box(self.body, grid=[0, 0, 3, 1], layout="auto", visible=False)
        overlay.bg = CONTROLS_BG
        overlay.tk.config(relief="raised", borderwidth=CONTROLS_BORDER_PX)

        header = Box(overlay, align="top", width="fill")
        header.bg = CONTROLS_HEADER_BG
        # Close rides in the title band rather than under the columns. Packed after the
        # content it was the first thing off the bottom of the display whenever the row
        # budget came out short: the only way out of the screen, clipped by a help row.
        # Created before the title because pack fills from the edges in child order -- the
        # button claims the right edge, then the title centres in what is left of the band.
        close = PushButton(header, text=CONTROLS_CLOSE_TEXT, align="right", command=self.close_controls)
        close.text_size = self.s_20
        close.tk.config(
            borderwidth=3,
            relief="raised",
            highlightthickness=1,
            highlightbackground="black",
            padx=6,
            pady=4,
            activebackground="#e0e0e0",
            background="#f7f7f7",
        )
        close.tk.pack_configure(padx=(0, 12), pady=6)
        title = Text(
            header,
            text=f"{CONTROLS_TITLE}   {self.version}",
            align="top",
            bold=True,
            size=CONTROLS_TITLE_SIZE,
            color=CONTROLS_HEADER_FG,
        )
        title.tk.config(padx=16, pady=6)
        self.cache(header, close, title)

        body = Box(overlay, align="top", layout="auto")
        self._controls_panel = ControlsPanel(self, self._controller_profile)
        self._controls_panel.build(body, height_px=self._controls_body_height(header))
        return overlay

    def _controls_body_height(self, header: Box) -> int:
        """Pixels the help columns may use: the display, less the chrome around them.

        Asked of the widget rather than assumed, because the band's height depends on the
        font Tk picked and on the Close button now inside it -- and the row budget divided
        out of this figure is what keeps a column inside the display.
        """
        band = CONTROLS_HEADER_FALLBACK_PX
        try:
            header.tk.update_idletasks()  # pack sizes the band at idle; ask after that
            band = max(band, header.tk.winfo_reqheight())
        except (AttributeError, TclError) as exception:
            log.debug("Controls header height unavailable (%s); assuming %d px", exception, band)
        return max(0, self.height - band - 2 * CONTROLS_BORDER_PX)

    def _build_focus_arrow(self) -> None:
        # An arrow that sits on the divider, in the same row as each pane's top
        # pulldown, pointing toward whichever pane currently has focus.
        #
        # visible=False deliberately: the arrow is positioned by place() into the
        # divider, and guizero only grids children it considers visible. Left visible it
        # would be re-gridded by every body.display_widgets() -- which both cancelled the
        # place() (dropping the arrow to mid-screen) and widened the divider's grid
        # column to the arrow's own width. place() is unaffected by guizero visibility,
        # so the arrow still shows.
        self.focus_arrow = Text(
            self.body,
            text=FOCUS_ARROW_RIGHT,
            grid=[1, 0],
            size=FOCUS_ARROW_SIZE,
            color=FOCUS_COLOR,
            visible=False,
        )
        self._position_focus_arrow()

    def _position_focus_arrow(self) -> None:
        arrow = getattr(self, "focus_arrow", None)
        divider = getattr(self, "divider", None)
        if arrow is None or divider is None:
            return
        arrow.tk.place(in_=divider.tk, relx=0.5, y=self._focus_arrow_y(), anchor="center")

    def _focus_arrow_y(self) -> int:
        header = getattr(self.left_gui, "header", None) if self.left_gui is not None else None
        if header is None:
            return FOCUS_BORDER + FOCUS_ARROW_SIZE
        try:
            self.body.tk.update_idletasks()
            return FOCUS_BORDER + max(1, int(header.tk.winfo_reqheight()) // 2)
        except (AttributeError, TclError, TypeError, ValueError):
            return FOCUS_BORDER + FOCUS_ARROW_SIZE

    def _refresh_focus_indicator(self) -> None:
        panes = (("left", getattr(self, "left_pane", None)), ("right", getattr(self, "right_pane", None)))
        for name, pane in panes:
            if pane is None:
                continue
            color = FOCUS_COLOR if name == self._focused_panel else UNFOCUSED_COLOR
            pane.tk.configure(
                highlightthickness=FOCUS_BORDER,
                highlightbackground=color,
                highlightcolor=color,
            )
        arrow = getattr(self, "focus_arrow", None)
        if arrow is not None:
            arrow.value = FOCUS_ARROW_LEFT if self._focused_panel == "left" else FOCUS_ARROW_RIGHT

    def transfer_linked_car(self, source_panel: PanelName, state: EngineState) -> bool:
        if source_panel not in ("left", "right"):
            raise ValueError(f"Unknown panel: {source_panel}")
        source = self.left_gui if source_panel == "left" else self.right_gui
        target = self.right_gui if source_panel == "left" else self.left_gui
        if source is None or target is None:
            return False
        linked = getattr(source, "linked_car_states", ())
        if not any(getattr(candidate, "tmcc_id", None) == getattr(state, "tmcc_id", None) for candidate in linked):
            return False
        if target.has_active_selection:
            name = getattr(state, "name", None) or getattr(state, "road_name", None) or f"TMCC {state.tmcc_id}"
            if not self._confirm_replace(f"Replace the other panel with linked car {name}?"):
                return False
        target.select_component(CommandScope.ENGINE, state.tmcc_id)
        return True

    def _confirm_panel_replace(self, message: str) -> bool:
        return bool(messagebox.askyesno("Replace controller?", message, parent=self.app.tk))

    @staticmethod
    def on_halt() -> None:
        KEY_TO_COMMAND[HALT_KEY].send()

    def _start_controller_input(self) -> None:
        if not getattr(self, "_enable_controller", False):
            return
        self._input_router = DeckInputRouter(
            self._controller_profile,
            left=lambda: self.left_gui,
            right=lambda: self.right_gui,
            focused=lambda: self.focused_gui,
            global_actions={
                "halt": self.on_halt,
                "focus_left": lambda: self.focus_panel("left"),
                "focus_right": lambda: self.focus_panel("right"),
                "focus_toggle": self.toggle_focus,
                "show_controls": self.on_show_controls,
            },
        )
        # The router resolves which panel a binding targets, so it is what answers whether
        # that panel is showing a track switch -- the provider needs to know because a
        # trigger throwing a switch fires on the squeeze rather than on the release.
        provider = SteamDeckInputProvider(
            self._controller_profile,
            switch_active=self._input_router.switch_active,
        )
        try:
            provider.start()
        except ControllerUnavailable as exc:
            log.warning("Native controller input unavailable: %s", exc)
            self._input_provider = None
            self._input_router = None
            self._controller_poll_id = None
            return
        self._input_provider = provider
        self._controller_poll_id = self.app.tk.after(CONTROLLER_POLL_MS, self._poll_controller)

    def _poll_controller(self) -> None:
        provider = self._input_provider
        router = self._input_router
        if provider is None or router is None:
            self._controller_poll_id = None
            return
        try:
            for action in provider.poll():
                router.handle(action)
            router.tick(time.monotonic())
        except Exception as exc:
            log.exception("Steam Deck controller polling failed", exc_info=exc)
        self._controller_poll_id = self.app.tk.after(CONTROLLER_POLL_MS, self._poll_controller)

    def _stop_controller_input(self) -> None:
        poll_id = getattr(self, "_controller_poll_id", None)
        if poll_id is not None:
            try:
                self.app.tk.after_cancel(poll_id)
            except (AttributeError, RuntimeError, TclError):
                pass
        self._controller_poll_id = None
        provider = getattr(self, "_input_provider", None)
        if provider is not None:
            provider.stop()
        router = getattr(self, "_input_router", None)
        if router is not None:
            router.clear()
        self._input_provider = None
        self._input_router = None

    def destroy_gui(self) -> None:
        self._stop_controller_input()
        for child_name in ("left_gui", "right_gui"):
            child = getattr(self, child_name, None)
            if child is not None:
                child.destroy_embedded()
                setattr(self, child_name, None)
        self.safe_destroy(getattr(self, "body", None))
        self.body = None
        self.left_pane = self.right_pane = self.divider = None
        self.focus_arrow = None
        self.left_root = self.right_root = None
        self.clear_cache()

    def calc_image_box_size(self) -> tuple[int, int]:
        return self._pane_width, self._pane_height
