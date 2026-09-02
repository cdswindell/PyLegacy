from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import src.pytrain.gui.controller.lcs_config_panel as mod
from src.pytrain.gui.controller.lcs_device_registry import AMC2, ASC2, BPC2, SENSOR_TRACK, STM2, LcsOption
from src.pytrain.pdi.irda_req import IrdaSequence
from src.pytrain.pdi.pdi_device import PdiDevice
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
)


class _DummyTk:
    def __init__(self) -> None:
        # What the widget was asked to bind, which is how the click-to-edit test reads the
        # desktop wiring without a real Tk event loop.
        self.binds: list[tuple[str, Any]] = []
        # And what it was configured with, which is how the wrapping tests read a Tk option
        # that has no guizero equivalent.
        self.configured: dict[str, Any] = {}

    def config(self, **kwargs: Any) -> None:
        self.configured.update(kwargs)

    def configure(self, **kwargs: Any) -> None:
        self.configured.update(kwargs)

    @staticmethod
    def grid_configure(**_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_columnconfigure(_col: int, **_kwargs: Any) -> None:
        return

    def bind(self, event: str, func, add: str | None = None) -> None:
        _ = add
        self.binds.append((event, func))

    @staticmethod
    def update_idletasks() -> None:
        return

    @staticmethod
    def winfo_reqwidth() -> int:
        return 160

    @staticmethod
    def pack_propagate(_flag: bool) -> None:
        return


class _DummyWidget:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.tk = _DummyTk()
        self.kwargs = dict(kwargs)
        # Children are recorded in creation order, which is what the whitespace tests read.
        self.children: list[Any] = []
        parent = args[0] if args else None
        if isinstance(getattr(parent, "children", None), list):
            parent.children.append(self)
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


class DummyTitleBox(_DummyWidget):
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
        self.show_keyboard_on_edit = kwargs.get("show_keyboard_on_edit", True)
        self.field_name = kwargs.get("field_name", "")
        self.edit_bg = "white"
        self.edit_fg = "black"
        self.edits = 0
        self.value = ""

    def begin_edit(self) -> None:
        self.edits += 1


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

    @staticmethod
    def decorate_checkbox(widget: Any, size: int, width: Any = None, **kwargs: Any) -> None:
        """Record what the real component would paint a lone checkbox with.

        The classmethod the Admin panel and the catalog's sort boxes already reach for; it
        draws the indicator, so what it is asked for is the whole of the assertion.
        """
        widget.decoration = dict(size=size, width=width, **kwargs)

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
        # is_amc2 among them: the panel can only name an AMC2, but a state that does not
        # carry the flag at all cannot even be recognized, which was the original bug.
        for flag in ("is_asc2", "is_bpc2", "is_stm2", "is_sensor_track", "is_amc2"):
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
            # What the popup is built to the width of, so it is what a line of prose is
            # wrapped at. A few pixels inside the pane, as the measured box is on a Pi.
            emergency_box_width=470,
            compact=False,
            state_store=store,
            cache=lambda _widget: None,
            app=FakeApp(),
            sent=[],
            vspaces=[],
        )

    def add_vspace(self, parent: Any, pixels: int) -> None:
        """Record the spacer and stand one in among the parent's children, as guizero would."""
        self.vspaces.append((parent, pixels))
        if isinstance(getattr(parent, "children", None), list):
            parent.children.append(SimpleNamespace(vspace=pixels))

    def submit_request(self, request: Any, repeat: int = 1, delay: float = 0.0) -> None:
        self.sent.append((request, repeat, delay))

    def queue_message(self, message: Any, *args: Any) -> None:
        message(*args)


def _new_host(store: FakeStore | None = None) -> Any:
    return FakeHost(store or FakeStore())


@pytest.fixture(autouse=True)
def _patch_widgets(monkeypatch):
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    monkeypatch.setattr(mod, "TitleBox", DummyTitleBox, raising=True)
    monkeypatch.setattr(mod, "Text", DummyText, raising=True)
    monkeypatch.setattr(mod, "HoldButton", DummyHoldButton, raising=True)
    monkeypatch.setattr(mod, "EditableText", DummyEditableText, raising=True)
    monkeypatch.setattr(mod, "CheckBoxGroup", DummyCheckBoxGroup, raising=True)
    monkeypatch.setattr(mod, "CheckBox", DummyCheckBox, raising=True)
    monkeypatch.setattr(mod, "StateWatcher", lambda _state, _action: None, raising=True)
    monkeypatch.setattr(mod, "style_footer_button", lambda _host, _btn: None, raising=True)
    # Pinned so the ID field's editor does not depend on the machine running the tests;
    # the platform-specific cases patch it themselves. Patched on the panel module, which
    # is only possible because is_linux is imported there at module scope rather than
    # reached for inside touch_only_editing.
    monkeypatch.setattr(mod, "is_linux", lambda: False, raising=True)


def _new_panel(store: FakeStore | None = None):
    panel = mod.LcsConfigPanel(_new_host(store))
    # Back and Next come with build(): the panel owns them, and the popup adds only Close.
    panel.build(DummyBox())
    return panel


def _appliance(monkeypatch) -> None:
    """Run as the Pi or the Steam Deck, where the panel opens on the module at the ID.

    The suite pins the platform to a desktop, on which the panel deliberately reflects
    nothing and opens on the first module by name. A test about seeding from the layout has
    to say which host it means.
    """
    monkeypatch.setattr(mod, "is_linux", lambda: True, raising=True)


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
    panel._refresh_nav()
    assert panel._next_btn.enabled is True

    panel.next_page()
    assert panel.page_index == mod.PAGE_ID
    assert panel._pages[mod.PAGE_ID].visible is True
    assert panel._back_btn.enabled is True


def test_device_options_cover_every_registry_device() -> None:
    keys = [value for _label, value in mod.LcsConfigPanel.device_options()]
    # In name order, which is the order the registry offers them in.
    assert keys == [ASC2.key, BPC2.key, SENSOR_TRACK.key, STM2.key]


def test_device_options_are_sorted_by_name() -> None:
    labels = [label for label, _value in mod.LcsConfigPanel.device_options()]
    assert labels == sorted(labels, key=str.upper)


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


def test_the_mode_rows_name_the_block_each_of_them_would_claim() -> None:
    # Every row says which TMCC IDs choosing it would set aside, so the operator reads the
    # addresses rather than adding a count to the ID above. This is what the page used to
    # say in one line below the boxes, for the selected mode only.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    assert [label for label, _key in panel._mode_group.options] == [
        "ACCessory TMCC IDs 12 - 19",
        "ACCessory TMCC ID 12",
        "SWitch pulse TMCC IDs 12 - 15",
        "SWitch latching TMCC IDs 12 - 15",
    ]


def test_stepping_the_id_relabels_every_mode_row() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._on_mode_selected("acc_1")
    panel._set_base_id(12)

    panel.step_up()

    assert [label for label, _key in panel._mode_group.options] == [
        "ACCessory TMCC IDs 13 - 20",
        "ACCessory TMCC ID 13",
        "SWitch pulse TMCC IDs 13 - 16",
        "SWitch latching TMCC IDs 13 - 16",
    ]
    # The rows are rebuilt to relabel them, and the selection is held by key rather than
    # by the text that just changed.
    assert panel._mode_group.value == "acc_1"
    assert panel.mode.key == "acc_1"


def test_a_mode_row_is_offered_at_the_highest_base_it_fits() -> None:
    # ID 95 is as high as the four-port switch modes go, and higher than the eight-ID
    # accessory mode can be based. Its row names the block it would claim from 91, which
    # is where selecting it lands the ID.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._on_mode_selected("sw_momentary")
    panel._set_base_id(95)

    assert panel._mode_group.options[0] == ("ACCessory TMCC IDs 91 - 98", "acc_8")

    panel._on_mode_selected("acc_8")
    assert panel.base_id == 91
    assert panel._mode_group.options[0] == ("ACCessory TMCC IDs 91 - 98", "acc_8")


def test_the_page_says_the_selected_block_once() -> None:
    # The line that used to stand below the boxes -- "Uses TMCC IDs 12 - 19" -- repeated
    # the row the operator had just chosen, and is gone with the mode rows naming their own.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    lines = [
        child.value for child in panel._pages[mod.PAGE_ID].children if isinstance(getattr(child, "value", None), str)
    ]
    assert not [line for line in lines if "TMCC ID" in line and line != panel.id_heading_text]


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
def test_configure_with_nothing_selected_defaults_to_id_one_and_the_first_device() -> None:
    panel = _new_panel()
    panel.configure(None, None, None)

    assert panel.base_id == 1
    assert panel.device is ASC2
    assert panel.mode is ASC2.default_mode
    assert panel._device_group.value == "asc2"
    assert panel.page_index == mod.PAGE_DEVICE


def test_the_default_device_is_the_first_one_offered() -> None:
    assert mod.LcsConfigPanel(_new_host()).default_device is ASC2


def test_the_first_page_is_never_a_dead_end() -> None:
    # A module is always selected, so Next has somewhere to go from the moment the panel
    # opens rather than only once something is picked.
    panel = _new_panel()
    panel.configure(None, None, None)

    assert panel._next_btn.enabled is True


def test_a_desktop_opens_on_the_first_device_whatever_holds_the_id() -> None:
    # No screen context on a desktop: the stand-alone window opens at TMCC ID 1 on nothing
    # in particular, so guessing from whatever sits there is what surprised the operator.
    state = FakeState(12, "is_bpc2", mode=0, num_ids=8)
    panel = _new_panel(FakeStore({CommandScope.TRAIN: [state]}))

    panel.configure(CommandScope.TRAIN, 12, state)

    assert panel.device is ASC2
    assert panel.base_id == 12
    # Still told what is out there, which is the assigned box's whole job.
    panel._on_mode_selected("acc_8")
    assert _assigned(panel) == [mod.UNASSIGNED]
    panel._on_device_selected("bpc2")
    assert _assigned(panel) == ["TR: BPC2 TMCC IDs 12 - 19"]


