#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from abc import ABCMeta, abstractmethod
from typing import Callable, TYPE_CHECKING

from guizero import Box

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class OverlayPanel(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, gui: "EngineGui", title: str, *, post_close: Callable = None):
        self._gui = gui
        self._title = title
        self._post_close = post_close
        self._overlay = None

    @abstractmethod
    def build(self, body: Box):
        pass

    @property
    def gui(self) -> "EngineGui":
        return self._gui

    @property
    def overlay(self) -> Box:
        if self._overlay is None:
            # noinspection PyProtectedMember
            self._overlay = self._gui._popup.create_popup(
                self._title,
                self,
                post_close_action=self._post_close,
            )
        return self._overlay

    @property
    def visible(self) -> bool:
        return self._overlay is not None and self._overlay.visible

    @property
    def has_close(self) -> bool:
        """Whether create_popup gives this panel's popup a Close button.

        True for every panel that has no other way off itself, which is all of them bar
        the LCS configuration panel; see LcsConfigPanel.has_close.
        """
        return True

    @property
    def closes_on_request_only(self) -> bool:
        """Whether this panel's popup goes off the screen only when something asks for it.

        False for a panel that is a view of whatever the pane has selected. The pane closes
        its popup whenever that selection is re-read -- see EngineGui.update_component_info
        and make_recent -- and a view of the component that *was* selected is worse than no
        view at all, so those panels are right to go quietly.

        True is for a panel the operator is working *in* rather than reading off: one with
        pages of its own, or an answer on it that arrived once and will not arrive again. The
        layout goes on reporting itself the whole time such a panel is up, and a report is
        not a reason to take it away; see LcsConfigPanel.closes_on_request_only.
        """
        return False

    @property
    def has_footer(self) -> bool:
        return False

    @property
    def footer_pad_px(self) -> int | None:
        """The vertical whitespace this panel wants in the footer band, in pixels.

        None -- which is what a panel says by saying nothing -- is the shared band:
        FOOTER_LEAD above the footer row and FOOTER_BUTTON_PAD above and below the button
        in it. That is right for a panel whose content ends where its footer begins, since
        the band is then the one thing holding the buttons off the panel and the pane.

        A panel with a row of buttons of its own directly above Close is the case for asking
        for less: the band is then whitespace between two rows of buttons rather than
        between a panel and its buttons, and three helpings of a footer band's worth of it
        stacked down one overlay is height the fullest page has nowhere to take from. See
        LcsConfigPanel.footer_pad_px.
        """
        return None

    def build_footer(self, footer: Box) -> None:
        pass

    def refresh_footer(self) -> None:
        pass

    def _close(self) -> None:
        # A panel closing itself is the operator asking for it to go, so it goes even where
        # the panel would otherwise stay put; see closes_on_request_only.
        if self._overlay and self._gui and self._gui.popup_manager:
            self._gui.popup_manager.close_requested(self._overlay)
