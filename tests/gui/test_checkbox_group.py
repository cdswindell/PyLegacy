from __future__ import annotations

from typing import Any

import pytest

import src.pytrain.gui.components.checkbox_group as mod


class DummyPhotoImage:
    """tk.PhotoImage as far as the indicator drawing uses it.

    No test in this project opens a real tkinter.Tk, and this must not be the first: the
    drawing helpers only ask an image its size and put pixels into it, so a double that records
    what it was filled with says everything worth asserting about them.
    """

    def __init__(self, width: int, height: int) -> None:
        self._size = (width, height)
        self.fills: list[tuple[str, Any]] = []

    def width(self) -> int:
        return self._size[0]

    def height(self) -> int:
        return self._size[1]

    def put(self, color: str, to: Any = None) -> None:
        self.fills.append((color, to))

    @property
    def ground(self) -> str:
        """The color the whole image was filled with before anything was drawn on it."""
        return self.fills[0][0]


class DummyRow:
    """One radio row, recording what it was asked to be configured with."""

    def __init__(self, value: str, background: str = "systemWindowBackgroundColor") -> None:
        self.value = value
        self.config_calls: list[dict[str, Any]] = []
        self._options: dict[str, Any] = {"background": background}

    def config(self, **kwargs: Any) -> None:
        self.config_calls.append(dict(kwargs))
        self._options.update(kwargs)

    def cget(self, option: str) -> Any:
        return self._options[option]

    @property
    def last(self) -> dict[str, Any]:
        return self.config_calls[-1]


@pytest.fixture(autouse=True)
def _no_display(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod.tk, "PhotoImage", DummyPhotoImage, raising=True)


def _rows(count: int = 3) -> list[DummyRow]:
    return [DummyRow(str(index)) for index in range(count)]


# noinspection PyProtectedMember
def _group(rows: list[DummyRow], **kwargs: Any) -> mod.CheckBoxGroup:
    """A group with the cursor armed over rows and nothing else built.

    __new__ rather than a constructor call: the parent is guizero's ButtonGroup, which would
    want a real Tk master. Everything the cursor is made of is these rows and the numbers it
    paints them with, which is why arming it is a method of its own.
    """
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)
    group._init_cursor([(row.value, row) for row in rows], 28, style="radio", **kwargs)
    return group


def test_arming_the_cursor_neutralises_the_select_colour_on_every_row() -> None:
    # The whole reason A-8 was needed. These rows are drawn with indicatoron=False, and Tk then
    # paints selectColor -- default #b03060 -- across the entire selected row. Nothing ever set
    # it, so a stepped row gained a filled maroon bar that read as "this is set". With the
    # cursor now owning the filled bar there must be exactly one, so Tk's is taken away.
    rows = _rows()

    _group(rows)

    for row in rows:
        assert row.config_calls == [{"selectcolor": "systemWindowBackgroundColor"}]
        assert row.cget("background") == "systemWindowBackgroundColor", "and the row is not tinted yet"


def test_arming_the_cursor_falls_back_to_tk_s_no_colour_form() -> None:
    # "" is Tk's documented "no special color", and the fallback where a platform refuses a
    # color in selectcolor. Refusing is what a TclError from config means.
    class AwkwardRow(DummyRow):
        def config(self, **kwargs: Any) -> None:
            if kwargs.get("selectcolor") == "systemWindowBackgroundColor":
                raise mod.tk.TclError("unknown color name")
            super().config(**kwargs)

    row = AwkwardRow("0")

    _group([row])

    assert row.config_calls == [{"selectcolor": ""}]


def test_the_cursor_tints_the_row_it_is_moved_to() -> None:
    rows = _rows()
    group = _group(rows)

    group.cursor = 1

    assert group.cursor == "1", "held as the string the rows are keyed by"
    assert rows[1].last["background"] == mod.CURSOR_BG
    assert rows[1].last["activebackground"] == mod.CURSOR_BG
    assert rows[1].last["selectcolor"] == mod.CURSOR_BG, "so the tint is the whole row, selected or not"
    assert len(rows[0].config_calls) == 1, "and the rows it is not on were left alone"
    assert len(rows[2].config_calls) == 1


