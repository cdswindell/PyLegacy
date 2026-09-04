#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import tkinter as tk
from tkinter import TclError
from typing import Any, Callable, Iterator

from guizero import Box

from ..guizero_base import LIONEL_BLUE, LIONEL_ORANGE

# What a widget may raise when it is asked about a screen it is no longer on -- a popup taken
# down mid-gesture, a row rebuilt under a drag. Caught rather than guarded against, as
# everywhere else in this package: there is no answer to give, and a scroll is not worth an
# exception reaching the operator.
SCROLL_EXCEPTIONS = (AttributeError, RuntimeError, TclError, TypeError, ValueError)

# How far a finger has to travel before a press becomes a drag, in pixels. Under it the press
# is left alone and lands on whatever is under it -- a radio row, a stepper key -- so tapping
# a control inside a scrolling page still works. Over it the content follows the finger.
#
# 8px is about a fingertip's own wobble on the Pi's panel. Lower and a firm tap on a radio row
# slides the page a little under the finger; higher and a short drag does nothing at all,
# which reads as the page being stuck.
DRAG_SLOP = 8

# What one notch of a mouse wheel moves, in pixels. A desk has no finger to drag with, and
# this is the one input on the desktop that scrolls without taking a button press away from
# something. Roughly two rows of the panel's own text.
WHEEL_STEP = 48

# How far the page slides, and for how long, when it shows the reader that it moves; see
# hint(). Far enough that the eye catches it -- a row's own height is about 34px, so this is a
# third of a row appearing at the foot of the window -- and brief enough that a finger already
# on its way to a control cannot land while the page is away from where it was seen.
HINT_PX = 12
HINT_MSEC = 220

# The bar drawn down the right edge of a page with more to it than fits. Placed over the
# content rather than packed beside it, so nothing outside this component has to know it is
# there: the window is the width it was asked for whether a bar is drawn in it or not, and
# what the bar costs is paid inside the window, out of the page -- and only while it is drawn.
# See the gutter in __init__ and _set_gutter.
#
# It is the only thing that says there is more of the page: a scrolled window with no mark on
# it is indistinguishable from a page that has been cut off, which is the very defect this is
# here to answer. It was first drawn as a painted block, and a painted block is all it said:
# a mark that reports where in the page the reader is, and looks like nothing that could be
# taken hold of. So it is Tk's own scrollbar now -- a trough, a handle, and an arrow head at
# either end, every one of them working -- which says what it is by being it.
#
# The colors and the styling are CatalogPanel's, wholesale, down to the orange edge: the
# operator meets a scrolling list there already, and two scroll bars in one GUI that look
# nothing alike are two things to learn instead of one. Lionel blue for the trough, the
# handle and arrows in gray against it, and orange for the element under the finger, which is
# the one part of it that answers back.
BAR_TROUGH_COLOR = LIONEL_BLUE
BAR_COLOR = "lightgrey"
BAR_ACTIVE_COLOR = LIONEL_ORANGE
BAR_EDGE_COLOR = LIONEL_ORANGE
BAR_EDGE_PX = 1

# The width is what a caller may ask for; this is the floor, and it is set by the narrowest
# screen the bar has to be *noticed* on. 6px was the first attempt and it was too fine to
# tell from the frame beside it on the Pi -- a bar nobody sees says nothing, which is the
# whole of what it is for -- and 10px read as a bar without reading as a control: at that
# width Tk draws the arrow heads as two specks, and the trough is too narrow to aim a finger
# at. 18px is the narrowest at which the whole of it is legible on the Pi, and a screen with
# width to spare should ask for more (see bar_px).
BAR_PX = 18

# The line drawn across the foot of the window while a page is being held back in it. The bar
# says there is more of the page; what it cannot say is where the page ends, and on a full
# page nothing else says it either -- the last row above the fold is the same prose drawn to
# the same width as the rest, and below it are the popup's own keys, which do not scroll and
# never leave. Two regions with no line between them read as one, and a reader who takes hold
# of a page there finds that half of what is under the finger moves and half of it does not.
#
# So the window closes its own foot. A hairline rather than a rule, and gray rather than
# either of the panel's own colors: this is a boundary and not a control, and it should be
# findable without ever being looked at. Drawn only with the bar, and for the bar's own
# reason -- a window showing the whole of its page has no fold to mark -- and the two
# together draw two sides of the region that moves.
FOLD_COLOR = "gray"
FOLD_PX = 1


