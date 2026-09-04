from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

import src.pytrain.gui.components.scroll_box as scroll_mod
import src.pytrain.gui.controller.lcs_config_panel as mod
import src.pytrain.gui.controller.lcs_device_registry as reg
import src.pytrain.gui.controller.popup_manager as pm
from src.pytrain.gui.components.checkbox_group import CheckBoxGroup as RealCheckBoxGroup
from src.pytrain.gui.controller.lcs_device_registry import AMC2, ASC2, BPC2, SENSOR_TRACK, STM2, LcsOption
from src.pytrain.gui.controller.lcs_id_map import TRAIN_LABEL
from src.pytrain.pdi.amc2_req import AccessType, Amc2Motor, Direction, OutputType
from src.pytrain.pdi.bpc2_req import Bpc2Action
from src.pytrain.pdi.constants import Amc2Action
from src.pytrain.pdi.irda_req import IrdaAction, IrdaSequence
from src.pytrain.pdi.pdi_device import PdiDevice
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
)


class _DummyTk:
    def __init__(self) -> None:
        # What the widget was asked to bind, and whether it asked to be added to whatever was
        # bound to that sequence already -- which is how the press-to-edit tests read the
        # wiring without a real Tk event loop.
        self.binds: list[tuple[str, Any, str | None]] = []
        # And what it was configured with, which is how the wrapping tests read a Tk option
        # that has no guizero equivalent.
        self.configured: dict[str, Any] = {}
        # Every such call rather than only what it left behind: the space beside a page's key
        # is re-sized on a Tk option, and one re-sized for nothing is a layout pass spent for
        # nothing. See LcsConfigPanel._fit_key_gutter.
        self.configs: list[dict[str, Any]] = []
        # What the widget would ask to be drawn at; see winfo_reqheight.
        self.reqheight = 0
        # And what it was placed in its grid with, which is how the listing's tests read an
        # alignment guizero has no way of asking for; see LcsConfigPanel._stick_inventory_cells.
        self.gridded: dict[str, Any] = {}
        # And what it was packed with, which is how the listing's tests read the white space
        # between the blocks of one cell -- pack padding being no more a guizero property
        # than the two above; see GroupedCell._space_blocks.
        self.packed: dict[str, Any] = {}
        # And what its grid columns were configured with, which is how a stretched box's
        # width floor is read: guizero has no way of asking for one. Keyed by column, since
        # the panel's stretched boxes all stand in column 0 of a container of their own; see
        # LcsConfigPanel._lay_out_titled_boxes and _stretch_manual_config.
        self.columns: dict[int, dict[str, Any]] = {}

    def config(self, **kwargs: Any) -> None:
        self.configs.append(dict(kwargs))
        self.configured.update(kwargs)

    def configure(self, **kwargs: Any) -> None:
        self.configs.append(dict(kwargs))
        self.configured.update(kwargs)

    def grid_configure(self, **kwargs: Any) -> None:
        self.gridded.update(kwargs)

    def pack_configure(self, **kwargs: Any) -> None:
        self.packed.update(kwargs)

    def grid_columnconfigure(self, col: int, **kwargs: Any) -> None:
        self.columns.setdefault(col, {}).update(kwargs)

    def bind(self, event: str, func, add: str | None = None) -> None:
        self.binds.append((event, func, add))

    @staticmethod
    def update_idletasks() -> None:
        return

    @staticmethod
    def winfo_reqwidth() -> int:
        return 160

    def winfo_reqheight(self) -> int:
        """How tall the widget asks to be. Nothing, for a widget no screen has drawn.

        Settable, because it is the one thing the panel takes off the font rather than from a
        constant of its own: the height of one of its keys, which is what the white space
        around the first page's row of them is measured against. A fake answers 0 -- there is
        no screen here, and 0 is what the panel is written to fall back from; see
        LcsConfigPanel._nav_key_px.
        """
        return self.reqheight

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
        # The two hands guizero's own widgets answer for. Both start off, as a widget built
        # with neither does: the status line is the one the panel sets them on, and it sets
        # both on every write; see LcsConfigPanel._show_status.
        self.text_bold = False
        self.text_italic = False
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
        # Whether the editor is open over the page, which is what the pad reads to know the
        # page has been left for the moment; see LcsConfigPanel._pad_target.
        self.is_editing = False

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
        self._cursor: str | None = None

    @property
    def row_values(self) -> tuple[str, ...]:
        """The rows' values as strings, which is what the real group answers with."""
        return tuple(str(option[1] if isinstance(option, (list, tuple)) else option) for option in self.options)

    @property
    def cursor(self) -> str | None:
        """Where the pad is pointing, as against value, which is what is chosen."""
        return self._cursor

    @cursor.setter
    def cursor(self, value: Any) -> None:
        # A value the rows do not hold clears the tint rather than raising, and it is held as
        # the string the rows are keyed by -- both as the real component has it.
        target = None if value is None else str(value)
        self._cursor = target if target in self.row_values else None

    @staticmethod
    def decorate_checkbox(widget: Any, size: int, width: Any = None, **kwargs: Any) -> None:
        """Record what the real component would paint a lone checkbox with.

        The classmethod the Admin panel and the catalog's sort boxes already reach for; it
        draws the indicator, so what it is asked for is the whole of the assertion.
        """
        widget.decoration = dict(size=size, width=width, **kwargs)

    # What a row spends before its text is arithmetic, and it is the component's arithmetic:
    # taken from the real class so a test cannot come to answer it differently than the panel
    # will be answered on a screen.
    row_chrome_for = RealCheckBoxGroup.row_chrome_for

    @staticmethod
    def fit_row_size(master: Any, texts: Any, width: int, ceiling: int, floor: int = None, style: str = "radio") -> int:
        """The size the caller asked for, which is what the real one answers unmeasured.

        Fitting a size means measuring a font on the screen the rows are drawn on, and there
        is no screen here. The real component answers with the ceiling wherever it cannot
        measure -- see CheckBoxGroup.fit_row_size -- so these tests see the size the panel
        asks for, and what it asks for is the thing they are about.
        """
        return ceiling

    def clear(self) -> None:
        self.options = []
        # A rebuild destroys the rows the tint was armed over, and clearing empties the list
        # outright, so nothing is left for the component's re-arm to put it back on; see
        # CheckBoxGroup._rearm_cursor.
        self._cursor = None

    def append(self, option: list[Any]) -> None:
        """Append a [text, value] list, matching guizero's ButtonGroup.append() signature."""
        if not isinstance(option, list) or len(option) != 2:
            raise TypeError(f"append() expects a [text, value] list, got {option!r}")
        self.options.append(tuple(option))

    @property
    def cursor_row(self) -> Any:
        """The row the tint is on, which is what a caller brings into view.

        A stand-in for it, since these rows are not drawn: the value itself, which is enough
        to say *which* row the window was asked to show.
        """
        return self._cursor


class DummyScrollBox:
    """The window the pages are drawn in, without a screen to measure.

    Records what the panel asked of it -- the budgets it was fitted to, the page turns that
    sent it back to the top, the rows it was told to bring into view -- and hands out an
    ordinary DummyBox as the container the pages are built into, so every existing test that
    walks the pages' children still finds what it did before.
    """

    def __init__(self, master: Any, *, width: int, align: str = "top", bar_px: int = None) -> None:
        self.width = width
        self.align = align
        # What the panel asked the bar be drawn at, which is a question about the screen
        # rather than about the window; see mod.scroll_bar_px.
        self.bar_px = bar_px
        self.viewport = DummyBox(master)
        self.content = DummyBox(self.viewport)
        self.fits: list[int | None] = []
        self.shown: list[Any] = []
        # Every pixel the pad has asked the page to move by, in order; see pad_scroll.
        self.scrolled: list[int] = []
        self.bindings = 0
        self.on_resize: Any = None
        self.watching: list[Any] = []
        self.view_px = 0
        self.offset = 0
        self.scrollable = False
        # How much of the window the real one is keeping clear of the page as things stand:
        # the bar's width while a bar is drawn in it and nothing while none is. Nothing here,
        # a window that has never been fitted having never drawn one; see ScrollBox.gutter_px
        # and what the panel does with it in _fit_key_gutter.
        self.gutter_px = 0
        # In the order they were asked for, since some of the rules are about the order: a
        # window scrolled before it is re-fitted is a window that may then be looking below
        # the end of a shorter page.
        self.calls: list[str] = []

    @property
    def resets(self) -> int:
        return self.calls.count("reset")

    def fit(self, budget: int | None = None) -> int:
        self.fits.append(budget)
        self.calls.append("fit")
        return self.view_px

    def reset(self) -> bool:
        self.calls.append("reset")
        return False

    def hint(self) -> bool:
        self.calls.append("hint")
        return self.scrollable

    def scroll_by(self, pixels: int) -> bool:
        self.scrolled.append(int(pixels))
        return self.scrollable

    def show_widget(self, widget: Any) -> bool:
        self.shown.append(widget)
        return self.scrollable

    def bind_scrolling(self) -> None:
        self.bindings += 1

    def on_content_resized(self, refit: Any, *also: Any) -> None:
        self.on_resize = refit
        self.watching = list(also)


#
# What the panel says, composed rather than spelled out
#
# Every expectation about wording below is built from whatever owns the words: the registry
# for a module, a mode, an option or a press, and the panel for the sentences it holds them
# in. A term reworded in either file reaches these tests without one of them being retyped,
# which is the point of composing them -- the suite is about what the panel puts where, not
# about how the words themselves read.
#
def _row_cells(scope: CommandScope, module: str, base_id: int, ports: int = 1) -> tuple[str, str, str]:
    """The three cells of one Currently Assigned or Overlaps row, as the panel grids them.

    The remote key with its colon, the module, and the spelling of the block it holds all
    come from the panel's own ModuleRow and the registry's tmcc_id_text, so a row is
    described here by what stands in it -- which key, which module, which addresses -- and
    never by how it reads.
    """
    return mod.ModuleRow(
        scope=f"{mod.SCOPE_LABEL[scope]}:",
        module=module,
        ids=reg.tmcc_id_text(base_id, base_id + ports - 1),
    ).cells


def _row(scope: CommandScope, module: str, base_id: int, ports: int = 1) -> str:
    """
    One of those rows as the single line the box reads as, joined as the row joins its cells.
    """
    return mod.ModuleRow(*_row_cells(scope, module, base_id, ports)).text


def _mode_options(device: reg.LcsDevice, base_id: int) -> list[tuple[str, str]]:
    """The Mode radios: every enabled mode named with the block it would claim at base_id.

    Each row is the mode's own ids_label against its key, in the order the registry lists the
    module's modes, which is what the group is filled from. This says no more than the panel's
    own mode_options does, so wherever a test compares the rows with it, it asks something of
    them besides; see the assertions beside each use.
    """
    return [(mode.ids_label(base_id), mode.key) for mode in reg.enabled_modes(device)]


def _press_lines(mode: reg.LcsMode, base_id: int, options: dict[str, Any] | None = None) -> list[str]:
    """The review page's numbered lines for a mode's presses.

    All that is spelled out here is the builder's numbering -- "N. " ahead of the press and
    its note in parentheses behind it -- because that format is what these tests are about;
    every word comes from the presses themselves. A mode whose press takes its digit from an
    option has to be given that option, exactly as the builder is. See
    lcs_sequence_builder._press_text.
    """
    settings = options or {}
    lines: list[str] = []
    for number, press in enumerate((p for p in mode.presses if p.is_included(settings)), start=1):
        label = press.resolved_label(settings).format(id=base_id, digit=press.digit(settings))
        lines.append(f"{number}. {label} ({press.note})" if press.note else f"{number}. {label}")
    return lines


def _says_with_id(button: Any, base_id: int) -> bool:
    """Whether one of the choice buttons reads as the panel built it, with an ID worked in.

    The panel words these two twice: once with the wording alone as it builds them, and again
    with an address in place when the banner speaks -- one of them ending with it, the other
    holding it mid-phrase. The words are read back off the button's own build-time text, so
    all this asks is that the ID has been dropped in and nothing else has changed.
    """
    words = str(button.text).split()
    if str(base_id) not in words:
        return False
    return [word for word in words if word != str(base_id)] == str(button.kwargs["text"]).split()


# The words a block of addresses is named with, taken from the registry's own spelling of one
# with the address dropped off it -- which is the term the ID page's heading is built on too.
# What the "said once" test looks for among that page's lines.
_ID_TERM = reg.tmcc_id_text(1).rsplit(" ", 1)[0]


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
        loco_rl: Any = None,
        loco_lr: Any = None,
        motors: tuple[Amc2Motor, ...] = (),
    ) -> None:
        self.address = address
        self.tmcc_id = address
        self.mode = mode
        self.num_ids = num_ids
        self.sequence = sequence
        # A Sensor Track's engine ID filters, which only its read-back line reads: 255 or
        # nothing at all means any engine, as IrdaState has it.
        self.loco_rl = loco_rl
        self.loco_lr = loco_lr
        self._parent = parent
        # An AMC2's motors, which the accessory state carries in the very shape its own
        # CONFIG packet does -- so the panel reads the module and the state it left behind
        # by one path. A state that has heard nothing from the module carries none.
        for i, motor in enumerate(motors, start=1):
            setattr(self, f"motor{i}", motor)
        # is_amc2 among them: a state that does not carry the flag at all cannot even be
        # recognized, which was the original bug.
        for flag in ("is_asc2", "is_bpc2", "is_stm2", "is_sensor_track", "is_amc2"):
            setattr(self, flag, flag == device_flag)

    @property
    def parent(self) -> Any:
        return self._parent

    @property
    def port(self) -> int:
        return self.address - self._parent.address + 1 if self._parent else 1


class FakeTrain:
    """Mirrors the parts of a TrainState the panel reads of a train.

    None of the registry's module flags, which is what makes it a train and not a module:
    a BPC2 addressed as a TR device leaves a state on these very keys, and that one
    answers is_bpc2.

    The road name and number are carried apart and everything else derived from them the
    way ComponentState derives it, so what a row can be given to name is what the layout
    can really report.
    """

    def __init__(self, address: int, road_name: str = None, road_number: str = None) -> None:
        self.address = address
        self.tmcc_id = address
        self.moniker = CommandScope.TRAIN.title
        self.is_road_name = bool(road_name)
        self.is_road_number = bool(road_number)
        self.is_name = self.is_road_name or self.is_road_number
        # Both fall back, as the real properties do: to the moniker, and to the address.
        self.road_name = road_name or self.moniker
        self.road_number = road_number or str(address)
        if self.is_name:
            # As ComponentState assembles it, which drops the number with the name: a train
            # carrying a number and no road name is called "NA" and nothing else.
            self.name = road_name + (f" #{road_number}" if road_number else "") if road_name else "NA"
        else:
            # Unnamed, the real state's own name property still answers with the address
            # worked into it -- "Train 3" -- so the fake does too, and the panel has to be
            # the thing that declines to spell the address twice.
            self.name = f"{self.moniker} {address}"


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
            s_13=13,
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
            # Varargs, as the host's own cache is: a caller with two widgets to keep -- a
            # row and the spacer on it -- hands over both in one breath.
            cache=lambda *_widgets: None,
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

    @staticmethod
    def queue_message(message: Any, *args: Any) -> None:
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
    monkeypatch.setattr(mod, "ScrollBox", DummyScrollBox, raising=True)
    monkeypatch.setattr(mod, "StateWatcher", lambda _state, _action: None, raising=True)
    monkeypatch.setattr(mod, "style_footer_button", lambda _host, _btn: None, raising=True)
    # Pinned so the ID field's editor does not depend on the machine running the tests;
    # the platform-specific cases patch it themselves. Patched on the panel module, which
    # is only possible because is_linux is imported there at module scope rather than
    # reached for inside touch_only_editing.
    monkeypatch.setattr(mod, "is_linux", lambda: False, raising=True)
    # And the pad for the same reason: whether the lists carry its highlight follows the
    # platform the install recorded, which is a fact about the machine the suite is run on --
    # a Deck would otherwise answer these differently than a desk. See pad_driven.
    monkeypatch.setattr(mod, "is_steam_deck", lambda: False, raising=True)


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


def _first_offered() -> reg.LcsDevice:
    """The module the device page's top row names, which is what the panel falls back to.

    Read off the page rather than named here, because which module that is moves with the
    registry: the rows are sorted by name, so it is the AMC2 today and was the ASC2 until
    the AMC2 became programmable. What the fallback tests are about is that the panel opens
    on the row an operator sees selected, whichever module that is.
    """
    return reg.device_for_key(mod.LcsConfigPanel.device_options()[0][1])


def _recognized_only(monkeypatch) -> reg.LcsDevice:
    """Stand a module the panel can name but not program in the registry, and return it.

    Every module in the registry can be programmed today, the AMC2 having been the last one
    that could not. The rules about such a module still hold and still matter -- it is the
    whole reason the configurable flag exists, and the next module met on a layout before
    its manual has been read will land in that state -- so they are pinned against a
    stand-in: the AMC2 with its modes taken away, which is exactly how it was declared
    before this pass. It replaces the real AMC2 rather than joining it, so the state it
    answers to names one module and not two.
    """
    device = replace(AMC2, configurable=False, modes=(), options=())
    monkeypatch.setattr(
        reg,
        "LCS_DEVICES",
        tuple(device if other is AMC2 else other for other in reg.LCS_DEVICES),
        raising=True,
    )
    return device


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
    assert keys == [AMC2.key, ASC2.key, BPC2.key, SENSOR_TRACK.key, STM2.key]


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

    labels = [label for label, _key in panel._mode_group.options]
    assert labels == [label for label, _key in _mode_options(ASC2, 12)]
    # And each row really does name a block, at the ID on the page: the addresses the mode
    # would set aside stand in its own row, and no two rows read alike.
    for label, key in panel._mode_group.options:
        mode = ASC2.mode(key)
        assert reg.tmcc_id_text(12, 12 + mode.ports - 1) in label
    assert len(set(labels)) == len(labels)


def test_stepping_the_id_relabels_every_mode_row() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._on_mode_selected("acc_1")
    panel._set_base_id(12)

    panel.step_up()

    labels = [label for label, _key in panel._mode_group.options]
    assert labels == [label for label, _key in _mode_options(ASC2, 13)]
    # Every row moved with the ID: the base stepped to stands in each of them, and the one
    # stepped off in none.
    assert all("13" in label for label in labels)
    assert not any("12" in label for label in labels)
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

    acc_8 = ASC2.mode("acc_8")
    assert panel._mode_group.options[0] == _mode_options(ASC2, 95)[0]
    # The block named is the one the mode can hold, from as high as it fits -- not the block
    # it would claim from the ID on the page, which runs off the end of the addresses.
    assert reg.tmcc_id_text(acc_8.max_base, reg.MAX_TMCC_ID) in panel._mode_group.options[0][0]

    panel._on_mode_selected("acc_8")
    assert panel.base_id == 91
    assert panel._mode_group.options[0] == _mode_options(ASC2, 95)[0]


def test_the_page_says_the_selected_block_once() -> None:
    # The line that used to stand below the boxes -- naming the block of the selected mode a
    # second time, e.g. "Uses TMCC IDs 12 - 19" -- repeated the row the operator had just
    # chosen, and is gone with the mode rows naming their own.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(12)

    lines = [
        child.value for child in panel._pages[mod.PAGE_ID].children if isinstance(getattr(child, "value", None), str)
    ]
    assert not [line for line in lines if _ID_TERM in line and line != panel.id_heading_text]


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

    device = _first_offered()
    assert panel.base_id == 1
    assert panel.device is device
    assert panel.mode is device.default_mode
    assert panel._device_group.value == device.key
    assert panel.page_index == mod.PAGE_DEVICE


def test_the_default_device_is_the_first_one_offered() -> None:
    # The row the device page opens on is the row it draws first, whichever module the
    # registry's name order puts there -- so the panel never opens with the dot on a row
    # the operator has to scroll to.
    assert mod.LcsConfigPanel(_new_host()).default_device is _first_offered()


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

    assert panel.device is _first_offered()
    assert panel.base_id == 12
    # Still told what is out there, which is the assigned box's whole job. The ASC2 is asked
    # for by name rather than left to the fallback: what this half is about is that the box
    # answers for the accessory key while a BPC2 sits on the train key, and a module whose
    # own opening mode happened to change would otherwise quietly stop asking it.
    panel._on_device_selected("asc2")
    panel._on_mode_selected("acc_8")
    assert _assigned(panel) == [mod.UNASSIGNED]
    panel._on_device_selected("bpc2")
    assert _assigned(panel) == [_row(CommandScope.TRAIN, BPC2.label, 12, 8)]


def test_an_appliance_falls_back_to_the_first_device_when_the_id_is_free(monkeypatch) -> None:
    _appliance(monkeypatch)
    panel = _new_panel()

    panel.configure(CommandScope.ACC, 40, None)

    assert panel.device is _first_offered()
    assert panel.base_id == 40


def test_the_entered_id_is_squared_with_the_opening_modes_ceiling(monkeypatch) -> None:
    # ID 95 fits a four-port switch mode, and a one-address module, but not the ASC2's
    # eight-ID accessory mode -- so the ID the operator came in with is brought down to the
    # highest base the mode the panel opened on can be programmed at, rather than being
    # taken as typed and refused at the end.
    #
    # The ASC2 is what the panel opens on here because the screen was on one; the module it
    # falls back to has an address to spare at 95 and so would not exercise the rule at all.
    _appliance(monkeypatch)
    state = FakeState(91, "is_asc2", mode=0, num_ids=8)
    panel = _new_panel(FakeStore({CommandScope.ACC: [state]}))

    panel.configure(CommandScope.ACC, 95, state)

    assert panel.device is ASC2
    assert panel.mode.key == "acc_8"
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
    assert _assigned(panel) == [_row(CommandScope.TRAIN, BPC2.label, 12, 8)]


