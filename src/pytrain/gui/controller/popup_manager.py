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
# Kept tight deliberately: this is spacing *inside* the row, separating the buttons from its
# edges. The row's own position in the overlay is not padding at all any more -- see
# footer_lead and footer_fill, which place the row within the overlay.
FOOTER_BUTTON_PAD_COMPACT = 4
FOOTER_BUTTON_PAD = 20
# Horizontal gap between a panel's own footer button and Close, expressed as a text size --
# the spacer is a single space, so its point size is what sets its width.
FOOTER_GAP = 40
FOOTER_GAP_COMPACT = 24
# Whitespace between a panel's content and its footer row, in pixels. Fixed rather than a share
# of the leftover: an expanded panel's spare band ranges from ~24px (the admin panel, which
# nearly fills the pane) to several hundred (Lights, Tower Dialogs), and a share of the latter
# leaves the buttons floating mid-overlay instead of attached to the panel. All the remaining
# space goes below the row -- see footer_fill.
#
# The compact value is the old FOOTER_ROW_PAD_COMPACT: on a pane where the whole band is 24px,
# 12px above and the rest below is the same picture as a centred row, which is the one that was
# signed off. Portrait gets more because it has far more of it to spend.
FOOTER_LEAD = 24
FOOTER_LEAD_COMPACT = 12
# Where a footer button remembers its packing, so it can be replayed. See restore_footer_packing.
_FOOTER_PACK_ATTR = "_pytrain_footer_pack"
# Where an overlay remembers the height it was built with, so expanding it is reversible.
_OVERLAY_HEIGHT_ATTR = "_pytrain_overlay_height"
# Set on an overlay that must never be expanded. Only the configured-accessory popups: those
# mount a foreign GUI that owns its own layout, and accessory images were the one thing still
# working through the regression that backed this feature out the first time.
_NO_EXPAND_ATTR = "_pytrain_no_expand"
# Where an overlay keeps its (lead, fill) pair, so the row's position can be corrected on show
# without walking the children and guessing which boxes are the spacers.
_FOOTER_BOXES_ATTR = "_pytrain_footer_boxes"
# How long to wait after showing a popup before measuring it. A sample taken any earlier is
# worthless: winfo_height reads 1 and winfo_rooty reads 0 until Tk has laid the widget out, which
# is how the first run of the admin panel's geometry trace produced a page of w=1 parent_w=1.
POPUP_GEOM_DELAY_MS = 500


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


def footer_fill(overlay: Box) -> Box:
    """Soak up an expanded panel's spare vertical space *below* the footer row.

    An empty ``height="fill"`` box: guizero gives it ``fill=Y`` plus ``expand=YES``, and Tk hands
    surplus space to the widgets that expand, so this one absorbs the whole band and leaves the
    row sitting directly above it. Paired with footer_lead, which then holds the row a fixed
    distance off the content.

    Together they replace an equal split between two filling boxes. Equal was right for a panel
    that nearly fills the pane -- the admin panel's spare band is only ~24px, so half of it is
    12px either side -- but proportional means a short panel (Lights, Tower Dialogs) gets half of
    several hundred pixels above its row, and the buttons float in the middle of nothing instead
    of reading as part of the panel.

    **Call this after the body and before the row**: pack fills a side in creation order, so this
    has to claim the bottom edge first to leave the row above it.

    Survives a repack, unlike ``pack_configure`` padding: ``Container._pack_widget`` rebuilds its
    option dict from scratch every pass and reads fill back off each widget's own ``height``.
    """
    return Box(overlay, align="bottom", height="fill")


def footer_lead(host, overlay: Box) -> Box:
    """Hold the footer row a fixed distance below the panel's content.

    A real widget of a fixed height rather than pack padding, for the same reason footer_spacer
    is one: padding set on the row is discarded the next time anything in the overlay is created
    or shown, and a widget is re-packed instead of forgotten.

    **Call this after the row**, even though it renders above it. It is the one thing here that
    asks for space unconditionally, and pack allots in creation order, so on a band too tight for
    both this has to be the thing that loses out rather than the buttons. Being last also means
    it is clipped to nothing instead of pushing the row off the bottom edge -- it is empty, so
    losing it costs nothing.

    ``width="fill"`` is not cosmetic: guizero warns "You must specify a width and a height"
    whenever both are ints and one of them is zero, and a fill is the documented exemption.
    """
    return Box(overlay, align="top", width="fill", height=footer_lead_height(host))


