"""A behavior-locking checkpoint for the graphical controller.

Written before any of the accessory/switch creation work, and asserting only what the
controller does *today*: which accessory panel each state resolves to, exactly which cells each
scope's operating screen shows, which gamepad context chain each panel claims, and -- the point
of the exercise -- that ``↵`` on a TMCC ID the store has never heard of drops straight back to
the entry keypad in every scope.

Nothing here is aspirational. Each assertion is a fact about the current code, so a later stage
that changes one of them changes it deliberately and everything else standing untouched is the
evidence that nothing else moved.

Headless throughout, in the style of ``test_keypad_view.py`` and ``test_engine_gui_transitions``:
guizero's widgets are replaced with the same shape of fakes those modules use, so there is no
display, no Tk main loop and no Base 3.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Callable

import pytest

import src.pytrain.gui.controller.engine_gui as gui_mod
import src.pytrain.gui.controller.keypad_view as mod
from src.pytrain.gui.controller.accessory_bindings import (
    ACC_ASC2_CONTEXT,
    ACC_BPC2_CONTEXT,
    ACC_CONTEXT,
    ACC_GENERIC_CONTEXT,
    ACC_SENSOR_TRACK_CONTEXT,
    PANEL_AMC2,
    PANEL_ASC2,
    PANEL_BPC2,
    PANEL_CONTEXT_CHAINS,
    PANEL_GENERIC,
    PANEL_SENSOR_TRACK,
    ROUTE_CONTEXT,
    SWITCH_CONTEXT,
)
from src.pytrain.gui.controller.engine_gui_conf import ENTER_KEY, ENTRY_LAYOUT
from src.pytrain.protocol.constants import CommandScope


class DummyTk:
    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._bindings: dict[str, list[Callable]] = {}
        self.after_idle_calls: list[tuple[Callable, tuple[Any, ...]]] = []
        # Records the last per-column grid_columnconfigure so the keypad-column lock can assert
        # which columns the reflow collapses (weight=0, minsize=0) and which it keeps.
        self._column_config: dict[int, dict[str, Any]] = {}

    def config(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def configure(self, **kwargs: Any) -> None:
        self.config(**kwargs)

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

    def after_idle(self, func: Callable, *args: Any) -> None:
        self.after_idle_calls.append((func, args))

    @staticmethod
    def grid_rowconfigure(_row: int, **_kwargs: Any) -> None:
        return

    def grid_columnconfigure(self, col: int, **kwargs: Any) -> None:
        self._column_config[col] = dict(kwargs)

    @staticmethod
    def grid_propagate(_value: bool) -> None:
        return

    @staticmethod
    def update_idletasks() -> None:
        return

    def winfo_reqheight(self) -> int:
        return int(self._config.get("height", 0))


class DummyWidget:
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        self.tk = DummyTk()
        self.visible = kwargs.get("visible", True)
        self.grid = kwargs.get("grid")
        self.width = kwargs.get("width")
        self.height = kwargs.get("height")
        self.text_color = kwargs.get("color", "black")
        self.enabled = True

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False


class DummyBox(DummyWidget):
    pass


class DummyTitleBox(DummyBox):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.text_size = kwargs.get("text_size")


class DummyText(DummyWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.value = kwargs.get("text", "")


class DummyButton(DummyWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.text = kwargs.get("text")
        self.image = kwargs.get("image")
        self.on_press = None
        self.on_repeat = None
        self.on_hold = None
        self.when_left_button_pressed = None
        self.when_left_button_released = None

    def update_command(self, command: Callable, args: list[Any] | None = None) -> None:
        self.on_press = (command, args or [])


class DummySlider(DummyWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.command = kwargs.get("command")
        self.value = 0


class DummyCheckBoxGroup(DummyWidget):
    """The Tk-backed string behavior ``CheckBoxGroup`` really has (see test_keypad_view)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._selected = str(kwargs.get("selected"))
        self._cursor = None

    @property
    def value(self) -> str:
        return self._selected

    @value.setter
    def value(self, value: Any) -> None:
        self._selected = str(value)

    @property
    def cursor(self) -> str | None:
        return self._cursor

    @cursor.setter
    def cursor(self, value: Any) -> None:
        self._cursor = None if value is None else str(value)


