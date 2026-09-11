#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
pycab: open the cab control panel (EngineGui) in its own window.

Follows the pylcs pattern exactly: a CliBase subclass parses the arguments, and a
CommandBase subclass brings PyTrain up as a client, against a named server, or directly
against a Base 3, then runs the GUI. No requests are built here -- the panel itself is
what sends anything, through the GUI's own request queue.

The window sizes itself to the display it opens on rather than to the Pi's touchscreen;
see window_geometry, and DESIGN_WIDTH for why a fixed 800x1280 does not travel.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from argparse import ArgumentParser
from threading import current_thread, main_thread
from tkinter import TclError
from typing import List, NamedTuple

from ..gui.controller.engine_gui import EngineGui
from ..protocol.command_base import CommandBase
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope
from ..utils.argument_parser import PyTrainArgumentParser
from . import CliBase

log = logging.getLogger(__name__)

# The portrait geometry the cab panel is drawn for, and the largest window worth opening --
# not a size that suits every display. The layout is proportioned around this pairing:
# boxes and images follow the width (button_size = width / 6, EngineGui.scope_size =
# width / 5), every text size follows scale_by alone, and the Pi runs 800 wide at
# scale_by 1.5 (see make_gui's control_panel). Asking for it verbatim on a desktop is what
# does not travel: on macOS a window's width and height are points, not pixels, so on a
# 5120x2880 iMac set to "looks like 2560x1440" a 1280 pt window plus a title bar wants more
# vertical room than the 1289 pt work area has, and lands as 2240 real pixels of a
# 2520 pixel panel. Hence: fit the window to the screen, keep this 5:8 shape, and take
# scale_by from the width that results.
DESIGN_WIDTH = 800
DESIGN_HEIGHT = 1280
DESIGN_SCALE_BY = 1.5

# The smallest window the panel is still proportioned for: GuiZeroBase.scale() clamps at
# 480 (max(orig_value, value * width / 480)) and stops applying scale_by at or below it, so
# a narrower window no longer shrinks the layout -- it only clips it.
MIN_WIDTH = 520
MIN_SCALE_BY = 0.75

# What a window costs beyond the size asked for, and how much screen to leave alone. The
# title bar is measured under Aqua: asked for +0+0, Tk reports the frame at y=30, below the
# menu bar, with the client area starting at y=62. X11 and Windows title bars are of the
# same order, and the margin absorbs the difference either way.
TITLE_BAR_HEIGHT = 32
SCREEN_MARGIN = 16

# How much of the work area the window may take on the macOS desktop. Filling it is what a
# touchscreen panel does and what a desktop window should not: the whole work area is
# 1289 pt on the 2560x1440 iMac above, so a window fitted to it stands 1273 pt tall with its
# title bar and reads as owning the screen -- and the panel is a window among windows there,
# not the display. Four fifths leaves a quarter of the screen's height clear and lands the
# panel at about the physical size of the Pi's 8 in touchscreen. Aqua only: X11 desktops keep
# the fitted size, and the Pi's control panel does not come through here at all (make_gui
# builds EngineGui directly, full screen, and never passes a width).
AQUA_HEIGHT_FRACTION = 0.8

# What the panel's buttons are sized against: button_size = width / this, and the ops keypad's
# speed slider is four of them tall. The Pi divides by 6, which puts a finger-sized key on an
# 8 in touchscreen; a desktop window is worked with a mouse, and its keys can be smaller than a
# fingertip. What that buys is the picture above them, which is the residual once every other
# row has taken its height: measured at 631x1009, the ops keypad falls from 607px to 477 and
# the engine image strip rises from 91px to 221, which is the difference between a locomotive
# drawn as a stripe and one drawn as a locomotive. The Steam Deck divides its own pane by 8 for
# a related reason, so this is the value the project already trusts a smaller key at.
DESKTOP_BUTTON_DIVISOR = 8.0

# Raised by Tk when there is no display to ask about, as on a headless server or over ssh.
SCREEN_QUERY_EXCEPTIONS = (RuntimeError, TclError)


class Screen(NamedTuple):
    """What a display offers a window: its work area, and who is drawing it."""

    width: int
    height: int
    windowing_system: str = ""

    @property
    def is_aqua(self) -> bool:
        """True on the macOS desktop, and false under X11 -- including XQuartz on a Mac."""
        return self.windowing_system == "aqua"