def test_configure_seeds_from_the_store_when_the_id_is_a_known_base(monkeypatch) -> None:
    # Which host this is has to be said: a desktop reflects nothing and would answer with
    # the module it falls back to, whatever the store holds -- so without this the test read
    # as passing while looking at the fallback rather than at the layout.
    _appliance(monkeypatch)
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

    Read out of the row widgets rather than off assigned_rows() / overlap_rows(), so the
    assertions cover what was actually written into the box -- including a row left over
    from a busier ID, which must be hidden rather than merely blanked.
    """
    lines = []
    for row in cells:
        if not row[1].visible:
            continue
        lines.append(" ".join(cell.value for cell in row if cell.value))
    return lines


# The row widgets are the panel's own, and reading them is the point of these helpers.
# noinspection PyProtectedMember
def _assigned(panel: mod.LcsConfigPanel) -> list[str]:
    return _rows(panel._assigned_cells)


# noinspection PyProtectedMember
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
    assert _assigned(panel) == [_row(CommandScope.ACC, ASC2.label, 9, 8)]
    assert panel._goto_btn.visible is True
    # Each button names an address: the base the module holds, and the ID as entered.
    assert _says_with_id(panel._goto_btn, 9)
    assert panel._new_btn.visible is True
    assert _says_with_id(panel._new_btn, 12)


def test_the_two_choices_are_drawn_as_the_panels_other_keys_are(monkeypatch) -> None:
    # Styled by their text size alone, these two were drawn flat -- two words in a rectangle,
    # on a page whose every other key wears the one shared look for the big keys of an
    # overlay: Back, Next and My Modules below the page, Configure on the page after it, the
    # Close below them all. What the look is remains the popup's to say; what is pinned here
    # is that these two are given it, and given it before their size is set, that look
    # carrying a size of its own.
    styled: list[Any] = []
    monkeypatch.setattr(mod, "style_footer_button", lambda _host, btn: styled.append(btn), raising=True)

    panel = _new_panel()

    assert styled[:2] == [panel._goto_btn, panel._new_btn]


def test_the_two_choices_are_read_at_a_size_worth_pressing() -> None:
    # They were the panel's fine print, on the page where the one decision that cannot be
    # undone by pressing Back is taken: whether the module already answering to this address
    # is the one being programmed. Four sizes up.
    panel = _new_panel()
    host = panel.gui

    assert panel._choice_key_size == host.s_16
    assert [btn.text_size for btn in (panel._goto_btn, panel._new_btn)] == [host.s_16] * 2
    # Above the boxes standing over them, which is where the fact they are answering is
    # reported -- what is already at the address, and what the chosen block would run into.
    assert panel._choice_key_size > panel._titled_text_size
    # And below the size the shared look draws a key at, which is the one part of that look
    # these two cannot have: they say an address as well as a verb and both are on screen
    # whenever either is, and at that size the pair comes to 443px of the Pi's 456px page
    # before any white space is put between them -- measured in the keys' own font with the
    # look's border and inner padding. See _choice_key_size.
    assert panel._choice_key_size < host.s_20


def test_white_space_stands_between_the_two_choices() -> None:
    # Packed with none at all, they were drawn edge to edge: one wide rectangle with two
    # verbs in it, which is what a single key with a long label looks like. Half a footer
    # button's own band either side of each, which is 24px between the two and 12px either
    # side of the pair -- a 415px row of the Pi's 456px page at the size they are now set in.
    # See CHOICE_KEY_PAD.
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(12)
    assert (panel._goto_btn.visible, panel._new_btn.visible) == (True, True)

    for btn in (panel._goto_btn, panel._new_btn):
        assert btn.tk.packed["padx"] == mod.CHOICE_KEY_PAD > 0
        # Recorded as well as applied, since what a replay puts back is what was recorded;
        # see the test below and repad_footer_button.
        assert getattr(btn, pm._FOOTER_PACK_ATTR)["padx"] == mod.CHOICE_KEY_PAD


def test_the_white_space_between_the_two_choices_survives_them_being_shown(monkeypatch) -> None:
    # guizero rebuilds a container's pack options from scratch whenever anything in it is
    # shown or hidden and keeps only side and fill, so the gap between these two keys is
    # discarded by the very act of putting them on screen -- and being put on screen is the
    # only thing that ever happens to them. Replayed once, after both, exactly as the row of
    # keys below the page is.
    replayed: list[tuple[Any, list[str]]] = []
    monkeypatch.setattr(
        mod,
        "restore_footer_packing",
        lambda row: replayed.append((row, [child.text for child in row.children if child.visible])),
        raising=True,
    )
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")

    panel._set_base_id(12)

    choices = [texts for row, texts in replayed if row is panel._choice_row]
    # Both of them showing by the time the replay runs: one call after the pair rather than
    # one apiece, the second key's show() having discarded whatever a replay after the first
    # put back.
    assert choices[-1] == ["Go to 9", "Configure 12 as new"]

    panel._set_base_id(40)

    # And nothing to put back where nothing is in the way: pack_configure *manages* a widget
    # pack has forgotten, so replaying a hidden key's padding would put it back on the page
    # at the end of the row. The replay passes a hidden key over; see restore_footer_packing.
    assert [texts for row, texts in replayed if row is panel._choice_row][-1] == []
    assert (panel._goto_btn.visible, panel._new_btn.visible) == (False, False)


def test_go_to_base_retargets_and_pre_fills() -> None:
    # A BPC2 in accessory mode holds ACC 9-16, and the operator arrives on ACC 12 meaning
    # to program an ASC2 there: same remote key, so the module really is in the way.
    store = FakeStore({CommandScope.ACC: [FakeState(9, "is_bpc2", mode=2, num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")
    panel._set_base_id(12)
    assert _assigned(panel) == [_row(CommandScope.ACC, BPC2.label, 9, 8)]

    panel.go_to_owning_base()

    assert panel.base_id == 9
    assert panel.device is BPC2
    assert panel.mode.key == "acc_8"
    assert panel._device_group.value == "bpc2"
    assert _assigned(panel) == [_row(CommandScope.ACC, BPC2.label, 9, 8)]


def test_go_to_base_ignores_a_module_on_another_remote_key() -> None:
    # The ASC2 at ACC 9-16 is nothing to a BPC2 being programmed at TR 12, so there is
    # nowhere to go and the panel stays exactly where the operator left it.
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("bpc2")
    panel._on_mode_selected("tr_8")  # the key the ASC2 is not on, said rather than assumed
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
    # box's title carries the word for what these rows are, so no row repeats it.
    assert [row.text for row in panel.overlap_rows()] == [_row(CommandScope.SWITCH, STM2.label, 28, 8)]
    assert _overlaps(panel) == [_row(CommandScope.SWITCH, STM2.label, 28, 8)]
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

    assert _overlaps(panel) == [_row(CommandScope.SWITCH, ASC2.label, 25, 4)]


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

    assert _assigned(panel) == [_row(CommandScope.SWITCH, STM2.label, 1, 16)]
    assert panel._goto_btn.visible is False
    assert panel._new_btn.visible is False


def test_the_same_id_reports_a_different_module_for_a_different_key() -> None:
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())

    # An ASC2 in its accessory mode shares the BPC2's key, and sees it.
    panel._on_device_selected("asc2")
    panel._set_base_id(1)
    assert panel.scope == CommandScope.ACC
    assert _assigned(panel) == [_row(CommandScope.ACC, BPC2.label, 1)]

    # A BPC2 in its track mode shares neither, so ID 1 really is free.
    panel._on_device_selected("bpc2")
    panel._on_mode_selected("tr_8")
    assert panel.scope == CommandScope.TRAIN
    assert _assigned(panel) == [mod.UNASSIGNED]


def test_switching_an_asc2_between_keys_changes_what_is_in_its_way() -> None:
    # The ASC2 is the one module that can be either, so it is the proof that the box
    # follows the mode radios and not merely the device.
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(1)
    assert _assigned(panel) == [_row(CommandScope.ACC, BPC2.label, 1)]

    panel._on_mode_selected("sw_momentary")

    assert panel.scope == CommandScope.SWITCH
    assert _assigned(panel) == [_row(CommandScope.SWITCH, STM2.label, 1, 16)]


def test_with_no_device_chosen_every_module_still_counts() -> None:
    # Nothing has been picked, so there is no key to filter by and no reason to hide
    # anything: the panel has not yet been told what it is looking at, and both modules
    # sitting on "1" get a row of their own.
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())
    panel._set_base_id(1)

    assert panel.scope is None
    assert _assigned(panel) == [
        _row(CommandScope.ACC, BPC2.label, 1),
        _row(CommandScope.SWITCH, STM2.label, 1, 16),
    ]


def test_configure_prefers_a_module_on_the_screens_own_key(monkeypatch) -> None:
    # The LCS... key pressed from the switch screen means switch IDs, so the module the
    # panel seeds itself from is the switch one, even though an accessory shares the number.
    _appliance(monkeypatch)
    panel = _new_panel(_stm2_at_1_and_bpc2_at_1_store())

    panel.configure(CommandScope.SWITCH, 1, None)
    assert panel.device is STM2

    panel.configure(CommandScope.ACC, 1, None)
    assert panel.device is BPC2
    # On the row it can be reprogrammed as, not the one it is running in: this BPC2 reports
    # one of the single-ID modes its own manual reserves, and no radio row is offered for
    # one. Seeded onto it, the mode radios would show nothing selected and Configure would
    # send the opening SET press and nothing after it. The same rule the panel already
    # applied when re-reading the mode at an address now holds when it first opens; see
    # _seed_mode_from_layout.
    assert panel.mode.key == "acc_8"
    assert BPC2.mode("acc_1").enabled is False


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
    assert panel._mode_group.options == _mode_options(SENSOR_TRACK, 3)
    label = panel._mode_group.options[0][0]
    assert reg.tmcc_id_text(3) in label
    assert all(option.label not in label for option in SENSOR_TRACK.options)


#
# The trains, which share the TR keys with a module addressed as one
#
# A road name and number as the base reports them, and the name they come to -- so a named
# train is told apart from the word for an unnamed one, and from the module labels beside it
# in the same box.
_A_ROAD, _A_NUMBER = "PRR", "8523"
_A_ROAD_NAME = f"{_A_ROAD} #{_A_NUMBER}"


def _trains_at_1_and_3_store() -> FakeStore:
    """Two trains: one nobody has named, and one the base has told us the road of."""
    return FakeStore({CommandScope.TRAIN: [FakeTrain(1), FakeTrain(3, road_name=_A_ROAD, road_number=_A_NUMBER)]})


def _bpc2_as(mode_key: str, base_id: int, store: FakeStore = None) -> Any:
    """A BPC2 aimed at base_id in one of its two addressing modes.

    The mode is said rather than taken from the row the page opens on, because which of the
    two keys the module is on is the whole of what these tests are about.
    """
    panel = _new_panel(store or _trains_at_1_and_3_store())
    panel._on_device_selected("bpc2")
    panel._on_mode_selected(mode_key)
    panel._set_base_id(base_id)
    return panel


def test_a_train_holds_a_track_address_against_the_module_being_programmed() -> None:
    # The report. A BPC2 addressed as a TR device takes its block out of the numbers the
    # trains themselves answer to, so the train at the address entered is what is currently
    # assigned to it, and a train further up the block is something it overlaps. Neither box
    # had anything to say about a train before.
    panel = _bpc2_as("tr_8", 1)

    assert panel.scope == CommandScope.TRAIN
    assert _assigned(panel) == [_row(CommandScope.TRAIN, TRAIN_LABEL, 1)]
    assert _overlaps(panel) == [_row(CommandScope.TRAIN, _A_ROAD_NAME, 3)]
    # The box is on the page at all, which for a module in the way is the same rule: a train
    # in the block is a reason to show it, and there was none before this.
    assert panel._overlap_box.visible is True


def test_a_train_is_named_for_its_road_and_for_what_it_is_otherwise() -> None:
    # A row reading "Train 3" would spell the address twice, once in each of two columns,
    # and a row naming nothing at all would read as an address holding an empty string.
    named = _bpc2_as("tr_8", 3)
    unnamed = _bpc2_as("tr_8", 1)

    assert _assigned(named) == [_row(CommandScope.TRAIN, _A_ROAD_NAME, 3)]
    assert _assigned(unnamed) == [_row(CommandScope.TRAIN, TRAIN_LABEL, 1)]


def test_a_train_row_is_colored_as_the_warning_it_is() -> None:
    # Every row either box can show is something in the way of the address being entered,
    # and a train is no exception: the one row in green is the one saying nobody holds it.
    panel = _bpc2_as("tr_8", 1)

    assert [cell.text_color for cell in panel._assigned_cells[0]] == [mod.CONFLICT_FG] * mod.ROW_COLUMNS


def test_the_trains_are_nothing_to_a_module_on_the_accessory_keys() -> None:
    # ACC 1 and TR 1 are two different addresses, and the BPC2's manual makes the choice
    # between them a matter of taste -- "the features available in both addressing modes are
    # identical". Which addresses the trains are on is what one of the two costs, and the
    # same store answers with nothing at all on the other.
    panel = _bpc2_as("acc_8", 1)

    assert panel.scope == CommandScope.ACC
    assert _assigned(panel) == [mod.UNASSIGNED]
    assert _overlaps(panel) == []
    assert panel._overlap_box.visible is False


def test_switching_a_bpc2_between_its_two_keys_changes_whether_the_trains_are_in_the_way() -> None:
    # The rows follow the mode radios rather than the module: the same module at the same
    # address is among the trains on one row and nowhere near them on the other.
    panel = _bpc2_as("acc_8", 1)
    assert _assigned(panel) == [mod.UNASSIGNED]

    panel._on_mode_selected("tr_8")

    assert _assigned(panel) == [_row(CommandScope.TRAIN, TRAIN_LABEL, 1)]
    assert _overlaps(panel) == [_row(CommandScope.TRAIN, _A_ROAD_NAME, 3)]


def test_only_a_track_mode_shares_the_trains_addresses() -> None:
    # Said over the registry rather than of the BPC2 alone, so the next module with a mode
    # on these keys is held to the same rule: the trains are in the way of exactly the modes
    # addressed among them. The ASC2 and STM2 are the proof it is the mode being asked and
    # not the module -- both have modes on two different keys.
    panel = _new_panel(_trains_at_1_and_3_store())
    asked = []
    for device in reg.configurable_devices():
        panel._on_device_selected(device.key)
        for mode in reg.enabled_modes(device):
            panel._on_mode_selected(mode.key)
            panel._set_base_id(1)
            where = f"{device.key}/{mode.key}"
            among_them = mode.scope == CommandScope.TRAIN
            assert panel.shares_train_ids is among_them, where
            assert bool(panel.assigned_trains()) is among_them, where
            assert bool(panel.overlap_trains()) is (among_them and mode.ports > 1), where
            asked.append(among_them)
    assert set(asked) == {True, False}, "both answers have to be reached for this to say anything"


def test_before_a_mode_is_chosen_no_block_is_taken_from_anyone() -> None:
    # Which addresses a block takes is a question about a block, and there is no block until
    # a mode says how long it is -- the same reason the overlaps go unanswered until then.
    panel = _new_panel(_trains_at_1_and_3_store())
    panel._set_base_id(1)

    assert panel.scope is None
    assert panel.shares_train_ids is False
    assert panel.assigned_trains() == []
    assert panel.overlap_trains() == []
    assert _assigned(panel) == [mod.UNASSIGNED]


def test_a_train_is_no_module_to_go_to_or_to_read_settings_off() -> None:
    # Why the trains are looked up apart from the modules. A train is not an LCS module:
    # offering to go to its base would be offering to program a locomotive, and seeding the
    # options page from it would read a BPC2's relay settings off a train.
    panel = _bpc2_as("tr_8", 1)

    assert _assigned(panel) == [_row(CommandScope.TRAIN, TRAIN_LABEL, 1)]
    assert panel.assigned_occupants() == []
    assert panel.programmable_occupant() is None
    assert panel.reconfigured_occupant() is None
    assert panel._goto_btn.visible is False
    assert panel._new_btn.visible is False


def test_a_module_addressed_as_a_track_device_is_not_reported_as_a_train_too() -> None:
    # A BPC2 in TR mode leaves a state on the train keys carrying is_bpc2 -- the very reason
    # a TrainState is an LcsProxyState -- and named as a train as well, it would read as a
    # module standing in its own way.
    store = FakeStore({CommandScope.TRAIN: [FakeState(1, "is_bpc2", mode=0, num_ids=8), FakeTrain(9)]})
    panel = _bpc2_as("tr_8", 1, store)

    assert _assigned(panel) == [_row(CommandScope.TRAIN, BPC2.label, 1, 8)]
    assert panel.reconfigured_occupant() is not None, "the module being reprogrammed, read as itself"
    assert _overlaps(panel) == [], "the train at 9 is outside a block of 1 - 8"


def test_the_modules_are_named_before_the_trains() -> None:
    # The modules are what the page is about; a train is the further thing the operator has
    # to know about the address, so it is read after them rather than in among them.
    store = FakeStore(
        {
            CommandScope.TRAIN: [
                FakeState(2, "is_bpc2", mode=0, num_ids=8),
                FakeTrain(1),
                FakeTrain(3, road_name=_A_ROAD, road_number=_A_NUMBER),
            ]
        }
    )
    panel = _bpc2_as("tr_8", 1, store)

    assert _assigned(panel) == [_row(CommandScope.TRAIN, TRAIN_LABEL, 1)]
    assert _overlaps(panel) == [
        _row(CommandScope.TRAIN, BPC2.label, 2, 8),
        _row(CommandScope.TRAIN, _A_ROAD_NAME, 3),
    ]


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


def _motor(num: int, output_type: OutputType, restore: bool = False) -> Amc2Motor:
    """One of an AMC2's motors as the module reports it: the real dataclass, not a stand-in.

    The direction, the restore state and the speed are what the module is doing rather than
    what it was configured as, and the panel programs none of them -- but they are what a
    real record carries beside the two fields it does read, so they are filled in.
    """
    return Amc2Motor(num, output_type, Direction.FORWARD, restore, False, 0)


def test_the_amc2_offers_a_mode_and_a_remember_flag_for_each_of_its_two_motors() -> None:
    # The module's software configuration "is a single operation that sets three distinct
    # features": the address, and then each motor's mode and whether it comes back up at the
    # speed it was turning. The address is the page before this one, so this page is the two
    # motors -- each a list of the three modes with its own remember flag under it, in the
    # order the manual programs them.
    panel = _new_panel()
    panel._on_device_selected(AMC2.key)

    assert panel._option_boxes[AMC2.key].visible is True
    assert [option.key for option in AMC2.options] == [
        "motor1_mode",
        "motor1_restore",
        "motor2_mode",
        "motor2_restore",
    ]
    for motor in (1, 2):
        modes = panel._option_widgets[(AMC2.key, f"motor{motor}_mode")]
        assert isinstance(modes, DummyCheckBoxGroup)
        assert len(modes.options) == 3
        assert isinstance(panel._option_widgets[(AMC2.key, f"motor{motor}_restore")], DummyCheckBox)
        # Named as the operating panel names the same output, so the module reads the same
        # way on the screen that configures it and the screen that drives it.
        assert AMC2.option(f"motor{motor}_mode").label == f"Motor #{motor}"


def test_the_amc2_motor_modes_are_the_three_the_manual_describes() -> None:
    # Two for DC motors and one for AC, valued as the module reports them rather than as the
    # manual numbers them: the option holds what the module says about itself, and the press
    # is what spells the key the operator taps. See Press.digit_offset.
    rows = AMC2.option("motor1_mode").choices

    assert [value for _label, value in rows] == [OutputType.NORMAL, OutputType.DELTA, OutputType.AC]
    assert [label for label, _value in rows] == ["Continuous (DC)", "Proportional (DC)", "AC"]
    assert AMC2.option("motor2_mode").choices == rows


def test_choosing_a_motor_mode_writes_that_motors_press_alone() -> None:
    # Two gestures on this page look alike -- an AUX key and a digit, twice -- so the one
    # that has to be right is that a choice made for one motor is sent for that motor and
    # the other is left as it was.
    panel = _new_panel()
    panel._on_device_selected(AMC2.key)
    panel._set_base_id(5)

    modes = panel._option_widgets[(AMC2.key, "motor2_mode")]
    modes.value = str([value for _label, value in AMC2.option("motor2_mode").choices].index(OutputType.AC))
    panel._on_option_changed(AMC2.key, "motor2_mode")

    assert panel.options["motor2_mode"] is OutputType.AC
    assert panel.options["motor1_mode"] is OutputType.NORMAL
    assert panel.review_lines == _press_lines(AMC2.mode("acc"), 5, panel.options)


def test_a_setting_below_the_one_being_marked_keeps_the_pad_on_the_page() -> None:
    # D-pad right chooses and turns the page where choosing is the whole of what the page
    # asks. The AMC2 is the first module to ask for more than one thing, and the pad steps
    # the first of its lists: turned there, the page would carry the operator past the motor
    # they have not answered for yet. The Sensor Track, whose one list is the whole page, is
    # the case the rule is read against.
    panel = _new_panel()
    panel.configure(None, 5, None)
    panel._on_device_selected(AMC2.key)
    panel._show_page(mod.PAGE_OPTIONS)
    assert panel.pad_mark_turns_page is False

    panel._on_device_selected(SENSOR_TRACK.key)
    panel._show_page(mod.PAGE_OPTIONS)
    assert panel.pad_mark_turns_page is True


def test_the_options_page_names_the_module_and_the_addresses_it_will_answer_to() -> None:
    # The head of the page, and now the whole of its prose: which module is being programmed
    # and which addresses the block chosen on the page before this one landed on. The mode's
    # own name is not repeated -- the block is what the choice came to.
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._on_mode_selected("acc_8")
    panel._set_base_id(1)

    base, mode = 1, BPC2.mode("acc_8")
    assert panel.options_summary == mod.CONFIGURING.format(
        module=BPC2.label,
        block=f"{mod.SCOPE_LABEL[mode.scope]} {reg.tmcc_id_span(base, base + mode.ports - 1)}",
    )
    assert panel._options_summary.value == panel.options_summary
    # Spelled out once, because this wording is what was asked for: the module, then the
    # remote key and both ends of the block it will answer to.
    assert panel.options_summary == "BPC2: Configuring as ACC 1 - 8"


def test_a_module_holding_a_single_address_names_that_address_alone() -> None:
    # The registry's own span, so a one-ID block reads "ACC 5" rather than "ACC 5 - 5".
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    panel._set_base_id(5)

    assert panel.ports == 1
    assert panel.options_summary == f"{SENSOR_TRACK.label}: Configuring as {mod.SCOPE_LABEL[CommandScope.ACC]} 5"


def test_the_options_page_holds_nothing_between_the_heading_and_the_settings() -> None:
    # Two lines of prose used to stand here. The module's warning is read on the page it is
    # acted on instead -- see review_note -- and the modes the manual reserves are named
    # nowhere: factually right, but about rows that are on no page and cannot be chosen, so
    # there is nothing for the operator to do with them.
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    page = panel._pages[mod.PAGE_OPTIONS]
    prose = [str(getattr(child, "value", "")) for child in page.children]
    assert panel._options_summary.value in prose
    assert BPC2.warning not in panel._options_summary.value
    assert all(BPC2.warning not in line for line in prose)
    reserved = [mode for mode in BPC2.modes if not mode.enabled]
    assert reserved
    for mode in reserved:
        assert mode.note and all(mode.note not in line for line in prose)
        assert all(mode.ports_label not in line for line in prose)


def test_toggling_the_bpc2_restore_flag_updates_the_presses() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)
    assert panel.options["restore"] is False
    assert len(panel.review_lines) == 2

    panel._option_widgets[("bpc2", "restore")].value = 1
    panel._on_option_changed("bpc2", "restore")

    assert panel.options["restore"] is True
    assert panel.review_lines == _press_lines(BPC2.default_mode, 12, {"restore": True})
    # The line the flag added is the press the registry gates on it, and it is there only
    # with the flag set. Read off the row the page opened on, since the flag is gated the
    # same way in either of the BPC2's addressing modes.
    gated = next(press for press in BPC2.default_mode.presses if press.include_if == "restore")
    assert len(panel.review_lines) == 3
    assert any(gated.label in line for line in panel.review_lines)


def test_sensor_track_action_is_required_and_defaults_to_no_action() -> None:
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    action = SENSOR_TRACK.option("action")
    assert action.required is True
    assert panel.options["action"] == IrdaSequence.NONE
    assert panel._option_widgets[("sensor_track", "action")].value == "0"
    # There is no "leave unchanged" row above the list: the first row is the option's own
    # default, and assigning an action is what ends program mode.
    assert len(action.choices) == 10
    assert action.choices[0][1] == action.default == panel.options["action"]


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
    assert panel.review_lines == _press_lines(SENSOR_TRACK.mode("acc"), 3, {"action": IrdaSequence.RECORDING})
    # The digit on the second line is the chosen command's own value, which is the whole
    # point of the option.
    assert str(IrdaSequence.RECORDING.value) in panel.review_lines[1]


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


def test_the_action_rows_are_set_at_the_size_every_other_control_is_and_one_length() -> None:
    # The Sensor Track's ten actions, the one radio option in the registry and the longest
    # list in the panel. It used to settle for the page's body size, because the page could
    # not hold ten rows of the size a lone control gets *and* the option's note under them,
    # and what Tk drops when a page runs out is the Back/Next row. The note is gone, and its
    # height is what these rows are set at the full size with; see LONG_OPTION_PAGE.
    panel = _new_panel()
    host = panel.gui

    action = panel._option_widgets[("sensor_track", "action")]

    assert len(SENSOR_TRACK.option("action").choices) > mod.LONG_OPTION_PAGE
    assert action.kwargs["size"] == host.s_18 > host.s_14
    # No note to spend that height on -- which is the trade, and it only holds while the
    # registry writes none.
    assert SENSOR_TRACK.option("action").note is None
    # And no whitespace between the rows: what sets a row apart is the painted indicator and
    # the row's own background. Ten rows of the padding a shorter list gets would cost the
    # panel its Back/Next row.
    assert action.kwargs["pady"] == 0
    assert action.kwargs["stretch"] is True
    assert "width" not in action.kwargs


def test_the_longest_list_is_set_at_the_size_the_lone_control_and_the_mode_rows_are() -> None:
    # One size for every control the panel offers, whichever page it is on: the size is what
    # a row is aimed at with a finger, and a list being long is not a reason to make it
    # harder to hit than the checkbox beside it on the same page.
    panel = _new_panel()

    action = panel._option_widgets[("sensor_track", "action")]

    assert action.kwargs["size"] == panel._option_widgets[("bpc2", "restore")].decoration["size"]
    assert action.kwargs["size"] == panel._mode_group.kwargs["size"]


def test_the_action_rows_are_headed_by_the_one_word() -> None:
    # "Action Command" is what the manual calls it, and the presses still say so where the
    # remote gesture is being described. The heading is read directly under the module line
    # with the ten actions themselves under it, so the second word names nothing the page
    # has not already said -- on the page that has the least room to say anything twice.
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    heading = panel._option_boxes["sensor_track"].children[0]

    assert SENSOR_TRACK.option("action").label == "Action"
    assert heading.value == "Action"
    assert heading.text_bold is True
    # And the gesture is still described in full on the page the presses are read on.
    assert any("action command" in line.lower() for line in panel.review_lines)


def test_nothing_is_read_under_the_action_rows() -> None:
    # A line about the R➟L / L➟R engine ID filters used to be: true, and about fields that
    # are not on this page and cannot be reached from it. Its height is what the rows are
    # set at the full size with; see LONG_OPTION_PAGE.
    panel = _new_panel()
    panel._on_device_selected("sensor_track")

    box = panel._option_boxes["sensor_track"]

    assert SENSOR_TRACK.option("action").note is None
    # The heading and the rows, and nothing after them.
    assert len(box.children) == 2
    assert box.children[1] is panel._option_widgets[("sensor_track", "action")]
    assert not any("filter" in str(getattr(child, "value", "")).lower() for child in box.children)


def test_the_engine_id_filters_are_still_reported_in_the_read_back() -> None:
    # Which is where the removed line said they were shown, and it is still true: the two
    # filters are read off the module after it answers, beside the action it is now set to.
    state = FakeState(3, "is_sensor_track", sequence=IrdaSequence.CROSSING_GATE_NONE, loco_rl=255, loco_lr=4)
    panel = _new_panel(FakeStore({CommandScope.ACC: [state], CommandScope.IRDA: [state]}))
    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    panel.on_configure()
    panel.on_readback()

    reported = panel._reported_line.value
    assert "R\u279fL Any" in reported
    assert "L\u279fR 4" in reported


def test_a_short_radio_list_is_set_at_the_size_a_lone_control_is() -> None:
    # No module in the registry declares one, so the option is made here: what decides the
    # treatment is how full the page is, not which module the rows belong to.
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


def test_the_whitespace_a_row_may_take_is_decided_by_the_whole_page() -> None:
    # Counted over the module's settings together, because what runs out is the page. The
    # AMC2 is why: four settings, none of them long, but eight rows between them -- read a
    # list at a time every row drew its full padding, and the page came to 748px on a desk
    # against the 679px of the tallest page before it, with 190px of itself held back by the
    # window on the Pi. Read as the page it is, it comes to 620px and the Pi holds back 62px.
    panel = _new_panel()

    assert mod.option_page_rows(AMC2) == 8 > mod.LONG_OPTION_PAGE
    assert mod.option_page_rows(SENSOR_TRACK) == 10 > mod.LONG_OPTION_PAGE
    assert mod.option_page_rows(BPC2) == 1 < mod.LONG_OPTION_PAGE
    for motor in (1, 2):
        assert panel._option_widgets[(AMC2.key, f"motor{motor}_mode")].kwargs["pady"] == 0
        assert panel._option_widgets[(AMC2.key, f"motor{motor}_restore")].decoration["pady"] == 0
    # And a page with the room keeps its whitespace, tick box and all.
    assert panel._option_widgets[(BPC2.key, "restore")].decoration["pady"] == mod.OPTION_ROW_PAD


def test_a_note_on_a_full_page_gets_no_padding_either() -> None:
    # No module in the registry writes one today; the rule is what a full page would do with
    # one. There is nothing left to hold it off the last row with, so the sentence is set
    # against it.
    panel = _new_panel()
    long_option = LcsOption(
        key="noted_long",
        label="Pick one",
        kind=mod.OptionKind.RADIO,
        choices=tuple((chr(ord("A") + i), i) for i in range(mod.LONG_OPTION_PAGE + 1)),
        note="A full sentence about the rows above it.",
    )
    box = DummyBox()

    panel._build_option(box, SENSOR_TRACK, long_option, tight=True)

    note = next(child for child in box.children if getattr(child, "value", None) == long_option.note)
    assert note.tk.configured["pady"] == 0
    # Still wrapped: it is a full sentence, and a page 446px wide.
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
    # The one line of prose left standing off its neighbors, on the review page: it is read
    # between the presses that will be sent and the button that sends them.
    assert panel._review_note_line.tk.configured["pady"] == note_pad
    # Not a page that is full: its rows get nothing on either kind of host.
    assert panel._option_widgets[("sensor_track", "action")].kwargs["pady"] == 0


def test_the_option_rows_are_held_apart_between_the_two_other_lists() -> None:
    # More than the mode rows, which share the fullest page in the panel; less than the
    # module rows, which have a page to themselves.
    assert mod.MODE_ROW_PAD < mod.OPTION_ROW_PAD < mod.RADIO_ROW_PAD
    assert mod.MODE_ROW_PAD_COMPACT <= mod.OPTION_ROW_PAD_COMPACT <= mod.RADIO_ROW_PAD_COMPACT


def test_the_pages_prose_is_read_at_the_body_size_not_below_it() -> None:
    # A step below the body size is fine print at the scale the Pi draws at, and this line
    # is what the page is about: which module, and which addresses.
    panel = _new_panel()
    host = panel.gui
    panel._on_device_selected("bpc2")

    assert panel._options_summary.text_size == host.s_14


def test_every_line_of_prose_the_panel_draws_is_wrapped_to_the_popups_width() -> None:
    # What the photograph showed: the BPC2's relay warning ran off both edges at once.
    # Tk truncates nothing -- it centers a label wider than its container, so the sentence
    # lost its beginning and its end -- and only a wraplength keeps it whole. Every prose
    # line in the panel, on whichever page: the heading's, the two around the mode radios,
    # and the review page's note, which is where that same warning is read now.
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    wrap = panel._wrap_px

    for line in (
        panel._options_summary,
        panel._mode_legend_line,
        panel._mode_note_line,
        panel._review_note_line,
    ):
        assert line.tk.configured["wraplength"] == wrap
        # A broken line follows the line above it, centered under the heading.
        assert line.tk.configured["justify"] == "center"


def test_a_checkbox_label_is_wrapped_from_the_left_beside_its_indicator() -> None:
    # Not centered like the prose: the label is set beside the indicator, so a second line
    # belongs under the first rather than under the middle of the box. And broken at what is
    # left of the row *after* that indicator, which the prose wrap knows nothing about: at
    # the pane's own wrap this one row came to 554px of the Pi's 480px pane.
    panel = _new_panel()
    host = panel.gui

    restore = panel._option_widgets[("bpc2", "restore")]

    assert restore.decoration["wrap"] == panel._row_wrap_px(host.s_18)
    assert restore.decoration["wrap"] < panel._wrap_px


def test_an_options_own_note_is_wrapped_and_read_at_the_body_size() -> None:
    # A note is a full sentence about the setting above it, read like the line at the head
    # of the page. The registry carries none today; the option is made here, as the short
    # list above is, because what the panel does with a note is not a fact about a module.
    panel = _new_panel()
    host = panel.gui
    short = LcsOption(
        key="noted",
        label="Pick one",
        kind=mod.OptionKind.RADIO,
        choices=(("A", 1), ("B", 2)),
        note="A full sentence about the two rows above it.",
    )
    box = DummyBox()

    panel._build_option(box, BPC2, short)

    note = next(child for child in box.children if getattr(child, "value", None) == short.note)
    assert note.text_size == host.s_14
    assert note.tk.configured["wraplength"] == panel._wrap_px
    # And held off the rows above it, unlike a long list's; see LONG_OPTION_PAGE.
    assert note.tk.configured["pady"] == mod.NOTE_PAD


def test_the_wrap_is_the_width_the_popup_is_built_to() -> None:
    # create_popup builds the popup's title row to the emergency box's width, so that is
    # the width a line inside it has to fit -- less the gutter the scroll bar is drawn in,
    # which is width the page never has; see _page_px.
    panel = _new_panel()
    host = panel.gui

    assert panel._wrap_px == host.emergency_box_width - mod.scroll_bar_px() - mod.WRAP_INSET


def test_the_wrap_falls_back_to_the_pane_and_then_to_a_floor() -> None:
    # A host that has not measured its emergency box yet still has a pane width; one with
    # neither gets a width narrower than any pane the GUI runs in, so a line can only ever
    # be broken early -- never off the edge of the screen.
    panel = _new_panel()
    host = panel.gui

    host.emergency_box_width = 0
    assert panel._wrap_px == host.width - mod.scroll_bar_px() - mod.WRAP_INSET

    host.width = 0
    assert panel._wrap_px == mod.MIN_WRAP_PX
    assert mod.MIN_WRAP_PX < 480


def test_a_page_is_drawn_in_the_pane_less_the_room_the_scroll_bar_takes() -> None:
    # The bar is drawn over the window the pages are seen through, so the room it takes has to
    # be kept out of the page: measured on a Pi pane, the widest line of the review page's
    # prose stops 9px inside it, which even the 10px bar this began as took the end of. Every
    # width the panel breaks a line at is taken from here, so the wrap and the boxes cannot
    # come to disagree about where the page ends.
    panel = _new_panel()
    host = panel.gui

    assert panel._page_px == panel._pane_px - mod.scroll_bar_px()
    assert panel._wrap_px == panel._page_px - mod.WRAP_INSET
    assert panel._titled_box_px == panel._page_px - mod.TITLED_BOX_INSET
    # The window itself keeps the pane's whole width: the gutter is inside it, which is how
    # the bar can appear and disappear without a row moving.
    assert panel._scroll_px == panel._pane_px

    # And a host that has measured nothing is given a page it can still hold a line in.
    host.emergency_box_width = host.width = 0
    assert panel._page_px == mod.MIN_WRAP_PX + mod.WRAP_INSET


def test_a_line_with_nothing_to_say_leaves_the_page_and_takes_its_gaps_with_it() -> None:
    # The review page's note is filled by the BPC2, which has a warning, and by no other
    # module -- the Sensor Track's caveat stood here too until the steps it was about were
    # given a box of their own. An empty label still stands a line tall and still carries its
    # own padding above and below.
    panel = _new_panel()

    panel._on_device_selected("bpc2")
    assert panel._review_note_line.visible is True

    panel._on_device_selected("asc2")
    assert panel.review_note == ""
    assert panel._review_note_line.visible is False

    panel._on_device_selected("sensor_track")
    assert panel._review_note_line.visible is False

    # And comes back with something to say.
    panel._on_device_selected("bpc2")
    assert panel._review_note_line.visible is True


def test_the_heading_is_followed_by_the_module_then_a_gap_then_the_settings() -> None:
    # The heading belongs with the line under it; the wider gap separates the module being
    # programmed from the settings being chosen for it. Children are recorded in creation
    # order, which is the order guizero packs them in.
    panel, _body, _host = _build_with_body()
    page = panel._pages[mod.PAGE_OPTIONS]

    assert page.children[0].value == mod.OPTIONS_TITLE
    assert getattr(page.children[1], "vspace", None) == mod.SECTION_GAP
    assert page.children[2] is panel._options_summary
    assert getattr(page.children[3], "vspace", None) == mod.PAGE_GAP
    assert page.children[4] in panel._option_boxes.values()


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
    # Every page is reached by index, and all of them are created once in build(); leaving
    # one out would move the review page. The listing is built with them though it is not
    # one of the four walked through; see PAGE_INVENTORY.
    panel = _new_panel()

    assert len(panel._pages) == 5
    assert panel._pages[mod.PAGE_REVIEW] is not panel._pages[mod.PAGE_OPTIONS]
    assert panel._pages[mod.PAGE_INVENTORY] is not panel._pages[mod.PAGE_REVIEW]


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

    lines = _press_lines(ASC2.mode("acc_8"), 9)
    assert panel.review_lines == lines
    assert panel._review_line.value == "\n".join(lines)
    assert f"{ASC2.program_button} button" in panel._program_line.value
    # The instruction names the button, how long to hold it, and what the module does to say
    # it heard -- which is the whole of what the operator has to do before Configure will
    # take. Held to the word here because it is the line the page is read for.
    instruction = f"Hold the {ASC2.label}'s PGM button for 1 second until the red LED blinks slowly"
    assert panel._program_line.value == instruction
    assert panel.footnote == mod.PROGRAM_MODE_NOTE.format(module=ASC2.label)
    assert panel._footnote_line.value == panel.footnote


def test_the_sensor_tracks_review_names_its_own_program_button() -> None:
    # A PROGRAM key where every other module has a PGM key, which the registry spells and the
    # instruction reads off it. The caveat that used to stand beside it -- that the sequence
    # is only complete once the Action Command has been assigned -- is drawn nowhere now: the
    # sequence is listed step by step in the Manual Configuration box, which is where an operator
    # reads what is done and what is left.
    panel = _new_panel()
    panel._on_device_selected("sensor_track")

    assert f"{SENSOR_TRACK.program_button} button" in panel._program_line.value
    assert panel.review_note == ""
    assert panel._review_note_line.visible is False
    assert "Action Command" not in panel._review_note_line.value
    assert panel.footnote == mod.PROGRAM_MODE_NOTE.format(module=SENSOR_TRACK.label)


def test_the_relay_warning_is_read_on_the_page_it_is_acted_on() -> None:
    # The one page it is read on now. It is not about the settings being chosen -- it is
    # about what the presses do, and what has to be done by hand afterwards -- so it stands
    # in front of the button that sends them rather than at the head of the page before.
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert BPC2.warning
    assert panel.review_note == BPC2.warning
    assert panel._review_note_line.value == BPC2.warning
    # In full, and read in one piece: an unwrapped label wider than the popup is centered
    # rather than truncated, which cost this sentence both its ends on the Pi.
    assert panel._review_note_line.tk.configured["wraplength"] == panel._wrap_px
    # Above the button, below the presses it is about. Both of those now stand on the page
    # inside something of their own -- the steps in their box, the key on its row -- so the
    # order is read through them.
    page = panel._pages[mod.PAGE_REVIEW]
    order = page.children.index
    steps = panel._manual_config_grid
    assert order(steps) < order(panel._review_note_line) < order(panel._configure_key_row)
    assert panel._review_line in panel._manual_config_box.children


def test_the_review_pages_heading_is_followed_by_half_a_line_then_the_instruction() -> None:
    # The heading stood flush against the instruction under it. Half a line of white space,
    # and half a line only: what follows the heading is the first thing to be done rather
    # than the next thing on the page, so it belongs to the heading. See REVIEW_HEADING_GAP.
    panel, _body, _host = _build_with_body()
    page = panel._pages[mod.PAGE_REVIEW]

    assert page.children[0].value == mod.REVIEW_TITLE
    assert getattr(page.children[1], "vspace", None) == mod.REVIEW_HEADING_GAP
    assert page.children[2] is panel._program_line


def test_the_instruction_and_the_steps_are_read_at_the_pages_own_size() -> None:
    # The instruction was set a step below the page's body, which made the one line in the
    # panel that has to be acted on before the button below it will do anything the smallest
    # text on any of its pages. It and the steps are a size above the body now, which the
    # instruction pays nothing for: it takes two lines at every size the panel draws.
    panel = _new_panel()
    host = panel.gui
    size = panel._review_text_size

    assert size == host.s_16 > host.s_14 > host.s_12
    assert panel._program_line.text_size == size
    assert panel._review_line.text_size == size
    # The box's title with them, as the ID page's boxes are titled at the size of their own
    # rows: a title two sizes below its list reads as fine print on it.
    assert panel._manual_config_box.text_size == size
    # And what the module answers with is left where it was: what grew is the work to be
    # done, not the record of what was asked and what came back.
    lines = (panel._footnote_line, panel._requested_line, panel._reported_line)
    assert [line.text_size for line in lines] == [host.s_12] * 3


def test_the_steps_stand_in_a_box_of_their_own_drawn_to_the_page() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(9)

    box = panel._manual_config_box
    assert box.text == mod.MANUAL_CONFIG_TITLE == "Manual Configuration"
    assert panel._review_line in box.children
    assert panel._review_line.value == "\n".join(_press_lines(ASC2.mode("acc_8"), 9))
    # Gridded into a column of its own and stretched across it, which is the only way a box
    # gets a width the page decides rather than the width of "1. ACC 1 SET" -- a frame a
    # third of the pane wide, with a title longer than the list under it.
    container = panel._manual_config_grid
    assert container.kwargs["layout"] == "grid" and box in container.children
    assert container.tk.columns[0] == {"weight": 1, "minsize": panel._manual_config_px}
    assert box.tk.gridded["sticky"] == "ew"


def test_the_steps_box_stands_in_a_margin_either_side_of_it() -> None:
    # It was stretched to the floor the ID page's three boxes share, which is 6px a side: a
    # frame all but on the edge of the page, with its numbers 2px inside it. Its width is the
    # page's own prose width now -- so the frame stands exactly where the instruction above it
    # breaks, with twice the white space either side -- and the list is held off the frame by
    # the same margin again. See _manual_config_px and MANUAL_CONFIG_PAD.
    panel = _new_panel()
    box, page = panel._manual_config_box, panel._page_px

    assert panel._manual_config_px == panel._wrap_px < panel._titled_box_px < page
    assert (page - panel._manual_config_px) // 2 == mod.WRAP_INSET // 2 == 12
    assert box.tk.gridded["sticky"] == "ew", "the box is what the column's width is given to"
    # And inside the frame: the presses begin a margin in, and are broken at what is left
    # rather than at the page's width, which is the frame's own now.
    line = panel._review_line
    assert line.tk.configured["padx"] == mod.MANUAL_CONFIG_PAD == 8
    assert line.tk.configured["wraplength"] == panel._manual_config_wrap_px
    assert panel._manual_config_wrap_px == panel._manual_config_px - 2 * mod.MANUAL_CONFIG_PAD


def test_the_steps_box_keeps_its_width_across_a_refresh() -> None:
    # guizero rebuilds a container's grid options from scratch whenever a child of it is
    # created, shown or hidden, and sticky is not among the options it replays -- which is
    # why the ID page's boxes are re-stretched after every refresh, and why this one is.
    panel = _new_panel()
    box, container = panel._manual_config_box, panel._manual_config_grid
    box.tk.gridded.clear()
    container.tk.columns.clear()

    panel._on_device_selected("bpc2")

    assert box.tk.gridded["sticky"] == "ew"
    assert container.tk.columns[0]["minsize"] == panel._manual_config_px

    # And a box the grid has forgotten is passed over: grid_configure on one would put it
    # back on the page.
    box.hide()
    box.tk.gridded.clear()
    panel._on_device_selected("asc2")

    assert box.tk.gridded == {}


def test_the_steps_read_from_the_left_edge_of_their_box() -> None:
    # A numbered list is read down its numbers, and centered lines start each of them
    # somewhere else -- which is how the presses read before they were given a box. The label
    # is stretched to the box and its text anchored west: justify alone would only line up
    # the second line of a press under the first, a label narrower than what it stands in
    # being centered in it whatever its own lines do. See _left_line.
    panel = _new_panel()
    line = panel._review_line

    assert line.kwargs["width"] == "fill"
    assert line.tk.configured["anchor"] == "w"
    assert line.tk.configured["justify"] == "left"
    # Broken inside the frame it stands in rather than at the page's width, which is that
    # frame's own width now: the wrap decides where a press breaks and not the frame.
    assert line.tk.configured["wraplength"] == panel._manual_config_wrap_px < panel._wrap_px
    # And the prose on the page is still centered under the heading, as all of it is.
    assert panel._program_line.tk.configured["justify"] == "center"


def test_the_configure_key_stands_where_the_keys_below_it_stand() -> None:
    # The one key built into a page at all, and it stood half a scroll bar left of the Back,
    # Next and Close beneath it: those are centered on the pane, while everything on a page is
    # centered on the page, and a page with a bar drawn down it is one bar narrower. So the
    # room the bar takes is handed back to the key on a row of its own. See _build_key_row.
    panel = _new_panel()
    row = panel._configure_key_row

    assert len(row.children) == 2 and row.children[1] is panel._configure_btn, "the gutter, then the key"
    gutter = row.children[0]
    assert gutter is panel._configure_key_gutter
    assert isinstance(gutter, DummyBox) and not gutter.value, "white space, and nothing else"
    # Built at the bar's width, that being the answer for a page held back in its window and
    # the only width a box can be built at -- what the window is really keeping is set on it
    # at the first fit; see the two tests below.
    assert gutter.kwargs["width"] == mod.scroll_bar_px() == mod.SCROLL_BAR_PX
    assert gutter.kwargs["height"] == 1, "it holds a column apart, not two rows"
    assert gutter.kwargs["align"] == panel._configure_btn.kwargs["align"] == "left"
    # And the row itself is centered on the page like anything else built into one.
    assert row.kwargs["align"] == "top"
    # The one key that asks for this now: the My Modules key was the other, and it stands on
    # the row of keys itself, which is centered on the pane and needs no gutter.
    assert panel._inventory_btn in panel._nav.children
    assert not any(isinstance(child, DummyBox) for child in panel._nav.children)


def test_the_space_beside_the_key_is_what_the_window_is_keeping_from_the_page() -> None:
    # And it is not a fixed thing, because what the page gives up is not: the window keeps the
    # bar's width clear of the page only while a bar is drawn in it. A bar's width of white
    # space beside the key on a page that is paying nothing for a bar puts the key half a bar
    # right of the keys below it -- the wrong side of where it stood before, by the same
    # amount. So the spacer is whatever is being kept, on every fit. See _fit_key_gutter.
    panel = _new_panel()
    gutter = panel._configure_key_gutter

    assert panel.scroll.gutter_px == 0
    assert gutter.tk.configured["width"] == 0, "a page with the whole window stands its key dead center"

    panel.scroll.gutter_px = mod.scroll_bar_px()
    panel._fit_scroll()

    assert gutter.tk.configured["width"] == mod.scroll_bar_px(), "and off center by a bar where one is drawn"

    panel.scroll.gutter_px = 0
    panel._fit_scroll()

    assert gutter.tk.configured["width"] == 0, "back again as a page comes to fit its window"


def test_a_fit_that_left_the_window_keeping_the_same_room_does_not_move_the_key() -> None:
    # The window is fitted on every layout pass -- a row built, a box shown, the popup laid
    # out -- and re-sizing the spacer costs a pass of its own, which would ask for the fit
    # that re-sized it. Nothing is moved unless the answer changed.
    panel = _new_panel()
    gutter = panel._configure_key_gutter
    widths = [call["width"] for call in gutter.tk.configs if "width" in call]

    panel._fit_scroll()
    panel._fit_scroll()

    assert widths == [0], "the one width the first fit set, the box having been built at the bar's"
    assert [call["width"] for call in gutter.tk.configs if "width" in call] == widths


def test_white_space_stands_either_side_of_the_configure_key() -> None:
    # It sends the steps above it and writes the read-back below it, and stood flush against
    # both. The page's own gap, which is what holds any two sections of a page apart.
    panel, _body, _host = _build_with_body()
    page = panel._pages[mod.PAGE_REVIEW]
    at = page.children.index(panel._configure_key_row)

    assert getattr(page.children[at - 1], "vspace", None) == mod.PAGE_GAP
    assert getattr(page.children[at + 1], "vspace", None) == mod.PAGE_GAP
    assert page.children[at + 2] is panel._footnote_line


#
# Configure and read-back
#
def test_configure_queues_the_presses_in_order_then_the_verify_gets() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._on_mode_selected("tr_8")  # the TR presses, so the enums below name one mode's own
    panel._set_base_id(12)

    panel.on_configure()

    sent = panel.gui.sent
    # Three keys, then CONFIG and INFO -- once for every time the module is asked.
    assert len(sent) == 3 + 2 * len(mod.LcsConfigPanel._verify_times(3))
    commands = [request.command for request, _repeat, _delay in sent[:3]]
    number, digit = reg.number_key(0, CommandScope.TRAIN)
    # The AUX key and the number are two keys, so they are two requests, staggered like any
    # other pair of presses -- which is what makes them two keystrokes on the handset rather
    # than one command claiming to be one.
    assert commands == [TMCC1EngineCommandEnum.SET_ADDRESS, reg.aux_key(1, CommandScope.TRAIN), number]
    assert sent[2][0].data == digit == 0
    delays = [delay for _request, _repeat, delay in sent]
    assert delays == sorted(delays)
    assert delays[0] == 0.0
    assert len({delays[1] - delays[0], delays[2] - delays[1]}) == 1
    assert delays[3] > delays[2]
    mode = BPC2.mode("tr_8")
    summary = mod.SUMMARY.format(
        module=BPC2.label,
        mode=mode.ports_label,
        scope=mod.SCOPE_LABEL[mode.scope],
        id=12,
    )
    assert panel._requested_line.value.startswith(mod.REQUESTED.format(summary=summary))
    # The module, the block it was asked for and the address are each on the line, so a
    # summary that dropped one of them would not pass for the sentence it is filled into.
    assert all(
        part in panel._requested_line.value
        for part in (BPC2.label, mode.ports_label, mod.SCOPE_LABEL[mode.scope], "12")
    )
    # And the panel says what it is doing about it: the module has been asked for its
    # configuration, and the answer is going to be held against what was just sent.
    assert panel._reported_line.value == "", "the module has not said anything yet"
    assert panel._status_line.value == mod.VERIFYING.format(module=BPC2.label)


def test_configure_of_a_sensor_track_always_sends_both_halves() -> None:
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    panel.on_configure()

    commands = [request.command for request, _repeat, _delay in panel.gui.sent[:3]]
    number, _digit = reg.number_key(0, CommandScope.ACC)
    assert commands == [TMCC1AuxCommandEnum.SET_ADDRESS, reg.aux_key(1, CommandScope.ACC), number]


def test_the_module_is_asked_again_and_again_while_the_panel_waits() -> None:
    # One GET is one chance at an answer. A module put into program mode a beat late, or a
    # request lost on the way, is silence -- and silence is now a verdict rather than a note,
    # so being wrong about it costs the operator a reprogramming.
    asks = mod.LcsConfigPanel._verify_times(3)

    assert len(asks) > 1
    assert asks[0] == 3 * mod.PRESS_DELAY + mod.VERIFY_DELAY, "not before the last press has landed"
    assert {round(later - earlier, 6) for earlier, later in zip(asks, asks[1:])} == {mod.VERIFY_POLL_DELAY}
    # And never after the panel has stopped listening: an answer arriving then cannot change
    # a verdict already written.
    assert asks[-1] < mod.READBACK_TIMEOUT_MSEC / 1000


def test_a_sequence_that_runs_past_the_wait_is_still_asked_once() -> None:
    # The presses are staggered, so a long sequence eats the wait: an AMC2's six keys are
    # 2.1 seconds of the 5. A module that is never asked can only be reported as silent,
    # which would fail a module that took everything it was sent.
    long_one = 100

    assert mod.LcsConfigPanel._verify_times(long_one) == [long_one * mod.PRESS_DELAY + mod.VERIFY_DELAY]


def test_the_status_line_is_not_colored_as_an_answer_until_there_is_one() -> None:
    # Green or red is an answer whatever the words beside it say, and there is none yet:
    # what the line reports at this point is that the panel is still asking.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)

    panel.on_configure()

    assert panel._status_line.visible is True
    assert panel._status_line.text_color == mod.VERIFYING_FG
    assert panel._status_line.text_color not in (mod.VERIFIED_FG, mod.UNVERIFIED_FG)


def test_the_configure_button_wears_the_shared_look_of_the_overlays_other_keys(monkeypatch) -> None:
    # Styled by its text size alone, it was drawn flat -- a rectangle with a word in it, the
    # one key in the panel that did not read as a key, and the one that programs a module.
    # What the look is remains the popup's to say; what is pinned here is that this button
    # is given it, exactly as Back, Next and the Close below them are.
    styled: list[Any] = []
    monkeypatch.setattr(mod, "style_footer_button", lambda _host, btn: styled.append(btn), raising=True)

    panel = _new_panel()

    assert panel._configure_btn in styled
    # Every key the panel draws, in the order they are built: the ID page's two choices, then
    # Configure on the page after it, then the three of the row of keys in the order they
    # stand in. The pages come before that row, and nothing else in the panel is a key.
    assert [btn.text for btn in styled] == [
        "Go to",
        "Configure as new",
        mod.CONFIGURE_TEXT,
        mod.BACK_TEXT,
        mod.INVENTORY_TEXT,
        mod.NEXT_TEXT,
    ]


def test_the_my_modules_key_is_drawn_as_a_key_like_the_ones_beside_it(monkeypatch) -> None:
    # It turns a page, which is what Back and Next do, and it stands on their row: drawn by
    # its text size alone it read as a word in a rectangle beside keys with an edge and a face
    # of their own.
    styled: list[Any] = []
    monkeypatch.setattr(mod, "style_footer_button", lambda _host, btn: styled.append(btn), raising=True)

    panel = _new_panel()

    assert panel._inventory_btn in styled
    assert panel._inventory_btn.text == mod.INVENTORY_TEXT == "My Modules"


def test_read_back_reports_what_the_module_says() -> None:
    state = FakeState(9, "is_asc2", mode=0, num_ids=8)
    store = FakeStore({CommandScope.ACC: [state]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")
    panel._set_base_id(9)

    panel.on_configure()
    panel.on_readback()

    mode = ASC2.mode("acc_8")
    assert panel._reported_line.value == mod.REPORTED.format(
        summary=", ".join(
            (
                mod.REPORTED_AT.format(module=ASC2.label, id=9),
                mod.SCOPE_LABEL[mode.scope],
                mod.REPORTED_IDS.format(count=8),
            )
        )
    )
    # What the module answered with, part by part: which module, at which address, on which
    # remote key, holding how many IDs.
    assert all(part in panel._reported_line.value for part in (ASC2.label, "9", mod.SCOPE_LABEL[mode.scope], "8"))
    # The presses that were sent stay on screen.
    assert panel._review_line.value.startswith(_press_lines(mode, 9)[0])


def test_read_back_timeout_reports_no_response_and_leaves_the_presses() -> None:
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._set_base_id(40)

    panel.on_configure()
    assert panel.gui.app.scheduled and panel.gui.app.scheduled[0][0] == mod.READBACK_TIMEOUT_MSEC
    panel.gui.app.fire()

    assert panel._reported_line.value == mod.NO_RESPONSE
    assert panel._review_line.value.startswith(_press_lines(ASC2.mode("acc_8"), 40)[0])


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
    assert panel._mode_group.options == _mode_options(ASC2, 1)
    # A row per mode the module offers, in the registry's order, and no two of them read
    # alike -- so a mode dropped, doubled or misordered shows up here.
    assert [key for _label, key in panel._mode_group.options] == [mode.key for mode in reg.enabled_modes(ASC2)]
    labels = [label for label, _key in panel._mode_group.options]
    assert len(set(labels)) == len(labels)
    # Both accessory modes are told apart by a qualifier of their own, which is the one
    # thing the block each claims cannot say.
    accessory = [mode for mode in reg.enabled_modes(ASC2) if mode.scope is CommandScope.ACC]
    assert len({mode.qualifier for mode in accessory}) == len(accessory)
    # Every switch mode names the block it consumes, as the accessory modes do.
    for label, key in panel._mode_group.options:
        mode = ASC2.mode(key)
        assert reg.tmcc_id_text(1, mode.ports) in label

    # Switch to Sensor Track, which has 1 mode
    panel._on_device_selected("sensor_track")
    assert len(panel._mode_group.options) == 1
    assert panel._mode_group.options == _mode_options(SENSOR_TRACK, 1)

    # Switch to BPC2, which has 2 enabled modes (the 1-ID modes are disabled)
    panel._on_device_selected("bpc2")
    assert len(panel._mode_group.options) == 2
    assert panel._mode_group.options == _mode_options(BPC2, 1)
    # The reserved modes are not among them, whatever they are named.
    assert [key for _label, key in panel._mode_group.options] == [mode.key for mode in reg.enabled_modes(BPC2)]


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

    assert _assigned(panel) == [_row(CommandScope.TRAIN, BPC2.label, 12, 8)]


def test_on_synchronized_re_seeds_while_the_operator_has_not_chosen(monkeypatch) -> None:
    # A module is always selected once the panel has been configured, so "untouched" is a
    # flag of its own now rather than the absence of a selection.
    _appliance(monkeypatch)
    states: dict[CommandScope, list[FakeState]] = {CommandScope.TRAIN: []}
    panel = _new_panel(FakeStore(states))
    panel.configure(None, 12, None)
    panel.set_sync_pending(True)
    assert panel.device is _first_offered()

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
    assert _assigned(panel) == [_row(CommandScope.SWITCH, STM2.label, 12, 8)]


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


# noinspection PyProtectedMember
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

    assert panel._titled_boxes.tk.columns == {0: {"weight": 1, "minsize": panel._titled_box_px}}
    # The stretch that makes them one width, and the whitespace that keeps the three from
    # reading as one ruled block. Padding rather than a spacer widget only because this
    # method is re-run after every refresh; see its docstring.
    stretched_and_spaced = {"sticky": "ew", "pady": (0, mod.BOX_GAP)}
    assert panel._mode_box.tk.grid_options == stretched_and_spaced
    assert panel._assigned_box.tk.grid_options == stretched_and_spaced
    # Bar the last one showing, which has no next box to be held off: under it is the page's
    # own gap and then the choice buttons, and the two stacked read as a hole in the page.
    assert panel._overlap_box.tk.grid_options == {"sticky": "ew", "pady": (0, 0)}


@pytest.mark.parametrize("compact, gap", [(False, mod.BOX_GAP), (True, mod.BOX_GAP_COMPACT)])
def test_the_gap_between_the_boxes_is_tighter_on_a_compact_host(compact: bool, gap: int) -> None:
    host = _new_host()
    host.compact = compact
    panel = mod.LcsConfigPanel(host)
    panel.build(DummyBox())
    # A module with modes, so the assigned box has one showing below it to be held off.
    panel._on_device_selected("asc2")
    _record_titled_boxes(panel)

    panel._lay_out_titled_boxes()

    assert panel._mode_box.tk.grid_options["pady"] == (0, gap)


def test_a_hidden_box_is_not_stretched_back_onto_the_screen() -> None:
    # No device chosen, so there are no modes to show and nothing can be in the way.
    # Configuring the grid for a widget the grid has forgotten would put the empty titled
    # frame back on the page.
    panel = _new_panel()
    assert panel._mode_box.visible is False
    assert panel._overlap_box.visible is False
    _record_titled_boxes(panel)

    panel._lay_out_titled_boxes()

    # The only box showing, so it is also the last: nothing below it to be held off.
    assert panel._assigned_box.tk.grid_options == {"sticky": "ew", "pady": (0, 0)}
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

    assert panel._titled_boxes.tk.columns == {0: {"weight": 1, "minsize": panel._titled_box_px}}
    assert panel._mode_box.tk.grid_options == {"sticky": "ew", "pady": (0, mod.BOX_GAP)}
    assert panel._assigned_box.tk.grid_options == {"sticky": "ew", "pady": (0, 0)}


def test_the_boxes_are_drawn_no_narrower_than_the_page_they_stand_on() -> None:
    # A width floor on the column all three share, so none of them shrinks to whatever is
    # inside it: the legend heading the Mode box is prose, and left to the widest radio row
    # it wrapped into a column with the page's right-hand side standing empty beside it.
    # Taken from the pane rather than chosen in pixels, so it holds at either font scale.
    panel = _new_panel()
    host = panel.gui

    assert panel._titled_box_px == host.emergency_box_width - mod.scroll_bar_px() - mod.TITLED_BOX_INSET
    # Wider than the longest line the boxes can hold, which is the point of the smaller
    # inset: the wrap decides where a sentence breaks, not the frame around it.
    assert mod.TITLED_BOX_INSET < mod.WRAP_INSET
    assert panel._titled_box_px > panel._wrap_px
    # And still a floor, not a fixed width: the stretch that lets a long module name widen
    # all three is asked for alongside it.
    _record_titled_boxes(panel)
    panel._lay_out_titled_boxes()
    assert panel._titled_boxes.tk.columns[0]["weight"] == 1


def test_a_host_that_has_measured_nothing_still_gets_boxes_wider_than_the_wrap() -> None:
    # The floor either side of the same difference, so the one rule -- a box wider than the
    # line it holds -- survives a host with no width to report.
    host = _new_host()
    host.emergency_box_width = 0
    host.width = 0
    panel = mod.LcsConfigPanel(host)

    assert panel._wrap_px == mod.MIN_WRAP_PX
    assert panel._titled_box_px > panel._wrap_px


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
    review_page = panel._pages[mod.PAGE_REVIEW]

    parents = [parent for parent, _pixels in host.vspaces]
    assert parents == [
        body,  # under the popup's title row
        # Under that page's prompt, and nothing below the modules: the My Modules key stood
        # there and stands on the row of keys now, which the body's own gap holds off.
        panel._pages[mod.PAGE_DEVICE],
        id_page,  # under the stepper row
        panel._mode_box,  # between the legend of keys and the mode radios
        panel._mode_box,  # between the radios and the note on the chosen one
        id_page,  # between the titled boxes and the choice buttons
        options_page,  # under that page's heading
        options_page,  # between the module and the settings chosen for it
        review_page,  # half a line under that page's heading
        review_page,  # between the steps and the key that sends them
        review_page,  # and between that key and the read-back below it
        panel._pages[mod.PAGE_INVENTORY],  # between the sort keys and the listing
    ]
    # And the two the panel builds itself, which are the two that move: the gaps either side
    # of the row of keys are not the same on every page. See LcsConfigPanel._refresh_nav_band.
    assert body.children.index(panel._nav_lead) < body.children.index(panel._nav)
    assert body.children.index(panel._nav) < body.children.index(panel._nav_trail)


def test_the_body_spacer_comes_before_the_sync_line_and_the_pages() -> None:
    panel, body, _host = _build_with_body()

    assert getattr(body.children[0], "vspace", None) == mod.SECTION_GAP
    assert body.children[1] is panel._sync_line
    # The pages are inside the window, and the window is what the body holds in their place.
    assert body.children[2] is panel.scroll.viewport
    assert panel._pages[mod.PAGE_DEVICE] in panel.scroll.content.children


def test_the_device_page_spacer_sits_between_the_prompt_and_the_group() -> None:
    panel, _body, _host = _build_with_body()
    page = panel._pages[mod.PAGE_DEVICE]

    assert page.children[0].value == mod.DEVICE_PROMPT
    assert getattr(page.children[1], "vspace", None) == mod.SECTION_GAP
    assert page.children[2] is panel._device_group


def test_the_id_pages_sections_are_held_apart() -> None:
    # The crowded page: the stepper, the three titled boxes and the choice buttons each
    # answer a different question, and ran together into one block without these.
    panel, _body, _host = _build_with_body()
    page = panel._pages[mod.PAGE_ID]

    assert page.children[0] is panel._id_heading
    assert page.children[1].kwargs["layout"] == "grid"  # the - 8 + row
    # Held apart, but tighter than the panel's other pages: this one carries more than any
    # of them, and what stands either side of these two gaps -- a box drawn like a text
    # field, a titled frame, a row of buttons -- says where one section ends without help.
    assert getattr(page.children[2], "vspace", None) == mod.ID_PAGE_GAP
    assert mod.ID_PAGE_GAP < mod.PAGE_GAP
    assert page.children[3] is panel._titled_boxes
    # One gap below the boxes, where there were two with the block line between them.
    assert getattr(page.children[4], "vspace", None) == mod.ID_PAGE_GAP
    # The choice buttons' row, and nothing after it: the page ends where the boxes' gap
    # leaves off, rather than with a line and a second gap between the two.
    assert panel._goto_btn in page.children[5].children
    assert panel._new_btn in page.children[5].children
    assert len(page.children) == 6


@pytest.mark.parametrize(
    "compact, section, page, id_page, prose, heading",
    [
        (False, mod.SECTION_GAP, mod.PAGE_GAP, mod.ID_PAGE_GAP, mod.MODE_PROSE_GAP, mod.REVIEW_HEADING_GAP),
        (
            True,
            mod.SECTION_GAP_COMPACT,
            mod.PAGE_GAP_COMPACT,
            mod.ID_PAGE_GAP_COMPACT,
            mod.MODE_PROSE_GAP_COMPACT,
            mod.REVIEW_HEADING_GAP_COMPACT,
        ),
    ],
)
def test_the_gaps_are_tighter_on_a_compact_host(
    compact: bool, section: int, page: int, id_page: int, prose: int, heading: int
) -> None:
    panel, _body, host = _build_with_body(compact=compact)

    assert [pixels for _parent, pixels in host.vspaces] == [
        section,
        section,
        id_page,
        prose,
        prose,
        id_page,
        section,
        page,
        heading,
        page,
        page,
        page,
    ]
    # The gap above the row of keys is the panel's own spacer rather than the host's, so it is
    # read off the panel instead of the roster; it is the same page gap underneath, which is
    # what the band on the first page is added to. See LcsConfigPanel._refresh_nav_band.
    assert panel._page_gap == page
    # Both halves of the same rule: a compact host takes less of everything, and the ID
    # page takes less than the pages that have room to spare.
    assert id_page < page
    # And the review page's own gap is half a line of its heading, which on a pane with room
    # lands between the two: wider than the gap a heading takes above a prompt, narrower than
    # the one between a page's sections. See REVIEW_HEADING_GAP.
    assert mod.SECTION_GAP < mod.REVIEW_HEADING_GAP < mod.PAGE_GAP
    # On a compact host it is squeezed onto the smaller of them, as everything here is.
    assert section <= heading <= page


#
# The panel's own row of keys: Back is off the first page, and left of Next on the rest
#
def test_the_row_of_keys_is_the_last_thing_in_the_body_after_a_gap() -> None:
    # The panel's own row, not the popup's footer: Close is added below everything build()
    # produces, so it lands on a line of its own under this row.
    panel, body, _host = _build_with_body()

    assert body.children[-3] is panel._nav_lead
    assert body.children[-2] is panel._nav
    # And a gap below it as well, which is what holds it off the Close button create_popup
    # adds under the whole of this; on every page but the first it is nothing to look at.
    assert body.children[-1] is panel._nav_trail
    # In creation order, which is the order Tk packs them in and so the order they are read:
    # My Modules stands left of Next, and right of Back on any page that showed both.
    assert [child.text for child in panel._nav.children if getattr(child, "text", "")] == [
        mod.BACK_TEXT,
        mod.INVENTORY_TEXT,
        mod.NEXT_TEXT,
    ]


def _band(panel) -> tuple[int, int]:
    """What the two gaps either side of the row of keys are set to, in pixels.

    Read off the boxes rather than off the panel's own count of it, since the point of the
    pair is what is drawn: a Tk height, for the reason the space beside a page's key is one.
    """
    return (
        panel._nav_lead.tk.configured.get("height", panel._nav_lead.kwargs.get("height")),
        panel._nav_trail.tk.configured.get("height", panel._nav_trail.kwargs.get("height")),
    )


def _keyed(panel, px: int):
    """Draw the row's keys px tall, as the machine's own font would, and re-read the page."""
    panel._next_btn.tk.reqheight = px
    panel._show_page(panel.page_index)
    return panel


# What a key measures on each of the three screens the panel is drawn on, read back in a live
# window: the Pi draws the panel's largest text in its smallest pane, a Deck pane the smallest.
PI_KEY_PX = 68
DESK_KEY_PX = 52
DECK_KEY_PX = 39


@pytest.mark.parametrize("compact, key", [(False, PI_KEY_PX), (False, DESK_KEY_PX), (True, DECK_KEY_PX)])
def test_the_first_page_holds_the_row_of_keys_off_at_either_end(compact: bool, key: int) -> None:
    # The first page shows two keys with nothing between them and the list of modules above,
    # so they read as the last line of that list. The band is what stands them apart -- and it
    # is added to the gap every page already has above the row, where below the row the panel
    # has nothing of its own at all.
    panel, _body, _host = _build_with_body(compact=compact)

    _keyed(panel, key)

    assert _band(panel) == (panel._page_gap + panel._nav_band_px, panel._nav_band_px)


@pytest.mark.parametrize(
    "key, expected",
    [
        (DECK_KEY_PX, DECK_KEY_PX),
        (mod.NAV_BAND_PX, mod.NAV_BAND_PX),
        (DESK_KEY_PX, mod.NAV_BAND_PX),
        (PI_KEY_PX, mod.NAV_BAND_PX),
        # A key no screen has drawn yet, which is every key until the popup is laid out: the
        # cap is the one figure known to fit each of the three, so it is what is assumed.
        (0, mod.NAV_BAND_PX),
    ],
)
def test_the_band_is_a_keys_own_height_up_to_what_the_tightest_screen_can_spare(key: int, expected: int) -> None:
    # A key's height, because that is what a button's worth of room looks like and a key is
    # not the same height on two of these machines. Capped, because the Pi's first page has
    # only 104px of its pane going spare and a whole key at either end is 136 of it -- see
    # NAV_BAND_PX, which also records why the cap is a constant rather than that room read
    # off the pane as things stand.
    panel = _keyed(_new_panel(), key)

    assert panel._nav_band_px == expected
    assert panel._nav_band == expected


@pytest.mark.parametrize("compact, key", [(False, PI_KEY_PX), (False, DESK_KEY_PX), (True, DECK_KEY_PX)])
def test_the_row_of_keys_is_left_a_keys_worth_of_room_at_either_end(compact: bool, key: int) -> None:
    # The ask, in the terms it was asked in: at least a button's height of white space before
    # the row and after it. Counted as everything that stands between the page and the keys
    # and between the keys and Close -- the band, the row's own padding, and that button's
    # lead and padding -- because the band is only the part of it this panel had to add.
    # Measured on the three: 70px above the keys and 66 below either side of a 68px key on the
    # Pi, 51 and 51 either side of a 39px one on a Deck pane.
    panel, _body, _host = _build_with_body(compact=compact)
    _keyed(panel, key)
    lead, trail = _band(panel)

    above = lead + panel._nav_row_pad
    below = trail + panel._nav_row_pad + 2 * panel.footer_pad_px
    assert above >= key
    assert above + below >= 2 * key, "a key's worth at either end, taking the two together"


def test_no_page_but_the_first_is_given_the_band() -> None:
    # The other four are the fullest pages in the panel -- on the Pi the window already holds
    # the options page back by 10px and the review page by 82 -- so white space there would be
    # taken out of what is scrolled rather than out of anything going spare.
    panel = _keyed(_new_panel(), PI_KEY_PX)
    panel._on_device_selected(BPC2.key)
    plain = (panel._page_gap, 1)

    for index in (mod.PAGE_ID, mod.PAGE_OPTIONS, mod.PAGE_REVIEW, mod.PAGE_INVENTORY):
        panel._show_page(index)
        assert _band(panel) == plain, f"page {index} keeps the one gap it has always had"

    # And it is put back on coming back, which is the whole reason the pair is re-read on
    # every page turn rather than set once where they are built.
    panel._show_page(mod.PAGE_DEVICE)
    assert _band(panel) == (panel._page_gap + panel._nav_band_px, panel._nav_band_px)


def test_the_band_is_set_before_the_window_is_given_the_room_that_is_left() -> None:
    # Order, because the band is part of what the window's budget is measured against: set
    # after the fit, the room the page was offered would be a page's worth of white space out
    # of date until something else asked for a fit.
    panel = _keyed(_new_panel(), PI_KEY_PX)
    panel._on_device_selected(BPC2.key)
    # Away from the first page, so the band has to be put back during the turn under test
    # rather than being there already.
    panel._show_page(mod.PAGE_ID)
    seen: list[tuple[str, Any]] = []
    panel.scroll.fit = lambda budget=None: seen.append(("fit", _band(panel)))

    panel._show_page(mod.PAGE_DEVICE)

    assert seen == [("fit", (panel._page_gap + panel._nav_band_px, panel._nav_band_px))]


def test_the_gaps_are_not_re_sized_for_a_band_that_did_not_change() -> None:
    # A box re-sized asks Tk for a layout pass, and a layout pass is what asks the panel to
    # re-read itself: the same rule the space beside a page's key is kept by. Turning to the
    # first page from the first page is exactly the case -- the pad's own refreshes do it.
    panel = _keyed(_new_panel(), PI_KEY_PX)
    before = (len(panel._nav_lead.tk.configs), len(panel._nav_trail.tk.configs))

    for _ in range(3):
        panel._show_page(mod.PAGE_DEVICE)

    assert (len(panel._nav_lead.tk.configs), len(panel._nav_trail.tk.configs)) == before


def test_a_gap_that_will_not_take_the_band_costs_the_page_turn_nothing() -> None:
    # The band is set on a Tk option of a widget that may be gone by the time it is asked
    # for: the pair is re-read on every page turn, and a popup being torn down turns its
    # page one last time. White space is worth less than the turn it would take down with
    # it, so the one that answers is still given its half. The panel's other measured
    # layout, the space beside a page's key, is kept the same way.
    panel = _keyed(_new_panel(), PI_KEY_PX)
    panel._on_device_selected(BPC2.key)
    panel._show_page(mod.PAGE_ID)

    def _raise(**_kwargs: Any) -> None:
        raise mod.TclError("no such widget")

    panel._nav_lead.tk.config = _raise

    panel._show_page(mod.PAGE_DEVICE)  # must not raise

    assert panel.page_index == mod.PAGE_DEVICE
    assert _band(panel)[1] == panel._nav_band_px, "the half that can be set still is"


def test_a_key_no_screen_can_measure_leaves_the_band_at_the_cap() -> None:
    # Both of the ways there is no height to read. A key on a screen that will not answer for
    # it -- the reading is a Tk call, and a torn-down widget raises rather than returning a
    # number -- and a panel whose row of keys is not built yet, which is every panel between
    # being made and being handed a body to draw in. Neither is an answer of nothing: the cap
    # is the one figure known to fit each of the three screens, so it is what is assumed until
    # a real key says otherwise. See NAV_BAND_PX.
    panel = _new_panel()

    def _raise() -> int:
        raise mod.TclError("no such widget")

    panel._next_btn.tk.winfo_reqheight = _raise

    assert panel._nav_key_px == 0
    assert panel._nav_band_px == mod.NAV_BAND_PX

    bare = mod.LcsConfigPanel(_new_host())
    assert bare._nav_key_px == 0
    bare._refresh_nav_band()  # must not raise: there are no gaps to set yet
    assert bare._nav_band == 0


def test_the_panel_offers_no_footer_so_close_gets_a_line_of_its_own() -> None:
    # create_popup's other branch: with no footer to append Close to, it adds the plain
    # centered Close button to the overlay itself, below the panel's own content.
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


@pytest.mark.parametrize("linux", [True, False])
def test_the_panel_holds_the_screen_where_it_carries_its_own_way_off_it(monkeypatch, linux: bool) -> None:
    # The pane closes its popup whenever it re-reads what it has selected, and the layout
    # gives it every reason to while this panel is up -- most sharply when the module just
    # programmed is promoted into recents, which took the verdict off the screen before it
    # could be read. So the panel holds the screen against the layout; but only where the
    # operator can let it go, which is the same question has_close asks. Tied to it rather
    # than answered separately, so the two cannot come apart into a panel with no way out.
    monkeypatch.setattr(mod, "is_linux", lambda: linux, raising=True)
    panel = _new_panel()

    assert panel.closes_on_request_only is linux
    assert panel.closes_on_request_only is panel.has_close


def test_holding_the_screen_is_this_panel_and_no_other() -> None:
    # Every other popup is a view of what the pane has selected, and a view of the component
    # that *was* selected is worse than no view at all, so the base class goes quietly.
    panel = _new_panel()

    assert mod.OverlayPanel.closes_on_request_only.fget(panel) is False
    assert mod.LcsConfigPanel.closes_on_request_only is not mod.OverlayPanel.closes_on_request_only


def test_the_device_page_shows_my_modules_and_next() -> None:
    # There is nowhere to go back to from the first page, so Back is off the row entirely --
    # not grayed, and not standing in a placeholder of its own width. What stands in its
    # place is the key that opens the listing, left of Next: the row asks for no width, so it
    # shrinks to the pair of them and Tk centers it.
    panel = _new_panel()

    assert panel.page_index == mod.PAGE_DEVICE
    assert panel._back_btn.visible is False
    assert [child.text for child in panel._nav.children if child.visible] == [
        mod.INVENTORY_TEXT,
        mod.NEXT_TEXT,
    ]


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


def test_the_keys_are_created_in_the_order_they_are_read() -> None:
    # What the Pi showed: Back reappeared on the first page *after* Next. guizero re-packs a
    # container's children in creation order, so the order asserted here is the order the row
    # keeps however often a key leaves it and comes back -- which is what puts My Modules
    # left of Next rather than wherever it was last shown.
    panel = _new_panel()
    panel._on_device_selected("asc2")

    order = [mod.BACK_TEXT, mod.INVENTORY_TEXT, mod.NEXT_TEXT]
    for _ in range(3):
        panel.next_page()
    for _ in range(3):
        panel.previous_page()
        assert [child.text for child in panel._nav.children] == order
    # And back at the first page, where the key is shown and Back is not, it is the left of
    # the two the row is showing.
    assert [child.text for child in panel._nav.children if child.visible] == [
        mod.INVENTORY_TEXT,
        mod.NEXT_TEXT,
    ]


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
    # The panel's own rows, never the popup's overlay: the keys live here now. The ID page's
    # pair of choices is the other row that shows and hides a styled key; see
    # test_the_white_space_between_the_two_choices_survives_them_being_shown.
    assert set(calls) == {panel._nav, panel._choice_row}


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


def test_next_leaves_the_row_on_the_page_it_could_never_lead_off() -> None:
    # The review page is the last, so Next there is a key with nowhere to go -- and one taken
    # off the row says that plainly, where one left standing gray invites a press and asks the
    # operator to work out why nothing happened. Which is what Back has always done on the
    # first page: the two ends of the panel now read alike. Configure is what that page
    # offers, and it is on the page itself.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)

    panel._show_page(mod.PAGE_REVIEW)

    assert panel.has_next_page is False
    assert panel._next_btn.visible is False
    # Disabled as well as hidden, though nothing can press it: a button whose look and whose
    # state disagree is one the next reader has to reason about.
    assert panel._next_btn.enabled is False
    assert [child.text for child in panel._nav.children if child.visible] == [mod.BACK_TEXT]

    panel.previous_page()

    assert (panel._next_btn.visible, panel._next_btn.enabled) == (True, True)
    assert [child.text for child in panel._nav.children if child.visible] == [mod.BACK_TEXT, mod.NEXT_TEXT]


def test_next_stands_grayed_where_there_is_a_page_but_nothing_to_go_on_with() -> None:
    # Shown and enabled are two questions, and the first page is where they part company:
    # there is a page after it whether or not a module has been chosen, so Next belongs on
    # the row -- grayed until there is something to configure. Taken off here it would leave
    # the opening page with no key on it at all, and that page's only way forward is Next.
    panel = _new_panel()

    assert panel.has_next_page is True
    assert (panel._next_btn.visible, panel._next_btn.enabled) == (True, False)

    panel._on_device_selected(BPC2.key)
    # The row is redrawn as a page turns, which is what the panel does with it; asked for
    # directly here because the point is the answer, not when it is asked.
    panel._refresh_nav()

    assert (panel._next_btn.visible, panel._next_btn.enabled) == (True, True)


@pytest.mark.parametrize(
    "compact, expected",
    [(False, mod.NAV_ROW_PAD), (True, mod.NAV_ROW_PAD_COMPACT)],
)
def test_the_nav_row_gives_back_the_footer_bands_vertical_padding(monkeypatch, compact: bool, expected: int) -> None:
    # Back and Next wear the shared footer look, but they are not in the popup's footer band:
    # Close is, below them, with its own lead and padding. A footer button's 20px above and
    # below, taken three times down one overlay, is what pushed Close off the ID page.
    #
    # Configure gives it back for the same reason and by the same number: it wears that look
    # too, and it stands in the middle of a page with a line of its own above and below it,
    # where a footer band's whitespace is a gap in the middle of the reading rather than the
    # room around a row of keys.
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(mod, "repad_footer_button", lambda btn, **kw: calls.append((btn.text, kw)), raising=True)

    _build_with_body(compact=compact)

    assert calls == [
        # The ID page's two choices give back the horizontal band as well, that being what
        # holds them apart rather than what holds a row off the pane; see the test below.
        ("Go to", {"padx": mod.CHOICE_KEY_PAD, "pady": expected}),
        ("Configure as new", {"padx": mod.CHOICE_KEY_PAD, "pady": expected}),
        (mod.CONFIGURE_TEXT, {"pady": expected}),
        (mod.BACK_TEXT, {"pady": expected}),
        (mod.INVENTORY_TEXT, {"pady": expected}),
        (mod.NEXT_TEXT, {"pady": expected}),
    ]
    # For a key that stands alone on its row, horizontal padding is untouched: it is the gap
    # between the keys of a row, and there is no second key beside any of these four.
    alone = (mod.CONFIGURE_TEXT, mod.BACK_TEXT, mod.INVENTORY_TEXT, mod.NEXT_TEXT)
    assert all("padx" not in kwargs for text, kwargs in calls if text in alone)


@pytest.mark.parametrize(
    "compact, expected",
    [(False, mod.NAV_ROW_PAD), (True, mod.NAV_ROW_PAD_COMPACT)],
)
def test_the_band_below_the_row_is_the_rows_own_whitespace(compact: bool, expected: int) -> None:
    # What the popup puts between this row and the Close below it. The shared band is not
    # wrong, it is answering a different question -- it holds a panel's buttons off the panel
    # -- and what is above Close here is not a panel but another row of buttons, already held
    # off the page by PAGE_GAP. One number for all three gaps, so the two read as a pair of
    # rows: on a portrait pane 24px of lead and 20px above and below Close became 6px apiece,
    # which measured out as 46px more page -- the worst page the Pi holds any of back went
    # from 124px to 78px.
    host = _new_host()
    host.compact = compact
    panel = mod.LcsConfigPanel(host)

    assert panel.footer_pad_px == expected
    # Less than the popup would otherwise put there, on either pane -- which is the whole of
    # what asking buys, and the direction it has to be in.
    assert panel.footer_pad_px < pm.FOOTER_LEAD_COMPACT < pm.FOOTER_LEAD


def test_the_row_holds_its_keys_and_nothing_else() -> None:
    # No placeholder standing in for Back. It bought Next a fixed x at the cost of a
    # Back-shaped hole beside it on the first page, and of a second widget that had to be
    # shown exactly when Back was not. Nor a spacer beside My Modules: this row is centered
    # on the pane already, which is the whole of what the gutter on a page's key is for.
    panel = _new_panel()

    assert [type(child).__name__ for child in panel._nav.children] == ["DummyHoldButton"] * 3


#
# The ID page names the module
#
def test_the_id_heading_names_the_selected_module() -> None:
    panel = _new_panel()

    assert panel._id_heading.value == mod.ID_HEADING.format(module=mod.ID_HEADING_FALLBACK)

    panel._on_device_selected("bpc2")
    assert panel.id_heading_text == mod.ID_HEADING.format(module=BPC2.label)
    assert panel._id_heading.value == panel.id_heading_text
    # The module named is the one selected, and the heading the page was built with is gone.
    assert BPC2.label in panel._id_heading.value
    assert mod.ID_HEADING_FALLBACK not in panel._id_heading.value

    panel._on_device_selected("stm2")
    assert panel._id_heading.value == mod.ID_HEADING.format(module=STM2.label)
    assert BPC2.label not in panel._id_heading.value


def test_the_editors_own_header_is_named_with_the_heading() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert panel._id_field.field_name == mod.ID_HEADING.format(module=BPC2.label)
    assert panel._id_field.field_name == panel.id_heading_text


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


@pytest.mark.parametrize("linux", [True, False])
def test_the_id_box_opens_for_typing_on_a_press(monkeypatch, linux: bool) -> None:
    # A box drawn to look like a text field is tapped, not leaned on, so the press opens it on
    # the Pi and the Deck as well as on a desktop -- it used to be bound only where there is a
    # mouse, leaving a second of press-and-hold as the appliance's only way in. What the
    # platform still decides is which editor then appears; see the parametrized test above.
    monkeypatch.setattr(mod, "is_linux", lambda: linux, raising=True)
    panel = _new_panel()

    bound = {event: func for event, func, _add in panel._id_field.tk.binds}
    assert "<Button-1>" in bound

    bound["<Button-1>"](None)
    assert panel._id_field.edits == 1


@pytest.mark.parametrize("linux", [True, False])
def test_the_press_leaves_the_components_own_hold_alone(monkeypatch, linux: bool) -> None:
    # <Button-1> is the same Tk sequence EditableText presses on to time its hold, and a bind
    # replaces whatever is on a sequence unless it asks to be added to it. Bound additively,
    # so the component's handler still runs -- begin_edit cancels the timer that press starts,
    # which is what lets both gestures live on the one widget.
    monkeypatch.setattr(mod, "is_linux", lambda: linux, raising=True)
    panel = _new_panel()

    assert [add for event, _func, add in panel._id_field.tk.binds if event == "<Button-1>"] == ["+"]


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
    # size -- as do the module rows on the page before, the choice being made there. Both
    # lists are aimed at with a finger on the two screens that have no keyboard: a list of
    # touch targets is not a caption. The module rows ask for a step more still, being the
    # shortest rows in the panel where a mode's row carries a block of TMCC IDs too.
    panel = _new_panel()
    host = panel.gui

    assert panel._mode_group.kwargs["size"] == host.s_18
    assert panel._mode_group.kwargs["size"] > host.s_14
    assert panel._device_group.kwargs["size"] == host.s_20
    assert panel._device_group.kwargs["size"] > panel._mode_group.kwargs["size"]


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
    # page body, so a painted indicator that grows with it -- while the device page has
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


def test_the_module_rows_are_body_size_and_the_mode_boxs_prose_below_it() -> None:
    # The rows name what already answers to this ID, which is the answer the operator came
    # to the page for. The two lines either side of the mode radios are captions on them --
    # context, not a choice -- and the quietest thing on the page.
    store = FakeStore({CommandScope.ACC: [FakeState(30, "is_bpc2", mode=2, num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")
    panel._set_base_id(25)  # the BPC2 at 30-37 runs into 25-32, so the Overlaps box speaks
    host = panel.gui

    assigned = panel._assigned_cells[0]
    assert [cell.text_size for cell in assigned] == [host.s_14] * mod.ROW_COLUMNS
    # The two boxes read as one list, so their rows are the same size.
    assert all(cell.text_size == host.s_14 for cell in panel._overlap_cells[0])
    # The legend is the longer of the two and is read before a row is chosen, so it is the
    # one drawn a step above the note below the rows -- and both still below the rows they
    # caption.
    assert panel._mode_legend_line.text_size == host.s_13
    assert panel._mode_note_line.text_size == host.s_10
    for line in (panel._mode_legend_line, panel._mode_note_line):
        assert line.text_size < assigned[0].text_size


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
    # A title of its own, and not the one the box below it carries: the two boxes answer
    # different questions, which is why there are two of them.
    assert mod.ASSIGNED_TITLE and mod.ASSIGNED_TITLE != mod.OVERLAP_TITLE
    assert panel._assigned_grid in panel._assigned_box.children
    assert all(cell in panel._assigned_grid.children for cell in panel._assigned_cells[0])


def test_an_unassigned_id_says_so_rather_than_going_blank() -> None:
    # The box is always shown, so an empty line inside a titled frame would read as a
    # failure to look rather than as an answer.
    panel = _new_panel()

    # Not the spelling of it but the part it plays: it is what the row's module cell holds
    # when nobody answers to the ID, and it is what marks the row as the one that is not a
    # module in the way.
    assert _assigned(panel) == [mod.UNASSIGNED]
    assert mod.ModuleRow(scope="", module=mod.UNASSIGNED).is_unassigned is True
    assert panel._assigned_box.visible is True


@pytest.mark.parametrize(
    "scope, flag, mode, num_ids, device_key, expected",
    [
        (CommandScope.ACC, "is_asc2", 0, 8, "asc2", _row(CommandScope.ACC, ASC2.label, 20, 8)),
        (CommandScope.SWITCH, "is_stm2", 1, 8, "stm2", _row(CommandScope.SWITCH, STM2.label, 20, 8)),
        (CommandScope.TRAIN, "is_bpc2", 0, 8, "bpc2", _row(CommandScope.TRAIN, BPC2.label, 20, 8)),
        (
            CommandScope.ACC,
            "is_sensor_track",
            None,
            1,
            "sensor_track",
            _row(CommandScope.ACC, SENSOR_TRACK.label, 20),
        ),
    ],
)
def test_an_assigned_id_names_the_module_its_remote_key_and_its_block(
    scope: CommandScope, flag: str, mode: Any, num_ids: int, device_key: str, expected: str
) -> None:
    # The remote key is the point of the line: it is how the operator addresses whatever
    # is already there. A single-port module names the one address it holds rather than a
    # range of one. Each module is looked for while programming a module on its own key,
    # because that is the only time it can be in the way.
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
    assert [cell.value for cell in (key, module, ids)] == list(_row_cells(CommandScope.ACC, ASC2.label, 9, 8))
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

    assert [cell.value for cell in panel._assigned_cells[0]] == list(_row_cells(CommandScope.ACC, ASC2.label, 9, 8))
    # The one word kept here, because what is being asserted is that the panel never says
    # it: no source owns a term its author refuses to use.
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
    # Its own title, as the box above it has its own: see the assigned box's counterpart.
    assert mod.OVERLAP_TITLE and mod.OVERLAP_TITLE != mod.ASSIGNED_TITLE
    assert panel._overlap_grid in panel._overlap_box.children
    assert all(cell in panel._overlap_grid.children for cell in panel._overlap_cells[0])


def test_each_module_in_the_way_gets_a_row_of_its_own() -> None:
    # Run together on one line, two neighbors ran off the right edge of the window; a row
    # each also lines their columns up the way the assigned box lines up its own.
    panel = _new_panel(_overlapping_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(25)

    assert _overlaps(panel) == [
        _row(CommandScope.ACC, BPC2.label, 26, 8),
        _row(CommandScope.ACC, ASC2.label, 30, 8),
    ]
    # The title carries the word for what these rows are, so no row repeats it.
    assert not any(mod.OVERLAP_TITLE in row for row in _overlaps(panel))
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
    assert _overlaps(panel) == [_row(CommandScope.ACC, BPC2.label, 26, 8)]
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


class FakePdiPacket:
    """One module's own CONFIG request: a Bpc2Req for a BPC2, an IrdaReq for a Sensor Track.

    Where a module's settings are, the mode among them. A BPC2's restore-on-power-up flag
    is the top bit of its mode byte, and Bpc2Req is what unpacks the two apart; a Sensor
    Track's Action Command is the sequence field of its own record.

    An AMC2 names nothing the way the others do: which of the three address types it
    answers to stands where their mode byte stands, and each motor's own settings are on
    the motor. Both are given the module's own names and shapes, so a record read for an
    AMC2 is read by the paths the registry declares rather than by paths written to suit
    the fake. The motors are the real Amc2Motor, which is a plain dataclass.
    """

    def __init__(
        self,
        mode: int | None = None,
        restore: bool | None = None,
        sequence: Any = None,
        access_type: AccessType | None = None,
        motors: tuple[Amc2Motor, ...] = (),
    ) -> None:
        # The flavor the request was built as, which every PDI request carries under the
        # name "action" -- and that is the very word the Sensor Track's Action Command
        # option is keyed by, so the record answers about that option only on the field the
        # option says the module reports it on. Stood in for here as the module's own CONFIG
        # action, since what matters is the name rather than which enum it belongs to.
        self.action = IrdaAction.CONFIG if sequence is not None else Bpc2Action.CONFIG
        if mode is not None:
            self.mode = mode
        if restore is not None:
            # Only a BPC2's request carries one.
            self.restore = restore
        if sequence is not None:
            # And only a Sensor Track's.
            self.sequence = sequence
        if access_type is not None or motors:
            self.action = Amc2Action.CONFIG
        if access_type is not None:
            self.access_type = access_type
        for i, motor in enumerate(motors, start=1):
            setattr(self, f"motor{i}", motor)


class FakePdiConfig:
    """The PDI store's entry for one module, as PdiDeviceConfig presents it.

    Built from the CONFIG request the module answered with, which it holds on config, and
    republishing that request's mode byte -- which is the whole of what PdiDeviceConfig
    republishes, so the settings can be read only from the request itself.
    """

    def __init__(
        self,
        tmcc_id: int,
        scope: CommandScope,
        mode: int | None = None,
        restore: bool | None = None,
        sequence: Any = None,
        access_type: AccessType | None = None,
        motors: tuple[Amc2Motor, ...] = (),
    ) -> None:
        self.tmcc_id = tmcc_id
        self.scope = scope
        if mode is not None:
            # Only ASC2, BPC2 and STM2 configs carry a mode; an AMC2's does not.
            self.mode = mode
        self.config = FakePdiPacket(mode, restore, sequence, access_type, motors)


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

    assert _assigned(panel) == [
        _row(CommandScope.ACC, BPC2.label, 1, 8),
        _row(CommandScope.ACC, AMC2.label, 1),
    ]


def test_the_shared_record_alone_could_not_say_that(monkeypatch) -> None:
    # Why the PDI store is read first: from the record they share, the AMC2 is invisible and
    # the BPC2 claims the single ID that record happens to be carrying.
    from src.pytrain.gui.controller import lcs_id_map

    monkeypatch.setattr(lcs_id_map, "_pdi_store", lambda pdi_store=None: None, raising=True)
    panel = _new_panel(_shared_acc_1_record())
    panel._on_device_selected("asc2")
    panel._set_base_id(1)

    assert _assigned(panel) == [_row(CommandScope.ACC, BPC2.label, 1)]


def test_an_id_inside_the_true_block_is_reported_against_that_block(monkeypatch) -> None:
    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2)]})
    panel = _new_panel(_shared_acc_1_record())
    panel._on_device_selected("asc2")
    panel._set_base_id(5)

    # The module's real range, from its own CONFIG packet, which is the whole point of
    # reading the PDI store first: the shared record would have said one ID.
    assert _assigned(panel) == [_row(CommandScope.ACC, BPC2.label, 1, 8)]
    assert _says_with_id(panel._goto_btn, 1)


def test_every_module_on_the_id_gets_a_row_of_its_own() -> None:
    # Naming only the first would tell the operator half the truth about the address.
    panel = _new_panel(_amc2_and_bpc2_at_1_store())
    panel._on_device_selected("asc2")  # accessory mode: the same remote key as both
    panel._set_base_id(1)

    assert _assigned(panel) == [
        _row(CommandScope.ACC, BPC2.label, 1),
        _row(CommandScope.ACC, AMC2.label, 1),
    ]
    assert [cell.grid for cell in panel._assigned_cells[1]] == [[0, 1], [1, 1], [2, 1]]


def test_a_module_this_pass_cannot_program_is_named_but_never_seeded_from(monkeypatch) -> None:
    # A module in the registry to be recognized rather than configured is reported, is not
    # offered on the device page, and the panel will not open on it even where opening on
    # the module at the ID is the rule.
    _appliance(monkeypatch)
    recognized = _recognized_only(monkeypatch)
    panel = _new_panel(FakeStore({CommandScope.ACC: [FakeState(1, "is_amc2", num_ids=1)]}))
    panel.configure(CommandScope.ACC, 1, None)

    assert _assigned(panel) == [_row(CommandScope.ACC, recognized.label, 1)]
    assert panel.device is _first_offered()
    assert recognized.key not in [value for _label, value in mod.LcsConfigPanel.device_options()]
    # And the guard is not decorative: there is genuinely no mode to have opened on, and it
    # is this module the complaint names.
    with pytest.raises(ValueError) as raised:
        panel._select_device(recognized)
    assert recognized.label in str(raised.value)


def test_opening_the_panel_from_an_amc2_screen_opens_it_on_the_amc2(monkeypatch) -> None:
    # Pressing LCS... with an AMC2 on screen hands the panel an AMC2 state, and an AMC2 is
    # now a module the panel can program -- so it opens on that module, at that address, on
    # the one key it is offered on, exactly as it does for every other module the operator
    # was already looking at.
    _appliance(monkeypatch)
    state = FakeState(1, "is_amc2", num_ids=1)
    panel = _new_panel(FakeStore({CommandScope.ACC: [state]}))

    panel.configure(CommandScope.ACC, 1, state)

    assert panel.device is AMC2
    assert panel.mode is AMC2.mode("acc")
    assert panel.base_id == 1
    assert panel._device_group.value == AMC2.key
    assert panel.page_index == mod.PAGE_DEVICE
    assert _assigned(panel) == [_row(CommandScope.ACC, AMC2.label, 1)]


def test_the_amc2_is_offered_on_the_accessory_key_alone(monkeypatch) -> None:
    # Its manual programs it as a TR or an ENG device as readily as an ACC one, and the
    # registry records both -- but nothing else in PyTrain drives an AMC2 addressed as a
    # train or an engine, so the panel offers no row that would put one there. What is not
    # offered is not mentioned either: a row an operator cannot choose is not a fact they
    # can act on.
    _appliance(monkeypatch)
    panel = _new_panel()
    panel._on_device_selected(AMC2.key)

    assert [key for _label, key in _mode_options(AMC2, panel.base_id)] == ["acc"]
    assert {mode.key for mode in AMC2.modes if not mode.enabled} == {"tr", "eng"}
    assert panel.mode_legend == mod.scope_use(CommandScope.ACC)
    assert "TR" not in panel.mode_legend
    assert "ENG" not in panel.mode_legend


def test_an_amc2_addressed_as_a_train_is_not_opened_on_a_mode_the_panel_cannot_offer(monkeypatch) -> None:
    # A module found running in a mode the panel does not offer is opened on the row it can
    # be reprogrammed as. Left on the mode it was found in, the radios would show no row
    # selected -- there being no row for it -- and Configure would send that mode's opening
    # SET press and nothing after it, which is a module half programmed.
    _appliance(monkeypatch)
    _with_pdi_store(
        monkeypatch,
        {PdiDevice.AMC2: [FakePdiConfig(5, CommandScope.TRAIN, access_type=AccessType.TRAIN)]},
    )
    panel = _new_panel()

    panel.configure(CommandScope.TRAIN, 5, None)
    panel._on_device_selected(AMC2.key)

    assert panel.mode is AMC2.mode("acc")
    assert panel.mode.enabled is True


def test_the_choice_buttons_ignore_a_module_that_cannot_be_programmed(monkeypatch) -> None:
    # Interior of the block of a module the panel can only recognize: there is nothing to go
    # to and nothing to take over, so neither button appears -- the buttons offer to program
    # a module, and this is one no sequence has been written for.
    recognized = _recognized_only(monkeypatch)
    store = FakeStore({CommandScope.ACC: [FakeState(1, "is_amc2", num_ids=8)]})
    panel = _new_panel(store)
    panel._on_device_selected("asc2")
    panel._set_base_id(4)

    assert _assigned(panel) == [_row(CommandScope.ACC, recognized.label, 1, 8)]
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
# The mode the module already at the address is in
#
def _bpc2_based_at(monkeypatch, base_id: int, mode: reg.LcsMode, restore: bool = False) -> None:
    """A BPC2 based at base_id, running in the given mode, as the PDI bus reported it.

    Keyed and filed from the registry's own facts about the mode -- its PDI mode byte and
    the remote key it puts the module on -- so the store says what the mode says and the
    assertions can be about the panel landing on it.
    """
    _with_pdi_store(
        monkeypatch,
        {PdiDevice.BPC2: [FakePdiConfig(base_id, mode.scope, mode=mode.pdi_mode, restore=restore)]},
    )


def _mode_the_page_does_not_open_on() -> reg.LcsMode:
    """A BPC2 mode other than the row the page opens on where the layout says nothing.

    Landing on it is a read of the module and can be nothing else: the default row is where
    the panel would have been standing anyway. Which of the two addressing modes that is is
    the registry's to order -- the rows read ACC and then TR today -- so it is asked for
    rather than named, and reordering them cannot quietly empty these tests.
    """
    return next(mode for mode in reg.enabled_modes(BPC2) if mode is not BPC2.default_mode)


def test_the_mode_radios_open_on_the_mode_the_module_is_running_in(monkeypatch) -> None:
    # Which mode a module is in is a fact about the module, recorded in its own CONFIG
    # packet, so the page that offers to reprogram it opens on that row rather than on the
    # module's default one -- which would re-address it onto a remote key it was never on.
    # The reported layout, a BPC2 addressed as an accessory holding ACC 1 - 8, is the row
    # the page opens on anyway, so the reading is shown here on the module's other mode.
    read = _mode_the_page_does_not_open_on()
    _bpc2_based_at(monkeypatch, 1, read)
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(1)

    assert panel.mode is read
    assert panel._mode_group.value == read.key
    # And with the mode, everything the page draws from it: the key the boxes search, so the
    # module is reported as the one being reconfigured rather than passed over as something
    # on another key, and the block the heading of the next page names.
    assert panel.scope is read.scope
    assert _assigned(panel) == [_row(read.scope, BPC2.label, 1, read.ports)]
    assert panel.options_summary == mod.CONFIGURING.format(
        module=BPC2.label,
        block=f"{mod.SCOPE_LABEL[read.scope]} {reg.tmcc_id_span(1, read.ports)}",
    )


def test_the_settings_are_read_off_the_module_on_the_key_it_reported(monkeypatch) -> None:
    # The mode is read before the options are, so the module the settings are read off is
    # the one on the key the layout reported -- which need not be the key the radios opened
    # on. A BPC2 running with restore on opens with its own row selected and its box ticked.
    #
    # In the single pass over the page that picking the module sets off, and asserted after
    # that one pass: from here the operator can walk straight on to the Options page, which
    # is shown as it was last written rather than written again on the way.
    read = _mode_the_page_does_not_open_on()
    _bpc2_based_at(monkeypatch, 1, read, restore=True)
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert panel.base_id == 1
    assert panel.mode is read
    assert panel.reconfigured_occupant().base_id == 1
    assert panel.options["restore"] is True
    assert panel._option_widgets[("bpc2", "restore")].value == 1


def test_the_mode_the_operator_picks_is_not_read_over(monkeypatch) -> None:
    # The radios are how the operator says what the module is to become, which need not be
    # what it is now: re-addressing a BPC2 from ACC to TR is the very thing the page is for.
    read, chosen = _mode_the_page_does_not_open_on(), BPC2.default_mode
    _bpc2_based_at(monkeypatch, 1, read)
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(1)
    assert panel.mode is read

    panel._on_mode_selected(chosen.key)
    panel._set_base_id(1)  # every refresh of the page runs the seeding again

    assert panel.mode is chosen
    # And it stands at another address as well: the choice is about the module, not about
    # the address it is being given.
    panel._set_base_id(20)
    panel._set_base_id(1)
    assert panel.mode is chosen


def test_choosing_another_module_reads_the_layout_afresh(monkeypatch) -> None:
    # A mode picked among one module's rows says nothing about another module's, so picking
    # a module starts the reading over -- as it does for that module's settings.
    read = _mode_the_page_does_not_open_on()
    _bpc2_based_at(monkeypatch, 1, read)
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._on_mode_selected(BPC2.default_mode.key)

    panel._on_device_selected("asc2")
    panel._on_device_selected("bpc2")

    assert panel.mode is read


def test_a_module_of_another_type_at_the_address_leaves_the_radios_alone(monkeypatch) -> None:
    # An STM2 based at SW 1 says nothing about how a BPC2 should be addressed, and its own
    # mode is not one of the BPC2's rows in any case.
    two_wire = STM2.mode("two_wire")
    _with_pdi_store(
        monkeypatch,
        {PdiDevice.STM2: [FakePdiConfig(1, two_wire.scope, mode=two_wire.pdi_mode)]},
    )
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(1)

    assert panel.mode is BPC2.default_mode


def test_an_id_inside_the_block_is_not_the_module_and_leaves_the_radios_alone(monkeypatch) -> None:
    # A module the ID merely falls inside is based somewhere else, so its mode is not read
    # there. The panel offers to go to that base, and going there is where it is read.
    _bpc2_based_at(monkeypatch, 12, _mode_the_page_does_not_open_on())
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(15)

    assert panel._based_here(None) is None
    assert panel.mode is BPC2.default_mode


def test_a_mode_read_off_a_module_stays_put_at_an_address_nothing_answers_to(monkeypatch) -> None:
    # Unlike a setting, which is given back its default there. The radios always show one row
    # or another, so what is shown at an address nothing is known about is a guess either way,
    # and the last thing the layout said is a better guess than the factory default. Flipping
    # them back under the operator's hand as they step the ID would also swing the key the two
    # module boxes search, emptying them mid-step. See _seed_options_from_layout.
    read = _mode_the_page_does_not_open_on()
    _bpc2_based_at(monkeypatch, 1, read, restore=True)
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(1)
    assert (panel.mode, panel.options["restore"]) == (read, True)

    panel._set_base_id(20)

    assert _assigned(panel) == [mod.UNASSIGNED]
    assert panel.mode is read
    assert panel.options["restore"] is BPC2.option("restore").default


def test_a_module_running_in_a_mode_the_manual_reserves_leaves_the_radios_alone(monkeypatch) -> None:
    # A reserved mode is on no radio row, so there is nothing to select; the module is left
    # to the row it can be reprogrammed as. See LcsMode.enabled.
    reserved = next(mode for mode in BPC2.modes if not mode.enabled)
    _bpc2_based_at(monkeypatch, 1, reserved)
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(1)

    assert panel._based_here(None).mode is reserved
    assert panel.mode is BPC2.default_mode


def test_the_mode_is_read_again_once_the_base_has_reported(monkeypatch) -> None:
    # The panel can be opened while the store is still filling; what it read off an empty
    # layout was nothing, so synchronization is where the module's mode is finally read.
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(1)
    assert panel.mode is BPC2.default_mode

    read = _mode_the_page_does_not_open_on()
    _bpc2_based_at(monkeypatch, 1, read)
    panel.on_synchronized()

    assert panel.mode is read


#
# What the module already at the address is set to
#
def _bpc2_at_12_holding(monkeypatch, restore: bool) -> None:
    """A BPC2 based at 12, running with restore on or off, as the PDI bus reported it.

    In the mode the panel opens a BPC2 on, so what these tests read is the flag alone and
    never the mode being read with it; that is the section above.
    """
    _bpc2_based_at(monkeypatch, 12, BPC2.default_mode, restore)


@pytest.mark.parametrize("restore", [True, False])
def test_the_restore_box_shows_what_the_bpc2_at_the_address_is_holding(monkeypatch, restore: bool) -> None:
    # No component state at all here, and none is needed: the flag is a bit of the mode byte
    # in the module's own CONFIG packet, and the PDI store is the only place it is recorded.
    _bpc2_at_12_holding(monkeypatch, restore)
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)

    assert panel.reconfigured_occupant().base_id == 12
    assert panel.options["restore"] is restore
    assert panel._option_widgets[("bpc2", "restore")].value == (1 if restore else 0)
    # And the presses follow it, so leaving the box alone reprograms the module as it stands:
    # the press the registry gates on the flag is there when it is set and not when it is not.
    gated = next(press for press in BPC2.default_mode.presses if press.include_if == "restore")
    assert any(gated.label in line for line in panel.review_lines) is restore


def test_only_the_module_at_the_address_is_read_and_only_on_the_key_being_programmed(monkeypatch) -> None:
    # The module in hand is the one based at the entered ID on the key being programmed.
    # A BPC2 based at 12 says nothing about the same address on its other remote key, which
    # is a different address on a different module, and nothing about 15, which is inside
    # its block but not its base -- the panel offers to go to the base for that.
    opened, other = BPC2.default_mode, _mode_the_page_does_not_open_on()
    _bpc2_at_12_holding(monkeypatch, True)
    panel = _new_panel()
    panel._on_device_selected("bpc2")  # the same mode the module is in
    panel._set_base_id(15)

    assert _assigned(panel) == [_row(opened.scope, BPC2.label, 12, opened.ports)]
    assert panel.reconfigured_occupant() is None
    assert panel.options["restore"] is BPC2.option("restore").default

    panel._on_mode_selected(other.key)
    panel._set_base_id(12)

    assert panel.scope is other.scope
    assert panel.reconfigured_occupant() is None
    assert panel.options["restore"] is BPC2.option("restore").default


def test_a_setting_read_off_one_module_is_not_carried_to_an_empty_address(monkeypatch) -> None:
    # It was a fact about the module it was read from. Carried along, it would be programmed
    # into a module the operator never said it about.
    _bpc2_at_12_holding(monkeypatch, True)
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)
    assert panel.options["restore"] is True

    panel._set_base_id(30)

    assert _assigned(panel) == [mod.UNASSIGNED]
    assert panel.options["restore"] is BPC2.option("restore").default is False
    # And reading the module again is all it takes to have it back.
    panel._set_base_id(12)
    assert panel.options["restore"] is True


def test_what_the_operator_sets_is_not_read_over_while_the_panel_stays_on_the_address(monkeypatch) -> None:
    # The box is the setting about to be programmed as well as a report of the one in force,
    # so a tick made against the address in hand stands until the panel is aimed elsewhere.
    _bpc2_at_12_holding(monkeypatch, True)
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)

    panel._option_widgets[("bpc2", "restore")].value = 0
    panel._on_option_changed("bpc2", "restore")
    panel._set_base_id(12)  # every refresh of the page runs the seeding again

    assert panel.options["restore"] is False
    # A choice of the operator's own at an address nothing answers to is theirs to keep too:
    # nothing was read there, so there is nothing to give back.
    panel._set_base_id(30)
    panel._option_widgets[("bpc2", "restore")].value = 1
    panel._on_option_changed("bpc2", "restore")
    panel._set_base_id(31)

    assert panel.options["restore"] is True


def test_the_module_is_read_again_once_the_base_has_reported(monkeypatch) -> None:
    # The panel can be opened while the store is still filling; what it read off an empty
    # layout was nothing, so synchronization is where the module is finally read.
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._set_base_id(12)
    assert panel.options["restore"] is False

    _bpc2_at_12_holding(monkeypatch, True)
    panel.on_synchronized()

    assert panel.options["restore"] is True


def test_a_module_of_another_type_at_the_address_is_not_read_for_its_settings(monkeypatch) -> None:
    # Read by the option's key, an AMC2's record could answer for a name a BPC2's option
    # happens to share -- so only the module of the type being programmed is read at all.
    _with_pdi_store(
        monkeypatch,
        {PdiDevice.AMC2: [FakePdiConfig(12, CommandScope.ACC, restore=True)]},
    )
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    panel._on_mode_selected("acc_8")
    panel._set_base_id(12)

    assert _assigned(panel) == [_row(CommandScope.ACC, AMC2.label, 12)]
    assert panel.reconfigured_occupant() is None
    assert panel.options["restore"] is False


def _sensor_track_based_at(monkeypatch, base_id: int, sequence: IrdaSequence) -> None:
    """A Sensor Track based at base_id, set to sequence, as the PDI bus reported it.

    Filed under the scope its own requests carry, the IRDA key, rather than the accessory
    key it is addressed on: which remote key addresses a module is the registry's to say,
    and the panel finds the record either way. See LcsOccupant.effective_scope.
    """
    _with_pdi_store(
        monkeypatch,
        {PdiDevice.IRDA: [FakePdiConfig(base_id, CommandScope.IRDA, sequence=sequence)]},
    )


def _amc2_based_at(monkeypatch, base_id: int, motors: tuple[Amc2Motor, ...]) -> None:
    """An AMC2 based at base_id running those motors, as the PDI bus reported it.

    Addressed as an accessory, which is the one way the panel offers -- and said as the
    module says it, an AccessType rather than a mode byte, because what the panel has to
    read is what the module publishes.
    """
    _with_pdi_store(
        monkeypatch,
        {PdiDevice.AMC2: [FakePdiConfig(base_id, CommandScope.ACC, access_type=AccessType.ACC, motors=motors)]},
    )


def test_the_motor_rows_show_what_the_amc2_at_the_address_is_running(monkeypatch) -> None:
    # Both motors, each read off the motor itself: an AMC2 reports its settings one level
    # down from the record it answers with, and the two are told apart by nothing but which
    # motor they are on. Read there, the page opens on what the module is running rather
    # than on the option's own default -- which, this being a single operation that sets
    # both motors, would otherwise reprogram the far motor the moment the near one was
    # changed.
    _amc2_based_at(monkeypatch, 5, (_motor(1, OutputType.AC, restore=True), _motor(2, OutputType.DELTA)))
    panel = _new_panel()
    panel._on_device_selected(AMC2.key)
    panel._set_base_id(5)

    assert panel.reconfigured_occupant().base_id == 5
    assert panel.options["motor1_mode"] is OutputType.AC
    assert panel.options["motor1_restore"] is True
    assert panel.options["motor2_mode"] is OutputType.DELTA
    assert panel.options["motor2_restore"] is False
    for motor, output_type in ((1, OutputType.AC), (2, OutputType.DELTA)):
        option = AMC2.option(f"motor{motor}_mode")
        assert output_type is not option.default  # or the row would be selected without being read
        row = [value for _label, value in option.choices].index(output_type)
        assert panel._option_widgets[(AMC2.key, option.key)].value == str(row)
    assert panel._option_widgets[(AMC2.key, "motor1_restore")].value == 1
    assert panel._option_widgets[(AMC2.key, "motor2_restore")].value == 0
    # And the presses follow, so leaving the page alone reprograms the module as it stands.
    assert panel.review_lines == _press_lines(AMC2.mode("acc"), 5, panel.options)


def test_an_amc2_that_has_reported_no_motors_leaves_them_at_their_defaults(monkeypatch) -> None:
    # A record built from a GET the module has not answered yet carries no motors at all,
    # and a path that runs out is the module saying nothing rather than saying zero -- which
    # would read as the first mode on the list and be programmed in as though chosen.
    _amc2_based_at(monkeypatch, 5, ())
    panel = _new_panel()
    panel._on_device_selected(AMC2.key)
    panel._set_base_id(5)

    for option in AMC2.options:
        assert panel.options[option.key] is option.default


def test_the_read_back_names_each_motor_and_whether_it_remembers() -> None:
    # What the module says it now holds, in the words the page offered: a mode per motor,
    # and the remember flag beside the motor it was set for. Both are read through the
    # options themselves, so the read-back is read the same way the module was read in the
    # first place.
    state = FakeState(
        5, "is_amc2", num_ids=1, motors=(_motor(1, OutputType.NORMAL, restore=True), _motor(2, OutputType.AC))
    )
    panel = _new_panel(FakeStore({CommandScope.ACC: [state]}))
    panel._on_device_selected(AMC2.key)
    panel._set_base_id(5)
    panel.on_configure()

    reported = panel.reported_text(state)
    assert "Motor #1 Continuous (DC) (remembers)" in reported
    assert "Motor #2 AC" in reported
    assert "Motor #2 AC (remembers)" not in reported


@pytest.mark.parametrize("sequence", [IrdaSequence.CROSSING_GATE_NONE, IrdaSequence.SLOW_SPEED_NORMAL_SPEED])
def test_the_action_command_shows_what_the_sensor_track_at_the_address_is_set_to(monkeypatch, sequence) -> None:
    # The Action Command a Sensor Track is running with is the sequence field of its own
    # IRDA CONFIG record, and that record is the only place it is recorded: the
    # accessory-scope state the panel is handed does not carry it at all. Read there, the
    # page opens on the row the module is set to rather than on the option's "No Action".
    _sensor_track_based_at(monkeypatch, 3, sequence)
    panel = _new_panel()
    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    action = SENSOR_TRACK.option("action")
    assert sequence is not action.default  # or the row would be selected without being read
    assert panel.reconfigured_occupant().base_id == 3
    assert panel.options["action"] is sequence
    row = [value for _label, value in action.choices].index(sequence)
    assert panel._option_widgets[("sensor_track", "action")].value == str(row)
    # And the presses follow it, so leaving the row alone reprograms the module as it stands:
    # the digit the mode's AUX1 press takes from the option is the sequence's own value.
    assert panel.review_lines == _press_lines(SENSOR_TRACK.default_mode, 3, {"action": sequence})
    assert str(sequence.value) in panel.review_lines[1]


def test_the_config_record_is_what_the_action_command_is_read_from(monkeypatch) -> None:
    # Two records at the address can speak about the Action Command: the IRDA state, which
    # is built from whatever control traffic has gone by, and the module's own CONFIG
    # record. The record is the module reporting its configuration, so it is what the page
    # opens on; the state is the fallback for a store with no PDI side at all.
    reported, stale = IrdaSequence.BELL_NONE, IrdaSequence.RECORDING
    _sensor_track_based_at(monkeypatch, 3, reported)
    panel = _new_panel(FakeStore({CommandScope.IRDA: [FakeState(3, "is_sensor_track", sequence=stale)]}))

    panel._on_device_selected("sensor_track")
    panel._set_base_id(3)

    assert panel.reconfigured_occupant().state.sequence is stale
    assert panel.options["action"] is reported


def test_an_option_is_read_on_the_field_the_module_reports_it_on() -> None:
    # A record is read for an option by the field the option says the module reports it on,
    # which for the Action Command is the sequence rather than the option's own key: read by
    # the key, an IRDA CONFIG record answers with the flavor it was built as.
    action = SENSOR_TRACK.option("action")
    record = SimpleNamespace(action=IrdaAction.CONFIG, sequence=IrdaSequence.BELL_NONE)

    assert action.reported_as == "sequence" != action.key
    assert mod.LcsConfigPanel._reported_option(action, record) is IrdaSequence.BELL_NONE
    assert mod.LcsConfigPanel._default_options(SENSOR_TRACK, record)["action"] is IrdaSequence.BELL_NONE
    # And a record with nothing to say on that field leaves the option its default, however
    # much it has to say under the option's own name.
    silent = SimpleNamespace(action=IrdaAction.CONFIG)
    assert mod.LcsConfigPanel._reported_option(action, silent) is None
    assert mod.LcsConfigPanel._default_options(SENSOR_TRACK, silent)["action"] is action.default


def test_a_field_that_means_something_else_on_the_record_is_not_taken_as_an_answer() -> None:
    # A field name can mean something else entirely on a record written for another purpose,
    # a request's own flavor among them -- so a record is read for an option only where the
    # field holds something the option could be set to.
    action = SENSOR_TRACK.option("action")
    restore = BPC2.option("restore")

    assert mod.LcsConfigPanel._can_hold(action, IrdaSequence.CROSSING_GATE_NONE) is True
    assert mod.LcsConfigPanel._can_hold(action, IrdaAction.CONFIG) is False
    assert mod.LcsConfigPanel._can_hold(restore, True) is True
    assert mod.LcsConfigPanel._can_hold(restore, IrdaAction.CONFIG) is False
    # Which is what a record answering on the field with something else gets: passed over.
    record = SimpleNamespace(sequence=IrdaAction.CONFIG, restore=Bpc2Action.CONFIG)
    assert mod.LcsConfigPanel._reported_option(action, record) is None
    assert mod.LcsConfigPanel._default_options(SENSOR_TRACK, record)["action"] == action.default
    assert mod.LcsConfigPanel._default_options(BPC2, record)["restore"] == restore.default


#
# The verdict: what the module reports, held against what was sent
#
# Configure sends handset presses and nothing else, so the module's own report is the only
# evidence any of it was taken -- and a module that was never put into program mode answers
# perfectly healthily with what it held all along. What makes the difference between those
# two is holding the answer against what was sent, which is what these ask about.
#
def _bpc2_state_at_12(mode: reg.LcsMode = None) -> FakeStore:
    """The component state a BPC2 at 12 leaves, which is where a read-back lands.

    Carries the mode and nothing else about the module's settings: a BPC2's restore flag is
    a bit of the mode byte in its own CONFIG packet and reaches no component state at all,
    which is why the layouts below are stood up in two halves.
    """
    mode = mode or BPC2.default_mode
    return FakeStore({mode.scope: [FakeState(12, "is_bpc2", mode=mode.pdi_mode, num_ids=mode.ports)]})


def _programmed_bpc2(store: FakeStore = None, mode: reg.LcsMode = None) -> Any:
    """A panel that has just sent a BPC2's sequence at 12, with nothing answered yet."""
    mode = mode or BPC2.default_mode
    panel = _new_panel(store)
    panel._on_device_selected(BPC2.key)
    panel._on_mode_selected(mode.key)
    panel._set_base_id(12)
    panel.on_configure()
    return panel