class DummyAccessoryState:
    """Stands in for ``AccessoryState``; the flags ``_panel_kind_for`` reads, and nothing else."""

    def __init__(self, tmcc_id: int = 19, **flags: bool) -> None:
        self.tmcc_id = tmcc_id
        self.address = tmcc_id
        self.scope = CommandScope.ACC
        self.relative_speed = 0
        self.is_sensor_track = False
        self.is_amc2 = False
        self.is_bpc2 = False
        self.is_asc2 = False
        for name, value in flags.items():
            setattr(self, name, value)


@pytest.fixture(autouse=True)
def _patch_widgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    monkeypatch.setattr(mod, "TitleBox", DummyTitleBox, raising=True)
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
    monkeypatch.setattr(mod, "CheckBoxGroup", DummyCheckBoxGroup, raising=True)
    monkeypatch.setattr(
        mod,
        "Amc2OpsPanel",
        lambda _host: SimpleNamespace(
            build=lambda _parent: None,
            update_from_state=lambda _state: None,
            refresh_layout=lambda: None,
        ),
        raising=True,
    )
    monkeypatch.setattr(mod, "find_file", lambda name: name, raising=True)


def _make_slider(
    _parent,
    title: str,
    command: Callable,
    frm: int,
    to: int,
    *,
    visible: bool = True,
    grid=(0, 0),
    level_text: str = "0",
    slider_width: int | None = None,
    slider_height: int | None = None,
    on_release: Callable | None = None,
    **_kwargs: Any,
):
    box = DummyBox(visible=visible, grid=list(grid))
    title_box = DummyTitleBox(box, title)
    level = DummyText(title_box, text=level_text)
    slider = DummySlider(box, visible=visible, width=slider_width, height=slider_height, command=command)
    slider.tk.config(from_=frm, to=to)
    if on_release is not None:
        slider.tk.bind("<ButtonRelease-1>", on_release, add="+")
    return box, title_box, level, slider


def _new_host(scope: CommandScope = CommandScope.ACC, tmcc_id: int = 19) -> SimpleNamespace:
    """A pane's worth of host attributes, enough for ``build`` and the mode transitions.

    ``make_keypad_button`` files cells into ``ops_cells`` / ``entry_cells`` exactly as
    ``EngineGui.make_keypad_button`` does, because which cells those two sets hold is precisely
    what ``entry_mode`` and ``enter_ops_mode_base`` act on.
    """

    @contextmanager
    def locked():
        yield

    host = SimpleNamespace()
    host.app = SimpleNamespace(tk=DummyTk())
    host.scope = scope
    host._scope_tmcc_ids = {s: 0 for s in CommandScope}
    host._scope_tmcc_ids[scope] = tmcc_id
    host.active_state = DummyAccessoryState(tmcc_id)
    host.button_size = 96
    host.slider_height = 320
    host.grid_pad_by = 2
    host.emergency_box_width = 180
    host.sensor_track_row_pady = 6
    for name in ("s_10", "s_12", "s_16", "s_18", "s_19", "s_22", "s_24", "s_30"):
        setattr(host, name, int(name.split("_")[1]))
    host.turn_on_image = host.turn_on_path = "on.jpg"
    host.turn_off_image = host.turn_off_path = "off.jpg"
    host.power_off_path = "off.png"
    host.power_on_path = "on.png"
    host.op_acc_image = "op-acc.jpg"
    host.image_box = DummyBox()
    host.keypad_box = None
    host.keypad_keys = None
    host.entry_cells = set()
    host.ops_cells = set()
    host.aux_cells = set()
    host.numeric_btns = {}
    host.locked = locked
    host.tmcc_id_text = DummyText(text="00")
    host.reset_btn = DummyButton()
    host.acc_overlay = None
    host.controller_view = SimpleNamespace(make_slider=_make_slider)
    host._controller_view = host.controller_view
    host.accessories = SimpleNamespace(configured_by_tmcc_id=lambda _tmcc_id: False)
    host.accessory_provider = SimpleNamespace(adapters_for_tmcc_id=lambda _tmcc_id: None)
    host.scope_tmcc_id = lambda s=None: host._scope_tmcc_ids.get(s or host.scope, 0)
    host.image_presenter = SimpleNamespace(update=lambda _tmcc_id: host.calls.append(("image", _tmcc_id)))

    host.calls: list[tuple] = []
    host.on_acc_command = lambda target, data=None: host.calls.append(("acc", target, data))
    host.on_engine_command = lambda *_a, **_k: host.calls.append(("engine",))
    host.on_keypress = lambda key: host.calls.append(("keypress", key))
    host.on_new_accessory = lambda state=None: host.calls.append(("new_accessory", state))
    host.on_new_route = lambda: host.calls.append(("new_route",))
    host.on_new_switch = lambda: host.calls.append(("new_switch",))
    host.reset_acc_overlay = lambda: host.calls.append(("reset_acc_overlay",))
    host.update_component_info = lambda tmcc_id, not_found_value=None: host.calls.append(("update_info", tmcc_id))
    host.do_command = lambda key: host.calls.append(("do_command", key))
    host.ops_mode = lambda update_info=False, state=None: host.calls.append(("ops_mode", update_info))
    host.make_recent = lambda _scope, _tmcc_id, state=None: False
    host.create_provisional_component = lambda scope_, tmcc_id_: (
        host.calls.append(("create_provisional", scope_, tmcc_id_)) or DummyAccessoryState(tmcc_id_)
    )
    host.on_info = lambda state=None: host.calls.append(("info", state))
    host.on_show_generic_acc_panel = lambda: host.calls.append(("show_generic",))
    host.on_show_native_acc_panel = lambda: host.calls.append(("show_native",))
    host.on_lcs_config_panel = lambda: host.calls.append(("lcs_config_panel",))
    host.on_set_key = lambda scope_, tmcc_id_: host.calls.append(("set_key", scope_, tmcc_id_))
    host.get_image = lambda _image, size=None: None
    host.on_configured_accessory = lambda _acc: None
    host.make_keypad_button = lambda *args, **kwargs: _keypad_button(host, *args, **kwargs)
    return host


