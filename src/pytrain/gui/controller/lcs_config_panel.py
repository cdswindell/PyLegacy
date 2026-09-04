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
presses and reads the module back over PDI. The options page is stepped over for a module
that declares none; see LcsConfigPanel.skip_options.

The panel takes every fact about a device from lcs_device_registry.py, every fact about
who owns a TMCC ID from lcs_id_map.py, and the presses themselves from
lcs_sequence_builder.py, so it holds no device knowledge of its own.

Configure sends presses only; nothing is written over PDI CONFIG SET. The read-back
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
    AMC2,
    BPC2,
    SENSOR_TRACK,
    configurable_devices,
    device_for_key,
    device_for_state,
    enabled_modes,
    programmed_options,
    reported_mode,
    tmcc_id_span,
    tmcc_id_text,
)
from .lcs_id_map import LcsOccupant, TrainOccupant, occupants, occupants_of, overlaps, train_overlaps, trains_of
from .lcs_sequence_builder import LcsProgram, build_program
from .overlay_panel import OverlayPanel
from .popup_manager import (
    repad_footer_button,
    restore_footer_packing,
    style_footer_button,
)
from ..components.checkbox_group import CheckBoxGroup
from ..components.editable_text import EditableText, EditorType
from ..components.hold_button import HoldButton
from ..components.scroll_box import ScrollBox
from ...db.state_watcher import StateWatcher
from ...protocol.constants import CommandScope
from ...utils.host_info import is_linux, is_steam_deck

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

log = logging.getLogger(__name__)

LCS_PANEL_TITLE = "LCS Module Configuration"

PAGE_DEVICE = 0
PAGE_ID = 1
PAGE_OPTIONS = 2
PAGE_REVIEW = 3
# The listing of every module the layout has reported, which is not a step of the march the
# other four make: nothing is chosen on it and nothing follows from it. It is built and
# shown by index like the rest -- a page outside the list of pages would need its own
# showing, its own fitting and its own place in the window -- and kept off the march by
# _skipped, so Next never arrives at it and Back leaves it for the page it was opened from.
PAGE_INVENTORY = 4

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

# The label on the box around what the chosen block runs into. A box of its own, directly
# under the one above, because it answers a different question: that one says what holds
# the entered ID, this one what the whole block would collide with. The title carries the
# word "Overlaps", so no row inside has to repeat it.
OVERLAP_TITLE = "Overlaps"

# What the rows in those two boxes are drawn in. Every row either box can show is something
# standing in the way of the address being entered -- a module that already answers to it,
# one the chosen block would run into, or a train numbered in the block a TR mode would take
# -- so the rows are colored as the warning they are, and the operator can see there is one
# without reading the box titles.
# The single exception is the row the assigned box shows for an address nobody holds, and
# that is the only good news on the page, so it is the only row in green.
#
# Dark rather than plain red and green: these are whole lines of text at the page's body
# size on a light panel, where a bright red reads as a smear and a bright green as a
# highlighter -- and plain "red" is already what admin_panel puts over Restart and
# Shutdown, which is a warning about an irreversible act rather than a report. Hex, as
# color is given everywhere else in the GUI, with Tk's own names for these two shades.
CONFLICT_FG = "#8B0000"  # dark red
UNASSIGNED_FG = "#006400"  # dark green

# And what the verdict on a read-back is written in, which is those same two shades: the
# panel has one green and one red, and whether the module took what it was sent is the
# other thing it has to say in them. Named apart from the rows above all the same, because
# they answer a different question -- an address already spoken for, against a module that
# did not come back holding what it was given -- and either could come to want its own
# shade without dragging the other along.
VERIFIED_FG = UNASSIGNED_FG
UNVERIFIED_FG = CONFLICT_FG

# Breathing room on either side of a module-row cell, so the gridded columns do not run
# into one another. Internal Label padding rather than grid padding, which is discarded
# every time anything in the box is shown, hidden or created.
ASSIGNED_CELL_PAD = 4

# A module row is the remote key, the module and its TMCC IDs, a column each.
ROW_COLUMNS = 3
# Which of the three holds the name, and so the one column whose contents nothing bounds:
# a module's label is the registry's to lengthen, and a train's is its owner's -- a road
# name and number as the base reports them, which can run to a sentence.
ROW_NAME_COLUMN = 1

# What the other two columns can take between them, as a multiple of the cell's own text
# size. Both are bounded: the longest remote key the rows can spell is "ACC:" and the
# longest block the registry can, "TMCC IDs 83 - 90". What is left over is the room the
# name column has, and it needs to be told, because wrapping every cell at the pane's own
# width does not hold a row inside the pane -- three columns each free to take the whole of
# it are three times too wide, which is how a long road name came to run off a Pi.
#
# Measured in the cells' own font at every size they are drawn at, the cell padding
# included: 264px at 18pt on a Pi, 215px at 14pt on the desk, 196px at 13pt on a Deck --
# 14.7, 15.4 and 15.1 times the size, one font at three sizes being why they agree. 16 is a
# shade over the worst of them, so the reservation is never short; being a shade generous
# costs a long name only a break it was going to take anyway.
ROW_FIXED_COLUMNS_EMS = 16

WAITING_FOR_BASE = "Waiting for Base 3..."
NO_RESPONSE = "No response from the module"

# What the panel says while it is checking, and the verdict it comes to. Configure sends
# Cab-remote presses and nothing else -- there is no PDI CONFIG SET anywhere in this pass --
# so what the module now holds is knowable only by asking it, and the answer is worth
# holding against what was sent rather than merely printing: a module that was never put
# into program mode takes none of the sequence and says so by reporting what it held all
# along, which reads like success to anyone not comparing the two.
VERIFYING = "Polling the {module} to verify its configuration matches what was sent..."
VERIFIED = "Success"
UNVERIFIED = "Unsuccessful"

# What follows that word on a line that failed: what is wrong, and what to do about it.
# Named rather than said in one sentence because the two reasons are different facts -- the
# module answered and disagrees, or it did not answer at all -- while the remedy is the same
# either way, and is the likeliest thing to have gone wrong: the sequence is only taken by a
# module standing in program mode, and the button that puts it there is on the module.
NOT_REPORTED = "no configuration reported"
NOT_AS_SENT = "not set as sent: {items}"
VERIFY_RETRY = "Hold the {module}'s {button} button and try again."
UNVERIFIED_LINE = "{verdict} - {reason}. {retry}"

# And what the line is written in while the panel is still asking, which is neither of the
# two verdict shades: a line already colored as an answer, before there is an answer, is one
# the operator reads as an answer. Stated rather than left to the widget's own default,
# because this one line is recolored and has to be able to get back.
VERIFYING_FG = "black"

# The heading each page opens with, and the three keys the operator presses. Named here
# with everything else the panel says rather than left inline where they are built: the
# wording of a page is a fact about the panel, not about the widget that happens to carry
# it, and naming it is what lets the tests read it instead of repeating it.
DEVICE_PROMPT = "Which module are you configuring?"
OPTIONS_TITLE = "Options"
REVIEW_TITLE = "Review and Configure"
BACK_TEXT = "Back"
NEXT_TEXT = "Next"
CONFIGURE_TEXT = "Configure"

# And the title of the box the presses stand in on the review page. What is listed under it
# is the sequence itself, key by key in the order it goes out -- which is the sequence an
# operator would work through on a Cab remote by hand if the panel were not there to send
# it, and the one they will work through if a press is missed. In a frame with a title on
# it, because a numbered list standing bare on a page says nothing about whose steps it is
# reporting; the frame also gives the list a left edge to be read from. See
# LcsConfigPanel._build_manual_config_box.
MANUAL_CONFIG_TITLE = "Manual Configuration"

# The key that opens the listing, on the device page, and the heading the listing opens
# with. The button says what it shows rather than what it does -- there is no verb an
# operator wants here -- and it says "My", which is the operator's own word for the modules
# on the layout in front of them: what is listed is what has reported itself on their bus.
# The heading is the same claim spelled out, the page being read on its own.
INVENTORY_TEXT = "My Modules"
INVENTORY_TITLE = "My LCS Modules"
# What the page says when nothing has reported itself, which is the ordinary state of a
# panel opened before the Base 3 has been heard from. Said rather than left as an empty
# grid under its own headings, which reads as a page that failed to look.
INVENTORY_EMPTY = "No LCS modules have reported themselves yet."

# The listing's columns, in the order they are read: which module it is, the TMCC ID it is
# based at, the remote key that addresses it, and everything else it says about itself.
# "ID" rather than "TMCC ID": every number on this page is a TMCC ID, and the column beside
# it spells the block out in full.
INVENTORY_HEADINGS: tuple[str, ...] = ("Module", "ID", "Scope", "Configuration")
INVENTORY_COLUMNS = len(INVENTORY_HEADINGS)
# Which column holds the configuration, and so the one column with no bound on what it can
# say: it runs to as many lines as the module has facts about itself. The three before it
# are each a word or two -- and the widest thing in each of them is that column's own
# heading, bar an ID column of two digits -- so they are the reservation the last column's
# wrap is taken from, exactly as ROW_FIXED_COLUMNS_EMS is taken for the module rows.
#
# Measured in the cells' own font at 12pt, 13 and 14, the cell padding included: 151px,
# 158px and 173px, which is 12.6, 12.2 and 12.4 times the size, one font at three sizes
# being why they agree. 13 is a shade over the worst of them. The listing is drawn at the
# page's body size wherever it is drawn -- 14 on the Pi and the desk, 13 on a Deck, and 12
# on none of them since it stopped following the titled boxes down; see
# LcsConfigPanel._inventory_text_size.
#
# A shade, where this reservation was several ems over before it was measured, because what
# too large a reservation costs here is not the break a long line was going to take anyway:
# the grid is centered in the page, so every em held back from the last column is width the
# rows do not take and the margins do. At 20 -- the module rows' 16, and a few more for the
# column those rows do not have -- the configuration column broke at 192px of a 432px page
# at 12pt: a module's Yes stood on a line of its own with 54px of nothing down either side
# of the listing. A screen whose font runs wider than the one measured here is a few pixels
# over rather than a column short, and what those come out of is WRAP_INSET, the page's own
# margin, which is kept outside this arithmetic.
INVENTORY_CONFIG_COLUMN = INVENTORY_COLUMNS - 1
INVENTORY_FIXED_COLUMNS_EMS = 13
# How a cell sits in its column: against the top of the row and against its left edge, which
# is Tk's own spelling of the two. Every row is as tall as its configuration column, that
# being the one column with several lines in it, and a cell left to what guizero grids it
# with -- sticky="W", from its align -- is centered against that height: "BPC2" floats
# halfway down a five-line row instead of standing beside the first line of what the module
# is set to. The three bounded columns are the reason this matters and the reason it is the
# whole grid: they are read down the page, so they have to start level with each other.
# Replayed after every re-order rather than set where a cell is built; see
# _stick_inventory_cells.
INVENTORY_STICKY = "nw"

# What the listing calls a module, where that is not the name the registry gives it. Only
# the IR Sensor Track, which is listed as the IR: the Module column is a column of short
# names -- ASC2, BPC2, STM2 -- read down the page rather than sentences read across it, and
# "IR" is what tells this module from those at a glance. Keyed by the registry's key rather
# than by its label, so the listing's name cannot come adrift from a re-worded label.
#
# This page alone. Everywhere else the panel names a module it is programming -- the device
# rows, the ID page's reports, the options heading, the presses on the review page -- and
# there it is named as the registry names it. See _inventory_module.
INVENTORY_MODULE_NAMES: dict[str, str] = {SENSOR_TRACK.key: "IR"}

# And what it calls a setting, where that is not the name the options page gives it. Both
# entries are the same flag under two modules' names -- the BPC2's "Restore last relay
# settings on power-up" and each of the AMC2's "Remember speed on power-up". Each is a
# sentence written to be read beside the box that decides it, with the width of an options
# row to say it in; wrapped at this column's width each takes two lines of the tallest
# column in the panel -- 374px and 305px at 14pt against a column of 250, 337 and 275 at
# 13pt against 263 -- on every such module the layout holds.
#
# Worded as the line an operator reads rather than as the question they were asked to
# answer: it says when the module restores and leaves what it restores to the module named
# two columns over, which is how one name can serve a BPC2's relays and an AMC2's motors
# alike. And short enough to hold its own Yes or No beside it on one line at either size --
# 221px and 199 against those same columns -- which is the whole point of a flag in a column
# read down the page.
#
# Keyed by the module's key and the setting's, neither of which is wording, so the short
# name cannot come adrift from a re-worded label -- and asked of the registry rather than
# spelled out here, so a key that is renamed or dropped is a failure at import rather than
# a long sentence quietly back in the column.
#
# This page alone. The options page draws each setting as its own label, where the operator
# is being asked to decide something rather than reminded what a module is set to, and the
# presses on the review page name it as that page does. See _inventory_option_name.
INVENTORY_RESTORE = "Restore on power-up"
INVENTORY_OPTION_NAMES: dict[tuple[str, str], str] = {
    (BPC2.key, BPC2.option("restore").key): INVENTORY_RESTORE,
    (AMC2.key, AMC2.option("motor1_restore").key): INVENTORY_RESTORE,
    (AMC2.key, AMC2.option("motor2_restore").key): INVENTORY_RESTORE,
}

# How the listing can be ordered, and the order it opens in. By module first, so the page
# reads as a tally of what kinds of module are out there; by ID for an operator looking for
# a free address; by remote key for one thinking in terms of the key they are about to
# press. Each row is [label, key], as a CheckBoxGroup takes its options -- the same shape
# the catalog panel's own Sort By rows have.
SORT_MODULE = "module"
SORT_ID = "id"
SORT_SCOPE = "scope"
INVENTORY_SORTS: tuple[tuple[str, str], ...] = (
    ("Module", SORT_MODULE),
    ("ID", SORT_ID),
    ("Scope", SORT_SCOPE),
)
INVENTORY_SORT_TITLE = "Sort By"
# Whitespace either side of a sort row's label, in pixels. The three stand on one line, so
# what holds them apart is their own padding rather than the gap between rows.
SORT_ROW_PAD = 10

# The lines the configuration column is written from. The mode as the registry names it,
# then the block of addresses the module holds on the key it answers to -- "ACC 1 - 8", the
# spelling the ID page's own summary uses -- then a line per setting the module reports.
# A module that has not said which mode it is in says so, rather than being written up as
# though the panel knew: a module known from control traffic alone reports no mode byte.
#
# What the module is set to, and nothing else it happens to report. Its firmware is a fact
# about the module rather than about its configuration, and this is the column an operator
# reads to see how their layout is addressed -- a version number down every row is a line
# per module that answers no question the page is open for. Nor anything the three columns
# beside it have already said; see inventory_config.
INVENTORY_MODE_UNKNOWN = "Mode not reported"
INVENTORY_SETTING = "{name}: {value}"
# What stands between one group of a module's settings and the next: an empty line in the
# text, and a few pixels of white space on the page. The AMC2 is the module with groups --
# a mode and a remember flag for each of its two motors -- and without a break the four
# read as one block of four rather than as two motors, the second motor's heading being
# just another line of the same column. See _inventory_settings.
#
# The empty line is notation and is never drawn. A cell of wrapped text has no white space
# but its own lines, and one line of this column costs the row the whole of a line's
# height -- 23px at the size the listing is drawn at, 20 on a Deck, Tk laying every line of
# a label out at the one font's height. So the listing goes on writing one string per
# module, with an empty line marking where a group ends, and the cell holds the blocks that
# line separates apart by INVENTORY_GROUP_GAP_PX of real padding instead; see GroupedCell.
#
# 6px is a quarter of a line at 14pt and a little under a third at 13: enough to see the
# second motor begin, and no more. What stands between one module and the next is nothing
# at all -- the bold name in the Module column is what tells them apart -- so a group given
# a line's worth reads as further from its own module than the module is from its
# neighbors, which is the very thing a full line was found to do.
INVENTORY_GROUP_GAP = ""
INVENTORY_GROUP_BREAK = f"\n{INVENTORY_GROUP_GAP}\n"
INVENTORY_GROUP_GAP_PX = 6
# What a flag reads as. Yes and No rather than the label's own wording, because the name of
# the setting is already the other half of the line.
INVENTORY_YES = "Yes"
INVENTORY_NO = "No"

# The lines the panel composes about the module in hand, as templates. Every term in them
# comes from the registry -- the module's label, the mode's counted label, the remote key
# -- so all that is written here is the sentence that holds them.
PROGRAM_MODE_NOTE = "Be sure your {module} is in Program mode."

# What the options page is about to do, at the head of it: "BPC2: Configuring as ACC 1 - 8".
# The addresses themselves rather than a count of them, because the block was chosen on the
# page before this one and this line is what says which addresses that choice landed on --
# a count leaves the operator to add it to a base ID themselves. See tmcc_id_span.
CONFIGURING = "{module}: Configuring as {block}"

# And what was programmed, once the presses have gone out: the module, the mode with the
# count of addresses it claims, and the address itself. Counted here rather than spanned,
# because this line is the record of a sequence that was sent -- it stands beside the
# module's own read-back below it, which reports a count too. See REPORTED.
SUMMARY = "{module} - {mode} at {scope} {id}"
REQUESTED = "Requested: {summary}"

# And what the module answered with, in the same order: a comma-separated list, because
# what a module reports varies with the module -- a Sensor Track adds its Action Command
# and its two engine ID filters. The count says plain "IDs" where the registry's own
# labels always say "TMCC IDs": this line is a read-back of a PDI field rather than a
# block being offered, and it sits beside the address it was read from.
REPORTED = "Reported: {summary}"
REPORTED_AT = "{module} at {id}"
REPORTED_IDS = "{count} IDs"

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

# And what the two gaps on the ID page itself are worth -- the one under the address and the
# one under the last titled box. Half of PAGE_GAP, because that page is the fullest in the
# panel by a long way and those two were the widest whitespace on it, while being the two
# least needed: what stands either side of them says where one section ends and the next
# begins without any help. Under the address there is a box drawn like a text field above and
# a titled frame below; under the last box there is that frame's own edge above and a row of
# buttons below.
#
# Worth 24px of the Pi's tallest page between them, which is 24px of it the window does not
# have to hold back; see _fit_scroll for what happens to the rest.
ID_PAGE_GAP = 8
ID_PAGE_GAP_COMPACT = 4

# And the white space under the review page's own heading, which stood flush against the
# instruction below it: half a line of it, that being what the page was asked for and what
# it wants -- the instruction is the first thing to do rather than the next thing on the
# page, so it belongs to the heading above it, and a full line's worth reads as a hole
# between the two.
#
# Measured in the heading's own font: a line at the size the headings are drawn (s_16) is
# 25px, so half of one is 12px. Which lands between the panel's two other gaps rather than
# on either -- wider than the one a heading takes above a prompt, narrower than the one
# between a page's sections -- and the compact pane takes half of it, as it takes half of
# both of those. See SECTION_GAP and PAGE_GAP.
REVIEW_HEADING_GAP = 12
REVIEW_HEADING_GAP_COMPACT = 6

# Whitespace between the Currently Assigned, Overlaps and Mode boxes, in pixels. Grid
# padding rather than a spacer widget, which is safe here for the one reason it is not
# safe elsewhere: _lay_out_titled_boxes already has to re-apply these boxes' grid options
# after every refresh, so the padding is replayed along with the stretch. Applied below
# each box, the last one included, which is whitespace the block line below wants anyway.
BOX_GAP = 8
BOX_GAP_COMPACT = 4

# Whitespace above and below the label in a radio row, in pixels -- which is what sets the
# gap between one radio and the next. Internal Checkbutton padding rather than grid padding,
# for the reason given above ASSIGNED_CELL_PAD: guizero rebuilds a container's grid options
# from scratch whenever anything in it is created, shown or hidden, and pady is not among
# the options it replays. CheckBoxGroup's own default of 6 read as one solid block of radios
# on the Pi, where the rows are the thing being aimed at with a finger.
RADIO_ROW_PAD = 12
RADIO_ROW_PAD_COMPACT = 6

# The mode radios get less of it, and not for want of asking. The ID page is by far the
# fullest of the four -- a heading, the stepper row, three titled boxes, two derived lines,
# two choice buttons and the Back/Next row -- and its rows are the tallest in the panel to
# begin with, since they are set a size above the page body and their painted indicator
# grows with it: 23px against the module rows' 18. The device page has nothing below its
# radios and can spend twice this; here the whitespace has to come out of the one page that
# has none to give, and the button below it all is the only way off the panel on the Pi.
MODE_ROW_PAD = 6
MODE_ROW_PAD_COMPACT = 3

# Whitespace between the mode radios and the prose either side of them, in pixels: above
# the list stands the legend naming what each remote key is for, below it the chosen mode's
# own note. Small on purpose, and smaller than the gap between two radios, so both read as
# part of the Mode box rather than as the next thing on the page -- and the same above as
# below, so the rows read as one block held between the two. Spacer widgets rather than
# padding of the lines' own, which would push them off the box's edges as well.
MODE_PROSE_GAP = 4
MODE_PROSE_GAP_COMPACT = 2

# Whitespace above the first mode radio of a new remote key, in pixels -- the ASC2's two SW
# modes held off its two ACC modes, the BPC2's ACC modes off its TR modes. What is chosen on
# this page is a key and then a mode on that key, so the rows read as two short lists rather
# than one list of four, which is also how the legend above them is written: a line per key.
# Wider than the gap between two rows of the same key, and narrower than the gaps between
# the page's own sections: this divides a list rather than ending it. Grid padding, replayed
# by the group after every rebuild -- see CheckBoxGroup.row_leads.
MODE_KEY_LEAD = 12
MODE_KEY_LEAD_COMPACT = 6

# Pack padding above and below Back and Next, in pixels, replacing the footer button's own
# 20. That 20 is sized to hold a footer row off the panel above it and the pane below; this
# row has the page's own gap above it and, where there is a Close button at all, that
# button's lead and padding below -- so a third helping of it is whitespace stacked on
# whitespace, and on the ID page it is whitespace that pushed Close off the screen.
NAV_ROW_PAD = 6
NAV_ROW_PAD_COMPACT = 4

# Whitespace above and below an option row on the options page. Between MODE_ROW_PAD and
# RADIO_ROW_PAD, and for the same reason those two differ: there is less of a page to spend
# here than the module radios have to themselves, and more than the mode radios can take
# out of the fullest page in the panel. Internal Checkbutton padding, for the reason given
# above RADIO_ROW_PAD.
OPTION_ROW_PAD = 8
OPTION_ROW_PAD_COMPACT = 4

