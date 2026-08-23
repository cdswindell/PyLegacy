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
from contextlib import contextmanager
from dataclasses import dataclass
from tkinter import TclError
from typing import Any, Callable, Iterable, Optional, TYPE_CHECKING

from guizero import Box, Combo, PushButton, Text

from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from .overlay_panel import OverlayPanel
from ..components.hold_button import HoldButton
from ...utils.path_utils import find_file

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

log = logging.getLogger(__name__)


@dataclass
class PopupState:
    current_popup: Box | None = None
    on_close_show: Box | None = None
    restore_image_box: bool = False
    restore_acc_box: bool = False


# Pack padding around a footer button. The compact pane cannot afford the portrait inset.
# Kept tight deliberately: the overlay has no vertical slack (it already ends within a dozen
# pixels of the pane's nav bar), so the row's outer spacing is set on the row itself -- see
# pad_footer_row and AdminPanel.compact_footer_gap -- where it can be traded against the gap
# above rather than silently growing the overlay and pushing the buttons under the nav bar.
FOOTER_BUTTON_PAD_COMPACT = 4
FOOTER_BUTTON_PAD = 20
# Horizontal gap between a panel's own footer button and Close, expressed as a text size --
# the spacer is a single space, so its point size is what sets its width.
FOOTER_GAP = 40
FOOTER_GAP_COMPACT = 24
# Where a footer button remembers its packing, so it can be replayed. See restore_footer_packing.
_FOOTER_PACK_ATTR = "_pytrain_footer_pack"


def style_footer_button(host, btn) -> None:
    """Give a footer button the one shared look.

    There were three copies of this block -- Close here, plus the extra button in each
    panel's build_footer -- and they drifted, which is the whole defect. AdminPanel's copy
    tracked compact correctly; StateInfoOverlay's never had a compact branch at all, so on a
    Deck pane its Clear button was styled for portrait next to a compact Close.

    The packing is *recorded* as well as applied, because guizero re-packs every sibling
    whenever a widget is created and keeps only side/fill (Container._pack_widget). Whichever
    footer button is created last keeps its padding; the others silently lose theirs.
    """
    compact = bool(getattr(host, "compact", False))
    btn.text_size = host.s_18 if compact else host.s_20
    btn.tk.config(
        borderwidth=3,
        relief="raised",
        highlightthickness=1,
        highlightbackground="black",
        padx=6,
        pady=1 if compact else 4,
        activebackground="#e0e0e0",
        background="#f7f7f7",
    )
    padding = FOOTER_BUTTON_PAD_COMPACT if compact else FOOTER_BUTTON_PAD
    options = {"padx": padding, "pady": padding}
    btn.tk.pack_configure(**options)
    setattr(btn, _FOOTER_PACK_ATTR, options)


def footer_spacer(host, footer) -> Text:
    """Put the gap between a panel's own footer button and Close.

    A widget rather than pack padding: create_popup adds Close to this same footer straight
    after, and creating it re-packs every sibling, discarding padx. A real widget survives
    because it is re-packed too.

    Shared so the gap tracks the mode. StateInfoOverlay's copy was a fixed host.s_72, which
    on a Deck pane is an enormous gap next to a compact Close.
    """
    compact = bool(getattr(host, "compact", False))
    spacer = Text(footer, text=" ", height=1, align="left")
    spacer.text_size = FOOTER_GAP_COMPACT if compact else FOOTER_GAP
    host.cache(spacer)
    return spacer


def center_in_leftover(widget) -> None:
    """Centre a bottom-packed widget in whatever vertical space the overlay has spare.

    ``expand`` grows the widget's *parcel* to take the leftover; with no ``fill`` the widget
    keeps its own height and pack centres it inside that parcel. So the row lands in the middle
    of the band between the panel's content and the scope buttons, at whatever size that band
    turns out to be -- which is why this replaced a pair of hand-tuned pads that had to be
    re-derived every time a section's height changed.

    Survives because nothing is created in the overlay afterwards: Close goes *inside* the row,
    and creating a child only re-packs that child's siblings -- not the row itself.
    """
    try:
        widget.tk.pack_configure(expand=True)
    except (AttributeError, TclError, RuntimeError):
        pass


def restore_footer_packing(footer) -> None:
    """Replay the packing of every styled button in a footer.

    Called once Close is in place -- it is always the last thing added to a footer, so it is
    the only button whose own packing survived creation.
    """
    for child in getattr(footer, "children", ()) or ():
        options = getattr(child, _FOOTER_PACK_ATTR, None)
        if options:
            try:
                child.tk.pack_configure(**options)
            except (AttributeError, TclError, RuntimeError):
                continue