def _keypad_button(
    host: SimpleNamespace,
    _parent,
    label: str | None = None,
    row: int = 0,
    col: int = 0,
    _size: int | None = None,
    *_args: Any,
    **kwargs: Any,
):
    cell = DummyBox(visible=kwargs.get("visible", True), grid=[col, row])
    btn = DummyButton(text=label, image=kwargs.get("image"))
    if kwargs.get("is_ops"):
        host.ops_cells.add(cell)
    if kwargs.get("is_entry"):
        host.entry_cells.add(cell)
    command = kwargs.get("command")
    if callable(command):
        args = kwargs["args"] if kwargs.get("args") is not None else [label]
        btn.on_press = (command, args)
    return cell, btn


def _built(scope: CommandScope = CommandScope.ACC, tmcc_id: int = 19) -> tuple[SimpleNamespace, mod.KeypadView]:
    host = _new_host(scope, tmcc_id)
    view = mod.KeypadView(host)
    view.build()
    return host, view


def _ops(host: SimpleNamespace, view: mod.KeypadView, state=None) -> None:
    view.enter_ops_mode_base()
    view.apply_ops_mode_ui_non_engine(state if state is not None else host.active_state)


# ---------------------------------------------------------------------------
# Panel selection: _panel_kind_for / accessory_panel_kind
# ---------------------------------------------------------------------------


def _kind_for(**flags: bool) -> str | None:
    host = _new_host()
    host.active_state = DummyAccessoryState(**flags)
    return mod.KeypadView(host).accessory_panel_kind


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({}, PANEL_GENERIC),
        ({"is_sensor_track": True}, PANEL_SENSOR_TRACK),
        ({"is_amc2": True}, PANEL_AMC2),
        ({"is_bpc2": True}, PANEL_BPC2),
        ({"is_asc2": True}, PANEL_ASC2),
    ],
)
def test_each_state_flag_resolves_to_its_own_panel(flags, expected) -> None:
    assert _kind_for(**flags) == expected


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        # An ASC2 draws everything a BPC2 does plus its own AUX1 key, so where both flags read
        # true -- a port whose control request has not settled -- the more specific one wins.
        ({"is_bpc2": True, "is_asc2": True}, PANEL_ASC2),
        ({"is_sensor_track": True, "is_asc2": True}, PANEL_SENSOR_TRACK),
        ({"is_sensor_track": True, "is_amc2": True}, PANEL_SENSOR_TRACK),
        ({"is_amc2": True, "is_asc2": True, "is_bpc2": True}, PANEL_AMC2),
    ],
)
def test_the_more_specific_panel_wins_where_flags_overlap(flags, expected) -> None:
    assert _kind_for(**flags) == expected


def test_an_unrecognised_lcs_port_falls_through_to_the_generic_panel() -> None:
    # ``is_lcs_component`` is deliberately not consulted: an STM2 is an LCS device and none of
    # the four named kinds, so it shows -- and reports showing -- the generic panel.
    assert _kind_for(is_lcs_component=True, is_stm2=True) == PANEL_GENERIC