def test_a_module_reporting_what_it_was_sent_is_a_success(monkeypatch) -> None:
    # The whole point of asking. Nothing else the panel can show says the sequence was
    # taken: the presses go out whether or not anything is listening.
    panel = _programmed_bpc2(_bpc2_state_at_12())
    _bpc2_based_at(monkeypatch, 12, BPC2.default_mode, restore=False)

    panel.on_readback()

    assert panel.verification() == mod.Verification(reported=True, differs=())
    assert panel.verification().passed is True
    assert panel._status_line.value == mod.VERIFIED
    assert panel._status_line.text_color == mod.VERIFIED_FG == mod.UNASSIGNED_FG
    assert panel._status_line.visible is True
    # And what the module said is still on the line above, so the verdict can be checked
    # rather than taken on trust.
    assert panel._reported_line.value.startswith(mod.REPORTED.format(summary=""))


def test_a_module_holding_something_else_is_unsuccessful_and_says_what(monkeypatch) -> None:
    # The failure the operator cannot see for themselves: the module answered, at the right
    # address on the right key, and is holding a setting it was not given. Which setting is
    # named, because that is the difference between reading the module's report and acting
    # on it.
    panel = _programmed_bpc2(_bpc2_state_at_12())
    assert panel._sent_program.options["restore"] is False
    _bpc2_based_at(monkeypatch, 12, BPC2.default_mode, restore=True)

    panel.on_readback()

    restore = BPC2.option("restore")
    assert panel.verification() == mod.Verification(reported=True, differs=(restore.label,))
    assert panel._status_line.value == mod.UNVERIFIED_LINE.format(
        verdict=mod.UNVERIFIED,
        reason=mod.NOT_AS_SENT.format(items=restore.label),
        retry=mod.VERIFY_RETRY.format(module=BPC2.label, button=BPC2.program_button),
    )
    assert panel._status_line.text_color == mod.UNVERIFIED_FG == mod.CONFLICT_FG
    # The word, the setting and the remedy are each on the line, whatever sentence holds them.
    assert all(part in panel._status_line.value for part in (mod.UNVERIFIED, restore.label, BPC2.program_button))


