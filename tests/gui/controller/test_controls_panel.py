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


@pytest.mark.parametrize("budget", range(ROWS_PER_COLUMN - 1, ROWS_PER_COLUMN + 5))
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


def test_the_action_text_is_configured_to_wrap(monkeypatch) -> None:
    # Without wraplength Tk neither wraps nor shrinks: the line is truncated, which is
    # what "Boost / brake speed (repeats)" was doing on the Deck.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Text", _FakeText)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_entry(object(), ControlEntry("Up / Down", "Boost / brake speed", "repeats"), 0)

    keycap, action = _FakeText.instances
    wrap = [cfg for cfg in action.tk.configs if "wraplength" in cfg]
    assert wrap, "action text must be given a wrap width"
    assert wrap[0]["wraplength"] == mod.ACTION_WRAP_PX
    assert wrap[0]["justify"] == "left"
    # The keycap must not wrap -- "L1 + R1" splitting across lines would look broken.
    assert not any("wraplength" in cfg for cfg in keycap.tk.configs)


def test_the_action_text_is_drawn_a_weight_lighter_than_its_keycap(monkeypatch) -> None:
    # Said rather than left alone, as the section note also has to say it: the row's
    # TitleBox bolds everything drawn inside it, so an action left to inherit came out
    # exactly as emphatic as the keycap beside it. That cost the keycap the one job its
    # bold is there for -- being found without reading the row -- and cost the row some 7%
    # of its width against a budget measured in the lighter weight, which is what broke
    # four lines on the Deck.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Text", _FakeText)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_entry(object(), ControlEntry("Up / Down", "Boost / brake speed", "repeats"), 0)

    keycap, action = _FakeText.instances
    assert keycap.text_bold is True
    assert action.text_bold is False


def test_the_rows_are_drawn_at_the_size_that_was_fitted(monkeypatch) -> None:
    # _fit_text gives back a point when a row will not fit its column, so the renderer has
    # to ask what size it settled on rather than reading the constant: drawing at 15pt what
    # was measured at 13 wraps exactly the rows the point was given back to save.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Text", _FakeText)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)
    panel._entry_size = mod.MIN_ENTRY_SIZE

    panel._render_entry(object(), ControlEntry("A", "Ring bell"), 0)

    keycap, action = _FakeText.instances
    assert keycap.kwargs["size"] == action.kwargs["size"] == mod.MIN_ENTRY_SIZE
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
                    text = mod.entry_text(entry)
                    assert panel._ruler.wrapped_rows(text, wrap_px) == 1, (section.title, text, wrap_px)
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
    action = max(len(mod.entry_text(entry)) for entry in section.entries)

    assert panel.action_wrap_px(section, 400) == 400 - keycap - mod.ENTRY_CHROME_PX
    assert panel.section_px(section) == keycap + action + mod.ENTRY_CHROME_PX
    # The estimate draws no such distinction and does not need to: a character count at the
    # high end of what a character measures is already generous enough for the bold.
    assert mod.ESTIMATED_RULER.keycap_width("Right stick") == mod.ESTIMATED_RULER.width("Right stick")


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
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Text", _FakeText)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_note(object(), "Hold for 3 seconds", 4, 400)

    (note,) = _FakeText.instances
    assert note.kwargs["text"] == "Hold for 3 seconds"
    assert note.kwargs["grid"] == [0, 4, 2, 1]
    assert note.kwargs["size"] == mod.FOOTNOTE_SIZE
    assert note.text_color == mod.FOOTNOTE_FG
    # Said rather than left alone: the section's TitleBox bolds everything inside it, so an
    # inherited font makes the aside as emphatic as the rows it qualifies.
    assert note.text_bold is False
    wrap = [cfg for cfg in note.tk.configs if "wraplength" in cfg]
    assert wrap[0]["wraplength"] == 400 - mod.ENTRY_CHROME_PX


def test_every_section_note_on_the_page_is_drawn(monkeypatch) -> None:
    # The bundled screen has one: the admin panel's three-second hold, which used to be
    # four copies of "(hold 3s)" on the four rows it is true of. A note the packer counts
    # and the renderer forgets would leave the reader nothing to explain them.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Box", _FakeText)
    monkeypatch.setattr(mod, "Text", _FakeText)
    monkeypatch.setattr(mod, "TitleBox", _FakeText)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_widgets: None, s_12=12)
    panel._pages = panel.paginate()
    panel._page_box = _FakeText(None)
    panel._page_box.children = []

    panel._render_page()

    notes = {section.note for column in panel._pages[0] for section in column if section.note}
    drawn = {widget.kwargs.get("text") for widget in _FakeText.instances}
    assert notes, "the bundled admin section carries one"
    assert notes <= drawn


def test_the_action_text_wraps_within_its_own_column(monkeypatch) -> None:
    # The renderer has to wrap where the packer counted it would, or a column that was
    # budgeted to fit runs past the bottom of the display.
    _FakeText.instances = []
    monkeypatch.setattr(mod, "Text", _FakeText)
    panel = _panel(ControlProfile.load(None))
    panel._gui = SimpleNamespace(cache=lambda *_w: None)

    panel._render_entry(object(), ControlEntry("Up / Down", "Boost / brake speed", "repeats"), 0, 203)

    _keycap, action = _FakeText.instances
    assert [cfg for cfg in action.tk.configs if "wraplength" in cfg][0]["wraplength"] == 203


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