def test_the_tinted_row_carries_indicator_images_painted_on_the_tint() -> None:
    # The single most likely way this ships looking wrong. The indicator pair is *filled* with
    # a background rather than drawn over a transparent ground, so a tinted row carrying the
    # white-backed pair shows a white patch around the ring.
    rows = _rows()
    group = _group(rows)

    group.cursor = 0
    tinted = rows[0].last["image"]

    group.cursor = 1
    untinted = rows[0].last["image"]

    assert tinted.ground == mod.CURSOR_BG
    assert untinted.ground == mod.WHITE
    assert tinted is not untinted, "two backgrounds on one widget are two images"


def test_moving_the_cursor_reconfigures_the_row_it_leaves_and_the_row_it_lands_on() -> None:
    # Two rows, not a pass over ten: the cursor moves on every D-pad press, and this list is
    # serviced from the same poll as the touch screen.
    rows = _rows(10)
    group = _group(rows)
    group.cursor = 4
    for row in rows:
        row.config_calls.clear()

    group.cursor = 5

    assert [index for index, row in enumerate(rows) if row.config_calls] == [4, 5]
    assert rows[4].last["background"] == "systemWindowBackgroundColor", "back to the row's own"
    assert rows[5].last["background"] == mod.CURSOR_BG


def test_the_cursor_can_be_cleared() -> None:
    rows = _rows()
    group = _group(rows)
    group.cursor = 2

    group.cursor = None

    assert group.cursor is None
    assert rows[2].last["background"] == "systemWindowBackgroundColor"
    assert rows[2].last["selectcolor"] == "systemWindowBackgroundColor"


@pytest.mark.parametrize("value", ["", "None", "Sound Horn", "12", -1])
def test_a_value_the_list_does_not_hold_clears_the_cursor_rather_than_raising(value: Any) -> None:
    # The reading the selection already gets: guizero answers with whatever string it was
    # handed, "None" among them, so a cursor set from one of those is no position at all.
    rows = _rows()
    group = _group(rows)
    group.cursor = 1

    group.cursor = value

    assert group.cursor is None
    assert rows[1].last["background"] == "systemWindowBackgroundColor"


def test_setting_the_cursor_where_it_already_is_configures_nothing() -> None:
    rows = _rows()
    group = _group(rows)
    group.cursor = 1
    rows[1].config_calls.clear()

    group.cursor = 1

    assert rows[1].config_calls == []


def test_a_group_without_the_cursor_is_configured_exactly_as_it_is_today() -> None:
    # The Admin panel, the catalog's sort radios and the AMC2 page selector share this
    # component. Both the cursor and the selectcolor change are opt-in, so none of them moves.
    row = DummyRow("0")

    mod.CheckBoxGroup.decorate_checkbox(row, 20, 10, style="radio")

    assert [set(call) for call in row.config_calls] == [
        {"font", "padx", "pady", "anchor", "width"},
        {"image", "selectimage", "compound", "indicatoron"},
    ]
    assert row.last["indicatoron"] is False
    assert row.last["image"].ground == mod.WHITE


class DummyRebuiltRow:
    """One row as _rbuttons holds it: a value, and the widget the cursor is armed over.

    The pair a re-arm reads. Everywhere else the cursor is armed over widgets directly, which
    is all the tinting needs; a rebuild is the one thing that has to look at _rbuttons,
    because the widgets it re-arms over are the ones guizero has just created.
    """

    def __init__(self, value: str) -> None:
        self.value = value
        self.tk = DummyRow(value)


# noinspection PyProtectedMember
def _rebuildable_group(values: list[str]) -> tuple[mod.CheckBoxGroup, list[DummyRebuiltRow]]:
    """A group with the cursor armed over rows it holds the way guizero holds them."""
    rows = [DummyRebuiltRow(value) for value in values]
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)
    group._rbuttons = rows
    group._init_cursor([(row.value, row.tk) for row in rows], 28, style="radio")
    return group, rows


def test_a_rebuilt_group_is_armed_over_the_rows_it_now_holds() -> None:
    # The cursor is armed over the row *widgets*, and guizero destroys every one of them on
    # any options change: the LCS panel's mode rows are replaced whenever the module or the
    # address changes, and without the re-arm the next press would tint a dead widget, which
    # is a TclError rather than a highlight in the wrong place.
    group, gone = _rebuildable_group(["0", "1", "2"])
    group.cursor = "1"
    rebuilt = [DummyRebuiltRow(value) for value in ("0", "1", "2")]
    group._rbuttons = rebuilt
    for row in gone:
        row.tk.config_calls.clear()

    group._rearm_cursor()

    assert group.cursor == "1", "the same row, on the list that now holds it"
    assert rebuilt[1].tk.last["background"] == mod.CURSOR_BG
    group.cursor = "2"
    assert rebuilt[2].tk.last["background"] == mod.CURSOR_BG
    assert [row.tk.config_calls for row in gone] == [[], [], []], "and the replaced rows are never touched again"


