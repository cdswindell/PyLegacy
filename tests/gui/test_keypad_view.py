from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Callable

import pytest

import src.pytrain.gui.controller.keypad_view as mod
from src.pytrain.protocol.constants import CommandScope


class DummyTk:
    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._bindings: dict[str, list[Callable]] = {}
        self._after_calls: dict[int, tuple[int, Callable, tuple[Any, ...]]] = {}
        self._next_after_id = 1
        self._focus_owner = None

    def config(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def configure(self, **kwargs: Any) -> None:
        self.config(**kwargs)

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

    def after(self, delay_ms: int, func: Callable, *args: Any) -> int:
        after_id = self._next_after_id
        self._next_after_id += 1
        self._after_calls[after_id] = (delay_ms, func, args)
        return after_id

    def after_cancel(self, after_id: int) -> None:
        self._after_calls.pop(after_id, None)

    def run_after(self, after_id: int) -> None:
        delay_ms, func, args = self._after_calls.pop(after_id)
        _ = delay_ms
        func(*args)

    def focus_set(self) -> None:
        self._focus_owner = self

    def focus_displayof(self):
        return self._focus_owner

    def focus_get(self):
        return None

    @staticmethod
    def grid_rowconfigure(_row: int, **_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_columnconfigure(_col: int, **_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_propagate(_value: bool) -> None:
        return

    @staticmethod
    def update_idletasks() -> None:
        return

    def winfo_reqheight(self) -> int:
        return int(self._config.get("height", 0))

    def winfo_height(self) -> int:
        return self.winfo_reqheight()


class DummyWidget:
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        self.tk = DummyTk()
        self.visible = kwargs.get("visible", True)
        self.grid = kwargs.get("grid")
        self.border = kwargs.get("border", 0)
        self.align = kwargs.get("align")
        self.layout = kwargs.get("layout")
        self.width = kwargs.get("width")
        self.height = kwargs.get("height")
        self.bg = kwargs.get("bg", "white")
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

    def focus_set(self) -> None:
        self.tk.focus_set()


class DummyBox(DummyWidget):
    pass


class DummyTitleBox(DummyBox):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.text_size = kwargs.get("text_size")


class DummyText(DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = kwargs.get("text", "")
        self.font = kwargs.get("font")
        self.size = kwargs.get("size")
        self.bold = kwargs.get("bold", False)

    def clear(self) -> None:
        self.value = ""


class DummyButton(DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
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
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.command = kwargs.get("command")
        self.value = 0


class DummyCheckBoxGroup(DummyWidget):
    """``CheckBoxGroup`` as guizero really behaves, strings and all.

    ``CheckBoxGroup`` subclasses guizero's ``ButtonGroup`` without overriding ``value``, and
    that property is backed by a Tk ``StringVar``: the setter does ``self._selected.set(str(
    value))`` and the getter hands back what the variable holds. So the group never yields an
    ``int`` and never yields ``None`` -- clearing it with ``value = None``, which
    ``EngineGui.on_new_accessory`` does for a Sensor Track with no ``IrdaState``, leaves the
    literal string ``"None"`` behind. A double that round-tripped whatever it was handed would
    let code that reads the group pass here and raise on the pane.
    """

    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = kwargs.get("selected")

    @property
    def value(self) -> str:
        return self._selected

    @value.setter
    def value(self, value: Any) -> None:
        self._selected = str(value)


class DummyAccessoryState:
    def __init__(self, tmcc_id: int = 19, relative_speed: int = 0) -> None:
        self.tmcc_id = tmcc_id
        self.relative_speed = relative_speed
        self.is_sensor_track = False
        self.is_amc2 = False
        self.is_bpc2 = False
        self.is_asc2 = False


@pytest.fixture(autouse=True)
def _patch_widgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    monkeypatch.setattr(mod, "TitleBox", DummyTitleBox, raising=True)
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
    monkeypatch.setattr(mod, "CheckBoxGroup", DummyCheckBoxGroup, raising=True)
    monkeypatch.setattr(mod, "Amc2OpsPanel", lambda _host: SimpleNamespace(build=lambda _parent: None), raising=True)
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


def _new_host() -> SimpleNamespace:
    @contextmanager
    def locked():
        yield

    host = SimpleNamespace()
    host.app = SimpleNamespace(tk=DummyTk())
    host.scope = CommandScope.ACC
    host._scope_tmcc_ids = {CommandScope.ACC: 19}
    host.active_state = DummyAccessoryState()
    host.button_size = 96
    host.slider_height = 320
    host.grid_pad_by = 2
    host.emergency_box_width = 180
    host.sensor_track_row_pady = 6
    host.s_22 = 22
    host.s_24 = 24
    host.s_30 = 30
    host.s_18 = 18
    host.s_16 = 16
    host.s_19 = 19
    host.s_10 = 10
    host.turn_on_image = "on.jpg"
    host.turn_off_image = "off.jpg"
    host.turn_on_path = "on.jpg"
    host.turn_off_path = "off.jpg"
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
    host.make_keypad_button = lambda *_args, **kwargs: (DummyBox(visible=kwargs.get("visible", True)), DummyButton())
    host.on_acc_command_calls = []
    host.on_acc_command = lambda target, data=None: host.on_acc_command_calls.append((target, data))
    host.on_engine_command = lambda *_args, **_kwargs: None
    host.on_keypress = lambda *_args, **_kwargs: None
    host.on_new_accessory = lambda *_args, **_kwargs: None
    host.on_new_route = lambda: None
    host.on_new_switch = lambda: None
    host.reset_acc_overlay = lambda: None
    host.update_ac_status = lambda _state: None
    host.accessories = SimpleNamespace(configured_by_tmcc_id=lambda _tmcc_id: False)
    host.accessory_provider = SimpleNamespace(adapters_for_tmcc_id=lambda _tmcc_id: None)
    host.acc_overlay = None
    host.amc2_ops_box = DummyBox(visible=False)
    host.amc2_ops_panel = SimpleNamespace(update_from_state=lambda _state: None, refresh_layout=lambda: None)
    host.sensor_track_box = DummyBox(visible=False)
    host.sensor_track_buttons = DummyCheckBoxGroup(selected=None)
    host.reset_btn = DummyButton()
    host.controller_view = SimpleNamespace(make_slider=_make_slider)
    host._controller_view = host.controller_view
    return host


def disabled_test_generic_accessory_ops_mode_shows_throttle_and_reflects_state() -> None:
    host = _new_host()
    view = mod.KeypadView(host)
    state = DummyAccessoryState(relative_speed=3)
    host.active_state = state

    view.build()
    view.apply_ops_mode_ui_non_engine(state)

    assert host.acc_throttle_box.visible is True
    assert host.acc_throttle.value == 3
    assert host.acc_throttle_level.value == "+3"


def test_accessory_throttle_repeats_until_release() -> None:
    host = _new_host()
    view = mod.KeypadView(host)
    host.active_state = DummyAccessoryState(relative_speed=0)
    view.build()
    host.acc_throttle.tk.focus_set()

    host.acc_throttle.value = 4
    view.on_accessory_throttle_change("4")

    assert host.acc_throttle_level.value == "+4"
    assert host.on_acc_command_calls == [("RELATIVE_SPEED", 4)]
    assert len(host.acc_throttle.tk._after_calls) == 1
    first_after_id = next(iter(host.acc_throttle.tk._after_calls))

    host.acc_throttle.tk.run_after(first_after_id)
    assert host.on_acc_command_calls == [("RELATIVE_SPEED", 4), ("RELATIVE_SPEED", 4)]
    assert len(host.acc_throttle.tk._after_calls) == 1

    view.on_accessory_throttle_release()

    assert host.acc_throttle.value == 0
    assert host.acc_throttle_level.value == "0"
    assert host.on_acc_command_calls[-1] == ("RELATIVE_SPEED", 0)
    assert host.acc_throttle.tk._after_calls == {}


def _kind_for(**flags: bool) -> str | None:
    host = _new_host()
    state = DummyAccessoryState()
    for name, value in flags.items():
        setattr(state, name, value)
    host.active_state = state
    return mod.KeypadView(host).accessory_panel_kind


def test_accessory_panel_kind_reports_each_panel() -> None:
    assert _kind_for(is_sensor_track=True) == "sensor_track"
    assert _kind_for(is_amc2=True) == "amc2"
    assert _kind_for(is_bpc2=True) == "bpc2"
    assert _kind_for(is_asc2=True) == "asc2"
    assert _kind_for() == "generic"


def test_accessory_panel_kind_prefers_the_more_specific_panel() -> None:
    # Both flags read true for a port whose control request has not settled: the panel drawn
    # is the ASC2 one, which shows everything the BPC2 panel does, so that is what is reported.
    assert _kind_for(is_bpc2=True, is_asc2=True) == "asc2"
    assert _kind_for(is_sensor_track=True, is_asc2=True) == "sensor_track"


def test_accessory_panel_kind_is_generic_for_an_lcs_component() -> None:
    # An STM2 is an LCS component and none of the four named kinds, so it shows -- and is
    # reported as showing -- the generic panel. is_lcs_component is deliberately not consulted.
    assert _kind_for(is_lcs_component=True, is_stm2=True) == "generic"


def test_accessory_panel_kind_is_none_off_an_accessory_panel() -> None:
    host = _new_host()
    host.scope = CommandScope.ENGINE
    host.active_state = DummyAccessoryState()
    assert mod.KeypadView(host).accessory_panel_kind is None

    host = _new_host()
    host.active_state = None
    assert mod.KeypadView(host).accessory_panel_kind is None


def test_accessory_panel_kind_reports_bpc2_for_a_train_scope_power_district(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyLcsProxyState:
        def __init__(self) -> None:
            self.tmcc_id = 4
            self.is_power_district = True

    monkeypatch.setattr(mod, "LcsProxyState", DummyLcsProxyState, raising=True)
    host = _new_host()
    host.scope = CommandScope.TRAIN
    host.active_state = DummyLcsProxyState()

    assert mod.KeypadView(host).accessory_panel_kind == "bpc2"


def test_accessory_panel_kind_unwraps_a_configured_accessory_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyAdapter:
        def __init__(self, state) -> None:
            self.state = state
            self.tmcc_id = state.tmcc_id

    monkeypatch.setattr(mod, "ConfiguredAccessoryAdapter", DummyAdapter, raising=True)
    host = _new_host()
    inner = DummyAccessoryState()
    inner.is_asc2 = True
    host.active_state = DummyAdapter(inner)

    assert mod.KeypadView(host).accessory_panel_kind == "asc2"


def _asc2_host(monkeypatch: pytest.MonkeyPatch, *, is_asc2: bool = True):
    """A pane holding an ASC2, with the request class recording what it is asked to send."""
    sent: list[tuple] = []

    class DummyAsc2Req:
        def __init__(self, address, pdi_command, action, values=None) -> None:
            self.args = (address, pdi_command, action, values)

        def send(self) -> None:
            sent.append(self.args)

    monkeypatch.setattr(mod, "Asc2Req", DummyAsc2Req, raising=True)
    host = _new_host()
    state = DummyAccessoryState()
    state.address = 7
    state.is_asc2 = is_asc2
    host.state_store = SimpleNamespace(get_state=lambda _scope, _tmcc_id, _create: state)
    return host, sent


def _expected_asc2(values: int) -> tuple:
    return 7, mod.PdiCommand.ASC2_SET, mod.Asc2Action.CONTROL1, values


def test_asc2_control_sends_the_same_request_the_key_did(monkeypatch: pytest.MonkeyPatch) -> None:
    host, sent = _asc2_host(monkeypatch)
    view = mod.KeypadView(host)

    view.asc2_control(True)
    view.asc2_control(False)

    assert sent == [_expected_asc2(1), _expected_asc2(0)]


def test_the_on_screen_key_still_sends_through_the_enabled_widget(monkeypatch: pytest.MonkeyPatch) -> None:
    # The wrappers keep the widget guard: a disabled key sends nothing, an enabled one sends
    # exactly what asc2_control does.
    host, sent = _asc2_host(monkeypatch)
    view = mod.KeypadView(host)
    button = DummyButton()

    button.enabled = False
    view.when_pressed(SimpleNamespace(widget=button))
    view.when_released(SimpleNamespace(widget=button))

    assert sent == []

    button.enabled = True
    view.when_pressed(SimpleNamespace(widget=button))
    view.when_released(SimpleNamespace(widget=button))

    assert sent == [_expected_asc2(1), _expected_asc2(0)]


def test_asc2_control_sends_nothing_for_a_port_that_is_not_an_asc2(monkeypatch: pytest.MonkeyPatch) -> None:
    host, sent = _asc2_host(monkeypatch, is_asc2=False)

    mod.KeypadView(host).asc2_control(True)

    assert sent == []


def _sensor_track_host(monkeypatch: pytest.MonkeyPatch, *, value=None, is_sensor_track: bool = True):
    """A pane showing a Sensor Track, with the request class recording what it is asked to send."""
    sent: list[tuple] = []

    class DummyIrdaReq:
        def __init__(self, tmcc_id, pdi_command, action, sequence=None) -> None:
            self.args = (tmcc_id, pdi_command, action, sequence)

        def send(self, *, repeat) -> None:
            # Required rather than defaulted, and the pane's repeat is a value no default
            # would land on: a send that dropped the operator's repeat count would otherwise
            # go unnoticed here.
            sent.append(self.args + (repeat,))

    monkeypatch.setattr(mod, "IrdaReq", DummyIrdaReq, raising=True)
    monkeypatch.setattr(mod, "IrdaSequence", SimpleNamespace(by_value=lambda v: f"SEQ_{v}"), raising=True)
    host = _new_host()
    host.repeat = 3
    state = DummyAccessoryState()
    state.is_sensor_track = is_sensor_track
    host.active_state = state
    host.sensor_track_buttons = DummyCheckBoxGroup(selected=value)
    return host, sent


def _expected_irda(sequence: int, repeat: int = 3) -> tuple:
    return 19, mod.PdiCommand.IRDA_SET, mod.IrdaAction.SEQUENCE, f"SEQ_{sequence}", repeat


def test_the_sequence_send_is_widget_free_and_takes_the_pair_it_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The same extraction asc2_control made: the value and the id are arguments rather than
    # things read off the panel, which is what lets the pad send a pair captured earlier.
    host, sent = _sensor_track_host(monkeypatch, value=4)
    view = mod.KeypadView(host)

    view.send_sensor_track_sequence(31, 7)

    assert sent == [(31, mod.PdiCommand.IRDA_SET, mod.IrdaAction.SEQUENCE, "SEQ_7", 3)]
    assert host.sensor_track_buttons.value == "4", "and the panel was neither read nor written"


def test_the_change_handler_still_sends_what_the_group_shows(monkeypatch: pytest.MonkeyPatch) -> None:
    # The on-screen path is unchanged: the handler reads the widget and hands it to the send.
    host, sent = _sensor_track_host(monkeypatch, value=6)

    mod.KeypadView(host).on_sensor_track_change()

    assert sent == [_expected_irda(6)]


@pytest.mark.parametrize(
    ("start", "delta", "expected"),
    [
        (0, 1, 1),
        (5, 1, 6),
        (5, -1, 4),
        (8, 1, 9),
        (9, -1, 8),
    ],
)
def test_stepping_moves_one_option_and_reports_where_it_landed(
    monkeypatch: pytest.MonkeyPatch, start, delta, expected
) -> None:
    host, sent = _sensor_track_host(monkeypatch, value=start)

    moved = mod.KeypadView(host).step_sensor_track_sequence(delta)

    assert moved == expected
    assert host.sensor_track_buttons.value == str(expected), "the group holds it as the string Tk keeps"
    assert sent == [], "the highlight moves and nothing is written"


@pytest.mark.parametrize(("start", "delta"), [(0, -1), (9, 1)])
def test_stepping_off_either_end_moves_nothing(monkeypatch: pytest.MonkeyPatch, start, delta) -> None:
    # Clamped rather than wrapping: an operator holding the pad against an end must not find
    # the selection rolled round to the far one.
    host, sent = _sensor_track_host(monkeypatch, value=start)

    moved = mod.KeypadView(host).step_sensor_track_sequence(delta)

    assert moved is None
    assert host.sensor_track_buttons.value == str(start)
    assert sent == []


@pytest.mark.parametrize("delta", [-1, 1])
def test_an_unset_selection_is_treated_as_the_first_option(monkeypatch: pytest.MonkeyPatch, delta) -> None:
    # No IrdaState for this Sensor Track yet, so the group shows nothing. The first press
    # either way lands on "No Action" and the second moves off it.
    host, sent = _sensor_track_host(monkeypatch, value=None)
    view = mod.KeypadView(host)

    assert host.sensor_track_buttons.value == "None", "which is all an unset group can say"

    assert view.step_sensor_track_sequence(delta) == 0
    assert host.sensor_track_buttons.value == "0"

    assert view.step_sensor_track_sequence(1) == 1
    assert sent == []


@pytest.mark.parametrize("value", ["", "None", "Sound Horn", "12"])
def test_a_selection_the_list_does_not_hold_is_read_as_unset(monkeypatch: pytest.MonkeyPatch, value) -> None:
    # Whatever the group is holding arrives as a string, and not every string is an option in
    # it: "None" is what clearing the group leaves behind, and a value outside the list could
    # only come from somewhere that does not know the list. Each is a state before the list
    # rather than a position in it, so the press lands on "No Action" instead of raising.
    host, sent = _sensor_track_host(monkeypatch)
    host.sensor_track_buttons.value = value

    assert mod.KeypadView(host).step_sensor_track_sequence(-1) == 0
    assert host.sensor_track_buttons.value == "0"
    assert sent == []


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (7, 7), (9, 9), (None, None), ("", None), ("12", None)])
def test_the_highlighted_option_is_read_back_through_one_normalising(
    monkeypatch: pytest.MonkeyPatch, value, expected
) -> None:
    # The reader the select works from. Every caller wanting "the option showing" comes here,
    # so the Tk string -- and the "None" an unset group answers with -- is understood once
    # rather than in each of them.
    host, sent = _sensor_track_host(monkeypatch)
    host.sensor_track_buttons.value = value

    assert mod.KeypadView(host).sensor_track_sequence == expected
    assert sent == []


def test_the_highlight_can_be_moved_to_a_named_option_without_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    # What a revert puts its option back with, and what the stepping is built on: an
    # assignment rather than a click, so the group's command does not fire.
    host, sent = _sensor_track_host(monkeypatch, value=3)
    view = mod.KeypadView(host)

    assert view.set_sensor_track_sequence(8) is True
    assert host.sensor_track_buttons.value == "8"
    assert view.sensor_track_sequence == 8
    assert sent == []


@pytest.mark.parametrize("value", [-1, 10, None, "Sound Horn"])
def test_the_highlight_is_not_moved_to_an_option_the_list_does_not_hold(monkeypatch: pytest.MonkeyPatch, value) -> None:
    # A value from outside the group is a caller that has lost track of the list, and moving
    # the highlight to it would leave the panel showing a selection with no option under it.
    host, sent = _sensor_track_host(monkeypatch, value=3)

    assert mod.KeypadView(host).set_sensor_track_sequence(value) is False
    assert host.sensor_track_buttons.value == "3"
    assert sent == []


def test_the_highlight_is_not_moved_where_the_panel_is_not_a_sensor_track(monkeypatch: pytest.MonkeyPatch) -> None:
    # Re-checked as the stepping is, and for the same reason: the press and the panel it was
    # aimed at are two moments, and a highlight moved on a panel no longer showing the group
    # would be a change nobody could see.
    host, sent = _sensor_track_host(monkeypatch, value=3, is_sensor_track=False)
    view = mod.KeypadView(host)

    assert view.set_sensor_track_sequence(8) is False
    assert view.sensor_track_sequence is None
    assert host.sensor_track_buttons.value == "3"


def test_stepping_is_refused_where_the_panel_is_not_a_sensor_track(monkeypatch: pytest.MonkeyPatch) -> None:
    # Re-checked rather than assumed: the pane may have been re-scoped between the press
    # being routed and the step being asked for.
    host, sent = _sensor_track_host(monkeypatch, value=3, is_sensor_track=False)

    assert mod.KeypadView(host).step_sensor_track_sequence(1) is None
    assert host.sensor_track_buttons.value == "3"
    assert sent == []


def test_external_accessory_throttle_update_repaints_slider() -> None:
    host = _new_host()
    view = mod.KeypadView(host)
    state = DummyAccessoryState(relative_speed=-2)
    host.active_state = state
    view.build()

    view.update_accessory_throttle_from_state(state)

    assert host.acc_throttle.value == -2
    assert host.acc_throttle_level.value == "-2"
