from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import src.pytrain.gui.components.scroll_box as mod


class DummyTk:
    """One Tk widget, as the window reaches for one.

    No test in this project opens a real tkinter.Tk, and this must not be the first: a window
    onto a page is measurement and placement and nothing besides, so a double that answers
    what a screen would answer and records what it was told to do says everything there is to
    assert about it.
    """

    _made = 0

    def __init__(self) -> None:
        DummyTk._made += 1
        # Tk names a widget by its path and bind_scrolling remembers the ones it has tagged by
        # that name, so no two of these may read alike.
        self._name = f".w{DummyTk._made}"
        # What the screen would say, for a test to say what is on it.
        self.reqheight = 0
        self.height = 0
        self.rooty = 0
        self.exists = True
        self.propagated: list[bool] = []
        self.placed: dict[str, Any] = {}
        self.binds: list[tuple[str, Any, str | None]] = []
        self.class_binds: list[tuple[str, str, Any, str | None]] = []
        self.children: list[DummyTk] = []
        self.idle: list[Any] = []
        self.timers: list[tuple[int, Any]] = []
        self.bars: list[DummyBar] = []
        self.folds: list[DummyFold] = []
        # Which of the things drawn over the page was raised over the other, in order.
        self.lifted: list[Any] = []
        # Every place the content has been given, rather than only the one it is standing at:
        # the gutter comes and goes by re-placing the page, and a place that changed nothing
        # is a layout pass spent for nothing. See _widths.
        self.place_calls: list[dict[str, Any]] = []
        self.tags: tuple[str, ...] = (self._name,)

    def __str__(self) -> str:
        return self._name

    def pack_propagate(self, flag: bool) -> None:
        self.propagated.append(flag)

    def place(self, **kwargs: Any) -> None:
        self.place_calls.append(dict(kwargs))
        self.placed.update(kwargs)

    def place_configure(self, **kwargs: Any) -> None:
        self.place_calls.append(dict(kwargs))
        self.placed.update(kwargs)

    def bind(self, sequence: str, func: Any, add: str | None = None) -> None:
        self.binds.append((sequence, func, add))

    def bind_class(self, tag: str, sequence: str, func: Any, add: str | None = None) -> None:
        self.class_binds.append((tag, sequence, func, add))

    def bindtags(self, tags: Any = None) -> tuple[str, ...] | None:
        """Tk's own getter and setter in one name, which is how the component uses it."""
        if tags is None:
            return self.tags
        self.tags = tuple(tags)
        return None

    def after_idle(self, func: Any) -> str:
        """Queue the callback and hand back an id, as Tk does. The test runs it itself."""
        self.idle.append(func)
        return f"after#{len(self.idle)}"

    def after(self, msec: int, func: Any) -> str:
        """The same, for a callback with a delay on it: the test decides when it is due."""
        self.timers.append((msec, func))
        return f"after#{len(self.timers)}"

    def winfo_children(self) -> list[DummyTk]:
        return list(self.children)

    def winfo_exists(self) -> bool:
        """Whether this widget is still on screen; a test takes a popup down by clearing it."""
        return self.exists

    def winfo_reqheight(self) -> int:
        return self.reqheight

    def winfo_height(self) -> int:
        return self.height

    def winfo_rooty(self) -> int:
        return self.rooty


class DummyBox:
    """guizero's Box as the window builds one: a Tk widget, and a height it can be told.

    height is a plain attribute for the reason it is one in guizero -- fitting the window is
    setting it -- and visible records what the content was created as, which is the whole
    trick that lets a placed child sit in a packed container.
    """

    def __init__(
        self,
        master: Any = None,
        align: str = "top",
        width: Any = None,
        height: Any = None,
        visible: bool = True,
    ) -> None:
        self.master = master
        self.align = align
        self.width = width
        self.height = height
        self.visible = visible
        self.tk = DummyTk()
        if isinstance(getattr(master, "tk", None), DummyTk):
            master.tk.children.append(self.tk)


class DummyBar:
    """The bar down the right edge, as _draw_bar makes one: a raw Tk Scrollbar.

    Tk's own widget rather than a painted block, so what it is told is a pair of fractions and
    what it does with them -- where to draw the handle, which arrow head the finger is on -- is
    Tk's business and not this suite's. What a test can ask is what it was built with, what it
    was told, and where it was put.

    Recorded on the window it is drawn over rather than handed back, so a test reads the bar
    off the box it is asking about. A bar taken down is kept and merely unplaced, which is
    what the component does with it, so placed rather than the object itself is what says
    whether anything is on screen.
    """

    def __init__(self, master: DummyTk, **kwargs: Any) -> None:
        self.master = master
        self.kwargs = dict(kwargs)
        self.placed: dict[str, Any] | None = None
        self.shown: tuple[float, float] | None = None
        self.lifts = 0
        master.bars.append(self)

    def set(self, first: float, last: float) -> None:
        self.shown = (float(first), float(last))

    def place(self, **kwargs: Any) -> None:
        self.placed = dict(kwargs)

    def place_forget(self) -> None:
        self.placed = None

    def lift(self) -> None:
        self.lifts += 1
        self.master.lifted.append(self)


