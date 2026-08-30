from __future__ import annotations

from typing import Any

import pytest

import src.pytrain.gui.components.checkbox_group as mod


class DummyPhotoImage:
    """``tk.PhotoImage`` as far as the indicator drawing uses it.

    No test in this project opens a real ``tkinter.Tk``, and this must not be the first: the
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
        """The colour the whole image was filled with before anything was drawn on it."""
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


def _group(rows: list[DummyRow], **kwargs: Any) -> mod.CheckBoxGroup:
    """A group with the cursor armed over ``rows`` and nothing else built.

    ``__new__`` rather than a constructor call: the parent is guizero's ``ButtonGroup``, which
    would want a real Tk master. Everything the cursor is made of is these rows and the numbers
    it paints them with, which is why arming it is a method of its own.
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
    # "" is Tk's documented "no special colour", and the fallback where a platform refuses a
    # colour in selectcolor. Refusing is what a TclError from config means.
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


def test_setting_the_cursor_on_a_group_that_did_not_opt_in_does_nothing() -> None:
    group = mod.CheckBoxGroup.__new__(mod.CheckBoxGroup)

    group.cursor = 3

    assert group.cursor is None


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
