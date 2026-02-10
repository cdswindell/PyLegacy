#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from dataclasses import dataclass
from tkinter import TclError
from typing import Callable, TYPE_CHECKING, Any, Optional, Protocol

from guizero import Box, PushButton, Text
from guizero.base import Widget

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui
    from ..components.hold_button import HoldButton


@dataclass
class PopupState:
    current_popup: Widget | None = None
    on_close_show: Widget | None = None
    restore_image_box: bool = False


class LightingOverlay(Protocol):
    steam_lights: Box
    diesel_lights: Box


class PopupManager:
    """
    Manages overlay popups for EngineGui.
    """

    def __init__(self, host: "EngineGui") -> None:
        self._host = host
        self._state = PopupState()
        self._overlays: dict[str, Box] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def get_or_create(self, key: str, title: str, build_body: Callable[[Box], None]) -> Box:
        existing = self._overlays.get(key)
        if isinstance(existing, Box) and getattr(existing, "overlay_key", None) == key:
            return existing
        overlay = self.create_popup(title, build_body)
        overlay.overlay_key = key
        self._overlays[key] = overlay
        return overlay

    def create_popup(self, title_text: str, build_body: Callable[[Box], None]) -> Box:
        host = self._host

        overlay = Box(host.app, align="top", border=2, visible=False)
        overlay.bg = "white"

        title_row = Box(
            overlay,
            width=host.emergency_box_width,
            height=host.button_size // 3,
        )
        title_row.bg = "lightgrey"

        title = Text(title_row, text=title_text, bold=True, size=host.s_18)
        title.bg = "lightgrey"
        overlay.title = title

        body = Box(overlay, layout="auto")
        build_body(body)

        btn = PushButton(
            overlay,
            text="Close",
            align="bottom",
            command=self.close,
            args=[overlay],
        )
        btn.text_size = host.s_20
        btn.tk.config(
            borderwidth=3,
            relief="raised",
            highlightthickness=1,
            highlightbackground="black",
            padx=6,
            pady=4,
            activebackground="#e0e0e0",
            background="#f7f7f7",
        )
        btn.tk.pack_configure(padx=20, pady=20)

        overlay.hide()
        return overlay

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def show(
        self,
        overlay: Widget,
        *,
        op: str | None = None,
        modifier: str | None = None,
        button: Optional["HoldButton"] = None,
        position: tuple[int, int] | None = None,
        hide_image_box: bool = False,
    ) -> None:
        host = self._host

        with host.locked():
            # Close any existing popup
            if self._state.current_popup:
                try:
                    self._state.current_popup.hide()
                    self._state.current_popup.tk.place_forget()
                except (AttributeError, RuntimeError, TclError):
                    pass
                self._state.current_popup = None

            self._restore_button_state(op=op, modifier=modifier, button=button)

            # Hide active content box
            self._state.on_close_show = None
            for box in (host.controller_box, host.keypad_box, host.sensor_track_box):
                if box and getattr(box, "visible", False):
                    box.hide()
                    self._state.on_close_show = box
                    break

            # Hide image box if requested
            self._state.restore_image_box = False
            if hide_image_box and host.image_box and host.image_box.visible:
                host.image_box.hide()
                self._state.restore_image_box = True

            self._state.current_popup = overlay

            x, y = position if position else host.popup_position
            overlay.tk.place(x=x, y=y)
            overlay.show()

    def close(self, overlay: Widget | None = None) -> None:
        host = self._host

        with host.locked():
            overlay = overlay or self._state.current_popup
            self._state.current_popup = None

            if overlay:
                try:
                    overlay.hide()
                    overlay.tk.place_forget()
                except (AttributeError, RuntimeError, TclError):
                    pass

            if self._state.restore_image_box and host.image_box:
                if not host.image_box.visible:
                    host.image_box.show()
            self._state.restore_image_box = False

            if self._state.on_close_show:
                try:
                    self._state.on_close_show.show()
                except (AttributeError, RuntimeError):
                    pass
                self._state.on_close_show = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _restore_button_state(
        self,
        *,
        op: str | None,
        modifier: str | None,
        button: Optional["HoldButton"] = None,
    ) -> None:
        host = self._host

        if button is not None:
            try:
                button.restore_color_state()
            except AttributeError:
                pass
            return

        if not op:
            return

        try:
            key: Any = (op, modifier) if modifier else op
            _, btn = host.engine_ops_cells[key]
            btn.restore_color_state()
        except (KeyError, AttributeError):
            pass