class PopupManager:
    """
    Manages overlay popups for EngineGui.
    """

    def __init__(self, host: "EngineGui") -> None:
        self._host = host
        self._state = PopupState()
        self._combo_hackable: bool = False
        self._overlays: dict[str, Box] = {}
        self._post_close_actions: dict[int, Callable[[Box], None]] = {}
        self._close_acc_paths = {
            False: find_file("raw-acc.jpg"),
            True: find_file("raw-acs2.jpg"),
        }
        self._close_acc_images: dict[tuple[bool, int], tuple[Any, Any]] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @contextmanager
    def _suspend_host_layout(self):
        root = getattr(self._host, "root", self._host.app)
        display_widgets = root.display_widgets
        root.display_widgets = lambda: None
        try:
            yield
        finally:
            root.display_widgets = display_widgets

    def get_or_create(
        self,
        key: str,
        title: str,
        body_src: Callable[[Box], None] | ConfiguredAccessoryAdapter | OverlayPanel,
        on_close: Callable = None,
        post_close_action: Callable[[Box], None] | None = None,
    ) -> Box:
        with self._host.locked():
            existing = self._overlays.get(key)
            if isinstance(existing, Box):
                return existing

        overlay = self.create_popup(title, body_src, on_close, post_close_action=post_close_action)
        setattr(overlay, "overlay_key", key)
        self._overlays[key] = overlay
        return overlay

    def forget(self, keys: Iterable[str]) -> None:
        """
        Remove cached overlays by key.

        Accessory overlays are rebuilt from accessory_config.json. When that
        file is reread, cached overlays must be discarded or get_or_create()
        will return stale GUI instances for reused instance_ids.
        """
        with self._host.locked():
            for key in keys:
                overlay = self._overlays.pop(key, None)
                if overlay is None:
                    continue
                if self._state.current_popup is overlay:
                    self._state.current_popup = None
                self._post_close_actions.pop(id(overlay), None)
                try:
                    overlay.hide()
                    overlay.tk.place_forget()
                except (AttributeError, RuntimeError, TclError):
                    pass
                try:
                    overlay.destroy()
                except (AttributeError, RuntimeError, TclError):
                    pass

    def discard_acc_overlay_restore(self) -> None:
        """
        Prevent close() from restoring an accessory overlay that was hidden by
        another popup.
        """
        with self._host.locked():
            self._state.restore_acc_box = False

    def create_popup(
        self,
        title_text: str,
        body_src: Callable[[Box], None] | ConfiguredAccessoryAdapter | OverlayPanel,
        on_close: Callable = None,
        *,
        post_close_action: Callable[[Box], None] | None = None,
    ) -> Box:
        host = self._host

        # A popup belongs to its host's root, which for an embedded EngineGui is its own
        # pane. It cannot be re-parented to the window to span both panes: guizero's
        # Widget.show() calls master.display_widgets(), which packs the overlay -- so an
        # overlay is positioned by that pack, not by the place() in show() below, and a
        # window-parented one lands after `body` and off screen.
        parent = getattr(host, "root", host.app)
        # guizero's hidden-widget construction calls master.display_widgets(),
        # which repacks the full app. Prewarmed overlays are not meant to affect
        # the visible layout until they are explicitly shown.
        with self._suspend_host_layout():
            # height="fill" is what makes every panel reach the scope buttons. The overlay is a
            # side=top packed child of the pane and the scope box is side=bottom, so the band
            # between them is exactly the overlay's parcel: guizero maps "fill" to Tk's fill=Y
            # and, for a top/bottom side, expand=YES. Declarative -- no measuring of where the
            # scope row happens to be, and it follows whatever else is packed above.
            overlay = Box(parent, align="top", border=2, visible=False, height="fill")
        if post_close_action:
            self._post_close_actions[id(overlay)] = post_close_action
        overlay.bg = "white"
        height = (title_text.count("\n") + 1) * host.button_size // 3 if title_text else host.button_size // 3
        if title_text:
            title_row = Box(
                overlay,
                align="top",
                width=host.emergency_box_width,
                height=height,
            )
            title_row.bg = "lightgrey"

            title = Text(title_row, text=title_text, bold=True, size=host.s_18)
            title.bg = "lightgrey"
            setattr(overlay, "title", title)

        if isinstance(body_src, ConfiguredAccessoryAdapter):
            body_src.ensure_gui(aggregator=self._host)
            body_src.gui.mount_gui(overlay)
            self.add_close_acc_btn(host, body_src, on_close, overlay)
            body_src.attach_overlay(overlay)
        elif isinstance(body_src, OverlayPanel):
            body = Box(overlay, align="top", layout="auto")
            body_src.build(body)
            if body_src.has_footer:
                button_row = Box(overlay, align="bottom")
                body_src.build_footer(button_row)
                self.add_close_btn(host, on_close, button_row, close_target=overlay, align="right", width=8)
                center_in_leftover(button_row)
            else:
                center_in_leftover(self.add_close_btn(host, on_close, overlay))
        else:
            body = Box(overlay, align="top", layout="auto")
            body_src(body)
            center_in_leftover(self.add_close_btn(host, on_close, overlay))

        if overlay.visible:
            with self._suspend_host_layout():
                overlay.hide()
        return overlay

    def add_close_btn(
        self,
        host: EngineGui,
        on_close: Callable[..., Any] | None,
        overlay: Box,
        close_target: Box = None,
        align="bottom",
        width: int = 5,
    ):
        close_target = close_target or overlay

        # show explicit close button
        btn = PushButton(
            overlay,
            text="Close",
            align=align,
            width=width,
            command=on_close or self.close,
            args=[close_target],
        )
        style_footer_button(host, btn)
        # Creating this button discarded the packing of everything already in the footer.
        restore_footer_packing(overlay)
        host.cache(btn)
        return btn

    def add_close_acc_btn(
        self,
        host: EngineGui,
        acc: ConfiguredAccessoryAdapter,
        on_close: Callable[..., Any] | None,
        overlay: Box,
    ):
        host.add_vspace(overlay, 40)
        bs = int(host.button_size * 1.0)
        img, inverted_img = self._get_close_acc_images(acc.state.is_asc2, bs)
        btn = HoldButton(
            overlay,
            text="",
            image=None,
            command=on_close or self.close,
            args=[overlay],
        )
        btn.images = img, inverted_img
        host.cache(btn)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    @property
    def current_popup(self) -> Box | None:
        return self._state.current_popup

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
                    image = find_file(button[2]) if len(button) > 2 else None
                    if image:
                        width = host.button_size
                else:
                    raise ValueError(f"Invalid button: {button} ({type(button)})")
                cell, nb = host.make_keypad_button(
                    button_box,
                    label,
                    r,
                    c,
                    image=image,
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

    @staticmethod
    def _pad_item(item: str, max_len: int, extra: int = 2) -> str:
        if len(item) < (max_len + extra):
            item = item + (" " * (max_len + extra - len(item)))
        return item

    def _make_combo_callback(self, cb: Combo, od: dict, title: str) -> Callable[[str], None]:
        def func(selected: str):
            self._on_combo_select(cb, od, title, selected)

        return func

    def _on_combo_select(self, cb: Combo, od: dict, title: str, selected: str) -> None:
        selected = selected.strip()
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
            title_len = 0
        else:
            title_len = len(title)

        for option in od.keys():
            cb.append(self._pad_item(option, title_len))

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
            self.close()

            # set this overlay as current
            self._state.current_popup = overlay

            # Hide the active content box
            self._state.on_close_show = None
            for box in (host.controller_box, host.keypad_box, host.amc2_ops_box, host.sensor_track_box):
                if box and getattr(box, "visible", True):
                    box.hide()
                    self._state.on_close_show = box
                    break

            # manage image box
            self._hide_image_box(hide_image_box, host)

            # Accessory popup
            self._state.restore_acc_box = False
            if host.acc_overlay and host.acc_overlay.visible:
                host.acc_overlay.hide()
                self._state.restore_acc_box = True
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
                try:
                    post_close_action = self._post_close_actions.get(id(overlay))
                    if callable(post_close_action):
                        post_close_action(overlay)
                except (AttributeError, RuntimeError, TclError):
                    pass

            if self._state.restore_image_box and host.image_box:
                if not host.image_box.visible:
                    host.image_box.show()
            self._state.restore_image_box = False

            if self._state.restore_acc_box and host.acc_overlay:
                if not host.acc_overlay.visible:
                    host.acc_overlay.show()
            self._state.restore_acc_box = False

            if self._state.on_close_show:
                try:
                    self._state.on_close_show.show()
                except (AttributeError, RuntimeError):
                    pass
                self._state.on_close_show = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _hide_image_box(self, hide_image_box: bool, host: EngineGui):
        # Hide image box if requested
        self._state.restore_image_box = False
        if hide_image_box and host.image_box and host.image_box.visible:
            host.image_box.hide()
            self._state.restore_image_box = True

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

    def _get_close_acc_images(self, is_asc2: bool, size: int):
        key = (is_asc2, size)
        images = self._close_acc_images.get(key)
        if images is None:
            images = self._host.get_image(self._close_acc_paths[is_asc2], size=(size, size))
            self._close_acc_images[key] = images
        return images

    def preload_images(self) -> None:
        bs = int(self._host.button_size * 1.0)
        self._get_close_acc_images(False, bs)
        self._get_close_acc_images(True, bs)
