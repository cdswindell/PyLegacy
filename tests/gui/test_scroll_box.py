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
        self.propagated: list[bool] = []
        self.placed: dict[str, Any] = {}
        self.binds: list[tuple[str, Any, str | None]] = []
        self.class_binds: list[tuple[str, str, Any, str | None]] = []
        self.children: list[DummyTk] = []
        self.idle: list[Any] = []
        self.thumbs: list[DummyThumb] = []
        self.tags: tuple[str, ...] = (self._name,)

    def __str__(self) -> str:
        return self._name

    def pack_propagate(self, flag: bool) -> None:
        self.propagated.append(flag)

    def place(self, **kwargs: Any) -> None:
        self.placed.update(kwargs)

    def place_configure(self, **kwargs: Any) -> None:
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

    def winfo_children(self) -> list[DummyTk]:
        return list(self.children)

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


class DummyThumb:
    """The bar down the right edge, as _draw_thumb makes one: a raw Tk Frame.

    Recorded on the window it is drawn over rather than handed back, so a test reads the bar
    off the box it is asking about. A bar taken down is kept and merely unplaced, which is
    what the component does with it, so placed rather than the object itself is what says
    whether anything is on screen.
    """

    def __init__(self, master: DummyTk, **kwargs: Any) -> None:
        self.master = master
        self.kwargs = dict(kwargs)
        self.placed: dict[str, Any] | None = None
        self.lifts = 0
        master.thumbs.append(self)

    def place(self, **kwargs: Any) -> None:
        self.placed = dict(kwargs)

    def place_forget(self) -> None:
        self.placed = None

    def lift(self) -> None:
        self.lifts += 1


@pytest.fixture(autouse=True)
def _no_display(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every widget the window makes, made without a screen to make it on."""
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    # The bar is a raw Tk Frame rather than a guizero widget -- it is drawn over the page
    # rather than packed beside it -- so tkinter's own name in the module is what stands in.
    monkeypatch.setattr(mod, "tk", SimpleNamespace(Frame=DummyThumb), raising=True)


def _window(content_px: int = 0, width: int = 400, thumb_px: int = None) -> mod.ScrollBox:
    """A window onto a page content_px tall.

    The height is the content's own answer to winfo_reqheight, which is where the real one
    reads it: a test grows or shrinks the page by saying that again.
    """
    box = mod.ScrollBox(DummyBox(), width=width, thumb_px=thumb_px)
    box.content.tk.reqheight = content_px
    return box


def _fitted(content_px: int, budget: int, width: int = 400, thumb_px: int = None) -> mod.ScrollBox:
    """That window, given the room a screen has for it."""
    box = _window(content_px, width, thumb_px)
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


def _bar(box: mod.ScrollBox) -> DummyThumb | None:
    """The bar the window has made, or None where it has made none."""
    bars = box.viewport.tk.thumbs
    return bars[-1] if bars else None


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
    assert box.viewport.tk.thumbs == [], "and no bar was ever drawn to say otherwise"


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


def test_the_bar_is_placed_against_the_windows_right_hand_edge() -> None:
    # Placed over the content rather than packed beside it, and to the edge the window turns
    # out to have rather than the one it asked for: the Pi has no width to give, so the bar
    # must cost none -- it appears and disappears without a single row moving.
    box = _fitted(content_px=900, budget=400)
    bar = _bar(box)

    assert bar.placed["relx"] == 1.0
    assert bar.placed["x"] == -mod.THUMB_PX, "inside that edge by its own width"
    assert bar.placed["width"] == mod.THUMB_PX
    assert bar.kwargs["bg"] == mod.THUMB_COLOR
    assert bar.lifts >= 1, "and over the page rather than under it"


def test_the_bar_is_as_tall_a_share_of_the_window_as_the_window_is_of_the_page() -> None:
    # What it says is how much of the page is in front of the reader and where in the page
    # this is: a bar of a fixed size would say the first thing wrongly and the second by
    # accident.
    box = _fitted(content_px=1000, budget=400)

    # Two fifths of the page is showing, so the bar is two fifths of the window.
    assert _bar(box).placed["height"] == 160
    assert _bar(box).placed["y"] == 0

    box.scroll_to(box.hidden_px)

    assert _bar(box).placed["y"] == 400 - 160, "at the foot of the window when at the foot of the page"


def test_the_bar_is_never_drawn_too_small_to_be_seen() -> None:
    # A long page in a short window works the share of it down to a couple of pixels, and a
    # mark that small is no mark: it reads as a speck on the border rather than as a bar the
    # reader can see move.
    box = _fitted(content_px=4000, budget=100)

    assert _bar(box).placed["height"] == mod.THUMB_MIN_PX


def test_the_bar_is_drawn_at_the_width_the_caller_asked_for() -> None:
    # How wide to draw it is a question about the screen rather than about scrolling: the bar
    # is painted over the page, so what a wider one takes is taken out of the right-hand end
    # of a row, and how much there is to spare there is the caller's own layout.
    box = _fitted(content_px=900, budget=400, thumb_px=18)
    bar = _bar(box)

    assert box.thumb_px == 18
    assert bar.kwargs["width"] == 18
    assert (bar.placed["x"], bar.placed["width"]) == (-18, 18), "inside that edge by its own width"


@pytest.mark.parametrize("asked", [None, 0])
def test_a_window_that_asks_for_no_width_gets_one_the_bar_can_be_seen_at(asked: int | None) -> None:
    # 6px was the first answer, and on the Pi it could not be told from the frame beside it --
    # so the one screen where a page is ever held back was the one screen with nothing to say
    # that it had been. The floor is what a caller gets for saying nothing.
    box = _fitted(content_px=900, budget=400, thumb_px=asked)

    assert box.thumb_px == mod.THUMB_PX
    assert _bar(box).placed["width"] == mod.THUMB_PX


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