def portrait_height(width: int) -> int:
    """The height that keeps the panel's shape at a given width."""
    return int(round(width * DESIGN_HEIGHT / DESIGN_WIDTH))


def portrait_width(height: int) -> int:
    """The width that keeps the panel's shape at a given height."""
    return int(round(height * DESIGN_WIDTH / DESIGN_HEIGHT))


def scale_for(width: int) -> float:
    """The text scale that pairs with a window width, from the Pi's 800 at 1.5.

    Sizes are split between the two dials, so turning the width alone leaves text jammed
    into smaller cells, or swimming in larger ones. Capped at the design factor, since a
    window wider than the Pi's panel is a desktop convenience and no reason to draw text
    larger than the panel ever draws it; floored so a deliberately tiny window keeps text
    that can still be read.
    """
    return min(DESIGN_SCALE_BY, max(MIN_SCALE_BY, width * DESIGN_SCALE_BY / DESIGN_WIDTH))


def fit_to_screen(screen: Screen) -> tuple[int, int]:
    """The largest window of the panel's shape worth opening on a given screen.

    Never larger than the design size: the panel is not drawn to grow, and a desktop
    display big enough to hold it gets exactly what the Pi's touchscreen gets. On the macOS
    desktop, never larger than its share of the work area either; see AQUA_HEIGHT_FRACTION.
    """
    budget = int(screen.height * AQUA_HEIGHT_FRACTION) if screen.is_aqua else screen.height
    height = min(DESIGN_HEIGHT, budget - TITLE_BAR_HEIGHT - SCREEN_MARGIN)
    width = portrait_width(height)
    if width > screen.width - SCREEN_MARGIN:
        # A screen shorter than it is narrow, or one turned portrait: the width is what
        # binds, and the height follows it back down.
        width = screen.width - SCREEN_MARGIN
        height = portrait_height(width)
    if width < MIN_WIDTH:
        # Nothing sensible is left to give up: past here the layout stops shrinking, so a
        # window that fit the screen would clip the panel rather than scale it.
        return MIN_WIDTH, portrait_height(MIN_WIDTH)
    return width, height


def usable_screen() -> Screen | None:
    """The screen area a window may occupy, in Tk pixels -- points, under Aqua.

    wm maxsize is what Tk makes of the platform's work area: the screen less the menu bar
    and the Dock on macOS, less panels and docks on X11. Measured (2560, 1289) against a
    2560x1440 screen on the iMac above. Read from a throwaway root that is never mapped, so
    nothing appears on screen, and None where there is no display to ask -- in which case
    the caller is left with the design size. The windowing system comes from the same root,
    as Tk sees it rather than as the platform is guessed at.
    """
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        width, height = root.wm_maxsize()
        # An X11 window manager that reports no work area answers with the screen itself, or
        # with something larger still; the screen is the ceiling either way.
        return Screen(
            min(width, root.winfo_screenwidth()),
            min(height, root.winfo_screenheight()),
            root.tk.call("tk", "windowingsystem"),
        )
    except SCREEN_QUERY_EXCEPTIONS as e:
        log.info(f"Cannot measure the screen, opening the cab panel at {DESIGN_WIDTH}x{DESIGN_HEIGHT}: {e}")
        return None
    finally:
        if root is not None:
            try:
                root.destroy()
            except TclError:
                pass


def window_geometry(
    width: int | None = None,
    height: int | None = None,
    scale_by: float | None = None,
    usable: Screen | None = None,
) -> tuple[int, int, float]:
    """Settle the window size and text scale, filling in whatever was not asked for.

    Neither dimension given: fit the screen. One of them given: the other keeps the panel's
    shape, which is what makes the width a single dial -- `-width 520` opens the window at
    about the physical size of the Pi's 8 in panel on a desktop display, proportioned the
    same way. Both given: both are honored, screen or no screen. The scale follows whatever
    width is in force, unless -scale_by named one.
    """
    if width is None and height is None:
        usable = usable if usable is not None else usable_screen()
        width, height = fit_to_screen(usable) if usable else (DESIGN_WIDTH, DESIGN_HEIGHT)
    elif height is None:
        height = portrait_height(width)
    elif width is None:
        width = portrait_width(height)
    return width, height, scale_by if scale_by is not None else scale_for(width)


