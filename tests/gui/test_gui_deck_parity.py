#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Compact (Steam Deck) parity for the creation, Info and panel-toggle work.

Everything added in this pass lands in ``EngineGui`` / ``KeypadView``, which ``SteamDeckGui``
hosts unchanged, so parity is asserted here rather than by touching the Deck GUI: the same cells
are built through a compact geometry path, and the same handlers are exercised on a pane-hosted
``EngineGui`` shell -- one carrying ``_parent`` and ``_parent_gui``, which is all a pane is.

The keypad fakes are the ones ``tests/gui/test_keypad_view.py`` already keeps faithful; they are
imported rather than copied so a drift in the real widget surface fails in one place.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest

from pytrain.gui.controller import engine_gui as engine_mod
from src.pytrain.protocol.constants import CommandScope
from tests.gui.test_keypad_view import (
    DummyAccessoryState,
    DummyBox,
    DummyButton,
    DummyCheckBoxGroup,
    DummyTitleBox,
    _flagged,
    _hold_button,
    _keypad_button,
    _make_slider,
    _new_host,
)
from tests.gui.test_keypad_view import mod as kv_mod

# ---------------------------------------------------------------------------
# The compact geometry the pane hands the keypad
# ---------------------------------------------------------------------------

COMPACT_BUTTON_SIZE = 62
PORTRAIT_BUTTON_SIZE = 96


def _geometry(compact: bool) -> engine_mod.EngineGui:
    """An ``EngineGui`` shell carrying only what the geometry properties read."""
    gui = engine_mod.EngineGui.__new__(engine_mod.EngineGui)
    gui._compact = compact
    gui.button_size = COMPACT_BUTTON_SIZE if compact else PORTRAIT_BUTTON_SIZE
    gui.width = 640 if compact else 480
    gui.height = 400 if compact else 800
    gui.s_18 = 18
    gui.s_20 = 20
    return gui


def test_the_compact_pane_bounds_the_info_box_and_the_portrait_one_does_not() -> None:
    compact = _geometry(True)
    assert compact.compact is True
    # 62 * 0.55 is under the floor, so the floor is what the pane gets.
    assert compact.info_box_height == 44
    assert compact.fit_info_box_height(300) == 44, "a taller requirement does not win on the pane"

    portrait = _geometry(False)
    assert portrait.info_box_height is None
    assert portrait.fit_info_box_height(300) == 300


def test_the_sequence_rows_are_padded_more_tightly_on_the_pane() -> None:
    # The one height the Sensor Track panel cannot spend, now that it also carries a footer
    # button: the ten radio rows have to fit the keypad-sized allocation either way.
    assert _geometry(True).sensor_track_row_pady == 5
    assert _geometry(False).sensor_track_row_pady == 6


def test_the_pane_clamps_the_image_box_and_portrait_takes_what_it_is_given() -> None:
    compact = _geometry(True)
    # min(available, 15% of the pane height, a third of the width), then 3:1.
    assert compact.fit_image_box_size(300, 600) == (60, 180)
    assert compact.fit_image_box_size(20, 600) == (20, 60), "a smaller allocation is not inflated"
    assert compact.fit_image_box_size(300, 90) == (30, 90), "nor is a narrow one overrun"
    assert compact.fit_image_box_size(-10, 600) == (0, 0), "and it never goes negative"

    assert _geometry(False).fit_image_box_size(300, 600) == (300, 600)


# ---------------------------------------------------------------------------
# Building the new cells through a compact host
# ---------------------------------------------------------------------------