def test_a_rebuild_that_replaces_the_list_drops_the_tint() -> None:
    # Which is what choosing another module does to the mode rows: one module's modes go and
    # another's arrive, and where the pad was pointing is no longer a place. clear() empties
    # the list outright, so the pair of calls a replacement is made of drops it either way.
    group, _gone = _rebuildable_group(["acc_8", "acc_1"])
    group.cursor = "acc_1"

    group._rbuttons = [DummyRebuiltRow(value) for value in ("sw_8", "sw_1")]
    group._rearm_cursor()

    assert group.cursor is None


def test_a_group_that_never_armed_a_cursor_is_untouched_by_a_rebuild() -> None:
    # Every other group in the app: the Admin panel's, the catalog's sort radios, the AMC2
    # page selector. A rebuild must not arm one on a group that asked for none -- and this
    # is reachable before __init__ has armed anything at all, guizero building its rows from
    # its own constructor.
    rows = [DummyRebuiltRow("0")]
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)
    group._rbuttons = rows

    group._rearm_cursor()

    assert group.cursor is None
    assert rows[0].tk.config_calls == [], "not even the selectcolor arming touches it"


def test_replacing_the_options_arms_the_cursor_again(monkeypatch: pytest.MonkeyPatch) -> None:
    # The wiring, as the repaint above it is wired: every options change routes through
    # _refresh_options, which is the moment the old widgets are gone and the new ones exist.
    group, gone = _rebuildable_group(["0", "1"])
    group.cursor = "1"
    rebuilt = [DummyRebuiltRow(value) for value in ("0", "1")]
    group._rbuttons = rebuilt
    monkeypatch.setattr(mod.ButtonGroup, "_refresh_options", lambda self: None, raising=True)

    group._refresh_options()

    for row in gone:
        row.tk.config_calls.clear()
    group.cursor = "0"
    assert rebuilt[0].tk.last["background"] == mod.CURSOR_BG
    assert rebuilt[1].tk.last["background"] == "systemWindowBackgroundColor", "the row it left"
    assert [row.tk.config_calls for row in gone] == [[], []]


def test_row_values_answers_with_the_string_every_row_holds() -> None:
    # What a caller stepping the cursor reads the list off: options answers with whatever it
    # was handed -- a mode key, an index, a tuple or a list -- while cursor and value are both
    # written and read as the string Tk holds.
    group, _rows = _rebuildable_group(["0", "1", "2"])

    assert group.row_values == ("0", "1", "2")
    assert mod.CheckBoxGroup.__new__(mod.CheckBoxGroup).row_values == (), "and a group with no rows yet is safe"


class DummyGroupTk:
    """The group's own Tk frame, as decorate_rows uses it: a bag of rows."""

    def __init__(self, rows: list[DummyRow]) -> None:
        self._rows = rows

    def winfo_children(self) -> list[DummyRow]:
        return list(self._rows)


def _painting_group(rows: list[DummyRow], size: int = 18, pady: int = 12) -> mod.CheckBoxGroup:
    """A group that has recorded how to paint its rows, and nothing else.

    __new__ for the reason _group uses it: the parent class would want a real Tk master, and
    everything the painting is made of is these rows and those numbers. The frame is assigned
    behind guizero's read-only tk property, which is where it keeps it.
    """
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)
    group._tk = DummyGroupTk(rows)
    group._padx, group._pady, group._dis_width = 18, pady, None
    group._row_size, group._row_style, group._row_thickness = size, "radio", 2
    return group