def descendants(widget: Any) -> Iterator[Any]:
    """Every Tk widget inside widget, and widget itself."""
    yield widget
    try:
        children = widget.winfo_children()
    except SCROLL_EXCEPTIONS:
        return
    for child in children:
        yield from descendants(child)


class ScrollBox:
    """A window onto a stack of widgets taller than the room there is for it.

    A page of an overlay is built into the content Box exactly as it would be built into any
    other container; what this adds is that the room it is given is decided separately from
    the room it asks for. Where the two agree nothing here is visible: the window is the
    height of its content and no bar is drawn. Where the content asks for more, the surplus
    is reached by moving the content behind the window rather than by being dropped.

    Dropped is what Tk does otherwise, and it drops the wrong end: pack allots space in
    creation order, so a page too tall for its pane costs whatever was packed last -- which
    in an overlay is the buttons along the bottom, including the one that closes it.

    How it is put together, and why it looks like this:

    * The window is an ordinary guizero Box with pack propagation off, which is the same
      trick GuiZeroBase.add_vspace uses for a spacer: a Box told its height keeps it instead
      of shrinking onto its children.
    * The content Box inside it is created hidden and then placed. guizero re-packs a
      container's children whenever anything in it is created, shown or hidden -- the reason
      so much of this package replays its own layout -- and a child it believes is hidden is
      one it never packs. place() then puts it on screen at a position of its own, and
      pack_forget on a placed widget is the no-op that lets the two coexist. Verified across
      page turns and rows built at runtime: the content stays placed.
    * Tk clips a child to its parent, so the window needs no canvas and no scroll region. What
      is outside it is simply not drawn.
    * The bar down the edge and the line across the foot are placed over the content as well,
      and the room the bar needs is taken out of the page only while it is drawn: a window
      with room for its whole page keeps nothing back and gives nothing up. See _set_gutter.
    """

    def __init__(self, master: Box, *, width: int, align: str = "top", bar_px: int = None) -> None:
        self._width = max(1, int(width))
        # How wide the bar down the right edge is drawn. Taken from the caller rather than
        # decided here, because it is a question about the screen and not about scrolling:
        # the bar is drawn over the page, so its width is paid for in what it covers of the
        # right-hand end of a row, and how much there is to cover is the caller's own layout.
        self._bar_px = max(1, int(bar_px or BAR_PX))
        # How much of that width is being kept clear of the page as things stand; see
        # _set_gutter. Nothing, until there is a bar to keep it for.
        self._gutter = 0
        self._offset = 0
        self._view_px = 0
        self._drag_from: tuple[int, int] | None = None
        self._dragging = False
        self._tag = f"PyTrainScroll{id(self):x}"
        self._tagged: set[str] = set()
        self._bar: Any = None
        self._fold: Any = None
        # Whether this page has already been shown that it moves; see hint().
        self._hinted = False
        self._viewport = Box(master, align=align, width=self._width, height=1)
        try:
            self._viewport.tk.pack_propagate(False)
        except SCROLL_EXCEPTIONS:
            pass
        # Hidden as far as guizero is concerned, and on screen as far as the operator is
        # concerned; see the class.
        self._content = Box(self._viewport, align="top", visible=False)
        try:
            # As wide as the window actually turns out to be, rather than as wide as it was
            # asked to be: a window packed into a body is given that body's width, which is
            # its own less whatever border is drawn around it. A content frame held to the
            # width asked for hangs a few pixels off the right-hand edge, and what hangs off
            # it is the end of every row. Hence relwidth, which is that width whatever it
            # comes to, less the gutter.
            #
            # The gutter is the bar's own width, kept clear of the page while a bar is drawn
            # in it and given back when none is. The bar is drawn over the window, so without
            # a gutter it is drawn over the *page* -- and a page is written to its own edge:
            # measured on a 480px Pi pane, the widest line of the review page's prose stops
            # 9px inside it, which even a 10px bar takes the end of. And a page that fits
            # should not pay for a bar that is never drawn, which on a Deck is 30px of a pane
            # with none to spare. So the page has the whole of the window until it overflows,
            # and the bar takes its width out of the page for as long as it is there.
            self._content.tk.place(x=0, y=0, relwidth=1.0, width=-self._gutter)
        except SCROLL_EXCEPTIONS:
            pass
        self._bind_gestures()

    @property
    def content(self) -> Box:
        """The container a caller builds its page into."""
        return self._content

    @property
    def bar_px(self) -> int:
        """How wide the bar down the right edge is drawn, in pixels."""
        return self._bar_px

    @property
    def gutter_px(self) -> int:
        """How much of the window is being kept clear of the page, in pixels.

        The bar's own width while there is a bar to keep it for, and nothing while there is
        not; see _set_gutter.
        """
        return self._gutter

    @property
    def viewport(self) -> Box:
        """The window the content is seen through -- what the layout above sees."""
        return self._viewport

    @property
    def offset(self) -> int:
        """How far the content has been moved up behind the window, in pixels."""
        return self._offset

    @property
    def content_px(self) -> int:
        """How tall the content is, in pixels. Zero where there is nothing to measure."""
        try:
            return int(self._content.tk.winfo_reqheight())
        except SCROLL_EXCEPTIONS:
            return 0

    @property
    def view_px(self) -> int:
        """How tall the window is, in pixels -- what fit last settled on."""
        return self._view_px

    @property
    def hidden_px(self) -> int:
        """How much of the content is out of sight, in pixels."""
        return max(0, self.content_px - self._view_px) if self._view_px else 0

    @property
    def scrollable(self) -> bool:
        """Whether there is more of the page than the window is showing."""
        return self.hidden_px > 0

    def fit(self, budget: int | None = None) -> int:
        """Give the window the room it has, and the content back whatever of it can use.

        budget is the most the window may take. Where it is None, or nothing measurable, the
        window is the height of its content, and nothing is hidden -- an unmeasured screen
        draws what it always drew rather than a window of some arbitrary height.

        Called whenever the content might have changed height, which is oftener than a caller
        can be expected to remember: the content's own <Configure> asks for it too.
        """
        wanted = self.content_px
        if wanted <= 0:
            return self._view_px
        height = wanted if budget is None or budget <= 0 else min(wanted, int(budget))
        if height != self._view_px:
            self._view_px = height
            try:
                self._viewport.height = height
            except SCROLL_EXCEPTIONS:
                pass
        self.scroll_to(self._offset)
        return self._view_px

    def scroll_to(self, offset: int) -> bool:
        """Move the content so offset pixels of it are above the window. True, where it moved.

        Clamped to what there is: a page that has shrunk under a scroll -- a titled box hidden
        as the module changed -- is pulled back down rather than left, showing the white space
        it used to have below it.
        """
        target = max(0, min(int(offset), self.hidden_px))
        moved = target != self._offset
        self._offset = target
        try:
            self._content.tk.place_configure(y=-target)
        except SCROLL_EXCEPTIONS:
            pass
        self._draw_bar()
        return moved

    def scroll_by(self, pixels: int) -> bool:
        """Move the content by pixels -- positive is further down the page."""
        return self.scroll_to(self._offset + int(pixels))

    def reset(self) -> bool:
        """Back to the top of the page. What a page turn does; see LcsConfigPanel._show_page."""
        # A new page is a page nobody has been shown yet, however often the last one was.
        self._hinted = False
        return self.scroll_to(0)

    def hint(self) -> bool:
        """Show once, by moving it, that the page under the reader moves. True where it did.

        The bar down the edge says there is more of the page; what it cannot say is that the
        page itself can be taken hold of anywhere, which is the gesture the operator actually
        has -- a bar 18px wide on a touch screen is not what a finger reaches for. So the page
        answers for itself: it slides a little and comes back, which reads as "this moves" in
        the time it takes to see it and asks nothing of the reader.

        Once per page, and only where there is something to show: a nudge repeated on every
        layout pass would be a page that will not sit still. Called after the window has been
        fitted, since until then whether the page even overflows is unknown.
        """
        if self._hinted or not self.scrollable or self._offset:
            return False
        self._hinted = True
        if not self.scroll_to(min(HINT_PX, self.hidden_px)):
            return False
        try:
            self._content.tk.after(HINT_MSEC, self._hint_over)
        except SCROLL_EXCEPTIONS:
            # No screen to animate on, and nothing to undo either: put it back at once rather
            # than leave the page standing where the hint left it.
            self.scroll_to(0)
            return False
        return True

    def _hint_over(self) -> None:
        """Put the page back where it was found. The other half of hint().

        A popup can be closed inside the moment the nudge lasts, and a page put back after its
        window has gone is a page put back nowhere. Everything this touches answers quietly to
        a widget that is no longer on screen, so nothing is guarded against here beyond asking
        first, which keeps a Tk background error out of the log for a gesture nobody saw.
        """
        try:
            if not self._content.tk.winfo_exists():
                return
        except SCROLL_EXCEPTIONS:
            return
        self.scroll_to(0)

    def show_widget(self, widget: Any) -> bool:
        """Bring widget into the window, moving as little as it takes. True, where it moved.

        The least movement, rather than centering it: what the operator is reading is where
        they left it, and a list stepped one row at a time should walk to its end rather than
        jump each time the row it is on happens to be near an edge.

        Takes a guizero widget or the Tk one inside it indifferently: a row of a CheckBoxGroup
        is held as the Tk widget it is painted through, and a caller with one of those in hand
        should not have to know which of the two this wanted.
        """
        if not self.scrollable:
            return False
        target = getattr(widget, "tk", widget)
        try:
            top = int(target.winfo_rooty()) - int(self._content.tk.winfo_rooty())
            height = int(target.winfo_height()) or int(target.winfo_reqheight())
        except SCROLL_EXCEPTIONS:
            return False
        if top < self._offset:
            return self.scroll_to(top)
        bottom = top + height
        if bottom > self._offset + self._view_px:
            return self.scroll_to(bottom - self._view_px)
        return False

    def bind_scrolling(self) -> None:
        """Let every widget in the content be dragged and wheeled, however new it is.

        The gestures are bound to a tag of this box's own rather than to each widget, so
        adding a row is adding a tag and never a second copy of a handler. Called after the
        content is built and again whenever it is rebuilt -- the mode rows are replaced every
        time the module changes -- and passing over what is already tagged is what makes
        calling it again free.
        """
        for widget in descendants(self._content.tk):
            try:
                name = str(widget)
                if name in self._tagged:
                    continue
                tags = widget.bindtags()
                if self._tag not in tags:
                    widget.bindtags(tuple(tags) + (self._tag,))
                self._tagged.add(name)
            except SCROLL_EXCEPTIONS:
                continue

    #
    # Gestures
    #
    # A finger on the panel and a wheel on the desk. Both are bound to the tag every widget
    # in the content carries, because a press lands on the row under it rather than on the
    # window behind it -- binding the window alone would scroll only where the page happens
    # to have nothing on it, which on a full page is nowhere.
    #
    def _bind_gestures(self) -> None:
        bind = getattr(self._viewport.tk, "bind_class", None)
        if bind is None:
            return
        for sequence, handler in (
            ("<Button-1>", self._on_press),
            ("<B1-Motion>", self._on_drag),
            ("<ButtonRelease-1>", self._on_release),
            ("<MouseWheel>", self._on_wheel),
            # X11 reports a wheel as a button, which is what the Pi's desktop sends.
            ("<Button-4>", self._on_wheel_up),
            ("<Button-5>", self._on_wheel_down),
        ):
            try:
                bind(self._tag, sequence, handler, add="+")
            except SCROLL_EXCEPTIONS:
                continue

    def _on_press(self, event: Any) -> None:
        self._drag_from = (int(getattr(event, "y_root", 0)), self._offset)
        self._dragging = False

    def _on_drag(self, event: Any) -> None:
        if self._drag_from is None or not self.scrollable:
            return
        start_y, start_offset = self._drag_from
        travel = start_y - int(getattr(event, "y_root", 0))
        if not self._dragging and abs(travel) < DRAG_SLOP:
            # Still a press as far as anything under the finger is concerned; see DRAG_SLOP.
            return
        self._dragging = True
        self.scroll_to(start_offset + travel)

    def _on_release(self, _event: Any = None) -> None:
        self._drag_from = None
        self._dragging = False

    def _on_wheel(self, event: Any) -> None:
        delta = int(getattr(event, "delta", 0) or 0)
        if delta:
            # macOS reports single notches, Windows multiples of 120; either way the sign is
            # what matters and one notch is one step.
            self.scroll_by(-WHEEL_STEP if delta > 0 else WHEEL_STEP)

    def _on_wheel_up(self, _event: Any = None) -> None:
        self.scroll_by(-WHEEL_STEP)

    def _on_wheel_down(self, _event: Any = None) -> None:
        self.scroll_by(WHEEL_STEP)

    #
    # The bar, the gutter it stands in, and the line across the foot of the window
    #
    def _draw_bar(self) -> None:
        """Show how much of the page is in the window, and where in it this is.

        Drawn only while there is something to say. Placed over the content at the right
        edge and down the whole of it, with the page held clear of its width for as long as
        it is there: the bar is over the page rather than beside it because that costs the
        layout above nothing, and what it costs instead is the end of every row unless the
        page gives it room. The line across the foot arrives with it and goes with it --
        both of them say the one thing, that this is part of a page.

        Where the handle sits inside it is Tk's arithmetic rather than this component's: a
        scrollbar is told the two fractions of the page the window is showing and draws
        itself from them, which is also what makes the handle draggable and the trough
        clickable without a line of code here. What is left to say is what the fractions are.
        """
        hidden = self.hidden_px
        if not hidden or self._view_px <= 0:
            self._hide_bar()
            return
        self._set_gutter(self._bar_px)
        # Before the bar rather than after it, so that the bar's own lift leaves it standing
        # over the line: the line is drawn the whole width of the window, and where the two
        # of them meet is the bar's corner and not the line's.
        self._draw_fold()
        total = self.content_px
        first = self._offset / total
        last = min(1.0, (self._offset + self._view_px) / total)
        try:
            if self._bar is None:
                self._bar = tk.Scrollbar(
                    self._viewport.tk,
                    orient="vertical",
                    command=self._on_bar,
                    width=self._bar_px,
                    troughcolor=BAR_TROUGH_COLOR,
                    bg=BAR_COLOR,
                    activebackground=BAR_ACTIVE_COLOR,
                    highlightthickness=BAR_EDGE_PX,
                    highlightbackground=BAR_EDGE_COLOR,
                    # A scrollbar that takes the focus takes it from whatever the operator is
                    # working the page with; the sliders in this GUI are built the same way.
                    takefocus=0,
                )
            self._bar.set(first, last)
            # Against the window's right-hand edge wherever that turns out to be, for the
            # reason the content is placed to the same edge: a window is as wide as the body
            # it was packed into, not as wide as it asked to be, and a bar placed at the
            # width asked for is a bar drawn off the screen.
            self._bar.place(relx=1.0, x=-self._bar_px, y=0, width=self._bar_px, relheight=1.0)
            self._bar.lift()
        except SCROLL_EXCEPTIONS:
            self._bar = None

    def _hide_bar(self) -> None:
        """Take the bar and the line down, and give the page the gutter back.

        The gutter first and whether or not there is a bar to forget: a window that has never
        overflowed has never made one, and it still owes the page an answer about the room --
        which is that a page with nothing hidden pays nothing for a bar that is not drawn.
        """
        self._set_gutter(0)
        self._hide_fold()
        if self._bar is None:
            return
        try:
            self._bar.place_forget()
        except SCROLL_EXCEPTIONS:
            self._bar = None

    def _on_bar(self, *args: Any) -> None:
        """Scroll the page as the bar was worked: Tk's own scrollbar protocol.

        Three gestures arrive here, and all three are the operator's: the handle dragged
        ("moveto" and where to), an arrow head pressed or held ("scroll" by units), and the
        trough clicked either side of the handle ("scroll" by pages). A unit is the wheel's
        own step, so the arrow heads and the wheel agree, and a page is the window less that
        step -- a line kept in sight across a jump is what says where the reader landed.
        """
        if not args:
            return
        how = str(args[0])
        try:
            if how == "moveto":
                self.scroll_to(int(float(args[1]) * self.content_px))
            elif how == "scroll":
                count = int(float(args[1]))
                step = WHEEL_STEP if str(args[2]).startswith("unit") else max(WHEEL_STEP, self._view_px - WHEEL_STEP)
                self.scroll_by(count * step)
        except (IndexError, TypeError, ValueError):
            return

    def _set_gutter(self, px: int) -> None:
        """Keep px pixels of the window's right-hand edge clear of the page.

        The bar's width while a bar is drawn and nothing while none is, which is what makes
        the room the bar takes room the page gets back. Re-placing the content is the whole
        of it: Tk lays the page out again at the width it now has, and the <Configure> that
        follows is what asks for the fit -- so a page whose height changed by being re-laid
        out is measured again before anything else is decided about it. See on_content_resized.

        Which is why the same value twice is a no-op rather than a harmless repeat: a place
        that changes nothing still costs a layout pass, and one of those per fit is a loop.
        What keeps the real thing from being one is that the two states cannot argue. A page
        gives the gutter up only where it fits without a bar, and widening a page cannot make
        it overflow; it takes one only where it overflows with the whole window to itself, and
        narrowing a page cannot make it fit. Whichever way it goes, it goes once.
        """
        if px == self._gutter:
            return
        self._gutter = px
        try:
            self._content.tk.place_configure(width=-px)
        except SCROLL_EXCEPTIONS:
            pass

    def _draw_fold(self) -> None:
        """Close the foot of the window with a hairline; see FOLD_COLOR.

        Placed against the window's own foot rather than at a height of its own, so it stays
        on it however often the window is fitted and re-fitted: rely puts it at the bottom
        edge whatever that comes to, and y brings it back inside by its own thickness.
        """
        try:
            if self._fold is None:
                self._fold = tk.Frame(
                    self._viewport.tk,
                    bg=FOLD_COLOR,
                    height=FOLD_PX,
                    borderwidth=0,
                    highlightthickness=0,
                )
            self._fold.place(x=0, rely=1.0, y=-FOLD_PX, relwidth=1.0, height=FOLD_PX)
            self._fold.lift()
        except SCROLL_EXCEPTIONS:
            self._fold = None

    def _hide_fold(self) -> None:
        if self._fold is None:
            return
        try:
            self._fold.place_forget()
        except SCROLL_EXCEPTIONS:
            self._fold = None

    def on_content_resized(self, refit: Callable[[], None], *also: Any) -> None:
        """Ask refit whenever the content changes height, once Tk has settled.

        A page is not done changing size when the widget that changed it is created: guizero
        packs it, Tk lays it out, and only then is the height of the new one. after_idle is that
        moment, and coalescing on the pending call is what keeps a page of rows from asking
        for a fit apiece as it is built.

        also is anything else whose resizing changes the answer -- the overlay the window is
        drawn in, which is laid out for the first time when it is put on screen. Until then
        every measurement of it reads 1 and there is no budget to be had, so without this the
        window would keep whatever height it was built with.

        The refit's own effect is safe to hear about: it changes the window's height, which
        resizes what is around it, which asks again -- and the second answer is the first,
        since the budget is taken as the overshoot and there is none left. It settles in one
        pass rather than oscillating.
        """
        pending: list[Any] = []

        def settle(_event: Any = None) -> None:
            if pending:
                return

            def run() -> None:
                pending.clear()
                refit()

            try:
                pending.append(self._content.tk.after_idle(run))
            except SCROLL_EXCEPTIONS:
                pending.clear()

        for widget in (self._content, *also):
            try:
                getattr(widget, "tk", widget).bind("<Configure>", settle, add="+")
            except SCROLL_EXCEPTIONS:
                continue
