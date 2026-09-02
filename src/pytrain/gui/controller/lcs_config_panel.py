#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
The LCS configuration panel: a stepped overlay that programs an LCS module.

The panel walks the operator through four pages -- Device, base TMCC ID, the selected
device's own options, and a review of the exact Cab-remote presses -- then emits those
presses and reads the module back over PDI.

The panel takes every fact about a device from :mod:`lcs_device_registry`, every fact
about who owns a TMCC ID from :mod:`lcs_id_map`, and the presses themselves from
:mod:`lcs_sequence_builder`, so it holds no device knowledge of its own.

Configure sends presses only; nothing is written over PDI ``CONFIG SET``. The read-back
is therefore the only honest evidence that the module accepted anything, which is why a
read-back that does not arrive is reported rather than passed over in silence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from tkinter import TclError
from typing import Any, Callable, Sequence, TYPE_CHECKING

from guizero import Box, CheckBox, Text, TitleBox

from .lcs_device_registry import (
    MAX_TMCC_ID,
    LcsDevice,
    LcsMode,
    LcsOption,
    OptionKind,
    SENSOR_TRACK,
    configurable_devices,
    device_for_key,
    device_for_state,
    enabled_modes,
)
from .lcs_id_map import LcsOccupant, occupants_of, overlaps
from .lcs_sequence_builder import LcsProgram, build_program
from .overlay_panel import OverlayPanel
from .popup_manager import (
    FOOTER_BUTTON_PAD,
    FOOTER_BUTTON_PAD_COMPACT,
    restore_footer_packing,
    style_footer_button,
)
from ..components.checkbox_group import CheckBoxGroup
from ..components.editable_text import EditableText, EditorType
from ..components.hold_button import HoldButton
from ...db.state_watcher import StateWatcher
from ...protocol.constants import CommandScope
from ...utils.host_info import is_linux

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

log = logging.getLogger(__name__)

LCS_PANEL_TITLE = "LCS Module Configuration"

PAGE_DEVICE = 0
PAGE_ID = 1
PAGE_OPTIONS = 2
PAGE_REVIEW = 3

MIN_TMCC_ID = 1

# The ID page's heading names the module being programmed -- "BPC2 TMCC ID" -- so the
# operator can see at a glance which device the ID belongs to. Only reachable with a
# device chosen; the fallback covers the page as it is first built.
ID_HEADING = "{module} TMCC ID"
ID_HEADING_FALLBACK = "Base"

# The label on the box around the mode radios.
MODE_TITLE = "Mode"

# The label on the box around the lines that say what already answers to this TMCC ID.
ASSIGNED_TITLE = "Currently Assigned"
UNASSIGNED = "Unassigned"

# The label on the box around the modules the chosen block runs into. A box of its own,
# directly under the one above, because it answers a different question: that one says
# what holds the entered ID, this one what the whole block would collide with. The title
# carries the word "Overlaps", so the rows inside name modules and nothing else.
OVERLAP_TITLE = "Overlaps"

# Breathing room on either side of a module-row cell, so the gridded columns do not run
# into one another. Internal Label padding rather than grid padding, which is discarded
# every time anything in the box is shown, hidden or created.
ASSIGNED_CELL_PAD = 4

# A module row is the remote key, the module and its TMCC IDs, a column each.
ROW_COLUMNS = 3
WAITING_FOR_BASE = "Waiting for Base 3..."
NO_OPTIONS = "This module needs no further settings."
AWAITING_READBACK = "Waiting for the module to report..."
NO_RESPONSE = "No response - is the module in program mode?"
SENSOR_TRACK_FILTER_NOTE = (
    "The R\u279fL / L\u279fR engine ID filters are shown from the read-back, but are not written here."
)
SENSOR_TRACK_REVIEW_NOTE = (
    "The sequence is only complete once the Action Command has been assigned; "
    "pressing PROGRAM again aborts it with no change."
)

# Tight whitespace under the popup title row, and under a page's prompt. Real spacer
# widgets (host.add_vspace), never pack padding: padding is discarded the next time
# anything in the container is created or shown -- the same reason footer_lead is a
# widget. The compact pane cannot afford the portrait value.
SECTION_GAP = 10
SECTION_GAP_COMPACT = 6

# Whitespace between the parts of the ID page -- the stepper row, the titled boxes, the
# lines derived from them, the choice buttons -- and above the Back/Next row. Wider than
# SECTION_GAP, which sits under a heading that belongs with whatever follows it; these
# separate sections that answer different questions, and without them the page read as
# one dense block on the Pi. Spacer widgets for the reason given above.
PAGE_GAP = 16
PAGE_GAP_COMPACT = 8

# Whitespace between the Currently Assigned, Overlaps and Mode boxes, in pixels. Grid
# padding rather than a spacer widget, which is safe here for the one reason it is not
# safe elsewhere: _lay_out_titled_boxes already has to re-apply these boxes' grid options
# after every refresh, so the padding is replayed along with the stretch. Applied below
# each box, the last one included, which is whitespace the block line below wants anyway.
BOX_GAP = 8
BOX_GAP_COMPACT = 4

# Fallback slot width for the hidden Back button, used only when the real button cannot
# be measured (a headless stand-in). Chosen from the measured 184 px request of a styled
# width=8 footer button at portrait size.
FOOTER_SLOT_FALLBACK = 184

# Presses are staggered so the base sees them as separate gestures, and the read-back
# GETs are held off until the module has had a moment to act on the last of them.
PRESS_DELAY = 0.35
VERIFY_DELAY = 1.0
READBACK_TIMEOUT_MSEC = 5000

# What the Cab remote calls each scope, which is the language the operator's manual uses.
SCOPE_LABEL: dict[CommandScope, str] = {
    CommandScope.ACC: "ACC",
    CommandScope.SWITCH: "SW",
    CommandScope.TRAIN: "TR",
}

# What each of those remote keys is for. The mode labels name the key -- "ACCessory",
# "SWitch", "TRack" -- but not what it is good for, which is the one thing an operator
# choosing between them needs. Only the keys the selected module actually offers are
# shown, so the footnote never states a fact that does not apply to the module in hand.
SCOPE_USE: dict[CommandScope, str] = {
    CommandScope.ACC: "ACC: Use for lighting and operating accessories",
    CommandScope.SWITCH: "SW: Use for Switches/Turnouts",
    CommandScope.TRAIN: "TR: Use for track power blocks",
}


@dataclass(frozen=True)
class ModuleRow:
    """
    One line of the Currently Assigned or Overlaps box: "ACC: BPC2 TMCC IDs 1 - 8".

    Held as separate parts rather than one string because both boxes grid them into
    columns, so that the module names and the ID ranges line up down the box however
    long the names above them run, and because only the remote key is drawn bold.
    """

    scope: str
    module: str
    ids: str = ""

    @property
    def cells(self) -> tuple[str, str, str]:
        return self.scope, self.module, self.ids

    @property
    def text(self) -> str:
        return " ".join(part for part in self.cells if part)


def touch_only_editing() -> bool:
    """True where an on-screen editor is the only keyboard: the Pi and the Steam Deck.

    Both are Linux, and ``is_linux()`` is what the rest of the project already uses to tell
    the appliance platform from a desktop. Taken from ``utils.host_info``, never from the
    ``pytrain`` package root: that package imports ``EngineGui`` -- and through it this
    module -- before it defines anything of its own, so importing it back is circular.
    ``admin_panel`` reads ``is_steam_deck`` from the same leaf module for the same reason.
    """
    return is_linux()