def footer_lead_height(host) -> int:
    """The whitespace a panel wants between its content and its footer row, before any correction."""
    return FOOTER_LEAD_COMPACT if bool(getattr(host, "compact", False)) else FOOTER_LEAD


def balance_footer_row(host, overlay) -> None:
    """Centre the footer row when the band it sits in is too tight to hold the lead comfortably.

    The fixed lead is right whenever there is more room below the row than above it. When there
    is *less* -- a panel whose content nearly reaches the scope buttons, so the whole spare band
    is under twice the lead -- keeping the lead fixed pins the row hard against the bottom edge.
    In that case the row is centred in whatever band there is instead.

    Which is ``min(lead, band / 2)``, and unlike the fixed lead it cannot be expressed in pack:
    two expanding boxes always divide space proportionally, and pack shrinks in creation order
    rather than proportionally, so nothing declarative caps one side. It needs the band measured.

    The measurement is a cheap one. ``footer_fill``'s own allocated height *is* the space below the
    row, so nothing has to be derived from the content, and correcting the lead alone is enough --
    the fill is the expander, so it re-absorbs whatever the lead gives back. It is also stable
    under repetition: once the two are equal the condition stops firing.

    Scheduled rather than immediate because ``winfo_height`` reads 1 until Tk has laid the overlay
    out. Any reposition is therefore visible, but bounded by half the lead -- at most 6px on a
    Deck pane -- and only in the tight case; a roomy panel measures once and changes nothing.
    """
    boxes = getattr(overlay, _FOOTER_BOXES_ATTR, None)
    if not boxes:
        return
    try:
        host.app.tk.after_idle(lambda: _balance_footer_row(host, overlay, *boxes))
    except (AttributeError, TclError, RuntimeError):
        pass