def test_no_panel_is_reported_off_an_accessory_screen() -> None:
    host = _new_host(CommandScope.ENGINE)
    host.active_state = DummyAccessoryState()
    assert mod.KeypadView(host).accessory_panel_kind is None

    host = _new_host()
    host.active_state = None
    assert mod.KeypadView(host).accessory_panel_kind is None


def test_a_state_that_is_not_an_accessory_at_all_reports_no_panel() -> None:
    host = _new_host()
    host.active_state = SimpleNamespace(tmcc_id=19)
    assert mod.KeypadView(host).accessory_panel_kind is None


def test_a_train_scope_power_district_reports_the_bpc2_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyLcsProxyState:
        def __init__(self) -> None:
            self.tmcc_id = 4
            self.is_power_district = True

    monkeypatch.setattr(mod, "LcsProxyState", DummyLcsProxyState, raising=True)
    host = _new_host(CommandScope.TRAIN)
    host.active_state = DummyLcsProxyState()

    assert mod.KeypadView(host).accessory_panel_kind == PANEL_BPC2


def test_a_configured_accessory_adapter_is_unwrapped_before_the_flags_are_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyAdapter:
        def __init__(self, state) -> None:
            self.state = state
            self.tmcc_id = state.tmcc_id

    monkeypatch.setattr(mod, "ConfiguredAccessoryAdapter", DummyAdapter, raising=True)
    host = _new_host()
    host.active_state = DummyAdapter(DummyAccessoryState(is_asc2=True))

    assert mod.KeypadView(host).accessory_panel_kind == PANEL_ASC2


def test_the_panel_kind_may_be_asked_about_a_state_that_is_not_the_active_one() -> None:
    # What ``apply_ops_mode_ui_non_engine`` relies on: it is handed the state it is about to
    # display and asks about that one rather than about whatever the pane still holds.
    host = _new_host()
    host.active_state = DummyAccessoryState()
    view = mod.KeypadView(host)

    assert view._panel_kind_for(DummyAccessoryState(is_bpc2=True)) == PANEL_BPC2
    assert view.accessory_panel_kind == PANEL_GENERIC


# ---------------------------------------------------------------------------
# The cells each scope's operating screen shows
# ---------------------------------------------------------------------------


def test_route_ops_mode_shows_the_fire_key_alone() -> None:
    host, view = _built(CommandScope.ROUTE, 5)
    _ops(host, view, state=None)

    assert host.fire_route_cell.visible is True
    assert host.switch_thru_cell.visible is False
    assert host.switch_out_cell.visible is False
    assert host.ac_on_cell.visible is False
    assert host.acc_throttle_box.visible is False
    assert host.sensor_track_box.visible is False
    assert host.amc2_ops_box.visible is False
    assert host.keypad_box.visible is True
    assert ("new_route",) in host.calls
    assert host.reset_btn.enabled is False


def test_switch_ops_mode_shows_thru_and_out_and_nothing_else() -> None:
    host, view = _built(CommandScope.SWITCH, 7)
    _ops(host, view, state=None)

    assert host.switch_thru_cell.visible is True
    assert host.switch_out_cell.visible is True
    assert host.fire_route_cell.visible is False
    assert host.acc_throttle_box.visible is False
    assert host.keypad_box.visible is True
    assert ("new_switch",) in host.calls


def test_the_switch_screen_carries_its_own_set_and_info_keys() -> None:
    # The gap this stage closes: a switch now has a Set key of its own and an Info key. It needs
    # the latter because ``_refresh_component_view`` hides ``image_box`` outside Engine/Train/Acc,
    # so there is no long-press route to the info panel there.
    host, view = _built(CommandScope.SWITCH, 7)
    _ops(host, view, state=None)

    assert host.sw_set_cell.visible is True
    assert host.info_cell.visible is True


def test_generic_accessory_ops_mode_expands_the_aux_keys_and_shows_the_throttle() -> None:
    host, view = _built()
    _ops(host, view)

    assert all(cell.visible for cell in host.aux_cells)
    assert host.acc_throttle_box.visible is True
    assert host.ac_on_cell.visible is False
    assert host.ac_aux1_cell.visible is False
    assert host.ac_op_cell.visible is False
    assert host.sensor_track_box.visible is False
    assert host.amc2_ops_box.visible is False
    assert host.keypad_box.visible is True
    assert ("reset_acc_overlay",) in host.calls


