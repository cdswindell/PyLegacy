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
