#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import copy
import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.pytrain.gui.controller.control_labels import (
    ADMIN_PANEL_TITLE,
    BUTTONS_TITLE,
    CATALOG_PANEL_TITLE,
    DPAD_TITLE,
    GLOBAL_CHORD_TITLE,
    GLOBAL_SECTION_BUTTONS,
    POPUP_PANEL_TITLE,
    ROUTE_PANEL_TITLE,
    SWITCH_PANEL_TITLE,
    ControlEntry,
    ControlSection,
    controls_summary,
)
import src.pytrain.gui.controller.controls_panel as mod
from src.pytrain.gui.controller.controls_panel import COLUMNS, ROWS_PER_COLUMN, ControlsPanel
from src.pytrain.gui.controller.steam_deck_input import ControlProfile

BUNDLED = Path(mod.__file__).with_name("steam_deck_default.json")


def _panel(profile: ControlProfile | None) -> ControlsPanel:
    # paginate() needs no Tk, so skip __init__ and set only what it reads. The ruler and
    # the budget are what build() would have measured; unmeasured, they are the estimate
    # and the calibrated fallback -- which is what a headless run gets.
    panel = ControlsPanel.__new__(ControlsPanel)
    panel._profile = profile
    panel._page = 0
    panel._pages = ()
    panel._page_box = None
    panel._ruler = mod.ESTIMATED_RULER
    panel._rows_per_column = ROWS_PER_COLUMN
    return panel


def _sections(panel: ControlsPanel) -> dict[str, ControlSection]:
    return {section.title: section for section in controls_summary(panel.profile)}


def _oversized_profile() -> ControlProfile:
    """A profile far larger than the bundled one, to force pagination.

    Sized past COLUMNS * ROWS_PER_COLUMN so it spans pages however those constants are
    later tuned -- the point is the paging behaviour, not any particular capacity. The
    buttons clear a whole column by themselves, allowing for the handful of indices the
    global section takes, so the Buttons section is still one that has to be split.
    """
    data = copy.deepcopy(json.loads(BUNDLED.read_text(encoding="utf-8")))
    buttons = ROWS_PER_COLUMN + len(GLOBAL_SECTION_BUTTONS) + 1
    data["buttons"] = {str(index): {"action": "bell", "target": "focused"} for index in range(buttons)}
    pairs = list(itertools.combinations(range(buttons), 2))[: COLUMNS * ROWS_PER_COLUMN]
    data["chords"] = [{"buttons": list(pair), "action": "halt", "target": "global"} for pair in pairs]
    return ControlProfile.from_dict(data)


def test_bundled_profile_fits_on_one_page() -> None:
    # Paging is for custom profiles; the shipped layout should never need it.
    panel = _panel(ControlProfile.load(None))

    assert len(panel.paginate()) == 1


@pytest.mark.parametrize("budget", range(ROWS_PER_COLUMN - 1, ROWS_PER_COLUMN + 9))
def test_the_last_column_holds_only_the_per_panel_sections(budget) -> None:
    # The column order is the section order in controls_summary, so this is the assertion
    # that keeps it: the reader asking what a control does while a panel of some kind is up
    # has one column to read, and the sections that answer a different question -- the
    # D-pad, and the X that closes whatever popup is on screen -- close the column before it
    # rather than sitting in the middle of that list.
    #
    # Asserted across budgets because the budget is derived from the display rather than
    # fixed: with the break left to arithmetic, the panel sections led the last column at
    # 20 rows and the first of them was pulled up into the bottom of the middle one at 22,
    # which is what the Deck itself derives. The layout cannot depend on the machine.
    #
    # The sweep's floor is a row under ROWS_PER_COLUMN, which is what these four sections
    # and the admin note come to: below that they do not fit at all, a question of capacity
    # rather than of packing. ROWS_PER_COLUMN itself is the floor the screen is ever drawn
    # at, being the fallback for when there is no Tk to measure with, so the layout holds
    # with a row in hand.
    #
    # The ceiling is well above what any display derives, and has to be: a row is as tall as
    # the taller of its text and a section heading, so thinning the section outlines to
    # SECTION_BORDER took the heading's two border pixels off every row and handed this
    # machine 24 rows where it had 22. Above 30 the layout does break -- the middle column
    # runs out of sections to hold and the D-pad moves up into the first -- which is a
    # different screen from the one these assertions describe.
    panel = _panel(ControlProfile.load(None))
    panel._rows_per_column = budget

    columns = panel.paginate()[0]

    assert [section.title for section in columns[-1]] == [
        SWITCH_PANEL_TITLE,
        ROUTE_PANEL_TITLE,
        ADMIN_PANEL_TITLE,
        CATALOG_PANEL_TITLE,
    ]
    assert columns[0][0].title == GLOBAL_CHORD_TITLE
    assert columns[1][-1].title == POPUP_PANEL_TITLE
    assert DPAD_TITLE in [section.title for section in columns[1]]


def test_a_section_that_starts_a_column_gets_one_of_its_own(monkeypatch) -> None:
    # Room left in the column in progress is no reason to fill it: a section that has to
    # head a column says so, and the packer obeys that before it obeys the budget.
    row = (ControlEntry("A", "Ring bell"),)
    sections = (ControlSection("First", row), ControlSection("Second", row, False, True))
    monkeypatch.setattr(mod, "controls_summary", lambda profile: sections)
    panel = _panel(ControlProfile.load(None))

    columns = panel.paginate()[0]

    assert [[section.title for section in column] for column in columns] == [["First"], ["Second"]]


def test_only_the_first_chunk_of_a_split_section_starts_a_column() -> None:
    # A continuation already opens a column by being a full one's worth; flagging every
    # chunk would leave the column before each of them half empty.
    entries = (ControlEntry("A", "Ring bell"),) * (ROWS_PER_COLUMN + 2)

    chunks = ControlsPanel._split_to_fit((ControlSection("Tall", entries, False, True),))

    assert len(chunks) > 1
    assert [chunk.starts_column for chunk in chunks] == [True] + [False] * (len(chunks) - 1)


def test_no_column_exceeds_its_row_budget() -> None:
    for profile in (ControlProfile.load(None), _oversized_profile()):
        panel = _panel(profile)
        for page in panel.paginate():
            assert len(page) <= COLUMNS
            for column in page:
                rows = sum(len(section.entries) + 1 for section in column)
                assert rows <= ROWS_PER_COLUMN


def test_pagination_loses_no_entries() -> None:
    # The failure this guards against is the nastiest kind: a clipped help screen looks
    # complete, so a dropped binding is invisible.
    profile = _oversized_profile()
    panel = _panel(profile)

    expected = sum(len(section.entries) for section in controls_summary(profile))
    paginated = sum(len(section.entries) for page in panel.paginate() for column in page for section in column)

    assert paginated == expected


def test_a_section_taller_than_a_column_is_split_and_marked() -> None:
    panel = _panel(_oversized_profile())

    titles = [section.title for page in panel.paginate() for column in page for section in column]

    assert BUTTONS_TITLE in titles
    assert f"{BUTTONS_TITLE} (cont.)" in titles


def test_split_preserves_the_fixed_flag() -> None:
    # A continuation of a fixed section is still fixed, or the "*" marker would lie.
    sections = controls_summary(ControlProfile.load(None))
    fixed = next(section for section in sections if section.fixed)
    tall = type(fixed)(fixed.title, fixed.entries * (ROWS_PER_COLUMN + 2), True)

    chunks = ControlsPanel._split_to_fit((tall,))

    assert len(chunks) > 1
    assert all(chunk.fixed for chunk in chunks)


def test_no_profile_paginates_to_nothing() -> None:
    # A GUI running without controller input still has to render something.
    assert _panel(None).paginate() == ()


def test_turn_page_wraps_in_both_directions() -> None:
    panel = _panel(_oversized_profile())
    panel._pages = panel.paginate()
    panel._render_page = lambda: None  # no Tk in this test
    assert panel.page_count > 1

    panel.turn_page(forward=True)
    assert panel.page == 1
    for _ in range(panel.page_count - 1):
        panel.turn_page(forward=True)
    assert panel.page == 0, "paging forward must wrap rather than dead-end"

    panel.turn_page(forward=False)
    assert panel.page == panel.page_count - 1


def test_turn_page_is_a_no_op_on_a_single_page() -> None:
    panel = _panel(ControlProfile.load(None))
    panel._pages = panel.paginate()
    panel._render_page = lambda: pytest.fail("must not redraw when there is nowhere to page")

    panel.turn_page(forward=True)

    assert panel.page == 0


def test_engine_gui_delegates_the_controls_screen_to_its_host() -> None:
    # A pane-hosted popup could never span both panes, so the pane just asks the host.
    from types import SimpleNamespace

    from src.pytrain.gui.controller.engine_gui import EngineGui

    calls: list[str] = []
    pane = SimpleNamespace(_parent_gui=SimpleNamespace(on_show_controls=lambda: calls.append("show")))

    EngineGui.on_controls_panel(pane)

    assert calls == ["show"]


