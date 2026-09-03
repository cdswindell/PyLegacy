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

# The bar drawn down the right edge of a page with more to it than fits. Placed over the
# content rather than packed beside it, so it costs no width -- the Pi has none to give -- and
# so it can appear and disappear without moving a single row.
#
# It is the only thing that says there is more of the page: a scrolled window with no mark on
# it is indistinguishable from a page that has been cut off, which is the very defect this is
# here to answer.
# Drawn in the gray this package already says "aside" in -- the color of the help screen's
# footnotes -- rather than in a color of its own: it is a fact about the page, not part of
# it. Shot at the pale border gray beside it, it read as a seam in the frame.
THUMB_PX = 6
THUMB_COLOR = "#6B7280"
THUMB_MIN_PX = 24


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
    * Tk clips a child to its parent, so the window needs no canvas and no scrollregion. What
      is outside it is simply not drawn.
    """

    def __init__(self, master: Box, *, width: int, align: str = "top") -> None:
        self._width = max(1, int(width))
        self._offset = 0
        self._view_px = 0
        self._drag_from: tuple[int, int] | None = None
        self._dragging = False
        self._tag = f"PyTrainScroll{id(self):x}"
        self._tagged: set[str] = set()
        self._thumb: Any = None
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
            # it is the end of every row.
            self._content.tk.place(x=0, y=0, relwidth=1.0)
        except SCROLL_EXCEPTIONS:
            pass
        self._bind_gestures()

    @property
    def content(self) -> Box:
        """The container a caller builds its page into."""
        return self._content

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
        """Give the window the room it has, and the content back whatever of it it can use.

        budget is the most the window may take. Where it is None, or nothing measurable, the
        window is the height of its content and nothing is hidden -- an unmeasured screen
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
        """Move the content so offset pixels of it are above the window. True where it moved.

        Clamped to what there is: a page that has shrunk under a scroll -- a titled box hidden
        as the module changed -- is pulled back down rather than left showing the white space
        it used to have below it.
        """
        target = max(0, min(int(offset), self.hidden_px))
        moved = target != self._offset
        self._offset = target
        try:
            self._content.tk.place_configure(y=-target)
        except SCROLL_EXCEPTIONS:
            pass
        self._draw_thumb()
        return moved

    def scroll_by(self, pixels: int) -> bool:
        """Move the content by pixels -- positive is further down the page."""
        return self.scroll_to(self._offset + int(pixels))

    def reset(self) -> bool:
        """Back to the top of the page. What a page turn does; see LcsConfigPanel._show_page."""
        return self.scroll_to(0)

    def show_widget(self, widget: Any) -> bool:
        """Bring widget into the window, moving as little as it takes. True where it moved.

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
    # The bar
    #
    def _draw_thumb(self) -> None:
        """Show how much of the page is in the window, and where in it this is.

        Drawn only while there is something to say. Placed over the content at the right
        edge, so it takes no width from the page and none of the rows move when it appears.
        """
        hidden = self.hidden_px
        if not hidden or self._view_px <= 0:
            self._hide_thumb()
            return
        total = self.content_px
        height = max(THUMB_MIN_PX, int(self._view_px * self._view_px / total))
        travel = self._view_px - height
        top = int(travel * self._offset / hidden) if travel > 0 else 0
        try:
            if self._thumb is None:
                self._thumb = tk.Frame(self._viewport.tk, bg=THUMB_COLOR, width=THUMB_PX)
            # Against the window's right-hand edge wherever that turns out to be, for the
            # reason the content is placed to the same edge: a window is as wide as the body
            # it was packed into, not as wide as it asked to be, and a bar placed at the
            # width asked for is a bar drawn off the screen.
            self._thumb.place(relx=1.0, x=-THUMB_PX, y=top, width=THUMB_PX, height=height)
            self._thumb.lift()
        except SCROLL_EXCEPTIONS:
            self._thumb = None

    def _hide_thumb(self) -> None:
        if self._thumb is None:
            return
        try:
            self._thumb.place_forget()
        except SCROLL_EXCEPTIONS:
            self._thumb = None

    def on_content_resized(self, refit: Callable[[], None], *also: Any) -> None:
        """Ask refit whenever the content changes height, once Tk has settled.

        A page is not done changing size when the widget that changed it is created: guizero
        packs it, Tk lays it out, and only then is the height the new one. after_idle is that
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