class RecordingCheckBoxGroup(DummyCheckBoxGroup):
    """Keeps the kwargs the Sequence group is built with -- ``pady`` is the compact one."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.parent = args[0] if args else None
        self.kwargs = dict(kwargs)


class RecordingTitleBox(DummyTitleBox):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.children: list[Any] = []


def _hold_button_in(parent, text: str = "", command=None, args: Any = None, **kwargs: Any):
    btn = _hold_button(parent, text, command, args, **kwargs)
    btn.parent = parent
    btn.width = kwargs.get("width")
    btn.text_size = kwargs.get("text_size")
    if isinstance(parent, RecordingTitleBox):
        parent.children.append(btn)
    return btn


class FakeAmc2Panel:
    """The AMC2 panel as ``build()`` finds it, including the exposed toggle button."""

    def __init__(self, _host) -> None:
        self.panel_toggle_button = DummyButton()
        self.built: list[Any] = []

    def build(self, parent) -> None:
        self.built.append(parent)

    def update_from_state(self, _state) -> None:
        return

    def refresh_layout(self) -> None:
        return


@pytest.fixture(autouse=True)
def _patch_widgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kv_mod, "Box", DummyBox, raising=True)
    monkeypatch.setattr(kv_mod, "TitleBox", RecordingTitleBox, raising=True)
    monkeypatch.setattr(kv_mod, "AccessoryState", DummyAccessoryState, raising=True)
    monkeypatch.setattr(kv_mod, "CheckBoxGroup", RecordingCheckBoxGroup, raising=True)
    monkeypatch.setattr(kv_mod, "Amc2OpsPanel", FakeAmc2Panel, raising=True)
    monkeypatch.setattr(kv_mod, "HoldButton", _hold_button_in, raising=True)
    monkeypatch.setattr(kv_mod, "find_file", lambda name: name, raising=True)


def _host(compact: bool) -> SimpleNamespace:
    """``_new_host`` re-sized by the real geometry properties, so the pane's numbers are the
    ones the keypad is built with rather than numbers a test made up."""
    geometry = _geometry(compact)
    host = _new_host()
    host.button_size = geometry.button_size
    host.sensor_track_row_pady = geometry.sensor_track_row_pady
    host.emergency_box_width = geometry.width // 3
    host.make_keypad_button = lambda *args, **kwargs: _keypad_button(host, *args, **kwargs)
    host.controller_view = SimpleNamespace(make_slider=_make_slider)
    host._controller_view = host.controller_view
    return host


def _built(compact: bool, scope: CommandScope = CommandScope.ACC, tmcc_id: int = 19, state=None):
    host = _host(compact)
    host.scope = scope
    host._scope_tmcc_ids = {s: 0 for s in CommandScope}
    host._scope_tmcc_ids[scope] = tmcc_id
    host.active_state = state if state is not None else (DummyAccessoryState() if scope == CommandScope.ACC else None)
    view = kv_mod.KeypadView(host)
    view.build()
    return host, view


def _ops(host, view, state=None) -> None:
    view.enter_ops_mode_base()
    view.apply_ops_mode_ui_non_engine(state if state is not None else host.active_state)


@pytest.mark.parametrize("compact", [True, False])
def test_every_new_cell_lands_in_the_same_slot_on_the_pane_as_in_portrait(compact: bool) -> None:
    # No rows and no columns were added for the pane's sake, and none may be: the compact
    # keypad is the same grid, drawn smaller.
    host, _view = _built(compact)

    assert host.sw_set_cell.grid == [3, 0]
    assert host.info_cell.grid == [3, 2]
    # Acc... now sits below "9" in the numeric column; the ASC2 Set/LCS keys stack in column 3.
    assert host.acc_generic_cell.grid == [2, 3]
    assert host.acc_set_cell.grid == [3, 0]
    assert host.lcs_noop_cell.grid == [3, 1]
    assert host.info_btn.on_press == (host.on_info, [])
    assert host.acc_generic_btn.on_press == (host.on_show_generic_acc_panel, [])
    assert host.lcs_noop_btn.on_press == (_view.on_lcs_noop, [])
    assert host.acc_set_btn.on_press[0] == _view.on_acc_set_key
    assert host.sw_set_btn.on_press[0] == _view.on_switch_set_key


@pytest.mark.parametrize("compact", [True, False])
def test_the_new_cells_are_ops_cells_on_the_pane_too(compact: bool) -> None:
    host, view = _built(compact, CommandScope.SWITCH, 7)
    for cell in (host.sw_set_cell, host.info_cell, host.acc_generic_cell):
        assert cell in host.ops_cells
        assert cell not in host.entry_cells

    _ops(host, view)
    assert (host.sw_set_cell.visible, host.info_cell.visible) == (True, True)

    view.entry_mode(clear_info=False)
    assert (host.sw_set_cell.visible, host.info_cell.visible, host.acc_generic_cell.visible) == (False, False, False)


@pytest.mark.parametrize("compact", [True, False])
def test_the_sensor_track_footer_button_is_built_below_the_sequence_rows(compact: bool) -> None:
    host, _view = _built(compact)

    assert host.sensor_track_buttons.kwargs["pady"] == host.sensor_track_row_pady
    assert host.sensor_track_generic_btn.parent is host.sensor_track_box
    assert host.sensor_track_generic_btn.width == "fill"
    assert host.sensor_track_generic_btn.text_size == host.s_12
    assert host.sensor_track_generic_btn.on_press == (host.on_show_generic_acc_panel, [])
    # Appended after the group, which is what puts it under the last radio row.
    assert host.sensor_track_box.children == [host.sensor_track_generic_btn]


@pytest.mark.parametrize("compact", [True, False])
def test_the_amc2_header_toggle_is_wired_on_the_pane_too(compact: bool) -> None:
    host, _view = _built(compact)

    assert host.amc2_ops_panel.built == [host.amc2_ops_box]
    assert host.amc2_ops_panel.panel_toggle_button.on_press == (host.on_show_generic_acc_panel, [])

    command, args = host.amc2_ops_panel.panel_toggle_button.on_press
    command(*args)
    assert host.on_show_panel_calls == ["generic"]


@pytest.mark.parametrize("compact", [True, False])
def test_the_configured_overlay_key_is_sized_from_the_pane_button_size(compact: bool) -> None:
    # The one branch of the shared key with Deck-sensitive geometry: it paints an image, and
    # the image is asked for at the pane's button size.
    adapter = SimpleNamespace(op_btn_image_path="op-acc.jpg", activate_tmcc_id=lambda _tmcc_id: None)
    sizes: list[int] = []
    host, view = _built(compact)
    host.accessories = SimpleNamespace(configured_by_tmcc_id=lambda _tmcc_id: True)
    host.accessory_provider = SimpleNamespace(adapters_for_tmcc_id=lambda _tmcc_id: [adapter])
    host.on_configured_accessory = lambda _acc: None
    host.get_image = lambda image, size=None: sizes.append(size) or image

    _ops(host, view)

    assert host.ac_op_cell.visible is True
    assert host.ac_op_btn.on_press == (host.on_configured_accessory, [adapter])
    # The pane-hosted key wears the accessory's own op icon, not the generic op-screen.jpg.
    assert host.ac_op_btn.image == "op-acc.jpg"
    assert sizes == [host.button_size]
    assert host.ac_op_btn.tk._config["width"] == host.button_size
    assert host.ac_op_btn.tk._config["height"] == host.button_size


@pytest.mark.parametrize("compact", [True, False])
def test_the_way_back_from_a_forced_generic_panel_wears_the_device_icon(compact: bool) -> None:
    # The other meaning of the same key: it returns to the native BPC2 panel and now wears the
    # BPC2 device icon, asked for at the pane's own button size.
    state = _flagged(is_bpc2=True)
    sizes: list[int] = []
    host, view = _built(compact, state=state)
    host.get_image = lambda image, size=None: sizes.append(size) or image
    view.set_panel_kind_override("generic")

    _ops(host, view, state)

    assert view.accessory_panel_kind == "generic", "and the pad reads the same property"
    assert host.ac_op_btn.on_press == (host.on_show_native_acc_panel, [])
    assert host.ac_op_btn.image == kv_mod.BPC2_OP_IMAGE
    assert sizes == [host.button_size]
    assert host.info_cell.visible is True


@pytest.mark.parametrize("compact", [True, False])
def test_the_way_back_wears_the_configured_accessory_icon_on_the_pane(compact: bool) -> None:
    # When the forced-generic panel sits over a configured operating accessory, the way-back key
    # wears that accessory's own op icon -- asked for at the pane's button size, not op-asc2.jpg.
    state = _flagged(is_asc2=True)
    adapter = SimpleNamespace(op_btn_image_path="op-station.jpg", activate_tmcc_id=lambda _tmcc_id: None)
    sizes: list[int] = []
    host, view = _built(compact, state=state)
    host.accessories = SimpleNamespace(configured_by_tmcc_id=lambda _tmcc_id: True)
    host.accessory_provider = SimpleNamespace(adapters_for_tmcc_id=lambda _tmcc_id: [adapter])
    host.get_image = lambda image, size=None: sizes.append(size) or image
    view.set_panel_kind_override("generic")

    _ops(host, view, state)

    assert host.ac_op_btn.on_press == (host.on_show_native_acc_panel, [])
    assert host.ac_op_btn.image == "op-station.jpg"
    assert sizes == [host.button_size]


# ---------------------------------------------------------------------------
# The empty 4th column collapses through the compact geometry too
# ---------------------------------------------------------------------------
#
# The reflow lands wholly in ``KeypadView``, so a compact host reaches it by the same path a
# portrait one does; the widths simply derive from the pane's own ``button_size``.


def _cell_width(host) -> int:
    return host.button_size + (2 * host.grid_pad_by)


@pytest.mark.parametrize("compact", [True, False])
def test_entry_collapses_the_fourth_column_on_the_pane(compact: bool) -> None:
    host, view = _built(compact)
    view.entry_mode(clear_info=False)

    cfg = host.keypad_keys.tk._column_config
    assert cfg[0] == {"weight": 1, "minsize": _cell_width(host)}
    assert cfg[3] == {"weight": 0, "minsize": 0}
    assert cfg[4] == {"weight": 0, "minsize": 0}


@pytest.mark.parametrize("compact", [True, False])
def test_switch_ops_expands_the_fourth_column_on_the_pane(compact: bool) -> None:
    host, view = _built(compact, CommandScope.SWITCH, 7)
    _ops(host, view)

    assert host.keypad_keys.tk._column_config[3] == {"weight": 1, "minsize": _cell_width(host)}


@pytest.mark.parametrize("compact", [True, False])
def test_generic_accessory_ops_expands_both_extra_columns_on_the_pane(compact: bool) -> None:
    host, view = _built(compact)
    _ops(host, view)

    cfg = host.keypad_keys.tk._column_config
    assert cfg[3] == {"weight": 1, "minsize": _cell_width(host)}
    assert cfg[4] == {"weight": 1, "minsize": _cell_width(host)}


@pytest.mark.parametrize("compact", [True, False])
def test_the_bpc2_panel_collapses_the_fourth_column_on_the_pane(compact: bool) -> None:
    host, view = _built(compact)
    _ops(host, view, _flagged(is_bpc2=True))

    assert host.keypad_keys.tk._column_config[3] == {"weight": 0, "minsize": 0}


@pytest.mark.parametrize("compact", [True, False])
def test_the_asc2_panel_expands_the_fourth_column_on_the_pane(compact: bool) -> None:
    host, view = _built(compact)
    _ops(host, view, _flagged(is_asc2=True))

    assert host.keypad_keys.tk._column_config[3] == {"weight": 1, "minsize": _cell_width(host)}


@pytest.mark.parametrize("compact", [True, False])
def test_the_pad_width_tightens_to_the_occupied_columns_on_the_pane(compact: bool) -> None:
    # Entry: three numeric columns stand, the 4th and the throttle collapse -> three cells wide.
    host, view = _built(compact)
    cell = _cell_width(host)
    view.entry_mode(clear_info=False)

    assert host.keypad_keys.tk._config["width"] == 3 * cell
    assert host.keypad_box.tk._config["width"] == 3 * cell

    # Generic accessory: the 4th column and the throttle both fill -> five cells wide.
    host, view = _built(compact)
    _ops(host, view)

    assert host.keypad_keys.tk._config["width"] == 5 * cell
    assert host.keypad_box.tk._config["width"] == 5 * cell


@pytest.mark.parametrize("compact", [True, False])
def test_returning_to_entry_recollapses_the_fourth_column_on_the_pane(compact: bool) -> None:
    host, view = _built(compact, CommandScope.SWITCH, 7)
    _ops(host, view)
    assert host.keypad_keys.tk._column_config[3] == {"weight": 1, "minsize": _cell_width(host)}

    view.entry_mode(clear_info=False)
    assert host.keypad_keys.tk._column_config[3] == {"weight": 0, "minsize": 0}


# ---------------------------------------------------------------------------
# The Sensor Track cursor contract, with the footer button in place
# ---------------------------------------------------------------------------


def _sensor_track(compact: bool, value=None):
    state = _flagged(is_sensor_track=True)
    host, view = _built(compact, state=state)
    host.active_state = state
    host.repeat = 3
    if value is not None:
        host.sensor_track_buttons.value = value
    return host, view


@pytest.mark.parametrize("compact", [True, False])
def test_the_footer_button_did_not_disturb_the_cursor_stepping(compact: bool) -> None:
    host, view = _sensor_track(compact, value=4)

    assert view.step_sensor_track_sequence(1) == 5
    assert host.sensor_track_buttons.cursor == "5"
    assert host.sensor_track_buttons.value == "4", "the dot is what the track holds and it did not move"


@pytest.mark.parametrize("compact", [True, False])
@pytest.mark.parametrize(("start", "delta"), [(0, -1), (9, 1)])
def test_the_cursor_still_clamps_at_both_ends_of_the_ten_rows(compact: bool, start: int, delta: int) -> None:
    host, view = _sensor_track(compact, value=start)
    view.set_sensor_track_sequence(start)

    assert view.step_sensor_track_sequence(delta) is None
    assert host.sensor_track_buttons.cursor == str(start)
    assert host.sensor_track_buttons.value == str(start)


@pytest.mark.parametrize("compact", [True, False])
def test_the_dot_and_the_cursor_stay_separate_things(compact: bool) -> None:
    host, view = _sensor_track(compact, value=2)

    view.step_sensor_track_sequence(1)
    view.step_sensor_track_sequence(1)

    assert host.sensor_track_buttons.cursor == "4", "where the pad is pointing"
    assert host.sensor_track_buttons.value == "2", "what the track is programmed with"
    assert view.sensor_track_sequence == 2, "and the reader answers with the latter"


# ---------------------------------------------------------------------------
# A pane-hosted EngineGui behaves as a standalone one -- SteamDeckGui unchanged
# ---------------------------------------------------------------------------


class DummyState:
    def __init__(self, scope: CommandScope = CommandScope.ACC, tmcc_id: int = 42) -> None:
        self.scope = scope
        self.tmcc_id = tmcc_id
        self.is_comp_data_empty = True
        self.initialized: list[tuple] = []

    def initialize(self, scope: CommandScope = None, tmcc_id: int = None) -> None:
        self.scope, self.tmcc_id = scope, tmcc_id
        self.initialized.append((scope, tmcc_id))


def _engine(pane: bool, scope: CommandScope = CommandScope.ACC) -> engine_mod.EngineGui:
    """The same shell either way, differing only in what a pane actually is: a parent Box and
    the ``SteamDeckGui`` that owns it."""
    gui = engine_mod.EngineGui.__new__(engine_mod.EngineGui)
    gui.scope = scope
    gui._cv = threading.RLock()
    gui._scope_tmcc_ids = {s: 0 for s in CommandScope}
    gui._provisional = set()
    gui._state_store = SimpleNamespace(get_state=lambda *_a, **_k: None)
    gui._app = SimpleNamespace(tk=None)
    gui._parent = DummyBox() if pane else None
    gui._parent_gui = SimpleNamespace(name="steam_deck") if pane else None
    gui.calls = []
    gui._popup = SimpleNamespace(close=lambda: gui.calls.append("popup_closed"))
    gui.ops_mode = lambda update_info=True, state=None: gui.calls.append(("ops_mode", update_info))
    gui.make_recent = lambda s, t, state=None: gui.calls.append(("make_recent", s, t)) or True
    gui._request_options_rebuild = lambda: gui.calls.append("rebuild")
    gui._reset_catalog_configured_accessories = lambda: gui.calls.append("catalog_reset")
    keypad = SimpleNamespace(_forced=None)
    keypad.set_panel_kind_override = lambda kind: setattr(keypad, "_forced", kind)
    gui._keypad_view = keypad
    return gui


def test_a_pane_hosted_gui_roots_itself_in_its_pane() -> None:
    assert isinstance(_engine(True).root, DummyBox)
    standalone = _engine(False)
    assert standalone.root is standalone.app


@pytest.mark.parametrize("pane", [True, False])
@pytest.mark.parametrize("scope", [CommandScope.ACC, CommandScope.SWITCH])
def test_creation_works_the_same_hosted_in_a_pane(pane: bool, scope: CommandScope, monkeypatch) -> None:
    created = DummyState(scope, 0)
    monkeypatch.setattr(
        engine_mod.ComponentStateStore,
        "get_state",
        classmethod(lambda _cls, _scope, _tmcc_id, create=True: created),
    )
    gui = _engine(pane, scope)

    state = gui.create_provisional_component(scope, 42)

    assert state is created
    assert created.initialized == [(scope, 42)]
    assert gui.is_provisional(scope, 42) is True
    assert gui._scope_tmcc_ids[scope] == 42


@pytest.mark.parametrize("pane", [True, False])
def test_promotion_works_the_same_hosted_in_a_pane(pane: bool) -> None:
    gui = _engine(pane)
    gui._provisional.add((CommandScope.ACC, 42))

    assert gui.promote_component(DummyState(CommandScope.ACC, 42)) is True

    assert gui.calls == [("make_recent", CommandScope.ACC, 42), "rebuild", "catalog_reset"]
    assert gui.is_provisional(CommandScope.ACC, 42) is False


@pytest.mark.parametrize("pane", [True, False])
def test_the_panel_toggles_work_the_same_hosted_in_a_pane(pane: bool) -> None:
    gui = _engine(pane)

    gui.on_show_generic_acc_panel()
    assert gui._keypad_view._forced == "generic"

    gui.on_show_native_acc_panel()
    assert gui._keypad_view._forced is None

    assert gui.calls == [
        "popup_closed",
        ("ops_mode", False),
        "popup_closed",
        ("ops_mode", False),
    ]