def test_standalone_engine_gui_has_no_controls_screen() -> None:
    # A portrait GUI has no host and no controller; asking must not raise.
    from types import SimpleNamespace

    from src.pytrain.gui.controller.engine_gui import EngineGui

    EngineGui.on_controls_panel(SimpleNamespace(_parent_gui=None))


def test_pane_reports_and_pages_the_hosts_screen() -> None:
    from types import SimpleNamespace

    from src.pytrain.gui.controller.engine_gui import EngineGui

    turned: list[bool] = []
    host = SimpleNamespace(
        controls_visible=True,
        page_controls=lambda forward: turned.append(forward) or True,
        close_controls=lambda: True,
    )
    pane = SimpleNamespace(_parent_gui=host)

    assert EngineGui.controls_visible.fget(pane) is True
    assert EngineGui.page_controls(pane, False) is True
    assert EngineGui.close_controls(pane) is True
    assert turned == [False]


def test_pane_without_a_host_reports_no_controls_screen() -> None:
    from types import SimpleNamespace

    from src.pytrain.gui.controller.engine_gui import EngineGui

    pane = SimpleNamespace(_parent_gui=None)

    assert EngineGui.controls_visible.fget(pane) is False
    assert EngineGui.page_controls(pane, True) is False
    assert EngineGui.close_controls(pane) is False


def test_a_long_entry_is_budgeted_two_rows() -> None:
    # Tk wraps the action text with wraplength; pagination has to know a wrapped entry is
    # taller, or the column overflows the display it was measured against. The long text is
    # written for this test rather than copied off the screen -- what is under test is the
    # arithmetic, and a sample sitting a few pixels either side of the budget would turn
    # this into a test of one label's length.
    short = ControlEntry("A", "Ring bell")
    long = ControlEntry("L2", "Engine shutdown, with the dialog it opens", "hold")

    assert ControlsPanel.entry_rows(short) == 1
    assert ControlsPanel.entry_rows(long) == 2


def test_section_rows_counts_the_header_and_wrapped_entries() -> None:
    section = ControlSection(
        "Triggers",
        (
            ControlEntry("L2", "Engine shutdown, with the dialog it opens", "hold"),
            ControlEntry("R2", "Engine startup, with the dialog it opens", "hold"),
        ),
    )

    assert ControlsPanel.section_rows(section) == 1 + 2 + 2


def test_a_section_note_costs_the_column_a_row() -> None:
    # A note is drawn inside the section's frame, so it takes room off the bottom of the
    # column exactly as a row of it does. Uncounted, the column it lands in is budgeted to
    # fit and does not -- and what runs off the display is whatever was drawn last.
    rows = (ControlEntry("L1 + X", "Quit PyTrain"),)
    plain = ControlSection(ADMIN_PANEL_TITLE, rows)
    annotated = ControlSection(ADMIN_PANEL_TITLE, rows, note="Hold for 3 seconds")

    assert ControlsPanel.note_rows(plain) == 0
    assert ControlsPanel.note_rows(annotated) == 1
    assert ControlsPanel.section_rows(annotated) == ControlsPanel.section_rows(plain) + 1


def test_a_split_section_keeps_its_note_on_the_last_chunk() -> None:
    # A section too tall for a column is dealt out over several, and a note true of all of
    # them reads under the last of its rows -- once, which is the point of a note. Every
    # chunk is charged for it even so: which one ends up with it is not known until the rows
    # have been dealt out, and a chunk budgeted a row short is a chunk that overflows.
    note = "Hold for 3 seconds"
    entries = (ControlEntry("A", "Ring bell"),) * (ROWS_PER_COLUMN + 2)

    chunks = ControlsPanel._split_to_fit((ControlSection("Tall", entries, note=note),))

    assert len(chunks) > 1
    assert [chunk.note for chunk in chunks] == [""] * (len(chunks) - 1) + [note]
    for chunk in chunks:
        assert ControlsPanel.section_rows(chunk) <= ROWS_PER_COLUMN, chunk.title


def test_columns_respect_the_row_budget_once_wrapping_is_counted() -> None:
    # The check that matters: measured in rendered rows, not entry counts.
    for profile in (ControlProfile.load(None), _oversized_profile()):
        panel = _panel(profile)
        for page in panel.paginate():
            for column in page:
                rows = sum(ControlsPanel.section_rows(section) for section in column)
                assert rows <= ROWS_PER_COLUMN, [section.title for section in column]


def test_bundled_profile_still_fits_one_page_with_wrapping() -> None:
    assert len(_panel(ControlProfile.load(None)).paginate()) == 1


# What a stand-in section frame answers when it is asked what colour it is drawn in. A row
# has to be told: it is a plain Tk label, which inherits no background from the frame it is
# gridded into (see ControlsPanel._section_background).
_FRAME_BG = "#FFFFFF"


class _FakeTextTk:
    def __init__(self) -> None:
        self.configs: list[dict] = []
        self.grids: list[dict] = []
        self.columns: list[tuple[int, dict]] = []
        # The sticky in force, as opposed to every sticky ever asked for: Tk keeps the last
        # one, and what a column ends up gridded with is the question here.
        self.sticky: str | None = None

    def config(self, **kwargs) -> None:
        self.configs.append(kwargs)

    def grid_configure(self, **kwargs) -> None:
        self.grids.append(kwargs)
        if "sticky" in kwargs:
            self.sticky = kwargs["sticky"]

    def grid_columnconfigure(self, index, **kwargs) -> None:
        self.columns.append((index, kwargs))

    def update_idletasks(self) -> None:
        self.updated = True

    def cget(self, _option) -> str:
        return _FRAME_BG

    def winfo_children(self):
        # Whatever the test says the rendered columns came out to; nothing, by default,
        # which is a render Tk cannot measure.
        return getattr(self, "holders", [])


class _FakeText:
    instances: list["_FakeText"] = []

    def __init__(self, _parent, **kwargs) -> None:
        self.kwargs = kwargs
        self.tk = _FakeTextTk()
        self.text_bold = None
        self.text_color = None
        self.bg = None
        # Widgets added to this one, in creation order -- what guizero re-grids each time
        # another joins them, and so what a test about that ordering has to look at.
        self.gridded: list["_FakeText"] = []
        _FakeText.instances.append(self)


class _FakeFrameTk:
    """Stand-in for a section's LabelFrame: what it was told, and what it can be asked.

    Separate from _FakeTextTk because a heading is the one place the panel asks Tk a
    question -- the frame's own background, so the labels it packs match it -- rather than
    only telling it things.
    """

    def __init__(self) -> None:
        self.configs: list[dict] = []

    def config(self, **kwargs) -> None:
        self.configs.append(kwargs)

    def cget(self, _option) -> str:
        return _FRAME_BG