# An options page drawing more rows than this cannot be given any of the whitespace above.
# Counted over the module's settings together rather than over any one of them, because what
# runs out is the page: Tk neither scrolls nor complains when it does -- it stops mapping
# children, and the ones at the end are the Back/Next row and the Close button below it,
# which is the only way off the panel on the Pi.
#
# So a page this full is packed tight, and that is what pays for its rows being set at the
# same size as every other control in the panel. The Sensor Track's ten actions were the
# case this was written for: with OPTION_ROW_PAD on each of them the list wants 160px more
# than the page can find. Measured on a 480x800 pane at the Pi's 1.5x font scale: 49px a
# row, and the page 635px -- exactly what it asked for when the rows were a size smaller
# with the option's note under them, and 44px inside the tallest page the panel then drew
# (the ASC2's ID page, at 679px). Which is the ceiling for the size: the next size up asks
# 645px, more than the page has ever taken, and the one after it 685px, more than the
# ASC2's. What sets one row apart from the next is the painted indicator and the row's own
# background rather than whitespace it cannot afford.
#
# The AMC2 is why the count is the page's. It asks for four settings -- a three-row list and
# a tick box for each of its two motors -- and no one of them is long, so read a list at a
# time every row on the page drew its full padding: eight rows' worth, and the page came to
# 748px on a desk and had 190px of itself held back by the scrolling window on the Pi, the
# most of any page in the panel by 112px. Read as the page it is, it comes to 620px and the
# Pi holds back 62px. The reason the Sensor Track's rows are packed tight is the reason
# these are: there is no more page to spend.
LONG_OPTION_PAGE = 6

# Whitespace above and below a line of prose about the module -- its warning, the modes it
# reserves, an option's own note. Internal Label padding rather than a spacer widget, and
# here that is not only about what guizero replays: every one of these lines is empty for
# most modules and is taken off the page when it is (see _refresh_note), so padding that
# belongs to the label goes away with it where a spacer would be left holding a gap over
# nothing.
NOTE_PAD = 8
NOTE_PAD_COMPACT = 4

# Where a line of prose is broken, in pixels: the width of the popup it is drawn in, less
# its border and a margin either side. Tk truncates nothing -- a label wider than the popup
# is centered in it, losing its beginning *and* its end, which is how the BPC2's relay
# warning read on the Pi -- so the wrap is the only thing that keeps a sentence whole.
#
# The popup is as wide as the emergency box: create_popup builds its title row with that
# width. Pixels rather than characters because that is the unit Tk's -wraplength takes, and
# the only honest one here: the same sentence is half again as wide on a Pi, whose fonts are
# scaled up, as it is on a desk.
WRAP_INSET = 24
# The floor, for a host that has not measured itself yet. Narrower than any pane the GUI
# runs in, so it can only ever break a line early -- never off the edge of the screen.
MIN_WRAP_PX = 240

# How much narrower than the pane the Mode, Currently Assigned and Overlaps boxes are drawn,
# in pixels: a margin either side of the block, and nothing more. The three of them used to
# take the width of whatever was inside them, which on a module whose rows are short left the
# legend heading the Mode box wrapped into a column half the pane wide -- lines of prose
# crammed under a title with the page's whole right-hand side standing empty beside them.
#
# Less than WRAP_INSET on purpose: the prose inside these boxes is broken at the pane's width
# less that inset, so a box drawn to this one is wider than the longest line it can hold, and
# the wrap decides where a sentence breaks rather than the frame around it. A width floor
# rather than a fixed width -- a box whose contents ask for more still gets more; see
# _lay_out_titled_boxes.
TITLED_BOX_INSET = 12

# And how far inside its own frame the review page's Manual Configuration box holds its
# presses, in pixels. That box is not drawn to the inset above -- see
# LcsConfigPanel._manual_config_px for where its frame stands and why -- and this is the
# white space between the frame and the list inside it: the numbers used to begin 2px in,
# which reads as a list pressed up against the ruled edge beside it.
#
# Measured in the presses' own font against the width the box then leaves, on the narrowest
# pane the panel runs in: the widest press a module can list, "2. AUX1 then 1 (Action
# Command)", is 312px at the size these are drawn -- 288 a size below, 353 a size above --
# against 416px, so the margin costs no press a line on any screen. Read back in a live
# window, the numbers now begin 10px inside the frame -- this margin and the frame's own
# 2px -- with the frame itself standing 12px inside either edge of the page.
#
# Internal Label padding rather than grid or pack padding, neither of which guizero replays;
# see _manual_config_wrap_px and _left_line.
MANUAL_CONFIG_PAD = 8

# How wide the bar down the right edge of a scrolling page is drawn, in pixels: one value for
# the Pi and the desk, a wider one for the Deck. See scroll_bar_px() for which screen gets
# which, and ScrollBox for what the bar is.
#
# It is a real scroll bar now -- trough, handle and an arrow head at either end -- and that
# is what raised these figures. 6px was the first attempt and could not be told from the frame
# beside it; 10px read as a bar but not as a control, its arrow heads two specks and its
# trough too narrow to put a thumb on. What is drawn now has parts, and a part too small to
# aim at is a part that may as well be paint. The catalog's own list, whose colors these are,
# draws its bar at 50px -- it has a whole pane to itself, and this has a page to share with.
#
# The Deck's is wider again because a bar takes its room from the page's own width, and a
# 640px pane has a third more of it to give than the Pi's 480px.
#
# Both are what measurement allowed rather than what looked about right, and what they cost is
# width and not words: the page is drawn in the pane less this, so nothing is ever under the
# bar to be covered (see _page_px). Swept across every module, mode, address and page:
#
# * On the Pi, 24px costs nothing at all -- the tallest page is 617px in a 539px window and 18
#   of the 72 pages are held back, exactly as at 10px and no gutter -- while 30px grows the
#   tallest page by 16px, a line that has to be scrolled to. So 24px is the last free width
#   and the one taken; the nearest ink to the edge is then 33px, clearing the bar by 9px.
# * On the Deck nothing overflows at any width up to 44px (tallest page 404px), so 30px is
#   free there and the nearest ink, 48px, clears it by 18px. Its bar is therefore never drawn
#   today: this is the width it would be drawn at on a Deck pane that did overflow.
# * A desk window never overflows either (tallest 460px), and takes the Pi's figure.
SCROLL_BAR_PX = 24
SCROLL_BAR_PX_DECK = 30


# Presses are staggered so the base sees them as separate gestures, and the read-back
# GETs are held off until the module has had a moment to act on the last of them.
PRESS_DELAY = 0.35
VERIFY_DELAY = 1.0
READBACK_TIMEOUT_MSEC = 5000

# And how often the module is asked again while the panel waits out that timeout. Asked
# more than once because a single GET is a single chance: a module put into program mode a
# beat late, or a request lost on the way, is a read-back that never arrives -- and the
# panel now draws a conclusion from that silence rather than merely noting it, so a module
# that took the sequence perfectly well would be reported as having failed. Two small PDI
# requests a second is a cheap way not to be wrong about that.
VERIFY_POLL_DELAY = 1.0

# What the Cab remote calls each scope, which is the language the operator's manual uses.
# The three the panel programs on, and the one it can only read: an AMC2 can be addressed
# as an engine and the registry records that mode, so a module already out on that key is
# named by the listing -- but no row is offered on it, and nothing the panel programs is
# ever written about it. See _select_device on how a mode the panel does not offer is kept
# from becoming the one being programmed, and the listing's Scope column for the one page
# the fourth key can appear on.
SCOPE_LABEL: dict[CommandScope, str] = {
    CommandScope.ACC: "ACC",
    CommandScope.SWITCH: "SW",
    CommandScope.TRAIN: "TR",
    CommandScope.ENGINE: "ENG",
}

# The order the remote keys are listed in, which is the order they are declared above: the
# accessory keys first, being where most of a layout's modules sit, and the engine key last,
# being the one no module is programmed onto. What the listing sorts its Scope column by,
# since neither the keys' spelling nor the scopes' own numbering is an order an operator
# would recognize.
SCOPE_ORDER: tuple[CommandScope, ...] = tuple(SCOPE_LABEL)

# What each of those remote keys is for. Every mode row below opens with one of these keys
# and says nothing about what it is good for, which is the one thing an operator choosing
# between them needs. Each line leads with the key spelled exactly as the rows spell it, so
# the eye can join the two, and the lines stand above the rows they name -- what the keys are
# is read before the list is chosen from, not after. Only the keys the selected module
# actually offers are shown, so the legend never states a fact that does not apply to the
# module in hand. The selected mode's own note answers from below the rows; see
# LcsConfigPanel.mode_note.
#
# Keyed by the remote key *and* the module, because what a key is for is not always a fact
# about the key alone. On most modules TR and ACC are two different jobs -- track power on
# the one, lighting and accessories on the other -- but a BPC2 does the same job either way:
# its manual is explicit that "the features available in both addressing modes are identical,
# choose whichever suits your layout best". So telling a BPC2's operator that ACC is for
# lighting states something untrue about the module in front of them, and what its two keys
# really offer is a choice of which address space to spend. The module half of the key is
# None for the line that speaks wherever a module has not been spoken for; see scope_use().
SCOPE_USE: dict[tuple[CommandScope, str | None], str] = {
    (CommandScope.ACC, None): "ACC: Use for lighting and operating accessories",
    (CommandScope.SWITCH, None): "SW: Use for Switches/Turnouts",
    (CommandScope.TRAIN, None): "TR: Use for track power blocks",
    # The BPC2's two keys, said as the two ways of addressing one module that they are. The
    # module's name and key are taken from the registry rather than spelled here, so the pair
    # cannot come to name a module other than the one they are filed under. Both fit the Pi's
    # legend on one line: 603 px and 576 px of the 690 px a line is broken at there, which is
    # narrower than the accessory line above them already asks for.
    (CommandScope.TRAIN, BPC2.key): f"TR: {BPC2.label} addressed as a TR (track) device",
    (CommandScope.ACC, BPC2.key): f"ACC: {BPC2.label} addressed as an ACC device",
    # The Sensor Track's one key, said as the module the address names rather than as a use:
    # it is addressed as an accessory but is neither lighting nor an operating accessory --
    # it reports what passes over it -- so the general line names a job it does not do. Its
    # name comes from the registry for the same reason the BPC2's does.
    (CommandScope.ACC, SENSOR_TRACK.key): f"ACC: LCS {SENSOR_TRACK.label}",
}


def scope_use(scope: CommandScope, device: LcsDevice | None = None) -> str | None:
    """What the legend says a remote key is for, on the module in hand.

    The module's own line where one is written for it, and the line that speaks for every
    other module otherwise -- so a key that means the same thing everywhere is worded once,
    and only a module the key means something else on has to say so. None for a key nothing
    is written about at all, which the legend passes over rather than heading with a blank
    line; see LcsConfigPanel.mode_legend.
    """
    key = device.key if device is not None else None
    return SCOPE_USE.get((scope, key)) or SCOPE_USE.get((scope, None))


def option_page_rows(device: LcsDevice) -> int:
    """How many rows the module's options page draws, all of its settings together.

    A radio setting is as many rows as it offers choices and a flag is the one row it is,
    which is what the page spends its height on -- the headings and notes between them are
    what is left over. What the count is for is deciding whether there is whitespace to
    spend; see LONG_OPTION_PAGE.

    Every setting is counted, including one this mode does not offer: a disabled row is
    drawn like any other and takes the same height.
    """
    return sum(len(option.choices) if option.kind == OptionKind.RADIO else 1 for option in device.options)


@dataclass(frozen=True)
class ModuleRow:
    """
    One line of the Currently Assigned or Overlaps box: "ACC: BPC2 TMCC IDs 1 - 8".

    Held as separate parts rather than one string because both boxes grid them into
    columns, so that the module names and the ID ranges line up down the box, however,
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

    @property
    def is_unassigned(self) -> bool:
        """Whether this is the row the assigned box shows for an address nobody holds.

        The one row in either box that is not a module in the way, which is what decides
        the color it is drawn in; see UNASSIGNED_FG. Read from the row rather than from
        whether the box has any rows at all, so one method fills the two boxes.
        """
        return self.module == UNASSIGNED


@dataclass(frozen=True)
class InventoryRow:
    """One line of the My Modules listing: "BPC2", "1", "ACC", and what it is set to.

    Held as separate parts for the reason ModuleRow is -- the listing grids them, so the
    columns line up down the page however long the names above them run -- and kept apart
    from that class because the two answer different questions and are not the same shape.
    A module row says what stands in the way of one address, three columns of it; this says
    what a module *is*, and its last column is the module's whole configuration, at whatever
    length that runs to.

    config carries its own line breaks, one per fact the module reports, and an empty line
    where one group of a module's settings ends and the next begins. Nothing else in the
    panel writes a cell of more than one line, and this is the column the page is for: what
    a module is set to cannot be said in a column's width, and saying it on the row keeps it
    beside the module it belongs to rather than in a page of its own. What the empty line
    comes out as on the page is the cell's business rather than the row's; see GroupedCell
    and INVENTORY_GROUP_GAP.
    """

    module: str
    tmcc_id: str
    scope: str
    config: str = ""

    @property
    def cells(self) -> tuple[str, str, str, str]:
        return self.module, self.tmcc_id, self.scope, self.config

    @property
    def text(self) -> str:
        return " ".join(part for part in self.cells if part)


class GroupedCell:
    """The listing's configuration cell: a module's settings as blocks, held apart by a hair.

    Every other cell of either grid is one label, and a label's own lines are the only white
    space it has: an empty line between two groups of a module's settings costs the row a
    whole line of the tallest column in the panel. So this cell is the groups themselves --
    one label each, stacked in a box that stands in the grid where a label would -- and what
    holds them apart is pack padding, which can be as many pixels as it is worth. See
    INVENTORY_GROUP_GAP_PX.

    It answers as a cell of either grid does -- value, visible, show, hide, text_bold,
    text_color, tk -- so the row it belongs to is written, hidden and gridded by the very
    code that writes every other row, and value is the whole of the text, empty line and
    all, exactly as a label's is. The blocks are what that empty line means here, so the
    listing goes on writing one string per module and the page is left to decide what a
    break between groups looks like. See _refresh_inventory and inventory_config.

    The blocks are grown as they are needed and then kept, as the rows of either grid are: a
    module reporting one group more than the module last written into this row is a block
    more to write, and a widget destroyed in a container takes the layout of its neighbors
    with it.
    """

    def __init__(self, box: Box, block: Callable[[Box], Text], gap_px: int) -> None:
        self._box = box
        # How a block is made, rather than what a block is: the labels of both grids are
        # sized, wrapped and padded in one place, and a block of this cell is one of them.
        # See _cell_label.
        self._block = block
        self._gap_px = max(0, int(gap_px))
        self._blocks: list[Text] = []
        self._bold = False
        self._color: Any = None
        self._value = ""

    @property
    def tk(self) -> Any:
        """The box's own widget: what the grid holds, and so what the grid is told about."""
        return self._box.tk

    @property
    def box(self) -> Box:
        """The box the blocks are stacked in, which is the cell as the grid sees it."""
        return self._box

    @property
    def blocks(self) -> tuple[Text, ...]:
        """The labels the cell writes on, in the order they are read, spare ones included."""
        return tuple(self._blocks)

    @property
    def visible(self) -> bool:
        return self._box.visible

    def show(self) -> None:
        self._box.show()

    def hide(self) -> None:
        self._box.hide()

    @property
    def text_bold(self) -> bool:
        return self._bold

    @text_bold.setter
    def text_bold(self, bold: bool) -> None:
        """Bold, or not -- and remembered, because a block may be made after it is asked for.

        The headings row is a cell of this kind too, and its heading is bold in every column;
        a block grown later is grown in the weight the cell was set to rather than in the one
        the label happened to be built with.
        """
        self._bold = bool(bold)
        for block in self._blocks:
            block.text_bold = self._bold

    @property
    def text_color(self) -> Any:
        return self._color

    @text_color.setter
    def text_color(self, color: Any) -> None:
        """Answered, and remembered, for the reason text_bold is.

        Nothing colors a cell of the listing: the module grids color theirs by whether the
        address the row reports is free, which is a question about one address rather than
        about a layout. A cell that could not be colored, though, would not be a cell of
        either grid -- and standing in for one anywhere either grid writes one is the whole
        of what this class is for.
        """
        self._color = color
        for block in self._blocks:
            block.text_color = color

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, text: str) -> None:
        """Write the text into the cell, a block per group of it.

        Spare blocks are hidden rather than blanked, for the reason the spare rows of either
        grid are hidden: an empty label still stands a line tall, so the cell would keep the
        height of the fullest module it had ever been written for.
        """
        self._value = "" if text is None else str(text)
        groups = self._value.split(INVENTORY_GROUP_BREAK)
        for index, group in enumerate(groups):
            block = self._grow(index)
            block.value = group
            if not block.visible:
                block.show()
        for spare in self._blocks[len(groups) :]:
            if spare.visible:
                spare.hide()
        self._space_blocks()

    def _grow(self, index: int) -> Text:
        """
        The block at index, made the first time the cell has that much to say.
        """
        while len(self._blocks) <= index:
            block = self._block(self._box)
            block.text_bold = self._bold
            if self._color is not None:
                block.text_color = self._color
            self._blocks.append(block)
        return self._blocks[index]

    def _space_blocks(self) -> None:
        """Put the space back between the blocks, after every write rather than once.

        guizero rebuilds a container's pack options from scratch whenever anything in it is
        created, shown or hidden, and padding is not among the options it replays -- so the
        space between the blocks has to follow the writing of them. Measured in a live
        window: a block hidden and shown again comes back against the one above it.

        A hidden block is passed over, and that is not an optimization: pack_configure
        *manages* a widget pack has forgotten, so padding replayed onto a spare block would
        put it back on the page carrying the text of the fuller module it was last written
        for. The same trap restore_footer_packing and _stick_inventory_cells each avoid.

        Above each block but the first, which is where a break belongs: the space says the
        group below it begins, and above the first there is nothing to tell it from.
        """
        opening = True
        for block in self._blocks:
            if not block.visible:
                continue
            try:
                block.tk.pack_configure(pady=(0 if opening else self._gap_px, 0))
            except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                continue
            opening = False


# A cell of either grid: the label all but one of them is, and the stack of labels the
# listing's configuration column is. See GroupedCell and _grid_cell.
GridCell = Text | GroupedCell


@dataclass(frozen=True)
class Verification:
    """The verdict on a read-back: what the module reports, held against what was sent.

    Two facts rather than one, because there are two ways for a programming pass to have
    failed and the operator can act on the difference: the module answered and is holding
    something else, or nothing answered at all. Only the first can name what is wrong.

    A verdict is never given on the panel's current selection but on the program that was
    actually sent, which is why this is built from an LcsProgram; see
    LcsConfigPanel.verification.
    """

    # Whether a module of the type programmed was found at the address it was programmed to.
    reported: bool = False
    # What it holds that is not what was sent, named as the pages that set it name it.
    differs: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """
        Whether the module came back holding what it was given, which is the only success.
        """
        return self.reported and not self.differs


def touch_only_editing() -> bool:
    """True where an on-screen editor is the only keyboard: the Pi and the Steam Deck.

    Both are Linux, and is_linux() is what the rest of the project already uses to tell the
    appliance platform from a desktop. Taken from utils.host_info, never from the pytrain
    package root: that package imports EngineGui -- and through it this module -- before it
    defines anything of its own, so importing it back is circular. admin_panel reads
    is_steam_deck from the same leaf module for the same reason.
    """
    return is_linux()


def reflects_layout_by_default() -> bool:
    """True, where the panel should open on the module already at the entered TMCC ID.

    On the Pi and the Steam Deck the panel is opened from a screen that is *about*
    something -- a switch, an accessory -- so the module answering to that address on that
    remote key is the one the operator means, and pre-selecting it saves them a tap.

    On a desktop there is no such context: the stand-alone window opens on nothing in
    particular at TMCC ID 1, and guessing from whatever happens to sit there is how a
    panel opened on an STM2 when the operator had come to program something else. There
    it opens on the first module offered, which is stable and predictable.

    Same platform test as touch_only_editing(), and for the same reason: Linux is the
    appliance, everything else is a desk.
    """
    return is_linux()


def needs_close_button() -> bool:
    """True where the panel has to carry a Close button: the Pi and the Steam Deck.

    Those two run full screen with no window frame, so a button below the panel is the
    only way off it. A desktop window has a title bar, and its close box is already wired
    to the very same shutdown -- GuiZeroBase.run sets App.when_closed to close -- so a
    Close inside the window is a second one of something the window already has.

    Same platform test as touch_only_editing(), and for the same reason.
    """
    return is_linux()


def every_mode_label() -> list[str]:
    """Every row the Mode list can ever show, each at the widest block it can claim.

    What the mode rows are sized against: the list is rebuilt whenever the module or the
    address changes, so sizing it to the module in hand would redraw it a size larger or
    smaller under the operator's eyes. At each mode's highest base, since that is where its
    label carries two two-digit addresses -- "91 - 98" against "1 - 8". See
    LcsConfigPanel._mode_row_size.
    """
    return [mode.ids_label(mode.max_base) for device in configurable_devices() for mode in enabled_modes(device)]


def cramped_pane() -> bool:
    """True on the Pi, the one screen the panel is drawn on that has no room to spare.

    480px wide and 800 tall at a font scale of 1.5, which is 33 percent larger text than the
    desk draws in two thirds of the width the Deck has -- the panel's fullest page asks for
    703px there against 408 on a Deck pane. What it decides is how large the titled boxes'
    own text is set: a size down on this screen, the page's body size everywhere else.

    is_linux() alone would take the Deck in with it, and the Deck has the room; hence the
    same pair pad_driven() is told apart by, read the other way round. A desk *window* sized
    and scaled like a Pi therefore keeps the larger text -- it can be resized, and what it
    cannot show it scrolls.
    """
    return is_linux() and not is_steam_deck()


def pad_driven() -> bool:
    """True where the panel is worked with a gamepad: the Steam Deck alone.

    The one place in this module where the two appliances part company, so not the platform
    test the three above share: the Pi is a touch screen and the Deck is a touch screen with
    a pad, and is_linux() cannot tell them apart. is_steam_deck() reads the platform the
    install recorded rather than probing hardware -- the Deck runs ordinary Linux, and the
    same machine can host a plain install -- which is how admin_panel already asks whether it
    is on a Deck. A Deck started outside its own launcher, with nothing exporting that
    platform, therefore reads as a desk: the panel is then worked with the touch screen it
    also has, which is the safe way round for a guess to be wrong.

    What it decides is whether the page's lists carry the pad's highlight, which is not free:
    arming a list takes Tk's own filled bar off the selected row, leaving the dot as the only
    mark that a row is set. There must be only one filled bar and the highlight owns it; see
    CheckBoxGroup._neutralise_select_color. A machine with nothing to move the highlight would
    pay that price for a highlight that can never appear, so the Pi and the desk keep the bar
    and the Deck trades it for the highlight it is worked by.
    """
    return is_steam_deck()