def test_a_module_reporting_another_mode_is_unsuccessful(monkeypatch) -> None:
    # A module can answer at the address it was given and still not be what was asked for:
    # an ASC2 told to hold eight accessory IDs and left holding one is on the same key at
    # the same address, and every other line on the page would read as though it had worked.
    asked, holding = ASC2.mode("acc_8"), ASC2.mode("acc_1")
    store = FakeStore({CommandScope.ACC: [FakeState(9, "is_asc2", mode=holding.pdi_mode, num_ids=holding.ports)]})
    panel = _new_panel(store)
    panel._on_device_selected(ASC2.key)
    panel._on_mode_selected(asked.key)
    panel._set_base_id(9)
    panel.on_configure()
    _with_pdi_store(monkeypatch, {PdiDevice.ASC2: [FakePdiConfig(9, CommandScope.ACC, mode=holding.pdi_mode)]})

    panel.on_readback()

    assert panel.verification() == mod.Verification(reported=True, differs=(mod.MODE_TITLE,))
    assert mod.MODE_TITLE in panel._status_line.value
    assert panel._status_line.text_color == mod.UNVERIFIED_FG


def test_a_module_that_never_answers_is_unsuccessful_too() -> None:
    # The likeliest failure of all, and the one the reminder is written for: a module that
    # was not in program mode took none of the sequence, and a module that is not there at
    # all cannot have taken it either. Silence is not a verdict the panel can withhold --
    # the operator would otherwise be left reading a page that says the presses were sent.
    panel = _programmed_bpc2()

    panel.gui.app.fire()

    assert panel._reported_line.value == mod.NO_RESPONSE
    assert panel.verification() == mod.Verification(reported=False, differs=())
    assert panel._status_line.value == mod.UNVERIFIED_LINE.format(
        verdict=mod.UNVERIFIED,
        reason=mod.NOT_REPORTED,
        retry=mod.VERIFY_RETRY.format(module=BPC2.label, button=BPC2.program_button),
    )
    assert panel._status_line.text_color == mod.UNVERIFIED_FG