class _FakeFrame:
    """The plain Tk frame a split heading is packed into, and handed over as labelwidget."""

    def __init__(self, parent, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs


class _FakeLabel:
    """Stand-in for a plain Tk label: the heading's parts, and every cell of every row.

    What it records is the shape of the change that made the help screen quick to build.
    Everything the panel has to say about a cell is a constructor argument -- the text, the
    font and its weight, the colours, the wrap -- and the only call after that is the grid.
    A cell configured afterwards instead would land in ``configs``, which is what a guizero
    row did a couple of hundred times over.
    """

    instances: list["_FakeLabel"] = []

    def __init__(self, parent, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.packed: dict = {}
        self.gridded: dict = {}
        self.configs: list[dict] = []
        _FakeLabel.instances.append(self)

    def pack(self, **kwargs) -> None:
        self.packed = kwargs

    def grid(self, **kwargs) -> None:
        self.gridded = kwargs

    def config(self, **kwargs) -> None:
        self.configs.append(kwargs)


def _section() -> SimpleNamespace:
    """A stand-in for the section frame a row is gridded into, and asked its colour."""
    return SimpleNamespace(tk=_FakeFrameTk())


def test_the_action_text_is_configured_to_wrap(monkeypatch) -> None:
    # Without wraplength Tk neither wraps nor shrinks: the line is truncated, which is
    # what "Boost / brake speed (repeats)" was doing on the Deck.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)
    entry = ControlEntry("Up / Down", "Boost / brake speed", "repeats")

    panel._render_entry(_section(), entry, 0)

    keycap, action, note = _FakeLabel.instances
    assert "wraplength" in action.kwargs, "action text must be given a wrap width"
    # The row's whole share less this row's own note, which is drawn beside it: the same sum
    # entry_rows does, or the packer counts one row and Tk draws two.
    assert action.kwargs["wraplength"] == mod.ACTION_WRAP_PX - panel._note_px(entry)
    assert action.kwargs["justify"] == "left"
    # The keycap must not wrap -- "L1 + R1" splitting across lines would look broken.
    assert "wraplength" not in keycap.kwargs
    # Nor the note: its column was measured to hold it, and a note broken over two lines
    # would cost the row a second one to say the same words.
    assert "wraplength" not in note.kwargs


def test_the_action_text_is_drawn_a_weight_lighter_than_its_keycap(monkeypatch) -> None:
    # Said rather than left alone, as the section note also has to say it: the row's
    # TitleBox bolds everything drawn inside it, so an action left to inherit came out
    # exactly as emphatic as the keycap beside it. That cost the keycap the one job its
    # bold is there for -- being found without reading the row -- and cost the row some 7%
    # of its width against a budget measured in the lighter weight, which is what broke
    # four lines on the Deck.
    #
    # It is the font that says so now rather than a property set afterwards. A plain Tk label
    # inherits nothing from the section frame it sits in, so the weight is simply whichever
    # one the ruler measured the string in -- which is the whole point of asking the ruler for
    # it (see _row_font).
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_entry(_section(), ControlEntry("Up / Down", "Boost / brake speed", "repeats"), 0)

    keycap, action, note = _FakeLabel.instances
    assert keycap.kwargs["font"] == (panel._ruler.family, mod.ENTRY_SIZE, "bold")
    assert action.kwargs["font"] == (panel._ruler.family, mod.ENTRY_SIZE)
    assert note.kwargs["font"] == (panel._ruler.family, mod.NOTE_SIZE)


def test_the_rows_are_drawn_at_the_size_that_was_fitted(monkeypatch) -> None:
    # _fit_text gives back a point when a row will not fit its column, so the renderer has
    # to ask what size it settled on rather than reading the constant: drawing at 15pt what
    # was measured at 13 wraps exactly the rows the point was given back to save.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)
    panel._entry_size = mod.MIN_ENTRY_SIZE

    panel._render_entry(_section(), ControlEntry("A", "Ring bell"), 0)

    keycap, action = _FakeLabel.instances
    assert keycap.kwargs["font"][1] == action.kwargs["font"][1] == mod.MIN_ENTRY_SIZE
    # And a panel that has not been built draws at the size as written.
    assert _panel(None)._entry_size == mod.ENTRY_SIZE


def test_the_wrap_predictor_agrees_with_the_pixel_budget() -> None:
    # The bug this guards: WRAP_CHARS and ACTION_WRAP_PX were written down separately and
    # drifted, so a 29-character line was budgeted one row while Tk wrapped it onto two.
    assert mod.WRAP_CHARS == int(mod.ACTION_WRAP_PX / mod.APPROX_CHAR_PX)
    # The predictor must not be more optimistic than the renderer.
    assert mod.WRAP_CHARS * mod.APPROX_CHAR_PX <= mod.ACTION_WRAP_PX


def test_a_measured_ruler_catches_the_wrap_the_character_count_missed() -> None:
    # Why measuring beats counting: at 10px a character this 29-character line came to
    # 290px, inside the 320px budget, so it was budgeted one row -- and Tk wrapped it onto
    # two. A ruler that measures the string cannot make that mistake, whatever the font.
    entry = ControlEntry("Left stick", "Throw switch thru", "own pane")
    wider_font = mod.TextRuler(measure=lambda text: 12 * len(text), row_px=30, footnote_px=15)

    assert ControlsPanel.entry_rows(entry) == 1
    assert ControlsPanel.entry_rows(entry, wider_font) == 2


def test_a_ruler_measures_each_string_once() -> None:
    # What made the screen quick to pack. The page is packed once per pass of
    # _fitted_column_widths, again by rows_fit_their_columns and again by build, and each pass
    # used to re-measure what the last had already measured: 2495 measurements of 140 distinct
    # strings on the bundled screen, each one a round trip into Tcl, which was 24ms of an 81ms
    # build. It is now 140. A ruler is built per point size and dropped with it, so what it
    # remembers cannot go stale.
    asked: list[str] = []
    keycaps: list[str] = []
    notes: list[str] = []
    ruler = mod.TextRuler(
        measure=lambda text: asked.append(text) or 10 * len(text),
        row_px=30,
        footnote_px=15,
        keycap_measure=lambda text: keycaps.append(text) or 12 * len(text),
        note_measure=lambda text: notes.append(text) or 7 * len(text),
    )

    for _ in range(3):
        assert ruler.width("Ring bell") == 90
        assert ruler.keycap_width(" A ") == 36
        assert ruler.note_width("(repeats)") == 63
        assert ruler.wrapped_rows("Boost / brake speed", 100) == 3

    assert asked.count("Ring bell") == 1
    assert keycaps == [" A "]
    assert notes == ["(repeats)"]
    # And the wrap, which is the expensive question: it is decided word by word, so one row
    # costs a measurement per word twice over -- and the packer asks about the same row in
    # every column it might land in.
    assert asked.count("Boost") <= 1
    # A different budget is a different question, and is asked.
    assert ruler.wrapped_rows("Boost / brake speed", 400) == 1


def test_the_packer_never_measures_a_string_twice() -> None:
    # The other half of the memo: this is what the passes actually do, and the reason it was
    # worth having. Nothing here is a repeat measurement even though the same sections are
    # priced three times over.
    asked: list[str] = []
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(measure=lambda text: asked.append(text) or 10 * len(text), row_px=30, footnote_px=15)
    panel._column_px = ControlsPanel.column_widths(1274)

    for _ in range(3):
        panel._column_needs()

    assert asked, "the sections have to be measured at least once"
    assert len(asked) == len(set(asked)), "every string measured once, however often it is asked about"


def test_an_unmeasurable_widget_leaves_the_estimate_in_place() -> None:
    # No display, or a stand-in where a widget should be: the screen still has to lay
    # itself out, so measuring is an improvement on estimating, never a requirement.
    ruler = mod.TextRuler.measured(object())

    assert ruler.exact is False
    assert ruler.width("abcd") == int(4 * mod.APPROX_CHAR_PX)
    assert ruler.rows_in(600) == ROWS_PER_COLUMN


def test_a_measured_ruler_reports_the_font_tk_will_draw_in() -> None:
    tk = pytest.importorskip("tkinter")
    from tkinter import font as tkfont

    try:
        root = tk.Tk()
    except tk.TclError as exception:  # pragma: no cover - depends on the display
        pytest.skip(f"no display to measure against: {exception}")
    try:
        ruler = mod.TextRuler.measured(SimpleNamespace(tk=root))
        family = tkfont.nametofont(mod.DEFAULT_FONT_NAME, root=root).actual("family")
        font = tkfont.Font(root=root, family=family, size=mod.ENTRY_SIZE)

        assert ruler.exact is True
        # The family it measured, which is also the one the rows are drawn in -- see
        # test_the_rows_are_drawn_in_the_font_the_ruler_measured.
        assert ruler.family == family
        # The font's own measurement, not a character count -- the whole point of asking.
        assert ruler.width("Boost / brake speed") == font.measure("Boost / brake speed")
        assert ruler.footnote_px > 0
        # A row is at least a line of entry text tall, or a column would overrun.
        assert ruler.rows_in(font.metrics("linespace") * 10) <= 10
    finally:
        root.destroy()


def test_the_row_budget_is_divided_out_of_the_room_available() -> None:
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(measure=len, row_px=30, footnote_px=15)

    # The footnote and the page label sit under the columns, so they come off the budget
    # here rather than being squeezed out of it at the bottom of the display.
    assert panel._rows_that_fit(600) == (600 - 2 * 15) // 30
    # Not so little room that the screen shatters into continuation chunks.
    assert panel._rows_that_fit(40) == mod.MIN_ROWS_PER_COLUMN

    # Nothing measured, or nothing said about the room: the calibrated fallback stands.
    panel._ruler = mod.ESTIMATED_RULER
    assert panel._rows_that_fit(600) == ROWS_PER_COLUMN
    assert panel._rows_that_fit(0) == ROWS_PER_COLUMN


def test_the_budget_never_promises_more_rows_than_the_display_holds() -> None:
    # The regression this exists for: the budget was a constant calibrated by eye against
    # one display and one font, so on any other the tallest column ran past the bottom --
    # and what went off the edge was whatever the packer placed last.
    row_px, footnote_px, room = 33, 16, 640
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(measure=len, row_px=row_px, footnote_px=footnote_px)
    panel._rows_per_column = panel._rows_that_fit(room)

    tallest = max(
        sum(ControlsPanel.section_rows(section, panel._ruler) for section in column)
        for page in panel.paginate()
        for column in page
    )

    assert tallest * row_px + mod.FOOTER_LINES * footnote_px <= room


def _fixed_ruler(*_args, **_kwargs) -> mod.TextRuler:
    """A measuring ruler whatever size it is asked for -- see _fit_text."""
    return mod.TextRuler(len, 30, 15, len)


def test_build_derives_the_budget_from_the_room_it_is_given(monkeypatch) -> None:
    # build() is where the two halves meet: the caller says how much room is left once its
    # own chrome is accounted for, and the panel divides it into rows it can measure.
    monkeypatch.setattr(mod, "Box", _FakeText)
    monkeypatch.setattr(mod, "Text", _FakeText)
    monkeypatch.setattr(mod.TextRuler, "measured", classmethod(_fixed_ruler))
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None)
    panel._render_page = lambda: None

    panel.build(_FakeText(None), height_px=600)

    assert panel.rows_per_column == (600 - 2 * 15) // 30


def test_the_entry_size_is_not_traded_for_a_wrapped_row(monkeypatch) -> None:
    # The size the screen is read at is not currency, which is what MIN_ENTRY_SIZE being
    # ENTRY_SIZE says: rows that do not fit are answered with width -- the columns take
    # what they need and the page overruns the display (_shared_widths) -- and never with a
    # smaller screen. So there is one size to try, and a display that cannot hold it still
    # gets it.
    tried: list[int] = []
    monkeypatch.setattr(mod.TextRuler, "measured", classmethod(_fixed_ruler))

    def never(self) -> bool:
        tried.append(self._entry_size)
        return False

    monkeypatch.setattr(ControlsPanel, "rows_fit_their_columns", never)
    panel = _panel(ControlProfile.load(None))

    panel._fit_text(object(), 600, 1274)

    assert mod.MIN_ENTRY_SIZE == mod.ENTRY_SIZE, "the floor is the ceiling: one size, always"
    assert tried == [mod.ENTRY_SIZE]
    assert panel.entry_size == mod.ENTRY_SIZE


def test_a_lowered_floor_brings_the_shrink_back(monkeypatch) -> None:
    # The floor is a lever rather than a leftover, so the machinery under it stays tested:
    # lower it and a display too narrow for its rows is answered with a point at a time
    # again, stopping at the first size that fits rather than walking to the bottom.
    tried: list[int] = []
    monkeypatch.setattr(mod.TextRuler, "measured", classmethod(_fixed_ruler))
    monkeypatch.setattr(mod, "MIN_ENTRY_SIZE", mod.ENTRY_SIZE - 2)

    def fits(self) -> bool:
        tried.append(self._entry_size)
        return self._entry_size == mod.ENTRY_SIZE - 1

    monkeypatch.setattr(ControlsPanel, "rows_fit_their_columns", fits)
    panel = _panel(ControlProfile.load(None))

    panel._fit_text(object(), 600, 1274)

    assert tried == [mod.ENTRY_SIZE, mod.ENTRY_SIZE - 1]
    assert panel.entry_size == mod.ENTRY_SIZE - 1
    # And what it settled on is measured at that size, not left as the first pass had it.
    assert panel.rows_per_column == (600 - 2 * 15) // 30
    assert panel.column_px


def test_the_entry_size_is_never_given_back_past_the_floor(monkeypatch) -> None:
    # A display too small for these rows at any size the floor allows gets the smallest one
    # and the wrapping, which the packer has counted rows for. Shrinking on past it would
    # answer a help screen nobody can read to a screen with a broken line in it. Driven
    # with the floor lowered, since as shipped there is nothing to give back.
    tried: list[int] = []
    monkeypatch.setattr(mod.TextRuler, "measured", classmethod(_fixed_ruler))
    monkeypatch.setattr(mod, "MIN_ENTRY_SIZE", mod.ENTRY_SIZE - 2)

    def never(self) -> bool:
        tried.append(self._entry_size)
        return False

    monkeypatch.setattr(ControlsPanel, "rows_fit_their_columns", never)
    panel = _panel(ControlProfile.load(None))

    panel._fit_text(object(), 600, 1274)

    assert tried == list(range(mod.ENTRY_SIZE, mod.ENTRY_SIZE - 3, -1))
    assert panel.entry_size == mod.ENTRY_SIZE - 2


def test_the_size_ceiling_does_not_cost_the_screen_a_page(monkeypatch) -> None:
    # The other half of raising ENTRY_SIZE, and the half _fit_text does not test for: a
    # taller row buys fewer of them, and a budget under what the sections need spills the
    # shipped screen onto a second page nobody would think to turn to. Modelled with a row
    # that grows with the point size, which is the worst case -- on the fonts measured here
    # a row is as tall as the taller of its text and a SECTION_SIZE heading, and the heading
    # wins at every size the ceiling can reach, so the real budget does not move at all.
    def sized_ruler(_cls, _widget, entry_size: int = mod.ENTRY_SIZE) -> mod.TextRuler:
        return mod.TextRuler(len, entry_size + 16, 15, len)

    monkeypatch.setattr(mod.TextRuler, "measured", classmethod(sized_ruler))
    panel = _panel(ControlProfile.load(None))

    # The room the Deck's own display leaves the columns, which is what the ceiling was
    # measured against: 800px less the title band and the overlay's border.
    panel._fit_text(object(), 738, 1274)

    assert panel.entry_size == mod.ENTRY_SIZE
    assert len(panel.paginate()) == 1


def test_an_unmeasurable_screen_draws_at_the_size_as_written() -> None:
    # Measuring is an improvement on the constants, never a requirement for drawing: with
    # no font to measure, the first size stands, as the calibrated row budget and the even
    # split do.
    panel = _panel(ControlProfile.load(None))

    panel._fit_text(object(), 600, 1274)

    assert panel.entry_size == mod.ENTRY_SIZE
    assert panel.rows_per_column == ROWS_PER_COLUMN
    assert panel.column_px == ControlsPanel.column_widths(1274)


def test_no_bundled_entry_is_predicted_to_wrap() -> None:
    # Not a rule for all time -- a custom profile may well wrap -- but the shipped screen
    # reads better on one line per binding, and this catches a label growing past the
    # budget unnoticed.
    for section in controls_summary(ControlProfile.load(None)):
        for entry in section.entries:
            assert ControlsPanel.entry_rows(entry) == 1, (section.title, entry.input, entry.action)


def test_the_middle_column_hands_its_width_to_the_two_beside_it() -> None:
    # What the width budget is for beyond fitting: the middle column carries the engine
    # commands, whose actions are the longest strings on the screen, so left to its content
    # it took the most room on a screen that had none to spare. It gives up a share of an
    # even third, and the two columns beside it get half of that each.
    #
    # This is the fallback now -- what a screen with nothing to measure with draws to. A
    # screen that can measure divides the width by what its rows need instead; see
    # test_the_columns_are_cut_to_what_their_rows_need.
    widths = ControlsPanel.column_widths(1274)

    even = 1274 // COLUMNS
    assert len(widths) == COLUMNS
    assert widths[0] == widths[-1] > widths[1]
    assert widths[1] == even - int(even * mod.CENTER_COLUMN_TRIM)
    assert widths[0] - even == (even - widths[1]) // 2


@pytest.mark.parametrize("width", [640, 1024, 1274, 1280, 1920])
def test_the_even_split_never_adds_up_past_the_room_it_was_given(width) -> None:
    # Three columns that between them ask for more than the display has: the overlay is
    # gridded from the left edge of a window that cannot grow, so the excess is not scaled
    # or scrolled -- it is cut.
    #
    # This holds of the even split, and of nothing else now. A screen that can measure its
    # own rows deliberately spends more than the display has rather than break a line; the
    # split is what a screen with no font to measure falls back to, and it cannot tell
    # whether a column it starved was going to wrap, so it starves none of them.
    assert sum(ControlsPanel.column_widths(width)) <= width


@pytest.mark.parametrize("width", [640, 1024, 1274, 1280, 1920])
@pytest.mark.parametrize("needs", [(100, 400, 400), (400, 400, 400), (900, 100, 100), (0, 0, 0)])
def test_no_measured_column_is_handed_less_than_its_rows_need(width, needs) -> None:
    # The reversal of the invariant above, and the whole of this change: the even split is
    # held to the display, but a column that measured its own rows gets what they need
    # whether or not the page can afford all three. A column handed less is a column with a
    # broken line in it, and a page that runs past the right edge costs its reader less
    # than that.
    widths = ControlsPanel._shared_widths(width, needs)

    assert all(width_px >= need for width_px, need in zip(widths, needs))
    if sum(needs) <= width:
        # Affordable: the slack is handed out rather than held back, to within the rounding.
        assert 0 <= width - sum(widths) < COLUMNS
    else:
        assert sum(widths) == sum(needs) > width, "the page overruns rather than trimming a column"


def test_the_columns_are_cut_to_what_their_rows_need() -> None:
    # The bug in one line: a flat trim took a fixed 15% off the middle column -- the one
    # holding "Boost / brake speed (repeats)", the longest string on the screen -- and gave
    # it to the column with the shortest rows, which wrapped rows while ~130px of the
    # Deck's display went unspent.
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(
        measure=lambda text: 8 * len(text),
        row_px=30,
        footnote_px=15,
        keycap_measure=lambda text: 9 * len(text),
    )

    panel._column_px = panel._fitted_column_widths(1274)
    needs = panel._column_needs()

    assert sum(panel.column_px) <= 1274
    assert all(width >= need for width, need in zip(panel.column_px, needs)), (panel.column_px, needs)
    # The widest column is the one with the widest rows, which a fixed trim could not say:
    # it narrowed the middle column whichever column the longest row was in.
    assert panel.column_px.index(max(panel.column_px)) == needs.index(max(needs))
    # And nothing is held back for a column that had no use for it: the page is spent.
    assert 1274 - sum(panel.column_px) < COLUMNS


def test_a_page_too_narrow_for_its_columns_overruns_rather_than_trimming_them() -> None:
    # What used to happen to these needs on this page: the column that fit an even share
    # kept 100 and the other two divided what was left, 250 each -- 150px short of what
    # their rows measured, so both wrapped. Nothing is divided now. Each column takes its
    # own need and the page is 300px too wide, which is a choice about where the cost of a
    # narrow display falls: on the edge of the page rather than in the middle of a line.
    widths = ControlsPanel._shared_widths(600, (100, 400, 400))

    assert widths == (100, 400, 400)
    assert sum(widths) - 600 == 300


@pytest.mark.parametrize("px_per_char", [8, 10, 12, 14])
def test_no_bundled_row_wraps_however_wide_the_display_draws_it(monkeypatch, px_per_char) -> None:
    # The whole of what the width policy is for, in one assertion: whatever the font
    # measures, every row of the shipped screen is drawn on one line -- and at the size it
    # is meant to be read at, not a point given back to buy the fit. How wide these strings
    # come out is not knowable from here (the Deck draws them some 6-12% wider than a desk
    # machine), so it is driven across a range that brackets both ends and well past them:
    # at the wide end the page runs off the display, which is the trade, and no line breaks.
    def ruler(_cls, _widget, entry_size: int = mod.ENTRY_SIZE) -> mod.TextRuler:
        return mod.TextRuler(
            measure=lambda text: px_per_char * len(text),
            row_px=30,
            footnote_px=15,
            # Keycaps are drawn bold, and bold is wider: charged here as it is charged there.
            keycap_measure=lambda text: px_per_char * len(text) + 8,
        )

    monkeypatch.setattr(mod.TextRuler, "measured", classmethod(ruler))
    panel = _panel(ControlProfile.load(None))

    panel._fit_text(object(), 738, 1274)

    assert panel.entry_size == mod.ENTRY_SIZE
    assert panel.rows_fit_their_columns()
    for page in panel.paginate():
        for index, column in enumerate(page):
            for section in column:
                wrap_px = panel._column_wrap_px(section, index)
                for entry in section.entries:
                    rows = ControlsPanel.entry_rows(entry, panel._ruler, wrap_px)
                    assert rows == 1, (section.title, entry.action, entry.note, wrap_px)
                if section.note:
                    note_px = panel.note_wrap_px(panel.column_px[index % COLUMNS])
                    assert panel._ruler.wrapped_rows(section.note, note_px) == 1, (section.title, section.note)


def test_the_columns_are_grown_until_the_sections_that_moved_fit(monkeypatch) -> None:
    # Why one pass is no longer enough. A column that takes more than an even share holds
    # more sections than it was measured with, and a section that lands in a column priced
    # without it wraps there -- modelled at 17pt on a font 12% wider than this machine's,
    # the second pass moved five rows into columns some 50px too narrow. So the packing is
    # followed up until no column is under its need, widening only: a column that already
    # holds its rows on one line cannot be made to break one by being handed more room.
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(measure=len, row_px=30, footnote_px=15, keycap_measure=len)
    packed: list[tuple[int, ...]] = []
    # What the sections in each column need, pass by pass: the second packing pulls a
    # section into the middle column that the first did not price, and the third confirms.
    answers = iter([(600, 400, 400), (600, 500, 400), (600, 500, 400)])

    def needs(self) -> tuple[int, ...]:
        packed.append(tuple(self._column_px))
        return next(answers)

    monkeypatch.setattr(ControlsPanel, "_column_needs", needs)

    widths = panel._fitted_column_widths(1274)

    assert widths == (600, 500, 400)
    # Measured against the even split first -- what a screen with no font to measure draws
    # -- then against its own answer, then once more to find it settled.
    assert packed == [ControlsPanel.column_widths(1274), (600, 400, 400), (600, 500, 400)]


def test_the_columns_stop_growing_after_a_bounded_number_of_passes(monkeypatch) -> None:
    # The passes converge because they only ever widen, and a column cannot outgrow the
    # widest section on the screen -- but that is an argument, not a guarantee against a
    # profile nobody has written yet, and this runs on the press of a button. So the work
    # is capped, and a page that has not settled is drawn with whatever wrapping is left,
    # which the packer has counted the rows for.
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(measure=len, row_px=30, footnote_px=15, keycap_measure=len)
    passes = itertools.count(1)

    def always_more(self) -> tuple[int, ...]:
        # Past the page every time, so the growth is never satisfied: a need the page can
        # afford is met out of the slack on the pass that finds it.
        step = 500 * next(passes)
        return (step,) * COLUMNS

    monkeypatch.setattr(ControlsPanel, "_column_needs", always_more)

    widths = panel._fitted_column_widths(1274)

    assert next(passes) == mod.WIDTH_PASSES + 1, "one packing per WIDTH_PASSES and no more"
    assert widths == (500 * mod.WIDTH_PASSES,) * COLUMNS


def test_the_slack_is_handed_to_the_columns_rather_than_held_back() -> None:
    # An unspent budget is not drawn as a gap -- the columns size themselves to their
    # content -- so holding it back buys nothing, while spending it covers ENTRY_CHROME_PX
    # guessing a pixel low.
    widths = ControlsPanel._shared_widths(1000, (300, 300, 300))

    assert widths == (333,) * COLUMNS


def test_nothing_to_measure_with_leaves_the_even_split() -> None:
    # Measuring is an improvement on the fixed trim, never a requirement for drawing: a
    # headless run, or a stand-in widget, still has to lay the page out.
    panel = _panel(ControlProfile.load(None))

    assert panel._ruler.exact is False
    assert panel._fitted_column_widths(1274) == ControlsPanel.column_widths(1274)
    assert panel._fitted_column_widths(0) == ()


def test_no_width_known_leaves_every_column_sizing_to_its_content() -> None:
    # A headless run, or a caller that does not know how much room it has: the screen still
    # has to lay itself out, so a width budget is an improvement on the fallback, never a
    # requirement -- exactly as the row budget is.
    panel = _panel(ControlProfile.load(None))
    section = _sections(panel)[GLOBAL_CHORD_TITLE]

    assert ControlsPanel.column_widths(0) == ()
    assert panel.column_px == ()
    assert panel.action_wrap_px(section) == mod.ACTION_WRAP_PX
    assert panel._column_wrap_px(section, 1) == mod.ACTION_WRAP_PX


def test_a_keycap_is_measured_in_the_weight_it_is_drawn_in() -> None:
    # The bug this exists for, and it is the one that wrapped four rows on the Deck against
    # a screen whose own tests said nothing wrapped: _render_entry draws a keycap bold, and
    # bold is some 7% wider. Measured light, the keycap is charged less of the column than
    # it takes, the action beside it is handed a budget the row does not have -- and Tk
    # breaks a line the packer counted as one.
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(measure=len, row_px=30, footnote_px=15, keycap_measure=lambda text: 2 * len(text))
    section = _sections(panel)[BUTTONS_TITLE]

    keycap = max(2 * len(mod.keycap_text(entry)) for entry in section.entries)
    noted = [entry for entry in section.entries if entry.note]
    row = max(len(entry.action) for entry in noted) + max(panel._note_px(entry) for entry in noted)

    assert panel.action_wrap_px(section, 400) == 400 - keycap - mod.ENTRY_CHROME_PX
    assert panel.section_px(section) == keycap + row + mod.ENTRY_CHROME_PX
    # The estimate draws no such distinction and does not need to: a character count at the
    # high end of what a character measures is already generous enough for the bold.
    assert mod.ESTIMATED_RULER.keycap_width("Right stick") == mod.ESTIMATED_RULER.width("Right stick")


def test_a_rows_note_is_priced_at_the_size_it_is_drawn_at() -> None:
    # The whole of what this bought. "(hold: w dialog)" and "(repeats)" were measured at the
    # entry size because they were inside the action's own label, and all seven notes on the
    # bundled screen are in the middle column -- the one whose need decides how wide the page
    # is. Charged at NOTE_SIZE, that column comes down 19px and stops being the widest.
    panel = _panel(ControlProfile.load(None))
    entry = ControlEntry("Up / Down", "Boost / brake speed", "repeats")
    smaller = mod.TextRuler(measure=lambda text: 10 * len(text), row_px=30, footnote_px=15, keycap_measure=len)
    same = mod.TextRuler(measure=lambda text: 10 * len(text), row_px=30, footnote_px=15, keycap_measure=len)
    smaller._note_measure = lambda text: 7 * len(text)

    panel._ruler = same
    at_entry_size = panel._note_px(entry)
    panel._ruler = smaller

    assert panel._note_px(entry) < at_entry_size
    # And a ruler with nothing to measure with charges the full size, which is the safe
    # direction: a column budgeted wider than its rows need, never narrower.
    assert mod.ESTIMATED_RULER.note_width("(repeats)") == mod.ESTIMATED_RULER.width("(repeats)")
    # A row with no note is charged nothing at all, padding included.
    assert panel._note_px(ControlEntry("Up / Down", "Smoke down / up")) == 0


def test_a_section_is_only_charged_for_the_notes_it_has() -> None:
    # The trap this exists for, and it cost the bundled Global section 75px before it was
    # caught: charge every row the widest action *and* the widest note, and a section pays
    # for both even when they are on different rows -- "HALT - emergency stop" carries no
    # note, and the only note up there is on the much shorter "Open catalog". The rows with
    # no note span the note column instead, so the section is as wide as its longest row.
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(measure=len, row_px=30, footnote_px=15, keycap_measure=len)
    long_action = ControlEntry("A", "A very long action indeed")
    short_with_note = ControlEntry("B", "Short", "a long note")
    section = ControlSection("Mixed", (long_action, short_with_note))
    keycap = max(len(mod.keycap_text(entry)) for entry in section.entries)

    widest_row = max(len(long_action.action), len(short_with_note.action) + panel._note_px(short_with_note))

    assert panel.section_px(section) == keycap + widest_row + mod.ENTRY_CHROME_PX
    # Which is less than the two maxima added together -- what the section would have cost.
    assert panel.section_px(section) < keycap + len(long_action.action) + panel._note_px(short_with_note) + (
        mod.ENTRY_CHROME_PX
    )
    # And a section whose longest row is the annotated one is charged for both of its parts.
    together = ControlSection("Annotated", (short_with_note, ControlEntry("A", "Mid", "n")))
    assert (
        panel.section_px(together)
        == max(len(mod.keycap_text(entry)) for entry in together.entries)
        + len(short_with_note.action)
        + panel._note_px(short_with_note)
        + mod.ENTRY_CHROME_PX
    )


def test_a_note_is_never_drawn_larger_than_the_row_it_qualifies() -> None:
    # An aside a size down, which is what it is for -- so on a display whose rows have come
    # down to meet it (a lowered MIN_ENTRY_SIZE) it comes down with them rather than ending
    # up the largest thing on the row.
    panel = _panel(ControlProfile.load(None))

    assert panel.note_size == mod.NOTE_SIZE < mod.ENTRY_SIZE
    panel._entry_size = mod.NOTE_SIZE - 2
    assert panel.note_size == mod.NOTE_SIZE - 2


def test_a_section_wraps_within_what_its_keycaps_leave_of_the_column() -> None:
    # Per section, not per column: the action text starts where the keycaps end, and
    # "Right stick" leaves a good deal less of a column than "A" does.
    panel = _panel(ControlProfile.load(None))
    panel._ruler = mod.TextRuler(measure=len, row_px=30, footnote_px=15)
    sections = _sections(panel)

    keycap = max(len(mod.keycap_text(entry)) for entry in sections[BUTTONS_TITLE].entries)
    assert panel.action_wrap_px(sections[BUTTONS_TITLE], 400) == 400 - keycap - mod.ENTRY_CHROME_PX
    # Wider keycaps, less room for the action beside them.
    assert panel.action_wrap_px(sections["Joysticks"], 400) < panel.action_wrap_px(sections[BUTTONS_TITLE], 400)
    # A column too narrow for its keycaps costs the page its width budget rather than
    # wrapping every row into a stack of single words.
    assert panel.action_wrap_px(sections["Joysticks"], 60) == mod.MIN_ACTION_WRAP_PX


def test_a_section_is_priced_by_the_column_it_is_packed_into() -> None:
    # The columns are no longer the same width, so neither is the cost of a section: the
    # same rows wrap in the narrow middle column and not beside it. Counting one width for
    # all three either overflows the narrow column or spills the page onto a second one for
    # rows the wide columns never needed.
    panel = _panel(ControlProfile.load(None))
    panel._column_px = (500, 200, 500)
    section = _sections(panel)[BUTTONS_TITLE]

    assert panel._column_wrap_px(section, 1) < panel._column_wrap_px(section, 0)
    # Columns run on across pages; the width belongs to the position on the page.
    assert panel._column_wrap_px(section, COLUMNS + 1) == panel._column_wrap_px(section, 1)
    # Splitting a too-tall section happens before it has a column, so it is measured
    # against the narrowest one: fitting there, a chunk fits wherever it is packed.
    assert panel._narrowest_wrap_px(section) == panel._column_wrap_px(section, 1)


def test_only_the_outer_columns_are_pinned_and_only_to_each_other(monkeypatch) -> None:
    # The width budget is a limit, not an allowance: a column that used less than its share
    # must not hold the difference open, or the leftover reads as a gap before the next
    # column. So the columns keep their own width and only the outer two are matched -- to
    # the wider of the two, since three columns whose outer pair differ read as a mistake.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Box", _FakeText)
    monkeypatch.setattr(mod, "Text", _FakeText)
    monkeypatch.setattr(mod, "TitleBox", _FakeText)
    # A row is a plain Tk label gridded into the section frame, not a guizero child of it.
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None, s_12=12)
    panel._column_px = ControlsPanel.column_widths(1274)
    panel._pages = panel.paginate()
    panel._page_box = _FakeText(None)
    panel._page_box.children = []
    panel._page_box.tk.holders = [
        SimpleNamespace(winfo_reqwidth=lambda width=width: width) for width in (300, 340, 320)
    ]

    panel._render_page()

    assert panel._page_box.tk.columns == [(0, {"minsize": 320}), (COLUMNS - 1, {"minsize": 320})]
    # align="top" alone grids a column sticky="N", which centres it in a cell wider than
    # its content: the narrower outer column would sit in a gap on both sides rather than
    # line up with its neighbour. Pinned, a column has to spend what it was pinned to.
    stretched = [widget for widget in _FakeText.instances if {"sticky": "new"} in widget.tk.grids]
    assert len(stretched) == COLUMNS