def scroll_bar_px() -> int:
    """How wide the bar down the right edge of a scrolling page is drawn, in pixels.

    Wider where there is width to be wide in. The bar is drawn over the page rather than
    beside it, so what a wider one costs is what it covers -- the last few pixels of the
    right-hand end of a row -- and a 640px Deck pane has a third more of them to spend than
    the Pi's 480px. See SCROLL_BAR_PX for the two widths and what bounds them.

    The desk reads as the narrower of the two, and rightly: its window is resizable, so its
    pane can be any width at all, and the narrowest is the one to be right about. is_linux()
    would not do here for the same reason it does not do in cramped_pane(): what is being
    asked is how wide the screen is, which is the one thing the Pi and the Deck differ in.
    """
    return SCROLL_BAR_PX_DECK if is_steam_deck() else SCROLL_BAR_PX


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
        # And False until the operator picks a mode for themselves, which is what stops the
        # module already at the address being read for one; see _seed_mode_from_layout.
        self._mode_chosen: bool = False

        self._pages: list[Box] = []
        self._body: Box | None = None
        # The size the mode rows came out at once the screen was measured; see _mode_row_size.
        self._mode_size: int | None = None
        # The window the pages are seen through. Everything below it -- Back, Next, and the
        # Close the popup adds under them -- stays where it is however tall a page becomes;
        # see build and _fit_scroll.
        self._scroll: ScrollBox | None = None
        self._device_group: CheckBoxGroup | None = None
        self._titled_boxes: Box | None = None
        self._mode_box: TitleBox | None = None
        self._mode_group: CheckBoxGroup | None = None
        self._id_heading: Text | None = None
        self._id_field: EditableText | None = None
        self._minus_btn: HoldButton | None = None
        self._plus_btn: HoldButton | None = None
        self._mode_legend_line: Text | None = None
        self._mode_note_line: Text | None = None
        self._assigned_box: TitleBox | None = None
        self._assigned_grid: Box | None = None
        # One tuple of three cells per row: the remote key, the module, and its TMCC IDs.
        # Created as they are first needed and reused from then on.
        self._assigned_cells: list[tuple[GridCell, ...]] = []
        self._overlap_box: TitleBox | None = None
        self._overlap_grid: Box | None = None
        self._overlap_cells: list[tuple[GridCell, ...]] = []
        self._goto_btn: HoldButton | None = None
        self._new_btn: HoldButton | None = None
        # My Modules: the key that opens the listing, the rows that order it, and the grid
        # it is written into. The heading row is the grid's first, so the cells below are
        # grown and reused exactly as the module rows' are; see _refresh_inventory.
        self._inventory_btn: HoldButton | None = None
        # The row that key stands on, which is what puts it in the other keys' column; see
        # _build_key_row.
        self._inventory_key_row: Box | None = None
        self._sort_group: CheckBoxGroup | None = None
        self._sort_key: str = SORT_MODULE
        self._inventory_grid: Box | None = None
        self._inventory_cells: list[tuple[GridCell, ...]] = []
        self._inventory_empty_line: Text | None = None
        self._back_btn: HoldButton | None = None
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
        # Which module, on which key, at which address the options on screen were read off
        # the layout for, and which of them were read there rather than chosen or defaulted;
        # see _seed_options_from_layout.
        self._options_read_from: tuple[str, CommandScope | None, int] | None = None
        self._options_from_layout: set[str] = set()

        # Review page
        self._program_line: Text | None = None
        # The presses, and the titled frame they are listed in -- with the grid column that
        # frame is stretched across, which is what gives it a width the page decides; see
        # _build_manual_config_box.
        self._review_line: Text | None = None
        self._manual_config_box: TitleBox | None = None
        self._manual_config_grid: Box | None = None
        self._review_note_line: Text | None = None
        self._configure_btn: HoldButton | None = None
        # The row that key stands on, which is what puts it in the other keys' column; see
        # _build_key_row.
        self._configure_key_row: Box | None = None
        self._footnote_line: Text | None = None
        self._requested_line: Text | None = None
        self._reported_line: Text | None = None
        self._status_line: Text | None = None

        # Read-back
        self._sent_program: LcsProgram | None = None
        self._readback_watcher: StateWatcher | None = None
        self._readback_pending = False

        # Gamepad: the page a mark was made on and the choice it displaced, which is what a
        # D-pad left puts back. One mark deep and dropped when the page turns; see pad_revert.
        self._pad_undo: tuple[int, str] | None = None

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
    def shares_train_ids(self) -> bool:
        """Whether the key being programmed is the one the trains themselves answer to.

        The TR key is the trains' own namespace, and a module addressed as a TR device takes
        its block out of it: a BPC2 programmed as TR 1 answers to the button that runs the
        train at TR 1. So on that key -- and only on it -- the trains are as much in the way
        as another module would be, and both occupancy boxes say so.

        False while no mode is chosen, for the reason overlap_occupants() answers with
        nothing then: which addresses are taken is a question about a block, and there is no
        block until a mode says how long it is.
        """
        return self.scope == CommandScope.TRAIN

    @property
    def compact(self) -> bool:
        return bool(getattr(self._gui, "compact", False))

    @property
    def touch_editing(self) -> bool:
        """
        Whether the ID field needs an on-screen editor; see touch_only_editing().
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
        # What the options were read off the layout before this is what an empty store had
        # to say about it, which is nothing; see _seed_options_from_layout. The mode needs
        # no such clearing: it is read afresh on every refresh of the page until the
        # operator picks one for themselves, and a choice of theirs stands here too.
        self._options_read_from = None
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
    def _id_page_gap(self) -> int:
        return ID_PAGE_GAP_COMPACT if self.compact else ID_PAGE_GAP

    @property
    def _review_heading_gap(self) -> int:
        return REVIEW_HEADING_GAP_COMPACT if self.compact else REVIEW_HEADING_GAP

    @property
    def _box_gap(self) -> int:
        return BOX_GAP_COMPACT if self.compact else BOX_GAP

    @property
    def _radio_row_pad(self) -> int:
        return RADIO_ROW_PAD_COMPACT if self.compact else RADIO_ROW_PAD

    @property
    def _mode_row_pad(self) -> int:
        return MODE_ROW_PAD_COMPACT if self.compact else MODE_ROW_PAD

    @property
    def _nav_row_pad(self) -> int:
        return NAV_ROW_PAD_COMPACT if self.compact else NAV_ROW_PAD

    @property
    def _mode_prose_gap(self) -> int:
        return MODE_PROSE_GAP_COMPACT if self.compact else MODE_PROSE_GAP

    @property
    def _mode_key_lead(self) -> int:
        return MODE_KEY_LEAD_COMPACT if self.compact else MODE_KEY_LEAD

    @property
    def _option_row_pad(self) -> int:
        return OPTION_ROW_PAD_COMPACT if self.compact else OPTION_ROW_PAD

    @property
    def _note_pad(self) -> int:
        return NOTE_PAD_COMPACT if self.compact else NOTE_PAD

    @property
    def _pane_px(self) -> int:
        """The width the popup is built to, in pixels.

        Asked of the host rather than measured, and asked defensively: the emergency box is
        what the popup is built to the width of, the pane's own width is the next best
        answer, and a host that has yet to report either answers with nothing. The one
        reading of it, so the wrap and the titled boxes below cannot come to disagree about
        how wide the page is.
        """
        host = self._gui
        return int(getattr(host, "emergency_box_width", 0) or 0) or int(getattr(host, "width", 0) or 0)

    @property
    def _page_px(self) -> int:
        """The width a page is actually drawn in: the pane, less the scroll bar's gutter.

        The bar is drawn down the right-hand edge of the window the pages are seen through,
        over whatever is there. So the room it takes is kept out of the page rather than
        found at the page's expense: the window spans the pane, the page spans the window
        less this, and the bar has the difference to itself.

        Kept whether or not the page in hand overflows, and on every machine, because it is
        what every line on the page is broken at: a gutter that came and went with the bar
        would re-break every line each time it did, and one screen's page would read
        differently from another's for no reason the operator could see. What it costs is the
        page sitting half a bar's width left of the popup's own title, which is what a
        scrolled pane looks like anywhere.

        See ScrollBox, which keeps the same room on the window's side, and scroll_bar_px().
        """
        return max(MIN_WRAP_PX + WRAP_INSET, self._pane_px - scroll_bar_px())

    @property
    def _wrap_px(self) -> int:
        """The width a line of prose is broken at; see WRAP_INSET.

        A host that has yet to report a width of its own gets the floor.
        """
        return max(MIN_WRAP_PX, self._page_px - WRAP_INSET)

    @property
    def _titled_box_px(self) -> int:
        """The least the Mode, Currently Assigned and Overlaps boxes are drawn to.

        Wider than the wrap, always: the inset it is taken with is the smaller of the two,
        and the floor is the wrap's own floor plus that difference, so a host that has
        measured nothing yet still gets boxes able to hold a line broken at MIN_WRAP_PX.
        See TITLED_BOX_INSET.
        """
        floor = MIN_WRAP_PX + (WRAP_INSET - TITLED_BOX_INSET)
        return max(floor, self._page_px - TITLED_BOX_INSET)

    @property
    def _manual_config_px(self) -> int:
        """The width the review page's Manual Configuration box is drawn to.

        The page's own prose width, which is not the floor the ID page's three boxes share:
        that inset is 6px a side, and drawn to it this box stood all but on the edge of the
        page -- 444px of a 456px page on the Pi, with the whole of its right-hand margin
        being the scroll bar's gutter. What the block wants is a margin, and the page already
        has one: every line of prose on it is broken at WRAP_INSET from the edges, so setting
        the frame there stands it exactly where the instruction above it breaks, and gives the
        block twice the white space it had either side.

        Which is also the one width no line on the page can overrun, so nothing inside the
        box is broken by the frame rather than by its own wrap; see _manual_config_wrap_px
        for the margin inside it and MANUAL_CONFIG_PAD for what that was measured against.
        """
        return self._wrap_px

    @property
    def _manual_config_wrap_px(self) -> int:
        """Where a press is broken inside that box: its width, less the margin either side.

        Not the page's wrap, which is the box's own width now and would let a press run to
        the frame and be broken by it. The floor is the wrap's floor, for a pane so narrow
        that the margin would eat into it: a line told to break at nothing is a line Tk does
        not break at all.
        """
        return max(MIN_WRAP_PX, self._manual_config_px - 2 * MANUAL_CONFIG_PAD)

    @property
    def _titled_text_size(self) -> int:
        """The size the titled boxes' own text is drawn at -- their titles and their rows.

        The page's body size, and a size below it where the pane has no room to spare. What
        these boxes hold is read rather than aimed at: three headings, and under two of them
        the modules the layout already has at the address. Nothing in them is a touch target
        bar the mode radios, which keep their own size; see _mode_row_size.

        A size is 3pt of the panel's own scale, which on the Pi is 4px off every line of
        every box -- and the boxes are three quarters of that machine's tallest page. See
        cramped_pane.
        """
        host = self._gui
        return host.s_12 if cramped_pane() else host.s_14

    @property
    def _inventory_text_size(self) -> int:
        """The size the My Modules listing is drawn at: the page's body size, on every screen.

        Not _titled_text_size, though the same code builds the listing's grid and the rows
        inside those boxes. What steps that size down on the Pi is height -- the three boxes
        are three quarters of that machine's tallest page, and 3pt off every line of them is
        what makes the page fit. This is a page of its own, a heading and three sort keys
        over a grid, and it is scrolled: what it cannot show it scrolls to. Nothing is bought
        there by drawing it small, and what it costs is that the one page in the panel which
        is nothing but reading matter is set in the smallest text on any of them.

        So the listing is a size up where the panel used to draw it a size down: 14 on the Pi
        and the desk, 13 on a Deck. It is paid for in width, the size being what the three
        bounded columns' reservation is a multiple of -- the configuration column breaks at
        250px rather than 276 -- and the largest size whose whole price is the one line the
        operator agreed to lose. Measured in the cells' own font against the column each size
        leaves: at 14 the IR Sensor Track's action takes two lines (311px against 250) and
        every other line the registry can write holds, the widest of them being "Motor #2:
        Proportional (DC)" at 236px and "Restore on power-up: Yes" at 221; at 15 the AMC2's
        motor modes go with it (244px against 237), and at 16 the flag beneath them (239
        against 224). See INVENTORY_FIXED_COLUMNS_EMS for the reservation itself.
        """
        return self._gui.s_14

    @property
    def _review_text_size(self) -> int:
        """The size the review page's instruction and its Manual Configuration are drawn at.

        A size above the page's body, and two above where the instruction was set: what
        stands here is not a caption on the page but the work itself -- the button to hold
        on the module, and the keys that go out when Configure is pressed -- read off a
        screen by someone standing at a layout with their hands full. It was the smallest
        text in the panel.

        Measured in the labels' own font against the page's 432px wrap, at every size the
        panel draws: the instruction takes two lines at all of them, from 12pt (524px for an
        ASC2) to 18pt (744px), so this size costs nothing a smaller one would save. The
        widest press a module can write, "2. AUX1 then 1 (Action Command)", holds one line at
        312px of the 416 its box leaves inside its own margin. The one module that pays is the
        IR Sensor Track, whose instruction carries the abort as well and goes from four lines
        to five -- height the page scrolls.
        """
        return self._gui.s_16

    @property
    def _status_text_size(self) -> int:
        """The size the verdict on a read-back is drawn at: the largest text the panel writes.

        Three sizes above the page's body, where this line was set: it is the answer to the
        one question the whole panel is walked to ask -- whether the module took what it was
        sent -- and it is read by an operator who has just had both hands on the module and is
        looking up from it. Every other line on the page can be read again at leisure; this
        one is looked for.

        Measured in the line's own bold font, drawn and wrapped by Tk against the narrowest
        page the panel runs on: "Success" stands on one line at every size above the body --
        108px of that page's 432 here, 128px at the largest size the panel sets anything -- so
        what a size costs is paid by the failure that has something to explain: the verdict,
        the settings that disagreed, and the button to hold to try again. The worst of those
        goes from three lines to five here, 84px of height to 185; a size further up costs
        15px more than that, and the largest, another 73.

        Which is height and not width, and height is what this page has: it is scrolled, and
        this line is scrolled to as soon as it is written -- see _reveal_status. Read back in
        a live window at the new size, the page is 355px of the Pi's 539px window with a
        Success on it and 510px with the worst failure spelled out.

        The polling line is written to this same widget and grows with it, which is right: it
        is the same sentence at an earlier moment, and it is what the operator is watching
        while the panel waits the module out. It goes from two lines to three. See VERIFYING
        and _show_status.
        """
        return self._gui.s_20

    @property
    def _row_name_wrap_px(self) -> int:
        """The width the name column of a module row breaks a name at.

        The page's own width less what the two columns beside it can take, so a name too
        long for its column breaks inside it rather than pushing the row off the pane. See
        ROW_FIXED_COLUMNS_EMS for the reservation and how it was measured.

        The floor is an equal share of the three columns, for a pane so narrow that the
        reservation would swallow it: a column left with nothing is a column told to break
        at zero, which in Tk is how a line is told not to break at all -- the very thing
        this is here to prevent.
        """
        reserved = ROW_FIXED_COLUMNS_EMS * self._titled_text_size
        return max(self._wrap_px // ROW_COLUMNS, self._wrap_px - reserved)

    @property
    def _mode_row_size(self) -> int:
        """The size a mode radio is drawn at: the largest at which the rows fit the page.

        A step above the page's body wherever there is room for it, because each row carries
        the block of TMCC IDs it would claim as well as its own name and is the thing being
        aimed at with a finger. On the Pi there is not: the longest of them, the STM2's
        single-wire block, asked for 666px of a 480px pane at that size. So the size is
        fitted to the screen instead of chosen for one and hoped for on the others; see
        CheckBoxGroup.fit_row_size.

        Fitted to *every* mode in the registry rather than to the module in hand, and to each
        of them at the widest block it can claim. The list is rebuilt whenever the module or
        the address changes, and a list that came back a size larger or smaller each time
        would be a worse thing to read than one drawn a step down throughout.

        Settled once, on the first page that asks: it is an answer about the screen, which
        does not change under a running panel, and the wrap below is taken from it.
        """
        host = self._gui
        if self._mode_size is None:
            self._mode_size = CheckBoxGroup.fit_row_size(
                getattr(host, "app", None),
                every_mode_label(),
                self._titled_box_px,
                ceiling=host.s_18,
                floor=host.s_12,
            )
        return self._mode_size

    def _fit_row_size(self, texts: Sequence[str], ceiling: int) -> int:
        """The largest size at or below ceiling at which every one of texts fits a row.

        The panel's own way of asking CheckBoxGroup.fit_row_size: measured against the width
        of the titled boxes, which is the widest anything on a page is drawn, and never taken
        below the size the page's prose is read at -- past that point a row is better broken
        onto a second line than shrunk further, which is what _row_wrap_px is for.
        """
        host = self._gui
        return CheckBoxGroup.fit_row_size(
            getattr(host, "app", None),
            texts,
            self._titled_box_px,
            ceiling=ceiling,
            floor=host.s_12,
        )

    def _row_wrap_px(self, size: int) -> int:
        """Where the label of a radio or tick row is broken, in pixels.

        The page's width less what the row spends before its text -- the painted indicator,
        the padding either side of the row's contents, the frame it is drawn with; see
        CheckBoxGroup.row_chrome_for. Taken off the titled boxes' width rather than the
        pane's, since the mode rows are drawn inside one and the boxes are the widest thing
        on any page.

        A row is stretched to the width of its container (see CheckBoxGroup.stretch_rows), so
        this decides nothing about how wide a row *is*; it decides where the words in it
        break. Without it a long label is cut at the pane's edge and what goes with it is the
        end of the line -- which on these rows is the address block, the one fact the row is
        chosen for. With the size fitted to the screen it should never fire on the rows the
        registry holds today; it is what a longer one would meet.
        """
        return max(MIN_WRAP_PX, self._titled_box_px - CheckBoxGroup.row_chrome_for(size, "radio"))

    @property
    def _scroll_px(self) -> int:
        """How wide the window the pages are seen through is drawn.

        The pane's own width, which is what the popup is already built to: the title row
        above the pages is created at exactly this width, so the window takes none of what
        the page had and adds nothing to what the popup asks for. A host that has measured
        nothing yet gets the same floor the wrap does, one inset wider.

        It is also a ceiling the pages did not have before. A window is as wide as it is
        told, so a line too long for it is cut at the pane's edge instead of widening the
        popup past it -- the page keeps its width and the operator loses the end of one line
        rather than both ends of it. Nothing on any page should reach it; see the wrap.
        """
        return max(MIN_WRAP_PX + WRAP_INSET, self._pane_px)

    @property
    def scroll(self) -> ScrollBox | None:
        """The window the pages are drawn in, or None before the panel is built."""
        return self._scroll

    def _fit_scroll(self) -> None:
        """Give the pages the room the pane has left, and no more.

        Called when a page is shown and whenever what is in one changes size. The window
        takes the height of the page where there is room for it -- which is most pages on
        most machines, and there the panel looks exactly as it did before there was a window
        at all -- and the room there is where there is not.
        """
        scroll = self._scroll
        if scroll is None:
            return
        scroll.fit(self._scroll_budget())
        # Rows built since the last pass -- the mode list is rebuilt on every module change
        # -- have no gestures on them until they are told about them.
        scroll.bind_scrolling()
        # And a page that turns out to be held back says so by moving, once, the first time
        # it is fitted with something to show. Asked here rather than where the page is turned
        # because a page is not measured until it is: built off screen, everything about it
        # reads 1, and whether it overflows is not known until the popup is laid out. See
        # ScrollBox.hint.
        scroll.hint()

    def _scroll_budget(self) -> int | None:
        """The most the pages may take, in pixels, or None where nothing can be measured.

        Measured rather than derived, and measured as the overshoot: the popup is asked how
        tall it wants to be, the window's own height is taken out of that to leave everything
        else the popup draws -- the title row, the banner, Back and Next, Close and the
        whitespace of the band it sits in -- and what is left of the pane after that is the
        window's. Nothing here has to know what those parts are or how tall each of them is,
        which is the point: they have all changed at least once, and a page rebuilt for a
        module with a different number of boxes changes the total again.

        The room is taken from the top of the popup down to the bottom of the pane, less
        whatever the pane keeps below it -- the scope buttons under an embedded panel. A
        window is not sized off a measurement Tk has not made yet: before the popup is on
        screen every reading is 1, and None leaves the pages at their own height.
        """
        scroll = self._scroll
        overlay = self._overlay
        if scroll is None or overlay is None:
            return None
        try:
            frame = overlay.tk
            if not frame.winfo_ismapped():
                return None
            parent = frame.master
            top = int(frame.winfo_rooty())
            room = int(parent.winfo_rooty()) + int(parent.winfo_height()) - top
            for sibling in parent.winfo_children():
                # What the pane keeps below the popup stays the pane's: an embedded panel is
                # drawn over the engine controls but above the scope buttons, which are how
                # the operator gets back to them.
                if sibling is frame or not sibling.winfo_ismapped():
                    continue
                if int(sibling.winfo_rooty()) >= top:
                    room -= int(sibling.winfo_height())
            chrome = int(frame.winfo_reqheight()) - scroll.view_px
            budget = room - chrome
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            return None
        return budget if budget > 0 else None

    def _wrap(self, widget: Any, justify: str = "center", pady: int = None, width: int = None) -> Any:
        """Break widget's text at the popup's width and hold it off its neighbors.

        Both are Tk widget options rather than layout ones, which is what makes them safe
        here: guizero rebuilds a container's pack and grid options from scratch every time
        anything in it is created, shown, or hidden -- and the options page shows and hides a
        box on every device change.

        justify is what a broken line is aligned on, so it follows the widget: the prose
        lines are centered under the heading, while a checkbox's label is set beside its
        indicator and reads from the left. Returned so a label can be built and wrapped in
        one breath.

        width is for a widget that is not the width of the page: the pane is the right
        answer for a line of prose, which has the page to itself, and the wrong one for a
        column standing beside two others. See _row_name_wrap_px.
        """
        options: dict[str, Any] = {"wraplength": width or self._wrap_px, "justify": justify}
        if pady is not None:
            options["pady"] = pady
        try:
            widget.tk.config(**options)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        return widget

    def build(self, body: Box) -> None:
        host = self._gui
        self._body = body
        # First child of the body, so every page sits this far below the title row.
        host.add_vspace(body, self._section_gap)
        # Above the pages, so the banner shows on whichever page is up.
        self._sync_line = self._label(body, "", bold=True)
        self._refresh_sync_line()
        # The pages go in a window of their own, and nothing else does. A page that asks for
        # more height than the pane has is scrolled inside it rather than running off the
        # bottom -- which is not a tidier way of losing the same thing: Tk allots space in
        # creation order, so what a page too tall for the pane actually costs is whatever is
        # packed last, and that is Back, Next and Close. Those stay outside the window and so
        # stay on screen at any height; see ScrollBox and _fit_scroll.
        self._scroll = scroll = ScrollBox(body, width=self._scroll_px, bar_px=scroll_bar_px())
        pages = scroll.content
        self._pages = [
            self._build_device_page(pages),
            self._build_id_page(pages),
            self._build_options_page(pages),
            self._build_review_page(pages),
            # Built with the four the operator walks, though it is not one of them: a page
            # is shown, hidden and fitted to the window by its index here, and one held
            # outside this list would need every one of those things done to it some other
            # way. See PAGE_INVENTORY.
            self._build_inventory_page(pages),
        ]
        # Back and Next belong to the panel, not to the popup's footer row: the popup adds
        # its own Close below everything built here, so Close gets a line of its own
        # instead of the three buttons sharing one. Created after the pages so the row is
        # packed below whichever page is showing.
        host.add_vspace(body, self._page_gap)
        self._build_nav(body)
        self._show_page(self._page_index)
        # A page is not done growing when it is built: a row added later, a titled box shown
        # for a module that has one, a note that arrives with the read-back. The window asks
        # to be re-fitted whenever what is in it changes size, so no caller has to remember --
        # and whenever the body it is drawn in does, which is what tells it the popup has
        # been put on screen. Nothing measured before that means anything: a popup is built
        # unmapped, and everything about an unmapped widget reads 1.
        scroll.bind_scrolling()
        scroll.on_content_resized(self._fit_scroll, body)
        self._fit_scroll()

    def _label(self, parent: Box, text: str, size: int | None = None, bold: bool = False, **kwargs) -> Text:
        """A line of the panel's own text, broken at the width of the pane it is drawn in.

        Wrapped by default, and that is the rule rather than a convenience: Tk truncates
        nothing, so a label wider than the popup is centered in it and loses its beginning
        *and* its end. Every line this panel writes is written by something -- a module's
        name, a mode's block of addresses, a sentence from the registry -- and none of them
        is bounded by anything that knows how wide the screen is. The one heading that had no
        wrap, the first page's own question, came to 552px of the Pi's 480px pane.
        """
        host = self._gui
        lbl = Text(parent, text=text, align="top", **kwargs)
        lbl.text_size = size or host.s_14
        lbl.text_bold = bold
        return self._wrap(lbl)

    def _build_device_page(self, body: Box) -> Box:
        host = self._gui
        page = Box(body, align="top", border=0)
        self._label(page, DEVICE_PROMPT, size=host.s_16, bold=True)
        host.add_vspace(page, self._section_gap)
        # The shortest rows in the panel -- a module's name and nothing else -- so the size
        # asked for is the size they get on every screen the panel is drawn on. Fitted all
        # the same, because what is asked of these rows is the registry's to change.
        device_size = self._fit_row_size([label for label, _key in self.device_options()], host.s_14)
        self._device_group = CheckBoxGroup(
            page,
            size=device_size,
            options=self.device_options(),
            selected=None,
            align="top",
            style="radio",
            # And a module named past even that is broken onto a second line rather than cut
            # off at the pane's edge; see _row_wrap_px.
            wrap=self._row_wrap_px(device_size),
            # The rows are held apart rather than stacked: this is the panel's first page and
            # every row on it is a touch target.
            pady=self._radio_row_pad,
            # One length for all of them, filling the page rather than each row stopping at
            # the end of its own label -- see CheckBoxGroup.stretch_rows.
            stretch=True,
            # The pad steps this list on the Deck, so the row it is pointing at and the row
            # that is chosen are two different things and both have to be shown; see the
            # Gamepad section. Armed only where there is a pad to move it -- see pad_driven --
            # and armed on every list there, the pad reaching all of them.
            cursor=pad_driven(),
            command=self._on_device_selected,
        )
        # And, below the choice, the way to go and look first. What is already out on the
        # layout is the thing an operator wants to know before they program anything -- which
        # addresses are taken, and by what -- and this is the page they are standing on when
        # they want it. Off to one side rather than in the march: it answers a question of
        # its own and leads nowhere, so it is a key that opens a page and comes back rather
        # than a step between this page and the next. See show_inventory.
        host.add_vspace(page, self._page_gap)
        self._inventory_key_row = row = self._build_key_row(page)
        self._inventory_btn = btn = HoldButton(row, text=INVENTORY_TEXT, align="left", command=self.show_inventory)
        # The one shared look for the big keys of an overlay, which Back, Next, Configure and
        # the Close below them all wear: a raised border and an edge, a lighter face than the
        # panel, and a darker one while it is held. It is drawn as a key rather than as a word
        # in a rectangle because it is one -- it turns a page, as the two below the panel do,
        # and it is the only key on this page besides them.
        #
        # Its pack padding is then trimmed exactly as the Back/Next row's is: the band a
        # footer button carries is meant to hold a row off the panel and the pane, and this
        # key stands in the middle of a page with the modules above it and Next below.
        # See style_footer_button and NAV_ROW_PAD.
        style_footer_button(host, btn)
        repad_footer_button(btn, pady=self._nav_row_pad)
        host.cache(btn)
        return page

    def _build_key_row(self, page: Box) -> Box:
        """A row for a key built into a page, which is what puts it in the other keys' column.

        Such a key wears the look of the panel's other big keys and stands directly above two
        of them, so it stands where they stand -- and it did not. Back, Next and the Close
        below them are centered on the pane; everything on a page is centered on the page, and
        the page is one scroll bar narrower than the pane, the bar being drawn over its
        right-hand edge rather than beside it (see _page_px and ScrollBox). Half a bar is what
        such a key stood left of the two keys beneath it: 12px on the Pi and the desk, 15px on
        a Deck, measured in a live window with the panel's own nesting.

        So the gutter is handed back to the key, as a spacer to the left of it on a row of its
        own: a row centered on the page with a bar's width of nothing at one end puts what is
        at the other end half a bar right of the page's middle, which is the pane's middle and
        the column the other keys stand in. Nothing else on the page moves. What stands above
        is read as a block of its own -- the module rows, the steps in their box -- and is
        centered as the contents of every page in the panel are.

        Two keys ask for this, and they are the only two the panel builds into a page: My
        Modules on the device page and Configure on the review page. Each is the one key on
        its page and each stands directly over Back, Next and Close.

        A spacer widget rather than pack padding, for the reason footer_spacer is one:
        guizero rebuilds a container's pack options from scratch whenever anything in it is
        created, shown or hidden, and padding is not among the options it replays -- and
        every turn of the panel hides a page and shows another.
        """
        host = self._gui
        row = Box(page, align="top", border=0)
        gutter = Box(row, align="left", width=scroll_bar_px(), height=1)
        host.cache(row, gutter)
        return row

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

        # Tighter than the gap between the page's other sections; see ID_PAGE_GAP.
        host.add_vspace(page, self._id_page_gap)

        # The titled boxes share one grid column, which is how they come out the same
        # width: the column is as wide as the widest of them, and each box is stretched
        # into it. Stacked rather than packed for exactly that reason -- packed boxes each
        # keep their own natural width, which is what left them ragged. The whitespace
        # between them rides along with that stretch; see _lay_out_titled_boxes.
        self._titled_boxes = Box(page, layout="grid", align="top", border=0)

        # The mode first, directly under the ID it goes with: those two are everything the
        # operator chooses on this page, and the boxes below them report what the choice
        # runs into. Reading down the page is then the order the work is done in -- pick the
        # address, pick the mode, see the consequences -- where the reports used to stand
        # between the two halves of the decision and be read before either was made.
        #
        # Titled, because the radios need a word for what they are choosing, and at the
        # page's body size like the two titles below it. The rows themselves are a size
        # above the body, since each one also carries the block of TMCC IDs it would claim.
        self._mode_box = TitleBox(self._titled_boxes, text=MODE_TITLE, grid=[0, 0], align=None)
        self._mode_box.text_size = self._titled_text_size
        # The legend heads the box, above the rows it names: what an ACC row and an SW row
        # are each good for is what the operator needs *before* choosing between them, and
        # read from below the list it was a note on a decision already made. Inside the box
        # either way rather than adrift among the page's other reports, where it read as a
        # statement about the panel at large.
        self._mode_legend_line = self._label(self._mode_box, "", size=host.s_13)
        host.add_vspace(self._mode_box, self._mode_prose_gap)
        mode_size = self._mode_row_size
        self._mode_group = CheckBoxGroup(
            self._mode_box,
            size=mode_size,
            options=self.mode_options(),
            selected=None,
            align="top",
            style="radio",
            # Less than the module radios ask for; see MODE_ROW_PAD.
            pady=self._mode_row_pad,
            # As on the device page, and here it is the width of the Mode box the rows take.
            # It has to survive a rebuild: these radios are replaced whenever the module
            # changes, and a rebuilt row goes back to the width of its own label.
            stretch=True,
            # And the rows of one remote key held off the rows of the next, so the list is
            # read as the legend above it is written -- a group per key. Set here as well as
            # on every refresh, since the group is built before a module is chosen.
            row_leads=self.mode_leads(),
            # The longest row in the panel: a mode names itself and the block of TMCC IDs it
            # would claim, and on the Pi the STM2's single-wire row asked for 666px of a
            # 480px pane. Broken rather than cut, so what is lost is a line's worth of
            # height and never the addresses at the end of it; see _row_wrap_px.
            wrap=self._row_wrap_px(mode_size),
            # Stepped by the pad, as the module rows are, and armed on the same terms. This is
            # the one armed list whose rows are replaced at runtime, which the component
            # re-arms itself for; see CheckBoxGroup._rearm_cursor and pad_cursor.
            cursor=pad_driven(),
            command=self._on_mode_selected,
        )
        # What the chosen row itself is for, which is the fact a row has no room for. Below
        # the rows, because it speaks for whichever one is selected and there is nothing to
        # say until one is. Held just off the last row; see MODE_PROSE_GAP.
        host.add_vspace(self._mode_box, self._mode_prose_gap)
        # Centered, like every other line of prose on the page: these lines are short and of
        # much the same length, and centered they read as a caption on the list they are
        # beside rather than as another row of it.
        self._mode_note_line = self._label(self._mode_box, "", size=host.s_10)

        # What already answers to the entered ID: it tells the operator whether they are
        # about to reprogram a module that is already out there. Titled, because a bare line
        # naming some other module beside the one being programmed reads as a contradiction
        # until you know it is reporting the layout rather than the choice. At the page's
        # body size, as are the module rows inside both boxes: a step below read as fine
        # print on the Pi, and what these boxes report is what the operator checks before
        # committing an ID.
        self._assigned_box = TitleBox(self._titled_boxes, text=ASSIGNED_TITLE, grid=[0, 1], align=None)
        self._assigned_box.text_size = self._titled_text_size
        # One row per module, gridded so the remote key, the module and its TMCC IDs line
        # up down the box instead of each row starting wherever the row above it ended.
        self._assigned_grid = Box(self._assigned_box, layout="grid", align="top", border=0)

        # Directly after it: the modules the chosen block would run into. Its own box, and
        # gridded a row per module rather than run together on one line, which is what put
        # two neighbors off the right edge of the window. Hidden when nothing is in the way,
        # since an empty titled frame reads as a failure to look rather than as an answer --
        # unlike the assigned box, which always has "Unassigned" to say.
        self._overlap_box = TitleBox(self._titled_boxes, text=OVERLAP_TITLE, grid=[0, 2], align=None)
        self._overlap_box.text_size = self._titled_text_size
        self._overlap_grid = Box(self._overlap_box, layout="grid", align="top", border=0)

        # One gap, where there used to be two with a line between them saying which TMCC
        # IDs the chosen mode claims. Every mode radio above now names its own block, so
        # that line only repeated the one the operator had just selected. Tighter than the
        # page's other gaps, and the last box above it carries none of its own; see
        # ID_PAGE_GAP and _lay_out_titled_boxes.
        host.add_vspace(page, self._id_page_gap)

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
        """Give the Mode, Currently Assigned and Overlaps boxes one width, and space between.

        All three are gridded into column 0 of the same container and stretched across it,
        so the column takes the width of whichever box asks for most and the others grow to
        match. No pixel width is chosen anywhere: a module name long enough to widen the
        assigned box widens the mode box with it, and vice versa.

        Re-applied after every refresh rather than set once, because guizero rebuilds a
        container's grid options from scratch in display_widgets -- which runs whenever any
        child is shown, hidden, or created -- and neither sticky nor pady is among the options
        it replays. Hiding the mode box for a device with no modes is enough to lose them. A
        hidden box is skipped: grid_configure on a widget the grid has forgotten would put it
        back on screen.

        That replay is also what makes pady the one place here where whitespace is
        padding rather than a spacer widget: it is re-applied on the same schedule as the
        stretch, so it cannot be silently dropped the way padding elsewhere in the panel
        would be. Stacked flush, the three boxes read as one ruled block on the Pi.
        """
        container = self._titled_boxes
        if container is None:
            return
        gap = self._box_gap
        # Which of them is the last one showing, so the block ends at its frame. The gap is
        # what holds one box off the next, and under the last there is no next: what follows
        # is the page's own gap and the choice buttons, and the two of them stacked read as a
        # hole below the reports. Asked of what is visible rather than of the three, since
        # the Overlaps box is taken off the page whenever nothing is in the way.
        showing = [
            box for box in (self._mode_box, self._assigned_box, self._overlap_box) if box is not None and box.visible
        ]
        try:
            # The column carries a width floor as well as the stretch: the boxes still grow
            # for a module whose rows ask for more, but none of them is drawn narrower than
            # the page it stands on -- which is what left the legend heading the Mode box
            # wrapped into a column the pane had no need to make it. See TITLED_BOX_INSET.
            container.tk.grid_columnconfigure(0, weight=1, minsize=self._titled_box_px)
            # In the order they are stacked, which is the order they are read in.
            for box in showing:
                box.tk.grid_configure(sticky="ew", pady=(0, 0 if box is showing[-1] else gap))
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    @staticmethod
    def _style_id_field(field: EditableText) -> None:
        """Draw the ID as a text box and open it for editing on a plain press.

        The field is a guizero Text, which renders as a bare label. The sunken border in the
        editor's own colors is what tells the operator it can be typed into, and it means the
        box does not change appearance when the Tk entry is placed over it.

        A box drawn to look like a text field is tapped, not leaned on, so a press opens it on
        every platform: the on-screen keypad on the Pi and the Deck, the system keyboard on a
        desktop. EditableText's own gesture is a full second of press-and-hold, which is right
        for a plain label that does not advertise itself -- the info overlay's fields, where a
        stray tap while reading a running engine would be an accident rather than an edit --
        and is bound by the component. Only this panel asks for the press, so it is bound here
        rather than turned on for every editable label.

        Both gestures survive together, and they have to: <Button-1> is the same Tk sequence
        the component presses on. Bound with add="+", so the component's own handler still
        runs first and starts its hold timer; begin_edit then cancels that timer, and a hold
        that outlives a press already editing does nothing.
        """
        try:
            field.tk.config(bg=field.edit_bg, fg=field.edit_fg, relief="sunken", bd=2)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
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
        self._label(page, OPTIONS_TITLE, size=host.s_16, bold=True)
        # The heading belongs with the line under it, so that gap is the tight one; the
        # wider one below separates the module being programmed from the settings being
        # chosen for it. See SECTION_GAP and PAGE_GAP.
        host.add_vspace(page, self._section_gap)
        self._options_summary = self._wrap(self._label(page, ""))
        # Nothing else stands between the heading and the settings. The module's warning was
        # read here and again on the review page, and it belongs on the one where it is acted
        # on -- it is about what pressing Configure does, not about what is being chosen; see
        # review_note. The modes the manual reserves were named here too, with the reason each
        # is unavailable: true, but about rows that are not on the page and cannot be reached
        # from it, which is nothing the operator can act on.
        host.add_vspace(page, self._page_gap)
        # One options box per device that declares any, built once and shown or hidden as
        # the selection changes. Rebuilding a CheckBoxGroup's rows at runtime loses the
        # painted indicators decorate_checkbox installs, so the rows a device declares are
        # created here, with the device, and never rebuilt.
        #
        # Nothing is built for a device with no options -- the page is not shown for one at
        # all; see skip_options.
        for device in configurable_devices():
            if not device.options:
                continue
            box = Box(page, align="top", border=0)
            self._option_boxes[device.key] = box
            # Whether there is whitespace to spend is a fact about the page rather than about
            # any one setting on it, so it is settled once for the module and handed to each;
            # see LONG_OPTION_PAGE.
            tight = option_page_rows(device) > LONG_OPTION_PAGE
            for option in device.options:
                self._build_option(box, device, option, tight)
            box.hide()
        return page

    def _note_line(self, parent: Box, text: str = "", pady: int = None, size: int | None = None) -> Text:
        """A line of prose about the module, wrapped and standing off what is around it.

        The page's body size unless the page it is on reads at another one; see _label, which
        is where the wrap comes from. What this adds is the padding: a note speaks about
        something above or below it and has to be seen to be apart from it.
        """
        return self._wrap(self._label(parent, text, size=size), pady=self._note_pad if pady is None else pady)

    def _build_option(self, box: Box, device: LcsDevice, option: LcsOption, tight: bool = False) -> None:
        host = self._gui
        key = (device.key, option.key)
        option_size = self._fit_row_size([label for label, _value in option.choices] or [option.label], host.s_18)
        if option.kind == OptionKind.RADIO:
            self._label(box, option.label, bold=True)
            self._option_choices[key] = [value for _label, value in option.choices]
            widget = CheckBoxGroup(
                box,
                # The size the mode radios and the lone checkbox are set at: these rows are
                # the choice being made on the page, and at the page's body size -- let
                # alone the step below it they were once drawn at -- the dot beside them was
                # barely there. A full page is set at it too, and pays for it in the
                # whitespace between its rows; see LONG_OPTION_PAGE.
                #
                # Asked for, rather than had: the Sensor Track's ten actions are the longest
                # rows the options page draws, at 575px of the Pi's 480px pane, so there they
                # come down to the size that fits. See _fit_row_size.
                size=option_size,
                # And broken rather than cut, for a choice named past even that.
                wrap=self._row_wrap_px(option_size),
                # The index is the row's value: an IrdaSequence is not a string, and
                # guizero hands back whatever string Tk holds.
                options=[[label, str(i)] for i, (label, _value) in enumerate(option.choices)],
                selected=None,
                align="top",
                style="radio",
                pady=0 if tight else self._option_row_pad,
                # One length for every row, filling the page rather than each row stopping
                # at the end of its own label -- as on the device and ID pages. See
                # CheckBoxGroup.stretch_rows.
                stretch=True,
                # And stepped by the pad, as the module and mode rows are. The Sensor Track's
                # ten actions are the longest list in the panel, and the one this matters most
                # on: ten rows is a lot to reach for on a Deck held in two hands.
                cursor=pad_driven(),
                command=self._option_command(device.key, option.key),
            )
        else:
            widget = CheckBox(
                box,
                text=option.label,
                align="top",
                command=self._option_command(device.key, option.key),
            )
            # The painted indicator, size and padding the module and mode radios carry, and
            # for the same reason: left to Tk this is the platform's own tick box, drawn at
            # the font's own scale and unfilled until it is set, which on the Pi read as a
            # smudge beside the label rather than as a control with a state.
            #
            # No row width. decorate_checkbox hands -width straight to the Checkbutton, and
            # a Checkbutton showing an image reads it in pixels and drops its padx with it,
            # which would pull the indicator flush against the row's left edge.
            CheckBoxGroup.decorate_checkbox(
                widget,
                option_size,
                pady=0 if tight else self._option_row_pad,
                width=None,
                style="checkbox",
                # Broken from the left, unlike the prose above it: the label is set beside
                # its indicator, so a second line belongs under the first and not under the
                # box -- and it is broken at what is left of the row after that indicator,
                # which is what the prose wrap does not know about. The BPC2's is the one
                # tick box in the panel, and at the pane's own wrap it came to 554px of the
                # Pi's 480. See _row_wrap_px.
                wrap=self._row_wrap_px(option_size),
            )
        self._option_widgets[key] = widget
        if not option.enabled:
            widget.disable()
        if option.note:
            # Body size and wrapped, like the line at the head of the page: a note is a full
            # sentence about the setting above it. No module in the registry writes one
            # today, and a full page is the case to be careful of if one does -- there is no
            # whitespace to hold it off the last row with, and none to draw it in either;
            # see LONG_OPTION_PAGE.
            self._note_line(box, option.note, pady=0 if tight else self._note_pad)

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

    @staticmethod
    def _refresh_note(line: Text | None, text: str) -> None:
        """Write a line of prose about the module, and take it off the page when there is none.

        An empty Label still stands a line tall and still carries its own padding, so a
        module with nothing to say would pay a line and two gaps of whitespace for a blank
        one -- the same reason a spare module row is hidden rather than blanked.

        Which modules say nothing is very nearly the mirror of one line to the next: the
        review page's note is filled by the BPC2 alone, while the note below the ID page's
        mode radios is filled by every module *but* the BPC2 and the Sensor Track. See
        review_note and _refresh_mode_note().
        """
        if line is None:
            return
        line.value = text
        if text and not line.visible:
            line.show()
        elif not text and line.visible:
            line.hide()

    @property
    def options_summary(self) -> str:
        """What the page is about to do: "BPC2: Configuring as ACC 1 - 8".

        The remote key and the addresses the chosen mode claims from the entered ID, which
        together are the module's new address -- said as the block it is rather than as a
        count and a base to add it to. The mode's own name is not repeated: which of a
        module's modes was chosen is a fact about the page before this one, and where two of
        them share a key they claim different blocks, so the block names the choice.
        """
        if self._device is None or self._mode is None:
            return ""
        scope = SCOPE_LABEL.get(self._mode.scope, "")
        span = tmcc_id_span(self._base_id, self._base_id + self.ports - 1)
        return CONFIGURING.format(
            module=self._device.label,
            block=" ".join(part for part in (scope, span) if part),
        )

    @property
    def requested_summary(self) -> str:
        """
        What was programmed, for the line that records it: see SUMMARY and REQUESTED.
        """
        if self._device is None or self._mode is None:
            return ""
        # The counted form, not the mode's radio label: this line names the address itself,
        # so the block it holds would be said twice. See LcsMode.ports_label.
        return SUMMARY.format(
            module=self._device.label,
            mode=self._mode.ports_label,
            scope=SCOPE_LABEL.get(self._mode.scope, ""),
            id=self._base_id,
        ).strip()

    #
    # Review page
    #
    def _build_review_page(self, body: Box) -> Box:
        host = self._gui
        size = self._review_text_size
        page = Box(body, align="top", border=0)
        self._label(page, REVIEW_TITLE, size=host.s_16, bold=True)
        # Half a line of white space, and half a line only: what stands under the heading is
        # the first thing to be done rather than the next thing on the page, so it belongs to
        # the heading above it. See REVIEW_HEADING_GAP.
        host.add_vspace(page, self._review_heading_gap)
        # Every line on this page is wrapped, and this is the page that most needs it: what
        # stands here is prose rather than a label -- how to put the module into program
        # mode, what will be pressed, what was asked for and what the module answered. The
        # instruction alone measured 2164px of the Pi's 480px pane, and an unwrapped line is
        # not cut short but centered, so it loses its beginning and its end at once.
        #
        # Read at this page's own size rather than a step below the body, which is where it
        # was set: it is the one line in the panel that has to be acted on before the button
        # below it will do anything. Two lines wide at every size the panel draws, so the
        # larger text costs the page nothing a smaller one would save; see _review_text_size.
        self._program_line = self._label(page, "", size=size)
        # And then the sequence itself, in a frame with a title on it. The list carries its
        # own line breaks, one per press; the wrap only breaks a press too long to stand on
        # one, which is why they are numbered. Read from the left edge of the box rather than
        # centered in it, a numbered list being read down its numbers; see _left_line.
        self._manual_config_box = self._build_manual_config_box(page)
        self._review_line = self._left_line(
            self._manual_config_box, size=size, wrap_px=self._manual_config_wrap_px, padx=MANUAL_CONFIG_PAD
        )
        # The one page the module's warning is read on now: held off the box above it and the
        # white space below by its own padding, which is what _note_line adds to the wrap the
        # rest of the page has. See review_note.
        self._review_note_line = self._note_line(page, size=host.s_12)
        # White space either side of the key, so it stands apart from the steps it sends and
        # from the read-back it writes below. The page's own gap, which is what holds any two
        # sections of a page in the panel apart; see PAGE_GAP.
        host.add_vspace(page, self._page_gap)
        # And the key on a row of its own, with the scroll bar's gutter beside it, so it
        # stands on the same centerline as the Back, Next and Close below the page rather
        # than half a bar to the left of them; see _build_key_row.
        self._configure_key_row = row = self._build_key_row(page)
        self._configure_btn = btn = HoldButton(row, text=CONFIGURE_TEXT, align="left", command=self.on_configure)
        # The one shared look for the big buttons of an overlay, which Back, Next and the
        # Close below them all wear: a raised border and an edge, a lighter face than the
        # panel, and a darker one while it is held. Set by its text size alone, this was the
        # only key in the panel drawn flat -- a rectangle with a word in it -- which is a
        # poor way to draw the one key that programs a module.
        #
        # Its pack padding is then trimmed exactly as the Back/Next row's is: the band a
        # footer button carries is meant to hold a row off the panel and the pane, and this
        # button stands in the middle of a page with white space of its own above and below.
        # See style_footer_button and NAV_ROW_PAD.
        style_footer_button(host, btn)
        repad_footer_button(btn, pady=self._nav_row_pad)
        host.cache(btn)
        host.add_vspace(page, self._page_gap)
        # How to put the module into program mode, what was asked of it, and what it said
        # back -- the last two arriving after Configure, at whatever length the module's own
        # report runs to.
        self._footnote_line = self._label(page, "", size=host.s_12)
        self._requested_line = self._label(page, "", size=host.s_12)
        self._reported_line = self._label(page, "", size=host.s_12)
        # And the verdict drawn from those two: whether the module came back holding what it
        # was sent. Below them, because it is the conclusion of reading them, and in bold at
        # the largest size the panel sets anything -- three above the page's body, and it was
        # set at the body -- because it is the one line on this page an operator is waiting
        # for, and they are reading it from wherever they were standing to hold the module's
        # button. It says nothing until Configure is pressed and takes no room while it says
        # nothing; see _status_text_size and _show_status.
        self._status_line = self._label(page, "", size=self._status_text_size, bold=True)
        self._status_line.hide()
        return page

    def _build_manual_config_box(self, page: Box) -> TitleBox:
        """The frame the presses are listed in, drawn to a width the page decides.

        Gridded into a column of its own rather than packed onto the page, which is the only
        way a box gets that: a packed box is as wide as whatever is inside it, and what is
        inside this one is "1. ACC 1 SET" -- a frame a third of the pane wide, with a title
        longer than the list under it.

        The width is the page's prose width rather than the floor the ID page's three boxes
        share, so the block stands in a margin either side instead of on the page's edge; see
        _manual_config_px, and MANUAL_CONFIG_PAD for the margin inside the frame.

        Titled at the size of what it holds, as those boxes are: a title set two sizes below
        its own list reads as fine print on it.
        """
        container = Box(page, layout="grid", align="top", border=0)
        self._manual_config_grid = container
        box = TitleBox(container, text=MANUAL_CONFIG_TITLE, grid=[0, 0], align=None)
        box.text_size = self._review_text_size
        self._manual_config_box = box
        self._stretch_manual_config()
        return box

    def _stretch_manual_config(self) -> None:
        """Give the Manual Configuration box its width, and give it back after a refresh.

        Replayed on every refresh for the reason _lay_out_titled_boxes is: guizero rebuilds
        a container's grid options from scratch in display_widgets, which runs whenever a
        child of that container is created, shown or hidden, and sticky is not among the
        options it replays. Nothing in this container is hidden today -- it holds the one box
        -- so this is what keeps that from being a fact the page depends on.
        """
        container, box = self._manual_config_grid, self._manual_config_box
        if container is None or box is None or not box.visible:
            return
        try:
            container.tk.grid_columnconfigure(0, weight=1, minsize=self._manual_config_px)
            box.tk.grid_configure(sticky="ew")
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    def _left_line(self, parent: Box, size: int | None = None, wrap_px: int = None, padx: int = 0) -> Text:
        """A line that reads from the left edge of what it stands in, not from its middle.

        Every other line of prose the panel writes is centered, and a numbered list cannot
        be: it is read down its numbers, and centered lines start each of them somewhere
        else -- which is how the presses read before they were given a box to stand in.

        Stretched to its container and its text anchored west, which is the pair the
        listing's stacked cells use and for the same reason: a label narrower than what it
        stands in is centered in it however its own lines are justified, so justify alone
        would only line up the second line of a press under the first. Both survive a
        re-pack -- "fill" is read off the widget by guizero itself, and the anchor is a Tk
        option rather than a layout one. See _cell_label.

        wrap_px is for a line that does not have the page to itself: what stands inside a
        frame is broken at that frame's width and not the pane's, or it is broken by the
        frame instead. padx is the white space it keeps from that frame's edge, which is
        also a Tk option and so survives with the rest. See MANUAL_CONFIG_PAD.
        """
        line = self._label(parent, "", size=size, width="fill")
        self._wrap(line, justify="left", width=wrap_px)
        try:
            line.tk.config(anchor="w", padx=padx)
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass
        return line

    #
    # My Modules listing
    #
    def _build_inventory_page(self, body: Box) -> Box:
        """Every LCS module the panel knows of, gridded and sortable.

        A page that asks nothing and answers one question: what is out there. It is opened
        from the device page and left by Back, and Next never reaches it; see PAGE_INVENTORY.

        Three parts, in the order they are read: the heading, the keys that order the rows,
        and the rows. The sort keys stand above what they order rather than below it -- they
        are read before the list is, and a page that can be re-ordered says so at its head --
        and they are one row of radios in a titled box, exactly as the roster panel's own
        Sort By is drawn, so the two pages are sorted the same way by the same-looking key.

        Every word on the page is set at the page's own body size, which is a size above what
        the titled boxes of the ID page are drawn at on the Pi: the keys read as the rows they
        order, and the heading a size above both. See _inventory_text_size.
        """
        host = self._gui
        size = self._inventory_text_size
        page = Box(body, align="top", border=0)
        self._label(page, INVENTORY_TITLE, size=host.s_16, bold=True)

        sort_box = TitleBox(page, text=INVENTORY_SORT_TITLE, align="top")
        sort_box.text_size = size
        self._sort_group = CheckBoxGroup(
            sort_box,
            size=size,
            options=[[label, key] for label, key in INVENTORY_SORTS],
            selected=self._sort_key,
            align="top",
            style="radio",
            # Side by side: three short words, and stacked they would cost the listing three
            # rows of the height it wants for modules.
            horizontal=True,
            padx=SORT_ROW_PAD,
            pady=self._mode_row_pad,
            # Broken inside the pane like every other row the panel draws, though no sort
            # key is anywhere near long enough to need it: what a row may not do is run off
            # the edge of the screen, and that is a rule about rows rather than about the
            # words in these three.
            wrap=self._row_wrap_px(size),
            # Stepped by the pad like every other list in the panel. It is the only control
            # on this page, so it is the only thing a Deck could be pointing at here.
            cursor=pad_driven(),
            command=self._on_sort_selected,
        )

        host.add_vspace(page, self._page_gap)
        self._inventory_grid = Box(page, layout="grid", align="top", border=0)
        # The headings are the grid's own first row rather than a row of their own above it,
        # which is what makes them sit over the columns they name: a separate box would be
        # laid out to its own widths and stand over nothing in particular.
        self._build_inventory_headings()
        # And, where there are no rows, the line that says so -- below the grid, where the
        # first row would have been.
        self._inventory_empty_line = self._note_line(page, size=size)
        self._refresh_inventory()
        return page

    def _build_inventory_headings(self) -> None:
        """
        Write the column headings into the listing's first row, and keep them there.
        """
        for cell, text in zip(self._inventory_row_cells(0), INVENTORY_HEADINGS):
            cell.value = text
            # All four, where a data row bolds only its first: a heading is a heading in
            # every column, and it is what tells the top row from the modules under it.
            cell.text_bold = True

    def _inventory_row_cells(self, index: int) -> tuple[GridCell, ...]:
        """
        The cells of one line of the listing, headings included, created as they are needed.
        """
        return self._grid_row(
            self._inventory_grid,
            self._inventory_cells,
            index,
            columns=INVENTORY_COLUMNS,
            wrap_column=INVENTORY_CONFIG_COLUMN,
            wrap_px=self._inventory_config_wrap_px,
            # The one column in either grid whose text comes in groups, and so the one cell
            # that is a stack of them rather than a label; see GroupedCell.
            group_gap_px=INVENTORY_GROUP_GAP_PX,
            # And the one grid drawn at the page's body size wherever it is drawn, the module
            # rows following the boxes they stand in; see _inventory_text_size.
            size=self._inventory_text_size,
        )

    @property
    def _inventory_config_wrap_px(self) -> int:
        """The width the configuration column breaks a line at.

        What is left of the page once the three bounded columns beside it have taken their
        room, exactly as a module row's name column is measured; see _row_name_wrap_px and
        INVENTORY_FIXED_COLUMNS_EMS. The floor is an equal share of the four columns, for a
        pane so narrow that the reservation would swallow the column -- a column told to
        break at zero is a column told not to break at all, which would carry the longest
        line a module can write straight off the edge of the pane.

        Taken with the listing's own size rather than the titled boxes', which is what the
        larger text on this page is paid for with: the column breaks at 250px where the
        smaller text left it 276. See _inventory_text_size.
        """
        reserved = INVENTORY_FIXED_COLUMNS_EMS * self._inventory_text_size
        return max(self._wrap_px // INVENTORY_COLUMNS, self._wrap_px - reserved)

    def show_inventory(self) -> None:
        """
        Open the listing, built afresh from what the layout says right now.

        Written on the way in rather than kept up to date behind the page: modules report
        themselves as the Base 3 gets round to them, and what the operator is owed is a
        listing that is true when they ask for it. Coming back to the page asks again.
        """
        self._refresh_inventory()
        self._show_page(PAGE_INVENTORY)

    def _on_sort_selected(self, value: str = None) -> None:
        """Re-order the listing. guizero hands the row's value in; the pad's mark reads it here.

        A key the page does not offer is ignored rather than taken: the value comes from a Tk
        StringVar, which answers with whatever string it was handed.
        """
        if value is None and self._sort_group is not None:
            value = str(self._sort_group.value)
        if value in {key for _label, key in INVENTORY_SORTS}:
            self._sort_key = value
        self._refresh_inventory()
        # The rows are as tall as their longest configuration cell, so re-ordering them
        # re-orders the page's height as well: what the window has to hold is measured again
        # rather than left at what the last order needed.
        self._fit_scroll()

    def _refresh_inventory(self) -> None:
        """Write the modules into the grid, growing it and hiding what is spare.

        Row 0 is the headings and is written once, so the modules start at row 1 and the
        spare rows begin one past the last of them. Hidden rather than blanked, for the
        reason the module grids hide theirs: an empty label still stands a line tall, and
        the page would keep the height of the fullest layout it had ever shown.

        The headings go with the rows. A grid standing empty under Module / ID / Scope reads
        as a page that looked and failed, where what is true is that nothing has reported
        itself -- which the line below says in words.

        The rows are put back against the top of their cells last of all, showing and hiding
        being what takes them off it; see _stick_inventory_cells.
        """
        if self._inventory_grid is None:
            return
        rows = self.inventory_rows()
        for index, row in enumerate(rows, start=1):
            for cell, value in zip(self._inventory_row_cells(index), row.cells):
                cell.value = value
                if not cell.visible:
                    cell.show()
        for spare in self._inventory_cells[len(rows) + 1 :]:
            for cell in spare:
                if cell.visible:
                    cell.hide()
        self._show_inventory_headings(bool(rows))
        self._stick_inventory_cells()
        self._refresh_note(self._inventory_empty_line, "" if rows else INVENTORY_EMPTY)

    def _stick_inventory_cells(self) -> None:
        """Stand every cell of the listing against the top of its row, and keep it there.

        Replayed over the whole grid rather than set once where a cell is built, for the
        reason _lay_out_titled_boxes replays its own: guizero rebuilds a container's grid
        options from scratch in display_widgets -- which runs whenever a child is shown,
        hidden or created -- and grids each cell from its align, i.e. sticky="W". Every
        re-order of the listing shows and hides rows, so the alignment has to follow the
        rows rather than the building of them. See INVENTORY_STICKY.

        A hidden cell is passed over, and that is not an optimization: grid_configure
        *manages* a widget the grid has forgotten, so a spare row put back on the page would
        come back carrying the text of the fuller layout it was last written for. The same
        trap restore_footer_packing avoids with a hidden button.
        """
        for row in self._inventory_cells:
            for cell in row:
                if not cell.visible:
                    continue
                try:
                    cell.tk.grid_configure(sticky=INVENTORY_STICKY)
                except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                    continue

    def _show_inventory_headings(self, showing: bool) -> None:
        """
        Put the column headings on the page, or take them off it with their rows.
        """
        for cell in self._inventory_cells[0] if self._inventory_cells else ():
            if showing and not cell.visible:
                cell.show()
            elif not showing and cell.visible:
                cell.hide()

    def inventory_rows(self) -> list[InventoryRow]:
        """
        Every module the layout has reported, as the listing writes them, in sorted order.
        """
        return [
            InventoryRow(
                module=self._inventory_module(occupant.device),
                tmcc_id=f"{occupant.base_id}",
                scope=self._scope_label(occupant.effective_scope),
                config=self.inventory_config(occupant),
            )
            for occupant in self.inventory_occupants()
        ]

    @staticmethod
    def _inventory_module(device: LcsDevice) -> str:
        """
        What the listing calls a module: its own name for it, where it has one, and the
        registry's everywhere else. See INVENTORY_MODULE_NAMES.
        """
        return INVENTORY_MODULE_NAMES.get(device.key, device.label)

    def inventory_occupants(self) -> list[LcsOccupant]:
        """Every module known to the panel, ordered by whichever key is chosen.

        The whole layout, not the entered ID's block: this page is the one place the panel
        speaks about modules it is not programming. See occupants().
        """
        return sorted(occupants(self._store), key=self._inventory_key)

    def _inventory_key(self, occupant: LcsOccupant) -> tuple:
        """What a row is ordered by, and what settles it where two rows agree on that.

        Always all three, in the order the chosen key puts them: two BPC2s are then listed
        by address, and two modules at ID 5 by name, rather than in whatever order the store
        happened to hand them over -- an order that would change under the page as the
        layout reported itself. The key chosen leads, and the other two follow it in the
        order the columns are read.

        A module is ordered by the name the listing gives it rather than by the registry's,
        so the rows come out in the order the Module column reads down the page; see
        _inventory_module. A remote key is ordered by where it stands among the keys rather
        than by its spelling, so the listing groups ACC, SW, TR and ENG the way the panel
        names them everywhere else; see SCOPE_ORDER.
        """
        module = self._inventory_module(occupant.device).upper()
        tmcc_id = occupant.base_id
        scope = self._scope_rank(occupant.effective_scope)
        if self._sort_key == SORT_ID:
            return tmcc_id, module, scope
        if self._sort_key == SORT_SCOPE:
            return scope, module, tmcc_id
        return module, tmcc_id, scope

    @staticmethod
    def _scope_rank(scope: CommandScope | None) -> tuple[int, str]:
        """
        Where a remote key stands in the listing, with its own name to settle an unknown one.
        """
        order = SCOPE_ORDER.index(scope) if scope in SCOPE_ORDER else len(SCOPE_ORDER)
        return order, f"{scope}"

    def inventory_config(self, occupant: LcsOccupant) -> str:
        """What a module says about itself, as the listing's last column writes it.

        One fact a line, and the lines in the order they answer the operator's questions:
        which mode the module is in, which addresses that mode takes from it, and what each
        of its own settings is set to. What it is set to and nothing else: its firmware is a
        fact about the module rather than about its configuration, and this column is read
        to see how a layout is addressed. See INVENTORY_MODE_UNKNOWN.

        And nothing the columns beside it have already said. This is the row's fourth column,
        not a summary of the module standing on its own: a line saying only what Module, ID
        and Scope say between them is read as a fact about the module and turns out to be an
        echo, and it costs a line of a column that is already the tallest thing on the page.
        Two lines can come out that way, each dropped by being compared with the very text the
        column beside it carries rather than by any rule about how it is spelled:

        - The mode, where the mode's whole name is the remote key -- a BPC2 in ACC mode, an
          IR Sensor Track, an AMC2. A mode named for what it is *for* stays, all of it: "ACC
          (mixed)" and "SW (pulse)" answer which of the module's modes it is in, which is
          the question the line is there for and one no other column touches.
        - The block, where the block is the one address the ID column names. "ACC 50" beside
          a row reading IR / 50 / ACC is those two columns again; "ACC 1 - 8" is not,
          being the seven further addresses the module has taken.

        A block that is kept is spelled with the remote key in front of it -- "ACC 1 - 8" --
        though the Scope column names the key. The line is about a block of addresses on a
        key, which is how a module's address is said everywhere else in the panel and how
        the manuals say it; see options_summary, which writes the same words about the module
        being programmed. What is dropped is a whole line that said nothing, not a word out
        of the middle of one that says something.

        Only what the module has actually reported. A module known from control traffic
        alone has published no CONFIG record, so it names no mode and no settings, and the
        listing says the one and passes over the others rather than inventing either. That
        the mode is not known is not an echo of anything, so it is said even where the
        block below it is dropped.
        """
        mode = occupant.mode
        scope = self._scope_label(occupant.effective_scope)
        lines: list[str] = []
        if mode is None:
            lines.append(INVENTORY_MODE_UNKNOWN)
        elif mode.name != scope:
            lines.append(mode.name)
        span = tmcc_id_span(occupant.base_id, occupant.last_id)
        if span != f"{occupant.base_id}":
            lines.append(" ".join(part for part in (scope, span) if part))
        lines.extend(self._inventory_settings(occupant))
        return "\n".join(lines)

    @classmethod
    def _inventory_settings(cls, occupant: LcsOccupant) -> list[str]:
        """A line per setting the module reports, named as the options page names it.

        Read through the options themselves, off the module's own CONFIG record first and
        its component state second, so the listing learns what a module is set to exactly
        as the options page learns what to open on; see _reported_option. A setting the
        module says nothing about is passed over rather than written up at its default,
        which would be the panel telling the operator something the module has not said.

        Named as the listing names it, which is the setting's own label unless this column
        has a shorter one for it; see _inventory_option_name. Its own label and nothing in
        front of it: a verdict puts the heading a setting stands under in front of one the
        module labels twice, and here that heading is already on the page. This column
        writes every setting the module reports, in the module's own order, so the setting
        the heading comes from is the line directly above -- an AMC2 reads as "Motor #1: AC"
        and the flag beneath it, then the same pair for the second motor, and naming the
        motor in the flag's line as well would say twice over what one line up has just said.

        Which is why the groups are held apart: a heading that opens one is given an empty
        line above it, so the second motor begins rather than continuing the first. The one
        above the first group would be white space under the block of addresses, which
        nothing is grouped away from, so it is only ever written between them. See
        INVENTORY_GROUP_GAP and _inventory_group_heads.
        """
        device = occupant.device
        heads = cls._inventory_group_heads(device)
        lines: list[str] = []
        for option in device.options:
            value = cls._reported_option(option, occupant.config, occupant.state)
            if value is None:
                continue
            if lines and option.key in heads:
                lines.append(INVENTORY_GROUP_GAP)
            lines.append(
                INVENTORY_SETTING.format(
                    name=cls._inventory_option_name(device, option),
                    value=cls._value_text(option, value),
                )
            )
        return lines

    @classmethod
    def _inventory_group_heads(cls, device: LcsDevice) -> set[str]:
        """The keys of the settings other settings of the module stand under.

        The headings, that is, and read off the same rule a verdict names a setting by, so
        the two cannot come to disagree about what heads what: a heading is whatever
        _option_heading finds above a setting the module labels ambiguously. The AMC2 has
        two of them, one per motor; every other module the registry holds has none, and its
        settings are written as the one block they are.
        """
        headings = (cls._option_heading(device, option) for option in device.options)
        return {heading.key for heading in headings if heading is not None}

    @staticmethod
    def _inventory_option_name(device: LcsDevice, option: LcsOption) -> str:
        """
        What the listing calls a setting: its own name for it, where it has one, and the
        label the options page draws everywhere else. See INVENTORY_OPTION_NAMES.
        """
        return INVENTORY_OPTION_NAMES.get((device.key, option.key), option.label)

    @classmethod
    def _value_text(cls, option: LcsOption, value: Any) -> str:
        """
        What a reported value reads as: the row's own words for a choice, Yes or No for a flag.
        """
        if option.kind == OptionKind.RADIO:
            return cls._choice_label(option, value)
        return INVENTORY_YES if value else INVENTORY_NO

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
        """What to know before pressing Configure: the module's own warning.

        The BPC2's warning is read here and nowhere else, where it used to stand at the head
        of the options page as well. It is not about the settings being chosen but about what
        the presses themselves do -- every track-block relay goes off, and has to be switched
        back on by hand afterwards -- so it belongs on the page they are sent from, in front
        of the button that sends them.

        The one module with a warning is the BPC2, so this is that sentence or nothing. The
        Sensor Track's own caveat -- that its sequence is only complete once the Action
        Command has been assigned -- used to stand here beside it and is no longer drawn: the
        sequence it is about is now listed step by step in a frame of its own two lines up,
        which is where an operator reads what has and has not been done. See
        MANUAL_CONFIG_TITLE.
        """
        warning = self._device.warning if self._device is not None else None
        return warning or ""

    @property
    def footnote(self) -> str:
        if self._device is None:
            return ""
        return PROGRAM_MODE_NOTE.format(module=self._device.label)

    def _refresh_review_page(self) -> None:
        program = self.program
        if self._program_line is not None:
            self._program_line.value = program.program_instruction if program else ""
        if self._review_line is not None:
            self._review_line.value = "\n".join(program.display) if program else ""
        # The steps' frame keeps its own width, whatever guizero has re-gridded since the
        # last refresh; see _stretch_manual_config.
        self._stretch_manual_config()
        self._refresh_note(self._review_note_line, self.review_note)
        if self._footnote_line is not None:
            self._footnote_line.value = self.footnote
        if self._configure_btn is not None:
            self._enable(self._configure_btn, self.can_configure)

    #
    # Configure
    #
    # The submit guard below is what makes the two loops safe, but a callable checked against
    # None reads as None again to PyCharm once the call is inside a loop.
    # noinspection PyCallingNonCallable
    def on_configure(self) -> None:
        """
        Emit the presses, then ask the module to report what it now holds.
        """
        program = self.program
        if program is None:
            return
        host = self._gui
        submit: Callable[..., Any] | None = getattr(host, "submit_request", None)
        if submit is None:  # pragma: no cover - every real host queues requests
            log.warning("Host cannot queue requests; LCS presses not sent")
            return
        # One request per key, so a gesture entering a digit is two of them, and the stagger
        # falls between the AUX key and the number exactly as it falls between any two
        # presses -- which is what makes them two keystrokes rather than one command; see
        # Press.build and PRESS_DELAY.
        for i, request in enumerate(program.presses):
            submit(request, 1, i * PRESS_DELAY)
        # And then the module is asked what it now holds, once the presses have had their
        # moment to land and again on the beat until the wait is up; see _verify_times.
        for at in self._verify_times(len(program.presses)):
            for j, request in enumerate(program.verify):
                submit(request, 1, at + j * PRESS_DELAY)

        self._sent_program = program
        self._readback_pending = True
        if self._requested_line is not None:
            self._requested_line.value = REQUESTED.format(summary=self.requested_summary)
        if self._reported_line is not None:
            # Emptied rather than filled with a line about waiting: what the module said is
            # this line's business, and it has not said anything yet. The waiting is the
            # status line's, which says what the waiting is for.
            self._reported_line.value = ""
        self._show_status(VERIFYING.format(module=program.device.label), VERIFYING_FG)
        self._watch_readback(program)
        self._schedule(READBACK_TIMEOUT_MSEC, self.on_readback_timeout)

    @staticmethod
    def _verify_times(presses: int) -> list[float]:
        """When to ask the module what it now holds, in seconds from the first press.

        Once the last press has had VERIFY_DELAY to land, and then again on
        VERIFY_POLL_DELAY for as long as the panel is going to wait on the answer. Every ask
        falls inside READBACK_TIMEOUT_MSEC: past that the panel has written its verdict, and
        a question asked then could only be answered later still. At least one is sent
        however long the sequence itself runs, because a module still has to be asked.

        The panel stops asking there; it does not stop listening. A module put into program
        mode late reports of its own accord, and the state watcher outlives the timeout, so
        an answer that does arrive is still read and still judged.

        The sequence's own length is what makes this worth computing rather than fixing: the
        presses are staggered, so an AMC2's six keys are 2.1 seconds of the 5 the panel
        waits before the first GET can even go out.
        """
        after_presses = presses * PRESS_DELAY + VERIFY_DELAY
        budget = READBACK_TIMEOUT_MSEC / 1000 - after_presses
        asks = max(1, int(budget / VERIFY_POLL_DELAY) + 1)
        return [after_presses + ask * VERIFY_POLL_DELAY for ask in range(asks)]

    def _schedule(self, msec: int, action: Callable[[], None]) -> None:
        app = getattr(self._gui, "app", None)
        if app is None:
            return
        try:
            app.after(msec, action)
        except Exception as e:  # pragma: no cover - defensive; Tk may be tearing down
            log.debug("Could not schedule LCS read-back timeout: %s", e)

    # noinspection PyCallingNonCallable
    def readback_state(self, program: LcsProgram | None = None) -> Any:
        """
        The component state the module's read-back lands in, if the store holds one.
        """
        program = program or self._sent_program
        store = self._store
        if program is None or store is None:
            return None
        get_state: Callable[..., Any] | None = getattr(store, "get_state", None)
        if get_state is None:
            return None
        scopes = [CommandScope.IRDA] if program.device is SENSOR_TRACK else [program.mode.scope]
        for scope in scopes:
            # noinspection PyBroadException
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
            # noinspection PyBroadException
            try:
                watcher.shutdown()
            except Exception:  # pragma: no cover - defensive
                pass

    # noinspection PyCallingNonCallable
    def _on_readback_changed(self) -> None:
        # Runs on the watcher thread; the display is touched on the Tk thread only.
        queue_message: Callable[..., Any] | None = getattr(self._gui, "queue_message", None)
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
            self._reported_line.value = REPORTED.format(summary=self.reported_text(state))
        self._show_verification(self.verification())

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
        # Nothing was heard, so nothing is judged: the verdict is that the module did not
        # report, whatever the stores may still hold about it from before the presses. A
        # module that answers on one side of the store and not the other is read the other
        # way round -- see on_readback, which judges whatever did arrive.
        self._show_verification(Verification())

    #
    # Verification: what the module reports, held against what was sent
    #
    def verification(self, program: LcsProgram | None = None) -> Verification:
        """Whether the module came back holding what the presses gave it.

        Configure is a handset gesture and nothing more -- the panel writes nothing over PDI
        -- so the module's own report is the only evidence a sequence was taken, and the
        only useful reading of that report is against what was sent. A module that was never
        put into program mode takes none of the sequence and reports exactly what it always
        held, which is a perfectly healthy-looking read-back and the commonest way for a
        programming pass to fail.

        Three things are compared. Its address and remote key, by the lookup itself: the
        module is asked for at the address and on the key the presses set, so being found at
        all is that part of the answer. The mode it reports. And every setting this mode's
        presses actually set, which is not always every setting the module has; see
        programmed_options.

        All of it read in the module's own terms, through the same two accessors the options
        page seeds itself with, so the panel understands a read-back exactly as well as it
        understands a module it comes across on the layout.

        A setting the module says nothing about is passed over rather than faulted: a record
        that has not been answered says nothing, and nothing is not disagreement -- the same
        rule the seeding follows. Nothing being found at all is the one silence that is not
        passed over, because that is the module failing to answer for itself entirely.
        """
        program = program or self._sent_program
        if program is None:
            return Verification()
        occupant = self._programmed_occupant(program)
        if occupant is None:
            return Verification()
        differs: list[str] = []
        if occupant.mode is not None and occupant.mode is not program.mode:
            # Named by the box the mode was chosen in, as every other line is named by the
            # thing that set it.
            differs.append(MODE_TITLE)
        records = (occupant.config, occupant.state)
        for option in programmed_options(program.device, program.mode):
            reported = self._reported_option(option, *records)
            if reported is not None and reported != program.options.get(option.key):
                differs.append(self._option_name(program.device, option))
        return Verification(reported=True, differs=tuple(differs))

    @classmethod
    def _option_name(cls, device: LcsDevice, option: LcsOption) -> str:
        """What to call a setting on a line that may have to name several of them.

        Its own label, which is what the options page draws it as -- except where the module
        gives two settings the same one. The AMC2 does: both its motors carry "Remember speed
        on power-up", worded for the room a Pi's page has rather than for being read out of
        context, and told apart on the page by the bold motor heading each stands under. So
        the heading comes with it here, and a verdict faulting both motors reads as two
        faults rather than as one written twice.

        A verdict names the settings that disagree and nothing else, so the heading has to
        travel with the one it belongs to. The My Modules listing, which writes every setting
        in turn, has the heading a line above and names a setting by itself; see
        _inventory_option_name.
        """
        heading = cls._option_heading(device, option)
        if heading is None:
            return option.label
        return f"{heading.label} {option.label[0].lower()}{option.label[1:]}"

    @staticmethod
    def _option_heading(device: LcsDevice, option: LcsOption) -> LcsOption | None:
        """The setting option stands under on the options page, where it needs one.

        None where the module names the setting uniquely, which is every setting of every
        module bar the AMC2's two remember flags: a setting that can be told from its
        fellows by its own label needs nothing in front of it and heads nothing itself.

        The heading is the nearest setting above it the module does name uniquely, which is
        what the page puts there; nothing is assumed about which settings a module groups.
        Read by _option_name, which puts it in front of a setting it names on a line of its
        own, and by _inventory_group_heads, which holds the groups it marks apart.
        """
        labels = [other.label for other in device.options]
        if labels.count(option.label) < 2:
            return None
        index = next((i for i, other in enumerate(device.options) if other is option), 0)
        return next(
            (other for other in reversed(device.options[:index]) if labels.count(other.label) == 1),
            None,
        )

    def _programmed_occupant(self, program: LcsProgram) -> LcsOccupant | None:
        """The module the program was aimed at, as the layout reports it now.

        A module of the type programmed, based at the address it was programmed to, on the
        key it was programmed on -- which are the three things the presses set, so a module
        that took none of them is not found here at all. _based_here is the same rule asked
        about the panel's current selection; this one is asked about the sequence that went
        out, and the two part company as soon as the operator turns a page.
        """
        for occupant in occupants_of(program.base_id, self._store, scope=program.mode.scope):
            if occupant.device is program.device and occupant.base_id == program.base_id:
                return occupant
        return None

    def verification_text(self, verification: Verification) -> str:
        """The line a verdict is written on: one word for success, three parts for anything else.

        A failure says what is wrong and what to do about it, and what to do is the same
        either way -- the module only takes a sequence while it stands in program mode, and
        nothing the panel can send puts it there. The button that does is named from the
        registry, since it is a PGM key on most modules and a PROGRAM key on the Sensor
        Track, and an operator told to press a button their module has not got is worse off
        than one told nothing.
        """
        if verification.passed:
            return VERIFIED
        program = self._sent_program
        device = program.device if program is not None else self._device
        reason = NOT_AS_SENT.format(items=", ".join(verification.differs)) if verification.differs else NOT_REPORTED
        retry = VERIFY_RETRY.format(module=device.label, button=device.program_button) if device is not None else ""
        return UNVERIFIED_LINE.format(verdict=UNVERIFIED, reason=reason, retry=retry).strip()

    def _show_verification(self, verification: Verification) -> None:
        self._show_status(
            self.verification_text(verification),
            VERIFIED_FG if verification.passed else UNVERIFIED_FG,
        )

    def _show_status(self, text: str, color: str) -> None:
        """Write the status line in the color what it says is worth, or take it off the page.

        Colored on every write rather than once: the line is the same widget throughout a
        programming pass -- asking, then answered -- and a red left over from the last pass
        would color the next one's polling line as a failure.
        """
        if self._status_line is not None:
            self._status_line.text_color = color
        self._refresh_note(self._status_line, text)
        if text:
            self._reveal_status()

    def _reveal_status(self) -> None:
        """Bring the status line into the window the pages are drawn in.

        A page can be taller than that window -- the Sensor Track's review page is, on a Pi,
        by 128px -- and this line is the last thing on it, so the answer the operator is
        standing there waiting for would arrive below the fold. Moved by as little as it
        takes, which is the same courtesy the pad's highlight gets; see ScrollBox.show_widget.

        Queued rather than done here, because the line has only just been shown: Tk lays the
        page out around it on the next idle, and until it has, every reading of where the line
        now is answers where it was while it was still hidden.
        """

        def reveal() -> None:
            self._fit_scroll()
            if self._scroll is not None and self._status_line is not None:
                self._scroll.show_widget(self._status_line)

        queue: Callable[..., Any] | None = getattr(self._gui, "queue_message", None)
        if queue is None:
            reveal()
        else:
            queue(reveal)

    def reported_text(self, state: Any) -> str:
        """
        What the module says it now holds, in the panel's own terms.
        """
        program = self._sent_program
        device = program.device if program else self._device
        label = device.label if device else "Module"
        address = getattr(state, "address", None) or getattr(state, "tmcc_id", None)
        parts = [REPORTED_AT.format(module=label, id=address)]
        # The registry's scope for the selected mode, never the parsed scope: a
        # mode-3 ASC2 is mis-scoped by asc2_req.py.
        mode = program.mode if program else self._mode
        if mode is not None:
            parts.append(SCOPE_LABEL.get(mode.scope, ""))
        num_ids = getattr(state, "num_ids", None)
        if isinstance(num_ids, int) and num_ids > 0:
            parts.append(REPORTED_IDS.format(count=num_ids))
        if device is SENSOR_TRACK:
            # The field the Action Command is reported on, asked of the option rather than
            # spelled here, so the panel reads a read-back the same way it reads the module
            # in the first place; see LcsOption.reported_by.
            sequence = SENSOR_TRACK.option("action").reported_by(state)
            if sequence is not None:
                parts.append(self._choice_label(SENSOR_TRACK.option("action"), sequence))
            parts.append(f"R\u279fL {self._filter_text(state, 'loco_rl')}")
            parts.append(f"L\u279fR {self._filter_text(state, 'loco_lr')}")
        elif device is AMC2:
            parts.extend(self._motor_readback(state))
        return ", ".join(part for part in parts if part)

    @classmethod
    def _motor_readback(cls, state: Any) -> list[str]:
        """What an AMC2 says each of its motors is now set to: "Motor #1 AC (remembers)".

        The mode it runs in and, where it is set, that it comes back up at the speed it was
        turning -- the two things the panel programmed for that output, read back off the
        module in the same words the options page offered them in.

        A motor the record says nothing about is passed over rather than reported as unset:
        an AccessoryState built before the module answered carries no motors at all, and a
        line inventing a mode for one would be the panel telling the operator something the
        module has not said. Read through the options themselves, so the field each is on is
        named once in the registry; see LcsOption.reported_by.
        """
        lines: list[str] = []
        for motor in (1, 2):
            mode = AMC2.option(f"motor{motor}_mode")
            value = mode.reported_by(state)
            if value is None:
                continue
            line = f"{mode.label} {cls._choice_label(mode, value)}"
            if AMC2.option(f"motor{motor}_restore").reported_by(state):
                line = f"{line} (remembers)"
            lines.append(line)
        return lines

    @staticmethod
    def _filter_text(state: Any, key: str) -> str:
        value = getattr(state, key, None)
        if value is None:
            value = getattr(state, f"_{key}", None)
        return "Any" if value in (None, 255) else f"{value}"

    @staticmethod
    def _choice_label(option: LcsOption, value: Any) -> str:
        """
        What the option's own rows call a value, so a read-back is read in the page's words.
        """
        for label, choice in option.choices:
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
        """Every mode the module offers, each named with the block it would claim.

        The labels move with the entered ID, which is why the group is rebuilt on every
        refresh of the page: what is being chosen here is a block of TMCC IDs, so the row
        names the addresses the operator would be setting aside rather than a count they
        have to add to the ID above it. A mode that cannot be based this high is offered
        at the highest base it fits, which is where choosing it lands; see
        LcsMode.ids_label().
        """
        if self._device is None:
            return []
        return [[mode.ids_label(self._base_id), mode.key] for mode in enabled_modes(self._device)]

    def mode_leads(self) -> dict[str, int]:
        """How far a mode row is held off the row above it, for the rows that ask.

        Only the first row of a new remote key does: an ASC2 lists two ACC modes and then
        two SW modes, and what is being chosen is a key first and a mode on that key second,
        so the rows are grouped the way the legend above them is written -- a line per key.
        A module whose modes are all on one key, an STM2, asks for nothing.

        The grouping is read off the modes themselves rather than spelled out here, so a
        module's list is grouped by the order the registry gives it in; see
        CheckBoxGroup.row_leads for what the group does with this.
        """
        if self._device is None:
            return {}
        leads: dict[str, int] = {}
        previous: CommandScope | None = None
        for mode in enabled_modes(self._device):
            if previous is not None and mode.scope is not previous:
                leads[mode.key] = self._mode_key_lead
            previous = mode.scope
        return leads

    #
    # Page swapping
    #
    @property
    def skip_options(self) -> bool:
        """Whether the options page is stepped over rather than shown.

        A module that declares no options has nothing to settle there -- an ASC2 or an STM2
        today -- and the page it was given said as much: a heading, the line the operator
        had already read on the page before it, and a sentence stating there was nothing to
        do. A press to arrive at it and a press to leave, for no decision. Next now goes
        from the TMCC ID straight to the review, and Back comes straight back.

        The page is still built. Every page is created once in build and shown or hidden by
        index, so leaving it out would move the review page's index -- and every page is
        reached by index.
        """
        return self._device is not None and not self._device.options

    def _stepped_over(self, index: int) -> bool:
        """Whether index names a page this module has nothing to say on.

        The options page and no other, which is a different question from whether a page is
        on the march at all: this one is asked of the page the panel finds itself on, and a
        page the module cannot fill is one it must be moved off. See _skipped.
        """
        return index == PAGE_OPTIONS and self.skip_options

    def _skipped(self, index: int) -> bool:
        """Whether Back and Next pass over index rather than stopping on it.

        A page the module has nothing to say on, and the listing -- which is not a step of
        anything: it is opened from the device page by its own key and left by Back, and a
        Next that walked into it would carry the operator out of the sequence they are
        working through. See PAGE_INVENTORY and show_inventory.
        """
        return self._stepped_over(index) or index == PAGE_INVENTORY

    def _page_after(self, index: int, step: int) -> int:
        """The next page in step's direction that is not skipped.

        A loop rather than a single test, so that a second skippable page would need
        nothing here. It cannot run away: it walks off the end of the pages, and
        _show_page() clamps whatever it is handed.
        """
        index += step
        while 0 <= index < len(self._pages) and self._skipped(index):
            index += step
        return index

    def _show_page(self, index: int) -> None:
        if not self._pages:
            self._page_index = index
            return
        index = max(0, min(index, len(self._pages) - 1))
        if self._stepped_over(index):
            # Reachable only when the module changes under a page already showing, which a
            # late synchronization can do while the operator has chosen nothing for
            # themselves -- see on_synchronized. Backwards rather than forwards: nobody is
            # advanced past a page they have not seen.
            index = self._page_after(index, -1)
        self._page_index = index
        # A page turned is as far back as a revert reaches: the choice a mark displaced is on
        # the page that was left, and the operator looking at this one cannot see it put back.
        self._pad_undo = None
        for i, page in enumerate(self._pages):
            if i == index:
                page.show()
            else:
                page.hide()
        self._refresh_nav()
        # A page is come to at its beginning, whatever the page before it was scrolled to,
        # and the window is re-fitted for a page of a different height. In that order: the
        # fit clamps the offset to what the new page has, so scrolling first cannot leave the
        # window looking at white space below a shorter page.
        if self._scroll is not None:
            self._scroll.reset()
            self._fit_scroll()

    def next_page(self) -> None:
        """Turn to the next page, where there is one; the last page stays put.

        Asked before it is turned to rather than clamped after the fact: the pages walked
        off the end of are no longer the last of the list -- the listing sits past them --
        and a walk clamped to the list would arrive there. See _page_after.
        """
        index = self._page_after(self._page_index, 1)
        if index < len(self._pages):
            self._show_page(index)

    def previous_page(self) -> None:
        """Turn back a page. From the listing, back to the page it was opened from.

        The listing is off the march, so there is no page "before" it to walk to: what Back
        means there is done looking, which is the device page the key that opened it stands
        on. See PAGE_INVENTORY.
        """
        if self._page_index == PAGE_INVENTORY:
            self._show_page(PAGE_DEVICE)
            return
        self._show_page(self._page_after(self._page_index, -1))

    @property
    def has_next_page(self) -> bool:
        """Whether the panel has a page after this one at all: the rule Next is shown by.

        Asked apart from can_advance because the two say different things about the same
        button. There is a page after the first one whether or not a module has been chosen,
        so Next stands there grayed until one is; after the review page there is none, and a
        key that will never lead anywhere from the page it is on is taken off the row --
        Configure is what that page offers, on the page itself.

        Asked of the march rather than of the list of pages, the two no longer being the
        same thing: the listing is the last page built and is on nobody's way anywhere, so
        Next is off the row there as it is on the review page.
        """
        return self._page_after(self._page_index, 1) < len(self._pages)

    @property
    def can_advance(self) -> bool:
        """Whether the panel can go on to the page after this one.

        The rule the Next key is enabled by, asked as a question so the A button can ask it
        too: one answer for the key and the pad, rather than two that could come to disagree
        about whether the panel has anywhere left to go. A module has to be chosen -- there
        is nothing to configure until one is -- and the review page is the last: Configure is
        what is pressed there, which A asks can_configure for.
        """
        return self.has_next_page and self._device is not None

    @property
    def can_go_back(self) -> bool:
        """Whether there is a page before this one. The rule the Back key is shown by."""
        return self._page_index > 0

    @property
    def can_configure(self) -> bool:
        """Whether Configure is there to be pressed: the rule that button is enabled by.

        Asked as a question for the same reason can_advance is. A presses Configure on the
        review page, and it must be able to press nothing a finger could not: a complete
        program is what there is to send, and nothing is sent while the panel is running
        ahead of Base 3 synchronization, the layout it would be read against not being known
        yet.
        """
        return self.program is not None and not self._sync_pending

    #
    # Gamepad
    #
    # On the Steam Deck this panel is worked through with the pad rather than with the
    # screen: the D-pad steps the list on the page showing, right marks the row it is on --
    # and turns the page with it, on a page whose list is the whole of what it asks -- left
    # puts back what that mark displaced, A marks and turns the page, or presses Configure on
    # the review page, which has no page after it, B turns it back, and X closes the panel
    # the way it closes every other popup. Which key does what is
    # DeckInputRouter._config_panel_only; what each of those *means* is here, so the panel
    # decides and the router only asks.
    #
    # Every mark runs the very handler a tap on the same row runs, and by the same route: a
    # group's value assigned in code moves the dot and fires nothing, guizero binding a
    # command to the click, so the handler is called outright. That is what keeps a page from
    # coming out one way under a finger and another under the pad.
    def _pad_target(self) -> tuple[Any, Callable[[], None]] | None:
        """What the pad acts on for the page showing, and what a tap on it would run.

        One page, one question, one control: the modules on the first page, the modes on the
        second, the module's own setting on the third. The review page asks nothing of the
        operator -- it reports what was chosen and offers Configure -- so the pad steps
        nothing there.

        Both halves are answered here together rather than in the two readers below, so the
        highlight cannot be stepped along one control while the mark is committed through
        another's handler. The commit is the widget's own command, built by the same factory
        that wired it, and not a handler named again here for the purpose.

        A page's rows come before a lone tick box, which is the order of the only two cases
        there are: no module declares both, and a module that did would be stepped through
        its rows -- a tick box has nothing to step.

        Nothing at all while the ID is being typed: on a touch appliance that field opens a
        keypad over the page, and the pad cannot type into it -- a highlight stepped behind
        it would be a change nobody can see, on a page the operator has left for the moment.
        """
        if self._id_field is not None and self._id_field.is_editing:
            return None
        if self._page_index == PAGE_DEVICE:
            group = self._device_group
            return (group, self._on_device_selected) if group is not None else None
        if self._page_index == PAGE_ID:
            group = self._mode_group
            return (group, self._on_mode_selected) if group is not None else None
        if self._page_index == PAGE_OPTIONS and self._device is not None:
            for kind in (OptionKind.RADIO, OptionKind.CHECKBOX):
                found = self._pad_option(kind)
                if found is not None:
                    option, widget = found
                    return widget, self._option_command(self._device.key, option.key)
        if self._page_index == PAGE_INVENTORY:
            # The sort keys, which are the only control the listing has. Nothing is being
            # chosen here -- the page is read rather than answered -- so right re-orders the
            # rows and stays put; see pad_mark_turns_page.
            group = self._sort_group
            return (group, self._on_sort_selected) if group is not None else None
        return None

    def _clear_pad_cursors(self) -> None:
        """Take the pad's highlight off every list, wherever it was left.

        Called as the panel is seeded, which is what happens each time it is opened: it comes
        up on the first page and on whatever module the layout is showing, so a tint left over
        from the last time it was up would point at a row nobody has stepped to in this pass.
        Every list rather than the one showing -- the operator may have left the panel from
        any page.
        """
        for widget in (self._device_group, self._mode_group, self._sort_group, *self._option_widgets.values()):
            if isinstance(widget, CheckBoxGroup):
                widget.cursor = None

    def _pad_option(self, kind: OptionKind) -> tuple[LcsOption, Any] | None:
        """The module's first option of kind that is on the page to be worked, with its widget.

        A disabled option is passed over: it is drawn to say the module has the setting and
        that this mode does not offer it, and the pad has no more business setting it than a
        finger has.
        """
        device = self._device
        if device is None:
            return None
        for option in device.options:
            if option.kind is not kind or not option.enabled:
                continue
            widget = self._option_widgets.get((device.key, option.key))
            if widget is not None:
                return option, widget
        return None

    @property
    def pad_group(self) -> CheckBoxGroup | None:
        """The radio group the pad steps on the page showing, or None where it steps nothing.

        None on the review page and on the options page of a module whose only setting is a
        tick box -- a BPC2's restore flag, which right sets and left clears, there being no
        list to move through and both states one press away either way.
        """
        target = self._pad_target()
        widget = target[0] if target is not None else None
        return widget if isinstance(widget, CheckBoxGroup) else None

    @property
    def pad_cursor(self) -> str | None:
        """The row value the pad is pointing at, falling back to the row that is selected.

        The fallback is what makes the first press behave: with nothing stepped yet the pad
        starts from the row the dot is on, so up moves one row off it rather than jumping to
        the top of a list the operator is already partway down. It also carries the pad across
        a rebuild -- the mode rows are replaced whenever the module or the address changes,
        which drops the tint with them; see CheckBoxGroup._rearm_cursor -- and after a mark
        the dot is on the row the pad was on, so stepping goes on from where it left off.

        A value neither the tint nor the dot holds is read as nothing: guizero keeps a
        selection in a Tk StringVar and answers with whatever string it was handed, "None"
        among them, so what "nothing" looks like is read off the rows rather than assumed.
        """
        group = self.pad_group
        if group is None:
            return None
        values = group.row_values
        for value in (group.cursor, group.value):
            if value is not None and str(value) in values:
                return str(value)
        return None

    def pad_step(self, delta: int) -> bool:
        """Move the highlight delta rows along the page's list. True where it moved.

        Clamped rather than wrapping, as the keypad's Sensor Track list is: a pad held against
        the end of a list stays there instead of rolling round to the far one, where the next
        mark would program something the operator never looked at.

        The highlight is all that moves. Nothing is chosen, nothing is sent, and the dot does
        not follow -- a row stepped over must not read as a row picked, which is the whole
        reason these groups carry a cursor apart from their selection.

        The page follows it, though. A list can be longer than the window it is drawn in, and
        a highlight stepped onto a row below the fold would otherwise leave the pad pointing
        at something the operator cannot see; the window is moved by as little as it takes to
        bring that row back into it. See ScrollBox.show_widget.
        """
        group = self.pad_group
        if group is None:
            return False
        values = group.row_values
        if not values:
            return False
        current = self.pad_cursor
        if current is None:
            # A list with nothing on it at all is a state before the list rather than a
            # position in it, so a press either way lands on the first row.
            target = 0
        else:
            target = values.index(current) + int(delta)
            if not 0 <= target < len(values):
                return False
        group.cursor = values[target]
        # Read back rather than assumed: a group built without a cursor takes the assignment
        # and tints nothing, and the pad has then moved nothing the operator can see.
        moved = group.cursor == values[target]
        if moved and self._scroll is not None:
            row = group.cursor_row
            if row is not None:
                self._scroll.show_widget(row)
        return moved

    @property
    def pad_mark_turns_page(self) -> bool:
        """Whether choosing is the whole of what the page asks, so right turns it as well.

        A page whose list answers one question is finished by the answer -- which module on
        the first page, which of a module's own settings on the third -- and stopping there
        to reach for A or Next is a second press for a decision already made. So right both
        chooses and goes on.

        Not on the ID page, which asks two things of the operator and lends the pad only one
        of them: the address is typed into a field the pad cannot reach, stepped with the two
        keys beside it and, for an address inside another module's block, taken over with the
        keys below the rows. A right press carrying the operator off that page would take
        with it the half of the decision they had not made yet.

        Not for a lone tick box either -- a BPC2's restore flag. Right sets it and left
        clears it, both states one press away, and a page turned on the set would leave the
        clear behind it.

        Nothing on the review page, where the pad marks nothing at all: A is what presses
        Configure there; see can_configure.
        """
        if self._page_index == PAGE_DEVICE:
            return self._pad_target() is not None
        if self._page_index == PAGE_OPTIONS:
            found = self._pad_option(OptionKind.RADIO)
            return found is not None and self._option_ends_the_page(found[0])
        return False

    def _option_ends_the_page(self, option: LcsOption) -> bool:
        """Whether option is the last thing the module's options page asks the operator for.

        Asked of the module rather than assumed, because a module can declare a setting below
        the one being marked -- the AMC2 declares four, a mode and a remember flag for each of
        its two motors -- and a page turned on the first would carry the operator straight past
        the rest. A disabled setting holds nothing up: it is drawn to say the module has it and
        that this mode does not offer it, which is a fact to read rather than a decision to
        make.
        """
        device = self._device
        if device is None:
            return False
        options = list(device.options)
        # By identity: which of a module's settings this is, not which one it equals.
        index = next((i for i, other in enumerate(options) if other is option), None)
        if index is None:
            return False
        return not any(other.enabled for other in options[index + 1 :])

    def pad_mark(self) -> bool:
        """Choose the row the pad is on -- D-pad right -- and, where that is all the page
        asks, turn the page with it. True where anything changed.

        Right is both how a choice is made and how the panel is walked, on the pages where
        the two are the same thing; where they are not, it chooses and stays put. Which is
        which is pad_mark_turns_page.

        The turn asks the question the Next key is enabled by, so right can go nowhere Next
        would not, and it asks it after the mark: a choice written onto the page after it
        turned would land on the next page's list. It goes whether or not the mark moved
        anything -- right on the row already chosen means "this one, go on", as A does.

        A page turned takes the revert with it (see _show_page), so on those pages left is
        what abandons a highlight before the mark and B is how a mark is come back to.
        """
        marked = self._pad_mark_row()
        if self.pad_mark_turns_page and self.can_advance:
            self.next_page()
            return True
        return marked

    def _pad_mark_row(self) -> bool:
        """Choose the row the pad is on, as a tap on it would. True where anything changed.

        The mark itself, apart from what the key that made it does next: right marks and may
        turn the page, A marks and turns it, and both stand in for the same tap.

        What the mark displaced is remembered, so left can put it back; see pad_revert. A
        highlight that has not moved off the selected row marks nothing: there is nothing to
        choose and nothing to remember, and saying so is what lets a page turn without
        leaving a revert behind that would undo a choice the operator never made.
        """
        target = self._pad_target()
        if target is None:
            return False
        widget, commit = target
        if not isinstance(widget, CheckBoxGroup):
            return self._pad_tick(widget, commit, True)
        cursor = self.pad_cursor
        if cursor is None or cursor == str(widget.value):
            return False
        self._pad_undo = (self._page_index, str(widget.value))
        widget.value = cursor
        commit()
        return True

    def pad_revert(self) -> bool:
        """Put back what the last mark displaced -- D-pad left. True where anything changed.

        Two things a left press can mean, and it means whichever is true. Where a mark on this
        page displaced a choice, that choice goes back -- through the handler the mark went
        through, so the page is rebuilt from it exactly as a tap would rebuild it -- and the
        highlight follows it, the pad now pointing at what the panel holds. Where nothing was
        marked, the highlight is what goes back: a row stepped onto but never chosen is
        abandoned, and the dot was never anywhere else.

        One mark deep, deliberately. The undo is dropped as it is used and dropped again
        whenever the page turns, so left cannot reach back past the page in front of the
        operator, nor undo the same mark twice.
        """
        target = self._pad_target()
        if target is None:
            return False
        widget, commit = target
        if not isinstance(widget, CheckBoxGroup):
            return self._pad_tick(widget, commit, False)
        undo = self._pad_undo
        if undo is not None and undo[0] == self._page_index and undo[1] in widget.row_values:
            self._pad_undo = None
            widget.value = undo[1]
            widget.cursor = undo[1]
            commit()
            return True
        cursor = widget.cursor
        selected = str(widget.value)
        if cursor is None or cursor == selected:
            # Nothing was marked and nothing is stepped: the highlight is already on the row
            # that is chosen, so there is nothing to put back and nothing to abandon.
            return False
        widget.cursor = selected if selected in widget.row_values else None
        return True

    def _pad_tick(self, widget: Any, commit: Callable[[], None], ticked: bool) -> bool:
        """Set or clear a lone tick box, as a tap on it would. True where it changed.

        Nothing is remembered for a revert: a tick box holds two states and the pad reaches
        both -- right sets, left clears -- so putting one back is the other press rather than
        an undo. Which is also how a power district's relays are worked from the pad.
        """
        want = 1 if ticked else 0
        if not getattr(widget, "enabled", True):
            return False
        try:
            if int(widget.value or 0) == want:
                return False
        except (TypeError, ValueError):
            pass
        widget.value = want
        commit()
        return True

    def pad_advance(self) -> bool:
        """Choose the highlighted row and turn the page -- the A button.

        Both halves, in that order: A on a row the pad has stepped to means "this one, go
        on", and marking after the page turned would write the choice onto the next page's
        list. A page whose highlight was never moved has nothing to mark and simply advances,
        the selection standing as it was.

        The mark is made rather than the right key asked to make it, so that the turn below
        is the only one there is: right turns some pages itself, and A on such a page would
        otherwise turn two. What A adds to right is the pages right leaves alone; see
        pad_mark_turns_page.

        The turn asks the same question the Next key is enabled by, so A can go nowhere Next
        would not. On the review page there is nowhere left to go, and Configure is the only
        control on it, so that is what A presses -- the panel worked from the pad end to end,
        which is what it is there for on a Deck. Through the handler the button's own command
        is, and only where the button is enabled, so A sends nothing a finger could not; see
        can_configure.
        """
        self._pad_mark_row()
        if self.can_advance:
            self.next_page()
            return True
        if self._page_index == PAGE_REVIEW and self.can_configure:
            self.on_configure()
            return True
        return False

    def pad_back(self) -> bool:
        """Turn back a page -- the B button. What the Back key does, and nothing more.

        A mark is not put back on the way: Back and revert are two different requests, and an
        operator asking for the page before this one has not asked to unpick what they chose
        on this one -- the page they arrive at is read with its own choice still in force.
        Left is how a mark is undone; see pad_revert.
        """
        if not self.can_go_back:
            return False
        self.previous_page()
        return True

    def pad_scroll(self, pixels: int) -> bool:
        """Move the page in its window -- the stick and the trackpad. True where it moved.

        Positive is further down the page. Every other pad key works a control *on* the page;
        this works the page itself, which on the one screen where a page is ever held back is
        a different thing to want: the highlight can be stepped to a row the window is showing
        and still leave the operator unable to read the box below it, since reading is not
        stepping and there is nothing to step to.

        Nothing is chosen and no highlight moves, exactly as a finger dragging the page
        chooses nothing -- this is the same gesture reaching the same window, arriving from
        the pad instead of the glass; see ScrollBox.

        False where the page is not scrolling: no window yet, no pixels asked for, or a page
        already at the end the stick is pushing toward. The caller is told so the stick can
        be known to be doing nothing, but nothing is refused: a page that fits its window is
        a page with nowhere to go, which is an answer rather than a fault.
        """
        scroll = self._scroll
        if scroll is None or not pixels:
            return False
        return scroll.scroll_by(int(pixels))

    #
    # Seeding
    #
    def configure(self, scope: CommandScope = None, tmcc_id: int = None, state: Any = None) -> None:
        """
        Seed the panel from whatever is on screen when the LCS... key is pressed.

        Which module the panel opens on depends on the host; see
        reflects_layout_by_default(). On the Pi and the Steam Deck the module already
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
        self._clear_pad_cursors()

        reflect = reflects_layout_by_default()
        device = device_for_state(state) if reflect else None
        if device is not None and not device.configurable:
            # The screen is on a module the registry can only recognize. It has nothing to
            # open the panel on, so it is treated as no device at all: the search below
            # still finds it, and it is named in the assigned box like any other. No module
            # is in that position today; see the registry's own note on the flag.
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

        configurable_devices is sorted by name, so this is the AMC2 today and stays the
        first name in the list as modules are added.
        """
        return configurable_devices()[0]

    def _select_device(
        self,
        device: LcsDevice | None,
        seed_mode_from: Any = None,
        mode: LcsMode = None,
        config: Any = None,
    ) -> None:
        self._device = device
        # The rows on both pages are about to be rebuilt for another module, so nothing is
        # left of what was read off the layout for the last one -- and no choice of the
        # operator's stands against reading it, those having been choices among another
        # module's rows. See _seed_options_from_layout and _seed_mode_from_layout.
        self._options_read_from = None
        self._options_from_layout = set()
        self._mode_chosen = False
        if device is None:
            self._mode = None
            self._options = {}
            return
        if mode is None or not mode.enabled:
            # A mode the panel does not offer is not one it can be left on, whoever named it:
            # a module found running in one -- a BPC2 in a single-ID mode its manual
            # reserves, an AMC2 addressed as a train -- is opened on the row it can be
            # reprogrammed as instead. Left as it was found, the radios would show no row
            # selected and Configure would send the opening SET press and nothing after it.
            #
            # Read on the field this module reports its mode on, which is not "mode" for
            # every module; see reported_mode().
            mode = device.mode_for_pdi_mode(reported_mode(device, seed_mode_from))
            if mode is None or not mode.enabled:
                mode = device.default_mode
        self._mode = mode
        self._options = self._default_options(device, seed_mode_from, config)

    @classmethod
    def _default_options(cls, device: LcsDevice, state: Any = None, config: Any = None) -> dict[str, Any]:
        """
        The module's options as it is running with them, falling back to their own defaults.
        """
        options: dict[str, Any] = {}
        for option in device.options:
            reported = cls._reported_option(option, config, state)
            options[option.key] = option.default if reported is None else reported
        return options

    @classmethod
    def _reported_option(cls, option: LcsOption, *records: Any) -> Any:
        """What the module itself says an option is set to, or None where nothing says.

        The CONFIG packet is read before the component state, because a module's settings
        are what its own CONFIG record carries: the BPC2's restore-on-power-up flag is a bit
        of the mode byte in that packet and is in no component state at all, and the Sensor
        Track's Action Command is in that packet alone as well.

        Records are read by the field the option says it is reported on, which is the
        option's own key wherever the panel and the module use the same word for a setting
        and the module's own word where they differ -- an option is named for what it sets,
        and a module names the field it reports. A field can name a path where the module
        reports a setting one level down, as an AMC2 does on each of its motors. See
        LcsOption.reported_by.
        """
        for record in records:
            value = option.reported_by(record)
            if value is not None and cls._can_hold(option, value):
                return value
        return None

    @staticmethod
    def _can_hold(option: LcsOption, value: Any) -> bool:
        """Whether value is something this option could be set to.

        A record is read by a field name, and that name can mean something else entirely on
        a record written for another purpose: every PDI request carries an action, so a
        record read for an option named "action" answers with the request's own flavor. So
        a value counts as an answer about the option only if the option could hold it -- one
        of the rows the list offers, or a flag's true or false.
        """
        if option.kind == OptionKind.RADIO:
            return any(value == choice for _label, choice in option.choices)
        return isinstance(value, bool)

    def _discovery_occupant(self, scope: CommandScope = None) -> LcsOccupant | None:
        """
        What holds the entered ID, before any module has been chosen to program.

        No mode has been picked yet, so the panel has no address space of its own to
        search in. The screen the operator came from is the best hint there is -- the
        LCS... key pressed from the switch screen means switch IDs -- so its scope is
        tried first. Only when that turns up nothing, or the screen is not on an LCS
        key at all, does the search widen to every module, because the whole point of
        this lookup is to discover what kind of module is out there.

        Only a module this pass can program is worth seeding from; one the registry merely
        recognizes is reported in the assigned box, but the panel cannot open on it.
        """
        if scope is not None:
            occupant = self._first_programmable(occupants_of(self._base_id, self._store, scope=scope))
            if occupant is not None:
                return occupant
        return self._first_programmable(occupants_of(self._base_id, self._store))

    def _seed_from_occupant(self, occupant: LcsOccupant) -> None:
        self._select_device(
            occupant.device,
            seed_mode_from=occupant.state,
            mode=occupant.mode,
            config=occupant.config,
        )

    def _seed_mode_from_layout(self) -> None:
        """Open the mode radios on the mode the module already at the entered address is in.

        A BPC2 addressed as ACC 1 - 8 reads with its ACC row selected rather than with the
        module's own default TR row, which is what the panel used to offer to reprogram it
        as. The mode is a fact about the module and is recorded in its CONFIG packet, so
        there is no need to ask the operator to tell the panel what the layout already
        knows -- and every reason not to, a wrong answer here re-addressing the module onto
        a remote key it was never on.

        Looked up on any key, not the one the radios happen to be on: which key the module
        answers to is the first half of what is being read, so filtering by the panel's
        current guess at it would find a module only once the guess was already right. The
        key it is on is preferred where two modules of the type share the address, since a
        module on the key in hand is the one the rest of the page is about.

        A mode the operator picked themselves is never read over, at this address or any
        other: the radios are how they say what the module is to become, which is the whole
        purpose of the page and need not agree with what it is now. Picking another module
        starts that over; see _select_device.
        """
        device = self._device
        if device is None or self._mode_chosen:
            return
        occupant = self._based_here(self.scope) or self._based_here(None)
        mode = occupant.mode if occupant is not None else None
        # A mode the manual reserves is on no radio row -- a BPC2's single-ID modes among
        # them -- so a module running in one is left to the row it can be reprogrammed as.
        if mode is None or not mode.enabled:
            return
        self._mode = mode
        # And the entered ID is squared with the mode just read, exactly as configure()
        # squares it with the mode the panel opens on: a wider mode has a lower ceiling. No
        # module in the registry has a default mode narrower than another of its own, so
        # today this only holds the invariant rather than moving anything.
        self._base_id = min(self._base_id, self.max_base)

    def _seed_options_from_layout(self) -> None:
        """Open the options on what the module already at the entered address is holding.

        A BPC2 based there with restore on reads with the box already ticked, so an operator
        reconfiguring it keeps that setting by leaving it alone rather than by remembering
        it -- and can see what the module is holding without going and reading its relays.
        Where nothing of the kind is at the address, the module's own defaults stand.

        Read once per address, not on every refresh: what the operator sets for the address
        in hand is theirs to keep. Aiming the panel elsewhere reads the new address instead,
        and a setting that stood there only because it was read off the layout is given back
        its default rather than carried to an address nothing is known about -- it was a fact
        about the module it was read from, and would otherwise be programmed into a new
        module unasked. Anything nothing was ever read for is left alone, which is what
        leaves the Sensor Track's Action Command as its IRDA state seeded it; see
        _seed_sensor_track_action.
        """
        device = self._device
        if device is None or not device.options:
            return
        aimed_at = (device.key, self.scope, self._base_id)
        if aimed_at == self._options_read_from:
            return
        self._options_read_from = aimed_at
        occupant = self.reconfigured_occupant()
        for option in device.options:
            reported = self._reported_option(option, occupant.config, occupant.state) if occupant else None
            if reported is not None:
                self._options[option.key] = reported
                self._options_from_layout.add(option.key)
            elif option.key in self._options_from_layout:
                self._options[option.key] = option.default
                self._options_from_layout.discard(option.key)

    def _seed_sensor_track_action(self) -> None:
        """Pre-fill the Action Command from the Sensor Track's own IRDA state.

        The panel is handed the accessory-scope proxy, which does not carry the sequence;
        the value lives on the IRDA-scope state at the same address. What the module's own
        CONFIG packet says is read with every other module's settings and is authoritative
        where the PDI store has it -- this covers the store that has no PDI side, where an
        IRDA state built from control traffic is all there is to read; see
        _seed_options_from_layout.

        Read by the field the option names, exactly as a CONFIG packet is: the Action
        Command is reported as a sequence on either record, the option's key being the word
        the press is built from rather than the word the module reports. See
        LcsOption.reported_as.
        """
        if self._device is not SENSOR_TRACK:
            return
        option = SENSOR_TRACK.option("action")
        reported = self._reported_option(option, self._irda_state(self._base_id))
        if reported is not None:
            self._options[option.key] = reported

    # noinspection PyCallingNonCallable
    def _irda_state(self, tmcc_id: int) -> Any:
        store = self._store
        get_state: Callable[..., Any] | None = getattr(store, "get_state", None) if store is not None else None
        if get_state is None:
            return None
        # noinspection PyBroadException
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
        self._show_status("", VERIFYING_FG)

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
        # Deliberate, so neither a late synchronization nor the module already at the
        # address may seed over it.
        self._device_chosen = self._mode_chosen = True
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
        Clamp value into 1 .. max_base and refresh everything that depends on it.
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
        # First of all, because the rest of the page is drawn from the mode: which radio row
        # is selected, which remote key the two module boxes search, and which module the
        # options are then read off. See _seed_mode_from_layout.
        self._seed_mode_from_layout()
        self._refresh_id_heading()
        self._refresh_id_field()
        self._refresh_mode_selector()
        self._refresh_mode_legend()
        self._refresh_mode_note()
        self._refresh_step_keys()
        self._refresh_occupancy()
        # Last, and after everything that shows or hides one of the titled boxes or changes
        # what is inside them: guizero drops the stretch that keeps them the same width
        # every time it re-displays them.
        self._lay_out_titled_boxes()
        # Before the options are drawn, and here rather than where the address is set,
        # because the module being programmed and the key it is on settle last; see
        # _seed_options_from_layout.
        self._seed_options_from_layout()
        self._refresh_options_page()
        self._refresh_review_page()

    def _refresh_mode_selector(self) -> None:
        if self._mode_group is None:
            return
        options = self.mode_options()
        # Before the rows are replaced, so the group grids each one with whatever gap it is
        # owed as it builds it rather than a moment afterwards.
        self._mode_group.row_leads = self.mode_leads()
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
    def mode_legend(self) -> str:
        """What each remote key the module offers is for, one line each.

        Read above the rows it names, since which key to be on is the first half of the
        choice the rows offer. The keys are taken from the module's own enabled modes, in
        the order the radios list them, so a BPC2 reads TR before ACC and an STM2 says
        nothing about accessories.

        Each line is looked up under the module as well as the key, because what a key is
        for can be a fact about the module rather than about the key: a BPC2's TR and ACC
        modes address the same relays either way. See scope_use().
        """
        if self._device is None:
            return ""
        lines: list[str] = []
        for mode in enabled_modes(self._device):
            use = scope_use(mode.scope, self._device)
            if use and use not in lines:
                lines.append(use)
        return "\n".join(lines)

    @property
    def mode_note(self) -> str:
        """What the selected mode is for, keyed by the qualifier its own row carries.

        The legend above the rows answers the key every row opens with; this answers the
        word in parentheses on the row that is chosen -- "uncouple: Uncoupling tracks only
        - pulsed output (fixed)" under "ACC (uncouple) TMCC ID 1" -- which is the fact the
        row itself has no room for, a radio row being as wide as its label. Below the rows,
        because it speaks for whichever of them is selected.

        Keyed only where the name qualifies itself: a module's plainest mode is named by
        its key alone, and its note then stands as the plain sentence it is. Empty for a
        mode with nothing written about it, so the box grows only for a row that speaks.
        """
        mode = self._mode
        if mode is None or not mode.note:
            return ""
        qualifier = mode.qualifier
        return f"{qualifier}: {mode.note}" if qualifier else mode.note

    def _refresh_mode_legend(self) -> None:
        if self._mode_legend_line is not None:
            self._mode_legend_line.value = self.mode_legend

    def _refresh_mode_note(self) -> None:
        # Taken off the page where the chosen mode has nothing written about it -- a BPC2, the
        # Sensor Track -- for the reason given at _refresh_note: an empty Label still stands a
        # line tall, and on the fullest page in the panel that is 30px of nothing at the Pi's
        # font scale. The legend above the rows is never empty for a module with modes, so it
        # is written rather than shown or hidden.
        self._refresh_note(self._mode_note_line, self.mode_note)

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
        # The buttons act on a module the panel could actually take over, so a module in
        # the registry to be named rather than programmed never puts them on screen.
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

    def _refresh_row_grid(self, grid: Box | None, cells: list[tuple[GridCell, ...]], rows: Sequence[ModuleRow]) -> None:
        """
        Write rows into one of the module grids, growing it and hiding what is spare.
        """
        if grid is None:
            return
        for index, row in enumerate(rows):
            # Colored here rather than where the cell is built, because a cell outlives the
            # row it last held: the same three labels report an address that is taken and
            # then, a step of the ID later, one that is free. See UNASSIGNED_FG.
            color = UNASSIGNED_FG if row.is_unassigned else CONFLICT_FG
            for cell, value in zip(self._grid_row(grid, cells, index), row.cells):
                cell.value = value
                cell.text_color = color
                if not cell.visible:
                    cell.show()
        # Rows left over from a busier ID are hidden rather than blanked: an empty label
        # still stands a line tall, so the box would keep the height of the fullest ID it
        # had ever shown.
        for spare in cells[len(rows) :]:
            for cell in spare:
                if cell.visible:
                    cell.hide()

    def _grid_row(
        self,
        grid: Box,
        cells: list[tuple[GridCell, ...]],
        index: int,
        columns: int = ROW_COLUMNS,
        wrap_column: int = ROW_NAME_COLUMN,
        wrap_px: int | None = None,
        group_gap_px: int = 0,
        size: int | None = None,
    ) -> tuple[GridCell, ...]:
        """
        The cells of one grid row, created the first time the row is used.

        Rows are grown on demand and then kept: how many modules answer to an ID changes
        as the ID does, and a widget destroyed and recreated in a grid takes the column
        options of its neighbors with it.

        The three columns of a module row unless another shape is asked for. The My Modules
        listing asks for four, the last of them the one that wraps; the two grids are the
        same thing done to different columns, and one row-builder is what keeps a cell of
        either looking like a cell of the other. See _refresh_inventory.

        group_gap_px is offered to every cell of the row and taken up by the one that wraps,
        that being the only column whose text comes in groups; see _grid_cell. size is the
        grid's own, the module rows taking the size of the boxes they stand in and the
        listing the size of the page it is; see _inventory_text_size.
        """
        while len(cells) <= index:
            row = len(cells)
            # Only the first column is bold; it is the column the eye runs down.
            cells.append(
                tuple(
                    self._grid_cell(grid, column, row, wrap_column, wrap_px, group_gap_px, size)
                    for column in range(columns)
                )
            )
        return cells[index]

    def _grid_cell(
        self,
        grid: Box,
        column: int,
        row: int,
        wrap_column: int = ROW_NAME_COLUMN,
        wrap_px: int | None = None,
        group_gap_px: int = 0,
        size: int | None = None,
    ) -> GridCell:
        """One cell of a grid: the label all but one of them is, or a stack of them.

        group_gap_px is the white space a cell wants between one group of its text and the
        next, and the listing's configuration column is the only column that asks for any:
        a cell that has to hold groups apart is the groups themselves, one label each,
        because a label's own lines are the only white space a label has. Every other cell,
        in either grid, is the one label it has always been. See GroupedCell.
        """
        # Broken like every other line the panel writes, though nothing here is prose: what
        # a cell holds is a module's name and its addresses, and a name is the registry's to
        # lengthen. A cell that wraps narrows its column and the row still fits the page; a
        # cell that does not takes the row off the edge of it. Broken from the left, since
        # these are columns the eye runs down.
        #
        # And broken at its own column's width rather than the page's, which is what keeps
        # the row inside the pane; see _row_name_wrap_px. Only the one unbounded column needs
        # telling: the columns either side of it cannot reach even their share of the row.
        wraps = column == wrap_column
        width = (wrap_px or self._row_name_wrap_px) if wraps else None
        if wraps and group_gap_px:
            # The box stands in the grid where the label would, and is gridded and hidden as
            # a label is; the blocks inside it are the cell's own business.
            box = Box(grid, grid=[column, row], align="left")
            return GroupedCell(
                box,
                lambda parent: self._cell_label(parent, align="top", width=width, size=size),
                group_gap_px,
            )
        return self._cell_label(grid, grid=[column, row], bold=column == 0, width=width, size=size)

    def _cell_label(
        self,
        parent: Box,
        *,
        grid: list[int] | None = None,
        align: str = "left",
        bold: bool = False,
        width: int | None = None,
        size: int | None = None,
    ) -> Text:
        """A label a grid cell is written on, styled as every cell of either grid is.

        The size of the box titles above them unless the grid asks for another: these rows
        are the answer the operator came to the page for, not a caption on it. Which is a
        size down where the pane has nothing to spare, as those titles are -- and the My
        Modules listing, which stands in no box and is scrolled, asks for the page's own
        body size instead. See _titled_text_size and _inventory_text_size.

        A label stacked inside a cell rather than gridded as one is stretched to the cell's
        width and its text anchored west, which is what keeps the left edges of two blocks
        of one cell in line: a label narrower than the block above it is otherwise centered
        against it, and a column the eye runs down cannot afford a ragged edge for the sake
        of three pixels. Both are set where they survive a re-pack -- "fill" is read off the
        widget by guizero itself, and the anchor is a Tk option rather than a layout one.
        """
        stacked = grid is None
        cell = Text(parent, text="", grid=grid, align=align, width="fill" if stacked else None)
        cell.text_size = size or self._titled_text_size
        cell.text_bold = bold
        self._wrap(cell, justify="left", width=width)
        try:
            cell.tk.config(padx=ASSIGNED_CELL_PAD)
            if stacked:
                cell.tk.config(anchor="w")
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

    def reconfigured_occupant(self) -> LcsOccupant | None:
        """The module the presses would reprogram, where the layout already holds one.

        A module of the type being programmed, based at the entered ID on the key being
        programmed -- the same module, that is, the panel is about to re-address, so what it
        is holding is worth reading. Another type of module answering to the ID says nothing
        about this one's settings, and one the ID merely falls inside is based somewhere
        else: the panel offers to go to its base rather than take it for the module in hand.
        """
        return self._based_here(self.scope)

    def _based_here(self, scope: CommandScope | None) -> LcsOccupant | None:
        """The module of the type being programmed based at the entered ID, or None.

        Based at it, not merely claiming it: a module the ID falls inside is based somewhere
        else, and the panel offers to go to that base rather than read the module as the one
        in hand.

        scope keeps only a module answering to that remote key; pass None where the key is
        not part of the question, which is the case for the one reader whose business is
        which key the module is on. See _seed_mode_from_layout.
        """
        for occupant in occupants_of(self._base_id, self._store, scope=scope):
            if occupant.device is self._device and occupant.base_id == self._base_id:
                return occupant
        return None

    @staticmethod
    def _first_programmable(occupants: Sequence[LcsOccupant]) -> LcsOccupant | None:
        """
        The first module in the list this pass knows how to program.

        A module the registry only recognizes has no modes and no presses, so seeding the
        panel from it would leave the operator on a device that cannot be configured. It is
        named in the box and otherwise passed over.
        """
        for occupant in occupants:
            if occupant.device.configurable:
                return occupant
        return None

    def assigned_trains(self) -> list[TrainOccupant]:
        """
        The trains answering to the entered ID, where the key being programmed is theirs.

        One at most, an address holding one train. Kept apart from assigned_occupants()
        rather than added to it because everything else that reads that list is looking for
        a module: the settings the options page opens on, the module the presses would
        reprogram, the base the Go to button retargets at. A train is none of those, and
        offering to go to one would be offering to program a locomotive.
        """
        if not self.shares_train_ids:
            return []
        return trains_of(self._base_id, self._store)

    def assigned_rows(self) -> list[ModuleRow]:
        """
        What the Currently Assigned box says: a row per module and train, or "Unassigned".

        A module is named the same way whether the entered ID is its base or one of its
        interior ports: the box reports what is out on the layout, and the range already
        says that the ID falls inside it. Which port it is exactly changes nothing the
        operator can act on -- the two buttons below the box are where the decision is
        made, and they name the base ID themselves.

        Modules first, then the trains: the modules are what the page is about, and a train
        is the further thing the operator has to know about the address. "Unassigned" only
        where neither has anything to say -- a train on the ID is an answer to the box's
        question, and the address is not free.
        """
        rows = [self._module_row(occupant) for occupant in self.assigned_occupants()]
        rows += [self._train_row(train) for train in self.assigned_trains()]
        if not rows:
            return [ModuleRow(scope="", module=UNASSIGNED)]
        return rows

    @classmethod
    def _module_row(cls, occupant: LcsOccupant) -> ModuleRow:
        scope, module, ids = cls._occupant_parts(occupant)
        return ModuleRow(scope=f"{scope}:" if scope else "", module=module, ids=ids)

    @classmethod
    def _train_row(cls, train: TrainOccupant) -> ModuleRow:
        """A train as the panel names it: "TR:", "PRR #8523", "TMCC ID 3".

        Spelled by the same rule as a module and gridded into the same three columns, since
        what the operator has to read off either is the same thing: something already
        answers to this address, and here is which key it answers on. The remote key is
        stated rather than left out as obvious -- it is what makes a train relevant at all,
        and a row that omitted it would read as though the address were keyless.
        """
        return ModuleRow(
            scope=f"{cls._scope_label(CommandScope.TRAIN)}:",
            module=train.name,
            ids=tmcc_id_text(train.base_id, train.last_id),
        )

    @classmethod
    def _occupant_parts(cls, occupant: LcsOccupant) -> tuple[str, str, str]:
        """A module as the panel names it: "ACC", "BPC2", "TMCC IDs 12 - 19".

        Named the way the operator would program it, and in the order they would do it in:
        the remote key first, because that is the first button pressed and the thing that
        decides whether the module is in the way at all, then the module, then the TMCC IDs
        it holds. The port count is not spelled out separately -- the range already says it.
        """
        # The registry's own spelling of a block, which is also what the mode radios above
        # these rows read, so a module in the way is named the way the mode that would
        # claim it is named.
        ids = tmcc_id_text(occupant.base_id, occupant.last_id)
        return cls._scope_label(occupant.effective_scope), occupant.device.label, ids

    @staticmethod
    def _scope_label(scope: CommandScope | None) -> str:
        """A remote key as the rows spell it: "ACC", "SW", "TR", "ENG".

        The panel's own short forms, which are the words on the remote's keys; the scope's
        own title is the fallback for a key the panel has no word of its own for, and the
        empty string for no key at all, which is what a row for an unowned address carries.
        The engine key is spelled for the listing alone -- nothing is programmed onto it; see
        SCOPE_LABEL.
        """
        return SCOPE_LABEL.get(scope, scope.title if scope is not None else "")

    def overlap_occupants(self) -> list[LcsOccupant]:
        """
        The modules the chosen block runs into, base first.

        Scoped like assigned_occupants(), because two blocks in different key namespaces
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

    def overlap_trains(self) -> list[TrainOccupant]:
        """
        The trains numbered inside the chosen block, where that block is on their key.

        The entered ID is left out, exactly as it is for the modules: whatever answers to it
        is named by the assigned box above, and naming it twice would read as two conflicts.
        """
        if not self.shares_train_ids:
            return []
        return train_overlaps(self._base_id, self.ports, self._store, ignore_base=self._base_id)

    def overlap_rows(self) -> list[ModuleRow]:
        """
        What the Overlaps box says: a row per module and train in the way, or nothing at all.

        Named exactly as the assigned box names them, and gridded into the same three
        columns, so the two boxes read as one list of what is out there. The word
        "Overlaps" is the box's title rather than a prefix on the first row.

        This is the box that matters most on a TR mode: a BPC2 addressed as TR 1 takes eight
        of the trains' own addresses, and seven of them are ones the operator never typed.
        """
        rows = [self._module_row(occupant) for occupant in self.overlap_occupants()]
        return rows + [self._train_row(train) for train in self.overlap_trains()]

    def go_to_owning_base(self) -> None:
        """
        Retarget the panel at the module that owns the entered ID, pre-filled from it.

        Scoped like assigned_occupants(), so the button always goes to a module the
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

        Only where the panel is the only way off itself; see needs_close_button(). Read by
        create_popup as the overlay is built, which is the one moment it is needed: an
        overlay is built on the machine it is shown on.
        """
        return needs_close_button()

    @property
    def closes_on_request_only(self) -> bool:
        """This panel goes when it is asked to go, and not because the layout said something.

        It is the one panel in the pane that is worked in rather than read off: four pages of
        choices, and on the last one a verdict on the presses that is written once. The pane
        closes its popup whenever it re-reads what it has selected, and while this panel is up
        the layout has every reason to make it do so -- most sharply in the case this rule was
        written for.

        A module the Base 3 has never heard of is held as a provisional record until the base
        answers for it. Configure is what makes it answer, so the presses are barely out
        before the record is promoted into recents, and that took the panel off the screen
        along with the Success or Unsuccessful line the operator had asked for and was reading;
        see EngineGui.make_recent. The same closing runs on a sensor track reporting a train
        that passed over it, and on a record cleared on the base.

        Back and Next still turn the pages, Close still closes, and so does the pad's close
        key: nothing here refuses the operator, only the layout. See PopupManager.close.

        Asked of has_close rather than answered outright, because a panel may only hold the
        screen where the operator can let it go: has_close is that same question -- is there a
        way off this panel that belongs to the panel itself? On the Pi and the Steam Deck
        there is, and those are the machines this is operated from. On a desk the way off is
        the pane's own controls, and holding the screen against them would be a panel with no
        way out at all.
        """
        return self.has_close

    @property
    def footer_pad_px(self) -> int:
        """How much whitespace stands between the Back/Next row and the Close below it.

        The row's own padding, so the three gaps that make up that band are one number and
        the two rows read as a pair of rows rather than as a panel and its footer. The
        shared band is not wrong, it is answering a different question: it holds a panel's
        buttons off the panel, and here what is above Close is not a panel but another row
        of buttons, already held off the page by PAGE_GAP.

        Worth 46px of the popup's own height on a portrait pane: 24px of lead and 20px above
        and below Close became 6px apiece. Which is 46px more page, measured -- the Pi's
        window grew from 493px to 539px and the worst page it holds any of back went from
        124px to 78px, while the desk's tallest page came down from 733px to 687px.
        """
        return self._nav_row_pad

    def _build_nav(self, body: Box) -> None:
        """Back and Next, on a row of the panel's own rather than in the popup's footer.

        has_footer is left False, so where create_popup adds a Close button at all (see
        has_close) it goes below everything the panel builds -- which puts Close on a line
        of its own, under these two, instead of all three crowding one row. Where it does
        not, these two are the last row in the overlay and nothing moves.

        The row is packed, not gridded, and asks for no width of its own, so it is as wide as
        the buttons it is showing and Tk centers it under the page above; Close below it is
        centered the same way. On the first page that means Next alone, centered -- the row
        shrinks to it rather than keeping a Back-shaped hole to its left.

        Back is created first, so it is always the left of the two: guizero re-packs a
        container's children in the order they were created, so an order set here is the
        order the row keeps however often Back is hidden and shown again.

        Styled with style_footer_button: that is the one shared look for the big buttons at
        the foot of an overlay, and the Close beneath them wears it too. Its vertical padding
        is then trimmed, because this row is not the popup's footer band and does not want a
        footer band's whitespace around it -- see NAV_ROW_PAD.
        """
        host = self._gui
        self._nav = nav = Box(body, align="top", border=0)
        self._back_btn = back = HoldButton(nav, text=BACK_TEXT, align="left", width=8, command=self.previous_page)
        style_footer_button(host, back)
        repad_footer_button(back, pady=self._nav_row_pad)
        host.cache(back)
        self._next_btn = nxt = HoldButton(nav, text=NEXT_TEXT, align="left", width=8, command=self.next_page)
        style_footer_button(host, nxt)
        repad_footer_button(nxt, pady=self._nav_row_pad)
        host.cache(nxt)
        self._refresh_nav()

    def _refresh_nav(self) -> None:
        """Which of Back and Next the row is showing, and whether what it shows can be pressed.

        Shown by whether there is a page that way at all, and enabled by whether the panel
        can go there yet. The two are not the same question: Next stands grayed on the first
        page until a module is chosen -- there is a page after it, just nothing to configure
        yet -- while on the review page there is nothing after it at all, and a key with
        nowhere to go is taken off the row rather than left standing gray. Which is what Back
        has always done on the first page; the two ends of the panel now read alike.
        """
        self._show_nav_button(self._back_btn, self.can_go_back)
        self._show_nav_button(self._next_btn, self.has_next_page, enabled=self.can_advance)
        # Replayed once, after both: hide() and show() each run the row's display_widgets(),
        # which rebuilds pack options from scratch and discards the padding
        # style_footer_button recorded.
        if self._nav is not None:
            restore_footer_packing(self._nav)

    def _show_nav_button(self, btn: HoldButton | None, visible: bool, enabled: bool = None) -> None:
        """Put one of the two keys on the row or take it off, and set what it can do there.

        A hidden button is disabled as well, though nothing can press it: the pad asks the
        panel rather than the row (see can_advance), and a button whose look and whose state
        disagree is a button the next reader has to reason about.

        The row's packing is replayed by the caller, not here, and the replay skips a hidden
        button -- which is what keeps this honest: pack_configure *manages* a widget pack has
        forgotten, so replaying a hidden button's padding puts it back on screen at the end
        of the row. That is exactly how Back once reappeared to the right of Next; see
        restore_footer_packing.
        """
        if btn is None:
            return
        if visible:
            btn.show()
        else:
            btn.hide()
        self._enable(btn, visible if enabled is None else enabled)