def test_a_module_that_answers_after_the_panel_gave_up_is_still_heard(monkeypatch) -> None:
    # The panel stops asking; it does not stop listening. An operator who reads the red line,
    # holds PGM and runs the sequence again from the module's side is answered by a module
    # that now holds what it was sent -- and a failure left standing over it would send them
    # back to a page that is already correct.
    store = FakeStore()
    panel = _programmed_bpc2(store)
    panel.gui.app.fire()
    assert panel._status_line.value.startswith(mod.UNVERIFIED), "nothing answered in time"

    store._states.update(_bpc2_state_at_12()._states)
    _bpc2_based_at(monkeypatch, 12, BPC2.default_mode, restore=False)
    panel.on_readback()

    assert panel._status_line.value == mod.VERIFIED
    assert panel._status_line.text_color == mod.VERIFIED_FG


@pytest.mark.parametrize("device", list(reg.configurable_devices()))
def test_the_reminder_names_the_button_the_module_really_has(device: reg.LcsDevice) -> None:
    # A PGM key on most modules and a PROGRAM key on the Sensor Track, so the sentence is
    # filled from the registry: an operator told to hold a button their module has not got
    # is worse off than one told nothing at all.
    panel = _new_panel()
    panel._on_device_selected(device.key)
    panel._show_page(mod.PAGE_REVIEW)
    panel.on_configure()

    panel.gui.app.fire()

    assert panel._status_line.value.endswith(mod.VERIFY_RETRY.format(module=device.label, button=device.program_button))
    assert device.program_button in panel._status_line.value


def test_a_setting_the_module_says_nothing_about_is_not_faulted(monkeypatch) -> None:
    # The same rule the options page seeds by: a record that has not been answered says
    # nothing, and nothing is not disagreement. An AMC2 that has reported no motors would
    # otherwise be failed for all four of its settings at once -- a record read as though
    # every unanswered field meant zero.
    _amc2_based_at(monkeypatch, 5, ())
    panel = _new_panel()
    panel._on_device_selected(AMC2.key)
    panel._set_base_id(5)
    panel.on_configure()

    assert reg.programmed_options(AMC2, AMC2.mode("acc")), "the mode does set them"
    assert panel.verification().passed is True
    assert panel.verification_text(panel.verification()) == mod.VERIFIED


def test_a_motor_holding_another_mode_is_named_by_the_motor(monkeypatch) -> None:
    # Two settings of the same kind on one module, told apart by the heading each stands
    # under on the options page -- which is the option's own label, so the verdict names
    # them the way the page that set them does.
    _amc2_based_at(monkeypatch, 5, (_motor(1, OutputType.NORMAL), _motor(2, OutputType.AC)))
    panel = _new_panel()
    panel._on_device_selected(AMC2.key)
    panel._set_base_id(5)
    sent = dict(panel.options)
    panel.on_configure()
    # The far motor is then found running something else: what a sequence half taken leaves.
    _amc2_based_at(monkeypatch, 5, (_motor(1, sent["motor1_mode"]), _motor(2, OutputType.DELTA)))

    assert panel.verification() == mod.Verification(reported=True, differs=(AMC2.option("motor2_mode").label,))
    assert AMC2.option("motor1_mode").label not in panel.verification_text(panel.verification())


def test_two_settings_a_module_names_alike_are_told_apart_by_their_motor(monkeypatch) -> None:
    # The AMC2 calls both its remember flags "Remember speed on power-up" -- worded for the
    # room a Pi's page has, and told apart on the page by the bold motor heading each stands
    # under. Faulting both of them by label alone would say the same words twice and leave
    # the operator no way to tell which motor is at fault.
    shared = [option.label for option in AMC2.options].count(AMC2.option("motor1_restore").label)
    assert shared == 2, "the module really does name them alike"
    running = (_motor(1, OutputType.NORMAL), _motor(2, OutputType.NORMAL))
    _amc2_based_at(monkeypatch, 5, running)
    panel = _new_panel()
    panel._on_device_selected(AMC2.key)
    panel._set_base_id(5)
    for key in ("motor1_restore", "motor2_restore"):
        panel._option_widgets[(AMC2.key, key)].value = 1
        panel._on_option_changed(AMC2.key, key)
    panel.on_configure()
    # Neither tap took: the module is still running with both motors forgetting their speed.
    _amc2_based_at(monkeypatch, 5, running)

    named = panel.verification().differs

    assert len(named) == 2, "two faults, not one written twice"
    assert len(set(named)) == 2
    for motor, name in zip(("Motor #1", "Motor #2"), named):
        assert name.startswith(motor), "named by the heading it stands under on the page"
        assert AMC2.option("motor1_restore").label.lower() in name.lower()


def test_a_setting_a_module_names_only_once_is_named_by_that_alone() -> None:
    # The general case, and the reason the qualifier is not simply always added: a module
    # with one such setting has nothing to tell it apart from, and the page draws it under
    # no heading but its own.
    assert mod.LcsConfigPanel._option_name(BPC2, BPC2.option("restore")) == BPC2.option("restore").label
    assert mod.LcsConfigPanel._option_name(AMC2, AMC2.option("motor2_mode")) == "Motor #2"


def test_the_verdict_is_given_on_what_was_sent_and_not_on_what_the_pages_now_show(monkeypatch) -> None:
    # The read-back takes seconds to arrive and the operator is free to walk back through
    # the pages while it does. Judged against the panel as it then stands, a module that
    # took the sequence perfectly would be reported as having failed the moment a box was
    # ticked -- and the tick has not been sent to anything.
    panel = _programmed_bpc2(_bpc2_state_at_12())
    _bpc2_based_at(monkeypatch, 12, BPC2.default_mode, restore=False)

    panel._option_widgets[(BPC2.key, "restore")].value = 1
    panel._on_option_changed(BPC2.key, "restore")

    assert panel.options["restore"] is True, "the page has changed"
    assert panel._sent_program.options["restore"] is False, "and what was sent has not"
    assert panel.verification().passed is True


def test_a_module_of_another_type_at_the_address_does_not_answer_for_it(monkeypatch) -> None:
    # An address can hold two modules, and a BPC2 that took nothing is not vouched for by
    # the AMC2 sitting beside it: the module asked for is the type that was programmed,
    # based where it was sent, on the key it was sent on. Read by the address alone, an
    # accessory answering there would pass for the module that never did.
    panel = _programmed_bpc2()
    _with_pdi_store(monkeypatch, {PdiDevice.AMC2: [FakePdiConfig(12, CommandScope.ACC, access_type=AccessType.ACC)]})

    assert panel.assigned_occupants(), "something does answer at the address"
    assert panel.verification().reported is False


def test_nothing_is_judged_before_anything_is_sent() -> None:
    # The panel is opened on a layout it has not touched, and every module on it is holding
    # whatever it is holding. There is no verdict to give until a sequence has gone out.
    panel = _new_panel(_bpc2_state_at_12())
    panel._on_device_selected(BPC2.key)
    panel._set_base_id(12)

    assert panel.verification() == mod.Verification()
    assert panel._status_line.value == ""
    assert panel._status_line.visible is False


def test_the_verdict_is_cleared_when_the_panel_is_reopened(monkeypatch) -> None:
    # It was a verdict on one module at one address; reopened, the panel is about to be
    # aimed at another, and a green Success left standing would be read as this one's.
    panel = _programmed_bpc2(_bpc2_state_at_12())
    _bpc2_based_at(monkeypatch, 12, BPC2.default_mode, restore=False)
    panel.on_readback()
    assert panel._status_line.value == mod.VERIFIED

    panel.configure(None, None, None)

    assert panel._status_line.value == ""
    assert panel._status_line.visible is False


def test_the_verdict_is_brought_into_view_when_it_is_written() -> None:
    # It is the last line of the tallest page the panel draws, and on a Pi that page is
    # taller than the window it is drawn in -- measured 747px of 619 for the Sensor Track --
    # so the answer the operator is standing there waiting for would arrive below the fold.
    # The window is moved as little as it takes, exactly as it is for a highlight the pad
    # steps onto a row nobody can see.
    panel, _body, _host = _build_with_body()
    scroll = panel.scroll
    panel._on_device_selected(SENSOR_TRACK.key)
    panel._show_page(mod.PAGE_REVIEW)
    scroll.shown.clear()

    panel.on_configure()

    assert scroll.shown[-1] is panel._status_line, "the polling line, as soon as it is written"
    scroll.shown.clear()
    panel.gui.app.fire()
    assert panel._status_line.value.startswith(mod.UNVERIFIED), "and the verdict that follows it"
    assert scroll.shown[-1] is panel._status_line
    # The page is refitted first: a line only just shown has not been laid out yet, and where
    # it was while it was hidden is nowhere worth scrolling to.
    assert scroll.fits, "the window is measured again before it is moved"