def test_replacing_the_options_repaints_every_row(monkeypatch: pytest.MonkeyPatch) -> None:
    # The LCS panel's mode radios, which are rebuilt every time the module changes. guizero
    # *destroys* a group's rows on any options change -- clear, append, insert, remove -- and
    # the plain Tk radiobuttons it puts in their place have the default font and the native
    # indicator, which on the Pi was a dot barely visible beside the module radios that are
    # built once. So the paint has to follow the rebuild rather than the construction.
    rows = _rows(2)
    group = _painting_group(rows)
    rebuilt: list[Any] = []
    monkeypatch.setattr(mod.ButtonGroup, "_refresh_options", lambda self: rebuilt.append(self), raising=True)

    group._refresh_options()

    assert rebuilt == [group], "the rows are still guizero's to rebuild"
    for row in rows:
        assert row.config_calls[0]["font"] == ("TkDefaultFont", 18)
        assert row.config_calls[0]["pady"] == 12
        assert row.last["indicatoron"] is False, "the painted indicator, not Tk's own"
        assert row.last["image"].width() == mod.CheckBoxGroup.indicator_size_for(18, "radio")


def test_a_group_that_recorded_nothing_leaves_its_rows_alone() -> None:
    # _refresh_options is reachable before this class has said what to paint with: guizero
    # calls it from its own __init__, and the cursor tests build a group by __new__.
    rows = _rows()
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)
    group._tk = DummyGroupTk(rows)

    group.decorate_rows()

    assert [row.config_calls for row in rows] == [[], [], []]


class DummyRadioTk:
    """One row's Tk widget, as stretch_rows uses it: something that can be re-gridded."""

    def __init__(self) -> None:
        self.grid_options: dict[str, Any] = {}

    def grid_configure(self, **kwargs: Any) -> None:
        self.grid_options.update(kwargs)


class DummyRadio:
    """One row as _rbuttons holds it: a guizero widget that knows its grid cell.

    value is what guizero answers with -- a string, whatever it was handed -- and what the
    leads are keyed by; visible is what tells a row the grid has forgotten from one it is
    still managing.
    """

    def __init__(self, grid: list[int], value: str = "", visible: bool = True) -> None:
        self.grid = grid
        self.value = value
        self.visible = visible
        self.tk = DummyRadioTk()


class DummyFrameTk(DummyGroupTk):
    """The group's frame, recording the column weights a real Tk frame would be given."""

    def __init__(self, rows: list[DummyRow] | None = None) -> None:
        super().__init__(rows or [])
        self.columns: dict[int, dict[str, Any]] = {}

    def grid_columnconfigure(self, column: int, **kwargs: Any) -> None:
        self.columns.setdefault(column, {}).update(kwargs)


def _stretching_group(rows: list[DummyRadio], stretch: bool = True) -> mod.CheckBoxGroup:
    """A group that has been told whether to stretch its rows, and nothing else.

    __new__ as above: the stretch is made of these rows' grid cells and the frame's
    column weights, so a real Tk master would add nothing to assert.
    """
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)
    group._tk = DummyFrameTk()
    group._rbuttons = rows
    group._stretch = stretch
    return group


def _column(rows: int = 3) -> list[DummyRadio]:
    """A vertical group's rows: guizero stacks them down column 0, from row 1."""
    return [DummyRadio([0, index + 1]) for index in range(rows)]


@pytest.mark.parametrize("stretch, expected", [(True, "fill"), (False, None)])
def test_only_a_stretch_group_asks_guizero_to_fill_its_container(
    monkeypatch: pytest.MonkeyPatch, stretch: bool, expected: str | None
) -> None:
    # The rows can only be as wide as the frame around them, and guizero packs a container
    # with fill=X on one condition: that the container's own width is the string "fill".
    seen: dict[str, Any] = {}

    def _init(self, _master: Any, **kwargs: Any) -> None:
        seen.update(kwargs)
        self._tk = DummyFrameTk()
        self._rbuttons = []

    monkeypatch.setattr(mod.ButtonGroup, "__init__", _init, raising=True)

    mod.CheckBoxGroup(None, size=18, style="radio", stretch=stretch)

    assert seen.get("width") == expected


def test_a_stretch_group_hands_every_row_the_width_of_its_column() -> None:
    # guizero grids a row from its align="left", i.e. sticky="W", so each row is only as
    # wide as its own label -- which is invisible until the rows are painted, and then reads
    # as fields of different lengths, the shortest mode ending well short of its box.
    rows = _column()
    group = _stretching_group(rows)

    group.stretch_rows()

    assert group.tk.columns == {0: {"weight": 1}}, "the spare width goes to the rows' column"
    assert [row.tk.grid_options for row in rows] == [{"sticky": "ew"}] * len(rows)


