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

import pytest

from src.pytrain.gui.controller.control_labels import controls_summary
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


def test_controls_panel_spans_the_window() -> None:
    # A pane is half the screen; the binding table is cramped in it.
    assert ControlsPanel.full_window.fget(_panel(ControlProfile.load(None))) is True


def test_other_panels_stay_inside_their_pane() -> None:
    # full_window has to be opt-in: every existing overlay belongs to its own pane, and
    # reparenting them to the window would move them.
    from src.pytrain.gui.controller.overlay_panel import OverlayPanel
    from src.pytrain.gui.controller.state_info_overlay import StateInfoOverlay

    assert OverlayPanel.full_window.fget(object()) is False
    assert StateInfoOverlay.full_window is OverlayPanel.full_window


def test_four_columns_now_that_it_has_the_width() -> None:
    # Three was what a 632px pane allowed; the point of spanning is using the rest.
    assert COLUMNS == 4