def test_an_appliance_falls_back_to_the_first_device_when_the_id_is_free(monkeypatch) -> None:
    _appliance(monkeypatch)
    panel = _new_panel()

    panel.configure(CommandScope.ACC, 40, None)

    assert panel.device is ASC2
    assert panel.base_id == 40


def test_the_entered_id_is_squared_with_the_opening_modes_ceiling() -> None:
    # ID 95 fits a four-port switch mode but not the ASC2's eight-ID accessory mode, which
    # is what the panel opens on when there is nothing to reflect.
    panel = _new_panel()
    panel.configure(None, 95, None)

    assert panel.device is ASC2
    assert panel.base_id == panel.max_base == 91


def test_configure_seeds_device_and_mode_from_a_known_bpc2_state(monkeypatch) -> None:
    _appliance(monkeypatch)
    state = FakeState(12, "is_bpc2", mode=0, num_ids=8)
    store = FakeStore({CommandScope.TRAIN: [state]})
    panel = _new_panel(store)

    panel.configure(CommandScope.TRAIN, 12, state)

    assert panel.device is BPC2
    assert panel.mode.key == "tr_8"
    assert panel.base_id == 12
    assert panel._device_group.value == "bpc2"
    assert panel.options == {"restore": False}
    assert _assigned(panel) == ["TR: BPC2 TMCC IDs 12 - 19"]


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


def _stm2_at_1_and_bpc2_at_1_store() -> FakeStore:
    """The layout from the report: a switch module and an accessory both based at 1.

    They do not collide. SW 1 and ACC 1 are two different addresses, so each is the only
    thing at "1" as far as the other is concerned.
    """
    return FakeStore(
        {
            CommandScope.ACC: [FakeState(1, "is_bpc2", mode=3, num_ids=1)],
            CommandScope.SWITCH: [FakeState(1, "is_stm2", mode=0, num_ids=16)],
        }
    )


def _rows(cells: list[tuple[Any, ...]]) -> list[str]:
    """What one of the module boxes is showing, one string per visible row.

    Read out of the row widgets rather than off ``assigned_rows()`` / ``overlap_rows()``,
    so the assertions cover what was actually written into the box -- including a row left
    over from a busier ID, which must be hidden rather than merely blanked.
    """
    lines = []
    for row in cells:
        if not row[1].visible:
            continue
        lines.append(" ".join(cell.value for cell in row if cell.value))
    return lines


def _assigned(panel: mod.LcsConfigPanel) -> list[str]:
    return _rows(panel._assigned_cells)


def _overlaps(panel: mod.LcsConfigPanel) -> list[str]:
    return _rows(panel._overlap_cells)


def test_unowned_id_reports_unassigned() -> None:
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(40)

    assert _assigned(panel) == [mod.UNASSIGNED]
    assert panel._goto_btn.visible is False
    assert panel._new_btn.visible is False


def test_interior_port_reports_its_owner_and_offers_both_choices() -> None:
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    # The module is named exactly as it is on a base hit: the box reports what is out on
    # the layout, and which port the entered ID happens to be is not part of that.
    assert _assigned(panel) == ["ACC: ASC2 TMCC IDs 9 - 16"]
    assert panel._goto_btn.visible is True
    assert panel._goto_btn.text == "Go to 9"
    assert panel._new_btn.visible is True
    assert panel._new_btn.text == "Configure 12 as new"