def test_a_horizontal_stretch_group_weights_the_columns_its_rows_are_actually_in() -> None:
    # guizero lays a horizontal group along one row from column 1, so column 0 holds nothing
    # of its and weighting that would stretch the rows into nowhere.
    rows = [DummyRadio([index + 1, 0]) for index in range(2)]
    group = _stretching_group(rows)

    group.stretch_rows()

    assert group.tk.columns == {1: {"weight": 1}, 2: {"weight": 1}}


def test_a_group_that_did_not_ask_to_be_stretched_is_left_as_guizero_gridded_it() -> None:
    # Opt-in: the Admin panel, the catalog's sort radios and the AMC2 page selector share
    # this component, and none of them asked for its rows to change width.
    rows = _column(1)
    group = _stretching_group(rows, stretch=False)

    group.stretch_rows()

    assert group.tk.columns == {}
    assert rows[0].tk.grid_options == {}


def test_rebuilding_the_options_stretches_every_row_again(monkeypatch: pytest.MonkeyPatch) -> None:
    # The regression, and the reason the stretch cannot be set once at construction: the LCS
    # panel's mode radios are rebuilt whenever the module changes, and a rebuilt row is
    # gridded from scratch -- sticky="W" again, back to the width of its own label, inside a
    # box that has not moved.
    rows = _column(2)
    group = _stretching_group(rows)
    monkeypatch.setattr(mod.ButtonGroup, "_refresh_options", lambda self: None, raising=True)

    group._refresh_options()

    assert group.tk.columns == {0: {"weight": 1}}
    assert [row.tk.grid_options for row in rows] == [{"sticky": "ew"}] * 2


def test_resizing_stretches_every_row_again(monkeypatch: pytest.MonkeyPatch) -> None:
    # And the reason the rebuild alone is not enough: ButtonGroup.append resizes the group
    # *after* rebuilding it, handing the group's own "fill" width to every row, and guizero
    # re-displays a container whenever a child's width is set to fill. That re-grid is the
    # last word, so the stretch has to come after it.
    rows = _column(1)
    group = _stretching_group(rows)
    resized: list[tuple[Any, Any]] = []
    monkeypatch.setattr(mod.ButtonGroup, "resize", lambda self, width, height: resized.append((width, height)))

    group.resize("fill", None)

    assert resized == [("fill", None)], "the resize is still guizero's"
    assert rows[0].tk.grid_options == {"sticky": "ew"}


def test_a_row_that_refuses_the_stretch_does_not_cost_the_others_theirs() -> None:
    # A row Tk has forgotten, which is what a TclError from grid_configure means.
    rows = _column(2)

    def _raise(**_kwargs: Any) -> None:
        raise mod.tk.TclError("bad window path name")

    rows[0].tk.grid_configure = _raise
    group = _stretching_group(rows)

    group.stretch_rows()  # must not raise

    assert rows[1].tk.grid_options == {"sticky": "ew"}


def _keyed(*values: str) -> list[DummyRadio]:
    """A vertical group's rows, each answering with the value it was built from."""
    return [DummyRadio([0, index + 1], value=value) for index, value in enumerate(values)]


def _leading_group(rows: list[DummyRadio], leads: dict[Any, int] = None) -> mod.CheckBoxGroup:
    """A group that has been told which of its rows begin a new block, and nothing else.

    __new__ as above: a lead is grid padding on the row itself, so a real Tk master would add
    nothing to assert.
    """
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)
    group._tk = DummyFrameTk()
    group._rbuttons = rows
    group._stretch = False
    group.row_leads = leads
    return group


def test_only_a_named_row_is_held_off_the_row_above_it() -> None:
    # Whitespace between blocks of rows rather than between every pair of them, which is what
    # pady already sets: the LCS panel's mode radios are two accessory modes and then two
    # switch modes, and an operator reading them needs to see two lists rather than one of
    # four. Above the row, so the gap falls between the blocks rather than inside either.
    rows = _keyed("acc_8", "acc_1", "sw_momentary", "sw_latching")
    group = _leading_group(rows, {"sw_momentary": 12})

    group.lead_rows()

    assert [row.tk.grid_options["pady"] for row in rows] == [(0, 0), (0, 0), (12, 0), (0, 0)]