def test_the_outer_columns_are_not_matched_past_the_display(monkeypatch) -> None:
    # Pinning widens the narrower of the two outer columns by the difference between them,
    # and that has to come out of the room the columns left over. Charged to a page with
    # none, it pushes the far side of the last column -- and the Close button in the title
    # band, which is the only way off this screen -- past the edge of the display. Tidiness
    # is not worth that.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Box", _FakeText)
    monkeypatch.setattr(mod, "Text", _FakeText)
    monkeypatch.setattr(mod, "TitleBox", _FakeText)
    # A row is a plain Tk label gridded into the section frame, not a guizero child of it.
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None, s_12=12)
    panel._pages = panel.paginate()
    panel._page_box = _FakeText(None)
    panel._page_box.children = []
    drawn = (300, 340, 380)
    panel._page_box.tk.holders = [SimpleNamespace(winfo_reqwidth=lambda width=width: width) for width in drawn]
    # Pinning the outer pair to 380 costs the page another 80px, and it has 20.
    panel._width_px = sum(drawn) + 20

    panel._render_page()

    assert panel._page_box.tk.columns == []
    # With room for it, the same page is matched: what is being tested is the affording,
    # not the matching.
    panel._page_box.tk.columns = []
    panel._width_px = sum(drawn) + 80
    panel._render_page()
    assert panel._page_box.tk.columns == [(0, {"minsize": 380}), (COLUMNS - 1, {"minsize": 380})]


