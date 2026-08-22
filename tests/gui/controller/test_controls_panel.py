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

from src.pytrain.gui.controller.control_labels import ControlEntry, ControlSection, controls_summary
import src.pytrain.gui.controller.controls_panel as mod
from src.pytrain.gui.controller.controls_panel import COLUMNS, ROWS_PER_COLUMN, ControlsPanel
from src.pytrain.gui.controller.steam_deck_input import ControlProfile

BUNDLED = Path("src/pytrain/gui/controller/steam_deck_default.json")


def _panel(profile: ControlProfile | None) -> ControlsPanel:
    # paginate() needs no Tk, so skip __init__ and set only what it reads.
    panel = ControlsPanel.__new__(ControlsPanel)
    panel._profile = profile
    panel._page = 0
    panel._pages = ()
    panel._page_box = None
    return panel


def _oversized_profile() -> ControlProfile:
    """A profile far larger than the bundled one, to force pagination.

    Sized past COLUMNS * ROWS_PER_COLUMN so it spans pages however those constants are
    later tuned -- the point is the paging behaviour, not any particular capacity.
    """
    data = copy.deepcopy(json.loads(BUNDLED.read_text(encoding="utf-8")))
    data["buttons"] = {str(index): {"action": "bell", "target": "focused"} for index in range(20)}
    pairs = list(itertools.combinations(range(20), 2))[: COLUMNS * ROWS_PER_COLUMN]
    data["chords"] = [{"buttons": list(pair), "action": "halt", "target": "global"} for pair in pairs]
    return ControlProfile.from_dict(data)


def test_bundled_profile_fits_on_one_page() -> None:
    # Paging is for custom profiles; the shipped layout should never need it.
    panel = _panel(ControlProfile.load(None))

    assert len(panel.paginate()) == 1


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

    assert "Buttons" in titles
    assert "Buttons (cont.)" in titles


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
    # taller, or the column overflows the display it was measured against.
    short = ControlEntry("A", "Ring bell")
    long = ControlEntry("L2", "Engine shutdown", "hold: with dialog")

    assert ControlsPanel.entry_rows(short) == 1
    assert ControlsPanel.entry_rows(long) == 2


def test_section_rows_counts_the_header_and_wrapped_entries() -> None:
    section = ControlSection(
        "Triggers",
        (
            ControlEntry("L2", "Engine shutdown", "hold: with dialog"),
            ControlEntry("R2", "Engine startup", "hold: with dialog"),
        ),
    )

    assert ControlsPanel.section_rows(section) == 1 + 2 + 2


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

    def config(self, **kwargs) -> None:
        self.configs.append(kwargs)

    def grid_configure(self, **kwargs) -> None:
        self.grids.append(kwargs)


class _FakeText:
    instances: list["_FakeText"] = []

    def __init__(self, _parent, **kwargs) -> None:
        self.kwargs = kwargs
        self.tk = _FakeTextTk()
        self.text_bold = None
        self.text_color = None
        self.bg = None
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


def test_the_wrap_predictor_agrees_with_the_pixel_budget() -> None:
    # The bug this guards: WRAP_CHARS and ACTION_WRAP_PX were written down separately and
    # drifted, so a 29-character line was budgeted one row while Tk wrapped it onto two.
    assert mod.WRAP_CHARS == int(mod.ACTION_WRAP_PX / mod.APPROX_CHAR_PX)
    # The predictor must not be more optimistic than the renderer.
    assert mod.WRAP_CHARS * mod.APPROX_CHAR_PX <= mod.ACTION_WRAP_PX


def test_no_bundled_entry_is_predicted_to_wrap() -> None:
    # Not a rule for all time -- a custom profile may well wrap -- but the shipped screen
    # reads better on one line per binding, and this catches a label growing past the
    # budget unnoticed.
    for section in controls_summary(ControlProfile.load(None)):
        for entry in section.entries:
            assert ControlsPanel.entry_rows(entry) == 1, (section.title, entry.input, entry.action)