def test_generic_accessory_ops_mode_rebinds_the_number_keys_to_accessory_commands() -> None:
    host, view = _built()
    _ops(host, view)

    assert host.numeric_btns[3].on_press == (host.on_acc_command, ["NUMERIC", 3])

    # And entry mode hands them straight back to the keypad.
    view.entry_mode(clear_info=False)
    assert host.numeric_btns[3].on_press == (host.on_keypress, ["3"])


def test_the_number_keys_start_out_bound_to_the_keypad() -> None:
    host, view = _built()

    assert host.numeric_btns[7].on_press == (view.on_keypress, ["7"])


def test_bpc2_ops_mode_shows_on_status_and_off() -> None:
    host, view = _built()
    _ops(host, view, DummyAccessoryState(is_bpc2=True))

    assert host.ac_on_cell.visible is True
    assert host.ac_status_cell.visible is True
    assert host.ac_off_cell.visible is True
    assert host.ac_aux1_cell.visible is False
    assert host.acc_throttle_box.visible is False
    assert all(not cell.visible for cell in host.aux_cells)
    assert host.keypad_box.visible is True


def test_asc2_ops_mode_adds_the_momentary_aux1_key_to_the_bpc2_set() -> None:
    host, view = _built()
    _ops(host, view, DummyAccessoryState(is_asc2=True))

    assert host.ac_on_cell.visible is True
    assert host.ac_status_cell.visible is True
    assert host.ac_off_cell.visible is True
    assert host.ac_aux1_cell.visible is True
    assert host.acc_throttle_box.visible is False


def test_each_lcs_panel_carries_a_key_to_the_generic_panel() -> None:
    # The gap this stage closes: from a BPC2 or ASC2 screen there is now a way to reach the
    # generic panel, which is where ``Set Address`` lives.
    host, view = _built()
    _ops(host, view, DummyAccessoryState(is_asc2=True))

    assert host.acc_generic_cell.visible is True
    # The Acc... toggle sits below "9" (row 3) and above "Off" (row 4) in the numeric column.
    assert host.acc_generic_cell.grid == [2, 3]
    assert host.acc_generic_btn.on_press == (host.on_show_generic_acc_panel, [])
    assert host.ac_op_cell.visible is False, "and the one free key is disabled without a configured accessory"
    assert host.ac_op_btn.enabled is False


# ---------------------------------------------------------------------------
# The width of the ops-only 4th keypad column, locked per view
# ---------------------------------------------------------------------------
#
# The one intended change of this stage: the 4th column (grid column 3) reserves
# space only where a view puts a visible key in it. Entry and the empty-column
# views (Route) collapse it; the views that fill it (Switch, generic accessory,
# BPC2 / ASC2) restore it. Every other locked expectation above is untouched.

# button_size + 2 * grid_pad_by -> 96 + 4 = 100 in this host.
_OCCUPIED_COL = {"weight": 1, "minsize": 100}
_COLLAPSED_COL = {"weight": 0, "minsize": 0}


def test_entry_mode_collapses_the_fourth_column() -> None:
    host, view = _built()
    view.entry_mode(clear_info=False)

    cfg = host.keypad_keys.tk._column_config
    assert cfg[0] == _OCCUPIED_COL
    assert cfg[1] == _OCCUPIED_COL
    assert cfg[2] == _OCCUPIED_COL
    assert cfg[3] == _COLLAPSED_COL


def test_route_ops_mode_collapses_the_fourth_column() -> None:
    host, view = _built(CommandScope.ROUTE, 5)
    _ops(host, view, state=None)

    assert host.keypad_keys.tk._column_config[3] == _COLLAPSED_COL


def test_switch_ops_mode_expands_the_fourth_column() -> None:
    host, view = _built(CommandScope.SWITCH, 7)
    _ops(host, view, state=None)

    assert host.keypad_keys.tk._column_config[3] == _OCCUPIED_COL


def test_generic_accessory_ops_mode_expands_the_fourth_column() -> None:
    host, view = _built()
    _ops(host, view)

    assert host.keypad_keys.tk._column_config[3] == _OCCUPIED_COL


def test_the_bpc2_panel_collapses_the_fourth_column() -> None:
    # BPC2 carries the Acc... toggle in the numeric column now, so its 4th column is empty.
    host, view = _built()
    _ops(host, view, DummyAccessoryState(is_bpc2=True))

    assert host.keypad_keys.tk._column_config[3] == _COLLAPSED_COL


def test_the_asc2_panel_expands_the_fourth_column() -> None:
    # ASC2 stacks its Set and LCS... keys in the 4th column.
    host, view = _built()
    _ops(host, view, DummyAccessoryState(is_asc2=True))

    assert host.keypad_keys.tk._column_config[3] == _OCCUPIED_COL