def test_the_columns_are_filled_after_everything_else_is_on_the_page(monkeypatch) -> None:
    # The bug this guards, and it is guizero's, not Tk's: adding a widget to a grid
    # container re-grids the widgets already in it, each from its own align -- so the
    # sticky that makes a column spend its cell was replaced by "N" the moment the next
    # column was created, and the first column drew at its text width, centred in the cell
    # it had been widened to, with half the difference showing as a gap before the middle
    # column. Filling them last is the fix, and "last" includes after the page label.
    class _Regridding(_FakeText):
        """A stand-in that re-grids its siblings the way guizero does."""

        def __init__(self, parent, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            if isinstance(parent, _FakeText):
                for sibling in parent.gridded:
                    sibling.tk.sticky = "N"  # from align="top", which is what these are
                parent.gridded.append(self)

    _FakeText.instances = []
    monkeypatch.setattr(mod, "Box", _Regridding)
    monkeypatch.setattr(mod, "Text", _Regridding)
    monkeypatch.setattr(mod, "TitleBox", _Regridding)
    # The rows do not join in: a plain Tk label is not a guizero child, so it neither re-grids
    # its siblings nor is re-gridded by them -- which is also why they are no longer un-padded
    # (see _place_row).
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(_oversized_profile())
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None, s_12=12)
    panel._pages = panel.paginate()
    panel._page_box = _Regridding(None)
    panel._page_box.children = []
    assert panel.page_count > 1, "the page label has to be one of the widgets added after the columns"

    panel._render_page()

    columns = panel._page_box.gridded[:COLUMNS]
    assert [holder.tk.sticky for holder in columns] == ["new"] * COLUMNS


