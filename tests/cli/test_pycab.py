#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The pycab command line and its main-thread cab control panel host.

Headless throughout: no window is ever opened, and the screen is never measured except
through a stand-in. The argument surface is exercised through the parser alone, main
against a stand-in PyCabCli, and PyCabPanelGui with its base constructor skipped, exactly
as tests/cli/test_lcs.py does for pylcs.
"""

from __future__ import annotations

from queue import Queue
from threading import Event, Thread
from types import SimpleNamespace

import pytest

import src.pytrain.cli.pycab as mod
from src.pytrain.cli.pycab import (
    DESIGN_HEIGHT,
    DESIGN_SCALE_BY,
    DESIGN_WIDTH,
    PyCabCli,
    PyCabGuiCmd,
    PyCabPanelGui,
    Screen,
    main,
)
from src.pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope

# The work area of a 5120x2880 iMac set to "looks like 2560x1440", as Tk reports it: the
# screen less the menu bar and the Dock. The one measurement these tests are anchored to.
IMAC = Screen(2560, 1289, "aqua")
# The same work area with someone else drawing it. A window is only held to a share of the
# screen on the macOS desktop, so this is the pairing that shows what the share costs.
X11_DESKTOP = Screen(2560, 1289, "x11")


#
# Argument parsing
#
def test_parser_leaves_the_window_unsized_so_it_can_be_fitted_to_the_display() -> None:
    # None rather than 800x1280: the panel's design size is the Pi's touchscreen, and what
    # suits a desktop display is not known until the display has been measured. Sizing is
    # window_geometry's job, below, and defaulting here would take it away.
    args = PyCabCli.command_parser().parse_args([])

    assert args.width is None
    assert args.height is None
    assert args.scale_by is None
    assert args.full_screen is False
    assert args.client is False
    assert args.server is None
    assert args.base is None
    assert args.port == DEFAULT_PORT
    assert args.baudrate == DEFAULT_BAUDRATE


@pytest.mark.parametrize(
    "cmd_line, attribute, expected",
    [
        (["-client"], "client", True),
        (["-server", "10.0.0.5"], "server", "10.0.0.5"),
        (["-base", "10.0.0.9"], "base", "10.0.0.9"),
        (["-width", "600"], "width", 600),
        (["-height", "900"], "height", 900),
        (["-scale_by", "1.5"], "scale_by", 1.5),
        (["-full_screen"], "full_screen", True),
    ],
)
def test_parser_accepts_each_connection_and_window_option(cmd_line, attribute, expected) -> None:
    args = PyCabCli.command_parser().parse_args(cmd_line)

    assert getattr(args, attribute) == expected


def test_the_help_renders_rather_than_raising_on_its_own_text() -> None:
    # argparse runs every help string through %-formatting, so a literal percent sign in one
    # is read as a conversion and takes `pycab -h` down with a TypeError -- which is exactly
    # what writing the macOS share of the screen as a percentage did.
    help_text = PyCabCli.command_parser().format_help()

    assert "-width" in help_text
    assert str(DESIGN_WIDTH) in help_text


#
# The window the panel opens in
#
def test_the_shape_helpers_keep_the_panel_proportioned_as_the_pi_draws_it() -> None:
    # 5:8 portrait, whichever dimension is the one in hand.
    assert mod.portrait_height(DESIGN_WIDTH) == DESIGN_HEIGHT
    assert mod.portrait_width(DESIGN_HEIGHT) == DESIGN_WIDTH
    assert mod.portrait_height(520) == 832
    assert mod.portrait_width(832) == 520


@pytest.mark.parametrize(
    "width, expected",
    [
        (DESIGN_WIDTH, DESIGN_SCALE_BY),
        (640, 1.2),
        (400, mod.MIN_SCALE_BY),
        (200, mod.MIN_SCALE_BY),
        (1600, DESIGN_SCALE_BY),
    ],
    ids=["the-design-pairing", "proportional", "at-the-floor", "below-the-floor", "above-the-cap"],
)
def test_the_text_scale_tracks_the_width_from_the_pis_pairing(width, expected) -> None:
    # Boxes and images follow the width, text follows scale_by alone, so a width without a
    # scale to match is text jammed into smaller cells. Capped at the design factor, since a
    # window wider than the Pi's panel is no reason to draw text larger than the Pi does.
    assert mod.scale_for(width) == pytest.approx(expected)


def test_the_window_is_the_largest_of_that_shape_the_work_area_holds() -> None:
    # 1289 pt of work area, less a 32 pt title bar and the margin, is 1241 pt of window --
    # which is the whole point: 1280 plus a title bar does not fit, so asking for the Pi's
    # geometry verbatim is what ran the panel off the bottom of the screen.
    assert mod.fit_to_screen(X11_DESKTOP) == (776, 1241)


def test_the_macos_window_takes_only_its_share_of_the_work_area() -> None:
    # The fitted window above stands 1273 pt tall with its title bar against a 1289 pt work
    # area, which is a window that owns the screen -- and on a desktop the panel is a window
    # among windows. Four fifths of 1289 is 1031, less the title bar and the margin: 983 pt,
    # which is 1015 with the chrome and leaves a quarter of the screen's height clear.
    assert mod.fit_to_screen(IMAC) == (614, 983)
    assert mod.AQUA_HEIGHT_FRACTION == 0.8


def test_a_display_with_room_to_spare_gets_exactly_what_the_pi_gets() -> None:
    # The panel is not drawn to grow, so a big desktop display is not an invitation to --
    # not even with a share of it to spend.
    assert mod.fit_to_screen(Screen(3840, 2112, "x11")) == (DESIGN_WIDTH, DESIGN_HEIGHT)
    assert mod.fit_to_screen(Screen(3840, 2112, "aqua")) == (DESIGN_WIDTH, DESIGN_HEIGHT)


def test_a_work_area_narrower_than_it_is_tall_binds_the_width_instead() -> None:
    # Only the height is fitted first; a narrow screen has to bring the width back down and
    # the height with it, or the window would hang off the side.
    assert mod.fit_to_screen(Screen(600, 2000, "x11")) == (584, 934)


def test_the_window_stops_shrinking_where_the_layout_stops_shrinking() -> None:
    # GuiZeroBase.scale() clamps at 480 and ignores scale_by at or below it, so a smaller
    # window would clip the panel rather than scale it. Better too tall than unusable, which
    # is also why the macOS share is a ceiling and not a promise.
    floor = (mod.MIN_WIDTH, mod.portrait_height(mod.MIN_WIDTH))

    assert mod.fit_to_screen(Screen(1024, 600, "x11")) == floor
    assert mod.fit_to_screen(Screen(1920, 1055, "aqua")) == floor


def test_an_unsized_window_is_fitted_to_the_screen_and_scaled_to_the_fit() -> None:
    width, height, scale_by = mod.window_geometry(usable=IMAC)

    assert (width, height) == (614, 983)
    assert scale_by == pytest.approx(1.15125)


def test_a_width_on_its_own_settles_both_the_height_and_the_scale() -> None:
    # The one dial worth having: 520 wide is about the physical size of the Pi's panel on a
    # desktop display, and it comes out proportioned the same way rather than as the Pi's
    # text in a two-thirds-size window. A width given is a width honored -- the share of the
    # screen is what to open at unasked, not a cap on what can be asked for.
    width, height, scale_by = mod.window_geometry(520, usable=IMAC)

    assert (width, height) == (520, 832)
    assert scale_by == pytest.approx(0.975)

    assert mod.window_geometry(DESIGN_WIDTH, usable=IMAC)[:2] == (DESIGN_WIDTH, DESIGN_HEIGHT)


def test_a_height_on_its_own_settles_the_width() -> None:
    assert mod.window_geometry(None, 900, usable=IMAC)[:2] == (562, 900)


def test_what_was_asked_for_is_honored_and_the_screen_left_unmeasured(monkeypatch) -> None:
    # Measuring the screen costs a Tk root, and a size given on the command line is not a
    # request for a second opinion about it.
    monkeypatch.setattr(mod, "usable_screen", lambda: pytest.fail("the screen was measured anyway"))

    assert mod.window_geometry(600, 900, 1.1) == (600, 900, 1.1)
    assert mod.window_geometry(600)[:2] == (600, 960)


def test_no_display_to_measure_leaves_the_design_size(monkeypatch) -> None:
    # As over ssh, or on a headless build: nothing to fit to, so the panel's own geometry.
    monkeypatch.setattr(mod, "usable_screen", lambda: None)

    assert mod.window_geometry() == (DESIGN_WIDTH, DESIGN_HEIGHT, DESIGN_SCALE_BY)


def test_the_screen_measurement_reports_nothing_rather_than_failing(monkeypatch) -> None:
    # tkinter raises when there is no display to open, and a cab panel that cannot measure
    # the screen still has a size it can open at.
    def no_display():
        raise mod.TclError("no display name and no $DISPLAY environment variable")

    monkeypatch.setattr(mod.tk, "Tk", no_display)

    assert mod.usable_screen() is None


def test_the_screen_measurement_is_capped_by_the_screen_itself(monkeypatch) -> None:
    # An X11 window manager that publishes no work area answers with the screen, or with
    # more than the screen; either way a window cannot occupy what is not there.
    class FakeRoot:
        destroyed = False

        def withdraw(self) -> None:
            pass

        def wm_maxsize(self) -> tuple[int, int]:
            return 4000, 4000

        def winfo_screenwidth(self) -> int:
            return 1920

        def winfo_screenheight(self) -> int:
            return 1080

        def destroy(self) -> None:
            FakeRoot.destroyed = True

        # Tk answers for the windowing system itself, which beats guessing from sys.platform:
        # XQuartz on a Mac draws x11 windows, and those are not held to the macOS share.
        tk = SimpleNamespace(call=lambda *_args: "x11")

    monkeypatch.setattr(mod.tk, "Tk", FakeRoot)

    assert mod.usable_screen() == Screen(1920, 1080, "x11")
    assert mod.usable_screen().is_aqua is False
    # The root is a means to a measurement, and leaving one behind would leave Tk
    # initialized in a process that has yet to build its window.
    assert FakeRoot.destroyed is True


# The window options are settled in the constructor, which is what is being skipped here.
# noinspection PyProtectedMember
def test_the_cli_settles_the_window_from_the_arguments_it_was_given() -> None:
    cli = object.__new__(PyCabCli)
    cli._args = SimpleNamespace(width=640, height=None, scale_by=None)

    assert cli._window_options() == (640, 1024, 1.2)


#
# main
#
def test_main_returns_zero_and_passes_its_arguments_through(monkeypatch) -> None:
    seen: dict = {}

    class FakeCli:
        def __init__(self, cmd_line=None) -> None:
            seen["cmd_line"] = cmd_line

    monkeypatch.setattr(mod, "PyCabCli", FakeCli, raising=True)

    assert main(["-client"]) == 0
    assert seen["cmd_line"] == ["-client"]


def test_main_reads_sys_argv_when_given_nothing(monkeypatch) -> None:
    seen: dict = {}

    class FakeCli:
        def __init__(self, cmd_line=None) -> None:
            seen["cmd_line"] = cmd_line

    monkeypatch.setattr(mod, "PyCabCli", FakeCli, raising=True)
    monkeypatch.setattr(mod.sys, "argv", ["cabp", "-base", "10.0.0.9"], raising=False)

    assert main() == 0
    assert seen["cmd_line"] == ["-base", "10.0.0.9"]


def test_main_exits_rather_than_raising_when_the_cli_fails(monkeypatch) -> None:
    class FakeCli:
        # cmd_line goes unread here because construction fails, but the name has to stay:
        # main passes it by keyword, and a fake that did not accept it would raise a
        # TypeError instead of the failure this test is about.
        # noinspection PyUnusedLocal,unused-parameter
        def __init__(self, cmd_line=None) -> None:
            raise RuntimeError("no base")

    monkeypatch.setattr(mod, "PyCabCli", FakeCli, raising=True)

    with pytest.raises(SystemExit):
        main(["-client"])


#
# The command: window construction, no requests
#
class FakeGui:
    """Stands in for PyCabPanelGui: records how it was constructed and returns from its loop at once."""

    instances: list["FakeGui"] = []

    def __init__(self, width=None, height=None, scale_by=None, full_screen=None, scope=None) -> None:
        self.width = width
        self.height = height
        self.scale_by = scale_by
        self.full_screen = full_screen
        self.scope = scope
        self.run_window_calls = 0
        FakeGui.instances.append(self)

    def run_window(self) -> None:
        self.run_window_calls += 1


# The command's own internals, set by hand because its constructor is what is being skipped.
# noinspection PyProtectedMember
def _command_for(cli) -> PyCabGuiCmd:
    """A PyCabGuiCmd without the PyTrain bring-up its constructor performs."""
    cmd = object.__new__(PyCabGuiCmd)
    cmd._cli = cli
    cmd._scope = CommandScope.ENGINE
    cmd._gui = None
    cmd._pytrain = None
    # is_synchronized() is False with no PyTrain, so wait_for_sync waits on this event.
    cmd._sc = Event()
    cmd._sc.set()
    return cmd


def test_send_opens_the_window_with_the_requested_geometry_and_runs_its_loop(monkeypatch) -> None:
    FakeGui.instances.clear()
    monkeypatch.setattr(mod, "PyCabPanelGui", FakeGui, raising=True)
    cli = SimpleNamespace(gui_width=600, gui_height=900, scale_by=1.5, is_full_screen=True)

    cmd = _command_for(cli)
    cmd.send()

    assert len(FakeGui.instances) == 1
    gui = FakeGui.instances[0]
    assert (gui.width, gui.height, gui.scale_by, gui.full_screen) == (600, 900, 1.5, True)
    assert gui.scope == CommandScope.ENGINE
    assert gui.run_window_calls == 1
    assert cmd.gui is gui


def test_send_waits_for_sync_and_shuts_pytrain_down_afterwards(monkeypatch) -> None:
    FakeGui.instances.clear()
    monkeypatch.setattr(mod, "PyCabPanelGui", FakeGui, raising=True)
    calls: list[str] = []

    cmd = _command_for(
        SimpleNamespace(gui_width=DESIGN_WIDTH, gui_height=DESIGN_HEIGHT, scale_by=1.0, is_full_screen=False)
    )
    cmd._pytrain = SimpleNamespace(shutdown=lambda: calls.append("shutdown"))
    monkeypatch.setattr(
        PyCabGuiCmd, "wait_for_sync", lambda self, *a, **k: calls.append("wait_for_sync"), raising=False
    )

    cmd.send()

    assert calls == ["wait_for_sync", "shutdown"]
    assert FakeGui.instances[0].run_window_calls == 1


def test_send_builds_no_requests() -> None:
    cmd = _command_for(SimpleNamespace())

    assert cmd._build_command() is None
    assert cmd._command_prefix() is None
    assert cmd._encode_address(0) is None


#
# The main-thread host
#
# noinspection PyProtectedMember
def _host() -> PyCabPanelGui:
    """A PyCabPanelGui with the GuiZeroBase bring-up its constructor performs skipped."""
    gui = object.__new__(PyCabPanelGui)
    gui._message_queue = Queue()
    gui._app = None
    gui.title = "Engine GUI"
    return gui


# noinspection PyProtectedMember
def test_start_queues_the_title_update_rather_than_spawning_the_tk_thread() -> None:
    gui = _host()

    gui.start()

    message, args = gui._message_queue.get_nowait()
    assert message == gui._on_synchronized
    assert args == ()
    # Nothing was queued twice, and no thread was started: the Tk loop is run_window's.
    assert gui._message_queue.empty()


def test_on_synchronized_applies_the_title_once_the_app_exists() -> None:
    gui = _host()

    # Before the App is built there is nothing to title, and this must not raise.
    gui._on_synchronized()

    gui._app = SimpleNamespace(title=None)
    gui._on_synchronized()

    assert gui._app.title == gui.title


def test_run_window_refuses_to_own_the_tk_loop_off_the_main_thread() -> None:
    gui = _host()
    failure: list[BaseException] = []

    def run() -> None:
        try:
            gui.run_window()
        except BaseException as e:
            failure.append(e)

    thread = Thread(target=run, name="not the main thread")
    thread.start()
    thread.join()

    assert isinstance(failure[0], RuntimeError)


def test_run_window_runs_the_inherited_loop_on_the_main_thread(monkeypatch) -> None:
    gui = _host()
    calls: list[str] = []
    monkeypatch.setattr(PyCabPanelGui, "run", lambda self: calls.append("run"), raising=False)

    gui.run_window()

    assert calls == ["run"]


#
# The info row the engine image used to be measured without
#
def _host_with_info_row(reqheight) -> PyCabPanelGui:
    """A host whose controller info row answers with the given height, or raises."""

    def measure() -> int:
        if isinstance(reqheight, BaseException):
            raise reqheight
        return reqheight

    gui = _host()
    gui._controller_view = SimpleNamespace(
        controller_info_box=SimpleNamespace(tk=SimpleNamespace(winfo_reqheight=measure))
    )
    return gui


def test_the_desktop_window_reserves_the_info_rows_own_height() -> None:
    # The row is built while the controller box is hidden, so it is not packed when the
    # image baseline is computed and contributes nothing to what that measures -- the image
    # takes the pixels and ops mode leaves the row clipped. Measured at 776x1241: 72 px
    # asked for, 22 allotted. The row knows its height regardless, so ask it.
    assert _host_with_info_row(72).controller_info_reserve == 72


# The controller view is built partway through build_gui, and the reserve is read at the end
# of it; a host that has not got there yet reserves nothing rather than failing.
# noinspection PyProtectedMember
@pytest.mark.parametrize(
    "view",
    [None, SimpleNamespace(controller_info_box=None)],
    ids=["no-controller-view", "no-info-row"],
)
def test_a_panel_with_no_info_row_yet_reserves_nothing(view) -> None:
    gui = _host()
    gui._controller_view = view

    assert gui.controller_info_reserve == 0


def test_a_row_that_cannot_be_measured_reserves_nothing() -> None:
    # Sizing the image is not the place to bring the panel down over a widget Tk has since
    # forgotten: without the reserve the layout is what it has always been on the Pi.
    assert _host_with_info_row(mod.TclError("bad window path name")).controller_info_reserve == 0
    # Nor is a negative reading something to hand back to the arithmetic.
    assert _host_with_info_row(-5).controller_info_reserve == 0
