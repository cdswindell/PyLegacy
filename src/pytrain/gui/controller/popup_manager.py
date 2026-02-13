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
import math
from dataclasses import dataclass
from tkinter import TclError
from typing import Any, Callable, Optional, TYPE_CHECKING

from guizero import Box, Combo, PushButton, Text

from .configured_accessory_adapter import ConfiguredAccessoryAdapter

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui
    from ..components.hold_button import HoldButton

log = logging.getLogger(__name__)


@dataclass
class PopupState:
    current_popup: Box | None = None
    on_close_show: Box | None = None
    restore_image_box: bool = False


class PopupManager:
    """
    Manages overlay popups for EngineGui.
    """

    def __init__(self, host: "EngineGui") -> None:
        self._host = host
        self._state = PopupState()
        self._combo_hackable: bool = False
        self._overlays: dict[str, Box] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def get_or_create(
        self, key: str, title: str, build_body: Callable[[Box], None] | ConfiguredAccessoryAdapter
    ) -> Box:
        with self._host.locked():
            existing = self._overlays.get(key)
            if isinstance(existing, Box):
                return existing

        overlay = self.create_popup(title, build_body)
        setattr(overlay, "overlay_key", key)
        self._overlays[key] = overlay
        return overlay

    def create_popup(self, title_text: str, build_body: Callable[[Box], None] | ConfiguredAccessoryAdapter) -> Box:
        host = self._host

        overlay = Box(host.app, align="top", border=2, visible=False)
        overlay.bg = "white"
        if title_text:
            title_row = Box(
                overlay,
                align="top",
                width=host.emergency_box_width,
                height=host.button_size // 3,
            )
            title_row.bg = "lightgrey"

            title = Text(title_row, text=title_text, bold=True, size=host.s_18)
            title.bg = "lightgrey"
            setattr(overlay, "title", title)

        if isinstance(build_body, ConfiguredAccessoryAdapter):
            build_body.ensure_gui(aggregator=self._host)
            build_body.gui.mount_gui(overlay)
        else:
            body = Box(overlay, align="top", layout="auto")
            build_body(body)

            # show explicit close button
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
    # API
    # ------------------------------------------------------------------

    @property
    def is_combo_hackable(self) -> bool:
        return self._combo_hackable

    @is_combo_hackable.setter
    def is_combo_hackable(self, value: bool) -> None:
        self._combo_hackable = value

    def build_button_panel(
        self,
        body: Box,
        buttons: list[list[tuple]],
    ) -> Box:
        host = self._host
        button_box = Box(body, layout="grid", border=1)
        width = int(3 * host.button_size)

        # Iterates button definitions; creates and configures each button
        for r, kr in enumerate(buttons):
            for c, button in enumerate(kr):
                if isinstance(button, tuple):
                    op = button[0]
                    label = button[1]
                else:
                    raise ValueError(f"Invalid button: {button} ({type(button)})")
                cell, nb = host.make_keypad_button(
                    button_box,
                    label,
                    r,
                    c,
                    bolded=True,
                    size=host.s_18,
                    command=host.on_engine_command,
                    args=[op],
                )
                cell.tk.config(width=width)
                nb.tk.config(width=width)
                host.cache(cell, nb)
        host.cache(button_box)
        return button_box

    def make_combo_panel(self, body: Box, options: dict, min_width: int = 12) -> Box:
        host = self._host
        combo_box = Box(body, layout="grid", border=1)

        # How many combo boxes do we have; display them in 2 columns:
        boxes_per_column = int(math.ceil(len(options) / 2))
        width = max(max(map(len, options.keys())) - 1, min_width)

        for idx, (title, values) in enumerate(options.items()):
            # place 4 per column
            row = idx % boxes_per_column
            col = idx // boxes_per_column

            # combo contents and mapping
            if self.is_combo_hackable:
                select_ops = [v[0] for v in values]
            else:
                select_ops = [title] + [v[0] for v in values]
            od = {v[0]: v[1] for v in values}

            slot = Box(combo_box, grid=[col, row])
            cb = Combo(slot, options=select_ops, selected=title)
            self._rebuild_combo(cb, od, title)

            cb.update_command(self._make_combo_callback(cb, od, title))
            cb.tk.config(width=width)
            cb.text_size = host.s_20
            cb.tk.pack_configure(padx=6, pady=15)
            # set the hover color of the element the curser is over when selecting an item
            if "menu" in cb.tk.children:
                menu = cb.tk.children["menu"]
                menu.config(activebackground="lightgrey")
            host.cache(slot, cb)
        host.cache(combo_box)
        return combo_box

    # ------------------------------------------------------------------
    # Combo box internals
    # ------------------------------------------------------------------

    def _make_combo_callback(self, cb: Combo, od: dict, title: str) -> Callable[[str], None]:
        def func(selected: str):
            self._on_combo_select(cb, od, title, selected)

        return func

    def _on_combo_select(self, cb: Combo, od: dict, title: str, selected: str) -> None:
        cmd = od.get(selected, None)
        if isinstance(cmd, str):
            self._host.on_engine_command(cmd)
        # rebuild combo
        self._rebuild_combo(cb, od, title)

    # noinspection PyProtectedMember
    def _rebuild_combo(self, cb: Combo, od: dict, title: str):
        cb.clear()
        if not self.is_combo_hackable:
            cb.append(title)

        for option in od.keys():
            cb.append(option)

        if self.is_combo_hackable:
            cb._selected.set(title)
        else:
            cb.select_default()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def show(
        self,
        overlay: Box,
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
            # set this overlay as current
            self._state.current_popup = overlay

            # Hide the active content box
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

        try:
            x, y = position if position else host.popup_position
            overlay.tk.place(x=x, y=y)
            overlay.show()
        except (AttributeError, RuntimeError, TclError):
            log.warning(f"Failed to place/show overlay: {overlay}")
            with host.locked():
                if self._state.current_popup is overlay:
                    self._state.current_popup = None
                    # restore image box
                if self._state.restore_image_box and host.image_box and not host.image_box.visible:
                    host.image_box.show()
                self._state.restore_image_box = False
                # restore content box
                if self._state.on_close_show:
                    try:
                        self._state.on_close_show.show()
                    except (AttributeError, RuntimeError):
                        pass
                    self._state.on_close_show = None
        finally:
            self._restore_button_state(op=op, modifier=modifier, button=button)

    def close(self, overlay: Box | None = None) -> None:
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
        """Restores button color state by operator or button"""
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