def test_a_render_tk_cannot_measure_leaves_the_columns_alone(monkeypatch) -> None:
    # A fake render, or a page Tk has not laid out yet: the screen is drawn either way,
    # with each column its own width, rather than raising on a widget that cannot be asked.
    monkeypatch.setattr(mod, "Box", _FakeText)
    monkeypatch.setattr(mod, "Text", _FakeText)
    monkeypatch.setattr(mod, "TitleBox", _FakeText)
    # A row is a plain Tk label gridded into the section frame, not a guizero child of it.
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None, s_12=12)
    panel._pages = panel.paginate()
    panel._page_box = _FakeText(None)
    panel._page_box.children = []

    panel._render_page()  # no holders to measure

    assert panel._page_box.tk.columns == []


def test_a_section_note_is_drawn_under_its_rows(monkeypatch) -> None:
    # Footnote-sized and grey, like the "*" line under the columns: it says something about
    # the rows above it rather than being one of them. It spans both of the section's
    # columns because it belongs to the section, not to any one input -- there is no keycap
    # to draw beside it, so it gets the whole width of the column less its chrome.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_note(_section(), "Hold for 3 seconds", 4, 400)

    (note,) = _FakeLabel.instances
    assert note.kwargs["text"] == "Hold for 3 seconds"
    assert note.gridded == {"row": 4, "column": 0, "columnspan": mod.ENTRY_COLUMNS, "sticky": "w"}
    assert note.kwargs["font"][1] == mod.FOOTNOTE_SIZE
    assert note.kwargs["foreground"] == mod.FOOTNOTE_FG
    # In the plain weight, which is what an aside is: the page's other footnote, outside any
    # section, is drawn the same way.
    assert note.kwargs["font"] == (panel._ruler.family, mod.FOOTNOTE_SIZE)
    assert note.kwargs["wraplength"] == 400 - mod.ENTRY_CHROME_PX