def test_a_line_taken_off_the_page_is_not_scrolled_to() -> None:
    # Nothing to show: the panel is reopened, which clears the verdict, and a window that
    # moved for it would carry the operator to the foot of a page they have not read.
    panel, _body, _host = _build_with_body()
    panel._show_page(mod.PAGE_REVIEW)
    panel.scroll.shown.clear()

    panel._reset_readback()

    assert panel._status_line.value == ""
    assert panel.scroll.shown == []


def test_the_verdict_stands_below_the_two_lines_it_is_drawn_from() -> None:
    # What was asked for, what the module answered, and only then what that amounts to: the
    # conclusion is read after the two facts it is drawn from, and it is the last word on
    # the page because there is nothing to say after it.
    panel = _new_panel()
    order = panel._pages[mod.PAGE_REVIEW].children.index

    assert order(panel._configure_key_row) < order(panel._requested_line)
    assert order(panel._requested_line) < order(panel._reported_line) < order(panel._status_line)
    assert panel._status_line.text_bold is True, "the one line on the page that is waited for"


def test_the_verdict_is_the_largest_text_on_the_page() -> None:
    # It was set at the page's body size, in among the record of what was asked and what came
    # back -- and it is the answer to the one question the whole panel is walked to ask, read
    # by an operator looking up from the module they have just had both hands on. So it is
    # three sizes above that body and larger than anything else the panel draws, including
    # the heading of the page it stands on. See _status_text_size.
    panel = _new_panel()
    host = panel.gui
    page = panel._pages[mod.PAGE_REVIEW]

    assert panel._status_text_size == host.s_20 > host.s_16 > host.s_14
    assert panel._status_line.text_size == panel._status_text_size
    assert page.children[0].value == mod.REVIEW_TITLE
    others = [
        child.text_size
        for child in page.children
        if child is not panel._status_line and isinstance(getattr(child, "text_size", None), int)
    ]
    assert others and max(others) < panel._status_line.text_size
    # And this is the hand the line is built in and cleared to, the poll setting its own on
    # the way in; see test_the_polling_line_is_read_as_the_note_it_is.
    panel._show_status("", mod.VERIFYING_FG)

    assert (panel._status_line.text_size, panel._status_line.text_bold) == (panel._status_text_size, True)


def test_the_polling_line_is_read_as_the_note_it_is() -> None:
    # It is written to the verdict's own widget and so was drawn in the verdict's hand: the
    # largest, boldest line on the page said only that the panel had not finished asking, and
    # said it for as long as the module took to answer. So it is read at the size of the notes
    # beneath the Configure key -- what was asked of the module and what it answered -- and in
    # italic rather than bold, which is a question rather than an answer. Read back in a live
    # window, it also costs 44px of the narrowest page's height where it cost 99.
    panel = _new_panel()
    host = panel.gui
    panel._on_device_selected(BPC2.key)

    panel.on_configure()

    line = panel._status_line
    assert line.value == mod.VERIFYING.format(module=BPC2.label)
    assert line.text_size == panel._polling_text_size == host.s_12 < panel._status_text_size
    # The same size as those notes, asked of them rather than of the number: what this line
    # is while it stands is one of them.
    assert {line.text_size} == {panel._footnote_line.text_size, panel._requested_line.text_size}
    assert (line.text_italic, line.text_bold) == (True, False)


def test_the_verdict_takes_the_line_back_from_the_poll(monkeypatch) -> None:
    # One widget written twice in a pass -- asking, then answered -- so whatever the poll left
    # standing on it would be read as belonging to the answer. The answer's hand is set on
    # every write rather than at the widget, exactly as its color is; see _show_status.
    panel = _programmed_bpc2(_bpc2_state_at_12())
    assert (panel._status_line.text_italic, panel._status_line.text_bold) == (True, False)
    _bpc2_based_at(monkeypatch, 12, BPC2.default_mode, restore=False)

    panel.on_readback()

    line = panel._status_line
    assert line.value == mod.VERIFIED
    assert line.text_size == panel._status_text_size
    assert (line.text_italic, line.text_bold) == (False, True)
    # And a second pass writes the question again in the question's hand, rather than keeping
    # the answer's: the line goes back and forth for as long as the operator keeps trying.
    panel.on_configure()

    assert (panel._status_line.text_italic, panel._status_line.text_size) == (True, panel._polling_text_size)


#
# The two reports are colored as the warning they are
#
def test_a_module_already_at_the_id_is_reported_in_dark_red() -> None:
    # Every cell of the row, not just the module: the remote key and the block it holds are
    # as much a part of the collision as the name is.
    panel = _new_panel(_asc2_at_9_store())
    panel._on_device_selected("asc2")
    panel._set_base_id(9)

    assert _assigned(panel) == [_row(CommandScope.ACC, ASC2.label, 9, 8)]
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
    assert mod.ModuleRow(*_row_cells(CommandScope.ACC, BPC2.label, 1, 8)).is_unassigned is False


#
# The prose either side of the mode radios: the legend of keys above them, and below them
# the note on the row that is chosen
#
def test_the_legend_heads_the_mode_box_and_the_note_ends_it() -> None:
    # The order the box is read in: what each remote key is for, the rows that choose
    # between them, then what the chosen row is for. The legend stands above the rows
    # because which key to be on is the first half of the choice they offer, and read from
    # below the list it was a note on a decision already made. The mode's own note stands
    # below them because it speaks for whichever row is selected, and until one is there is
    # nothing for it to say.
    panel = _new_panel()
    box = panel._mode_box

    assert box.children[0] is panel._mode_legend_line
    assert getattr(box.children[1], "vspace", None) == mod.MODE_PROSE_GAP
    assert box.children[2] is panel._mode_group
    assert getattr(box.children[3], "vspace", None) == mod.MODE_PROSE_GAP
    assert box.children[4] is panel._mode_note_line
    assert len(box.children) == 5
    # Both inside the radios' own box, not adrift among the page's other derived lines.
    for line in (panel._mode_legend_line, panel._mode_note_line):
        assert line not in panel._pages[mod.PAGE_ID].children


def test_both_lines_of_prose_are_centered_and_wrapped() -> None:
    # Centered like every other line of prose in the panel: the lines are short and of much
    # the same length, and centered they read as a caption on the list beside them rather
    # than as another row of it. align is where guizero packs it -- "top", so it spans the
    # box and is centered in it -- and justify how Tk sets the lines within that.
    panel = _new_panel()

    for line in (panel._mode_legend_line, panel._mode_note_line):
        assert line.kwargs["align"] == "top"
        assert line.tk.configured["justify"] == "center"
        assert line.tk.configured["wraplength"] == panel._wrap_px


def test_the_radios_are_held_off_the_prose_on_either_side_of_them() -> None:
    # Less than the gap between two radios, so both lines read as part of the box rather
    # than as the next thing on the page -- and the same above as below, so the rows read as
    # one block held between the two. Spacer widgets rather than padding of the lines' own,
    # which would push them off the box's edges as well.
    assert mod.MODE_PROSE_GAP < mod.MODE_ROW_PAD
    assert mod.MODE_PROSE_GAP <= 5
    assert mod.MODE_PROSE_GAP_COMPACT < mod.MODE_PROSE_GAP


def test_no_device_means_neither_line_says_anything() -> None:
    panel = _new_panel()

    assert panel.mode_legend == ""
    assert panel.mode_note == ""
    assert panel._mode_legend_line.value == ""
    assert panel._mode_note_line.value == ""


@pytest.mark.parametrize(
    "device_key, expected",
    [
        # In the order the module's own radios list them, so a BPC2 reads ACC before TR and
        # an STM2 says nothing about accessories. Looked up as the panel looks them up --
        # under the module as well as the key -- so the BPC2 is expected to read its own
        # wording of ACC and TR rather than the line every other module reads.
        ("asc2", [mod.scope_use(CommandScope.ACC, ASC2), mod.scope_use(CommandScope.SWITCH, ASC2)]),
        ("bpc2", [mod.scope_use(CommandScope.ACC, BPC2), mod.scope_use(CommandScope.TRAIN, BPC2)]),
        ("stm2", [mod.scope_use(CommandScope.SWITCH, STM2)]),
        ("sensor_track", [mod.scope_use(CommandScope.ACC, SENSOR_TRACK)]),
    ],
)
def test_the_legend_covers_every_key_the_module_offers_and_no_other(device_key: str, expected: list[str]) -> None:
    panel = _new_panel()
    panel._on_device_selected(device_key)

    assert panel.mode_legend.split("\n") == expected
    assert panel._mode_legend_line.value == panel.mode_legend


def test_the_legend_says_what_each_key_is_for() -> None:
    # A line per key the panel knows, each opening with that key spelled exactly as the mode
    # rows spell it and going on to say what it is good for -- which is the one thing the
    # rows themselves cannot say. Read as a rule about the lines rather than as their text,
    # so rewording what a key is for is free and dropping the key off the front is not.
    #
    # Every key the panel offers a row on, and no other -- not every key it can spell. The
    # engine key is spelled by SCOPE_LABEL so the Known Modules listing can name a module
    # already out on it, and it is on no row for a legend line to head.
    offered = {mode.scope for device in reg.configurable_devices() for mode in reg.enabled_modes(device)}
    assert {scope for scope, _module_key in mod.SCOPE_USE} == offered
    for (scope, _module_key), use in mod.SCOPE_USE.items():
        key = mod.SCOPE_LABEL[scope]
        assert use.startswith(f"{key}:")
        assert use[len(key) + 1 :].strip()
    # And every key has the line that speaks wherever a module has not been spoken for, so
    # no module can be left with a key the legend says nothing about.
    for scope in offered:
        assert (scope, None) in mod.SCOPE_USE


def test_a_key_that_means_the_same_everywhere_is_worded_once() -> None:
    # Only a module a key means something else on has a line written for it; every other
    # module reads the line filed under no module in particular, so a key that means the same
    # thing everywhere is worded once. Which modules those are is read out of the map rather
    # than named here: the Sensor Track's own ACC line was written after this test was, and a
    # module named here as reading the general line is a fact this test cannot know.
    read_the_general_line: list[str] = []
    for device in reg.configurable_devices():
        for mode in reg.enabled_modes(device):
            own = mod.SCOPE_USE.get((mode.scope, device.key))
            general = mod.SCOPE_USE[(mode.scope, None)]
            assert mod.scope_use(mode.scope, device) == (own or general)
            if own is None:
                read_the_general_line.append(f"{device.key}/{mod.SCOPE_LABEL[mode.scope]}")
    # And the general lines are read rather than merely written: most modules have nothing of
    # their own to say about most of the keys they offer.
    assert read_the_general_line
    # Asked with no module at all -- which is what the panel does before a device is chosen
    # -- the general line answers for every key one is written for.
    for scope, module_key in mod.SCOPE_USE:
        if module_key is None:
            assert mod.scope_use(scope) == mod.SCOPE_USE[(scope, None)]
    # A key nothing is written about at all is passed over rather than headed with a blank
    # line. The AMC2's ENG mode is on such a key, and the legend never has to: a mode the
    # panel does not offer is on no row for the legend to head.
    assert mod.scope_use(CommandScope.ENGINE) is None
    offered = {mode.scope for device in reg.configurable_devices() for mode in reg.enabled_modes(device)}
    assert CommandScope.ENGINE not in offered


def test_a_line_written_for_one_module_names_that_module() -> None:
    # Why a line is filed under a module at all: the general line for the key is wrong about
    # this one, so the line has to say which module it is speaking about -- read as a fact
    # about the key alone it is no truer than the line it replaced. Asked of every override
    # rather than of the two written today, so the next one is held to the same rule, and the
    # name is taken from the registry here as it is there, so neither can drift.
    overrides = [(scope, key) for scope, key in mod.SCOPE_USE if key is not None]
    assert overrides
    for scope, module_key in overrides:
        device = reg.device_for_key(module_key)
        line = mod.SCOPE_USE[(scope, module_key)]
        assert device.label in line
        assert line != mod.SCOPE_USE[(scope, None)]
        # And the module reads it: a line filed under a key the module does not offer would
        # never reach the legend, and is a line written about nothing.
        assert scope in {mode.scope for mode in reg.enabled_modes(device)}
        assert mod.scope_use(scope, device) == line


def test_the_bpc2s_two_keys_are_two_ways_of_addressing_it_rather_than_two_uses() -> None:
    # Its manual: "Your BPC2 can be addressed as either a TR (Track) device or an ACC
    # (Accessory). The features available in both addressing modes are identical, choose
    # whichever suits your layout best." So the general lines are wrong about it on both
    # keys -- its ACC modes are not lighting, and TR is not the only way it does track power
    # -- and each of its own lines names which addressing mode the row below it chooses.
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert panel.mode_legend.split("\n") == [
        mod.SCOPE_USE[(CommandScope.ACC, BPC2.key)],
        mod.SCOPE_USE[(CommandScope.TRAIN, BPC2.key)],
    ]
    for scope in (CommandScope.ACC, CommandScope.TRAIN):
        key = mod.SCOPE_LABEL[scope]
        line = mod.scope_use(scope, BPC2)
        # Its own wording, and the general line nowhere on the page.
        assert line != mod.SCOPE_USE[(scope, None)]
        assert mod.SCOPE_USE[(scope, None)] not in panel.mode_legend
        # Which module, and which of its two addressing modes: the two facts a line about
        # the key alone cannot carry. The module is named from the registry, so the pair
        # cannot come to speak for some other module than the one they are filed under.
        assert BPC2.label in line
        assert "addressed as" in line
        assert key in line[len(key) + 1 :]


def test_no_legend_line_asks_for_more_than_one_line_of_the_pane() -> None:
    # A legend line is prose, so an over-long one wraps rather than being lost -- but the ID
    # page is the fullest in the panel, and a line taking two of them spends a row the page
    # has not got. The accessory line is the widest the panel draws today: 47 characters,
    # which is 672 px of the 690 px a line is broken at on the Pi at its 1.5x font scale.
    # The BPC2's own two come to 603 px and 576 px, so each sits on one line there too.
    # Characters as the ceiling, as the registry pins its widest radio row, with the pixels
    # measured before a longer wording is adopted.
    for (scope, module_key), use in mod.SCOPE_USE.items():
        assert len(use) <= 47, f"{module_key or 'any module'}/{mod.SCOPE_LABEL[scope]}: {use}"


def test_the_legend_leads_with_the_word_the_rows_lead_with() -> None:
    # What joins the legend to the list below it: a switch row is answered by the line for
    # the switch key, one word, spelled the same in both places. The two sets are pinned to
    # each other and to the module's own modes, so a mode named any other way -- or a key
    # the module does not offer -- shows up here.
    panel = _new_panel()
    panel._on_device_selected("asc2")

    rows = {label.split()[0] for label, _key in panel._mode_group.options}
    keys = {line.split(":")[0] for line in panel.mode_legend.split("\n")}
    offered = {mod.SCOPE_LABEL[mode.scope] for mode in reg.enabled_modes(ASC2)}

    assert rows == keys == offered
    # The ASC2 is the module that offers two of them, which is what makes it the case worth
    # asking about.
    assert len(offered) == 2


def test_the_legend_speaks_for_the_module_rather_than_for_the_chosen_row() -> None:
    # What an ACC row is good for is as true before a row is tapped as after, so the legend
    # does not move with the selection -- the line below the rows is what does.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    legend = panel.mode_legend

    panel._on_mode_selected("acc_1")

    assert panel.mode_legend == legend
    assert panel._mode_legend_line.value == legend
    assert panel.mode_note not in panel._mode_legend_line.value


def test_the_selected_mode_says_what_it_is_for_below_the_rows() -> None:
    # The row has no room for it: it says which mode and which address -- e.g. "ACC
    # (uncouple) TMCC ID 1" -- and this says the rest, keyed by the word in parentheses on
    # the row it explains, as the legend above is keyed by the word every row opens with.
    # Both the key and the sentence are taken from the mode rather than spelled again here,
    # so the prose is settled in one file.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    panel._on_mode_selected("acc_1")

    uncouple = ASC2.mode("acc_1")
    assert panel.mode_note == f"{uncouple.qualifier}: {uncouple.note}"
    assert panel._mode_note_line.value == panel.mode_note
    assert panel._mode_note_line.visible is True
    # And the word it is keyed by is the word the chosen row carries.
    labels = {key: label for label, key in panel._mode_group.options}
    assert f"({panel.mode_note.split(':')[0]})" in labels["acc_1"]


def test_the_note_speaks_for_the_row_the_operator_chose() -> None:
    # One line, about the mode in hand, replaced as the operator taps down the list -- not
    # every mode's note at once, on the page that has the least room to spare.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    pulse = ASC2.mode("sw_momentary")
    uncouple = ASC2.mode("acc_1")
    panel._on_mode_selected("sw_momentary")
    assert panel.mode_note == f"{pulse.qualifier}: {pulse.note}"

    panel._on_mode_selected("acc_1")

    assert panel.mode_note == f"{uncouple.qualifier}: {uncouple.note}"
    assert pulse.note not in panel._mode_note_line.value


def test_a_mode_named_by_its_key_alone_keys_nothing() -> None:
    # Nothing in its name tells it from another mode on the same key, so there is no word to
    # look the sentence up under and it stands as the plain sentence it is. No module offers
    # such a mode today -- every offered mode that has anything written about it is one of a
    # pair on its key -- so the case is reached through the BPC2's reserved 1-ID mode, which
    # carries a note and is named by its key alone, as the mode beside it is.
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    reserved = BPC2.mode("tr_1")
    panel._on_mode_selected("tr_1")

    assert reserved.qualifier is None
    assert panel.mode_note == reserved.note
    assert panel._mode_note_line.value == reserved.note


def test_a_mode_with_nothing_written_about_it_adds_no_line() -> None:
    # The box grows only for a row that speaks, and the ID page is the fullest the panel has:
    # neither BPC2 mode it offers carries a note, and an empty Label would still stand a line
    # tall -- 30px of nothing at the Pi's font scale -- so it is taken off the page instead.
    panel = _new_panel()
    panel._on_device_selected("asc2")
    assert panel._mode_note_line.visible is True, "the ASC2's every mode has something to say"

    panel._on_device_selected("bpc2")
    panel._on_mode_selected("tr_8")

    assert panel.mode_note == ""
    assert panel._mode_note_line.value == ""
    assert panel._mode_note_line.visible is False
    # The legend is not hidden with it: a module with modes always has keys to name.
    assert panel._mode_legend_line.visible is True
    assert panel.mode_legend.split("\n") == [
        mod.scope_use(CommandScope.ACC, BPC2),
        mod.scope_use(CommandScope.TRAIN, BPC2),
    ]


def test_the_legend_follows_the_device_the_operator_switches_to() -> None:
    panel = _new_panel()
    panel._on_device_selected("bpc2")
    assert mod.scope_use(CommandScope.TRAIN, BPC2) in panel._mode_legend_line.value

    panel._on_device_selected("stm2")
    assert panel._mode_legend_line.value == mod.scope_use(CommandScope.SWITCH, STM2)
    assert mod.scope_use(CommandScope.TRAIN, BPC2) not in panel._mode_legend_line.value
    # And a line written for one module is left behind with it: nothing filed under another
    # module is on the page. Read off the map rather than named here, so a line written for
    # one more module is covered by this as it stands.
    for (_scope, module_key), line in mod.SCOPE_USE.items():
        if module_key not in (None, STM2.key):
            assert line not in panel._mode_legend_line.value


#
# The mode rows are grouped by the remote key they are on
#
def test_the_rows_of_one_key_are_held_off_the_rows_of_the_next() -> None:
    # The ASC2 lists two ACC modes and then two SW modes: only the first SW row asks for a
    # gap, so the two pairs read as two short lists rather than one list of four -- which is
    # how the legend above them is written, a line per key.
    panel = _new_panel()
    panel._on_device_selected("asc2")

    assert panel.mode_leads() == {"sw_momentary": mod.MODE_KEY_LEAD}


def test_the_gap_falls_wherever_the_key_changes() -> None:
    # Read off the modes rather than spelled out, so a module is grouped by the order the
    # registry lists it in: the BPC2 reads ACC and then TR, and its disabled 1-ID modes --
    # one of which stands between the two on the list -- are not rows and so break nothing.
    panel = _new_panel()
    panel._on_device_selected("bpc2")

    assert panel.mode_leads() == {"tr_8": mod.MODE_KEY_LEAD}


@pytest.mark.parametrize("device_key", ["stm2", "sensor_track"])
def test_a_module_whose_modes_share_one_key_asks_for_no_gap(device_key: str) -> None:
    # Both of the STM2's modes are SW, and the Sensor Track offers one mode at all: there is
    # no second group for a gap to stand between.
    panel = _new_panel()
    panel._on_device_selected(device_key)

    assert panel.mode_leads() == {}


def test_no_device_means_no_gaps() -> None:
    assert _new_panel().mode_leads() == {}


def test_the_group_is_told_the_gaps_when_it_is_built_and_on_every_refresh() -> None:
    # The rows are destroyed and rebuilt on every refresh of the page -- that is how they
    # are relabeled as the ID steps -- and a rebuilt row is gridded from scratch, so the
    # group has to be holding the gaps rather than have been handed them once.
    panel = _new_panel()

    # Built before a module is chosen, so it starts with nothing to say.
    assert panel._mode_group.kwargs["row_leads"] == {}

    panel._on_device_selected("asc2")
    assert panel._mode_group.row_leads == {"sw_momentary": mod.MODE_KEY_LEAD}

    # And the gaps of the module left behind do not follow the operator to the next one.
    panel._on_device_selected("stm2")
    assert panel._mode_group.row_leads == {}


def test_the_gap_between_keys_is_tighter_on_a_compact_host() -> None:
    panel, _body, _host = _build_with_body(compact=True)
    panel._on_device_selected("asc2")

    assert panel.mode_leads() == {"sw_momentary": mod.MODE_KEY_LEAD_COMPACT}


def test_the_gap_between_keys_divides_the_list_rather_than_ending_it() -> None:
    # Wider than the gap between two rows of the same key, so the break is seen; narrower
    # than the gaps between the page's own sections, so the four rows are still one list.
    assert mod.MODE_ROW_PAD < mod.MODE_KEY_LEAD < mod.PAGE_GAP
    assert mod.MODE_KEY_LEAD_COMPACT < mod.MODE_KEY_LEAD


#
# The panel is worked with the gamepad
#
# On the Steam Deck the D-pad steps the list on the page showing, right marks the row it is
# on -- and turns the page with it, on a page whose list is the whole of what it asks -- left
# puts back what that mark displaced, A marks and turns the page, or presses Configure on the
# last page, which has no page after it, and B turns it back. Which key does what is
# DeckInputRouter._config_panel_only and is tested there; what each of them means is the
# panel's own, and is what these ask.
#
def _module_keys() -> list[str]:
    """The module rows in the order the first page lists them."""
    return [key for _label, key in mod.LcsConfigPanel.device_options()]


def _mode_keys(device: reg.LcsDevice) -> list[str]:
    """The mode rows in the order the ID page lists them."""
    return [mode.key for mode in reg.enabled_modes(device)]


def _tap_module(panel: Any, key: str) -> None:
    """Choose a module the way a finger does: the row holds the value, and then it fires.

    The handler alone is the tap without the press. guizero has put the value in the group
    by the time a command runs, so nothing on this page writes it back -- every other path
    that changes the module (configure, Go to, a late synchronization) writes it through
    _refresh_device_selector, and the pad writes it itself before committing. These tests
    are about where the pad steps from, which is the row the dot is on, so the dot has to be
    where a real press would have left it.
    """
    panel._device_group.value = key
    panel._on_device_selected(key)


def test_the_pad_steps_the_module_rows_without_choosing_one() -> None:
    # The whole reason these lists carry a highlight apart from their dot: a row stepped over
    # must not read as a row chosen, and on this page choosing one rebuilds both pages after
    # it. So the pad moves the highlight and nothing else moves at all.
    panel = _new_panel()
    _tap_module(panel, ASC2.key)
    keys = _module_keys()

    assert panel.pad_step(1) is True

    assert panel._device_group.cursor == keys[keys.index(ASC2.key) + 1]
    assert panel._device_group.value == ASC2.key, "the dot has not moved"
    assert panel.device is ASC2


def test_the_pad_starts_from_the_row_the_dot_is_on() -> None:
    # What makes the first press behave: the operator is already partway down the list, so
    # one press moves one row from where the panel is rather than jumping to the top.
    panel = _new_panel()
    _tap_module(panel, SENSOR_TRACK.key)
    keys = _module_keys()

    panel.pad_step(-1)

    assert panel._device_group.cursor == keys[keys.index(SENSOR_TRACK.key) - 1]


@pytest.mark.parametrize("delta", [1, -1])
def test_the_pad_lands_on_the_first_row_where_nothing_is_chosen_yet(delta: int) -> None:
    # A list with nothing on it is a state before the list rather than a position in it, so
    # a press either way lands on the first row. Reading it as "already on the first" would
    # make that press either do nothing or skip a row, depending on which way it went.
    panel = _new_panel()

    assert panel.pad_cursor is None
    assert panel.pad_step(delta) is True
    assert panel._device_group.cursor == _module_keys()[0]


def test_the_pad_stops_at_either_end_of_the_list() -> None:
    # Clamped rather than wrapping, as the keypad's Sensor Track list is: a pad held against
    # the end stays there instead of rolling round to the far one, where the next mark would
    # program something the operator never looked at.
    panel = _new_panel()
    keys = _module_keys()

    _tap_module(panel, keys[0])
    assert panel.pad_step(-1) is False
    assert panel._device_group.cursor is None, "and nothing moved on the way to saying so"

    _tap_module(panel, keys[-1])
    assert panel.pad_step(1) is False


def test_a_marked_row_is_chosen_exactly_as_a_tap_would_choose_it() -> None:
    # A value assigned to a group moves its dot and fires nothing -- guizero binds a command
    # to the click -- so a mark that only assigned would leave every page after this one
    # describing the module the operator had just stopped choosing.
    panel = _new_panel()
    _tap_module(panel, ASC2.key)
    panel.pad_step(1)

    assert panel.pad_mark() is True

    assert panel.device is BPC2
    assert panel._device_group.value == BPC2.key
    assert panel.id_heading_text == mod.ID_HEADING.format(module=BPC2.label)
    assert panel._mode_group.row_values == tuple(_mode_keys(BPC2)), "and the page after it was rebuilt"


def test_a_highlight_that_never_moved_marks_nothing() -> None:
    # Which is what lets a page turn without leaving a revert behind: there is nothing to put
    # back after a press that chose the row that was already chosen. Asked on the ID page,
    # which right marks without turning -- on a page it turns, the turn is the answer and
    # whether anything was marked on the way is beside the point.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel.next_page()
    modes = _mode_keys(BPC2)

    assert panel.pad_cursor == modes[0], "the pad starts on the row that is chosen"
    assert panel.pad_mark() is False
    assert panel.mode.key == modes[0]
    assert panel.page_index == mod.PAGE_ID


def test_a_module_marked_with_right_is_come_back_to_with_b() -> None:
    # Right turns the page with the mark, and a page turned is as far back as a revert
    # reaches: the choice it displaced is on the page that was left. So the way back to a
    # module marked in passing is B, and it is the marked module that is there -- left speaks
    # for the list on the page it is pressed on, whichever page that is.
    panel = _new_panel()
    _tap_module(panel, ASC2.key)
    panel.pad_step(1)
    panel.pad_mark()

    assert panel.pad_revert() is False, "the mode rows it landed on have nothing marked on them"

    assert panel.pad_back() is True
    assert (panel.device, panel.page_index) == (BPC2, mod.PAGE_DEVICE)
    assert panel.pad_revert() is False
    assert panel._device_group.value == BPC2.key


def test_a_left_press_with_nothing_marked_abandons_the_move() -> None:
    # The other thing a left press can mean, and the panel means whichever is true: a row
    # stepped onto but never chosen is abandoned, and the dot was never anywhere else.
    panel = _new_panel()
    _tap_module(panel, ASC2.key)
    panel.pad_step(1)

    assert panel.pad_revert() is True

    assert panel._device_group.cursor == ASC2.key
    assert panel.device is ASC2


def test_a_revert_is_one_mark_deep() -> None:
    # The undo is dropped as it is used, so a second left press cannot undo the same mark
    # twice -- and by then the highlight is on the row that is chosen, so it means nothing
    # else either. On the ID page, the one a mark leaves the panel standing on.
    panel = _new_panel()
    panel._on_device_selected(ASC2.key)
    panel.next_page()
    modes = _mode_keys(ASC2)
    panel.pad_step(1)
    panel.pad_mark()
    panel.pad_revert()

    assert panel.pad_revert() is False
    assert panel.mode.key == modes[0]


def test_a_page_turned_is_as_far_back_as_a_revert_reaches() -> None:
    # The choice a mark displaced is on the page that was left, and the operator looking at
    # another one cannot see it put back: a mode swapped under the page they are reading
    # would read as the panel losing their place. Not even on coming back to the page it was
    # made on -- a mark the operator has walked away from and returned to is the panel's
    # state now, not a move still in progress.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel.next_page()
    modes = _mode_keys(BPC2)
    panel.pad_step(1)
    panel.pad_mark()
    assert panel.mode.key == modes[1]

    panel.pad_back()
    panel.next_page()

    assert panel.pad_revert() is False
    assert panel.mode.key == modes[1]


def test_the_pad_chooses_a_mode_and_can_put_it_back() -> None:
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel.next_page()
    modes = _mode_keys(BPC2)
    assert panel.mode.key == modes[0]

    panel.pad_step(1)
    assert panel.pad_mark() is True
    assert panel.mode.key == modes[1]

    assert panel.pad_revert() is True
    assert panel.mode.key == modes[0]


def test_the_pad_goes_on_from_the_row_it_marked() -> None:
    # The mode rows are destroyed and rebuilt whenever the module or the address changes --
    # which is what relabels them as the ID steps -- and the tint goes with them. The dot is
    # then on the row the pad was on, so stepping carries on from where it left off rather
    # than from the top of the list.
    panel = _new_panel()
    panel._on_device_selected(ASC2.key)
    panel.next_page()
    modes = _mode_keys(ASC2)
    panel.pad_step(1)
    panel.pad_mark()

    assert panel._mode_group.cursor is None, "the rebuild took the tint with it"
    assert panel.pad_step(1) is True
    assert panel._mode_group.cursor == modes[2]


def test_the_right_key_chooses_the_module_and_turns_the_page() -> None:
    # The first page asks one question and its rows are the whole of it, so the answer
    # finishes the page: a press to choose and a second to go on are two presses for one
    # decision. Both halves in that order, as A does them -- a choice written after the turn
    # would land on the next page's list.
    panel = _new_panel()
    _tap_module(panel, ASC2.key)
    panel.pad_step(1)

    assert panel.pad_mark() is True

    assert (panel.device, panel.page_index) == (BPC2, mod.PAGE_ID)
    heading = mod.ID_HEADING.format(module=BPC2.label)
    assert panel.id_heading_text == heading, "the page it turned to is the marked module's"