def test_returning_to_entry_recollapses_the_fourth_column() -> None:
    host, view = _built(CommandScope.SWITCH, 7)
    _ops(host, view, state=None)
    assert host.keypad_keys.tk._column_config[3] == _OCCUPIED_COL

    view.entry_mode(clear_info=False)
    assert host.keypad_keys.tk._column_config[3] == _COLLAPSED_COL


def test_sensor_track_ops_mode_replaces_the_keypad_with_the_sequence_box() -> None:
    host, view = _built()
    _ops(host, view, DummyAccessoryState(is_sensor_track=True))

    assert host.sensor_track_box.visible is True
    assert host.keypad_box.visible is False
    assert host.amc2_ops_box.visible is False
    assert host.acc_throttle_box.visible is False


def test_amc2_ops_mode_replaces_the_keypad_with_the_amc2_box() -> None:
    host, view = _built()
    host.amc2_ops_panel = SimpleNamespace(
        update_from_state=lambda state: host.calls.append(("amc2_update", state)),
        refresh_layout=lambda: host.calls.append(("amc2_layout",)),
    )
    state = DummyAccessoryState(is_amc2=True)

    _ops(host, view, state)

    assert host.amc2_ops_box.visible is True
    assert host.keypad_box.visible is False
    assert host.sensor_track_box.visible is False
    assert ("amc2_update", state) in host.calls
    assert ("amc2_layout",) in host.calls


def test_a_configured_accessory_puts_the_overlay_key_in_the_free_generic_slot() -> None:
    # ``ac_op_btn`` means "the more specific view of this id", and on the generic panel it sits
    # at [1, 4]; on an ASC2 panel it moves to [2, 3].
    adapter = SimpleNamespace(
        op_btn_image_path="op-acc.jpg",
        activate_tmcc_id=lambda tmcc_id: host.calls.append(("activate", tmcc_id)),
    )
    host, view = _built()
    host.accessories = SimpleNamespace(configured_by_tmcc_id=lambda _tmcc_id: True)
    host.accessory_provider = SimpleNamespace(adapters_for_tmcc_id=lambda _tmcc_id: [adapter])

    _ops(host, view)

    assert host.ac_op_cell.grid == [1, 4]
    assert host.ac_op_cell.visible is True
    assert host.ac_op_btn.enabled is True
    assert host.ac_op_btn.on_press == (host.on_configured_accessory, [adapter])
    assert ("activate", 19) in host.calls


def test_a_configured_accessory_on_an_asc2_panel_moves_the_overlay_key() -> None:
    adapter = SimpleNamespace(
        op_btn_image_path="op-acc.jpg",
        activate_tmcc_id=lambda _tmcc_id: None,
    )
    host, view = _built()
    host.accessories = SimpleNamespace(configured_by_tmcc_id=lambda _tmcc_id: True)
    host.accessory_provider = SimpleNamespace(adapters_for_tmcc_id=lambda _tmcc_id: [adapter])

    _ops(host, view, DummyAccessoryState(is_asc2=True))

    assert host.ac_op_cell.grid == [3, 2]
    assert host.ac_op_cell.visible is True


# ---------------------------------------------------------------------------
# Entry mode, ops mode, and the aux collapse/expand
# ---------------------------------------------------------------------------


def test_the_aux_keys_carry_the_grids_the_collapse_and_expand_move_them_between() -> None:
    # Four rows of ENTRY_LAYOUT, so the aux column is 3 and the two keys that move between
    # columns fall back to column 2 when collapsed. Column 3 row 2 is nobody's slot.
    host, _view = _built()
    row = len(ENTRY_LAYOUT)
    render = sorted(getattr(cell, "render_grid") for cell in host.aux_cells if hasattr(cell, "render_grid"))
    reset = sorted(getattr(cell, "reset_grid") for cell in host.aux_cells if hasattr(cell, "reset_grid"))

    assert row == 4
    assert render == [[3, 0], [3, 1], [3, 3], [3, 4]]
    assert reset == [[2, 3], [2, 4]]
    assert [3, 2] not in render, "the free slot the Info key is destined for"


