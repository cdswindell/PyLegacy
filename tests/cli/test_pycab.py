#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The cabp command line and its main-thread cab control panel host.

Headless throughout: no window is ever opened. The argument surface is exercised through the
parser alone, main against a stand-in CabpCli, and CabPanelGui with its base constructor
skipped, exactly as tests/cli/test_lcs.py does for pylcs.
"""

from __future__ import annotations

from queue import Queue
from threading import Event, Thread
from types import SimpleNamespace

import pytest

import src.pytrain.cli.pycab as mod
from src.pytrain.cli.pycab import DEFAULT_HEIGHT, DEFAULT_WIDTH, PyCabCli, PyCabGuiCmd, PyCabPanelGui, main
from src.pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope


#
# Argument parsing
#
def test_parser_defaults_to_a_client_on_the_portrait_panel_geometry() -> None:
    args = PyCabCli.command_parser().parse_args([])

    assert args.width == DEFAULT_WIDTH == 800
    assert args.height == DEFAULT_HEIGHT == 1280
    assert args.scale_by == 1.0
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
    """Stands in for CabPanelGui: records how it was constructed and returns from its loop at once."""

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
    """A CabpGuiCmd without the PyTrain bring-up its constructor performs."""
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
        SimpleNamespace(gui_width=DEFAULT_WIDTH, gui_height=DEFAULT_HEIGHT, scale_by=1.0, is_full_screen=False)
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
    """A CabPanelGui with the GuiZeroBase bring-up its constructor performs skipped."""
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