def test_the_right_key_turns_the_page_where_the_highlight_never_moved() -> None:
    # Right on the row already chosen means "this one, go on": answering the page's question
    # with the row it opened on is an answer, and on the Pi and the Deck that row is the
    # module the operator's screen was showing -- the one they are most likely to want.
    panel = _new_panel()
    _tap_module(panel, BPC2.key)

    assert panel.pad_mark() is True

    assert (panel.device, panel.page_index) == (BPC2, mod.PAGE_ID), "the selection stands as it was"


def test_the_right_key_goes_nowhere_until_a_module_is_chosen() -> None:
    # The question the Next key is enabled by, asked by right as well as by A: with nothing
    # chosen there is nothing to configure, and the page it would turn to would open on no
    # module at all.
    panel = _new_panel()

    assert panel.pad_mark() is False
    assert panel.page_index == mod.PAGE_DEVICE


def test_the_right_key_chooses_a_mode_without_turning_the_id_page() -> None:
    # That page asks two things of the operator and lends the pad one of them: the address is
    # typed into a field the pad cannot reach, stepped with the two keys beside it and, for
    # an address inside another module's block, taken over with the keys below the rows. A
    # page turned on the mode would carry the operator off with half the decision unmade.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel.next_page()
    modes = _mode_keys(BPC2)
    panel.pad_step(1)

    assert panel.pad_mark_turns_page is False
    assert panel.pad_mark() is True

    assert panel.mode.key == modes[1]
    assert panel.page_index == mod.PAGE_ID


def test_the_right_key_turns_the_page_on_a_modules_only_setting() -> None:
    # The Sensor Track's ten actions are the whole of that page -- nothing is drawn under
    # them -- so choosing one finishes it, exactly as choosing a module finishes the first.
    panel = _new_panel()
    panel._on_device_selected(SENSOR_TRACK.key)
    panel._show_page(mod.PAGE_OPTIONS)
    choices = [value for _label, value in SENSOR_TRACK.option("action").choices]
    panel.pad_step(1)

    assert panel.pad_mark() is True

    assert panel.options["action"] == choices[1]
    assert panel.page_index == mod.PAGE_REVIEW


def test_a_setting_below_the_one_marked_holds_the_page() -> None:
    # What "the whole of the page" means, asked of the module rather than assumed: every
    # module in the registry declares one setting today, and one that declared a second below
    # its rows would be asking for something a page turn on the first would carry the
    # operator straight past.
    panel = _new_panel()
    panel._on_device_selected(SENSOR_TRACK.key)
    panel._show_page(mod.PAGE_OPTIONS)

    assert panel.pad_mark_turns_page is True, "the action list alone"

    below = LcsOption(key="below", label="And this", kind=mod.OptionKind.CHECKBOX, choices=())
    device = replace(SENSOR_TRACK, options=(*SENSOR_TRACK.options, below))
    panel._device = device
    panel._build_option(DummyBox(), device, below)

    assert panel.pad_mark_turns_page is False

    # A setting the module declares but this mode does not offer is a fact to read rather
    # than a decision to make, so it holds nothing up -- the pad passes over it too.
    panel._device = replace(device, options=(*SENSOR_TRACK.options, replace(below, enabled=False)))
    assert panel.pad_mark_turns_page is True


def test_the_a_key_chooses_the_highlighted_row_and_turns_the_page() -> None:
    # Both halves, in that order: marking after the page turned would write the choice onto
    # the next page's list.
    panel = _new_panel()
    _tap_module(panel, ASC2.key)
    panel.pad_step(1)

    assert panel.pad_advance() is True

    assert panel.device is BPC2
    assert panel.page_index == mod.PAGE_ID


def test_the_a_key_turns_the_page_where_nothing_was_highlighted() -> None:
    panel = _new_panel()
    _tap_module(panel, BPC2.key)

    assert panel.pad_advance() is True

    assert panel.device is BPC2, "the selection stands as it was"
    assert panel.page_index == mod.PAGE_ID


def test_the_a_key_goes_nowhere_until_a_module_is_chosen() -> None:
    # The question the Next key is enabled by, asked by the pad as well, so A cannot go
    # anywhere Next would not.
    panel = _new_panel()

    assert panel.pad_advance() is False
    assert panel.page_index == mod.PAGE_DEVICE


def test_the_a_key_presses_configure_on_the_review_page() -> None:
    # The last page has no page after it and one control on it, and that control programs the
    # module: with A pressing it the panel is worked from the pad end to end, which is what
    # it is there for on a Deck. What is sent is what the button sends -- the same handler,
    # compared against a panel the button was pressed on -- so the module cannot be
    # programmed one way by a finger and another by the pad.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel._on_mode_selected("tr_8")
    panel._set_base_id(12)
    panel._show_page(mod.PAGE_REVIEW)

    assert panel.pad_advance() is True

    assert panel.page_index == mod.PAGE_REVIEW, "and stays there: there is nowhere left to go"
    tapped = _new_panel()
    tapped._on_device_selected(BPC2.key)
    tapped._on_mode_selected("tr_8")
    tapped._set_base_id(12)
    tapped.on_configure()
    assert len(panel.gui.sent) == len(tapped.gui.sent)
    assert [(request.command, delay) for request, _repeat, delay in panel.gui.sent[:2]] == [
        (request.command, delay) for request, _repeat, delay in tapped.gui.sent[:2]
    ]
    # And the module is asked what it now holds, which is the half of Configure that is not
    # presses: a press that sent the sequence and armed no read-back would report nothing.
    assert panel._status_line.value == mod.VERIFYING.format(module=BPC2.label)


def test_the_a_key_sends_nothing_where_configure_is_disabled() -> None:
    # A asks the rule the button is enabled by, so it can press nothing a finger could not:
    # nothing is sent while the panel is running ahead of Base 3 synchronization, the layout
    # it would be read against not being known yet.
    panel = _new_panel()
    host = panel.gui
    panel._on_device_selected(BPC2.key)
    panel._set_base_id(12)
    panel._show_page(mod.PAGE_REVIEW)
    panel.set_sync_pending(True)

    assert panel.pad_advance() is False

    assert host.sent == []
    assert (panel.can_configure, panel._configure_btn.enabled) == (False, False)


def test_the_b_key_turns_back_a_page_and_stops_at_the_first() -> None:
    # And it puts nothing back on the way: Back and revert are two different requests, so
    # the page arrived at is read with its own choice still in force.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel.next_page()

    assert panel.pad_back() is True
    assert panel.page_index == mod.PAGE_DEVICE
    assert panel.device is BPC2

    assert panel.pad_back() is False
    assert panel.page_index == mod.PAGE_DEVICE


def test_the_stick_moves_the_page_and_chooses_nothing() -> None:
    # The pad's keys work the controls on a page; the stick and the trackpad work the page
    # itself, which on the one screen that ever holds a page back is a different thing to
    # want: a highlight can only be stepped to a row, and reading the box below the rows is
    # not stepping. So it reaches the same window a finger dragging the page reaches, and
    # like that finger it chooses nothing.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    scroll = panel.scroll
    scroll.scrollable = True
    chosen = panel._device_group.value

    assert panel.pad_scroll(60) is True
    assert panel.pad_scroll(-60) is True

    assert scroll.scrolled == [60, -60], "positive is further down the page"
    assert panel._device_group.value == chosen
    assert panel.pad_cursor is None, "and no highlight moved with it"


def test_a_page_with_nowhere_to_go_answers_the_stick_with_nothing() -> None:
    # A page that fits its window is a page at both of its ends at once, and a stick held
    # over one is doing nothing -- which the caller is told, rather than refused. Nothing is
    # asked of the window for a press worth no pixels at all.
    panel = _new_panel()
    scroll = panel.scroll
    scroll.scrollable = False

    assert panel.pad_scroll(60) is False
    assert scroll.scrolled == [60], "asked all the same: how far it can go is the window's own"

    assert panel.pad_scroll(0) is False
    assert scroll.scrolled == [60], "and a nudge worth no pixels is not worth asking about"


def test_a_panel_with_no_window_yet_is_safe_to_scroll() -> None:
    # The pad is answered by whatever is on screen, and a panel that has been built but never
    # laid out has no window to move. A press arriving then is early rather than wrong.
    panel = mod.LcsConfigPanel(_new_host())

    assert panel.scroll is None
    assert panel.pad_scroll(60) is False


def test_the_pad_ticks_and_clears_the_only_setting_a_bpc2_has() -> None:
    # A lone tick box is the whole of that page, and there is no list to step through: right
    # sets it and left clears it, both states one press away either way -- which is how a
    # power district's relays are worked from the pad.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel._show_page(mod.PAGE_OPTIONS)
    restore = panel._option_widgets[("bpc2", "restore")]

    assert panel.pad_group is None
    assert panel.pad_step(1) is False

    assert panel.pad_mark() is True
    assert restore.value == 1
    assert panel.options["restore"] is True
    assert panel.page_index == mod.PAGE_OPTIONS, "and no page is turned: left has to be able to clear it"
    assert panel.pad_mark_turns_page is False

    assert panel.pad_revert() is True
    assert restore.value == 0
    assert panel.options["restore"] is False
    assert panel.pad_revert() is False, "and a box already clear is not cleared twice"


def test_the_pad_steps_the_sensor_tracks_actions() -> None:
    # The longest list in the panel, and the one this matters most on: ten rows is a lot to
    # reach for on a Deck held in two hands.
    panel = _new_panel()
    panel._on_device_selected(SENSOR_TRACK.key)
    panel._show_page(mod.PAGE_OPTIONS)
    action = panel._option_widgets[("sensor_track", "action")]
    choices = [value for _label, value in SENSOR_TRACK.option("action").choices]

    panel.pad_step(1)
    panel.pad_step(1)
    assert action.cursor == "2"
    assert panel.options["action"] == choices[0], "stepping chooses nothing"

    assert panel.pad_mark() is True
    assert action.value == "2"
    assert panel.options["action"] == choices[2]


def test_the_pad_leaves_a_setting_the_page_has_disabled_alone() -> None:
    # A disabled setting is drawn to say the module has it and this mode does not offer it,
    # and the pad has no more business setting it than a finger has.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel._show_page(mod.PAGE_OPTIONS)
    restore = panel._option_widgets[("bpc2", "restore")]
    restore.disable()

    assert panel.pad_mark() is False
    assert restore.value == 0


def test_the_pad_does_nothing_on_the_review_page() -> None:
    # It asks nothing of the operator: it reports what was chosen and offers Configure.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel._show_page(mod.PAGE_REVIEW)

    assert panel.pad_group is None
    assert panel.pad_cursor is None
    assert panel.pad_step(1) is False
    assert panel.pad_mark() is False
    assert panel.pad_mark_turns_page is False, "there is nothing to mark, and nowhere to turn to"
    assert panel.pad_revert() is False


def test_the_pad_does_nothing_while_the_id_is_being_typed() -> None:
    # On a touch appliance that field opens a keypad over the page, and the pad cannot type
    # into it: a highlight stepped behind it would be a change nobody can see.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    panel.next_page()
    panel._id_field.is_editing = True

    assert panel.pad_group is None
    assert panel.pad_step(1) is False
    assert panel.pad_mark() is False

    panel._id_field.is_editing = False
    assert panel.pad_step(1) is True


@pytest.mark.parametrize("deck", [True, False])
def test_every_list_the_pad_steps_shows_where_it_is_where_there_is_a_pad(monkeypatch, deck: bool) -> None:
    # The tint is opt-in on the component -- the Admin panel, the catalog's sort radios and
    # the AMC2 page selector share it and asked for none -- so every list the pad can reach
    # has to ask for it, or the highlight would move where nothing showed it. Every one of
    # them or none: which list the pad steps is which page is showing, so a list left unarmed
    # would be a page where the pad moved nothing.
    #
    # And only where there is a pad to move it. Arming a list takes Tk's own filled bar off
    # the selected row -- the highlight owns the filled bar, and there must be one of them --
    # so the Pi and the desk would be paying that price for a highlight that can never
    # appear. See pad_driven.
    monkeypatch.setattr(mod, "is_steam_deck", lambda: deck, raising=True)
    panel = _new_panel()
    groups = [panel._device_group, panel._mode_group]
    groups += [w for w in panel._option_widgets.values() if isinstance(w, DummyCheckBoxGroup)]

    assert len(groups) > 2, "the module rows, the mode rows and every radio setting"
    for group in groups:
        assert group.kwargs["cursor"] is deck


@pytest.mark.parametrize("linux", [True, False])
def test_the_highlight_is_armed_on_the_deck_rather_than_on_an_appliance(monkeypatch, linux: bool) -> None:
    # Not the platform test the panel's other three share: the Pi is a touch screen and the
    # Deck is a touch screen with a pad, so is_linux() cannot tell them apart -- a Pi armed
    # by that test would lose the filled bar to a highlight nothing can move. The answer is
    # the platform the install recorded, which is how admin_panel asks the same question.
    monkeypatch.setattr(mod, "is_linux", lambda: linux, raising=True)

    monkeypatch.setattr(mod, "is_steam_deck", lambda: False, raising=True)
    assert mod.pad_driven() is False

    monkeypatch.setattr(mod, "is_steam_deck", lambda: True, raising=True)
    assert mod.pad_driven() is True


def test_the_panel_opens_with_no_row_highlighted() -> None:
    # It is seeded afresh each time it is opened -- first page, whatever module the layout is
    # showing -- so a tint left over from the last time it was up would point at a row nobody
    # has stepped to in this pass.
    panel = _new_panel()
    panel._on_device_selected(SENSOR_TRACK.key)
    panel.pad_step(1)
    panel._show_page(mod.PAGE_OPTIONS)
    panel.pad_step(1)
    assert panel._device_group.cursor is not None
    assert panel._option_widgets[("sensor_track", "action")].cursor is not None

    panel.configure(CommandScope.ACC, 3, None)

    assert panel._device_group.cursor is None
    assert panel._option_widgets[("sensor_track", "action")].cursor is None


def test_the_pad_keys_ask_the_same_questions_the_nav_buttons_do() -> None:
    # One answer for the key and the pad, rather than two that could come to disagree about
    # whether the panel has anywhere left to go.
    panel = _new_panel()
    assert (panel.can_advance, panel._next_btn.enabled) == (False, False)

    panel._on_device_selected(BPC2.key)
    panel._refresh_nav()
    assert (panel.can_advance, panel._next_btn.enabled) == (True, True)
    assert (panel.can_go_back, panel._back_btn.visible) == (False, False)

    panel.next_page()
    assert (panel.can_go_back, panel._back_btn.visible) == (True, True)

    panel._show_page(mod.PAGE_REVIEW)
    assert (panel.can_advance, panel._next_btn.enabled) == (False, False)
    # And on the page where A presses Configure instead, the question it asks there.
    assert (panel.can_configure, panel._configure_btn.enabled) == (True, True)

    panel.set_sync_pending(True)
    assert (panel.can_configure, panel._configure_btn.enabled) == (False, False)


#
# Nothing runs off the screen
#
# The panel is drawn on a 480x800 pane at a font scale of 1.5 on the Pi and on a 640x800 pane
# at 0.9 on the Deck, and what it has to say is the registry's rather than its own -- a
# module's name, a mode's block of addresses, a sentence about what a setting does. Two rules
# hold it inside those panes: everything it writes is broken at the pane's width, and the
# pages are drawn in a window that keeps the buttons below them on the screen at any height.
#
# The second is the one worth stating plainly. Tk allots space in creation order, so a page
# too tall for the pane does not overflow it evenly -- it costs whatever was packed last, and
# what is packed last here is Back, Next and the Close that is the only way off the panel on
# an appliance.
#
def _every_widget(box: Any) -> list[Any]:
    """Every widget in box, however deep, box itself excepted."""
    found: list[Any] = []
    for child in getattr(box, "children", []):
        found.append(child)
        found.extend(_every_widget(child))
    return found


def _panel_widgets(panel: Any) -> list[Any]:
    """Everything the panel has drawn.

    The body holds it all: the window is packed into it, and the pages are inside the
    window, so walking the body reaches them without reaching them twice.
    """
    return _every_widget(panel._body)


def test_the_pages_are_drawn_in_a_window_and_the_buttons_below_it() -> None:
    # The whole point of the window: a page taller than the pane is scrolled inside it
    # instead of pushing what is under it off the screen, and what is under it is the row
    # that closes the panel. So the pages go in and nothing else does.
    panel, body, _host = _build_with_body()

    assert [page in panel.scroll.content.children for page in panel._pages] == [True] * len(panel._pages)
    assert body.children[2] is panel.scroll.viewport
    nav = panel._nav
    assert panel._back_btn in nav.children and panel._next_btn in nav.children
    assert body.children.index(panel.scroll.viewport) < body.children.index(nav)
    # As wide as the pane, so the window takes nothing off the page's own width.
    assert panel.scroll.width == panel._scroll_px == panel._pane_px


@pytest.mark.parametrize("deck, expected", [(True, mod.SCROLL_BAR_PX_DECK), (False, mod.SCROLL_BAR_PX)])
def test_the_bar_is_drawn_wide_enough_to_be_seen_and_wider_where_there_is_room(
    monkeypatch, deck: bool, expected: int
) -> None:
    # The bar is the only thing that says a page is being held back, and at the 6px it was
    # first drawn at it could not be told from the frame beside it on the Pi -- the one
    # screen that ever holds a page back was the one screen it was invisible on. Wider again
    # on the Deck, whose pane is a third wider: the bar is painted over the page, so what it
    # takes is taken from the right-hand end of a row, and the Deck has more of it to give.
    monkeypatch.setattr(mod, "is_steam_deck", lambda: deck, raising=True)

    assert mod.scroll_bar_px() == expected
    assert _new_panel().scroll.bar_px == expected


@pytest.mark.parametrize("deck", [True, False])
def test_no_bar_is_drawn_over_anything_the_page_has_written(monkeypatch, deck: bool) -> None:
    # What a bar may cover is nothing at all, and that is arranged rather than hoped for: the
    # page is drawn in the pane less the bar's own width, on either machine and whether or not
    # the page in hand overflows. Measured in a real Tk with that kept clear, the nearest ink
    # on any page of any module comes 33px inside a Pi pane against its 24px bar, and 48px
    # inside a Deck pane against its 30px one.
    monkeypatch.setattr(mod, "is_steam_deck", lambda: deck, raising=True)
    panel = _new_panel()

    assert panel._pane_px - panel._page_px == mod.scroll_bar_px()


def test_a_bar_is_drawn_wide_enough_to_be_worked_and_wider_where_there_is_width() -> None:
    # It has an arrow head at either end now and a trough between them, all three of which are
    # pressed rather than read: a part too small to aim at may as well be paint. The component
    # holds the floor, this holds the choice between the two panes.
    assert mod.SCROLL_BAR_PX_DECK > mod.SCROLL_BAR_PX, "wider where the pane has the width"
    assert mod.SCROLL_BAR_PX >= scroll_mod.BAR_PX


def test_a_page_is_come_to_at_its_top_and_the_window_re_fitted_for_it() -> None:
    # A page turned is a page begun, whatever the one before it was scrolled to. Re-fitted
    # after, not before: the fit is what clamps the offset to the new page, so a window
    # scrolled first could be left looking below the end of a shorter one.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)
    scroll = panel.scroll
    scroll.calls.clear()

    panel.next_page()

    # And shown, last of the three, that it moves -- which it can only be told once it has
    # been measured against the room there is; see test_a_page_being_held_back_says_so.
    assert scroll.calls == ["reset", "fit", "hint"]


def test_the_window_is_given_the_room_the_popup_leaves_it() -> None:
    # Measured rather than derived: what the panel draws above and below the window has
    # changed more than once, and a page rebuilt for another module changes the total again.
    # With nothing on screen to measure there is no budget to give, and a window sized off a
    # measurement Tk has not made would be a window of some arbitrary height.
    panel = _new_panel()

    assert panel._scroll_budget() is None
    assert panel.scroll.fits and set(panel.scroll.fits) == {None}


def test_the_window_asks_again_whenever_what_is_in_it_changes_size() -> None:
    # A page is not done growing when it is built -- a titled box shown for the module
    # chosen, a note arriving with the read-back -- and it is not done being laid out until
    # the popup is on screen, which is what watching the body is for: before that every
    # measurement of it reads 1.
    panel, body, _host = _build_with_body()

    assert panel.scroll.on_resize == panel._fit_scroll
    assert panel.scroll.watching == [body]
    assert panel.scroll.bindings >= 1, "and every row in it can be dragged"


def test_every_line_the_panel_writes_is_broken_at_the_pane() -> None:
    # Tk truncates nothing: a label wider than the popup is centered in it and loses its
    # beginning and its end at once. Asserted over every line rather than the ones that were
    # found overflowing, because what these lines say comes from the registry and from the
    # layout, and neither is bounded by anything that knows how wide the screen is.
    #
    # Every line but the ones that do not have the page to themselves: the one column of a
    # grid row that has the others beside it -- a module row's name, a listing row's
    # configuration -- and the presses, which stand inside a frame of their own. See the
    # tests below.
    panel = _new_panel()

    lines = [w for w in _panel_widgets(panel) if isinstance(w, DummyText)]
    bounded = [cell[mod.ROW_NAME_COLUMN] for cell in panel._assigned_cells + panel._overlap_cells]
    # The listing's configuration column is not a label but a stack of them, one per group of
    # a module's settings, and each block of it is broken at the column; see GroupedCell.
    bounded += [block for cell in panel._inventory_cells for block in cell[mod.INVENTORY_CONFIG_COLUMN].blocks]
    # And the review page's presses, whose frame is narrower than the page by the margin
    # either side of it: broken at the page's width they would be broken by the frame.
    bounded.append(panel._review_line)

    assert len(lines) > 10, "the pages' own prose, their headings and the boxes' cells"
    assert bounded, "the assigned box writes a row before an ID is even entered"
    assert [line.tk.configured.get("wraplength") for line in lines if line not in bounded] == [panel._wrap_px] * (
        len(lines) - len(bounded)
    )
    assert panel._review_line.tk.configured["wraplength"] == panel._manual_config_wrap_px < panel._wrap_px


def test_a_name_is_broken_inside_its_own_column_and_not_at_the_page() -> None:
    # What wrapping every cell at the page's width cannot do: three columns each free to
    # take the whole of it are three times too wide, and the row runs off the pane. Which is
    # how it read on a Pi with a train on the address -- a module's label is short enough to
    # have hidden this, a road name is not.
    panel = _new_panel()
    scope, name, ids = panel._assigned_cells[0]

    assert name.tk.configured["wraplength"] == panel._row_name_wrap_px
    assert panel._row_name_wrap_px < panel._wrap_px, "a column has less room than the page"
    # The two beside it break at the page, and are welcome to: neither can reach even a
    # third of a row. What they hold is a remote key and a block of addresses.
    for cell in (scope, ids):
        assert cell.tk.configured["wraplength"] == panel._wrap_px


def test_a_name_is_left_the_page_less_what_the_columns_beside_it_take() -> None:
    # Reserved rather than measured, and the reservation is a multiple of the cells' own
    # size because that is what the width of the two bounded columns follows: one font at
    # three sizes. See ROW_FIXED_COLUMNS_EMS for the measurements behind the multiple.
    panel = _new_panel()

    reserved = mod.ROW_FIXED_COLUMNS_EMS * panel._titled_text_size
    assert panel._row_name_wrap_px == panel._wrap_px - reserved
    assert panel._row_name_wrap_px > 0, "a column told to break at nothing is one that never breaks"


def test_the_listing_leaves_its_last_column_the_page_less_the_three_beside_it() -> None:
    # Reserved as a module row's name column is, and the reservation is a measurement rather
    # than a share of the row: the widest thing in each of the three bounded columns is that
    # column's own heading, bar an ID column of two digits, which comes to 151px at 12pt, 158
    # at 13 and 173 at 14 -- 12.6, 12.2 and 12.4 times the cells' own size. See
    # INVENTORY_FIXED_COLUMNS_EMS for the measurements behind the multiple.
    #
    # Taken with the listing's own size rather than the titled boxes', which is what the
    # larger text on this page is paid for with; see _inventory_text_size.
    panel = _new_panel()

    reserved = mod.INVENTORY_FIXED_COLUMNS_EMS * panel._inventory_text_size
    assert panel._inventory_config_wrap_px == panel._wrap_px - reserved
    cells = panel._inventory_cells[0]
    # Every block of that column, the column being a stack of them rather than a label; see
    # GroupedCell.
    blocks = cells[mod.INVENTORY_CONFIG_COLUMN].blocks
    assert blocks, "the heading is written on a block of its own"
    assert [block.tk.configured["wraplength"] for block in blocks] == [panel._inventory_config_wrap_px] * len(blocks)
    # The three beside it break at the page, and are welcome to: not one of them can reach
    # even a quarter of a row.
    for column in range(mod.INVENTORY_CONFIG_COLUMN):
        assert cells[column].tk.configured["wraplength"] == panel._wrap_px
    # Fewer ems than the module rows hold back for two columns, though this grid has three of
    # them: what an over-large reservation costs here is not the break a long line was going
    # to take anyway but a page of white space, the grid being centered in it. More than half
    # the page is left to the column that carries the module's configuration.
    assert mod.INVENTORY_FIXED_COLUMNS_EMS < mod.ROW_FIXED_COLUMNS_EMS
    assert panel._inventory_config_wrap_px > panel._wrap_px // 2


def test_the_configuration_column_keeps_a_share_of_the_row_where_the_reservation_would_swallow_it(
    monkeypatch,
) -> None:
    # The floor, and it has to be a floor and not a subtraction: a column left with nothing
    # is a column told to break at zero, which in Tk is how a line is told not to break at
    # all -- and the line this one carries is the longest the panel writes.
    panel = _new_panel()
    monkeypatch.setattr(mod, "INVENTORY_FIXED_COLUMNS_EMS", mod.MIN_WRAP_PX, raising=True)

    assert panel._inventory_config_wrap_px == panel._wrap_px // mod.INVENTORY_COLUMNS
    assert panel._inventory_config_wrap_px > 0


def test_a_name_keeps_a_share_of_the_row_on_a_pane_too_narrow_to_reserve_from() -> None:
    # The floor, and it has to be a floor and not a subtraction: past this point the
    # reservation is the whole of the pane, and a column left with nothing is a column told
    # to break at zero -- which is how Tk is told not to break a line at all.
    host = _new_host()
    host.width = 0
    host.emergency_box_width = 0
    panel = mod.LcsConfigPanel(host)
    panel.build(DummyBox())

    assert panel._wrap_px == mod.MIN_WRAP_PX
    assert panel._row_name_wrap_px == mod.MIN_WRAP_PX // mod.ROW_COLUMNS
    assert panel._row_name_wrap_px > 0


def test_every_row_the_panel_draws_is_broken_inside_the_pane() -> None:
    # And the rows likewise, at the narrower width a row has: the indicator and the padding
    # around it come off the front of every one of them. Cut instead, what a mode row loses
    # is the block of TMCC IDs at the end of it -- the one fact the row is chosen for.
    panel = _new_panel()

    groups = [w for w in _panel_widgets(panel) if isinstance(w, DummyCheckBoxGroup)]

    assert len(groups) == 6, (
        "the modules, the modes, the Sensor Track's actions, the AMC2's two motors, the listing's sort keys"
    )
    for group in groups:
        wrap = group.kwargs["wrap"]
        assert wrap == panel._row_wrap_px(group.kwargs["size"])
        assert wrap < panel._wrap_px, "a row has less room for words than a line of prose"


def test_a_row_is_left_the_pane_less_what_it_spends_before_its_text() -> None:
    # The component's own arithmetic, asked rather than repeated here: the indicator grows
    # with the font and the rest of it does not, so a bigger row is not merely a taller one.
    panel = _new_panel()
    host = panel.gui

    for size in (host.s_12, host.s_18):
        assert panel._row_wrap_px(size) == panel._titled_box_px - RealCheckBoxGroup.row_chrome_for(size, "radio")
    assert panel._row_wrap_px(host.s_18) < panel._row_wrap_px(host.s_12)


def test_a_row_keeps_a_floor_of_room_on_a_host_that_has_measured_nothing() -> None:
    # A pane of no width is a pane that has not been drawn yet, and a wrap of nothing would
    # break every row after its first word.
    host = _new_host()
    host.width = 0
    host.emergency_box_width = 0
    panel = mod.LcsConfigPanel(host)
    panel.build(DummyBox())

    assert panel._row_wrap_px(host.s_18) == mod.MIN_WRAP_PX


def test_the_mode_rows_are_sized_against_every_row_they_can_show(monkeypatch) -> None:
    # The list is rebuilt whenever the module or the address changes, so a size fitted to
    # the module in hand would redraw it larger or smaller under the operator's eyes. Fitted
    # once, to everything it could ever hold, and settled: it is an answer about the screen.
    asked: list[dict[str, Any]] = []

    def _spy(master: Any, texts: Any, width: int, ceiling: int, floor: int = None, style: str = "radio") -> int:
        asked.append(dict(texts=list(texts), width=width, ceiling=ceiling, floor=floor))
        return ceiling

    monkeypatch.setattr(DummyCheckBoxGroup, "fit_row_size", staticmethod(_spy), raising=True)
    panel = _new_panel()
    host = panel.gui

    modes = next(call for call in asked if call["texts"] == mod.every_mode_label())
    assert (modes["ceiling"], modes["floor"]) == (host.s_18, host.s_12)
    assert modes["width"] == panel._titled_box_px
    assert panel._mode_group.kwargs["size"] == host.s_18, "the size asked for, where it fits"

    before = len(asked)
    assert panel._mode_row_size == panel._mode_row_size
    assert len(asked) == before, "settled once and kept"


def test_the_module_rows_are_fitted_a_step_above_the_mode_rows(monkeypatch) -> None:
    # The first choice the panel asks for, and a touch target on the Pi and the Deck, so it
    # is drawn above the page's body size -- and above the other list of touch targets, these
    # being the shortest rows the panel draws. Fitted rather than simply set: these labels are
    # the registry's to lengthen, and the Pi's fonts are scaled up far enough that the size
    # asked for there does not fit.
    asked: list[dict[str, Any]] = []

    def _spy(master: Any, texts: Any, width: int, ceiling: int, floor: int = None, style: str = "radio") -> int:
        asked.append(dict(texts=list(texts), width=width, ceiling=ceiling, floor=floor))
        return ceiling

    monkeypatch.setattr(DummyCheckBoxGroup, "fit_row_size", staticmethod(_spy), raising=True)
    panel = _new_panel()
    host = panel.gui

    labels = [label for label, _key in mod.LcsConfigPanel.device_options()]
    modules = next(call for call in asked if call["texts"] == labels)
    assert (modules["ceiling"], modules["floor"]) == (host.s_20, host.s_12)
    assert modules["width"] == panel._titled_box_px
    assert panel._device_group.kwargs["size"] == host.s_20, "the size asked for, where it fits"


def test_every_mode_label_is_a_row_a_module_can_show_at_its_widest() -> None:
    # What the fit is measured against, and it has to be the whole of it: a mode left out is
    # a row that can still come to be drawn wider than the screen. At each mode's highest
    # base, where its block carries two-digit addresses at both ends.
    labels = mod.every_mode_label()

    expected = [
        mode.ids_label(mode.max_base) for device in reg.configurable_devices() for mode in device.modes if mode.enabled
    ]
    assert labels == expected
    assert any("98" in label for label in labels), "the widest block a mode can claim"


def test_the_pad_brings_the_row_it_steps_onto_into_view() -> None:
    # A list can be longer than the window it is drawn in, and a highlight stepped below the
    # fold would leave the pad pointing at something the operator cannot see.
    panel = _new_panel()
    panel._on_device_selected(SENSOR_TRACK.key)
    panel._show_page(mod.PAGE_OPTIONS)
    scroll = panel.scroll
    scroll.shown.clear()

    assert panel.pad_step(1) is True

    assert scroll.shown == [panel.pad_cursor], "the row the tint is on, and not another"