def test_go_to_base_retargets_and_pre_fills() -> None:
    # A BPC2 in accessory mode holds ACC 9-16, and the operator arrives on ACC 12 meaning
    # to program an ASC2 there: same remote key, so the module really is in the way.
    store = FakeStore({CommandScope.ACC: [FakeState(9, "is_bpc2", mode=2, num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")
    panel._set_base_id(12)
    assert _assigned(panel) == ["ACC: BPC2 TMCC IDs 9 - 16"]

    panel.go_to_owning_base()

    assert panel.base_id == 9
    assert panel.device is BPC2
    assert panel.mode.key == "acc_8"
    assert panel._device_group.value == "bpc2"
    assert _assigned(panel) == ["ACC: BPC2 TMCC IDs 9 - 16"]


def test_go_to_base_ignores_a_module_on_another_remote_key() -> None:
    # The ASC2 at ACC 9-16 is nothing to a BPC2 being programmed at TR 12, so there is
    # nowhere to go and the panel stays exactly where the operator left it.
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)
    assert _assigned(panel) == [mod.UNASSIGNED]

    panel.go_to_owning_base()

    assert panel.base_id == 12
    assert panel.device is BPC2


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


def test_overlaps_are_advisory() -> None:
    store = FakeStore({CommandScope.SWITCH: [FakeState(28, "is_stm2", mode=1, num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("stm2")
    panel._on_mode_selected("single_wire")  # 16 ports
    panel._set_base_id(20)

    # Named the way the assigned box names a module: which key, which one, which IDs. The
    # word "Overlaps" is the box's title, so it is not repeated in the row.
    assert [row.text for row in panel.overlap_rows()] == ["SW: STM2 TMCC IDs 28 - 35"]
    assert _overlaps(panel) == ["SW: STM2 TMCC IDs 28 - 35"]
    # Advisory only: the ID the operator typed is untouched.
    assert panel.base_id == 20


def test_a_switch_mode_asc2_overlaps_a_switch_module_that_runs_into_it() -> None:
    # An ASC2 in switch mode claims SW 25-28 whatever scope its state was filed under,
    # and an STM2 based at SW 20 with 16 inputs runs straight through it.
    store = FakeStore({CommandScope.ACC: [FakeState(25, "is_asc2", mode=2, num_ids=4)]})
    panel = _new_panel(store)
    panel._on_device_selected("stm2")
    panel._on_mode_selected("single_wire")  # 16 ports: 20-35
    panel._set_base_id(20)

    assert _overlaps(panel) == ["SW: ASC2 TMCC IDs 25 - 28"]


def test_an_accessory_never_overlaps_a_switch_block() -> None:
    # The reported layout: an STM2 based at SW 1 claims SW 1-16, and the BPC2 on ACC 1 is
    # not in its way, so the Overlaps box says nothing and is not on the page at all.
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())
    panel._on_device_selected("stm2")
    panel._on_mode_selected("single_wire")  # 16 ports: 1-16
    panel._set_base_id(1)

    assert panel.overlap_rows() == []
    assert _overlaps(panel) == []
    assert panel._overlap_box.visible is False


def test_the_assigned_box_names_the_module_on_the_key_being_programmed() -> None:
    # The reported layout: an STM2 based at SW 1, and a BPC2 on ACC 1. Programming the
    # STM2, the switch module is what is already at "1"; the accessory is a different
    # address entirely and has no business in the box.
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())
    panel._on_device_selected("stm2")
    panel._set_base_id(1)

    assert _assigned(panel) == ["SW: STM2 TMCC IDs 1 - 16"]
    assert panel._goto_btn.visible is False
    assert panel._new_btn.visible is False


def test_the_same_id_reports_a_different_module_for_a_different_key() -> None:
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())

    # An ASC2 in its accessory mode shares the BPC2's key, and sees it.
    panel._on_device_selected("asc2")
    panel._set_base_id(1)
    assert panel.scope == CommandScope.ACC
    assert _assigned(panel) == ["ACC: BPC2 TMCC ID 1"]

    # A BPC2 in its track mode shares neither, so ID 1 really is free.
    panel._on_device_selected("bpc2")
    assert panel.scope == CommandScope.TRAIN
    assert _assigned(panel) == [mod.UNASSIGNED]


def test_switching_an_asc2_between_keys_changes_what_is_in_its_way() -> None:
    # The ASC2 is the one module that can be either, so it is the proof that the box
    # follows the mode radios and not merely the device.
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(1)
    assert _assigned(panel) == ["ACC: BPC2 TMCC ID 1"]

    panel._on_mode_selected("sw_momentary")

    assert panel.scope == CommandScope.SWITCH
    assert _assigned(panel) == ["SW: STM2 TMCC IDs 1 - 16"]


def test_with_no_device_chosen_every_module_still_counts() -> None:
    # Nothing has been picked, so there is no key to filter by and no reason to hide
    # anything: the panel has not yet been told what it is looking at, and both modules
    # sitting on "1" get a row of their own.
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())
    panel._set_base_id(1)

    assert panel.scope is None
    assert _assigned(panel) == ["ACC: BPC2 TMCC ID 1", "SW: STM2 TMCC IDs 1 - 16"]


def test_configure_prefers_a_module_on_the_screens_own_key(monkeypatch) -> None:
    # The LCS... key pressed from the switch screen means switch IDs, so the module the
    # panel seeds itself from is the switch one, even though an accessory shares the number.
    _appliance(monkeypatch)
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())

    panel.configure(CommandScope.SWITCH, 1, None)
    assert panel.device is STM2

    panel.configure(CommandScope.ACC, 1, None)
    assert panel.device is BPC2
    assert panel.mode.key == "acc_1"


def test_configure_widens_the_search_when_the_screen_is_not_on_an_lcs_key(monkeypatch) -> None:
    # From the engine screen there is no LCS key to prefer, so the search takes whatever
    # module holds the ID rather than reporting nothing.
    _appliance(monkeypatch)
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())

    panel.configure(CommandScope.ENGINE, 1, None)

    assert panel.device in (BPC2, STM2)


def test_sensor_track_claims_a_single_id() -> None:
    panel = _new_panel()
    panel._on_device_selected("sensor_track")

    panel._set_base_id(3)
    assert panel.device is SENSOR_TRACK
    assert panel.ports == 1
    assert panel.max_base == 98
    # Its one row names that address and nothing else: naming the Action Command set in
    # the same gesture made the widest row the panel has, and it lost both its ends on the
    # Pi. That option is the whole of the page after this one.
    assert panel._mode_group.options == [("ACCessory TMCC ID 3", "acc")]


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


def test_a_module_with_no_options_gets_no_controls_and_no_page() -> None:
    # The page it used to be given held a heading, the line already read on the page
    # before it and a sentence saying there was nothing to do -- a press to arrive and a
    # press to leave, for no decision.
    panel = _new_panel()
    panel._on_device_selected("asc2")

    assert ASC2.options == ()
    assert panel.skip_options is True
    assert "asc2" not in panel._option_boxes
    assert panel._option_widgets.get(("asc2", "restore")) is None


def test_bpc2_relay_warning_and_reserved_modes_are_shown_with_their_reason() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert "relay" in panel._warning_line.value
    assert panel._warning_line.value == BPC2.warning
    assert panel.reserved_text == (
        "Not available: TRack, 1 TMCC ID (reserved, no Cab support), ACCessory, 1 TMCC ID (reserved, no Cab support)"
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
# The options page is legible: a painted checkbox, wrapped prose, and whitespace
#
def test_the_lone_checkbox_is_painted_like_the_radio_lists() -> None:
    # What the Pi showed: the platform's own tick box at the label's own scale, unfilled
    # until it was set -- a smudge beside the text rather than a control with a state. The
    # module and mode radios are painted by the same call, at the same size.
    panel = _new_panel()
    host = panel.gui

    restore = panel._option_widgets[("bpc2", "restore")]

    assert restore.decoration["size"] == host.s_18
    assert restore.decoration["style"] == "checkbox"
    assert restore.decoration["pady"] == mod.OPTION_ROW_PAD
    # A pixel width would take the row's padx with it and pull the indicator flush against
    # the left edge -- the reason the radio lists are stretched by a grid option instead.
    assert restore.decoration["width"] is None


def test_the_checkbox_is_painted_at_the_size_the_mode_radios_use() -> None:
    panel = _new_panel()

    assert panel._option_widgets[("bpc2", "restore")].decoration["size"] == panel._mode_group.kwargs["size"]


def test_the_action_rows_are_larger_than_they_were_and_one_length() -> None:
    # The Sensor Track's ten Action Commands, the one radio option in the registry and the
    # longest list in the panel. A step up from the size below the page's body it was drawn
    # at, but not the checkbox's size: ten rows of that do not fit the page, and what Tk
    # drops when they do not is the Back/Next row. See LONG_OPTION_LIST.
    panel = _new_panel()
    host = panel.gui

    action = panel._option_widgets[("sensor_track", "action")]

    assert len(SENSOR_TRACK.option("action").choices) > mod.LONG_OPTION_LIST
    assert action.kwargs["size"] == host.s_14
    assert action.kwargs["size"] > host.s_12
    # And no whitespace between them: what sets a row apart is the painted indicator and
    # the row's own background. Ten rows of the padding a shorter list gets would cost the
    # page its note and the panel its Back/Next row.
    assert action.kwargs["pady"] == 0
    assert action.kwargs["stretch"] is True
    assert "width" not in action.kwargs


def test_a_short_radio_list_is_set_at_the_size_a_lone_control_is() -> None:
    # No module in the registry declares one, so the option is made here: what decides the
    # treatment is the number of rows, not which module they belong to.
    panel = _new_panel()
    host = panel.gui
    short = LcsOption(
        key="short",
        label="Pick one",
        kind=mod.OptionKind.RADIO,
        choices=(("A", 1), ("B", 2)),
    )

    panel._build_option(DummyBox(), BPC2, short)

    widget = panel._option_widgets[("bpc2", "short")]
    assert widget.kwargs["size"] == host.s_18
    assert widget.kwargs["pady"] == mod.OPTION_ROW_PAD


def test_a_long_lists_note_gets_no_padding_either() -> None:
    # The whole of that page is the list; the sentence under it is set against the last row
    # because there is nothing left to hold it off with.
    panel = _new_panel()

    box = panel._option_boxes["sensor_track"]
    note = next(child for child in box.children if getattr(child, "value", None) == mod.SENSOR_TRACK_FILTER_NOTE)

    assert note.tk.configured["pady"] == 0
    # Still wrapped: it is a full sentence, and 741px of it against a 446px page.
    assert note.tk.configured["wraplength"] == panel._wrap_px


@pytest.mark.parametrize(
    "compact, option_pad, note_pad",
    [
        (False, mod.OPTION_ROW_PAD, mod.NOTE_PAD),
        (True, mod.OPTION_ROW_PAD_COMPACT, mod.NOTE_PAD_COMPACT),
    ],
)
def test_the_options_page_holds_its_rows_and_its_prose_apart(compact: bool, option_pad: int, note_pad: int) -> None:
    panel, _body, _host = _build_with_body(compact=compact)

    assert panel._option_widgets[("bpc2", "restore")].decoration["pady"] == option_pad
    assert panel._warning_line.tk.configured["pady"] == note_pad
    assert panel._reserved_line.tk.configured["pady"] == note_pad
    # Not the long list: its rows get nothing on either kind of host.
    assert panel._option_widgets[("sensor_track", "action")].kwargs["pady"] == 0


def test_the_option_rows_are_held_apart_between_the_two_other_lists() -> None:
    # More than the mode rows, which share the fullest page in the panel; less than the
    # module rows, which have a page to themselves.
    assert mod.MODE_ROW_PAD < mod.OPTION_ROW_PAD < mod.RADIO_ROW_PAD
    assert mod.MODE_ROW_PAD_COMPACT <= mod.OPTION_ROW_PAD_COMPACT <= mod.RADIO_ROW_PAD_COMPACT


def test_the_pages_prose_is_read_at_the_body_size_not_below_it() -> None:
    # These are the longest sentences in the panel, and on the Pi they were the two lines
    # an operator could not read: a step below the body size, which is fine print at the
    # scale the Pi draws at.
    panel = _new_panel()
    host = panel.gui
    panel._on_device_selected("bpc2")

    assert panel._warning_line.text_size == host.s_14
    assert panel._reserved_line.text_size == host.s_14
    assert panel._options_summary.text_size == host.s_14


def test_every_line_of_prose_on_the_page_is_wrapped_to_the_popups_width() -> None:
    # What the photograph showed: the BPC2's relay warning ran off both edges at once.
    # Tk truncates nothing -- it centers a label wider than its container, so the sentence
    # lost its beginning and its end -- and only a wraplength keeps it whole.
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    wrap = panel._wrap_px

    for line in (panel._options_summary, panel._warning_line, panel._reserved_line):
        assert line.tk.configured["wraplength"] == wrap
        # A broken line follows the line above it, centered under the heading.
        assert line.tk.configured["justify"] == "center"


def test_a_checkbox_label_is_wrapped_from_the_left_beside_its_indicator() -> None:
    # Not centered like the prose: the label is set beside the indicator, so a second line
    # belongs under the first rather than under the middle of the box.
    panel = _new_panel()

    restore = panel._option_widgets[("bpc2", "restore")]

    assert restore.tk.configured["wraplength"] == panel._wrap_px
    assert restore.tk.configured["justify"] == "left"


def test_an_options_own_note_is_wrapped_and_read_at_the_body_size() -> None:
    # The Sensor Track's note about the engine ID filters -- a full sentence, and the one
    # note the registry carries.
    panel = _new_panel()
    host = panel.gui

    box = panel._option_boxes["sensor_track"]
    note = next(child for child in box.children if getattr(child, "value", None) == mod.SENSOR_TRACK_FILTER_NOTE)

    assert note.text_size == host.s_14
    assert note.tk.configured["wraplength"] == panel._wrap_px


def test_the_wrap_is_the_width_the_popup_is_built_to() -> None:
    # create_popup builds the popup's title row to the emergency box's width, so that is
    # the width a line inside it has to fit.
    panel = _new_panel()
    host = panel.gui

    assert panel._wrap_px == host.emergency_box_width - mod.WRAP_INSET


def test_the_wrap_falls_back_to_the_pane_and_then_to_a_floor() -> None:
    # A host that has not measured its emergency box yet still has a pane width; one with
    # neither gets a width narrower than any pane the GUI runs in, so a line can only ever
    # be broken early -- never off the edge of the screen.
    panel = _new_panel()
    host = panel.gui

    host.emergency_box_width = 0
    assert panel._wrap_px == host.width - mod.WRAP_INSET

    host.width = 0
    assert panel._wrap_px == mod.MIN_WRAP_PX
    assert mod.MIN_WRAP_PX < 480


def test_a_line_with_nothing_to_say_leaves_the_page_and_takes_its_gaps_with_it() -> None:
    # Only a BPC2 fills either line -- it is the one module with a warning and the one with
    # reserved modes -- and an empty label still stands a line tall and still carries its
    # own padding above and below.
    panel = _new_panel()

    panel._on_device_selected("bpc2")
    assert panel._warning_line.visible is True
    assert panel._reserved_line.visible is True

    panel._on_device_selected("sensor_track")
    assert panel._warning_line.visible is False
    assert panel._reserved_line.visible is False

    # And comes back with something to say.
    panel._on_device_selected("bpc2")
    assert panel._warning_line.visible is True


def test_the_heading_is_followed_by_the_module_then_a_gap_then_the_settings() -> None:
    # The heading belongs with the line under it; the wider gap separates the module being
    # programmed from the settings being chosen for it. Children are recorded in creation
    # order, which is the order guizero packs them in.
    panel, _body, _host = _build_with_body()
    page = panel._pages[mod.PAGE_OPTIONS]

    assert page.children[0].value == "Options"
    assert getattr(page.children[1], "vspace", None) == mod.SECTION_GAP
    assert page.children[2] is panel._options_summary
    assert page.children[3] is panel._warning_line
    assert page.children[4] is panel._reserved_line
    assert getattr(page.children[5], "vspace", None) == mod.PAGE_GAP
    assert page.children[6] in panel._option_boxes.values()


#
# The options page is stepped over for a module that has none
#
@pytest.mark.parametrize(
    "key, skipped",
    [("asc2", True), ("stm2", True), ("bpc2", False), ("sensor_track", False)],
)
def test_only_a_module_with_no_options_skips_the_page(key: str, skipped: bool) -> None:
    panel = _new_panel()
    panel._on_device_selected(key)

    assert panel.skip_options is skipped


def test_no_module_chosen_yet_skips_nothing() -> None:
    # Next is disabled until a module is chosen, so this is never stepped through -- but
    # the answer has to be about a module, not about the absence of one.
    panel = _new_panel()

    assert panel.device is None
    assert panel.skip_options is False


def test_next_goes_from_the_id_straight_to_the_review_for_a_module_with_no_options() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")

    panel.next_page()
    assert panel.page_index == mod.PAGE_ID

    panel.next_page()
    assert panel.page_index == mod.PAGE_REVIEW
    assert panel._pages[mod.PAGE_OPTIONS].visible is False


def test_back_comes_straight_back_from_the_review_to_the_id() -> None:
    panel = _new_panel()
    panel._on_device_selected("stm2")
    panel.next_page()
    panel.next_page()
    assert panel.page_index == mod.PAGE_REVIEW

    panel.previous_page()

    assert panel.page_index == mod.PAGE_ID


def test_a_module_with_an_option_still_stops_on_the_page() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    panel.next_page()
    panel.next_page()

    assert panel.page_index == mod.PAGE_OPTIONS
    assert panel._pages[mod.PAGE_OPTIONS].visible is True
    assert panel._option_boxes["bpc2"].visible is True


def test_the_page_is_still_built_so_the_review_keeps_its_index() -> None:
    # Every page is reached by index, and the four are created once in build(); leaving one
    # out would move the review page.
    panel = _new_panel()

    assert len(panel._pages) == 4
    assert panel._pages[mod.PAGE_REVIEW] is not panel._pages[mod.PAGE_OPTIONS]


def test_a_module_that_changes_under_the_open_page_falls_back_rather_than_forward() -> None:
    # Reachable when a late synchronization seeds a module while the operator is already on
    # the options page. Nobody is advanced past a page they have not seen.
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel.next_page()
    panel.next_page()
    assert panel.page_index == mod.PAGE_OPTIONS

    panel._on_device_selected("asc2")
    panel._show_page(mod.PAGE_OPTIONS)

    assert panel.page_index == mod.PAGE_ID


def test_stepping_past_the_last_page_still_lands_on_the_review() -> None:
    # The walk off the end of the pages that _show_page clamps.
    panel = _new_panel()
    panel._on_device_selected("asc2")

    for _ in range(6):
        panel.next_page()

    assert panel.page_index == mod.PAGE_REVIEW


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
    assert panel._requested_line.value.startswith("Requested: BPC2 - TRack, 8 TMCC IDs at TR 12")
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

    # Select ASC2, which has 4 enabled modes. The panel opens at TMCC ID 1, which is the
    # address every row is labeled from.
    panel._on_device_selected("asc2")
    assert len(panel._mode_group.options) == 4
    assert panel._mode_group.options[0] == ("ACCessory TMCC IDs 1 - 8", "acc_8")
    assert panel._mode_group.options[1] == ("ACCessory TMCC ID 1", "acc_1")
    # Every switch mode names the block it consumes, as the accessory modes do.
    assert panel._mode_group.options[2] == ("SWitch pulse TMCC IDs 1 - 4", "sw_momentary")
    assert panel._mode_group.options[3] == ("SWitch latching TMCC IDs 1 - 4", "sw_latching")

    # Switch to Sensor Track, which has 1 mode
    panel._on_device_selected("sensor_track")
    assert len(panel._mode_group.options) == 1
    assert panel._mode_group.options[0] == ("ACCessory TMCC ID 1", "acc")

    # Switch to BPC2, which has 2 enabled modes (the 1-ID modes are disabled)
    panel._on_device_selected("bpc2")
    assert len(panel._mode_group.options) == 2
    assert panel._mode_group.options[0] == ("TRack TMCC IDs 1 - 8", "tr_8")
    assert panel._mode_group.options[1] == ("ACCessory TMCC IDs 1 - 8", "acc_8")


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
    panel._refresh_nav()
    assert panel._next_btn.enabled is True

    panel.next_page()
    assert panel.page_index == mod.PAGE_ID
    panel.previous_page()
    assert panel.page_index == mod.PAGE_DEVICE
    assert panel._sync_line.visible is True


def test_occupancy_is_unassigned_until_the_store_is_populated(monkeypatch) -> None:
    # On the appliance, because the module that turns up at synchronization is also the one
    # the panel then opens on, which is what puts it on the remote key the box reports.
    _appliance(monkeypatch)
    states: dict[CommandScope, list[FakeState]] = {CommandScope.TRAIN: []}
    panel = _new_panel(FakeStore(states))
    panel.set_sync_pending(True)
    panel._set_base_id(12)

    assert _assigned(panel) == [mod.UNASSIGNED]

    states[CommandScope.TRAIN].append(FakeState(12, "is_bpc2", mode=0, num_ids=8))
    panel.on_synchronized()

    assert _assigned(panel) == ["TR: BPC2 TMCC IDs 12 - 19"]


def test_on_synchronized_re_seeds_while_the_operator_has_not_chosen(monkeypatch) -> None:
    # A module is always selected once the panel has been configured, so "untouched" is a
    # flag of its own now rather than the absence of a selection.
    _appliance(monkeypatch)
    states: dict[CommandScope, list[FakeState]] = {CommandScope.TRAIN: []}
    panel = _new_panel(FakeStore(states))
    panel.configure(None, 12, None)
    panel.set_sync_pending(True)
    assert panel.device is ASC2

    states[CommandScope.TRAIN].append(FakeState(12, "is_bpc2", mode=0, num_ids=8))
    panel.on_synchronized()

    assert panel.device is BPC2
    assert panel.mode.key == "tr_8"
    assert panel._device_group.value == "bpc2"
    assert panel.sync_pending is False
    assert panel._sync_line.visible is False


def test_on_synchronized_keeps_the_operators_choices() -> None:
    states: dict[CommandScope, list[FakeState]] = {CommandScope.SWITCH: []}
    panel = _new_panel(FakeStore(states))
    panel.set_sync_pending(True)
    panel._on_device_selected("stm2")
    panel._set_base_id(12)
    panel._options["restore"] = True

    states[CommandScope.SWITCH].append(FakeState(12, "is_stm2", mode=1, num_ids=8))
    panel.on_synchronized()

    assert panel.device is STM2
    assert panel.base_id == 12
    assert panel.options["restore"] is True
    assert panel._configure_btn.enabled is True
    assert _assigned(panel) == ["SW: STM2 TMCC IDs 12 - 19"]


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


#
# Equal-width radio rows
#
def test_both_radio_lists_are_stretched_to_the_box_around_them() -> None:
    # One length for every row, rather than each ending where its own label does. Left to
    # guizero a row is gridded sticky="W", which went unnoticed until the rows were painted
    # with a background of their own: on the ID page the shortest mode then stopped well
    # short of the Mode box while the longest nearly filled it.
    panel = _new_panel()

    assert panel._device_group.kwargs["stretch"] is True
    assert panel._mode_group.kwargs["stretch"] is True


def test_neither_radio_list_is_built_with_an_explicit_row_width() -> None:
    # A pixel width would equalize the rows too, and take their padx with it: Tk drops padx
    # when a Checkbutton showing an image is given -width, pulling every indicator flush
    # against the left edge. The stretch above is a grid option instead.
    panel = _new_panel()

    for group in (panel._device_group, panel._mode_group):
        assert "width" not in group.kwargs


#
# Equal-width Currently Assigned, Overlaps and Mode boxes
#
class _RecordingGridTk:
    """Records the grid calls a real Tk frame would receive."""

    def __init__(self) -> None:
        self.columns: dict[int, dict[str, Any]] = {}
        self.grid_options: dict[str, Any] = {}

    def grid_columnconfigure(self, col: int, **kwargs: Any) -> None:
        self.columns.setdefault(col, {}).update(kwargs)

    def grid_configure(self, **kwargs: Any) -> None:
        self.grid_options.update(kwargs)


def _record_titled_boxes(panel: mod.LcsConfigPanel) -> None:
    for widget in (panel._titled_boxes, panel._assigned_box, panel._overlap_box, panel._mode_box):
        widget.tk = _RecordingGridTk()


def test_the_titled_boxes_are_stacked_in_one_column() -> None:
    # Same column, one above the other: that alone is what makes them equally wide, and
    # it is why they are gridded rather than packed.
    panel = _new_panel()

    for box in (panel._assigned_box, panel._overlap_box, panel._mode_box):
        assert box in panel._titled_boxes.children
    assert panel._titled_boxes.kwargs["layout"] == "grid"
    # The mode is chosen first; Currently Assigned and then Overlaps report what it and the
    # ID above it run into.
    assert [panel._mode_box.grid, panel._assigned_box.grid, panel._overlap_box.grid] == [
        [0, 0],
        [0, 1],
        [0, 2],
    ]


def test_every_showing_box_is_stretched_across_that_column_and_spaced_from_the_next() -> None:
    store = FakeStore({CommandScope.ACC: [FakeState(30, "is_bpc2", mode=2, num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")  # the mode box is showing
    panel._set_base_id(25)  # and the BPC2 at 30-37 runs into 25-32
    assert panel._overlap_box.visible is True
    _record_titled_boxes(panel)

    panel._lay_out_titled_boxes()

    assert panel._titled_boxes.tk.columns == {0: {"weight": 1}}
    # The stretch that makes them one width, and the whitespace that keeps the three from
    # reading as one ruled block. Padding rather than a spacer widget only because this
    # method is re-run after every refresh; see its docstring.
    stretched_and_spaced = {"sticky": "ew", "pady": (0, mod.BOX_GAP)}
    assert panel._assigned_box.tk.grid_options == stretched_and_spaced
    assert panel._overlap_box.tk.grid_options == stretched_and_spaced
    assert panel._mode_box.tk.grid_options == stretched_and_spaced


@pytest.mark.parametrize("compact, gap", [(False, mod.BOX_GAP), (True, mod.BOX_GAP_COMPACT)])
def test_the_gap_between_the_boxes_is_tighter_on_a_compact_host(compact: bool, gap: int) -> None:
    host = _new_host()
    host.compact = compact
    panel = mod.LcsConfigPanel(host)
    panel.build(DummyBox())
    _record_titled_boxes(panel)

    panel._lay_out_titled_boxes()

    assert panel._assigned_box.tk.grid_options["pady"] == (0, gap)


def test_a_hidden_box_is_not_stretched_back_onto_the_screen() -> None:
    # No device chosen, so there are no modes to show and nothing can be in the way.
    # Configuring the grid for a widget the grid has forgotten would put the empty titled
    # frame back on the page.
    panel = _new_panel()
    assert panel._mode_box.visible is False
    assert panel._overlap_box.visible is False
    _record_titled_boxes(panel)

    panel._lay_out_titled_boxes()

    assert panel._assigned_box.tk.grid_options == {"sticky": "ew", "pady": (0, mod.BOX_GAP)}
    assert panel._overlap_box.tk.grid_options == {}
    assert panel._mode_box.tk.grid_options == {}


def test_the_stretch_is_re_applied_on_every_id_page_refresh() -> None:
    # guizero rebuilds a container's grid options from scratch whenever a child is shown
    # or hidden, and neither sticky nor pady is among the options it replays, so setting
    # them once at build time would be lost the first time the mode box appeared.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    _record_titled_boxes(panel)

    panel._refresh_id_page()

    assert panel._titled_boxes.tk.columns == {0: {"weight": 1}}
    assert panel._assigned_box.tk.grid_options == {"sticky": "ew", "pady": (0, mod.BOX_GAP)}
    assert panel._mode_box.tk.grid_options == {"sticky": "ew", "pady": (0, mod.BOX_GAP)}


def test_equalizing_survives_a_tcl_error() -> None:
    panel = _new_panel()
    _record_titled_boxes(panel)

    def _raise(**_kwargs: Any) -> None:
        raise mod.TclError("no such widget")

    panel._assigned_box.tk.grid_configure = _raise

    panel._lay_out_titled_boxes()  # must not raise


#
# Whitespace: tight under a heading, wider between the sections of a page
#
def _build_with_body(compact: bool = False):
    host = _new_host()
    host.compact = compact
    panel = mod.LcsConfigPanel(host)
    body = DummyBox()
    panel.build(body)
    return panel, body, host


def test_every_spacer_that_is_asked_for_and_no_other() -> None:
    panel, body, host = _build_with_body()
    id_page = panel._pages[mod.PAGE_ID]
    options_page = panel._pages[mod.PAGE_OPTIONS]

    parents = [parent for parent, _pixels in host.vspaces]
    assert parents == [
        body,  # under the popup's title row
        panel._pages[mod.PAGE_DEVICE],  # under that page's prompt
        id_page,  # under the stepper row
        panel._mode_box,  # between the mode radios and the footnote under them
        id_page,  # between the titled boxes and the choice buttons
        options_page,  # under that page's heading
        options_page,  # between the module and the settings chosen for it
        body,  # above the Back/Next row
    ]


def test_the_body_spacer_comes_before_the_sync_line_and_the_pages() -> None:
    panel, body, _host = _build_with_body()

    assert getattr(body.children[0], "vspace", None) == mod.SECTION_GAP
    assert body.children[1] is panel._sync_line
    assert body.children[2] is panel._pages[mod.PAGE_DEVICE]


def test_the_device_page_spacer_sits_between_the_prompt_and_the_group() -> None:
    panel, _body, _host = _build_with_body()
    page = panel._pages[mod.PAGE_DEVICE]

    assert page.children[0].value == "Which module are you configuring?"
    assert getattr(page.children[1], "vspace", None) == mod.SECTION_GAP
    assert page.children[2] is panel._device_group


def test_the_id_pages_sections_are_held_apart() -> None:
    # The crowded page: the stepper, the three titled boxes and the choice buttons each
    # answer a different question, and ran together into one block without these.
    panel, _body, _host = _build_with_body()
    page = panel._pages[mod.PAGE_ID]

    assert page.children[0] is panel._id_heading
    assert page.children[1].kwargs["layout"] == "grid"  # the - 8 + row
    assert getattr(page.children[2], "vspace", None) == mod.PAGE_GAP
    assert page.children[3] is panel._titled_boxes
    # One gap below the boxes, where there were two with the block line between them.
    assert getattr(page.children[4], "vspace", None) == mod.PAGE_GAP
    # The choice buttons' row, and nothing after it: the page ends where the boxes' gap
    # leaves off, rather than with a line and a second gap between the two.
    assert panel._goto_btn in page.children[5].children
    assert panel._new_btn in page.children[5].children
    assert len(page.children) == 6


@pytest.mark.parametrize(
    "compact, section, page, lead",
    [
        (False, mod.SECTION_GAP, mod.PAGE_GAP, mod.MODE_NOTE_LEAD),
        (True, mod.SECTION_GAP_COMPACT, mod.PAGE_GAP_COMPACT, mod.MODE_NOTE_LEAD_COMPACT),
    ],
)
def test_the_gaps_are_tighter_on_a_compact_host(compact: bool, section: int, page: int, lead: int) -> None:
    _panel, _body, host = _build_with_body(compact=compact)

    assert [pixels for _parent, pixels in host.vspaces] == [
        section,
        section,
        page,
        lead,
        page,
        section,
        page,
        page,
    ]


#
# The panel's own Back/Next row: Back is off the first page, and left of Next on the rest
#
def test_back_and_next_are_the_last_thing_in_the_body_after_a_gap() -> None:
    # The panel's own row, not the popup's footer: Close is added below everything build()
    # produces, so it lands on a line of its own under these two.
    panel, body, _host = _build_with_body()

    assert getattr(body.children[-2], "vspace", None) == mod.PAGE_GAP
    assert body.children[-1] is panel._nav
    assert [child.text for child in panel._nav.children if getattr(child, "text", "")] == ["Back", "Next"]


def test_the_panel_offers_no_footer_so_close_gets_a_line_of_its_own() -> None:
    # create_popup's other branch: with no footer to append Close to, it adds the plain
    # centred Close button to the overlay itself, below the panel's own content.
    panel = _new_panel()

    assert panel.has_footer is False
    assert mod.LcsConfigPanel.build_footer is mod.OverlayPanel.build_footer


@pytest.mark.parametrize("linux", [True, False])
def test_close_is_asked_for_only_where_the_window_has_no_title_bar(monkeypatch, linux: bool) -> None:
    # The Pi and the Deck run full screen, so a button below the panel is the only way off
    # it. A Mac or a PC window has a close box already wired to the same shutdown, and a
    # Close inside the window duplicates it. Same platform helper as the ID editor.
    monkeypatch.setattr(mod, "is_linux", lambda: linux, raising=True)

    assert mod.needs_close_button() is linux
    assert _new_panel().has_close is linux


def test_declining_close_is_this_panel_and_no_other() -> None:
    # Every other overlay is dismissed by Close and nothing else, so the base class says
    # yes and create_popup goes on adding it there.
    panel = _new_panel()

    assert mod.OverlayPanel.has_close.fget(panel) is True
    assert mod.LcsConfigPanel.has_close is not mod.OverlayPanel.has_close


def test_the_device_page_shows_next_alone() -> None:
    # There is nowhere to go back to from the first page, so Back is off the row entirely --
    # not greyed, and not standing in a placeholder of its own width. The row asks for no
    # width, so it shrinks to Next and Tk centers it.
    panel = _new_panel()

    assert panel.page_index == mod.PAGE_DEVICE
    assert panel._back_btn.visible is False
    assert [child.text for child in panel._nav.children if child.visible] == ["Next"]


def test_back_is_visible_and_enabled_on_every_later_page() -> None:
    panel = _new_panel()
    # A BPC2 rather than an ASC2: it is the module that declares an option, so all four
    # pages are walked rather than the options page being stepped over.
    panel._on_device_selected("bpc2")

    for expected in (mod.PAGE_ID, mod.PAGE_OPTIONS, mod.PAGE_REVIEW):
        panel.next_page()
        assert panel.page_index == expected
        assert panel._back_btn.visible is True
        assert panel._back_btn.enabled is True


def test_back_is_created_first_so_it_is_never_to_the_right_of_next() -> None:
    # What the Pi showed: Back reappeared on the first page *after* Next. guizero re-packs a
    # container's children in creation order, so the order asserted here is the order the row
    # keeps however often Back leaves it and comes back.
    panel = _new_panel()
    panel._on_device_selected("asc2")

    for _ in range(3):
        panel.next_page()
    for _ in range(3):
        panel.previous_page()
        assert [child.text for child in panel._nav.children] == ["Back", "Next"]


def test_stepping_forward_and_back_restores_the_initial_visibility() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    before = panel._back_btn.visible

    panel.next_page()
    panel.previous_page()

    assert panel._back_btn.visible == before


def test_the_rows_packing_is_replayed_after_every_toggle(monkeypatch) -> None:
    # Hiding or showing Back runs the row's own display_widgets(), which rebuilds pack
    # options from scratch and discards the padding style_footer_button recorded.
    calls: list[Any] = []
    monkeypatch.setattr(mod, "restore_footer_packing", lambda row: calls.append(row), raising=True)

    panel = mod.LcsConfigPanel(_new_host())
    panel.build(DummyBox())
    built = len(calls)
    assert built >= 1

    panel._on_device_selected("asc2")
    panel.next_page()
    panel.previous_page()

    assert len(calls) > built
    # The panel's own row, never the popup's overlay: the buttons live here now.
    assert set(calls) == {panel._nav}


def test_next_enablement_is_unchanged_by_the_hidden_back_button() -> None:
    panel = _new_panel()

    assert panel._next_btn.enabled is False
    panel._on_device_selected("asc2")
    panel._refresh_nav()
    assert panel._next_btn.enabled is True

    for _ in range(3):
        panel.next_page()
    assert panel.page_index == mod.PAGE_REVIEW
    assert panel._next_btn.enabled is False


@pytest.mark.parametrize(
    "compact, expected",
    [(False, mod.NAV_ROW_PAD), (True, mod.NAV_ROW_PAD_COMPACT)],
)
def test_the_nav_row_gives_back_the_footer_bands_vertical_padding(monkeypatch, compact: bool, expected: int) -> None:
    # Back and Next wear the shared footer look, but they are not in the popup's footer band:
    # Close is, below them, with its own lead and padding. A footer button's 20px above and
    # below, taken three times down one overlay, is what pushed Close off the ID page.
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(mod, "repad_footer_button", lambda btn, **kw: calls.append((btn.text, kw)), raising=True)

    _build_with_body(compact=compact)

    assert calls == [("Back", {"pady": expected}), ("Next", {"pady": expected})]
    # Horizontal padding is untouched: it is the gap between the two buttons.
    assert all("padx" not in kwargs for _text, kwargs in calls)


def test_the_row_holds_the_two_buttons_and_nothing_else() -> None:
    # No placeholder standing in for Back. It bought Next a fixed x at the cost of a
    # Back-shaped hole beside it on the first page, and of a second widget that had to be
    # shown exactly when Back was not.
    panel = _new_panel()

    assert [type(child).__name__ for child in panel._nav.children] == ["DummyHoldButton"] * 2


#
# The ID page names the module
#
def test_the_id_heading_names_the_selected_module() -> None:
    panel = _new_panel()

    assert panel._id_heading.value == "Base TMCC ID"

    panel._on_device_selected("bpc2")
    assert panel.id_heading_text == "BPC2 TMCC ID"
    assert panel._id_heading.value == "BPC2 TMCC ID"

    panel._on_device_selected("stm2")
    assert panel._id_heading.value == "STM2 TMCC ID"


def test_the_editors_own_header_is_named_with_the_heading() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert panel._id_field.field_name == "BPC2 TMCC ID"


#
# The ID box is typed into with whatever keyboard the platform has
#
@pytest.mark.parametrize(
    "touch, editor, on_screen",
    [(True, mod.EditorType.KEYPAD, True), (False, mod.EditorType.KEYBOARD, False)],
)
def test_the_id_editor_follows_the_platform(monkeypatch, touch: bool, editor: Any, on_screen: bool) -> None:
    monkeypatch.setattr(mod, "is_linux", lambda: touch, raising=True)
    panel = _new_panel()

    assert panel._id_field.editor is editor
    assert panel._id_field.show_keyboard_on_edit is on_screen


def test_a_desktop_id_box_opens_for_typing_on_a_click(monkeypatch) -> None:
    monkeypatch.setattr(mod, "is_linux", lambda: False, raising=True)
    panel = _new_panel()

    bound = dict(panel._id_field.tk.binds)
    assert "<Button-1>" in bound

    bound["<Button-1>"](None)
    assert panel._id_field.edits == 1


def test_a_touch_id_box_keeps_press_and_hold_only(monkeypatch) -> None:
    monkeypatch.setattr(mod, "is_linux", lambda: True, raising=True)
    panel = _new_panel()

    assert panel._id_field.tk.binds == []


@pytest.mark.parametrize("linux", [True, False])
def test_touch_only_editing_asks_the_platform_helper(monkeypatch, linux: bool) -> None:
    # The Pi and the Deck are the Linux hosts, and the answer comes from utils.host_info:
    # importing it from the pytrain package root instead would be circular, because that
    # package imports EngineGui -- and through it this panel -- before defining anything.
    monkeypatch.setattr(mod, "is_linux", lambda: linux, raising=True)

    assert mod.touch_only_editing() is linux
    assert mod.LcsConfigPanel(_new_host()).touch_editing is linux


#
# The mode radios live in a titled box
#
def test_the_mode_radios_are_in_a_box_titled_mode() -> None:
    panel = _new_panel()

    assert panel._mode_box.text == mod.MODE_TITLE
    assert panel._mode_group in panel._mode_box.children


def test_the_mode_box_is_hidden_until_a_device_declares_modes() -> None:
    panel = _new_panel()

    assert panel._mode_box.visible is False

    panel._on_device_selected("asc2")
    assert panel._mode_box.visible is True

    panel._select_device(None)
    panel._refresh_mode_selector()
    assert panel._mode_box.visible is False


#
# The ID page's type scale, and the order of its lines
#
def test_the_mode_options_are_larger_than_the_page_body() -> None:
    # The modes are the choice being made on this page, so they read above the page's body
    # size -- and above the device rows on the page before.
    panel = _new_panel()
    host = panel.gui

    assert panel._mode_group.kwargs["size"] == host.s_18
    assert panel._mode_group.kwargs["size"] > host.s_14
    assert panel._device_group.kwargs["size"] == host.s_14


@pytest.mark.parametrize(
    "compact, device, mode",
    [
        (False, mod.RADIO_ROW_PAD, mod.MODE_ROW_PAD),
        (True, mod.RADIO_ROW_PAD_COMPACT, mod.MODE_ROW_PAD_COMPACT),
    ],
)
def test_both_radio_lists_hold_their_rows_apart(compact: bool, device: int, mode: int) -> None:
    # Whitespace between one radio and the next, on the page that chooses the module and on
    # the page that chooses its mode. Asked for as the row's own padding rather than as grid
    # padding, because guizero rebuilds a container's grid options from scratch whenever
    # anything in it is created, shown or hidden, and pady is not among the ones it replays.
    panel, _body, _host = _build_with_body(compact=compact)

    assert panel._device_group.kwargs["pady"] == device
    assert panel._mode_group.kwargs["pady"] == mode


def test_the_mode_rows_are_held_apart_less_than_the_module_rows() -> None:
    # The ID page is the fullest of the four and its rows are the tallest -- a size above the
    # page body, so a painted indicator half again as large -- while the device page has
    # nothing below its radios at all. Both are more than those rows had before, which was
    # Tk's own single pixel: the rebuild that lost their paint lost their padding with it.
    assert mod.MODE_ROW_PAD < mod.RADIO_ROW_PAD
    assert mod.MODE_ROW_PAD_COMPACT < mod.RADIO_ROW_PAD_COMPACT
    assert mod.RADIO_ROW_PAD > 6


def test_the_three_titled_boxes_are_labelled_at_the_page_body_size() -> None:
    # A step below it read as fine print on the Pi, and what these boxes report is what the
    # operator checks before committing an ID.
    panel = _new_panel()
    host = panel.gui

    assert panel._assigned_box.text_size == host.s_14
    assert panel._overlap_box.text_size == host.s_14
    assert panel._mode_box.text_size == host.s_14
    assert panel._mode_group.kwargs["size"] > panel._mode_box.text_size


def test_the_module_rows_are_body_size_and_the_footnote_below_it() -> None:
    # The rows name what already answers to this ID, which is the answer the operator came
    # to the page for. The footnote is a caption on the radios above it -- context, not a
    # choice -- and the quietest thing on the page.
    store = FakeStore({CommandScope.ACC: [FakeState(30, "is_bpc2", mode=2, num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")
    panel._set_base_id(25)  # the BPC2 at 30-37 runs into 25-32, so the Overlaps box speaks
    host = panel.gui

    assigned = panel._assigned_cells[0]
    assert [cell.text_size for cell in assigned] == [host.s_14] * mod.ROW_COLUMNS
    # The two boxes read as one list, so their rows are the same size.
    assert all(cell.text_size == host.s_14 for cell in panel._overlap_cells[0])
    assert panel._mode_footnote_line.text_size == host.s_10
    assert panel._mode_footnote_line.text_size < assigned[0].text_size


def test_the_mode_sits_directly_under_the_id_row_and_the_reports_below_both() -> None:
    # The two things chosen on the page come first, in the order they are chosen: the
    # address, then the mode. Only then what those choices run into. Children are recorded
    # in creation order, which is the order guizero packs them in.
    panel = _new_panel()
    order = panel._pages[mod.PAGE_ID].children
    row = next(i for i, child in enumerate(order) if panel._minus_btn in getattr(child, "children", []))

    heading = order.index(panel._id_heading)
    boxes = order.index(panel._titled_boxes)

    assert heading < row < boxes
    # Nothing between the stepper and the boxes but the spacer that holds them apart.
    assert boxes == row + 2
    # The titled boxes share that one slot: the mode radios, then assigned, then overlaps.
    assert panel._mode_box.grid == [0, 0]
    assert panel._assigned_box.grid == [0, 1]
    assert panel._overlap_box.grid == [0, 2]


#
# What is already assigned to this TMCC ID
#
def test_the_assignment_line_is_in_a_box_titled_currently_assigned() -> None:
    panel = _new_panel()

    assert panel._assigned_box.text == mod.ASSIGNED_TITLE
    assert mod.ASSIGNED_TITLE == "Currently Assigned"
    assert panel._assigned_grid in panel._assigned_box.children
    assert all(cell in panel._assigned_grid.children for cell in panel._assigned_cells[0])


def test_an_unassigned_id_says_so_rather_than_going_blank() -> None:
    # The box is always shown, so an empty line inside a titled frame would read as a
    # failure to look rather than as an answer.
    panel = _new_panel()

    assert mod.UNASSIGNED == "Unassigned"
    assert _assigned(panel) == [mod.UNASSIGNED]
    assert panel._assigned_box.visible is True


@pytest.mark.parametrize(
    "scope, flag, mode, num_ids, device_key, expected",
    [
        (CommandScope.ACC, "is_asc2", 0, 8, "asc2", "ACC: ASC2 TMCC IDs 20 - 27"),
        (CommandScope.SWITCH, "is_stm2", 1, 8, "stm2", "SW: STM2 TMCC IDs 20 - 27"),
        (CommandScope.TRAIN, "is_bpc2", 0, 8, "bpc2", "TR: BPC2 TMCC IDs 20 - 27"),
        (CommandScope.ACC, "is_sensor_track", None, 1, "sensor_track", "ACC: Sensor Track TMCC ID 20"),
    ],
)
def test_an_assigned_id_names_the_module_its_remote_key_and_its_block(
    scope: CommandScope, flag: str, mode: Any, num_ids: int, device_key: str, expected: str
) -> None:
    # The remote key is the point of the line: it is how the operator addresses whatever
    # is already there. A single-port module says "TMCC ID", not a range of one. Each
    # module is looked for while programming a module on its own key, because that is the
    # only time it can be in the way.
    store = FakeStore({scope: [FakeState(20, flag, mode=mode, num_ids=num_ids)]})
    panel = _new_panel(store)
    panel._on_device_selected(device_key)
    panel._set_base_id(20)

    assert _assigned(panel) == [expected]


def test_the_row_is_gridded_with_the_remote_key_first_and_bold() -> None:
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(9)

    key, module, ids = panel._assigned_cells[0]
    assert [cell.value for cell in (key, module, ids)] == ["ACC:", "ASC2", "TMCC IDs 9 - 16"]
    # The key is the column the eye runs down, and the only part drawn bold.
    assert key.text_bold is True
    assert [cell.text_bold for cell in (module, ids)] == [False, False]
    # A column each, so the module names and the ID ranges line up down the box.
    assert [cell.grid for cell in panel._assigned_cells[0]] == [[0, 0], [1, 0], [2, 0]]
    assert mod.ROW_COLUMNS == 3


def test_an_interior_hit_does_not_spell_out_which_port_it_is() -> None:
    # The range already says the entered ID falls inside the module, and which port of it
    # exactly is nothing the operator can act on -- the two buttons below the box are
    # where that decision is made, and they name the base ID themselves.
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    assert [cell.value for cell in panel._assigned_cells[0]] == ["ACC:", "ASC2", "TMCC IDs 9 - 16"]
    assert "port" not in " ".join(_assigned(panel))


#
# What the chosen block runs into
#
def _overlapping_store() -> FakeStore:
    """Two accessory modules above ID 25, so an eight-ID block at 25 runs into both."""
    return FakeStore(
        {
            CommandScope.ACC: [
                FakeState(26, "is_bpc2", mode=2, num_ids=8),
                FakeState(30, "is_asc2", mode=0, num_ids=8),
            ]
        }
    )


def test_the_overlaps_are_in_a_box_of_their_own_titled_overlaps() -> None:
    panel = _new_panel(_overlapping_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(25)

    assert panel._overlap_box.text == mod.OVERLAP_TITLE
    assert mod.OVERLAP_TITLE == "Overlaps"
    assert panel._overlap_grid in panel._overlap_box.children
    assert all(cell in panel._overlap_grid.children for cell in panel._overlap_cells[0])


def test_each_module_in_the_way_gets_a_row_of_its_own() -> None:
    # Run together on one line, two neighbors ran off the right edge of the window; a row
    # each also lines their columns up the way the assigned box lines up its own.
    panel = _new_panel(_overlapping_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(25)

    assert _overlaps(panel) == ["ACC: BPC2 TMCC IDs 26 - 33", "ACC: ASC2 TMCC IDs 30 - 37"]
    # The title carries the word, so no row repeats it.
    assert not any("Overlaps" in row for row in _overlaps(panel))
    assert [cell.grid for cell in panel._overlap_cells[0]] == [[0, 0], [1, 0], [2, 0]]
    assert panel._overlap_cells[0][0].text_bold is True


def test_the_overlaps_box_comes_and_goes_with_what_is_in_the_way() -> None:
    # Nothing in the way is an answer the title alone cannot give, so the box leaves the
    # page rather than standing empty -- and a row left over from a busier block is hidden
    # rather than blanked, which would keep the box the height of its fullest moment.
    panel = _new_panel(_overlapping_store())
    panel._on_device_selected("asc2")

    panel._set_base_id(25)
    assert panel._overlap_box.visible is True
    assert len(_overlaps(panel)) == 2

    panel._set_base_id(30)  # 30-37 is the ASC2's own block, and the BPC2 ends at 33
    assert _overlaps(panel) == ["ACC: BPC2 TMCC IDs 26 - 33"]
    assert panel._overlap_cells[1][1].visible is False

    panel._set_base_id(50)
    assert panel._overlap_box.visible is False
    assert _overlaps(panel) == []

    panel._set_base_id(25)
    assert panel._overlap_box.visible is True
    assert len(_overlaps(panel)) == 2


def _amc2_and_bpc2_at_1_store() -> FakeStore:
    """The reported layout: an AMC2 and a BPC2 both answering to ACC 1."""
    return FakeStore(
        {
            CommandScope.ACC: [
                FakeState(1, "is_bpc2", mode=3, num_ids=1),
                FakeState(1, "is_amc2", num_ids=1),
            ]
        }
    )


class FakePdiConfig:
    """One module's own PDI CONFIG packet, as PdiDeviceConfig presents it."""

    def __init__(self, tmcc_id: int, scope: CommandScope, mode: int | None = None) -> None:
        self.tmcc_id = tmcc_id
        self.scope = scope
        if mode is not None:
            # Only ASC2, BPC2 and STM2 configs carry a mode; an AMC2's does not.
            self.mode = mode


class FakePdiStore:
    """Stand-in for PdiStateStore: one entry per module type per TMCC ID."""

    def __init__(self, configs: dict[Any, list[FakePdiConfig]]) -> None:
        self._configs = configs

    def keys(self) -> list[Any]:
        return list(self._configs.keys())

    def get_all(self, device: Any) -> list[FakePdiConfig]:
        return self._configs.get(device, [])


def _with_pdi_store(monkeypatch, configs: dict[Any, list[FakePdiConfig]]) -> None:
    """Stand a PDI device store behind the panel, as a synchronized process has."""
    from src.pytrain.gui.controller import lcs_id_map

    store = FakePdiStore(configs)
    monkeypatch.setattr(lcs_id_map, "_pdi_store", lambda pdi_store=None: store, raising=True)


def _shared_acc_1_record() -> FakeStore:
    """
    One accessory record at ACC 1, as the real store keeps it.

    A component state is keyed by scope and address alone, so the AMC2 and the BPC2 both
    answering to ACC 1 share this one record, and its mode and num_ids belong to whichever
    of them reported last.
    """
    return FakeStore({CommandScope.ACC: [FakeState(1, "is_bpc2", mode=3, num_ids=1)]})


def test_the_assigned_box_names_every_module_the_pdi_bus_reported(monkeypatch) -> None:
    # The reported layout: a BPC2 in its eight-ID accessory mode and an AMC2, both on ACC 1.
    _with_pdi_store(
        monkeypatch,
        {
            PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2)],
            PdiDevice.AMC2: [FakePdiConfig(1, CommandScope.ACC)],
        },
    )
    panel = _new_panel(_shared_acc_1_record())
    panel._on_device_selected("asc2")  # accessory mode: the same remote key as both
    panel._set_base_id(1)

    assert _assigned(panel) == ["ACC: BPC2 TMCC IDs 1 - 8", "ACC: AMC2 TMCC ID 1"]


def test_the_shared_record_alone_could_not_say_that(monkeypatch) -> None:
    # Why the PDI store is read first: from the record they share, the AMC2 is invisible and
    # the BPC2 claims the single ID that record happens to be carrying.
    from src.pytrain.gui.controller import lcs_id_map

    monkeypatch.setattr(lcs_id_map, "_pdi_store", lambda pdi_store=None: None, raising=True)
    panel = _new_panel(_shared_acc_1_record())
    panel._on_device_selected("asc2")
    panel._set_base_id(1)

    assert _assigned(panel) == ["ACC: BPC2 TMCC ID 1"]


def test_an_id_inside_the_true_block_is_reported_against_that_block(monkeypatch) -> None:
    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2)]})
    panel = _new_panel(_shared_acc_1_record())
    panel._on_device_selected("asc2")
    panel._set_base_id(5)

    # The module's real range, from its own CONFIG packet, which is the whole point of
    # reading the PDI store first: the shared record would have said one ID.
    assert _assigned(panel) == ["ACC: BPC2 TMCC IDs 1 - 8"]
    assert panel._goto_btn.text == "Go to 1"


def test_every_module_on_the_id_gets_a_row_of_its_own() -> None:
    # Naming only the first would tell the operator half the truth about the address.
    panel = _new_panel(_amc2_and_bpc2_at_1_store())
    panel._on_device_selected("asc2")  # accessory mode: the same remote key as both
    panel._set_base_id(1)

    assert _assigned(panel) == ["ACC: BPC2 TMCC ID 1", "ACC: AMC2 TMCC ID 1"]
    assert [cell.grid for cell in panel._assigned_cells[1]] == [[0, 1], [1, 1], [2, 1]]


def test_a_module_this_pass_cannot_program_is_named_but_never_seeded_from(monkeypatch) -> None:
    # An AMC2 is in the registry to be recognized, not to be configured: it is reported,
    # it is not offered on the device page, and the panel will not open on it even where
    # opening on the module at the ID is the rule.
    _appliance(monkeypatch)
    panel = _new_panel(FakeStore({CommandScope.ACC: [FakeState(1, "is_amc2", num_ids=1)]}))
    panel.configure(CommandScope.ACC, 1, None)

    assert _assigned(panel) == ["ACC: AMC2 TMCC ID 1"]
    assert panel.device is ASC2
    assert "amc2" not in [value for _label, value in mod.LcsConfigPanel.device_options()]


def test_opening_the_panel_from_an_amc2_screen_does_not_open_it_on_the_amc2(monkeypatch) -> None:
    # Pressing LCS... with an AMC2 on screen hands the panel an AMC2 state. It has no
    # modes, so opening on it would leave the operator on a device that cannot be
    # configured -- and would ask a mode-less device for its default mode.
    _appliance(monkeypatch)
    state = FakeState(1, "is_amc2", num_ids=1)
    panel = _new_panel(FakeStore({CommandScope.ACC: [state]}))

    panel.configure(CommandScope.ACC, 1, state)  # must not raise

    assert panel.device is ASC2
    assert panel.page_index == mod.PAGE_DEVICE
    # Recognized all the same: it is what the box reports at that ID.
    assert _assigned(panel) == ["ACC: AMC2 TMCC ID 1"]
    # And the guard is not decorative: there is genuinely no mode to have opened on.
    with pytest.raises(ValueError, match="no modes"):
        panel._select_device(AMC2)


def test_the_choice_buttons_ignore_a_module_that_cannot_be_programmed() -> None:
    # Interior of an AMC2's block, if it ever reported one: there is nothing to go to and
    # nothing to take over, so neither button appears.
    store = FakeStore({CommandScope.ACC: [FakeState(1, "is_amc2", num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")
    panel._set_base_id(4)

    assert _assigned(panel) == ["ACC: AMC2 TMCC IDs 1 - 8"]
    assert panel.programmable_occupant() is None
    assert panel._goto_btn.visible is False
    assert panel._new_btn.visible is False


def test_a_row_left_over_from_a_busier_id_is_hidden_not_blanked() -> None:
    # An empty label still stands a line tall, so the box would keep the height of the
    # fullest ID it had ever shown.
    panel = _new_panel(_amc2_and_bpc2_at_1_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(1)
    assert len(_assigned(panel)) == 2

    panel._set_base_id(40)

    assert _assigned(panel) == [mod.UNASSIGNED]
    assert all(cell.visible is False for cell in panel._assigned_cells[1])
    # And the row comes back, rather than staying hidden, when the ID fills up again.
    panel._set_base_id(1)
    assert len(_assigned(panel)) == 2


#
# The two reports are colored as the warning they are
#
def test_a_module_already_at_the_id_is_reported_in_dark_red() -> None:
    # Every cell of the row, not just the module: the remote key and the block it holds are
    # as much a part of the collision as the name is.
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(9)

    assert _assigned(panel) == ["ACC: ASC2 TMCC IDs 9 - 16"]
    assert [cell.text_color for cell in panel._assigned_cells[0]] == [mod.CONFLICT_FG] * mod.ROW_COLUMNS


def test_an_address_nobody_holds_is_reported_in_dark_green() -> None:
    # The one row in either box that is not something in the way, and the only one in green.
    panel = _new_panel()

    assert _assigned(panel) == [mod.UNASSIGNED]
    assert [cell.text_color for cell in panel._assigned_cells[0]] == [mod.UNASSIGNED_FG] * mod.ROW_COLUMNS


def test_every_module_in_the_way_is_reported_in_dark_red() -> None:
    panel = _new_panel(_overlapping_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(25)

    assert len(_overlaps(panel)) == 2
    for row in panel._overlap_cells:
        assert [cell.text_color for cell in row] == [mod.CONFLICT_FG] * mod.ROW_COLUMNS


def test_the_very_same_cells_turn_green_when_the_address_frees_up() -> None:
    # The rows are grown on demand and then kept, so a cell outlives the row it last held:
    # colored where it is built rather than where it is written, the box would keep saying
    # in red that an address it now reports as free is taken.
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(9)
    cells = panel._assigned_cells[0]
    assert [cell.text_color for cell in cells] == [mod.CONFLICT_FG] * mod.ROW_COLUMNS

    panel._set_base_id(40)

    assert _assigned(panel) == [mod.UNASSIGNED]
    assert panel._assigned_cells[0] is cells
    assert [cell.text_color for cell in cells] == [mod.UNASSIGNED_FG] * mod.ROW_COLUMNS


def test_the_two_report_colors_are_dark_shades() -> None:
    # Whole lines of text at the page's body size on a light panel: a bright red reads as a
    # smear, and plain "red" is what admin_panel puts over Restart and Shutdown.
    assert (mod.CONFLICT_FG, mod.UNASSIGNED_FG) == ("#8B0000", "#006400")
    assert mod.ModuleRow(scope="", module=mod.UNASSIGNED).is_unassigned is True
    assert mod.ModuleRow(scope="ACC:", module="BPC2", ids="TMCC IDs 1 - 8").is_unassigned is False


#
# The footnote under the mode radios
#
def test_the_footnote_is_the_last_thing_inside_the_mode_box() -> None:
    # A caption on the radios above it -- what each remote key they offer is for -- so it
    # belongs inside their box, not adrift among the page's other derived lines.
    panel = _new_panel()
    box = panel._mode_box

    assert box.children[0] is panel._mode_group
    assert getattr(box.children[1], "vspace", None) == mod.MODE_NOTE_LEAD
    assert box.children[2] is panel._mode_footnote_line
    assert panel._mode_footnote_line not in panel._pages[mod.PAGE_ID].children


def test_the_footnote_is_centered_under_the_radios() -> None:
    # Centered like every other line of prose in the panel: the two lines are short and of
    # much the same length, and centered they read as a caption on the list above rather
    # than as another row of it. align is where guizero packs it -- "top", so it spans the
    # box and is centered in it -- and justify how Tk sets the lines within that.
    panel = _new_panel()
    line = panel._mode_footnote_line

    assert line.kwargs["align"] == "top"
    assert line.tk.configured["justify"] == "center"
    # Wrapped like every other line of prose in the panel.
    assert line.tk.configured["wraplength"] == panel._wrap_px


def test_the_footnote_is_held_just_off_the_last_radio() -> None:
    # Less than the gap between two radios, so the footnote reads as part of the box rather
    # than as the next thing on the page -- and a spacer widget rather than padding of the
    # line's own, which would push it off the bottom of the box as well.
    assert mod.MODE_NOTE_LEAD < mod.MODE_ROW_PAD
    assert mod.MODE_NOTE_LEAD <= 5
    assert mod.MODE_NOTE_LEAD_COMPACT < mod.MODE_NOTE_LEAD


def test_no_device_means_no_mode_footnote() -> None:
    panel = _new_panel()

    assert panel.mode_footnote == ""
    assert panel._mode_footnote_line.value == ""


@pytest.mark.parametrize(
    "device_key, expected",
    [
        # In the order the module's own radios list them, so a BPC2 reads TR first.
        ("asc2", [mod.SCOPE_USE[CommandScope.ACC], mod.SCOPE_USE[CommandScope.SWITCH]]),
        ("bpc2", [mod.SCOPE_USE[CommandScope.TRAIN], mod.SCOPE_USE[CommandScope.ACC]]),
        ("stm2", [mod.SCOPE_USE[CommandScope.SWITCH]]),
        ("sensor_track", [mod.SCOPE_USE[CommandScope.ACC]]),
    ],
)
def test_the_footnote_covers_every_key_the_module_offers_and_no_other(device_key: str, expected: list[str]) -> None:
    panel = _new_panel()
    panel._on_device_selected(device_key)

    assert panel.mode_footnote.split("\n") == expected
    assert panel._mode_footnote_line.value == panel.mode_footnote


def test_the_footnote_says_what_each_key_is_for() -> None:
    assert mod.SCOPE_USE[CommandScope.ACC] == "ACC: Use for lighting and operating accessories"
    assert mod.SCOPE_USE[CommandScope.SWITCH] == "SW: Use for Switches/Turnouts"
    assert mod.SCOPE_USE[CommandScope.TRAIN].startswith("TR: ")


def test_the_footnote_follows_the_device_the_operator_switches_to() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    assert mod.SCOPE_USE[CommandScope.TRAIN] in panel._mode_footnote_line.value

    panel._on_device_selected("stm2")
    assert panel._mode_footnote_line.value == mod.SCOPE_USE[CommandScope.SWITCH]
    assert mod.SCOPE_USE[CommandScope.TRAIN] not in panel._mode_footnote_line.value