def test_a_row_that_no_longer_begins_a_block_loses_its_gap() -> None:
    # The rows are replaced with a differently grouped list whenever the LCS module changes --
    # an STM2's modes are all on one key -- and a gap left standing above a row that begins
    # nothing is whitespace in the middle of a list.
    rows = _keyed("acc_8", "sw_momentary")
    group = _leading_group(rows, {"sw_momentary": 12})
    assert rows[1].tk.grid_options["pady"] == (12, 0), "asking for them applies them"

    group.row_leads = {}

    assert [row.tk.grid_options["pady"] for row in rows] == [(0, 0), (0, 0)]


def test_the_leads_are_held_as_pixels_keyed_by_the_value_a_row_answers_with() -> None:
    # guizero stores whatever it was handed and answers in kind, and a row carries no index
    # for the mapping to be keyed by.
    group = _leading_group(_keyed("1"), {1: "12"})

    assert group.row_leads == {"1": 12}


def test_the_gaps_can_be_asked_for_when_the_group_is_built(monkeypatch: pytest.MonkeyPatch) -> None:
    # The LCS panel hands them over at construction as well as on every refresh, since the
    # group is built before a module has been chosen.
    rows = _keyed("acc_8", "sw_momentary")

    def _init(self, _master: Any, **_kwargs: Any) -> None:
        self._tk = DummyFrameTk()
        self._rbuttons = rows

    monkeypatch.setattr(mod.ButtonGroup, "__init__", _init, raising=True)

    group = mod.CheckBoxGroup(None, size=18, style="radio", row_leads={"sw_momentary": 12})

    assert group.row_leads == {"sw_momentary": 12}
    assert rows[1].tk.grid_options["pady"] == (12, 0)


def test_rebuilding_the_options_leads_every_row_again(monkeypatch: pytest.MonkeyPatch) -> None:
    # The same reason the stretch cannot be set once: a rebuilt row is gridded from scratch,
    # and grid padding is not among the options guizero replays.
    rows = _keyed("acc_8", "sw_momentary")
    group = _leading_group(rows, {"sw_momentary": 12})
    rows[1].tk.grid_options.clear()
    monkeypatch.setattr(mod.ButtonGroup, "_refresh_options", lambda self: None, raising=True)

    group._refresh_options()

    assert rows[1].tk.grid_options["pady"] == (12, 0)


def test_resizing_leads_every_row_again(monkeypatch: pytest.MonkeyPatch) -> None:
    # And the reason the rebuild alone is not enough: ButtonGroup.append resizes the group
    # after rebuilding it, and that re-grid is the last word.
    rows = _keyed("sw_momentary")
    group = _leading_group(rows, {"sw_momentary": 12})
    rows[0].tk.grid_options.clear()
    monkeypatch.setattr(mod.ButtonGroup, "resize", lambda self, width, height: None, raising=True)

    group.resize("fill", None)

    assert rows[0].tk.grid_options["pady"] == (12, 0)


def test_a_hidden_row_is_left_where_the_grid_forgot_it() -> None:
    # Tk's grid configure *manages* a widget the grid has forgotten, so padding a hidden row
    # would put it back on screen -- which is exactly what padding a hidden footer button did
    # to the popup's Back key.
    rows = _keyed("acc_8", "sw_momentary")
    rows[1].visible = False

    _leading_group(rows, {"sw_momentary": 12})

    assert rows[1].tk.grid_options == {}
    assert rows[0].tk.grid_options == {"pady": (0, 0)}, "and the row still on screen is"


def test_a_group_that_named_no_rows_leaves_them_alone() -> None:
    # lead_rows is reachable before this class has recorded anything, exactly as decorate_rows
    # is: guizero calls _refresh_options from its own __init__, and the cursor tests build a
    # group by __new__.
    rows = _keyed("acc_8")
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)
    group._rbuttons = rows

    group.lead_rows()

    assert rows[0].tk.grid_options == {}


def test_a_row_that_refuses_its_gap_does_not_cost_the_others_theirs() -> None:
    # A row Tk has forgotten, which is what a TclError from grid_configure means.
    rows = _keyed("acc_8", "sw_momentary")

    def _raise(**_kwargs: Any) -> None:
        raise mod.tk.TclError("bad window path name")

    rows[0].tk.grid_configure = _raise

    _leading_group(rows, {"sw_momentary": 12})  # must not raise

    assert rows[1].tk.grid_options["pady"] == (12, 0)


def test_setting_the_cursor_on_a_group_that_did_not_opt_in_does_nothing() -> None:
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)

    group.cursor = 3

    assert group.cursor is None