class DummyFold:
    """The line across the foot of the window, as _draw_fold makes one: a raw Tk Frame.

    A gray hairline and nothing besides, so what there is to ask of it is what it was built
    with and where it was put -- and, the bar being drawn over the same page, which of the two
    of them was raised over the other.

    Recorded on the window and merely unplaced when it goes, exactly as the bar is, so placed
    rather than the object itself is what says whether anything is on screen.
    """

    def __init__(self, master: DummyTk, **kwargs: Any) -> None:
        self.master = master
        self.kwargs = dict(kwargs)
        self.placed: dict[str, Any] | None = None
        self.lifts = 0
        master.folds.append(self)

    def place(self, **kwargs: Any) -> None:
        self.placed = dict(kwargs)

    def place_forget(self) -> None:
        self.placed = None

    def lift(self) -> None:
        self.lifts += 1
        self.master.lifted.append(self)


@pytest.fixture(autouse=True)
def _no_display(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every widget the window makes, made without a screen to make it on."""
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    # The bar and the line at the foot are raw Tk widgets rather than guizero ones -- both are
    # drawn over the page rather than packed beside it -- so tkinter's own name in the module
    # is what stands in.
    monkeypatch.setattr(mod, "tk", SimpleNamespace(Scrollbar=DummyBar, Frame=DummyFold), raising=True)


def _window(content_px: int = 0, width: int = 400, bar_px: int = None) -> mod.ScrollBox:
    """A window onto a page content_px tall.

    The height is the content's own answer to winfo_reqheight, which is where the real one
    reads it: a test grows or shrinks the page by saying that again.
    """
    box = mod.ScrollBox(DummyBox(), width=width, bar_px=bar_px)
    box.content.tk.reqheight = content_px
    return box


def _fitted(content_px: int, budget: int, width: int = 400, bar_px: int = None) -> mod.ScrollBox:
    """That window, given the room a screen has for it."""
    box = _window(content_px, width, bar_px)
    box.fit(budget)
    return box


def _child(parent: DummyTk) -> DummyTk:
    """One more widget inside parent, as building a row into the page makes one."""
    widget = DummyTk()
    parent.children.append(widget)
    return widget


def _row_at(box: mod.ScrollBox, top: int, height: int = 40) -> DummyTk:
    """A row standing top pixels down the page.

    Placed in screen coordinates rather than page ones, because that is the only measurement
    there is: a row's place on the page is the distance between its own root y and the
    content's, and the two move together whenever the content is scrolled.
    """
    row = _child(box.content.tk)
    row.rooty = box.content.tk.rooty + top
    row.height = height
    return row


def _tag(box: mod.ScrollBox) -> str:
    """The tag the window's gestures are bound to, read off the binding itself.

    The widgets in the content carry the same one, and that is the whole of how a press
    landing on a row reaches the window behind it -- so a test reads it where it was bound
    rather than being told what it is.
    """
    tags = {tag for tag, _sequence, _handler, _add in box.viewport.tk.class_binds}
    assert len(tags) == 1, "one tag, however many gestures are bound to it"
    return tags.pop()


def _gesture(box: mod.ScrollBox, sequence: str) -> Any:
    """The handler bound for sequence, to be called as Tk would call it."""
    handlers = [handler for _tag_name, bound, handler, _add in box.viewport.tk.class_binds if bound == sequence]
    assert handlers, f"nothing is bound to {sequence}"
    return handlers[0]


def _bar(box: mod.ScrollBox) -> DummyBar | None:
    """The bar the window has made, or None where it has made none."""
    bars = box.viewport.tk.bars
    return bars[-1] if bars else None


def _fold(box: mod.ScrollBox) -> DummyFold | None:
    """The line the window has drawn across its foot, or None where it has drawn none."""
    folds = box.viewport.tk.folds
    return folds[-1] if folds else None


def _widths(box: mod.ScrollBox) -> list[Any]:
    """Every width the page has been placed at, in the order it was placed at them."""
    return [call["width"] for call in box.content.tk.place_calls if "width" in call]


def test_a_window_with_room_for_its_whole_page_hides_nothing() -> None:
    # The rule that says nothing has changed. On every screen with the room for the page --
    # a desk, and most pages on the Deck -- the panel has to look exactly as it did before
    # there was a window at all: the height of its own content, no bar down its edge, and
    # nothing held back.
    box = _fitted(content_px=300, budget=400)

    assert box.view_px == 300
    assert box.viewport.height == 300, "the window takes the page's height, not the budget's"
    assert box.hidden_px == 0
    assert box.scrollable is False
    assert box.viewport.tk.bars == [], "and no bar was ever drawn to say otherwise"


def test_a_window_given_less_room_than_its_page_holds_the_rest_back() -> None:
    # The defect this component exists for: Tk's pack allots space in creation order, so a
    # page too tall for its pane costs whatever was packed last -- the Back, Next and Close
    # keys along the bottom. The window keeps the room it was given and the surplus goes
    # behind it instead of off the screen.
    box = _fitted(content_px=900, budget=400)

    assert box.view_px == 400
    assert box.viewport.height == 400
    assert box.hidden_px == 500
    assert box.scrollable is True


def test_a_page_that_has_not_been_measured_is_left_at_its_own_height() -> None:
    # An overlay is laid out for the first time when it is put on screen, and until then every
    # measurement of it reads 1. Nothing may be sized off a measurement Tk has not made: an
    # unmeasured screen draws what it always drew rather than a window of some arbitrary
    # height, and the fit that follows the first <Configure> is the one that counts.
    asked_for_nothing = _window(content_px=300)

    assert asked_for_nothing.fit(None) == 300
    assert asked_for_nothing.hidden_px == 0

    unmeasured = _window(content_px=0)

    assert unmeasured.fit(400) == 0
    assert unmeasured.viewport.height == 1, "the height it was built with, untouched"


def test_the_content_is_placed_across_the_windows_real_width_and_moved_to_scroll() -> None:
    # The whole mechanism, and worth stating plainly. The content is created hidden so guizero
    # never packs it and then placed, which is what lets it sit in a packed container at a
    # position of its own; it is placed to the window's real width rather than the width asked
    # for, since a window packed into a body is as wide as that body less its border, and a
    # frame held to the wider figure hangs the end of every row off the right edge.
    box = _window(content_px=900)

    assert box.content.visible is False, "guizero packs nothing it believes is hidden"
    assert box.content.tk.placed["x"] == 0
    assert box.content.tk.placed["relwidth"] == 1.0
    assert box.viewport.tk.propagated == [False], "and the window keeps the height it is told"

    # And to the whole of that width until something is held back in it: the gutter the bar
    # stands in is kept only while there is a bar to keep it for; see below.
    assert box.content.tk.placed["width"] == 0

    box.fit(400)
    box.scroll_to(120)

    assert box.content.tk.placed["y"] == -120, "scrolling is the content moving behind the window"


def test_scrolling_stops_at_the_top_and_at_the_end_of_what_is_hidden() -> None:
    # A wheel notch and a drag both ask for wherever they land, and neither knows where the
    # page ends. Past either end there is white space and no way back to the rows, so what is
    # asked for is taken as far as it goes -- and answering whether anything actually moved is
    # what lets a caller tell a scroll from a press that did nothing.
    box = _fitted(content_px=900, budget=400)

    assert box.scroll_to(-50) is False, "already at the top"
    assert box.offset == 0
    assert box.scroll_to(120) is True
    assert box.offset == 120
    assert box.scroll_to(9999) is True
    assert box.offset == 500, "the last of what is hidden, and no further"
    assert box.scroll_to(700) is False, "and there it stays"
    assert box.offset == 500


def test_a_page_that_shrinks_under_a_scroll_pulls_the_window_back_down() -> None:
    # A titled box hidden as the module changes takes its height with it, and a window left
    # where it was is a window looking at the white space the page used to have below it. The
    # fit that follows the change is the moment to notice, and it notices by asking for the
    # offset it already has.
    box = _fitted(content_px=900, budget=400)
    box.scroll_to(500)

    box.content.tk.reqheight = 500
    box.fit(400)

    assert box.offset == 100, "as far down as there is now page to show"
    assert box.content.tk.placed["y"] == -100


def test_a_page_turn_starts_at_the_top() -> None:
    # Four pages drawn in one window: a reader turning to a page has read none of it, and
    # arriving halfway down it reads as a page missing its heading.
    box = _fitted(content_px=900, budget=400)
    box.scroll_to(300)

    assert box.reset() is True
    assert box.offset == 0
    assert box.content.tk.placed["y"] == 0
    assert box.reset() is False, "and turning to a page already at its top moves nothing"


def test_a_row_below_the_fold_is_brought_just_into_view() -> None:
    # The least movement rather than centering the row: what the operator is reading stays
    # where they left it, so a list stepped a row at a time walks to its end instead of
    # jumping every time the row it is on nears an edge.
    box = _fitted(content_px=900, budget=400)
    row = _row_at(box, top=600, height=40)

    assert box.show_widget(row) is True
    assert box.offset == 240, "the row's foot at the window's, and not a pixel more"


def test_a_row_above_the_window_is_scrolled_back_up_to() -> None:
    # The pad steps in both directions, and a row walked off the top of the window is as far
    # out of sight as one below the bottom of it.
    box = _fitted(content_px=900, budget=400)
    box.scroll_to(300)
    row = _row_at(box, top=100, height=40)

    assert box.show_widget(row) is True
    assert box.offset == 100, "the row's head at the window's"


def test_a_row_already_in_view_moves_nothing() -> None:
    # Most presses land on a row that is already showing, and a page that shifted under every
    # one of them would be unreadable.
    box = _fitted(content_px=900, budget=400)
    box.scroll_to(100)
    row = _row_at(box, top=150, height=40)

    assert box.show_widget(row) is False
    assert box.offset == 100


def test_a_page_that_fits_moves_for_nothing() -> None:
    # Where the whole page is showing there is no such thing as out of sight, and a window
    # that scrolled anyway would move rows that had no reason to move.
    box = _fitted(content_px=300, budget=400)
    row = _row_at(box, top=200, height=40)

    assert box.show_widget(row) is False
    assert box.offset == 0


def test_a_row_is_taken_as_the_widget_or_as_the_tk_inside_it() -> None:
    # A row of a CheckBoxGroup is held as the Tk widget it is painted through, while everything
    # else in the panel is a guizero widget. A caller with one of them in hand should not have
    # to know which of the two this wanted.
    box = _fitted(content_px=900, budget=400)

    assert box.show_widget(_row_at(box, top=600, height=40)) is True
    bare = box.offset

    box.reset()

    assert box.show_widget(SimpleNamespace(tk=_row_at(box, top=600, height=40))) is True
    assert box.offset == bare


@pytest.mark.parametrize(
    "sequence, event, notches",
    [
        # macOS reports single notches and Windows multiples of 120; either way the sign is
        # what says which way the wheel turned.
        ("<MouseWheel>", SimpleNamespace(delta=1), -1),
        ("<MouseWheel>", SimpleNamespace(delta=120), -1),
        ("<MouseWheel>", SimpleNamespace(delta=-1), 1),
        ("<MouseWheel>", SimpleNamespace(delta=-120), 1),
        # X11 reports a wheel as a pair of buttons, which is what the Pi's desktop sends.
        ("<Button-4>", SimpleNamespace(), -1),
        ("<Button-5>", SimpleNamespace(), 1),
    ],
)
def test_one_notch_of_the_wheel_moves_the_page_one_step_that_way(sequence: str, event: Any, notches: int) -> None:
    # The one input on a desk that scrolls without taking a button press away from something
    # under it -- and the step is a couple of rows of the panel's own text, so a notch reads
    # as a nudge rather than as a page turn.
    box = _fitted(content_px=900, budget=400)
    box.scroll_to(200)

    _gesture(box, sequence)(event)

    assert box.offset == 200 + notches * mod.WHEEL_STEP


def test_a_press_that_barely_moves_is_left_to_whatever_is_under_it() -> None:
    # A fingertip wobbles on the Pi's panel, and every press inside a scrolling page lands on
    # something -- a radio row, a stepper key. Under the slop the press is left alone, so
    # tapping a control inside a page that happens to scroll still chooses it.
    box = _fitted(content_px=900, budget=400)
    box.scroll_to(100)

    _gesture(box, "<Button-1>")(SimpleNamespace(y_root=500))
    _gesture(box, "<B1-Motion>")(SimpleNamespace(y_root=500 - (mod.DRAG_SLOP - 1)))

    assert box.offset == 100


def test_a_drag_past_the_slop_carries_the_page_with_the_finger() -> None:
    # And over it the page follows by exactly the travel, measured from where the finger went
    # down: a drag that moved by the difference between reports would drop the slop's worth of
    # travel on the floor, and the page would lag the finger by it for the rest of the gesture.
    box = _fitted(content_px=900, budget=400)
    box.scroll_to(100)
    press, drag, release = (_gesture(box, sequence) for sequence in ("<Button-1>", "<B1-Motion>", "<ButtonRelease-1>"))

    press(SimpleNamespace(y_root=500))
    drag(SimpleNamespace(y_root=460))

    assert box.offset == 140

    drag(SimpleNamespace(y_root=440))

    assert box.offset == 160, "still measured from the press"

    release(SimpleNamespace(y_root=440))
    press(SimpleNamespace(y_root=300))
    drag(SimpleNamespace(y_root=300 - (mod.DRAG_SLOP - 1)))

    assert box.offset == 160, "and the next press is a press again"


def test_every_widget_in_the_content_is_tagged_and_tagged_once() -> None:
    # A press lands on the row under it rather than on the window behind it, so the gestures
    # are bound to a tag every widget in the content carries. Binding them to the window alone
    # would scroll only where the page has nothing on it, which on a full page is nowhere.
    box = _window(content_px=900)
    rows = [_child(box.content.tk) for _ in range(3)]
    nested = _child(rows[0])

    box.bind_scrolling()
    box.bind_scrolling()

    for widget in (box.content.tk, *rows, nested):
        assert widget.tags.count(_tag(box)) == 1, "a second call is free, not a second handler"


def test_a_widget_built_after_the_page_was_bound_is_picked_up_on_the_next_call() -> None:
    # Which is the reason this is a call rather than something done once at construction: the
    # mode rows are destroyed and rebuilt every time the module or the address changes, and a
    # row that arrived since cannot be dragged until it is tagged.
    box = _window(content_px=900)
    box.bind_scrolling()
    later = _child(box.content.tk)

    assert _tag(box) not in later.tags, "it was not there to be tagged"

    box.bind_scrolling()

    assert later.tags.count(_tag(box)) == 1
    assert box.content.tk.tags.count(_tag(box)) == 1, "and what was tagged already is left as it is"


def test_the_bar_is_drawn_only_while_part_of_the_page_is_out_of_sight() -> None:
    # It is the only thing that says there is more of the page: a scrolled window carrying no
    # mark is indistinguishable from a page that has been cut off, which is the very defect
    # this component is here to answer. And a page that has come to fit says nothing, because
    # by then there is nothing to say.
    box = _fitted(content_px=900, budget=400)

    assert _bar(box).placed is not None

    box.content.tk.reqheight = 300
    box.fit(400)

    assert box.scrollable is False
    assert _bar(box).placed is None


def test_the_bar_is_placed_down_the_windows_right_hand_edge() -> None:
    # Placed over the window rather than packed beside it, and to the edge the window turns
    # out to have rather than the one it asked for. Down the whole of it, because it is a
    # scroll bar and not a mark: the trough is a place to press and the arrow heads are at its
    # two ends, none of which is anywhere unless the bar is the height of the window.
    box = _fitted(content_px=900, budget=400)
    bar = _bar(box)

    assert bar.placed["relx"] == 1.0
    assert bar.placed["x"] == -mod.BAR_PX, "inside that edge by its own width"
    assert bar.placed["width"] == mod.BAR_PX
    assert (bar.placed["y"], bar.placed["relheight"]) == (0, 1.0)
    assert bar.lifts >= 1, "and over the page rather than under it"


def test_the_bar_is_drawn_in_the_colors_the_catalogs_own_list_is() -> None:
    # The operator meets a scrolling list in the catalog panel already, and two scroll bars in
    # one GUI that look nothing alike are two things to learn instead of one. Asserted against
    # the module's own constants rather than against color strings so the two can be moved
    # together, and the Lionel pair are the ones the rest of the GUI paints with.
    bar = _bar(_fitted(content_px=900, budget=400))

    assert bar.kwargs["troughcolor"] == mod.BAR_TROUGH_COLOR
    assert bar.kwargs["bg"] == mod.BAR_COLOR, "the handle and the arrow heads"
    assert bar.kwargs["activebackground"] == mod.BAR_ACTIVE_COLOR, "and whichever of them is under the finger"
    assert (bar.kwargs["highlightthickness"], bar.kwargs["highlightbackground"]) == (
        mod.BAR_EDGE_PX,
        mod.BAR_EDGE_COLOR,
    )
    assert bar.kwargs["orient"] == "vertical"
    assert bar.kwargs["takefocus"] == 0, "a bar that took the focus would take it from the page"


def test_the_bar_is_told_what_share_of_the_page_is_showing_and_where_in_it() -> None:
    # The two fractions are the whole of what a scroll bar needs: from them Tk draws the handle
    # at the size and the place it belongs, which is what says how much of the page is in front
    # of the reader and how far down it they are. Nothing here decides where the handle goes --
    # that would be a second opinion about a thing Tk is already right about.
    box = _fitted(content_px=1000, budget=400)

    assert _bar(box).shown == (0.0, 0.4), "at the top, with two fifths of the page showing"

    box.scroll_to(box.hidden_px)

    assert _bar(box).shown == (0.6, 1.0), "and at the foot of the page when it is scrolled there"


def test_the_bar_is_drawn_at_the_width_the_caller_asked_for() -> None:
    # How wide to draw it is a question about the screen rather than about scrolling: the page
    # is drawn in the window less this, so a wider bar is width the page does not get, and how
    # much there is to spare is the caller's own layout.
    box = _fitted(content_px=900, budget=400, bar_px=24)
    bar = _bar(box)

    assert box.bar_px == 24
    assert bar.kwargs["width"] == 24
    assert (bar.placed["x"], bar.placed["width"]) == (-24, 24), "inside that edge by its own width"
    assert box.content.tk.placed["width"] == -24, "and the page keeps clear of the whole of it"


@pytest.mark.parametrize("asked", [None, 0])
def test_a_window_that_asks_for_no_width_gets_one_the_bar_can_be_worked_at(asked: int | None) -> None:
    # 6px was the first answer and could not be told from the frame beside it on the Pi; 10px
    # read as a bar but not as a control, its arrow heads two specks. A bar with parts needs
    # room for them, and the floor is what a caller gets for saying nothing.
    box = _fitted(content_px=900, budget=400, bar_px=asked)

    assert box.bar_px == mod.BAR_PX
    assert _bar(box).placed["width"] == mod.BAR_PX


def test_a_page_being_held_back_is_drawn_clear_of_the_bar() -> None:
    # The bar is drawn over the window rather than packed beside it, so a page spanning the
    # window is a page with the end of every row under the bar -- and a page is written to its
    # own edge: measured on a 480px Pi pane, the widest line of the review page's prose stops
    # 9px inside it, which even a 10px bar takes the end of. So the page keeps off it.
    box = _fitted(content_px=900, budget=400, bar_px=18)

    assert box.scrollable is True
    assert box.gutter_px == 18
    assert box.content.tk.placed["width"] == -18


def test_a_page_with_room_for_itself_is_drawn_to_the_whole_of_the_window() -> None:
    # And a page with no bar down it keeps nothing clear for one: 18px of a 480px Pi pane, 30px
    # of a Deck's, is too much to spend on a bar that is not there. The room is the page's
    # until the moment something is held back in the window, and the page's again as soon as
    # nothing is.
    fits = _fitted(content_px=300, budget=400, bar_px=18)

    assert fits.scrollable is False
    assert fits.gutter_px == 0
    assert fits.content.tk.placed["width"] == 0, "the whole of the window, less nothing"


def test_the_room_the_bar_took_is_handed_back_when_the_page_comes_to_fit() -> None:
    # A titled box hidden as the module changes takes its height with it, and a page that has
    # come to fit its window is a page with no bar to keep clear of. Re-placing it is the whole
    # of the reclaim: Tk lays the page out again at the width it now has, and the <Configure>
    # that follows is what fits the window to whatever that came to.
    box = _fitted(content_px=900, budget=400, bar_px=24)

    assert box.gutter_px == 24

    box.content.tk.reqheight = 300
    box.fit(400)

    assert box.gutter_px == 0
    assert box.content.tk.placed["width"] == 0

    box.content.tk.reqheight = 900
    box.fit(400)

    assert box.gutter_px == 24, "and taken again by a page grown back past its window"
    assert box.content.tk.placed["width"] == -24


def test_a_fit_that_leaves_the_gutter_where_it_was_does_not_place_the_page_again() -> None:
    # The window is fitted on every layout pass -- a row built, a box shown, the popup laid out
    # -- and re-placing the page costs a pass of its own, which would ask for the fit that
    # placed it. Nothing is moved unless the answer changed, which is what keeps the one from
    # feeding the other.
    box = _fitted(content_px=900, budget=400)
    placed = _widths(box)

    box.fit(400)
    box.scroll_to(120)
    box.fit(400)

    assert _widths(box) == placed, "one page placed at one width, however often it is asked"


def test_the_line_across_the_foot_is_drawn_only_while_a_page_is_held_back() -> None:
    # The bar says there is more of the page; what it cannot say is where the page stops. Under
    # the fold are the popup's own keys, which neither scroll nor leave, and two regions with
    # no line between them read as one -- a reader taking hold of the page there finds half of
    # what is under the finger moving and half of it standing still.
    fits = _fitted(content_px=300, budget=400)

    assert _fold(fits) is None, "a window showing the whole of its page has no fold to mark"

    box = _fitted(content_px=900, budget=400)

    assert _fold(box).placed is not None

    box.content.tk.reqheight = 300
    box.fit(400)

    assert _fold(box).placed is None, "and it goes with the bar, there being nothing left to say"


def test_the_line_is_drawn_across_the_whole_foot_of_the_window_with_the_bar_over_it() -> None:
    # Against the window's own foot rather than at a height of its own, so it stays on it
    # however often the window is fitted; the width of the window, the bar included, and the
    # bar raised after it so the corner where the two meet is the bar's.
    box = _fitted(content_px=900, budget=400)
    fold = _fold(box)

    assert (fold.placed["x"], fold.placed["relwidth"]) == (0, 1.0)
    assert fold.placed["rely"] == 1.0
    assert fold.placed["y"] == -mod.FOLD_PX, "inside the foot by its own thickness"
    assert fold.placed["height"] == mod.FOLD_PX
    assert box.viewport.tk.lifted[-1] is _bar(box), "and both of them over the page"


def test_the_line_is_a_gray_hairline_and_nothing_besides() -> None:
    # A boundary rather than a control: it is there to be found without being looked at, which
    # is why it is neither of the colors anything in this GUI is worked by, and why it is a
    # line and not a frame with a line in it.
    fold = _fold(_fitted(content_px=900, budget=400))

    assert fold.kwargs["bg"] == mod.FOLD_COLOR
    assert fold.kwargs["height"] == mod.FOLD_PX
    assert (fold.kwargs["borderwidth"], fold.kwargs["highlightthickness"]) == (0, 0)


@pytest.mark.parametrize(
    "asked, moved",
    [
        (("moveto", "0.5"), 500),
        (("moveto", "0.0"), 0),
        (("moveto", "1.0"), 600),
        (("scroll", "1", "units"), mod.WHEEL_STEP),
        (("scroll", "-1", "units"), 0),
        (("scroll", "1", "pages"), 352),
    ],
)
def test_the_bar_is_worked_by_dragging_it_pressing_it_and_pressing_its_arrows(
    asked: tuple[str, ...], moved: int
) -> None:
    # Everything a scroll bar offers arrives at one callback in Tk's own words, and all three
    # are the operator's: the handle dragged ("moveto"), an arrow head pressed or held (a
    # "unit"), and the trough pressed either side of the handle (a "page"). Answering them is
    # what makes the bar a control rather than a picture of one -- the arrow heads in
    # particular are what a reader who has not guessed that the page can be dragged will
    # reach for.
    box = _fitted(content_px=1000, budget=400)

    box._on_bar(*asked)

    assert box.offset == moved


def test_a_unit_of_the_bar_and_a_notch_of_the_wheel_are_the_same_step() -> None:
    # One idea of how far "a bit further down" is, so a page reads the same however it is
    # moved -- and a page is a window less that step, which keeps a line in sight across a
    # jump so the reader can see where they landed.
    box = _fitted(content_px=1000, budget=400)

    box._on_bar("scroll", "1", "units")
    stepped = box.offset
    box.reset()
    _gesture(box, "<Button-5>")(SimpleNamespace())

    assert box.offset == stepped == mod.WHEEL_STEP


def test_a_bar_asked_for_something_it_cannot_be_asked_for_moves_nothing() -> None:
    # Tk's protocol is a handful of words and this answers those; anything else is a Tk that
    # has changed under us, and a page that leaps to nowhere is a worse answer to that than a
    # page that sits still.
    box = _fitted(content_px=1000, budget=400)
    box.scroll_to(200)

    box._on_bar()
    box._on_bar("moveto")
    box._on_bar("moveto", "halfway")
    box._on_bar("scroll", "1")
    box._on_bar("sideways", "1", "units")

    assert box.offset == 200


def test_a_page_that_is_being_held_back_shows_once_that_it_moves() -> None:
    # The bar says there is more of the page; what it cannot say is that the page itself can be
    # taken hold of anywhere, which is the gesture the operator actually has -- and on a touch
    # screen an 18px bar is not what a finger reaches for. So the page answers for itself, and
    # comes back to where it was, which reads as "this moves" in the time it takes to see it.
    box = _fitted(content_px=900, budget=400)

    assert box.hint() is True
    assert box.offset == mod.HINT_PX

    delay, put_back = box.content.tk.timers[-1]
    assert delay == mod.HINT_MSEC
    put_back()

    assert box.offset == 0, "and the page is where it was, in the time it takes to notice"


def test_a_page_is_shown_that_it_moves_once_and_not_again() -> None:
    # The window is re-fitted on every layout pass -- a row built, a box shown, the popup laid
    # out -- so a hint that fired each time would be a page that will not sit still.
    box = _fitted(content_px=900, budget=400)
    box.hint()
    box.content.tk.timers[-1][1]()

    assert box.hint() is False
    assert box.offset == 0


def test_a_page_turn_is_a_new_page_to_be_shown() -> None:
    # Each page has its own height and only some of them overflow, so the one the operator has
    # just turned to is one they have not been shown yet, however often the last one was.
    box = _fitted(content_px=900, budget=400)
    box.hint()
    box.content.tk.timers[-1][1]()

    box.reset()

    assert box.hint() is True


def test_a_page_that_fits_and_a_page_already_scrolled_are_shown_nothing() -> None:
    # Nothing to say in the first case, and in the second the operator has already found the
    # gesture -- a page moving under a reader who is reading it is an interruption.
    fits = _fitted(content_px=300, budget=400)

    assert fits.hint() is False

    scrolled = _fitted(content_px=900, budget=400)
    scrolled.scroll_to(200)

    assert scrolled.hint() is False
    assert scrolled.offset == 200


def test_a_page_with_barely_anything_hidden_is_moved_only_as_far_as_there_is() -> None:
    # The nudge is a distance rather than a place, and a page with less than that held back
    # would otherwise be asked for more than it has. Clamped, so what the reader sees is the
    # whole of what there is to see.
    box = _fitted(content_px=405, budget=400)

    assert box.hint() is True
    assert box.offset == 5


def test_a_page_whose_popup_went_down_mid_hint_is_not_put_back_anywhere() -> None:
    # A popup can be closed inside the fifth of a second the nudge lasts, and the page it was
    # moving no longer has a window to be put back into. Asked rather than caught, so what is
    # in the log is what actually went wrong somewhere, not a gesture nobody saw.
    box = _fitted(content_px=900, budget=400)
    box.hint()
    box.content.tk.exists = False

    box.content.tk.timers[-1][1]()

    assert box.offset == mod.HINT_PX, "nothing was moved, there being nowhere to move it"


def test_a_page_that_cannot_be_animated_is_not_left_where_the_hint_put_it() -> None:
    # Every other measurement in this component answers with nothing where there is no screen;
    # a hint cannot, having already moved the page by the time it finds out. So it puts it back
    # itself rather than leave the page standing a little way down for good.
    box = _fitted(content_px=900, budget=400)

    def no_screen(*_args: Any) -> None:
        raise mod.TclError("no screen")

    box.content.tk.after = no_screen

    assert box.hint() is False
    assert box.offset == 0


def test_the_window_is_refitted_when_the_content_or_anything_around_it_is_laid_out() -> None:
    # A caller cannot be expected to know when its page changed height -- a titled box shown, a
    # list of rows replaced -- so the page says so itself. And so does the overlay around it,
    # which is laid out for the first time when it is put on screen: until that moment there is
    # no budget to be had, and without hearing about it the window would keep the height it
    # was built with.
    box = _window(content_px=900)
    overlay = DummyBox()
    raw = DummyTk()
    refits: list[str] = []

    box.on_content_resized(lambda: refits.append("fit"), overlay, raw)

    for widget in (box.content.tk, overlay.tk, raw):
        assert [sequence for sequence, _handler, _add in widget.binds] == ["<Configure>"]
        assert widget.binds[0][2] == "+", "added to whatever was bound there already"

    box.content.tk.binds[0][1]()
    box.content.tk.idle[-1]()
    overlay.tk.binds[0][1]()
    box.content.tk.idle[-1]()

    assert refits == ["fit", "fit"]


def test_two_changes_before_tk_settles_ask_for_one_refit() -> None:
    # A page is not done changing size when the widget that changed it is created: guizero
    # packs it, Tk lays it out, and only then is the height the new one. Waiting for that
    # moment and coalescing on it is what keeps a page of rows from asking for a fit apiece as
    # it is built.
    box = _window(content_px=900)
    refits: list[str] = []
    box.on_content_resized(lambda: refits.append("fit"))
    settle = box.content.tk.binds[0][1]

    settle()
    settle()

    assert len(box.content.tk.idle) == 1, "one refit, however many rows were built"

    box.content.tk.idle[0]()

    assert refits == ["fit"]

    settle()

    assert len(box.content.tk.idle) == 2, "and the next change is heard again"