class PyCabPanelGui(EngineGui):
    """
    EngineGui that owns the Tk event loop on the process main thread.

    GuiZeroBase is a Thread, and the sync watcher normally starts it, building the
    guizero App inside that thread. macOS Aqua requires every NSWindow on the process
    main thread, so a stand-alone run must keep Tk where it was started from; see the
    recipe in lcs_gui, which LcsGui follows for the same reason.

    It is also where the panel is drawn smaller than the touchscreen it was laid out for,
    which is what the overrides below are: a window on a desk is a window among windows,
    and shorter than the Pi's screen without its contents being proportionally shorter.
    """

    def __init__(self, *args, button_divisor: float = DESKTOP_BUTTON_DIVISOR, **kwargs) -> None:
        # Defaulted here rather than passed by the caller: the smaller key belongs to this
        # window, not to one way of opening it, so anything that builds the desktop panel --
        # the CLI, a probe -- gets the same panel. See DESKTOP_BUTTON_DIVISOR.
        super().__init__(*args, button_divisor=button_divisor, **kwargs)

    @property
    def preserve_image_aspect(self) -> bool:
        """True: draw the picture at its own proportions rather than filling the strip.

        The strip here is short -- the residual after every other row, and this window has
        fewer pixels to leave over than the Pi's screen -- so filling its width is what turned
        a 3:1 locomotive into a 6.9:1 stripe. Costing nothing where the picture would have
        filled the width anyway, which is the roomy case; see GuiZeroBase._fit_image_size.
        """
        return True

    def fit_popup_title_height(self, measured_height: int, required_height: int) -> int:
        """Whichever is larger: a title row built from the key size, or the title in it.

        The two are the same number on a panel drawn as it was laid out, and this window is
        not -- its keys are smaller than the Pi's while its fonts are only smaller in
        proportion to the window, so a row of button_size // 3 per line came out 52px for a
        70px two-line title and cut the version off the admin panel's heading. Costing the
        panel below it the difference, which is why it is the row's height rather than the
        title's size that gives way: a heading half drawn is worse than a panel 18px shorter.
        """
        return max(measured_height, required_height)

    @property
    def popup_may_cover_info_box(self) -> bool:
        """True: a panel that will not fit may have the ID/road-name row's height.

        The admin panel is the one that asks -- 787px of the 720 this window leaves below that
        row, where the Pi's screen leaves it 941 for the 931 it asks there -- and what it lost
        was its Close button, clipped to 3px of the 58 it wanted. The row names whatever the
        pane had selected, which is nothing the admin panel is about. See
        PopupManager._make_room_for, which hides it only for a panel that really does not fit.
        """
        return True

    @property
    def controller_info_reserve(self) -> int:
        """Hold the controller's info row out of what the engine image is measured against.

        The row -- Mom, Brake, Smoke, Speed Lim, Effort, RPM -- is built while the
        controller box is hidden, so it is not packed when the image baseline is computed
        and none of its height is reserved; the image takes those pixels, and ops mode
        leaves the row clipped to whatever slack is left. Measured on this panel at
        776x1241: the row asks for 72 px and is allotted 22. The row knows its own height
        by then, packed or not, so reserve it and let the image be the residual it already
        is. Desktop window only: the Pi's control panel and the Steam Deck build EngineGui
        themselves and keep the default of 0.
        """
        view = self.controller_view
        row = view.controller_info_box if view is not None else None
        if row is None:
            return 0
        try:
            return max(0, row.tk.winfo_reqheight())
        except TclError:
            return 0

    def start(self) -> None:
        """Deliberately does NOT start a thread.

        GuiZeroBase._on_initial_sync calls this from the sync watcher's thread. The Tk
        loop belongs to whoever called run_window() -- the process main thread -- so all
        this does is hand the newly applied title off to that thread.
        """
        self.queue_message(self._on_synchronized)

    def run_window(self) -> None:
        """Own the Tk event loop on the calling thread, which must be the main thread."""
        if current_thread() is not main_thread():
            raise RuntimeError("PyCabPanelGui.run_window() must be called on the main thread")
        self.run()

    def _on_synchronized(self) -> None:
        """On the Tk thread: apply the title _on_initial_sync took from the Base 3."""
        if self.app is not None:
            self.app.title = self.title