def test_expanding_and_collapsing_moves_only_the_cells_with_both_grids() -> None:
    host, view = _built()
    with_reset = [cell for cell in host.aux_cells if hasattr(cell, "reset_grid")]

    view._expand_acc_aux_cells()
    assert all(cell.grid == getattr(cell, "render_grid") for cell in host.aux_cells if hasattr(cell, "render_grid"))

    view._collapse_acc_aux_cells()
    assert all(cell.grid == getattr(cell, "reset_grid") for cell in with_reset)
    # The two without a reset grid stay where the expand put them.
    assert all(
        cell.grid == getattr(cell, "render_grid")
        for cell in host.aux_cells
        if hasattr(cell, "render_grid") and not hasattr(cell, "reset_grid")
    )


def test_entry_mode_shows_the_entry_cells_and_hides_every_ops_cell() -> None:
    host, view = _built()
    _ops(host, view)

    view.entry_mode(clear_info=False)

    power_keys = {host.on_key_cell, host.off_key_cell}
    assert view.is_entry_mode is True
    assert all(cell.visible for cell in host.entry_cells - power_keys)
    assert all(not cell.visible for cell in host.ops_cells)
    assert host.keypad_box.visible is True
    assert host.image_box.visible is False, "hidden rather than repainted when the info is kept"
    assert view.reset_on_keystroke is True
    assert host.set_btn.visible is True
    assert host.on_key_cell.visible is False, "no start/shutdown keys outside engine and train scope"
    assert host.off_key_cell.visible is False
    assert host.reset_btn.enabled is False


def test_entry_mode_clears_the_component_info_by_default() -> None:
    host, view = _built()

    view.entry_mode()

    assert ("update_info", 0) in host.calls
    assert view.reset_on_keystroke is False


def test_entry_mode_hides_the_set_key_for_a_route_and_enables_reset_for_an_engine() -> None:
    host, view = _built(CommandScope.ROUTE, 5)
    view.entry_mode(clear_info=False)
    assert host.set_btn.visible is False

    host, view = _built(CommandScope.ENGINE, 34)
    view.entry_mode(clear_info=False)
    assert host.set_btn.visible is True
    assert host.on_key_cell.visible is True
    assert host.off_key_cell.visible is True
    assert host.reset_btn.enabled is True


def test_enter_ops_mode_base_hides_both_cell_sets_and_collapses_the_aux_keys() -> None:
    host, view = _built()
    view.entry_mode(clear_info=False)

    view.enter_ops_mode_base()

    assert view.is_entry_mode is False
    assert all(not cell.visible for cell in host.entry_cells)
    assert all(not cell.visible for cell in host.ops_cells)
    assert all(cell.grid == getattr(cell, "reset_grid") for cell in host.aux_cells if hasattr(cell, "reset_grid"))
    assert host.numeric_btns[5].on_press == (view.on_keypress, ["5"]), "the digits are the keypad's again"


def test_scope_keypad_forces_entry_mode_where_nothing_is_selected() -> None:
    host, view = _built(CommandScope.ACC, 0)

    view.scope_keypad()

    assert view.is_entry_mode is True
    assert host.keypad_box.visible is True


def test_scope_keypad_leaves_a_selected_component_in_ops_mode() -> None:
    host, view = _built()
    _ops(host, view)

    view.scope_keypad()

    assert view.is_entry_mode is False


# ---------------------------------------------------------------------------
# Enter on an id the store has never heard of
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scope",
    [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ROUTE],
)
def test_enter_on_an_unknown_id_returns_to_entry_mode_in_every_scope(scope) -> None:
    """The dead end that survives: creation is deliberately limited to Accessories and Switches.

    ``make_recent`` answers False whenever the store has no state for the id, and a
    non-creatable scope then lands back on the entry keypad.
    """
    host, view = _built(scope, 0)
    host.tmcc_id_text.value = "42"
    host.make_recent = lambda _scope, _tmcc_id, state=None: False
    _ops(host, view, state=None)

    view.on_keypress(ENTER_KEY)

    assert view.is_entry_mode is True
    assert not any(call[0] == "ops_mode" for call in host.calls)
    assert view.reset_on_keystroke is True, "and the next digit starts a fresh id"


@pytest.mark.parametrize("scope", [CommandScope.ACC, CommandScope.SWITCH])
def test_enter_on_an_unknown_id_creates_a_provisional_component(scope) -> None:
    """Changed by step 2: an undefined Accessory / Switch id is now created, not rejected."""
    host, view = _built(scope, 0)
    host.tmcc_id_text.value = "42"
    recorded: list[tuple] = []
    host.make_recent = lambda s, tmcc_id, state=None: recorded.append((s, tmcc_id)) or False

    view.on_keypress(ENTER_KEY)

    assert recorded == [(scope, 42)]
    assert ("create_provisional", scope, 42) in host.calls
    assert ("ops_mode", True) in host.calls