# Every text size these rows are drawn at, on all three machines: the LCS panel's module
# radios at s_14 and its mode rows, option rows and lone checkbox at s_18, the keypad's
# Sensor Track group at s_19, the Admin panel's scope radios at s_20 -- each of them
# round(size * scale), and the scale is 0.9 on the Deck's compact pane, 1.0 on a desk and
# 1.5 on the Pi.
ROW_SIZES = [13, 14, 16, 17, 18, 19, 20, 21, 27, 28, 30]

# The largest indicator a row's text box holds, as a multiple of the row's text size,
# measured on macOS off screenshots of a row packed tight at every one of those sizes: at or
# under it the row's frame comes through untouched, above it the indicator paints over it.
# See INDICATOR_SCALE, which is the ratio the component actually draws with.
FRAME_CEILING = 1.33


@pytest.mark.parametrize("style", ["radio", "checkbox"])
@pytest.mark.parametrize("size", ROW_SIZES)
def test_the_painted_indicator_stays_off_the_rows_own_frame(size: int, style: str) -> None:
    # What the ring came down from 1.5x for. These rows are drawn with indicatoron=False, so
    # each carries a frame of its own, and macOS draws that frame 3px inside the row's edge --
    # while the indicator is *filled* with a ground rather than drawn over a transparent one,
    # so one as tall as the row's text box does not merely touch the frame, it paints it out.
    # At 18pt, the size the LCS panel's option rows are drawn at on a desk, 1.5x was 27px of a
    # 28px text box, and all ten Sensor Track actions came out with their frame broken open
    # around the ring, top and bottom. The Pi and the Deck never showed it: X11 draws no frame
    # on these rows at all, which is why the ratio has to be held to here rather than seen.
    assert mod.CheckBoxGroup.indicator_size_for(size, style) <= int(size * FRAME_CEILING)


@pytest.mark.parametrize("size", ROW_SIZES)
def test_a_ring_and_a_tick_box_are_drawn_at_one_size(size: int) -> None:
    # Both are as large as the row's text box allows, and that box is the font's: it says
    # nothing about which shape is painted in it.
    radio = mod.CheckBoxGroup.indicator_size_for(size, "radio")

    assert radio == mod.CheckBoxGroup.indicator_size_for(size, "checkbox")


@pytest.mark.parametrize("size", ROW_SIZES)
def test_the_painted_indicator_is_still_larger_than_the_text_beside_it(size: int) -> None:
    # The floor, and the reason these rows are painted at all rather than left to Tk: the
    # platform's own indicator is drawn at the font's own scale and read as a smudge beside
    # the label on the Pi. So the frame is cleared by drawing the indicator smaller, not by
    # drawing it small.
    assert mod.CheckBoxGroup.indicator_size_for(size, "radio") > size


@pytest.mark.parametrize("style", ["radio", "checkbox"])
def test_a_row_is_painted_with_a_square_indicator_of_that_size(style: str) -> None:
    # And the rules above are about what is drawn rather than about arithmetic: the pair a row
    # is configured with is that many pixels each way, which is what has to clear the frame.
    row = DummyRow("0")

    mod.CheckBoxGroup.decorate_checkbox(row, 18, None, style=style)

    size = mod.CheckBoxGroup.indicator_size_for(18, style)
    for image in (row.last["image"], row.last["selectimage"]):
        assert (image.width(), image.height()) == (size, size)


@pytest.mark.parametrize("style", ["radio", "checkbox"])
def test_the_indicator_cache_is_keyed_by_background(style: str) -> None:
    # Latent until A-8, because there was only ever one background: the key held the style and
    # the size and nothing else, so the second background asked for would have been handed the
    # first one's images.
    row = DummyRow("0")

    white = mod.CheckBoxGroup.indicator_images(row, 24, style=style, background=mod.WHITE)
    again = mod.CheckBoxGroup.indicator_images(row, 24, style=style, background=mod.WHITE)
    tinted = mod.CheckBoxGroup.indicator_images(row, 24, style=style, background=mod.CURSOR_BG)

    assert again is white, "cached, so a row is painted once rather than per press"
    assert tinted[0] is not white[0]
    assert tinted[1] is not white[1]
    assert tinted[0].ground == mod.CURSOR_BG
    assert white[0].ground == mod.WHITE