def test_a_step_that_moves_nothing_scrolls_nothing() -> None:
    # The pad held against the end of a list stays there, and a window that jumped anyway
    # would be the one thing on the page still moving.
    panel = _new_panel()
    scroll = panel.scroll
    panel.pad_step(1)
    scroll.shown.clear()

    assert panel.pad_step(-1) is False

    assert scroll.shown == []


@pytest.mark.parametrize(
    "linux, deck, cramped",
    [(True, False, True), (True, True, False), (False, False, False)],
)
def test_the_pi_is_the_pane_with_nothing_to_spare(monkeypatch, linux: bool, deck: bool, cramped: bool) -> None:
    # The Pi alone: two thirds of the Deck's width at a third again its text size. is_linux
    # by itself would take the Deck in with it, and the Deck has the room.
    monkeypatch.setattr(mod, "is_linux", lambda: linux, raising=True)
    monkeypatch.setattr(mod, "is_steam_deck", lambda: deck, raising=True)

    assert mod.cramped_pane() is cramped

    panel = _new_panel()
    host = panel.gui
    assert panel._titled_text_size == (host.s_12 if cramped else host.s_14)


def test_the_titled_boxes_and_their_rows_read_at_one_size(monkeypatch) -> None:
    # Three headings and, under two of them, what the layout already has at the address:
    # read rather than aimed at, so they are the first thing to give where the pane is tight.
    # One size for the lot -- a box whose title and rows disagreed would read as two things.
    monkeypatch.setattr(mod, "is_linux", lambda: True, raising=True)
    panel = _new_panel()
    panel._set_base_id(1)
    size = panel._titled_text_size

    assert size < panel.gui.s_14
    assert [box.text_size for box in (panel._mode_box, panel._assigned_box, panel._overlap_box)] == [size] * 3
    assert [cell.text_size for cell in panel._assigned_cells[0]] == [size] * mod.ROW_COLUMNS


#
# The My Modules listing
#
def _a_layout_of_three(monkeypatch) -> None:
    """Three modules on two remote keys, each in a mode of its own.

    A BPC2 addressed as ACC 1 - 8 and remembering its relays, an ASC2 driving switch motors
    at SW 20 - 23, and an STM2 holding SW 40 - 55. Reported through the PDI store, which is
    where a module's own settings are: the component state carries none of them.
    """
    _with_pdi_store(
        monkeypatch,
        {
            PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2, restore=True)],
            PdiDevice.ASC2: [FakePdiConfig(20, CommandScope.SWITCH, mode=2)],
            PdiDevice.STM2: [FakePdiConfig(40, CommandScope.SWITCH, mode=0)],
        },
    )


def _listed(panel: mod.LcsConfigPanel) -> list[tuple[str, str, str]]:
    """
    The listing as it reads down the page: the module, its base ID and its remote key.
    """
    return [(row.module, row.tmcc_id, row.scope) for row in panel.inventory_rows()]


# The row widgets are the panel's own, and reading them is the point of this helper.
# noinspection PyProtectedMember
def _listing_grid(panel: mod.LcsConfigPanel) -> list[tuple[str, ...]]:
    """
    What was actually written into the grid, headings included, spare rows left out.
    """
    return [tuple(cell.value for cell in row) for row in panel._inventory_cells if row[0].visible]


def test_the_listing_names_every_module_the_layout_reports(monkeypatch) -> None:
    # The whole layout rather than the entered ID's block: this is the one page the panel
    # speaks about modules it is not programming, and what it is for is seeing what is out
    # there before choosing an address to program.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()

    assert _listed(panel) == [
        (ASC2.label, "20", "SW"),
        (BPC2.label, "1", "ACC"),
        (STM2.label, "40", "SW"),
    ]


def test_the_listing_calls_the_ir_sensor_track_the_ir(monkeypatch) -> None:
    # The listing's own name for a module, which is the short one that reads as a name in a
    # column of ASC2, BPC2 and STM2. The listing alone: the pages that program the module
    # name it as the registry does -- the IR Sensor Track, in full -- and the first page
    # offers it under that name.
    _sensor_track_based_at(monkeypatch, 3, IrdaSequence.CROSSING_GATE_NONE)
    panel = _new_panel()

    assert [(row.module, row.tmcc_id) for row in panel.inventory_rows()] == [("IR", "3")]
    assert mod.INVENTORY_MODULE_NAMES[SENSOR_TRACK.key] == "IR"
    assert SENSOR_TRACK.label == "IR Sensor Track"
    assert [label for label, key in panel.device_options() if key == SENSOR_TRACK.key] == [
        f"{SENSOR_TRACK.label} ({SENSOR_TRACK.blurb})"
    ]
    # And it is ordered by the name the listing gives it, or the Module column would not read
    # down the page in the order it is sorted by.
    assert panel._inventory_key(panel.inventory_occupants()[0])[0] == "IR"


def test_the_last_column_says_what_a_module_is_set_to(monkeypatch) -> None:
    # The column the page is for: a line for the mode, a line for the block of addresses it
    # takes on the key it answers to, and a line for each setting the module reports. The
    # block is spelled with its key in front of it, as the ID page spells the one it is about
    # to program; the setting is named as the options page names it, and reads Yes or No.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()

    listed = {row.module: row.config.split("\n") for row in panel.inventory_rows()}
    # The BPC2's mode is named "ACC" and nothing else, which the Scope column beside it has
    # already said; see the test below.
    assert listed[BPC2.label] == [
        "ACC 1 - 8",
        f"{mod.INVENTORY_RESTORE}: {mod.INVENTORY_YES}",
    ]
    # A mode whose name carries what it is good for keeps it, and a module reporting no
    # settings of its own says nothing further: the ASC2 declares none at all.
    assert listed[ASC2.label] == [ASC2.mode("sw_momentary").name, "SW 20 - 23"]
    assert listed[STM2.label] == [STM2.mode("single_wire").name, "SW 40 - 55"]


def test_a_mode_named_for_nothing_but_the_remote_key_is_left_unsaid(monkeypatch) -> None:
    # "ACC" under Configuration, beside a Scope column reading ACC, is that column again: a
    # line read as a fact about the module that turns out to be an echo, in the one column of
    # the page that is already several lines tall. A mode named for what it is *for* stays,
    # all of it -- "ACC (mixed)" answers which of the module's modes it is in, and no other
    # column touches that.
    _with_pdi_store(
        monkeypatch,
        {
            PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2, restore=True)],
            PdiDevice.ASC2: [FakePdiConfig(30, CommandScope.ACC, mode=0)],
        },
    )
    panel = _new_panel()

    listed = {row.module: row.config.split("\n") for row in panel.inventory_rows()}
    assert BPC2.mode("acc_8").name == "ACC" == listed[BPC2.label][0].split(" ")[0]
    assert BPC2.mode("acc_8").name not in listed[BPC2.label]
    assert listed[ASC2.label] == [ASC2.mode("acc_8").name, "ACC 30 - 37"]
    assert listed[ASC2.label][0] == "ACC (mixed)"


def test_a_block_of_one_address_is_left_to_the_id_column(monkeypatch) -> None:
    # "ACC 50" beside a row reading IR / 50 / ACC is those two columns read back: the
    # line is worth its height where it says how far a block runs past the address the ID
    # column names, which is what "ACC 1 - 8" says and a single address does not.
    _sensor_track_based_at(monkeypatch, 50, IrdaSequence.CROSSING_GATE_NONE)
    panel = _new_panel()

    action = SENSOR_TRACK.option("action")
    chosen = next(label for label, value in action.choices if value is IrdaSequence.CROSSING_GATE_NONE)
    assert panel.inventory_rows()[0].config.split("\n") == [f"{action.label}: {chosen}"]
    # The mode goes with it, being the Scope column again -- so the row says the one thing
    # about the module the three columns beside it cannot.
    assert SENSOR_TRACK.mode("acc").name == "ACC"
    assert (panel.inventory_rows()[0].tmcc_id, panel.inventory_rows()[0].scope) == ("50", "ACC")


def test_a_module_with_nothing_of_its_own_to_say_says_nothing() -> None:
    # An IR Sensor Track known from control traffic alone: its one mode is named for the
    # remote key, it holds the single address the ID column names, and the Action Command it
    # is running with is recorded in the IRDA CONFIG record it has not published. Everything
    # known about it is in the three columns beside the last, so the last is left empty
    # rather than filled with either of them again.
    panel = _new_panel(FakeStore({CommandScope.ACC: [FakeState(50, "is_sensor_track")]}))

    row = panel.inventory_rows()[0]
    assert (row.module, row.tmcc_id, row.scope) == ("IR", "50", "ACC")
    assert row.config == ""


def test_a_flag_the_module_reports_as_off_is_written_as_off(monkeypatch) -> None:
    # Not the same thing as a setting the module has said nothing about: a BPC2 that
    # reported its relays are not remembered has told the operator something, and the line
    # is the answer rather than the absence of one.
    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2, restore=False)]})
    panel = _new_panel()

    assert panel.inventory_rows()[0].config.endswith(f"{mod.INVENTORY_RESTORE}: {mod.INVENTORY_NO}")


def test_the_listing_says_on_one_line_what_the_options_page_says_in_a_sentence(monkeypatch) -> None:
    # "Restore last relay settings on power-up" is written to be read beside the box that
    # decides it, and it has an options row to say it in. Wrapped at this column's width it
    # is two lines of the tallest column in the panel, on every BPC2 the layout holds, to say
    # what one line says -- and the row is being read to see what the module is set to rather
    # than to decide anything. Worded for the line it is read on: it says when the module
    # restores and leaves what it restores to the module named two columns over, which is how
    # one name serves a BPC2's relays and an AMC2's motors alike.
    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2, restore=True)]})
    panel = _new_panel()

    assert mod.INVENTORY_RESTORE == "Restore on power-up"
    assert panel.inventory_rows()[0].config.split("\n")[-1] == f"{mod.INVENTORY_RESTORE}: {mod.INVENTORY_YES}"
    # The listing's own name for it and no other page's: the setting is still labeled as it
    # was, and that label is what the box on the options page is drawn with.
    assert BPC2.option("restore").label == "Restore last relay settings on power-up"
    panel._on_device_selected(BPC2.key)
    assert panel._option_widgets[(BPC2.key, "restore")].text == BPC2.option("restore").label


def test_the_motor_a_setting_belongs_to_is_named_once(monkeypatch) -> None:
    # The AMC2 labels both its remember flags alike, so a verdict faulting one has to put the
    # motor in front of it. Here the motor is already on the page: the column writes every
    # setting the module reports, in the module's own order, so each flag stands directly
    # under the line naming the motor whose mode it is -- and naming the motor again in the
    # flag's own line is a line and a half of the column saying what the line above just did.
    _amc2_based_at(monkeypatch, 1, (_motor(1, OutputType.AC, restore=True), _motor(2, OutputType.NORMAL)))
    panel = _new_panel()

    assert [option.label for option in AMC2.options].count("Remember speed on power-up") == 2
    assert panel.inventory_rows()[0].config.split("\n") == [
        "Motor #1: AC",
        f"{mod.INVENTORY_RESTORE}: {mod.INVENTORY_YES}",
        # The second motor begins rather than carrying on from the first. An empty line is
        # how the listing writes that break; what it comes out as on the page is the cell's
        # business, and it is a few pixels rather than a line of its own -- see the tests of
        # GroupedCell below. Nothing above the first group: it is being told from nothing,
        # and a break there is a hole under the module's addresses.
        mod.INVENTORY_GROUP_GAP,
        "Motor #2: Continuous (DC)",
        f"{mod.INVENTORY_RESTORE}: {mod.INVENTORY_NO}",
    ]
    # A verdict has no line above it to lean on, and still names the motor it faults.
    assert mod.LcsConfigPanel._option_name(AMC2, AMC2.option("motor1_restore")).startswith("Motor #1")


def test_a_module_whose_settings_are_one_block_is_written_as_one(monkeypatch) -> None:
    # Only a heading other settings hang from opens a group of its own, and the AMC2 is the
    # one module the registry holds that has any -- a mode and a remember flag for each of
    # its two motors, the flags labeled alike. A BPC2 reports its block of addresses and one
    # flag, which are the block they read as, and a break between them would be white space
    # holding nothing apart.
    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2, restore=True)]})
    panel = _new_panel()

    assert mod.INVENTORY_GROUP_GAP == "", "an empty line, which is how the listing writes a break"
    assert mod.INVENTORY_GROUP_GAP not in panel.inventory_rows()[0].config.split("\n")
    # Read off the rule a verdict names a setting by, so the two cannot come to disagree
    # about what stands under what; see _option_heading.
    assert mod.LcsConfigPanel._inventory_group_heads(AMC2) == {"motor1_mode", "motor2_mode"}
    assert [mod.LcsConfigPanel._inventory_group_heads(device) for device in (ASC2, BPC2, STM2, SENSOR_TRACK)] == [
        set()
    ] * 4


def test_the_configuration_column_says_nothing_about_the_module_firmware(monkeypatch) -> None:
    # A version number is a fact about the module rather than about how it is configured, and
    # this is the column read to see how a layout is addressed: a line of it down every row
    # is a line per module answering a question the page is not open for.
    _a_layout_of_three(monkeypatch)
    state = FakeState(1, "is_bpc2", mode=2)
    state.firmware = "1.2"
    panel = _new_panel(FakeStore({CommandScope.ACC: [state]}))

    rows = panel.inventory_rows()
    assert [row.config for row in rows if row.module == BPC2.label] == [
        "\n".join(
            (
                "ACC 1 - 8",
                f"{mod.INVENTORY_RESTORE}: {mod.INVENTORY_YES}",
            )
        )
    ]
    assert all(state.firmware not in row.config for row in rows)


def test_a_module_that_has_not_said_which_mode_it_is_in_says_so() -> None:
    # A module known from control traffic alone has published no CONFIG record, so nothing
    # says which mode it is in or what it is set to. The listing says the one and invents
    # neither: a mode written in for it would be the panel telling the operator something the
    # module has not.
    panel = _new_panel(FakeStore({CommandScope.ACC: [FakeState(9, "is_asc2")]}))

    row = panel.inventory_rows()[0]
    assert (row.module, row.tmcc_id, row.scope) == (ASC2.label, "9", "ACC")
    # And that is the whole of the column: not knowing the mode, the panel takes the module
    # for a single address, which the ID column beside it already names.
    assert row.config.split("\n") == [mod.INVENTORY_MODE_UNKNOWN]


@pytest.mark.parametrize(
    "sort_key, expected",
    [
        # By name, which is what the page opens on: a tally of what kinds of module are out
        # there. By address, for an operator looking for a free one. By remote key, in the
        # order the panel names the keys everywhere else -- and within a key, by name again,
        # so the rows under it do not shuffle as the layout reports itself.
        (mod.SORT_MODULE, [(ASC2.label, "20"), (BPC2.label, "1"), (STM2.label, "40")]),
        (mod.SORT_ID, [(BPC2.label, "1"), (ASC2.label, "20"), (STM2.label, "40")]),
        (mod.SORT_SCOPE, [(BPC2.label, "1"), (ASC2.label, "20"), (STM2.label, "40")]),
    ],
)
def test_the_listing_is_ordered_by_the_key_the_operator_chooses(
    monkeypatch, sort_key: str, expected: list[tuple[str, str]]
) -> None:
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()

    panel._on_sort_selected(sort_key)

    assert [(row.module, row.tmcc_id) for row in panel.inventory_rows()] == expected
    assert [(module, tmcc_id) for module, tmcc_id, _scope in _listed(panel)] == expected


def test_the_key_the_page_opens_on_is_the_one_the_rows_show(monkeypatch) -> None:
    # The radios and the order have to be the same fact: a page opening on a row whose order
    # the rows are not in would be a page lying about itself before it is touched.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()

    assert panel._sort_group.kwargs["selected"] == mod.SORT_MODULE
    assert [label for label, _key in mod.INVENTORY_SORTS] == ["Module", "ID", "Scope"]
    assert _listed(panel) == sorted(_listed(panel), key=lambda row: row[0].upper())


def test_a_key_the_page_does_not_offer_leaves_the_order_alone(monkeypatch) -> None:
    # The value comes out of a Tk StringVar, which answers with whatever string it was
    # handed -- "None" among them.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()
    panel._on_sort_selected(mod.SORT_ID)

    panel._on_sort_selected("no_such_key")

    assert [row.tmcc_id for row in panel.inventory_rows()] == ["1", "20", "40"]


def test_the_listing_is_written_into_a_grid_under_its_headings(monkeypatch) -> None:
    # Gridded so the columns line up down the page however long the names above them run,
    # and the headings are the grid's own first row so they stand over the columns they name.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()

    grid = _listing_grid(panel)
    assert grid[0] == mod.INVENTORY_HEADINGS
    assert [row[:3] for row in grid[1:]] == [
        (ASC2.label, "20", "SW"),
        (BPC2.label, "1", "ACC"),
        (STM2.label, "40", "SW"),
    ]
    # The last column carries the module's whole configuration, at whatever length it runs
    # to: the one multi-line cell the panel writes.
    assert "\n" in grid[2][mod.INVENTORY_CONFIG_COLUMN]
    assert all(cell.text_bold for cell in panel._inventory_cells[0]), "a heading in every column"


def test_every_cell_stands_at_the_top_of_its_row(monkeypatch) -> None:
    # A row is as tall as its configuration column, that being the one column with several
    # lines in it, and a cell placed as guizero places it -- sticky="W", from its align -- is
    # centered against that height: "BPC2" floats halfway down a five-line row instead of
    # standing beside the first line of what the module is set to.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()

    assert mod.INVENTORY_STICKY == "nw", "the top of the row, and the left of the column"
    assert [cell.tk.gridded["sticky"] for row in panel._inventory_cells for cell in row] == [mod.INVENTORY_STICKY] * (
        len(panel._inventory_cells) * mod.INVENTORY_COLUMNS
    )


def test_the_cells_are_stood_up_again_after_a_re_order(monkeypatch) -> None:
    # guizero rebuilds a container's grid options from scratch whenever a child is shown or
    # hidden, and a re-order does both: set once where the cells are built, the alignment
    # would hold only until the first press of a sort key.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()
    for row in panel._inventory_cells:
        for cell in row:
            cell.tk.gridded.clear()

    panel._on_sort_selected(mod.SORT_ID)

    assert all(cell.tk.gridded.get("sticky") == mod.INVENTORY_STICKY for row in panel._inventory_cells for cell in row)


@pytest.mark.parametrize("linux, cramped", [(True, True), (False, False)])
def test_the_listing_reads_at_the_page_body_size_on_every_screen(monkeypatch, linux: bool, cramped: bool) -> None:
    # The listing's grid is built by the very code that builds the module rows of the ID
    # page, and those rows take the size of the titled boxes they stand in -- a size down on
    # the Pi, which is what makes that page, three quarters of it boxes, fit the screen at
    # all. This page has none of that: a heading, three sort keys and a grid, and it is
    # scrolled, so what it cannot show it scrolls to. Nothing was bought there by drawing it
    # small, and what it cost was that the one page in the panel which is nothing but reading
    # matter was set in the smallest text on any of them.
    #
    # So the listing is a size up on the Pi and the same size everywhere. It is paid for in
    # width, the size being the multiple the three bounded columns are reserved by: the
    # configuration column breaks at 250px rather than 276, at which the IR Sensor Track's
    # action takes the second line it was given leave to take (311px) and every other line
    # the registry can write still holds -- the widest are 236px and 221 against that 250.
    # See _inventory_text_size for the measurements at the sizes either side of it.
    monkeypatch.setattr(mod, "is_linux", lambda: linux, raising=True)
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()
    host = panel.gui
    panel._set_base_id(1)
    size = panel._inventory_text_size

    assert size == host.s_14
    assert cramped == (panel._titled_text_size < size), "a size up exactly where the boxes step down"
    # Every word on the page, the heading keeping its own step above the lot.
    row = panel._inventory_cells[1]
    assert [cell.text_size for cell in row[: mod.INVENTORY_CONFIG_COLUMN]] == [size] * mod.INVENTORY_CONFIG_COLUMN
    assert [block.text_size for block in row[mod.INVENTORY_CONFIG_COLUMN].blocks] == [size]
    assert panel._sort_group.kwargs["size"] == size
    sort_box = next(
        child for child in panel._pages[mod.PAGE_INVENTORY].children if child.text == mod.INVENTORY_SORT_TITLE
    )
    assert sort_box.text_size == size
    assert panel._inventory_empty_line.text_size == size
    # And the rows of the ID page are left where they were, which is the whole of the reason
    # the size had to become the grid's rather than the panel's.
    assert [cell.text_size for cell in panel._assigned_cells[0]] == [panel._titled_text_size] * mod.ROW_COLUMNS


def test_a_group_of_settings_begins_a_few_pixels_below_the_one_above_it(monkeypatch) -> None:
    # What an empty line in the text comes out as on the page. A cell of wrapped text has no
    # white space but its own lines, and one line of this column costs the row a whole line's
    # height -- 23px at the size the listing is drawn at, 20 on a Deck -- which read as
    # further between one motor and the next than between one module and the next, there being
    # nothing at all between two modules. So the cell is the groups themselves, a label
    # apiece, and what holds them apart is padding: 6px, a quarter of a line at 14pt.
    _amc2_based_at(monkeypatch, 1, (_motor(1, OutputType.AC, restore=True), _motor(2, OutputType.NORMAL)))
    panel = _new_panel()

    cell = panel._inventory_cells[1][mod.INVENTORY_CONFIG_COLUMN]
    assert [block.value for block in cell.blocks] == [
        f"Motor #1: AC\n{mod.INVENTORY_RESTORE}: {mod.INVENTORY_YES}",
        f"Motor #2: Continuous (DC)\n{mod.INVENTORY_RESTORE}: {mod.INVENTORY_NO}",
    ]
    # Above the second block and not the first: the space says the group below it begins, and
    # above the first there is nothing to tell it from.
    assert [block.tk.packed["pady"] for block in cell.blocks] == [(0, 0), (mod.INVENTORY_GROUP_GAP_PX, 0)]
    # A break rather than a line, which is the whole of the change: a line of this column is
    # taller again than the size it is drawn at.
    assert 0 < mod.INVENTORY_GROUP_GAP_PX < panel._inventory_text_size
    # And the listing still writes one string per module, empty line and all: what the break
    # looks like is the cell's business, and the row's business is what the module reports.
    assert cell.value == panel.inventory_rows()[0].config
    assert mod.INVENTORY_GROUP_BREAK in cell.value


def test_a_module_with_one_group_of_settings_has_nothing_to_hold_apart(monkeypatch) -> None:
    # A BPC2's block of addresses and its one flag are one group, and a cell with one block
    # in it is a cell that reads exactly as the label it used to be.
    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2, restore=True)]})
    panel = _new_panel()

    cell = panel._inventory_cells[1][mod.INVENTORY_CONFIG_COLUMN]
    assert [block.value for block in cell.blocks] == [panel.inventory_rows()[0].config]
    assert cell.blocks[0].tk.packed["pady"] == (0, 0)


def test_the_blocks_of_a_cell_are_spaced_again_after_a_re_order(monkeypatch) -> None:
    # guizero rebuilds a container's pack options from scratch whenever a child is shown or
    # hidden, and padding is not among the options it replays: set once where the blocks are
    # built, the space between them would hold only until the first press of a sort key.
    # Measured in a live window -- a block hidden and shown again comes back against the one
    # above it. The same defect the alignment above has, answered the same way.
    _amc2_based_at(monkeypatch, 1, (_motor(1, OutputType.AC, restore=True), _motor(2, OutputType.NORMAL)))
    panel = _new_panel()
    cell = panel._inventory_cells[1][mod.INVENTORY_CONFIG_COLUMN]
    for block in cell.blocks:
        block.tk.packed.clear()

    panel._on_sort_selected(mod.SORT_ID)

    assert [block.tk.packed.get("pady") for block in cell.blocks] == [(0, 0), (mod.INVENTORY_GROUP_GAP_PX, 0)]


def test_a_block_left_over_from_a_fuller_module_is_taken_off_the_page(monkeypatch) -> None:
    # An empty label still stands a line tall, so a cell written for one group after being
    # written for two would keep the height of the fuller module. And the spare block is left
    # where it is rather than spaced: pack_configure *manages* a widget pack has forgotten,
    # so padding replayed onto it would put it back on the page carrying the second motor of
    # a module that is no longer in this row.
    _amc2_based_at(monkeypatch, 1, (_motor(1, OutputType.AC, restore=True), _motor(2, OutputType.NORMAL)))
    panel = _new_panel()
    cell = panel._inventory_cells[1][mod.INVENTORY_CONFIG_COLUMN]
    assert len(cell.blocks) == 2
    for block in cell.blocks:
        block.tk.packed.clear()

    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2, restore=True)]})
    panel.show_inventory()

    assert [block.visible for block in cell.blocks] == [True, False]
    assert cell.value == panel.inventory_rows()[0].config, "the BPC2 stands in that row now"
    assert [block.tk.packed.get("pady") for block in cell.blocks] == [(0, 0), None]


def test_a_row_the_page_is_no_longer_showing_is_left_where_it_is(monkeypatch) -> None:
    # Not an optimization: grid_configure *manages* a widget the grid has forgotten, so
    # replaying a spare row's alignment would put it back on the page carrying the text of
    # the fuller layout it was last written for.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()
    for row in panel._inventory_cells:
        for cell in row:
            cell.tk.gridded.clear()

    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2)]})
    panel.show_inventory()

    # The headings, the one module still reported, and the two rows that went with the
    # others: only what is on the page was placed again.
    assert [bool(row[0].tk.gridded) for row in panel._inventory_cells] == [True, True, False, False]


def test_a_row_left_over_from_a_fuller_layout_is_taken_off_the_page(monkeypatch) -> None:
    # Hidden rather than blanked, as the module boxes hide theirs: an empty label still
    # stands a line tall, so the page would keep the height of the fullest layout it had
    # ever shown.
    _a_layout_of_three(monkeypatch)
    panel = _new_panel()
    assert len(_listing_grid(panel)) == 4  # the headings and the three modules

    _with_pdi_store(monkeypatch, {PdiDevice.BPC2: [FakePdiConfig(1, CommandScope.ACC, mode=2)]})
    panel.show_inventory()

    assert [row[0] for row in _listing_grid(panel)] == [mod.INVENTORY_HEADINGS[0], BPC2.label]
    assert len(panel._inventory_cells) == 4, "the cells are kept and reused, not destroyed"


def test_a_layout_that_has_reported_nothing_says_so_rather_than_showing_a_bare_grid() -> None:
    # Which is how the panel opens before the Base 3 has been heard from. A grid standing
    # empty under its own headings reads as a page that looked and failed.
    panel = _new_panel()

    assert panel.inventory_rows() == []
    assert panel._inventory_empty_line.value == mod.INVENTORY_EMPTY
    assert panel._inventory_empty_line.visible is True
    assert all(not cell.visible for cell in panel._inventory_cells[0]), "the headings go with the rows"


def test_the_listing_is_read_afresh_each_time_it_is_opened(monkeypatch) -> None:
    # Modules report themselves as the Base 3 gets round to them, and what the operator is
    # owed is a listing that is true when they ask for it.
    panel = _new_panel()
    assert panel.inventory_rows() == []

    _a_layout_of_three(monkeypatch)
    panel.show_inventory()

    assert panel.page_index == mod.PAGE_INVENTORY
    assert len(_listing_grid(panel)) == 4
    assert panel._inventory_empty_line.visible is False


def test_the_key_that_opens_the_listing_stands_left_of_next() -> None:
    # On the panel's own row of keys, and on the first page -- what is already out on the
    # layout is what an operator wants to know before they program anything -- where Back is
    # not there to stand right of. Left of Next because it is created before it: guizero packs
    # a row in creation order. See _build_nav.
    panel = _new_panel()
    row = panel._nav

    assert panel._inventory_btn.text == mod.INVENTORY_TEXT
    assert row.children.index(panel._inventory_btn) < row.children.index(panel._next_btn)
    assert panel._inventory_btn not in panel._pages[mod.PAGE_DEVICE].children
    assert panel._inventory_btn.kwargs["align"] == panel._next_btn.kwargs["align"] == "left"
    # And no width of its own, where Back and Next are eight characters wide: what is written
    # on it is two words, and read back in a live window with the shared look it comes to
    # 191px against those keys' 184 -- so the pair of them is a 455px row of the Pi's 480px
    # pane, centered within a pixel of the pane's own middle.
    assert "width" not in panel._inventory_btn.kwargs

    panel._inventory_btn.command()

    assert panel.page_index == mod.PAGE_INVENTORY


def test_the_key_that_opens_the_listing_is_shown_on_the_first_page_alone() -> None:
    # It asks a question about the layout rather than about the module being configured, and
    # the first page is where that is asked -- before anything has been chosen. Past it the
    # operator is working on one module, and on the listing there is nothing for the key to
    # open.
    #
    # Which is also what keeps the row inside the pane: it is shown exactly where Back is not,
    # so the row is never three keys wide -- measured with the shared look, two are 455px of
    # the Pi's 480px pane and three are 679. See shows_inventory_key.
    panel = _new_panel()
    panel._on_device_selected(BPC2.key)

    assert (panel.shows_inventory_key, panel._inventory_btn.visible) == (True, True)
    for page in (mod.PAGE_ID, mod.PAGE_OPTIONS, mod.PAGE_REVIEW, mod.PAGE_INVENTORY):
        panel._show_page(page)
        assert panel.shows_inventory_key is False
        assert panel._inventory_btn.visible is False, "and a hidden key cannot be pressed"
        assert panel._inventory_btn.enabled is False
        assert panel._back_btn.visible is True, "the key stands in the space Back leaves"

    panel._show_page(mod.PAGE_DEVICE)

    assert (panel._inventory_btn.visible, panel._inventory_btn.enabled) == (True, True)
    assert panel._back_btn.visible is False
    assert len([child for child in panel._nav.children if child.visible]) == 2


def test_the_listing_is_left_by_back_for_the_page_it_was_opened_from() -> None:
    # It answers a question of its own and leads nowhere, so there is no page "before" it to
    # walk to: what Back means there is done looking.
    panel = _new_panel()
    panel.show_inventory()

    assert panel.can_go_back is True
    panel.previous_page()

    assert panel.page_index == mod.PAGE_DEVICE


def test_next_never_walks_into_the_listing() -> None:
    # It is the last page built and is on nobody's way anywhere. Walked at from the review
    # page, which is the page it sits after, and from the listing itself.
    panel = _new_panel()
    panel._on_device_selected(ASC2.key)
    panel._show_page(mod.PAGE_REVIEW)

    for _ in range(3):
        panel.next_page()
    assert panel.page_index == mod.PAGE_REVIEW

    panel.show_inventory()
    assert panel.has_next_page is False
    assert panel.can_advance is False
    panel.next_page()
    assert panel.page_index == mod.PAGE_INVENTORY


def test_the_pad_works_the_sort_keys_and_turns_no_page_with_them() -> None:
    # The only control the listing has, so it is the only thing a Deck could be pointing at
    # here -- and nothing is being chosen: right re-orders the rows and stays put.
    panel = _new_panel()
    panel.show_inventory()

    widget, commit = panel._pad_target()

    assert widget is panel._sort_group
    assert commit == panel._on_sort_selected
    assert panel.pad_mark_turns_page is False
