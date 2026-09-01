from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import src.pytrain.gui.controller.lcs_config_panel as mod
from src.pytrain.gui.controller.lcs_device_registry import ASC2, BPC2, SENSOR_TRACK, STM2
from src.pytrain.pdi.irda_req import IrdaSequence
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
)


class _DummyTk:
    @staticmethod
    def config(**_kwargs: Any) -> None:
        return

    @staticmethod
    def configure(**_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_configure(**_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_columnconfigure(_col: int, **_kwargs: Any) -> None:
        return

    @staticmethod
    def bind(_event: str, _func, add: str | None = None) -> None:
        _ = add
        return


class _DummyWidget:
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        self.tk = _DummyTk()
        self.visible = True
        self.enabled = True
        self.text = kwargs.get("text", "")
        self.value = kwargs.get("text", "")
        self.text_size = kwargs.get("text_size", 12)
        self.text_bold = False
        self.grid = kwargs.get("grid")

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False


class DummyBox(_DummyWidget):
    pass


class DummyText(_DummyWidget):
    pass


class DummyHoldButton(_DummyWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.command = kwargs.get("command")


class DummyEditableText(_DummyWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.on_commit = kwargs.get("on_commit")
        self.compact = kwargs.get("compact", False)
        self.max_length = kwargs.get("max_length")
        self.editor = kwargs.get("editor")
        self.value = ""


class DummyCheckBox(_DummyWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.command = kwargs.get("command")
        self.value = 0


class DummyCheckBoxGroup(_DummyWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.options = kwargs.get("options", [])
        self.value = kwargs.get("selected")
        self.command = kwargs.get("command")

    def clear(self) -> None:
        self.options = []

    def append(self, option: list[Any]) -> None:
        """Append a [text, value] list, matching guizero's ButtonGroup.append() signature."""
        if not isinstance(option, list) or len(option) != 2:
            raise TypeError(f"append() expects a [text, value] list, got {option!r}")
        self.options.append(tuple(option))


class FakeState:
    """Mirrors the parts of LcsProxyState the panel and the ID map read."""

    def __init__(
        self,
        address: int,
        device_flag: str,
        mode: Any = "NA",
        num_ids: int | None = None,
        parent: Any = None,
        sequence: Any = None,
    ) -> None:
        self.address = address
        self.tmcc_id = address
        self.mode = mode
        self.num_ids = num_ids
        self.sequence = sequence
        self._parent = parent
        for flag in ("is_asc2", "is_bpc2", "is_stm2", "is_sensor_track"):
            setattr(self, flag, flag == device_flag)

    @property
    def parent(self) -> Any:
        return self._parent

    @property
    def port(self) -> int:
        return self.address - self._parent.address + 1 if self._parent else 1


class FakeStore:
    def __init__(self, states: dict[CommandScope, list[FakeState]] | None = None) -> None:
        self._states = states or {}

    def get_all(self, scope: CommandScope) -> list[FakeState]:
        return list(self._states.get(scope, []))

    def get_state(self, scope: CommandScope, address: int, create: bool = True) -> Any:
        _ = create
        for state in self._states.get(scope, []):
            if state.address == address:
                return state
        return None


class FakeApp:
    """Records what the panel schedules rather than running a Tk event loop."""

    def __init__(self) -> None:
        self.scheduled: list[tuple[int, Any]] = []

    def after(self, msec: int, action: Any) -> None:
        self.scheduled.append((msec, action))

    def fire(self) -> None:
        for _msec, action in list(self.scheduled):
            action()


class FakeHost(SimpleNamespace):
    def __init__(self, store: FakeStore) -> None:
        super().__init__(
            s_10=10,
            s_12=12,
            s_14=14,
            s_16=16,
            s_18=18,
            s_20=20,
            button_size=100,
            width=480,
            compact=False,
            state_store=store,
            cache=lambda _widget: None,
            app=FakeApp(),
            sent=[],
        )

    def submit_request(self, request: Any, repeat: int = 1, delay: float = 0.0) -> None:
        self.sent.append((request, repeat, delay))

    def queue_message(self, message: Any, *args: Any) -> None:
        message(*args)


def _new_host(store: FakeStore | None = None) -> Any:
    return FakeHost(store or FakeStore())


@pytest.fixture(autouse=True)
def _patch_widgets(monkeypatch):
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    monkeypatch.setattr(mod, "Text", DummyText, raising=True)
    monkeypatch.setattr(mod, "HoldButton", DummyHoldButton, raising=True)
    monkeypatch.setattr(mod, "EditableText", DummyEditableText, raising=True)
    monkeypatch.setattr(mod, "CheckBoxGroup", DummyCheckBoxGroup, raising=True)
    monkeypatch.setattr(mod, "CheckBox", DummyCheckBox, raising=True)
    monkeypatch.setattr(mod, "StateWatcher", lambda _state, _action: None, raising=True)
    monkeypatch.setattr(mod, "style_footer_button", lambda _host, _btn: None, raising=True)
    monkeypatch.setattr(mod, "footer_spacer", lambda _host, _footer: None, raising=True)


def _new_panel(store: FakeStore | None = None):
    panel = mod.LcsConfigPanel(_new_host(store))
    panel.build(DummyBox())
    panel.build_footer(DummyBox())
    return panel


#
# Pages
#
def test_build_shows_device_page_first() -> None:
    panel = _new_panel()

    assert panel.page_index == mod.PAGE_DEVICE
    assert panel._pages[mod.PAGE_DEVICE].visible is True
    assert panel._pages[mod.PAGE_ID].visible is False


def test_next_page_requires_a_device_then_shows_id_page() -> None:
    panel = _new_panel()

    assert panel._next_btn.enabled is False
    panel._on_device_selected("asc2")
    panel.refresh_footer()
    assert panel._next_btn.enabled is True

    panel.next_page()
    assert panel.page_index == mod.PAGE_ID
    assert panel._pages[mod.PAGE_ID].visible is True
    assert panel._back_btn.enabled is True


def test_device_options_cover_every_registry_device() -> None:
    keys = [value for _label, value in mod.LcsConfigPanel.device_options()]
    assert keys == [ASC2.key, BPC2.key, STM2.key, SENSOR_TRACK.key]


#
# Base ID clamping and step keys
#
def test_set_base_id_clamps_at_one() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")

    assert panel._set_base_id(0) == 1
    assert panel._set_base_id(-5) == 1
    panel.step_down()
    assert panel.base_id == 1


def test_set_base_id_clamps_at_mode_max() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")  # defaults to ACC eight-ID: 8 ports, max base 91

    assert panel.max_base == 91
    assert panel._set_base_id(95) == 91
    panel.step_up()
    assert panel.base_id == 91


def test_step_keys_disable_exactly_at_the_limits() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")

    panel._set_base_id(1)
    assert panel._minus_btn.enabled is False
    assert panel._plus_btn.enabled is True

    panel._set_base_id(91)
    assert panel._minus_btn.enabled is True
    assert panel._plus_btn.enabled is False

    panel._set_base_id(50)
    assert panel._minus_btn.enabled is True
    assert panel._plus_btn.enabled is True


def test_keypad_commit_of_bad_text_leaves_the_id_alone() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    for text in ("", "  ", "abc", None):
        panel._on_id_committed(panel._id_field, text)
        assert panel.base_id == 12
    assert panel._id_field.value == "12"

    panel._on_id_committed(panel._id_field, "0")
    assert panel.base_id == 1
    panel._on_id_committed(panel._id_field, "99")
    assert panel.base_id == 91


def test_block_line_tracks_the_mode() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    assert panel.block_text == "Claims IDs 12-19 (8 ports)"
    assert panel._block_line.value == "Claims IDs 12-19 (8 ports)"

    panel._on_mode_selected("acc_1")
    assert panel.block_text == "Claims ID 12 (1 port)"
    assert panel.max_base == 98


def test_widening_the_mode_lowers_an_out_of_range_id() -> None:
    panel = _new_panel()
    panel._on_device_selected("stm2")
    panel._on_mode_selected("two_wire")  # 8 ports, max base 91
    panel._set_base_id(91)

    panel._on_mode_selected("single_wire")  # 16 ports, max base 83
    assert panel.max_base == 83
    assert panel.base_id == 83


#
# Seeding
#
def test_configure_with_nothing_selected_defaults_to_id_one_and_no_device() -> None:
    panel = _new_panel()
    panel.configure(None, None, None)

    assert panel.base_id == 1
    assert panel.device is None
    assert panel._device_group.value is None
    assert panel.page_index == mod.PAGE_DEVICE


def test_configure_seeds_device_and_mode_from_a_known_bpc2_state() -> None:
    state = FakeState(12, "is_bpc2", mode=0, num_ids=8)
    store = FakeStore({CommandScope.TRAIN: [state]})
    panel = _new_panel(store)

    panel.configure(CommandScope.TRAIN, 12, state)

    assert panel.device is BPC2
    assert panel.mode.key == "tr_8"
    assert panel.base_id == 12
    assert panel._device_group.value == "bpc2"
    assert panel.options == {"restore": False}
    assert panel._occupancy_line.value == "BPC2 at 12 - TR, 8 IDs"


def test_configure_seeds_from_the_store_when_the_id_is_a_known_base() -> None:
    state = FakeState(9, "is_asc2", mode=0, num_ids=8)
    store = FakeStore({CommandScope.ACC: [state]})
    panel = _new_panel(store)

    panel.configure(CommandScope.ACC, 9, None)

    assert panel.device is ASC2
    assert panel.mode.key == "acc_8"
    assert panel.base_id == 9


#
# Occupancy
#
def _asc2_at_9_store() -> FakeStore:
    return FakeStore({CommandScope.ACC: [FakeState(9, "is_asc2", mode=0, num_ids=8)]})


def test_unowned_id_reports_not_in_use() -> None:
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(40)

    assert panel._occupancy_line.value == mod.NOT_IN_USE
    assert panel._goto_btn.visible is False
    assert panel._new_btn.visible is False


def test_interior_port_reports_its_owner_and_offers_both_choices() -> None:
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    assert panel._occupancy_line.value == "ID 12 is port 4 of the ASC2 based at 9"
    assert panel._goto_btn.visible is True
    assert panel._goto_btn.text == "Go to 9"
    assert panel._new_btn.visible is True
    assert panel._new_btn.text == "Configure 12 as new"


def test_go_to_base_retargets_and_pre_fills() -> None:
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)

    panel.go_to_owning_base()

    assert panel.base_id == 9
    assert panel.device is ASC2
    assert panel.mode.key == "acc_8"
    assert panel._device_group.value == "asc2"
    assert panel._occupancy_line.value == "ASC2 at 9 - ACC, 8 IDs"


def test_configure_as_new_keeps_the_entered_id() -> None:
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    panel.configure_as_new()

    assert panel.base_id == 12
    assert panel.is_configure_as_new is True
    assert panel._goto_btn.visible is False
    assert panel._new_btn.visible is False

    # Moving off the ID retires the override, so the banner speaks again.
    panel._set_base_id(13)
    assert panel.is_configure_as_new is False
    assert panel._goto_btn.visible is True


def test_overlap_line_is_advisory() -> None:
    store = FakeStore({CommandScope.SWITCH: [FakeState(28, "is_stm2", mode=1, num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("stm2")
    panel._on_mode_selected("single_wire")  # 16 ports
    panel._set_base_id(20)

    assert panel.overlap_text() == "Overlaps STM2 at 28-35"
    assert panel._overlap_line.value == "Overlaps STM2 at 28-35"
    # Advisory only: the ID the operator typed is untouched.
    assert panel.base_id == 20


def test_sensor_track_claims_a_single_id() -> None:
    panel = _new_panel()
    panel._on_device_selected("sensor_track")

    panel._set_base_id(3)
    assert panel.device is SENSOR_TRACK
    assert panel.ports == 1
    assert panel.max_base == 98
    assert panel.block_text == "Claims ID 3 (1 port)"


#
# Options page
#
def test_options_page_renders_only_the_selected_device_controls() -> None:
    panel = _new_panel()

    panel._on_device_selected("bpc2")
    assert panel._option_boxes["bpc2"].visible is True
    assert panel._option_boxes["sensor_track"].visible is False
    # A flag is a checkbox, not a radio.
    restore = panel._option_widgets[("bpc2", "restore")]
    assert isinstance(restore, DummyCheckBox)
    assert restore.value == 0

    panel._on_device_selected("sensor_track")
    assert panel._option_boxes["bpc2"].visible is False
    assert panel._option_boxes["sensor_track"].visible is True
    action = panel._option_widgets[("sensor_track", "action")]
    assert isinstance(action, DummyCheckBoxGroup)
    assert len(action.options) == 10


def test_devices_without_options_say_so() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")

    assert ASC2.options == ()
    assert panel._option_boxes["asc2"].visible is True
    assert panel._option_widgets.get(("asc2", "restore")) is None


def test_bpc2_relay_warning_and_reserved_modes_are_shown_with_their_reason() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert "relay" in panel._warning_line.value
    assert panel._warning_line.value == BPC2.warning
    assert panel.reserved_text == (
        "Not available: Track, 1 TMCC ID (reserved, no Cab support), Accessory, 1 TMCC ID (reserved, no Cab support)"
    )
    assert panel._reserved_line.value == panel.reserved_text

    panel._on_device_selected("stm2")
    assert panel._warning_line.value == ""
    assert panel._reserved_line.value == ""


def test_toggling_the_bpc2_restore_flag_updates_the_presses() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)
    assert panel.options["restore"] is False
    assert len(panel.review_lines) == 2

    panel._option_widgets[("bpc2", "restore")].value = 1
    panel._on_option_changed("bpc2", "restore")

    assert panel.options["restore"] is True
    assert panel.review_lines == [
        "1. TR 12 SET",
        "2. Coupler R (restore on)",
        "3. AUX1 then 0 (8-ID sub-mode)",
    ]


def test_sensor_track_action_is_required_and_defaults_to_no_action() -> None:
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    assert SENSOR_TRACK.option("action").required is True
    assert panel.options["action"] == IrdaSequence.NONE
    assert panel._option_widgets[("sensor_track", "action")].value == "0"
    # There is no "leave unchanged" row: assigning an action is what ends program mode.
    labels = [label for label, _value in SENSOR_TRACK.option("action").choices]
    assert len(labels) == 10 and labels[0] == "No Action"
    assert mod.SENSOR_TRACK_FILTER_NOTE == SENSOR_TRACK.option("action").note


def test_sensor_track_action_is_seeded_from_the_irda_state() -> None:
    irda = FakeState(3, "is_sensor_track", sequence=IrdaSequence.CROSSING_GATE_NONE)
    store = FakeStore({CommandScope.IRDA: [irda]})
    panel = _new_panel(store)

    panel.configure(CommandScope.ACC, 3, None)
    panel._on_device_selected("sensor_track")

    assert panel.device is SENSOR_TRACK
    assert panel.options["action"] == IrdaSequence.CROSSING_GATE_NONE
    assert panel._option_widgets[("sensor_track", "action")].value == "1"


def test_choosing_an_action_command_changes_the_press_digit() -> None:
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    panel._option_widgets[("sensor_track", "action")].value = "9"
    panel._on_option_changed("sensor_track", "action")

    assert panel.options["action"] == IrdaSequence.RECORDING
    assert panel.review_lines == ["1. ACC 3 SET", "2. AUX1 then 9 (action command)"]


#
# Review page
#
def test_review_page_is_numbered_in_send_order_with_the_pgm_instruction() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(9)

    assert panel.review_lines == ["1. ACC 9 SET", "2. AUX1 then 0 (8-ID sub-mode)"]
    assert panel._review_line.value == "1. ACC 9 SET\n2. AUX1 then 0 (8-ID sub-mode)"
    assert "PGM button" in panel._program_line.value
    assert panel.footnote == "Be sure your ASC2 is in Program mode."
    assert panel._footnote_line.value == panel.footnote


def test_sensor_track_review_notes_the_abort_and_the_mandatory_action() -> None:
    panel = _new_panel()
    panel._on_device_selected("sensor_track")

    assert mod.SENSOR_TRACK_REVIEW_NOTE in panel._review_note_line.value
    assert "PROGRAM button" in panel._program_line.value
    assert panel.footnote == "Be sure your Sensor Track is in Program mode."


def test_bpc2_review_repeats_the_relay_warning() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert BPC2.warning in panel._review_note_line.value


#
# Configure and read-back
#
def test_configure_queues_the_presses_in_order_then_the_verify_gets() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)

    panel.on_configure()

    sent = panel.gui.sent
    assert len(sent) == 4  # two presses, then CONFIG and INFO
    commands = [request.command for request, _repeat, _delay in sent[:2]]
    assert commands == [TMCC1EngineCommandEnum.SET_ADDRESS, TMCC1EngineCommandEnum.AUX_NUMBER_0]
    delays = [delay for _request, _repeat, delay in sent]
    assert delays == sorted(delays)
    assert delays[0] == 0.0
    assert delays[2] > delays[1]
    assert panel._requested_line.value.startswith("Requested: BPC2 - Track, 8 TMCC ID at TR 12")
    assert panel._reported_line.value == mod.AWAITING_READBACK


def test_configure_of_a_sensor_track_always_sends_both_halves() -> None:
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    panel.on_configure()

    commands = [request.command for request, _repeat, _delay in panel.gui.sent[:2]]
    assert commands == [TMCC1AuxCommandEnum.SET_ADDRESS, TMCC1AuxCommandEnum.AUX_NUMBER_0]


def test_read_back_reports_what_the_module_says() -> None:
    state = FakeState(9, "is_asc2", mode=0, num_ids=8)
    store = FakeStore({CommandScope.ACC: [state]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")
    panel._set_base_id(9)

    panel.on_configure()
    panel.on_readback()

    assert panel._reported_line.value == "Reported: ASC2 at 9, ACC, 8 IDs"
    # The presses that were sent stay on screen.
    assert panel._review_line.value.startswith("1. ACC 9 SET")


def test_read_back_timeout_reports_no_response_and_leaves_the_presses() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(40)

    panel.on_configure()
    assert panel.gui.app.scheduled and panel.gui.app.scheduled[0][0] == mod.READBACK_TIMEOUT_MSEC
    panel.gui.app.fire()

    assert panel._reported_line.value == mod.NO_RESPONSE
    assert panel._review_line.value.startswith("1. ACC 40 SET")


def test_reopening_the_panel_clears_the_previous_read_back() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(40)
    panel.on_configure()
    panel.gui.app.fire()
    assert panel._reported_line.value == mod.NO_RESPONSE

    panel.configure(None, None, None)

    assert panel._reported_line.value == ""
    assert panel._requested_line.value == ""
    assert panel.page_index == mod.PAGE_DEVICE


def test_mode_selector_repopulates_correctly_on_device_change() -> None:
    """
    Verify that the mode selector is correctly repopulated when the device changes.
    This test exercises the widget-facing refresh path and would fail if append()
    is called with two positional arguments instead of a single list argument.
    """
    panel = _new_panel()

    # Select ASC2, which has 4 enabled modes
    panel._on_device_selected("asc2")
    assert len(panel._mode_group.options) == 4
    assert panel._mode_group.options[0] == ("Accessory, Eight ID", "acc_8")
    assert panel._mode_group.options[1] == ("Accessory, Single ID", "acc_1")
    assert panel._mode_group.options[2] == ("Switch, momentary", "sw_momentary")
    assert panel._mode_group.options[3] == ("Switch, latching", "sw_latching")

    # Switch to Sensor Track, which has 1 mode
    panel._on_device_selected("sensor_track")
    assert len(panel._mode_group.options) == 1
    assert panel._mode_group.options[0] == ("Accessory ID and Action Command", "acc")

    # Switch to BPC2, which has 2 enabled modes (the 1-ID modes are disabled)
    panel._on_device_selected("bpc2")
    assert len(panel._mode_group.options) == 2
    assert panel._mode_group.options[0] == ("Track, 8 TMCC ID", "tr_8")
    assert panel._mode_group.options[1] == ("Accessory, 8 TMCC ID", "acc_8")


#
# Waiting for the Base 3
#
def test_panel_is_not_sync_pending_by_default() -> None:
    panel = _new_panel()

    assert panel.sync_pending is False
    assert panel._sync_line.visible is False
    assert panel._sync_line.value == ""


def test_sync_pending_shows_the_banner_and_disables_configure() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(40)
    assert panel.program is not None
    assert panel._configure_btn.enabled is True

    panel.set_sync_pending(True)

    assert panel.sync_pending is True
    assert panel._sync_line.visible is True
    assert panel._sync_line.value == mod.WAITING_FOR_BASE
    assert panel._configure_btn.enabled is False
    # The preview and the footnote still render, so the operator can read the sequence.
    assert panel._review_line.value != ""
    assert panel._footnote_line.value != ""

    panel.set_sync_pending(False)

    assert panel._sync_line.visible is False
    assert panel._configure_btn.enabled is True


def test_every_other_control_stays_usable_while_sync_is_pending() -> None:
    panel = _new_panel()
    panel.set_sync_pending(True)

    panel._on_device_selected("bpc2")
    assert panel.device is BPC2
    panel._set_base_id(12)
    assert panel.base_id == 12
    panel.refresh_footer()
    assert panel._next_btn.enabled is True

    panel.next_page()
    assert panel.page_index == mod.PAGE_ID
    panel.previous_page()
    assert panel.page_index == mod.PAGE_DEVICE
    assert panel._sync_line.visible is True


def test_occupancy_is_not_in_use_until_the_store_is_populated() -> None:
    states: dict[CommandScope, list[FakeState]] = {CommandScope.TRAIN: []}
    panel = _new_panel(FakeStore(states))
    panel.set_sync_pending(True)
    panel._set_base_id(12)

    assert panel._occupancy_line.value == mod.NOT_IN_USE

    states[CommandScope.TRAIN].append(FakeState(12, "is_bpc2", mode=0, num_ids=8))
    panel.on_synchronized()

    assert panel._occupancy_line.value == "BPC2 at 12 - TR, 8 IDs"


def test_on_synchronized_re_seeds_when_no_device_was_chosen() -> None:
    states: dict[CommandScope, list[FakeState]] = {CommandScope.TRAIN: []}
    panel = _new_panel(FakeStore(states))
    panel.set_sync_pending(True)
    panel._set_base_id(12)
    assert panel.device is None

    states[CommandScope.TRAIN].append(FakeState(12, "is_bpc2", mode=0, num_ids=8))
    panel.on_synchronized()

    assert panel.device is BPC2
    assert panel.mode.key == "tr_8"
    assert panel._device_group.value == "bpc2"
    assert panel.sync_pending is False
    assert panel._sync_line.visible is False


def test_on_synchronized_keeps_the_operators_choices() -> None:
    states: dict[CommandScope, list[FakeState]] = {CommandScope.TRAIN: []}
    panel = _new_panel(FakeStore(states))
    panel.set_sync_pending(True)
    panel._on_device_selected("stm2")
    panel._set_base_id(12)
    panel._options["restore"] = True

    states[CommandScope.TRAIN].append(FakeState(12, "is_bpc2", mode=0, num_ids=8))
    panel.on_synchronized()

    assert panel.device is STM2
    assert panel.base_id == 12
    assert panel.options["restore"] is True
    assert panel._configure_btn.enabled is True
    assert panel._occupancy_line.value == "BPC2 at 12 - TR, 8 IDs"


def test_on_synchronized_is_idempotent() -> None:
    state = FakeState(12, "is_bpc2", mode=0, num_ids=8)
    panel = _new_panel(FakeStore({CommandScope.TRAIN: [state]}))
    panel.set_sync_pending(True)
    panel._set_base_id(12)

    panel.on_synchronized()
    device, mode, base_id = panel.device, panel.mode, panel.base_id
    panel.on_synchronized()

    assert (panel.device, panel.mode, panel.base_id) == (device, mode, base_id)
    assert panel.sync_pending is False