def test_every_section_note_on_the_page_is_drawn(monkeypatch) -> None:
    # The bundled screen has one: the admin panel's three-second hold, which used to be
    # four copies of "(hold 3s)" on the four rows it is true of. A note the packer counts
    # and the renderer forgets would leave the reader nothing to explain them.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Box", _FakeText)
    monkeypatch.setattr(mod, "Text", _FakeText)
    monkeypatch.setattr(mod, "TitleBox", _FakeText)
    # A row is a plain Tk label gridded into the section frame, not a guizero child of it.
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None, s_12=12)
    panel._pages = panel.paginate()
    panel._page_box = _FakeText(None)
    panel._page_box.children = []

    panel._render_page()

    notes = {section.note for column in panel._pages[0] for section in column if section.note}
    drawn = {widget.kwargs.get("text") for widget in _FakeText.instances + _FakeLabel.instances}
    assert notes, "the bundled admin section carries one"
    assert notes <= drawn


def test_the_action_text_wraps_within_its_own_column(monkeypatch) -> None:
    # The renderer has to wrap where the packer counted it would, or a column that was
    # budgeted to fit runs past the bottom of the display.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)
    plain = ControlEntry("Up / Down", "Smoke down / up")

    panel._render_entry(_section(), plain, 0, 203)

    _keycap, action = _FakeLabel.instances
    assert action.kwargs["wraplength"] == 203

    # And a row with a note gets what is left of that once the note is drawn beside it.
    _FakeLabel.instances = []
    noted = ControlEntry("Up / Down", "Boost / brake speed", "repeats")

    panel._render_entry(_section(), noted, 0, 400)

    _keycap, action, _note = _FakeLabel.instances
    wrapped = action.kwargs["wraplength"]
    assert wrapped == 400 - panel._note_px(noted)
    # One sum, done in both places: what the packer charged the row is what Tk is told to
    # wrap it at. Priced apart, the note is the row the column was not budgeted for.
    assert ControlsPanel.entry_rows(noted, panel._ruler, 400) == panel._ruler.wrapped_rows(noted.action, wrapped)

    # A row whose note would leave the action nothing gets the floor, not a negative wrap:
    # Tk reads that as "no wrapping" and truncates the line at the edge of the column.
    _FakeLabel.instances = []

    panel._render_entry(_section(), noted, 0, panel._note_px(noted))

    _keycap, action, _note = _FakeLabel.instances
    assert action.kwargs["wraplength"] == mod.MIN_ACTION_WRAP_PX
    assert ControlsPanel.entry_rows(noted, panel._ruler, panel._note_px(noted)) >= 1


def test_a_rows_note_is_drawn_beside_it_a_size_down(monkeypatch) -> None:
    # What was asked for, and where the width came from: the parenthesised phrase is an
    # aside on the action rather than part of it, so it is drawn at NOTE_SIZE -- the size
    # every other aside on the screen is drawn at -- in a column of its own, which also
    # lines the parentheses up down the section.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_entry(_section(), ControlEntry("Up / Down", "Boost / brake speed", "repeats"), 3)

    _keycap, action, note = _FakeLabel.instances
    assert action.kwargs["text"] == "Boost / brake speed", "the note must not be inside the action any more"
    assert action.kwargs["font"][1] == mod.ENTRY_SIZE
    assert note.kwargs["text"] == "(repeats)"
    assert note.kwargs["font"][1] == mod.NOTE_SIZE < mod.ENTRY_SIZE
    # Its own grid column, on the row it belongs to.
    assert (action.gridded["column"], action.gridded["row"]) == (1, 3)
    assert (note.gridded["column"], note.gridded["row"]) == (2, 3)
    # And the same colour as the action: these two words are sometimes the whole of what a
    # row is telling you, and greying them as well as shrinking them puts them past reading.
    assert note.kwargs["foreground"] == mod.ENTRY_FG == action.kwargs["foreground"]


def test_a_row_with_no_note_spans_the_column_the_notes_use(monkeypatch) -> None:
    # Otherwise the note column is empty on that row and the section pays for it anyway --
    # 75px on the bundled Global section, whose longest row carries no note. Spanning is what
    # makes an aligned note column free; see test_a_section_is_only_charged_for_the_notes.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_entry(_section(), ControlEntry("Left / Right", "Smoke down / up"), 2)

    keycap, action = _FakeLabel.instances
    assert keycap.gridded == {"row": 2, "column": 0, "columnspan": 1, "sticky": "w"}
    assert action.gridded == {"row": 2, "column": 1, "columnspan": 2, "sticky": "w"}


def test_a_row_is_built_in_a_single_call(monkeypatch) -> None:
    # Why the help screen is quick to build, and the invariant that keeps it so: everything a
    # cell needs is a constructor argument, so drawing one is two round trips into Tcl -- the
    # label and its grid -- against the ~200 a guizero Text cost, because guizero reads every
    # option back off a new widget to remember its defaults and then re-applies seven
    # inherited text properties, each of which asks for the option list again. Measured on the
    # bundled page: 0.93ms a label against 0.07ms, so 85ms of a 92-label page against 7ms,
    # which is the whole of the stutter the prewarm caused on the Deck.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_entry(_section(), ControlEntry("Up / Down", "Boost / brake speed", "repeats"), 0, 400, _FRAME_BG)
    panel._render_note(_section(), "Hold for 3 seconds", 1, 400, _FRAME_BG)

    assert len(_FakeLabel.instances) == 4
    for label in _FakeLabel.instances:
        assert label.configs == [], "a cell told something afterwards is a round trip that was not needed"
        assert {"text", "font", "foreground", "background"} <= set(label.kwargs)


def test_the_rows_carry_no_grid_padding(monkeypatch) -> None:
    # Not an oversight, and worth a test because it looks like one: this is the geometry the
    # screen has always been drawn in. The old renderer asked for pady=2 and padx=(4, 8) on
    # every row and got them on almost none -- guizero re-grids every child of a container each
    # time another joins it, from that child's grid and align alone, so each row's padding was
    # thrown away by the next row added to the same section, and only the last row of each kept
    # it. Honouring it measures 12px a row: 48px on the page, which puts the Deck at its widest
    # font 52px past the right edge of the display against 4px today.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_entry(_section(), ControlEntry("Up / Down", "Boost / brake speed", "repeats"), 0)
    panel._render_note(_section(), "Hold for 3 seconds", 1)

    for label in _FakeLabel.instances:
        assert set(label.gridded) == {"row", "column", "columnspan", "sticky"}, label.kwargs["text"]
    # The height budget allows what is not drawn, which is the safe direction: a column of
    # rows shorter than the budget thinks cannot run off the bottom of the display.
    assert mod.ROW_PADDING_PX > 0


def test_the_rows_are_told_the_colour_their_section_is_drawn_in(monkeypatch) -> None:
    # guizero handed a new widget its master's background; a plain Tk label is born in the
    # system's own window colour, which behind the text of a white section is a grey block. So
    # the frame is asked once per section -- not once per row -- and every row of it is told.
    _FakeText.instances = []
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Box", _FakeText)
    monkeypatch.setattr(mod, "Text", _FakeText)
    monkeypatch.setattr(mod, "TitleBox", _FakeText)
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None, s_12=12)

    panel._render_column(_FakeText(None), panel.paginate()[0][0], 0)

    assert _FakeLabel.instances, "the column has rows"
    keycaps = [label for label in _FakeLabel.instances if label.kwargs["background"] == mod.KEYCAP_BG]
    assert keycaps, "a keycap is drawn on its own colour, as a keycap"
    assert all(label.kwargs["background"] in (_FRAME_BG, mod.KEYCAP_BG) for label in _FakeLabel.instances)
    # And a frame that cannot be asked leaves the rows Tk's own colour rather than raising:
    # measuring and asking are improvements on drawing, never requirements for it.
    assert panel._section_background(SimpleNamespace(tk=object())) == ""