def _balance_footer_row(host, overlay, lead: Box, fill: Box) -> None:
    """Measure the band below the footer row and even it up with the lead if it is the smaller."""
    try:
        # Flush the pending geometry work first: an idle callback is not guaranteed to run after
        # the geometry manager's own, and measuring before it does reads 1 and would "centre" the
        # row on a band that does not exist yet.
        host.app.tk.update_idletasks()
        # Both guards are about the same hazard: winfo_height reports 1 until Tk has allocated the
        # widget, and a reading taken before then would "centre" the row on a band that does not
        # exist yet. Mapped plus flushed means the number is real.
        if not overlay.tk.winfo_ismapped():
            return
        wanted = footer_lead_height(host)
        above = int(lead.height)
        below = int(fill.tk.winfo_height())
        # Derived from the whole band, not from ``below`` against the constant. The band is what
        # stays invariant under the correction -- whatever the lead gives back, the fill takes --
        # so this settles in a single pass. Measuring ``below`` against ``wanted`` instead creeps:
        # each show closes half the remaining gap and the lead climbs back to its fixed value.
        target = min(wanted, (above + below) // 2)
        # Only when it differs: assigning a height re-packs the overlay, and the roomy case --
        # every panel, most of the time -- must measure and then do nothing at all.
        if above != target:
            lead.height = target
    except (AttributeError, TclError, RuntimeError, TypeError, ValueError):
        pass


def expand_overlay(overlay) -> None:
    """Make a panel reach down to the scope buttons, for as long as it is on screen.

    ``height="fill"`` is guizero's own vocabulary for this: ``Container._pack_widget`` maps it to
    Tk's ``fill=Y`` and, for a top or bottom side, adds ``expand=YES``. The overlay is a top-side
    child of its root and the scope box a bottom-side one, so the band between them is exactly
    the overlay's parcel -- no measuring of where the scope row happens to sit, and it follows
    whatever else is packed above.

    That depends on the scope box already being in the pack order when this expands: pack allots
    parcels in creation order, and an expanding child takes its space out of whatever is still
    unclaimed. ``EngineGui.build_gui`` reserves the bottom edge first, in both modes, for exactly
    this reason -- portrait used to create the scope buttons last.

    Reading it off the widget's own attribute is also what makes it durable. A raw
    ``pack_configure(expand=True)`` is discarded by the next ``display_widgets()`` pass, because
    that rebuilds the option dict from scratch and only ever consults ``width``/``height``.

    **At show time, not construction time.** A fill widget present while EngineGui measures the
    widget tree for its image baseline is how portrait lost its engine image box last time. The
    baseline is computed once, at the end of ``build_gui``, so nothing measured afterwards can be
    disturbed by this -- see collapse_overlay for the other half of the promise.
    """
    if getattr(overlay, _NO_EXPAND_ATTR, False):
        return
    try:
        if not hasattr(overlay, _OVERLAY_HEIGHT_ATTR):
            setattr(overlay, _OVERLAY_HEIGHT_ATTR, overlay.height)
        overlay.height = "fill"
    except (AttributeError, TclError, RuntimeError):
        pass


def collapse_overlay(overlay) -> None:
    """Give back the height expand_overlay took, so a closed popup leaves no trace in the pack.

    Called before ``hide()``, which is what triggers the repack: assigning a height that is not
    ``"fill"`` deliberately does *not* (``SizeMixin.resize`` only repacks for a fill), and
    ``_set_tk_config`` restores the tk default when handed ``None``.
    """
    try:
        overlay.height = getattr(overlay, _OVERLAY_HEIGHT_ATTR, None)
    except (AttributeError, TclError, RuntimeError):
        pass


def debug_diagnostics_enabled() -> bool:
    """Whether a DEBUG record would actually reach a handler, so measuring it is worth paying for.

    ``log.isEnabledFor(logging.DEBUG)`` is not enough on its own here, and on its own is in fact
    always true: ``set_up_logging`` puts the *root* logger at DEBUG unconditionally -- "required
    for handler levels to work" -- and filters entirely on the handlers, which is what ``-debug``
    and the runtime ``-debug`` toggle raise and lower. Guarding on the logger alone therefore
    buys nothing: every Tk round-trip below gets paid on every popup and the records are then
    dropped on the floor.

    Consulting the handlers also means the runtime toggle takes effect immediately, with no
    restart -- turn debug on, open the panel, read the numbers, turn it back off.
    """
    if not log.isEnabledFor(logging.DEBUG):
        return False
    return any(handler.level <= logging.DEBUG for handler in logging.getLogger().handlers)


def log_popup_geometry(host, overlay) -> None:
    """Schedule a report of where an overlay and its children actually landed.

    Both halves of "panels reach the scope buttons and the footer row is centred" are claims
    about pixels, and the last attempt at them was unpicked by bisect because nothing in the
    running program measured anything. Run with -debug and grep the log for "popupgeom".

    Deliberately *not* gated on ``compact``, unlike the admin panel's trace: portrait is the mode
    that regressed, so it is the mode that needs numbers.

    Diagnostics only -- it must never be able to break a popup, hence the broad guards and the
    single call site after the overlay is on screen.
    """
    if not debug_diagnostics_enabled():
        return
    try:
        host.app.tk.after(POPUP_GEOM_DELAY_MS, lambda: _report_popup_geometry(host, overlay))
    except (AttributeError, TclError, RuntimeError):
        pass


def _report_popup_geometry(host, overlay) -> None:
    """Log the overlay's reach and every child's band, once Tk has laid them out."""
    try:
        host.app.tk.update_idletasks()
        tk = overlay.tk
        bottom = tk.winfo_rooty() + tk.winfo_height()
        scope = getattr(host, "scope_box", None)
        # The target the panel is supposed to reach. gap= is the whole question: 0 means the
        # panel extends to the scope row, a large positive number means it stopped short, and a
        # negative one means it has run underneath.
        scope_top = scope.tk.winfo_rooty() if scope is not None else None
        log.debug(
            "popupgeom OVERLAY map=%s y=%s h=%s bottom=%s scope_top=%s gap=%s",
            int(tk.winfo_ismapped()),
            tk.winfo_rooty(),
            tk.winfo_height(),
            bottom,
            scope_top,
            None if scope_top is None else scope_top - bottom,
        )
        for child in getattr(overlay, "children", ()) or ():
            ctk = child.tk
            # Per-child tops and bottoms, so the footer row's centre can be compared against the
            # centre of the band left below the content without re-deriving either by hand.
            log.debug(
                "popupgeom   %-14s map=%s y=%-4s h=%-4s bottom=%-4s",
                ctk.winfo_class(),
                int(ctk.winfo_ismapped()),
                ctk.winfo_rooty(),
                ctk.winfo_height(),
                ctk.winfo_rooty() + ctk.winfo_height(),
            )
    except (AttributeError, TclError, RuntimeError, TypeError):
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
            overlay = Box(parent, align="top", border=2, visible=False)
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
            setattr(overlay, _NO_EXPAND_ATTR, True)
            body_src.ensure_gui(aggregator=self._host)
            body_src.gui.mount_gui(overlay)
            self.add_close_acc_btn(host, body_src, on_close, overlay)
            body_src.attach_overlay(overlay)
        elif isinstance(body_src, OverlayPanel):
            body = Box(overlay, align="top", layout="auto")
            body_src.build(body)
            fill = footer_fill(overlay)
            if body_src.has_footer:
                footer = Box(overlay, align="bottom")
                body_src.build_footer(footer)
                self.add_close_btn(host, on_close, footer, close_target=overlay, align="right", width=8)
            else:
                # add_close_btn already defaults to align="bottom", so a bare Close button is
                # positioned exactly as a row would be, and the overlay stands in as the footer.
                footer = overlay
                self.add_close_btn(host, on_close, overlay)
            self._place_footer_lead(host, overlay, footer, fill)
        else:
            body = Box(overlay, align="top", layout="auto")
            body_src(body)
            fill = footer_fill(overlay)
            self.add_close_btn(host, on_close, overlay)
            self._place_footer_lead(host, overlay, overlay, fill)

        if overlay.visible:
            with self._suspend_host_layout():
                overlay.hide()
        return overlay

    @staticmethod
    def _place_footer_lead(host, overlay: Box, footer: Box, fill: Box) -> None:
        """Add the whitespace above the footer row, and give the row its packing back.

        The lead has to be created after the row (see footer_lead), and creating anything in the
        overlay re-packs the overlay's children. That matters only when Close is a direct child
        of the overlay, since then it is one of them and loses the padding style_footer_button
        gave it; when there is a real footer row the buttons are inside it and untouched. Replayed
        either way, so this stays correct if the order ever changes again.

        The pair is recorded on the overlay because balance_footer_row needs both on every show,
        and picking them back out of the children by their height would break the moment the
        correction changed one of them.
        """
        lead = footer_lead(host, overlay)
        restore_footer_packing(footer)
        setattr(overlay, _FOOTER_BOXES_ATTR, (lead, fill))

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
        shown = False
        try:
            x, y = position if position else host.popup_position
            overlay.tk.place(x=x, y=y)
            expand_overlay(overlay)
            overlay.show()
            shown = True
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
        if shown:
            # Both outside the try on purpose: a measurement that failed must not be mistaken for
            # a popup that failed to appear, which would run the rollback above on a live overlay.
            balance_footer_row(host, overlay)
            log_popup_geometry(host, overlay)

    def close(self, overlay: Box | None = None) -> None:
        host = self._host

        with host.locked():
            overlay = overlay or self._state.current_popup
            self._state.current_popup = None

            if overlay:
                try:
                    # Before hide(), which is the call that repacks: a closed popup has to leave
                    # the host's pack exactly as it found it.
                    collapse_overlay(overlay)
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
