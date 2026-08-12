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

from guizero import Box, Text

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
HORIZONTAL_MARGIN = 12
DIVIDER_WIDTH = 4
FOCUS_BORDER = 3
FOCUS_COLOR = "#3B82F6"
UNFOCUSED_COLOR = "#555555"
FOCUS_ARROW_LEFT = "◀"
FOCUS_ARROW_RIGHT = "▶"
FOCUS_ARROW_SIZE = 22
LANDSCAPE_FONT_SCALE = 0.9
LANDSCAPE_BUTTON_DIVISOR = 8.0
COMPACT_SCALE = LANDSCAPE_FONT_SCALE
CONTROLLER_POLL_MS = 20

PanelName = Literal["left", "right"]
log = logging.getLogger(__name__)


class LandscapeEngineGui(GuiZeroBase):
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
        self._focused_panel: PanelName = "left"
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
        self.init_complete()

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

    def _build_focus_arrow(self) -> None:
        # An arrow that sits on the divider, in the same row as each pane's top
        # pulldown, pointing toward whichever pane currently has focus.
        self.focus_arrow = Text(
            self.body,
            text=FOCUS_ARROW_RIGHT,
            grid=[1, 0],
            size=FOCUS_ARROW_SIZE,
            color=FOCUS_COLOR,
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
            },
        )
        provider = SteamDeckInputProvider(self._controller_profile)
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