def test_the_rows_are_drawn_in_the_font_the_ruler_measured(monkeypatch) -> None:
    # Measuring and drawing have to agree, or the budget is not the budget: the keycap is
    # measured bold because that is what it is drawn in, and this is where the two meet. The
    # renderer takes the family from the ruler rather than looking it up again.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)
    panel._ruler = mod.TextRuler(measure=len, row_px=30, footnote_px=15, family="Helvetica")

    panel._render_entry(_section(), ControlEntry("A", "Ring bell"), 0)

    keycap, action = _FakeLabel.instances
    assert keycap.kwargs["font"] == ("Helvetica", mod.ENTRY_SIZE, "bold")
    assert action.kwargs["font"] == ("Helvetica", mod.ENTRY_SIZE)
    # With nothing to measure with, the named font stands in as a family and Tk substitutes
    # its own default -- which is what an unmeasured screen was drawn in before.
    assert mod.ESTIMATED_RULER.family == mod.DEFAULT_FONT_NAME


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # The four focus-scoped panel headings, and the one that carries the "*" as well.
        (CATALOG_PANEL_TITLE, ("Catalog Panel", "(w focus)", "")),
        (f"{CATALOG_PANEL_TITLE} *", ("Catalog Panel", "(w focus)", "*")),
        # A section too tall for its column: both parentheses go small together, since both
        # say when rather than what.
        (f"{BUTTONS_TITLE} (cont.)", ("Buttons", "(w focus) (cont.)", "")),
        # Nothing to shrink, which is most of them -- returned whole rather than as a head
        # with an empty qualifier, so the renderer leaves the frame's own title alone.
        (POPUP_PANEL_TITLE, (POPUP_PANEL_TITLE, "", "")),
        (f"{GLOBAL_CHORD_TITLE} *", (f"{GLOBAL_CHORD_TITLE} *", "", "")),
    ],
)
def test_a_heading_splits_into_what_is_scanned_and_what_qualifies_it(title, expected) -> None:
    assert mod.heading_parts(title) == expected


def test_a_heading_qualifier_is_drawn_a_size_down(monkeypatch) -> None:
    # "(w focus)" says when the rows below apply, which is read once and then known, where
    # the panel type is what an eye scanning the headings comes back to. A LabelFrame's own
    # title is one string in one font, so two sizes means handing it a labelwidget.
    #
    # The "*" stays the size of the heading it marks: it points at the footnote under the
    # columns rather than saying anything itself.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Frame", _FakeFrame)
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    monkeypatch.setattr(mod.tkfont, "nametofont", lambda *_a, **_k: SimpleNamespace(actual=lambda _key: "Helvetica"))
    panel = _panel(ControlProfile.load(None))
    box = SimpleNamespace(tk=_FakeFrameTk())

    panel._render_heading(box, f"{CATALOG_PANEL_TITLE} *")

    assert [label.kwargs["text"] for label in _FakeLabel.instances] == ["Catalog Panel", "(w focus)", "*"]
    assert [label.kwargs["font"][1] for label in _FakeLabel.instances] == [
        mod.SECTION_SIZE,
        mod.NOTE_SIZE,
        mod.SECTION_SIZE,
    ]
    # Bold and the heading colour throughout: the qualifier is part of the heading, not a
    # footnote to it, and 12pt unbolded grey is close to invisible at arm's length.
    assert all(label.kwargs["font"][2] == "bold" for label in _FakeLabel.instances)
    assert all(label.kwargs["foreground"] == mod.SECTION_FG for label in _FakeLabel.instances)
    assert [config for config in box.tk.configs if "labelwidget" in config], "the frame has to be given the widget"


def test_a_heading_with_nothing_to_qualify_is_left_as_one_string(monkeypatch) -> None:
    # Most of them: no parentheses, nothing to shrink, and no reason to build three widgets
    # and a frame to draw what the LabelFrame draws itself.
    _FakeLabel.instances = []
    monkeypatch.setattr(mod, "Frame", _FakeFrame)
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    box = SimpleNamespace(tk=_FakeFrameTk())

    panel._render_heading(box, f"{POPUP_PANEL_TITLE} *")

    assert _FakeLabel.instances == []
    assert box.tk.configs == []


def test_a_heading_tk_cannot_split_is_drawn_in_one_size(monkeypatch) -> None:
    # Measuring and building widgets is an improvement on the plain title, never a
    # requirement for drawing it: a stand-in widget, or no display, leaves the heading as the
    # frame was created with it rather than raising on the way to a smaller "(w focus)".
    monkeypatch.setattr(mod, "Frame", _FakeFrame)
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))

    panel._render_heading(SimpleNamespace(tk=object()), CATALOG_PANEL_TITLE)


def test_a_real_labelframe_accepts_the_split_heading() -> None:
    # The fakes above cannot say whether Tk will take a labelwidget on a LabelFrame that also
    # grids the section's rows inside it, which is the one thing about this that could fail
    # on the machine rather than in the arithmetic.
    tk = pytest.importorskip("tkinter")
    from tkinter import font as tkfont

    try:
        root = tk.Tk()
    except tk.TclError as exception:  # pragma: no cover - depends on the display
        pytest.skip(f"no display to draw against: {exception}")
    try:
        frame = tk.LabelFrame(root, text=CATALOG_PANEL_TITLE)
        panel = _panel(ControlProfile.load(None))

        panel._render_heading(SimpleNamespace(tk=frame), f"{CATALOG_PANEL_TITLE} *")

        name = frame.cget("labelwidget")
        assert name, "without this the heading is drawn in one size"
        parts = root.nametowidget(name).winfo_children()
        assert [part.cget("text") for part in parts] == ["Catalog Panel", "(w focus)", "*"]
        sizes = [tkfont.Font(root=root, font=part.cget("font")).actual("size") for part in parts]
        assert sizes == [mod.SECTION_SIZE, mod.NOTE_SIZE, mod.SECTION_SIZE]
    finally:
        root.destroy()


def test_the_sections_are_outlined_in_a_single_line(monkeypatch) -> None:
    # The gap between the columns, which is not padding: the columns are flush (padx=0, every
    # section packed fill="x"), and what showed between them was two section frames' own
    # 2px groove -- dark, light, light, dark -- of which the two light pixels read as a gap.
    # One line each, and two neighbours meet in a single rule with no white in it.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Box", _FakeText)
    monkeypatch.setattr(mod, "Text", _FakeText)
    monkeypatch.setattr(mod, "TitleBox", _FakeText)
    # A row is a plain Tk label gridded into the section frame, not a guizero child of it.
    monkeypatch.setattr(mod, "Label", _FakeLabel)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None, s_12=12)

    panel._render_column(_FakeText(None), panel.paginate()[0][0], 0)

    frames = [widget for widget in _FakeText.instances if widget.kwargs.get("layout") == "grid"]
    assert frames, "the sections are the frames drawn with a border"
    assert all(frame.kwargs["border"] == mod.SECTION_BORDER == 1 for frame in frames)
    # In the one call that also gives the frame its heading font and colour: guizero's three
    # text properties each read the widget's font back and ask it for its option list first,
    # and nothing inherits from this frame any more -- its rows are plain Tk labels.
    for frame in frames:
        (config,) = [config for config in frame.tk.configs if "relief" in config]
        assert config["relief"] == mod.SECTION_RELIEF
        assert config["font"][1:] == (mod.SECTION_SIZE, "bold")
        assert config["foreground"] == mod.SECTION_FG
    # And the row model follows it, or the columns are budgeted for a taller heading than
    # they draw and give back a row they could have had.
    assert mod.TITLE_BOX_BORDER_PX == 2 * mod.SECTION_BORDER


def test_every_bundled_section_is_drawable_within_its_column() -> None:
    # What the width budget promises, checked against the strings the screen really draws:
    # at the Deck's budget every section fits the column it is packed into, keycaps and all,
    # so no column has to grow past its share and take the page off the edge of the display.
    # (What Tk makes of it is what scripts/controlspreview.py is for -- laying the real
    # widgets out here hangs a headless run.)
    panel = _panel(ControlProfile.load(None))
    panel._column_px = ControlsPanel.column_widths(1274)

    for page in panel.paginate():
        for index, column in enumerate(page):
            budget = panel.column_px[index]
            for section in column:
                wrap_px = panel.action_wrap_px(section, budget)
                keycap = max(panel._ruler.width(mod.keycap_text(entry)) for entry in section.entries)
                assert keycap + wrap_px + mod.ENTRY_CHROME_PX <= budget, (section.title, index)
                # And the budget is one text really fits in, not the floor a column too
                # narrow for its keycaps falls back to.
                assert wrap_px > mod.MIN_ACTION_WRAP_PX, (section.title, index)