class PyCabGuiCmd(CommandBase):
    """
    Run the stand-alone cab control panel window.

    A special case of CommandBase where no requests are created nor sent: PyTrain
    initialization is all that is wanted from it.
    """

    def __init__(self, cli: PyCabCli) -> None:
        self._cli = cli
        self._scope: CommandScope = cli.scope
        self._gui = None

        # with PyTrain initialization sorted out, initialize CommandBase.
        # If we are stand-alone, set daemon to False, as we need the process to continue running.
        CommandBase.__init__(
            self,
            None,
            None,
            1,
            scope=self._scope,
            server=self._cli.args.server if "server" in self._cli.args else None,
            client=self._cli.args.client if "client" in self._cli.args else False,
            base=self._cli.args.base if "base" in self._cli.args else None,
            cache_sync=True,
        )
        self._command = self._build_command()

    @property
    def scope(self) -> CommandScope:
        return self._cli.scope

    @property
    def gui(self):
        return self._gui

    # noinspection PyTypeChecker
    def send(
        self,
        repeat: int = None,
        delay: float = None,
        duration: float = None,
        interval: int = None,
        shutdown: bool = False,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ):
        # pause until Base 3 sync complete: the panel is built from the component state
        # store, so it has to be loaded before the window is laid out.
        self.wait_for_sync()

        log.info(
            f"Opening cab control panel window "
            f"({self._cli.gui_width}x{self._cli.gui_height}, scale_by {self._cli.scale_by:.2f})..."
        )
        self._gui = PyCabPanelGui(
            width=self._cli.gui_width,
            height=self._cli.gui_height,
            scale_by=self._cli.scale_by,
            full_screen=self._cli.is_full_screen,
            scope=self._scope,
        )
        # The Tk event loop must own the process main thread; macOS aborts on an NSWindow
        # built anywhere else. This blocks here until the window is closed.
        self._gui.run_window()
        if self.pytrain is not None:
            self.pytrain.shutdown()

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class PyCabCli(CliBase):
    """
    Cab control panel window
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        parser = PyTrainArgumentParser(add_help=False)
        # Each of the three is left unset rather than defaulted, as what makes a sensible
        # value depends on the display and on the others; see window_geometry.
        parser.add_argument(
            "-width",
            action="store",
            type=int,
            # No percent sign in any of these: argparse runs a help string through
            # %-formatting, so a literal % is read as a conversion and raises.
            help=f"Window width, in pixels (fitted to the screen, at most {DESIGN_WIDTH}, "
            f"and to a share of it on the macOS desktop)",
        )
        parser.add_argument(
            "-height",
            action="store",
            type=int,
            help="Window height, in pixels (proportional to the width)",
        )
        parser.add_argument(
            "-scale_by",
            action="store",
            type=float,
            help="Scale fonts and buttons by this factor (derived from the window width)",
        )
        parser.add_argument(
            "-full_screen",
            action="store_true",
            help="Open the window full screen",
        )

        # Return parser
        return PyTrainArgumentParser("Cab control panel options", parents=[parser, cls.cli_parser()])

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._gui_width, self._gui_height, self._scale_by = self._window_options()
        self._full_screen = self._args.full_screen
        self._scope = CommandScope.ENGINE
        try:
            cmd = PyCabGuiCmd(self)
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)

    def _window_options(self) -> tuple[int, int, float]:
        """The window size and text scale, filling in whatever the arguments left out."""
        return window_geometry(
            self._args.width,
            self._args.height,
            self._args.scale_by,
        )

    @property
    def scope(self) -> CommandScope:
        return CommandScope.ENGINE

    @property
    def gui_width(self) -> int | None:
        return self._gui_width

    @property
    def gui_height(self) -> int | None:
        return self._gui_height

    @property
    def scale_by(self) -> float:
        return self._scale_by

    @property
    def is_full_screen(self) -> bool:
        return self._full_screen


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        PyCabCli(cmd_line=args)
        return 0
    except Exception as e:
        sys.exit(f"{__file__}: error: {e}\n")