def reflects_layout_by_default() -> bool:
    """True where the panel should open on the module already at the entered TMCC ID.

    On the Pi and the Steam Deck the panel is opened from a screen that is *about*
    something -- a switch, an accessory -- so the module answering to that address on that
    remote key is the one the operator means, and pre-selecting it saves them a tap.

    On a desktop there is no such context: the stand-alone window opens on nothing in
    particular at TMCC ID 1, and guessing from whatever happens to sit there is how a
    panel opened on an STM2 when the operator had come to program something else. There
    it opens on the first module offered, which is stable and predictable.

    Same platform test as :func:`touch_only_editing`, and for the same reason: Linux is
    the appliance, everything else is a desk.
    """
    return is_linux()


def needs_close_button() -> bool:
    """True where the panel has to carry a Close button: the Pi and the Steam Deck.

    Those two run full screen with no window frame, so a button below the panel is the
    only way off it. A desktop window has a title bar, and its close box is already wired
    to the very same shutdown -- ``GuiZeroBase.run`` sets ``App.when_closed`` to ``close``
    -- so a Close inside the window is a second one of something the window already has.

    Same platform test as :func:`touch_only_editing`, and for the same reason.
    """
    return is_linux()


class LcsConfigPanel(OverlayPanel):
    """
    A stepped overlay that walks the operator through programming an LCS module.
    """

    def __init__(
        self,
        host: "EngineGui",
        title: str = LCS_PANEL_TITLE,
        *,
        post_close: Callable = None,
    ) -> None:
        # post_close is what a stand-alone host uses to shut its window down when the panel
        # is dismissed; embedded in EngineGui there is a GUI underneath, so nothing is passed
        # and closing the popup just uncovers it.
        super().__init__(host, title, post_close=post_close)
        self._device: LcsDevice | None = None
        self._mode: LcsMode | None = None
        self._base_id: int = MIN_TMCC_ID
        self._options: dict[str, Any] = {}
        self._page_index: int = PAGE_DEVICE
        # The ID the operator explicitly chose to reconfigure as a new module, so the
        # occupancy banner stops offering to seed it from the module that owns it.
        self._configure_as_new_id: int | None = None
        # False until the operator picks a module for themselves. A module is always
        # selected -- the first one offered when there is nothing to reflect -- so the
        # selection alone can no longer say whether the panel is still showing its own
        # opening guess, which is what may be re-seeded when the store arrives late.
        self._device_chosen: bool = False

        self._pages: list[Box] = []
        self._body: Box | None = None
        self._device_group: CheckBoxGroup | None = None
        self._titled_boxes: Box | None = None
        self._mode_box: TitleBox | None = None
        self._mode_group: CheckBoxGroup | None = None
        self._id_heading: Text | None = None
        self._id_field: EditableText | None = None
        self._minus_btn: HoldButton | None = None
        self._plus_btn: HoldButton | None = None
        self._block_line: Text | None = None
        self._mode_footnote_line: Text | None = None
        self._assigned_box: TitleBox | None = None
        self._assigned_grid: Box | None = None
        # One tuple of three cells per row: the remote key, the module, and its TMCC IDs.
        # Created as they are first needed and reused from then on.
        self._assigned_cells: list[tuple[Text, ...]] = []
        self._overlap_box: TitleBox | None = None
        self._overlap_grid: Box | None = None
        self._overlap_cells: list[tuple[Text, ...]] = []
        self._goto_btn: HoldButton | None = None
        self._new_btn: HoldButton | None = None
        self._back_btn: HoldButton | None = None
        self._back_slot: Box | None = None
        self._next_btn: HoldButton | None = None
        self._nav: Box | None = None
        self._suspend_device_selector = False
        self._suspend_option_selectors = False
        # Set only by a stand-alone host that opens the window ahead of synchronization;
        # a panel embedded in a running GUI never turns this on.
        self._sync_pending = False
        self._sync_line: Text | None = None

        # Options page
        self._option_boxes: dict[str, Box] = {}
        self._option_widgets: dict[tuple[str, str], Any] = {}
        self._option_choices: dict[tuple[str, str], list[Any]] = {}
        self._options_summary: Text | None = None
        self._warning_line: Text | None = None
        self._reserved_line: Text | None = None

        # Review page
        self._program_line: Text | None = None
        self._review_line: Text | None = None
        self._review_note_line: Text | None = None
        self._configure_btn: HoldButton | None = None
        self._footnote_line: Text | None = None
        self._requested_line: Text | None = None
        self._reported_line: Text | None = None

        # Read-back
        self._sent_program: LcsProgram | None = None
        self._readback_watcher: StateWatcher | None = None
        self._readback_pending = False

    #
    # State
    #
    @property
    def device(self) -> LcsDevice | None:
        return self._device

    @property
    def mode(self) -> LcsMode | None:
        return self._mode

    @property
    def base_id(self) -> int:
        return self._base_id

    @property
    def options(self) -> dict[str, Any]:
        return dict(self._options)

    @property
    def page_index(self) -> int:
        return self._page_index

    @property
    def max_base(self) -> int:
        return self._mode.max_base if self._mode else MAX_TMCC_ID

    @property
    def ports(self) -> int:
        return self._mode.ports if self._mode else 1

    @property
    def scope(self) -> CommandScope | None:
        return self._mode.scope if self._mode else None

    @property
    def compact(self) -> bool:
        return bool(getattr(self._gui, "compact", False))

    @property
    def touch_editing(self) -> bool:
        """
        Whether the ID field needs an on-screen editor; see :func:`touch_only_editing`.
        """
        return touch_only_editing()

    @property
    def id_heading_text(self) -> str:
        """
        The ID page's heading, naming the selected module: "BPC2 TMCC ID".
        """
        module = self._device.label if self._device else ID_HEADING_FALLBACK
        return ID_HEADING.format(module=module)

    @property
    def _store(self) -> Any:
        return getattr(self._gui, "state_store", None)

    @property
    def sync_pending(self) -> bool:
        """
        True while the panel is running ahead of Base 3 synchronization.
        """
        return self._sync_pending

    def set_sync_pending(self, pending: bool) -> None:
        """
        Show or hide the waiting banner and re-gate Configure accordingly.
        """
        self._sync_pending = bool(pending)
        self._refresh_sync_line()
        self._refresh_review_page()

    def on_synchronized(self) -> None:
        """
        The state store is populated: refresh what the panel reads from it.

        The operator's own choices are never overwritten; the panel re-seeds itself from
        the store only while it is still showing the module it opened on. Safe to call
        twice.
        """
        self.set_sync_pending(False)
        if not self._device_chosen:
            self.configure(tmcc_id=self._base_id)
            return
        self._seed_sensor_track_action()
        self._refresh_id_page()
        self._refresh_review_page()

    def _refresh_sync_line(self) -> None:
        if self._sync_line is None:
            return
        if self._sync_pending:
            self._sync_line.value = WAITING_FOR_BASE
            self._sync_line.show()
        else:
            self._sync_line.value = ""
            self._sync_line.hide()

    #
    # Construction
    #
    @property
    def _section_gap(self) -> int:
        return SECTION_GAP_COMPACT if self.compact else SECTION_GAP

    @property
    def _page_gap(self) -> int:
        return PAGE_GAP_COMPACT if self.compact else PAGE_GAP

    @property
    def _box_gap(self) -> int:
        return BOX_GAP_COMPACT if self.compact else BOX_GAP

    def build(self, body: Box) -> None:
        host = self._gui
        self._body = body
        # First child of the body, so every page sits this far below the title row.
        host.add_vspace(body, self._section_gap)
        # Above the pages, so the banner shows on whichever page is up.
        self._sync_line = self._label(body, "", bold=True)
        self._refresh_sync_line()
        self._pages = [
            self._build_device_page(body),
            self._build_id_page(body),
            self._build_options_page(body),
            self._build_review_page(body),
        ]
        # Back and Next belong to the panel, not to the popup's footer row: the popup adds
        # its own Close below everything built here, so Close gets a line of its own
        # instead of the three buttons sharing one. Created after the pages so the row is
        # packed below whichever page is showing.
        host.add_vspace(body, self._page_gap)
        self._build_nav(body)
        self._show_page(self._page_index)

    def _label(self, parent: Box, text: str, size: int | None = None, bold: bool = False, **kwargs) -> Text:
        host = self._gui
        lbl = Text(parent, text=text, align="top", **kwargs)
        lbl.text_size = size or host.s_14
        lbl.text_bold = bold
        return lbl

    def _build_device_page(self, body: Box) -> Box:
        host = self._gui
        page = Box(body, align="top", border=0)
        self._label(page, "Which module are you configuring?", size=host.s_16, bold=True)
        host.add_vspace(page, self._section_gap)
        self._device_group = CheckBoxGroup(
            page,
            size=host.s_14,
            options=self.device_options(),
            selected=None,
            align="top",
            style="radio",
            command=self._on_device_selected,
        )
        self._equalize_group_rows(self._device_group)
        return page

    @staticmethod
    def _equalize_group_rows(group: CheckBoxGroup) -> None:
        """Make every row of a vertical ButtonGroup as wide as the widest one.

        guizero grids a vertical group's rows into one column with align="left", i.e.
        sticky="W", so each row keeps its natural width and a short label leaves a short
        box -- measured 326 / 317 / 225 / 318 px for ASC2 / BPC2 / STM2 / Sensor Track.
        Giving the column weight and stretching each row into it makes them all the
        column's width, which is the widest row's.

        Deliberately not CheckBoxGroup(width=...): Tk honors an explicit -width by
        *dropping* the row's padx (306 px at width=300 regardless of padx), which would
        pull every radio dot flush against the left edge.

        Only safe on a group whose rows are not rebuilt. ButtonGroup._refresh_options
        destroys and recreates them, and creating a widget re-grids every sibling and wipes
        sticky -- see admin_panel._apply_compact_grid. The device group never rebuilds; the
        mode and option groups do, and are left alone.
        """
        rows = getattr(group, "_rbuttons", None) or ()
        try:
            group.tk.grid_columnconfigure(0, weight=1)
            for row in rows:
                row.tk.grid_configure(sticky="ew")
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def _build_id_page(self, body: Box) -> Box:
        host = self._gui
        page = Box(body, align="top", border=0)
        self._id_heading = self._label(page, self.id_heading_text, size=host.s_16, bold=True)

        row = Box(page, layout="grid", align="top", border=0)
        self._minus_btn = HoldButton(
            row,
            text="-",
            grid=[0, 0],
            align=None,
            width=3,
            command=self.step_down,
        )
        # A desktop has a real keyboard, so the ID is an ordinary text box the system
        # keyboard types into; the Pi and the Deck are touch-only and get the on-screen
        # keypad. Both cases stay one EditableText, so everything that reads or writes the
        # field -- _refresh_id_field, _on_id_committed -- is the same on either platform.
        touch = self.touch_editing
        self._id_field = EditableText(
            row,
            grid=[1, 0],
            align=None,
            width=4,
            height=1,
            editor=EditorType.KEYPAD if touch else EditorType.KEYBOARD,
            # Only a touch appliance needs an editor drawn on screen.
            show_keyboard_on_edit=touch,
            compact=self.compact,
            field_name=self.id_heading_text,
            max_length=2,
            on_commit=self._on_id_committed,
        )
        self._id_field.text_size = host.s_20
        self._style_id_field(self._id_field)
        self._plus_btn = HoldButton(
            row,
            text="+",
            grid=[2, 0],
            align=None,
            width=3,
            command=self.step_up,
        )
        for btn in (self._minus_btn, self._plus_btn):
            btn.text_size = host.s_20

        host.add_vspace(page, self._page_gap)

        # The titled boxes share one grid column, which is how they come out the same
        # width: the column is as wide as the widest of them, and each box is stretched
        # into it. Stacked rather than packed for exactly that reason -- packed boxes each
        # keep their own natural width, which is what left them ragged. The whitespace
        # between them rides along with that stretch; see _lay_out_titled_boxes.
        self._titled_boxes = Box(page, layout="grid", align="top", border=0)

        # What already answers to this ID, directly under the ID row it describes: it tells
        # the operator whether they are about to reprogram a module that is already out
        # there, which they need to know before choosing a mode, not after. Titled, because
        # a bare line naming some other module beside the one being programmed reads as a
        # contradiction until you know it is reporting the layout rather than the choice.
        # At the page's body size, as are the other two titles and the module rows inside
        # all three: a step below read as fine print on the Pi, and what these boxes report
        # is what the operator checks before committing an ID.
        self._assigned_box = TitleBox(self._titled_boxes, text=ASSIGNED_TITLE, grid=[0, 0], align=None)
        self._assigned_box.text_size = host.s_14
        # One row per module, gridded so the remote key, the module and its TMCC IDs line
        # up down the box instead of each row starting wherever the row above it ended.
        self._assigned_grid = Box(self._assigned_box, layout="grid", align="top", border=0)

        # Directly after it: the modules the chosen block would run into. Its own box, and
        # gridded a row per module rather than run together on one line, which is what put
        # two neighbors off the right edge of the window. Hidden when nothing is in the way,
        # since an empty titled frame reads as a failure to look rather than as an answer --
        # unlike the assigned box, which always has "Unassigned" to say.
        self._overlap_box = TitleBox(self._titled_boxes, text=OVERLAP_TITLE, grid=[0, 1], align=None)
        self._overlap_box.text_size = host.s_14
        self._overlap_grid = Box(self._overlap_box, layout="grid", align="top", border=0)

        # The mode radios are the only choice on this page besides the ID itself, so they
        # are given a titled box that says what they are choosing -- and a size above the
        # page's body text, since each label also carries the port count.
        self._mode_box = TitleBox(self._titled_boxes, text=MODE_TITLE, grid=[0, 2], align=None)
        self._mode_box.text_size = host.s_14
        self._mode_group = CheckBoxGroup(
            self._mode_box,
            size=host.s_18,
            options=self.mode_options(),
            selected=None,
            align="top",
            style="radio",
            command=self._on_mode_selected,
        )

        host.add_vspace(page, self._page_gap)

        # The block the chosen mode claims, derived from the ID and the mode above it, so
        # it is one of the quietest lines on the page.
        self._block_line = self._label(page, "", size=host.s_10)
        # A footnote to the mode radios: what each remote key above is actually for.
        self._mode_footnote_line = self._label(page, "", size=host.s_10)

        host.add_vspace(page, self._page_gap)

        choices = Box(page, align="top", border=0)
        self._goto_btn = HoldButton(choices, text="Go to", align="left", command=self.go_to_owning_base)
        self._new_btn = HoldButton(choices, text="Configure as new", align="left", command=self.configure_as_new)
        for btn in (self._goto_btn, self._new_btn):
            btn.text_size = host.s_12
            btn.hide()
        # No device is chosen yet, so the mode box starts hidden rather than empty.
        self._refresh_mode_selector()
        # Builds the first assigned row, so that box says something from the outset.
        self._refresh_occupancy()
        self._lay_out_titled_boxes()
        return page

    def _lay_out_titled_boxes(self) -> None:
        """Give the Currently Assigned, Overlaps and Mode boxes one width, and space between.

        All three are gridded into column 0 of the same container and stretched across it,
        so the column takes the width of whichever box asks for most and the others grow to
        match. No pixel width is chosen anywhere: a module name long enough to widen the
        assigned box widens the mode box with it, and vice versa.

        Re-applied after every refresh rather than set once, because guizero rebuilds a
        container's grid options from scratch in ``display_widgets`` -- which runs whenever
        any child is shown, hidden or created -- and neither ``sticky`` nor ``pady`` is among
        the options it replays. Hiding the mode box for a device with no modes is enough to
        lose them. A hidden box is skipped: ``grid_configure`` on a widget the grid has
        forgotten would put it back on screen.

        That replay is also what makes ``pady`` the one place here where whitespace is
        padding rather than a spacer widget: it is re-applied on the same schedule as the
        stretch, so it cannot be silently dropped the way padding elsewhere in the panel
        would be. Stacked flush, the three boxes read as one ruled block on the Pi.
        """
        container = self._titled_boxes
        if container is None:
            return
        gap = self._box_gap
        try:
            container.tk.grid_columnconfigure(0, weight=1)
            for box in (self._assigned_box, self._overlap_box, self._mode_box):
                if box is not None and box.visible:
                    box.tk.grid_configure(sticky="ew", pady=(0, gap))
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def _style_id_field(self, field: EditableText) -> None:
        """Draw the ID as a text box, and open it on a click where there is a mouse.

        The field is a guizero Text, which renders as a bare label. The sunken border in the
        editor's own colors is what tells the operator it can be typed into, and it means the
        box does not change appearance when the Tk entry is placed over it.

        Press-and-hold is a touchscreen gesture: a mouse click is released long before any
        hold threshold, so on a desktop the box also opens for editing on a plain click.
        """
        try:
            field.tk.config(bg=field.edit_bg, fg=field.edit_fg, relief="sunken", bd=2)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        if self.touch_editing:
            return
        try:
            field.tk.bind("<Button-1>", lambda _event: field.begin_edit(), add="+")
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    #
    # Options page
    #
    def _build_options_page(self, body: Box) -> Box:
        host = self._gui
        page = Box(body, align="top", border=0)
        self._label(page, "Options", size=host.s_16, bold=True)
        self._options_summary = self._label(page, "")
        self._warning_line = self._label(page, "", size=host.s_12)
        self._reserved_line = self._label(page, "", size=host.s_12)
        # One options box per device, built once and shown or hidden as the selection
        # changes. Rebuilding a CheckBoxGroup's rows at runtime loses the painted
        # indicators decorate_checkbox installs, so the rows a device declares are
        # created here, with the device, and never rebuilt.
        for device in configurable_devices():
            box = Box(page, align="top", border=0)
            self._option_boxes[device.key] = box
            if device.options:
                for option in device.options:
                    self._build_option(box, device, option)
            else:
                self._label(box, NO_OPTIONS)
            box.hide()
        return page

    def _build_option(self, box: Box, device: LcsDevice, option: LcsOption) -> None:
        host = self._gui
        key = (device.key, option.key)
        if option.kind == OptionKind.RADIO:
            self._label(box, option.label, bold=True)
            self._option_choices[key] = [value for _label, value in option.choices]
            widget = CheckBoxGroup(
                box,
                size=host.s_12,
                # The index is the row's value: an IrdaSequence is not a string, and
                # guizero hands back whatever string Tk holds.
                options=[[label, str(i)] for i, (label, _value) in enumerate(option.choices)],
                selected=None,
                align="top",
                style="radio",
                command=self._option_command(device.key, option.key),
            )
        else:
            widget = CheckBox(
                box,
                text=option.label,
                align="top",
                command=self._option_command(device.key, option.key),
            )
            widget.text_size = host.s_14
        self._option_widgets[key] = widget
        if not option.enabled:
            widget.disable()
        if option.note:
            self._label(box, option.note, size=host.s_12)

    def _option_command(self, device_key: str, option_key: str) -> Callable[[], None]:
        # guizero calls a widget's command with no arguments, so the closure carries
        # which option it belongs to and reads the value from the widget itself.
        def command() -> None:
            self._on_option_changed(device_key, option_key)

        return command

    def _on_option_changed(self, device_key: str, option_key: str) -> None:
        if self._suspend_option_selectors or self._device is None or self._device.key != device_key:
            return
        widget = self._option_widgets.get((device_key, option_key))
        if widget is None:
            return
        option = self._device.option(option_key)
        if option.kind == OptionKind.RADIO:
            choices = self._option_choices.get((device_key, option_key), [])
            try:
                index = int(widget.value)
            except (TypeError, ValueError):
                return
            if 0 <= index < len(choices):
                self._options[option_key] = choices[index]
        else:
            self._options[option_key] = bool(int(widget.value or 0))
        self._refresh_review_page()

    def _refresh_options_page(self) -> None:
        device = self._device
        if self._options_summary is not None:
            self._options_summary.value = self.options_summary
        if self._warning_line is not None:
            self._warning_line.value = device.warning if device and device.warning else ""
        if self._reserved_line is not None:
            self._reserved_line.value = self.reserved_text
        for key, box in self._option_boxes.items():
            if device is not None and key == device.key:
                box.show()
            else:
                box.hide()
        if device is None:
            return
        self._suspend_option_selectors = True
        try:
            for option in device.options:
                widget = self._option_widgets.get((device.key, option.key))
                if widget is None:
                    continue
                value = self._options.get(option.key)
                if option.kind == OptionKind.RADIO:
                    choices = self._option_choices.get((device.key, option.key), [])
                    widget.value = str(choices.index(value)) if value in choices else None
                else:
                    widget.value = 1 if value else 0
        finally:
            self._suspend_option_selectors = False

    @property
    def options_summary(self) -> str:
        if self._device is None or self._mode is None:
            return ""
        scope = SCOPE_LABEL.get(self._mode.scope, "")
        return f"{self._device.label} - {self._mode.label} at {scope} {self._base_id}".strip()

    @property
    def reserved_text(self) -> str:
        """
        The modes the manual reserves, named with their reason, so an operator looking
        for one is told why it is not on offer rather than left to wonder.
        """
        if self._device is None:
            return ""
        reserved = [mode for mode in self._device.modes if not mode.enabled]
        if not reserved:
            return ""
        parts = [f"{mode.label} ({mode.note})" if mode.note else mode.label for mode in reserved]
        return "Not available: " + ", ".join(parts)

    #
    # Review page
    #
    def _build_review_page(self, body: Box) -> Box:
        host = self._gui
        page = Box(body, align="top", border=0)
        self._label(page, "Review and Configure", size=host.s_16, bold=True)
        self._program_line = self._label(page, "", size=host.s_12)
        self._review_line = self._label(page, "")
        self._review_note_line = self._label(page, "", size=host.s_12)
        self._configure_btn = btn = HoldButton(page, text="Configure", align="top", command=self.on_configure)
        btn.text_size = host.s_16
        self._footnote_line = self._label(page, "", size=host.s_12)
        self._requested_line = self._label(page, "", size=host.s_12)
        self._reported_line = self._label(page, "", size=host.s_12)
        return page

    @property
    def program(self) -> LcsProgram | None:
        """
        The programming sequence for the current selection, or None when it is incomplete.
        """
        if self._device is None or self._mode is None:
            return None
        try:
            return build_program(self._device, self._mode, self._base_id, self._options)
        except ValueError as ve:
            log.debug("Cannot build LCS program: %s", ve)
            return None

    @property
    def review_lines(self) -> list[str]:
        program = self.program
        return list(program.display) if program else []

    @property
    def review_note(self) -> str:
        notes: list[str] = []
        if self._device is not None and self._device.warning:
            notes.append(self._device.warning)
        if self._device is SENSOR_TRACK:
            notes.append(SENSOR_TRACK_REVIEW_NOTE)
        return " ".join(notes)

    @property
    def footnote(self) -> str:
        if self._device is None:
            return ""
        return f"Be sure your {self._device.label} is in Program mode."

    def _refresh_review_page(self) -> None:
        program = self.program
        if self._program_line is not None:
            self._program_line.value = program.program_instruction if program else ""
        if self._review_line is not None:
            self._review_line.value = "\n".join(program.display) if program else ""
        if self._review_note_line is not None:
            self._review_note_line.value = self.review_note
        if self._footnote_line is not None:
            self._footnote_line.value = self.footnote
        if self._configure_btn is not None:
            self._enable(self._configure_btn, program is not None and not self._sync_pending)

    #
    # Configure
    #
    def on_configure(self) -> None:
        """
        Emit the presses, then ask the module to report what it now holds.
        """
        program = self.program
        if program is None:
            return
        host = self._gui
        submit = getattr(host, "submit_request", None)
        if submit is None:  # pragma: no cover - every real host queues requests
            log.warning("Host cannot queue requests; LCS presses not sent")
            return
        for i, request in enumerate(program.presses):
            submit(request, 1, i * PRESS_DELAY)
        after_presses = len(program.presses) * PRESS_DELAY + VERIFY_DELAY
        for j, request in enumerate(program.verify):
            submit(request, 1, after_presses + j * PRESS_DELAY)

        self._sent_program = program
        self._readback_pending = True
        if self._requested_line is not None:
            self._requested_line.value = f"Requested: {self.options_summary}"
        if self._reported_line is not None:
            self._reported_line.value = AWAITING_READBACK
        self._watch_readback(program)
        self._schedule(READBACK_TIMEOUT_MSEC, self.on_readback_timeout)

    def _schedule(self, msec: int, action: Callable[[], None]) -> None:
        app = getattr(self._gui, "app", None)
        if app is None:
            return
        try:
            app.after(msec, action)
        except Exception as e:  # pragma: no cover - defensive; Tk may be tearing down
            log.debug("Could not schedule LCS read-back timeout: %s", e)

    def readback_state(self, program: LcsProgram | None = None) -> Any:
        """
        The component state the module's read-back lands in, if the store holds one.
        """
        program = program or self._sent_program
        store = self._store
        if program is None or store is None:
            return None
        get_state = getattr(store, "get_state", None)
        if get_state is None:
            return None
        scopes = [CommandScope.IRDA] if program.device is SENSOR_TRACK else [program.mode.scope]
        for scope in scopes:
            try:
                state = get_state(scope, program.base_id, False)
            except Exception:  # pragma: no cover - store shapes vary
                state = None
            if state is not None:
                return state
        return None

    def _watch_readback(self, program: LcsProgram) -> None:
        self._stop_readback_watcher()
        state = self.readback_state(program)
        if state is None:
            return
        try:
            self._readback_watcher = StateWatcher(state, self._on_readback_changed)
        except Exception as e:  # pragma: no cover - defensive
            log.debug("Could not watch LCS read-back: %s", e)

    def _stop_readback_watcher(self) -> None:
        watcher, self._readback_watcher = self._readback_watcher, None
        if watcher is not None:
            try:
                watcher.shutdown()
            except Exception:  # pragma: no cover - defensive
                pass

    def _on_readback_changed(self) -> None:
        # Runs on the watcher thread; the display is touched on the Tk thread only.
        queue_message = getattr(self._gui, "queue_message", None)
        if queue_message is None:
            self.on_readback()
        else:
            queue_message(self.on_readback)

    def on_readback(self) -> None:
        state = self.readback_state()
        if state is None:
            return
        self._readback_pending = False
        if self._reported_line is not None:
            self._reported_line.value = f"Reported: {self.reported_text(state)}"

    def on_readback_timeout(self) -> None:
        """
        A read-back that never arrived. The presses stay on screen; only the reported
        line changes, because what was sent is still the truth about what was sent.
        """
        if not self._readback_pending:
            return
        if self.readback_state() is not None:
            self.on_readback()
            return
        self._readback_pending = False
        if self._reported_line is not None:
            self._reported_line.value = NO_RESPONSE

    def reported_text(self, state: Any) -> str:
        """
        What the module says it now holds, in the panel's own terms.
        """
        program = self._sent_program
        device = program.device if program else self._device
        label = device.label if device else "Module"
        address = getattr(state, "address", None) or getattr(state, "tmcc_id", None)
        parts = [f"{label} at {address}"]
        # The registry's scope for the selected mode, never the parsed scope: a
        # mode-3 ASC2 is mis-scoped by asc2_req.py.
        mode = program.mode if program else self._mode
        if mode is not None:
            parts.append(SCOPE_LABEL.get(mode.scope, ""))
        num_ids = getattr(state, "num_ids", None)
        if isinstance(num_ids, int) and num_ids > 0:
            parts.append(f"{num_ids} IDs")
        if device is SENSOR_TRACK:
            sequence = getattr(state, "sequence", None)
            if sequence is not None:
                parts.append(self._action_label(sequence))
            parts.append(f"R\u279fL {self._filter_text(state, 'loco_rl')}")
            parts.append(f"L\u279fR {self._filter_text(state, 'loco_lr')}")
        return ", ".join(part for part in parts if part)

    @staticmethod
    def _filter_text(state: Any, key: str) -> str:
        value = getattr(state, key, None)
        if value is None:
            value = getattr(state, f"_{key}", None)
        return "Any" if value in (None, 255) else f"{value}"

    @staticmethod
    def _action_label(value: Any) -> str:
        for label, choice in SENSOR_TRACK.option("action").choices:
            if choice == value:
                return label
        return f"{value}"

    #
    # Options presented on the device and mode radios
    #
    @staticmethod
    def device_options() -> list[list[str]]:
        # Only the modules this pass can program; the registry also holds modules it can
        # merely recognize, and offering one of those would lead nowhere.
        return [[f"{device.label} ({device.blurb})", device.key] for device in configurable_devices()]

    def mode_options(self) -> list[list[str]]:
        if self._device is None:
            return []
        return [[mode.label, mode.key] for mode in enabled_modes(self._device)]

    #
    # Page swapping
    #
    def _show_page(self, index: int) -> None:
        if not self._pages:
            self._page_index = index
            return
        index = max(0, min(index, len(self._pages) - 1))
        self._page_index = index
        for i, page in enumerate(self._pages):
            if i == index:
                page.show()
            else:
                page.hide()
        self._refresh_nav()

    def next_page(self) -> None:
        self._show_page(self._page_index + 1)

    def previous_page(self) -> None:
        self._show_page(self._page_index - 1)

    #
    # Seeding
    #
    def configure(self, scope: CommandScope = None, tmcc_id: int = None, state: Any = None) -> None:
        """
        Seed the panel from whatever is on screen when the LCS... key is pressed.

        Which module the panel opens on depends on the host; see
        :func:`reflects_layout_by_default`. On the Pi and the Steam Deck the module already
        answering to the entered ID on the screen's own remote key is pre-selected, because
        that screen is what the operator was looking at. On a desktop nothing is reflected
        and the first module offered is chosen instead. Either way a module *is* chosen, so
        the page never opens with an empty radio group and Next always has somewhere to go.
        """
        self._configure_as_new_id = None
        self._page_index = PAGE_DEVICE
        self._device = self._mode = None
        self._options = {}
        self._reset_readback()

        reflect = reflects_layout_by_default()
        device = device_for_state(state) if reflect else None
        if device is not None and not device.configurable:
            # The screen is on a module this pass can only recognize -- an AMC2. It has no
            # modes to open the panel on, so it is treated as no device at all: the search
            # below still finds it, and it is named in the assigned box like any other.
            device = None
        self._device_chosen = False
        if device is not None:
            self._select_device(device, seed_mode_from=state)
        base_id = tmcc_id if isinstance(tmcc_id, int) and tmcc_id >= MIN_TMCC_ID else MIN_TMCC_ID
        self._base_id = min(max(base_id, MIN_TMCC_ID), self.max_base)
        if device is None and reflect:
            occupant = self._discovery_occupant(scope)
            if occupant is not None and occupant.base_id == self._base_id:
                self._seed_from_occupant(occupant)
        if self._device is None:
            self._select_device(self.default_device)
        # The mode is settled only now, and with it how many IDs the block needs, so the
        # entered ID is squared with the chosen mode's ceiling rather than the global one.
        self._base_id = min(self._base_id, self.max_base)
        self._seed_sensor_track_action()
        self._refresh_device_selector()
        self._refresh_id_page()
        self._show_page(PAGE_DEVICE)

    @property
    def default_device(self) -> LcsDevice:
        """
        The module the panel opens on when there is nothing to reflect: the first offered.

        ``configurable_devices`` is sorted by name, so this is the ASC2 today and stays the
        first name in the list as modules are added.
        """
        return configurable_devices()[0]

    def _select_device(self, device: LcsDevice | None, seed_mode_from: Any = None, mode: LcsMode = None) -> None:
        self._device = device
        if device is None:
            self._mode = None
            self._options = {}
            return
        if mode is None:
            mode = None
            pdi_mode = getattr(seed_mode_from, "mode", None)
            if isinstance(pdi_mode, int) and not isinstance(pdi_mode, bool):
                mode = device.mode_for_pdi_mode(pdi_mode)
            if mode is None or not mode.enabled:
                mode = device.default_mode
        self._mode = mode
        self._options = self._default_options(device, seed_mode_from)

    def _default_options(self, device: LcsDevice, state: Any = None) -> dict[str, Any]:
        options: dict[str, Any] = {}
        for option in device.options:
            value = option.default
            seeded = getattr(state, option.key, None) if state is not None else None
            if seeded is not None:
                value = seeded
            options[option.key] = value
        return options

    def _discovery_occupant(self, scope: CommandScope = None) -> LcsOccupant | None:
        """
        What holds the entered ID, before any module has been chosen to program.

        No mode has been picked yet, so the panel has no address space of its own to
        search in. The screen the operator came from is the best hint there is -- the
        LCS... key pressed from the switch screen means switch IDs -- so its scope is
        tried first. Only when that turns up nothing, or the screen is not on an LCS
        key at all, does the search widen to every module, because the whole point of
        this lookup is to discover what kind of module is out there.

        Only a module this pass can program is worth seeding from; an AMC2 sitting on the
        ID is reported in the assigned box, but the panel cannot open on it.
        """
        if scope is not None:
            occupant = self._first_programmable(occupants_of(self._base_id, self._store, scope=scope))
            if occupant is not None:
                return occupant
        return self._first_programmable(occupants_of(self._base_id, self._store))

    def _seed_from_occupant(self, occupant: LcsOccupant) -> None:
        self._select_device(occupant.device, seed_mode_from=occupant.state, mode=occupant.mode)

    def _seed_sensor_track_action(self) -> None:
        """
        Pre-fill the Action Command from the Sensor Track's own IRDA state.

        The panel is handed the accessory-scope proxy, which does not carry the
        sequence; the value lives on the IRDA-scope state at the same address.
        """
        if self._device is not SENSOR_TRACK:
            return
        state = self._irda_state(self._base_id)
        sequence = getattr(state, "sequence", None) if state is not None else None
        if sequence is not None:
            self._options["action"] = sequence

    def _irda_state(self, tmcc_id: int) -> Any:
        store = self._store
        get_state = getattr(store, "get_state", None) if store is not None else None
        if get_state is None:
            return None
        try:
            return get_state(CommandScope.IRDA, tmcc_id, False)
        except Exception:  # pragma: no cover - store shapes vary
            return None

    def _reset_readback(self) -> None:
        self._stop_readback_watcher()
        self._sent_program = None
        self._readback_pending = False
        for line in (self._requested_line, self._reported_line):
            if line is not None:
                line.value = ""

    #
    # Device selection
    #
    def _on_device_selected(self, value: str = None) -> None:
        if self._suspend_device_selector:
            return
        if value is None and self._device_group is not None:
            value = self._device_group.value
        if not value:
            return
        try:
            device = device_for_key(str(value))
        except ValueError:
            log.debug("Unknown LCS device key: %s", value)
            return
        self._device_chosen = True
        if device is self._device:
            return
        self._select_device(device)
        self._seed_sensor_track_action()
        self._refresh_id_page()

    def _on_mode_selected(self, value: str = None) -> None:
        if self._device is None:
            return
        if value is None and self._mode_group is not None:
            value = self._mode_group.value
        if not value:
            return
        try:
            mode = self._device.mode(str(value))
        except ValueError:
            log.debug("Unknown %s mode: %s", self._device.label, value)
            return
        # Deliberate, so a late synchronization must not seed over it.
        self._device_chosen = True
        self._mode = mode
        # A narrower mode can raise the ceiling; a wider one can lower it below the ID in hand.
        self._set_base_id(self._base_id)

    def _refresh_device_selector(self) -> None:
        if self._device_group is None:
            return
        self._suspend_device_selector = True
        try:
            self._device_group.value = self._device.key if self._device else None
        finally:
            self._suspend_device_selector = False

    #
    # Base TMCC ID
    #
    def _set_base_id(self, value: Any) -> int:
        """
        Clamp ``value`` into ``1 .. max_base`` and refresh everything that depends on it.
        """
        try:
            new_id = int(value)
        except (TypeError, ValueError):
            new_id = self._base_id
        new_id = max(MIN_TMCC_ID, min(new_id, self.max_base))
        if new_id != self._base_id:
            self._configure_as_new_id = None
        self._base_id = new_id
        self._refresh_id_page()
        return self._base_id

    def step_up(self) -> None:
        self._set_base_id(self._base_id + 1)

    def step_down(self) -> None:
        self._set_base_id(self._base_id - 1)

    def _on_id_committed(self, field: EditableText, new_value: Any, _old_value: Any = None) -> None:
        text = str(new_value).strip() if new_value is not None else ""
        if text.isdigit():
            self._set_base_id(int(text))
        else:
            # Empty or non-numeric text leaves the ID it had; the field is redrawn from it.
            self._refresh_id_field()
        _ = field

    def _refresh_id_field(self) -> None:
        if self._id_field is not None:
            self._id_field.value = f"{self._base_id}"

    def _refresh_id_heading(self) -> None:
        """
        Name the selected module in the heading, and in the editor's own header with it.
        """
        heading = self.id_heading_text
        if self._id_heading is not None:
            self._id_heading.value = heading
        if self._id_field is not None:
            # A compact editor is centered over the panel, covering the heading, so it
            # repeats the field's name in its own header.
            self._id_field.field_name = heading

    #
    # ID page refresh
    #
    def _refresh_id_page(self) -> None:
        self._refresh_id_heading()
        self._refresh_id_field()
        self._refresh_mode_selector()
        self._refresh_block_line()
        self._refresh_mode_footnote()
        self._refresh_step_keys()
        self._refresh_occupancy()
        # Last, and after everything that shows or hides one of the titled boxes or changes
        # what is inside them: guizero drops the stretch that keeps them the same width
        # every time it re-displays them.
        self._lay_out_titled_boxes()
        self._refresh_options_page()
        self._refresh_review_page()

    def _refresh_mode_selector(self) -> None:
        if self._mode_group is None:
            return
        options = self.mode_options()
        self._mode_group.clear()
        for label, key in options:
            self._mode_group.append([label, key])
        self._mode_group.value = self._mode.key if self._mode else None
        # The titled box goes with the group it labels: a bare "Mode" frame with nothing in
        # it would be left behind for a device that declares no modes.
        container = self._mode_box if self._mode_box is not None else self._mode_group
        if options:
            container.show()
        else:
            container.hide()

    @property
    def block_text(self) -> str:
        """The TMCC IDs the chosen mode claims: "Uses TMCC IDs 12 - 19".

        The count is not spelled out again -- the mode label above already says how many
        TMCC IDs the mode uses, and the range says it a second time.
        """
        if self._mode is None:
            return ""
        ports = self.ports
        if ports <= 1:
            return f"Uses TMCC ID {self._base_id}"
        return f"Uses TMCC IDs {self._base_id} - {self._base_id + ports - 1}"

    def _refresh_block_line(self) -> None:
        if self._block_line is not None:
            self._block_line.value = self.block_text

    @property
    def mode_footnote(self) -> str:
        """What each remote key the selected module offers is used for, one line each.

        Taken from the module's own enabled modes, in the order the radios list them, so
        a BPC2 reads TR before ACC and an STM2 says nothing about accessories.
        """
        if self._device is None:
            return ""
        lines: list[str] = []
        for mode in enabled_modes(self._device):
            use = SCOPE_USE.get(mode.scope)
            if use and use not in lines:
                lines.append(use)
        return "\n".join(lines)

    def _refresh_mode_footnote(self) -> None:
        if self._mode_footnote_line is not None:
            self._mode_footnote_line.value = self.mode_footnote

    def _refresh_step_keys(self) -> None:
        if self._minus_btn is not None:
            self._enable(self._minus_btn, self._base_id > MIN_TMCC_ID)
        if self._plus_btn is not None:
            self._enable(self._plus_btn, self._base_id < self.max_base)

    @staticmethod
    def _enable(widget: Any, enabled: bool) -> None:
        if enabled:
            widget.enable()
        else:
            widget.disable()

    #
    # Occupancy
    #
    def _refresh_occupancy(self) -> None:
        self._refresh_row_grid(self._assigned_grid, self._assigned_cells, self.assigned_rows())
        self._refresh_overlaps()
        # The buttons act on a module the panel could actually take over, so an AMC2 -- in
        # the registry to be named, not to be programmed -- never puts them on screen.
        occupant = self.programmable_occupant()
        interior = occupant is not None and occupant.base_id != self._base_id
        if self._goto_btn is not None:
            if interior:
                self._goto_btn.text = f"Go to {occupant.base_id}"
                self._goto_btn.show()
            else:
                self._goto_btn.hide()
        if self._new_btn is not None:
            if interior:
                self._new_btn.text = f"Configure {self._base_id} as new"
                self._new_btn.show()
            else:
                self._new_btn.hide()

    def _refresh_overlaps(self) -> None:
        """
        Fill the Overlaps box, and take it off the page when nothing is in the way.

        The box goes with its rows, exactly as the mode box goes with its radios: a titled
        frame standing empty says the panel failed to look, when in fact the answer is that
        the block is clear.
        """
        rows = self.overlap_rows()
        self._refresh_row_grid(self._overlap_grid, self._overlap_cells, rows)
        if self._overlap_box is not None:
            if rows:
                self._overlap_box.show()
            else:
                self._overlap_box.hide()

    def _refresh_row_grid(self, grid: Box | None, cells: list[tuple[Text, ...]], rows: Sequence[ModuleRow]) -> None:
        """
        Write ``rows`` into one of the module grids, growing it and hiding what is spare.
        """
        if grid is None:
            return
        for index, row in enumerate(rows):
            for cell, value in zip(self._grid_row(grid, cells, index), row.cells):
                cell.value = value
                if not cell.visible:
                    cell.show()
        # Rows left over from a busier ID are hidden rather than blanked: an empty label
        # still stands a line tall, so the box would keep the height of the fullest ID it
        # had ever shown.
        for spare in cells[len(rows) :]:
            for cell in spare:
                if cell.visible:
                    cell.hide()

    def _grid_row(self, grid: Box, cells: list[tuple[Text, ...]], index: int) -> tuple[Text, ...]:
        """
        The three cells of one module row, created the first time the row is used.

        Rows are grown on demand and then kept: how many modules answer to an ID changes
        as the ID does, and a widget destroyed and recreated in a grid takes the column
        options of its neighbors with it.
        """
        while len(cells) <= index:
            row = len(cells)
            # Only the remote key is bold; it is the column the eye runs down.
            cells.append(tuple(self._grid_cell(grid, column, row) for column in range(ROW_COLUMNS)))
        return cells[index]

    def _grid_cell(self, grid: Box, column: int, row: int) -> Text:
        cell = Text(grid, text="", grid=[column, row], align="left")
        # The size of the box titles above them: these rows are the answer the operator
        # came to the page for, not a caption on it.
        cell.text_size = self._gui.s_14
        cell.text_bold = column == 0
        try:
            cell.tk.config(padx=ASSIGNED_CELL_PAD)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        return cell

    def assigned_occupants(self) -> list[LcsOccupant]:
        """
        Every module answering to the entered ID on the key being programmed.

        Only modules answering to the same remote key as the mode being programmed can
        own the ID: an STM2 is always a switch, so a BPC2 holding ACC 1 does not stand
        in the way of an STM2 based at SW 1, and reporting it would read as a conflict
        where there is none. Before a mode is chosen there is no key yet, and the
        unfiltered answer is the honest one.

        All of them, not just the first: an AMC2 and a BPC2 can both answer to ACC 1, and
        naming one of them would tell the operator half the truth about the address.
        """
        return occupants_of(self._base_id, self._store, scope=self.scope)

    def programmable_occupant(self) -> LcsOccupant | None:
        """
        The module at the entered ID the panel could seed itself from, if there is one.
        """
        return self._first_programmable(self.assigned_occupants())

    @staticmethod
    def _first_programmable(occupants: Sequence[LcsOccupant]) -> LcsOccupant | None:
        """
        The first module in the list this pass knows how to program.

        A module the registry only recognizes -- the AMC2 -- has no modes and no presses,
        so seeding the panel from it would leave the operator on a device that cannot be
        configured. It is named in the box and otherwise passed over.
        """
        for occupant in occupants:
            if occupant.device.configurable:
                return occupant
        return None

    def assigned_rows(self) -> list[ModuleRow]:
        """
        What the Currently Assigned box says: one row per module, or a single "Unassigned".

        A module is named the same way whether the entered ID is its base or one of its
        interior ports: the box reports what is out on the layout, and the range already
        says that the ID falls inside it. Which port it is exactly changes nothing the
        operator can act on -- the two buttons below the box are where the decision is
        made, and they name the base ID themselves.
        """
        occupants = self.assigned_occupants()
        if not occupants:
            return [ModuleRow(scope="", module=UNASSIGNED)]
        return [self._module_row(occupant) for occupant in occupants]

    @classmethod
    def _module_row(cls, occupant: LcsOccupant) -> ModuleRow:
        scope, module, ids = cls._occupant_parts(occupant)
        return ModuleRow(scope=f"{scope}:" if scope else "", module=module, ids=ids)

    @staticmethod
    def _occupant_parts(occupant: LcsOccupant) -> tuple[str, str, str]:
        """A module as the panel names it: "ACC", "BPC2", "TMCC IDs 12 - 19".

        Named the way the operator would program it, and in the order they would do it in:
        the remote key first, because that is the first button pressed and the thing that
        decides whether the module is in the way at all, then the module, then the TMCC IDs
        it holds. The port count is not spelled out separately -- the range already says it.
        """
        scope = occupant.effective_scope
        scope_label = SCOPE_LABEL.get(scope, scope.title if scope is not None else "")
        if occupant.last_id > occupant.base_id:
            ids = f"TMCC IDs {occupant.base_id} - {occupant.last_id}"
        else:
            ids = f"TMCC ID {occupant.base_id}"
        return scope_label, occupant.device.label, ids

    def overlap_occupants(self) -> list[LcsOccupant]:
        """
        The modules the chosen block runs into, base first.

        Scoped like :meth:`assigned_occupants`, because two blocks in different key namespaces
        cannot collide however far they run into one another: an STM2 claiming SW 20-35
        overlaps an ASC2 based at SW 25, and nothing at all on the accessory keys.
        """
        if self._mode is None:
            return []
        return [
            occupant
            for occupant in overlaps(
                self._base_id,
                self.ports,
                self._store,
                ignore_base=self._base_id,
                scope=self._mode.scope,
            )
            if occupant.base_id != self._base_id
        ]

    def overlap_rows(self) -> list[ModuleRow]:
        """
        What the Overlaps box says: one row per module in the way, or nothing at all.

        Named exactly as the assigned box names a module, and gridded into the same three
        columns, so the two boxes read as one list of what is out there. The word
        "Overlaps" is the box's title rather than a prefix on the first row.
        """
        return [self._module_row(occupant) for occupant in self.overlap_occupants()]

    def go_to_owning_base(self) -> None:
        """
        Retarget the panel at the module that owns the entered ID, pre-filled from it.

        Scoped like :meth:`assigned_occupants`, so the button always goes to a module the
        assigned box named and never to some other one on a different remote key -- and to
        one this pass can actually program, since the point of going there is to change it.
        """
        occupant = self.programmable_occupant()
        if occupant is None:
            return
        # Deliberate, so a late synchronization must not seed over it.
        self._device_chosen = True
        self._seed_from_occupant(occupant)
        self._configure_as_new_id = None
        self._base_id = occupant.base_id
        self._seed_sensor_track_action()
        self._refresh_device_selector()
        self._refresh_id_page()

    def configure_as_new(self) -> None:
        """
        Keep the entered ID and treat it as the base of a new module.
        """
        # Deliberate, so a late synchronization must not seed over it.
        self._device_chosen = True
        self._configure_as_new_id = self._base_id
        if self._goto_btn is not None:
            self._goto_btn.hide()
        if self._new_btn is not None:
            self._new_btn.hide()

    @property
    def is_configure_as_new(self) -> bool:
        return self._configure_as_new_id == self._base_id

    #
    # Page navigation
    #
    @property
    def has_close(self) -> bool:
        """Whether the popup adds its Close button below the panel's Back/Next row.

        Only where the panel is the only way off itself; see :func:`needs_close_button`.
        Read by ``create_popup`` as the overlay is built, which is the one moment it is
        needed: an overlay is built on the machine it is shown on.
        """
        return needs_close_button()

    def _build_nav(self, body: Box) -> None:
        """Back and Next, on a row of the panel's own rather than in the popup's footer.

        ``has_footer`` is left False, so where ``create_popup`` adds a Close button at all
        (see :meth:`has_close`) it goes below everything the panel builds -- which puts
        Close on a line of its own, under these two, instead of all three crowding one row.
        Where it does not, these two are the last row in the overlay and nothing moves.

        The row is packed, not gridded, and asks for no width of its own, so Tk centers it
        under the page above; Close below it is centered the same way. Its width does not
        change between pages, because the slot stands in for Back while Back is hidden.

        Styled with ``style_footer_button`` all the same: that is the one shared look for
        the big buttons at the foot of an overlay, and the Close beneath them wears it too.
        """
        host = self._gui
        self._nav = nav = Box(body, align="top", border=0)
        self._back_btn = back = HoldButton(nav, text="Back", align="left", width=8, command=self.previous_page)
        style_footer_button(host, back)
        host.cache(back)
        # Holds Back's place while it is hidden, so Next never moves between pages.
        self._back_slot = self._button_slot(nav, back)
        self._next_btn = nxt = HoldButton(nav, text="Next", align="left", width=8, command=self.next_page)
        style_footer_button(host, nxt)
        host.cache(nxt)
        self._refresh_nav()

    def _button_slot(self, parent: Box, button: HoldButton) -> Box:
        """An empty Box exactly as wide as ``button``'s slot in the row, created hidden.

        Measured rather than guessed: a styled width=8 footer button requests 184x52 while
        an identically padded Label of the same width requests only 156x48, so a label
        stand-in would let Next drift 28 px. An empty frame is also genuinely invisible on
        Aqua, where a tk.Button background is not dependable.
        """
        pad = FOOTER_BUTTON_PAD_COMPACT if self.compact else FOOTER_BUTTON_PAD
        try:
            button.tk.update_idletasks()
            width = int(button.tk.winfo_reqwidth()) + 2 * pad
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            width = FOOTER_SLOT_FALLBACK + 2 * pad
        slot = Box(parent, align="left", width=width, height=1)
        try:
            slot.tk.pack_propagate(False)
        except (AttributeError, RuntimeError, TclError):
            pass
        slot.hide()
        return slot

    def _refresh_nav(self) -> None:
        self._show_back(self._page_index > 0)
        if self._next_btn is not None:
            can_advance = self._page_index < len(self._pages) - 1 and self._device is not None
            self._enable(self._next_btn, can_advance)

    def _show_back(self, visible: bool) -> None:
        """Back is meaningless on the first page, so it is hidden rather than greyed.

        Its slot stays behind: _back_slot is an empty Box of Back's own requested width,
        shown exactly when Back is not, so Next keeps the same x on every page. Both hide()
        and show() run the row's display_widgets(), which rebuilds pack options from
        scratch and discards the padding style_footer_button recorded, so it is replayed.
        """
        if self._back_btn is not None:
            if visible:
                self._back_btn.show()
                self._enable(self._back_btn, True)
            else:
                self._back_btn.hide()
        if self._back_slot is not None:
            if visible:
                self._back_slot.hide()
            else:
                self._back_slot.show()
        if self._nav is not None:
            restore_footer_packing(self._nav)