@pytest.mark.parametrize("tmcc_id", ["00", "01", "42", "98", "99"])
def test_enter_on_a_known_id_enters_ops_mode(tmcc_id) -> None:
    host, view = _built(CommandScope.ACC, 0)
    host.tmcc_id_text.value = tmcc_id
    host.make_recent = lambda _scope, _tmcc_id, state=None: True

    view.on_keypress(ENTER_KEY)

    assert ("ops_mode", False) in host.calls


# ---------------------------------------------------------------------------
# The gamepad follows the panel: input_contexts / _accessory_contexts
# ---------------------------------------------------------------------------


def _gui(scope: CommandScope, tmcc_id: int, kind: str | None) -> gui_mod.EngineGui:
    gui = gui_mod.EngineGui.__new__(gui_mod.EngineGui)
    gui.scope = scope
    gui._scope_tmcc_ids = {s: 0 for s in CommandScope}
    gui._scope_tmcc_ids[scope] = tmcc_id
    gui._keypad_view = SimpleNamespace(accessory_panel_kind=kind)
    return gui


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (PANEL_GENERIC, (ACC_GENERIC_CONTEXT, ACC_CONTEXT)),
        (PANEL_BPC2, (ACC_BPC2_CONTEXT, ACC_CONTEXT)),
        (PANEL_ASC2, (ACC_ASC2_CONTEXT, ACC_BPC2_CONTEXT, ACC_CONTEXT)),
        (PANEL_SENSOR_TRACK, (ACC_SENSOR_TRACK_CONTEXT, ACC_CONTEXT)),
        # AMC2 is absent from the table deliberately: its controls have no gamepad bindings, and
        # a chain of nothing but the base would claim every control and send none of them.
        (PANEL_AMC2, ()),
        (None, ()),
    ],
)
def test_each_panel_claims_the_pad_through_the_shared_chain_table(kind, expected) -> None:
    assert PANEL_CONTEXT_CHAINS.get(kind, ()) == expected

    gui = _gui(CommandScope.ACC, 19, kind)
    assert gui._accessory_contexts == expected
    assert gui.input_contexts == expected


def test_an_accessory_scope_with_nothing_selected_claims_nothing() -> None:
    gui = _gui(CommandScope.ACC, 0, PANEL_GENERIC)

    assert gui._accessory_contexts == ()
    assert gui.input_contexts == ()


def test_a_selected_switch_and_route_claim_their_own_contexts() -> None:
    assert _gui(CommandScope.SWITCH, 7, None).input_contexts == (SWITCH_CONTEXT,)
    assert _gui(CommandScope.ROUTE, 5, None).input_contexts == (ROUTE_CONTEXT,)


def test_an_unselected_switch_or_route_claims_nothing() -> None:
    assert _gui(CommandScope.SWITCH, 0, None).input_contexts == ()
    assert _gui(CommandScope.ROUTE, 0, None).input_contexts == ()


def test_an_engine_panel_remaps_nothing() -> None:
    assert _gui(CommandScope.ENGINE, 34, None).input_contexts == ()


def test_a_power_district_in_train_scope_claims_the_bpc2_chain() -> None:
    # The pane is showing a BPC2 panel even though the scope is Train, and the chain follows the
    # panel rather than the scope.
    gui = _gui(CommandScope.TRAIN, 4, PANEL_BPC2)

    assert gui.input_contexts == (ACC_BPC2_CONTEXT, ACC_CONTEXT)


def test_the_screen_and_the_pad_read_the_same_property() -> None:
    """The invariant every later stage has to preserve.

    ``apply_ops_mode_ui_non_engine`` draws from ``_panel_kind_for`` and the input layer resolves
    from ``accessory_panel_kind``, which is the same property applied to the active state. So a
    panel drawn one way cannot be claimed as another.
    """
    for flags, kind in (
        ({}, PANEL_GENERIC),
        ({"is_bpc2": True}, PANEL_BPC2),
        ({"is_asc2": True}, PANEL_ASC2),
        ({"is_sensor_track": True}, PANEL_SENSOR_TRACK),
        ({"is_amc2": True}, PANEL_AMC2),
    ):
        host, view = _built()
        state = DummyAccessoryState(**flags)
        host.active_state = state

        _ops(host, view, state)

        assert view.accessory_panel_kind == kind
        assert _gui(CommandScope.ACC, 19, kind).input_contexts == PANEL_CONTEXT_CHAINS.get(kind, ())
