#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
A stand-alone window whose whole content is the LCS configuration panel.

This is a thin *host*, not a second GUI. LcsConfigPanel is written against the small
surface OverlayPanel and PopupManager need -- app / root, _popup /
popup_manager, show_popup, locked, cache, state_store,
submit_request, queue_message, the s_* font sizes and button_size -- and
almost all of it already comes from GuiZeroBase. What is added here is the handful of
attributes PopupManager reads off an EngineGui: the content boxes it hides while
a popup is up, the image box it restores afterwards, and the position it places a popup
at. They are all None here, because this window has no content other than the panel
itself.

Keeping the panel behind PopupManager in both hosts is deliberate: the panel code,
its footer styling, and its title row are then identical whether it is opened from
EngineGui or run from the pylcs command line.

Recipe for a stand-alone PyTrain GUI on macOS or Windows
--------------------------------------------------------
GuiZeroBase is a Thread and normally builds its guizero App inside its own thread
body, which the sync watcher starts. That is legal under X11 on the Pi, but macOS Aqua
requires every NSWindow on the process main thread, so Tk aborts the process with
NSInternalInconsistencyException. A stand-alone entry point must therefore:

1. Construct the host on the process **main** thread.
2. Always pass explicit width and height, so the throwaway screen-measuring
   tkinter.Tk() in GuiZeroBase.__init__ is never built.
3. Override Thread.start() so the sync watcher cannot spawn the Tk thread; it should
   only record synchronization and hand it off through queue_message.
4. Call the inherited run() from the main thread -- see LcsGui.run_window() -- so the
   App, build_gui(), and app.display() all happen there.
5. Marshal **every** cross-thread update through queue_message, which _poll_shutdown
   drains on the Tk thread; a message queued before the app exists simply waits.
"""

from __future__ import annotations

import logging
from threading import current_thread, main_thread
from typing import Any

from guizero import App, Box

from .lcs_config_panel import LcsConfigPanel
from .popup_manager import PopupManager
from ..guizero_base import GuiZeroBase
from ...protocol.constants import PROGRAM_NAME

log = logging.getLogger(__name__)

LCS_GUI_TITLE = f"{PROGRAM_NAME} LCS Configuration"

# The portrait EngineGui overlay's own proportions, so a desktop run is laid out like the
# embedded panel rather than stretched across a full-screen desktop window.
DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 800


class LcsGui(GuiZeroBase):
    """
    Hosts LcsConfigPanel as the entire content of its own window.
    """

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        scale_by: float = 1.0,
        stand_alone: bool = True,
        full_screen: bool = False,
        x_offset: int = 0,
        y_offset: int = 0,
        button_divisor: float = 6.0,
    ) -> None:
        super().__init__(
            title=LCS_GUI_TITLE,
            width=width or DEFAULT_WIDTH,
            height=height or DEFAULT_HEIGHT,
            scale_by=scale_by,
            stand_alone=stand_alone,
            full_screen=full_screen,
            x_offset=x_offset,
            y_offset=y_offset,
            button_divisor=button_divisor,
        )
        # A stand-alone window is never the compact Deck pane.
        self._compact = False

        # The EngineGui surface PopupManager reads. Nothing but the panel is ever on
        # screen here, so every content box is absent by construction.
        self.controller_box: Box | None = None
        self.keypad_box: Box | None = None
        self.amc2_ops_box: Box | None = None
        self.sensor_track_box: Box | None = None
        self.image_box: Box | None = None
        self._acc_overlay: Box | None = None
        self.popup_position: tuple[int, int] = (0, 0)
        self.emergency_box_width: int = self.width

        self._popup: PopupManager = PopupManager(self)
        self._panel: LcsConfigPanel | None = None
        self._overlay: Box | None = None

        # tell GuiZeroBase we have set up our variables and are ready to proceed
        self.init_complete()

    #
    # Host surface
    #
    @property
    def root(self) -> App | Box:
        return self.app

    @property
    def compact(self) -> bool:
        return self._compact

    @property
    def popup_manager(self) -> PopupManager:
        return self._popup

    @property
    def acc_overlay(self) -> Box | None:
        return self._acc_overlay

    @property
    def panel(self) -> LcsConfigPanel | None:
        return self._panel

    def show_popup(
        self,
        overlay,
        op: str = None,
        modifier: str = None,
        button: Any = None,
        position: tuple = None,
        hide_image_box: bool = False,
    ) -> None:
        self._popup.show(
            overlay=overlay,
            op=op,
            modifier=modifier,
            button=button,
            position=position,
            hide_image_box=hide_image_box,
        )

    def calc_image_box_size(self) -> tuple[int, int]:
        """No image is ever presented here; the panel occupies the whole window."""
        return int(self.height / 2), self.width

    #
    # Lifecycle
    #
    def build_gui(self) -> None:
        self._panel = LcsConfigPanel(self, post_close=self._on_panel_closed)
        self._overlay = self._panel.overlay
        # Nothing is selected in a stand-alone run, so the panel opens on its device page
        # with the default base ID, exactly as it does when opened with no active state.
        self._panel.configure()
        # A window opened ahead of synchronization says so and holds Configure back; one
        # opened after the store is loaded shows nothing out of the ordinary.
        self._panel.set_sync_pending(not self.is_synchronized)
        self.show_popup(self._overlay)

    def _on_panel_closed(self, _overlay: Box) -> None:
        """Dismissing the panel here dismisses the program: the panel is the whole window.

        Embedded in EngineGui closing the popup uncovers the GUI underneath, so no
        post-close action is passed there. Here there is nothing underneath, and hiding the
        overlay on its own would leave an empty white frame with no way back.

        close() is exactly what the window's own title bar does -- GuiZeroBase.run sets
        App.when_closed to it -- so the Close button the Pi and the Steam Deck show (see
        needs_close_button()) ends the run the same way the title bar ends it on a desktop,
        which is why a desktop needs no such button.
        """
        self.close()

    def destroy_gui(self) -> None:
        self._panel = None
        self._overlay = None

    #
    # Main-thread ownership of the Tk event loop
    #
    def start(self) -> None:
        """Deliberately does NOT start a thread.

        GuiZeroBase._on_initial_sync calls this from the sync watcher's thread. On macOS a
        window built on that thread aborts the process, so the Tk loop is owned by whoever
        called run_window() -- the process main thread -- and this only reports that the
        Base 3 is now synchronized.
        """
        self.queue_message(self._on_synchronized)

    def run_window(self) -> None:
        """Own the Tk event loop on the calling thread, which must be the main thread."""
        if current_thread() is not main_thread():
            raise RuntimeError("LcsGui.run_window() must be called on the main thread")
        self.run()

    def _on_synchronized(self) -> None:
        """On the Tk thread: apply the title, then let the panel refresh what it reads."""
        if self.app is not None:
            self.app.title = self.title
        if self._panel is not None:
            self._panel.on_synchronized()

    @property
    def is_synchronized(self) -> bool:
        """GuiZeroBase keeps _synchronized private and exposes no such property."""
        if self._synchronized:
            return True
        return self._sync_state is not None and self._sync_state.is_synchronized()
