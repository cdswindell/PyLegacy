#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Headless tests for the pyroutes command line and window lifecycle."""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

import src.pytrain.cli.routes as mod
from src.pytrain.cli.routes import RoutesCli, RoutesGuiCmd, main
from src.pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope


@pytest.fixture
def pytrain(monkeypatch):
    """Replace only CommandBase's hardware initialization, keeping fire and send real."""
    instance = Mock(spec=["shutdown"])
    instance.initializations = []

    def initialize(command, *args, **kwargs):
        instance.initializations.append((args, kwargs))
        command._pytrain = instance
        command._command_req = args[1]

    monkeypatch.setattr(mod.CommandBase, "__init__", initialize)
    return instance


@pytest.fixture
def gui_class(monkeypatch):
    """Keep the CLI tests independent of Tk and the stand-alone GUI implementation."""
    module = ModuleType("src.pytrain.gui.controller.routes_gui")
    module.RoutesGui = Mock(name="RoutesGui")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module.RoutesGui


#
# Argument parsing
#
def test_parser_defaults_to_a_client_with_no_window_overrides() -> None:
    args = RoutesCli.command_parser().parse_args([])

    assert args.width is None
    assert args.height is None
    assert args.scale_by == 1.0
    assert args.full_screen is False
    assert args.client is False
    assert args.server is None
    assert args.base is None
    assert args.port == DEFAULT_PORT
    assert args.baudrate == DEFAULT_BAUDRATE


def test_parser_help_describes_the_default_window_size() -> None:
    help_text = RoutesCli.command_parser().format_help()

    assert "Window width, in pixels (640)" in help_text
    assert "Window height, in pixels (800)" in help_text


@pytest.mark.parametrize(
    "cmd_line, attribute, expected",
    [
        (["-client"], "client", True),
        (["-server", "10.0.0.5"], "server", "10.0.0.5"),
        (["-base", "10.0.0.9"], "base", "10.0.0.9"),
        (["-port", "/dev/ttyUSB1"], "port", "/dev/ttyUSB1"),
        (["-baudrate", "19200"], "baudrate", 19200),
        (["-width", "600"], "width", 600),
        (["-height", "900"], "height", 900),
        (["-scale_by", "1.5"], "scale_by", 1.5),
        (["-full_screen"], "full_screen", True),
    ],
)
def test_parser_accepts_each_connection_and_window_option(cmd_line, attribute, expected) -> None:
    args = RoutesCli.command_parser().parse_args(cmd_line)

    assert getattr(args, attribute) == expected


@pytest.mark.parametrize(
    "cmd_line",
    [
        ["-width", "wide"],
        ["-height", "tall"],
        ["-scale_by", "large"],
        ["-baudrate", "12345"],
        ["-unknown"],
    ],
)
def test_parser_rejects_invalid_options(cmd_line) -> None:
    with pytest.raises(SystemExit) as exc:
        RoutesCli.command_parser().parse_args(cmd_line)

    assert exc.value.code == 2


#
# CLI construction and fire
#
@pytest.mark.parametrize(
    "cmd_line, connection",
    [
        ([], {"server": None, "client": False, "base": None}),
        (["-client"], {"server": None, "client": True, "base": None}),
        (["-server", "10.0.0.5"], {"server": "10.0.0.5", "client": False, "base": None}),
        (["-base", "10.0.0.9"], {"server": None, "client": False, "base": "10.0.0.9"}),
    ],
)
def test_cli_initializes_a_system_command_without_building_requests(cmd_line, connection, pytrain, gui_class) -> None:
    cli = RoutesCli(cmd_line=cmd_line, do_fire=False)

    assert cli.scope == CommandScope.SYSTEM
    assert cli.command.scope == CommandScope.SYSTEM
    assert cli.command.command_req is None
    assert cli.command.command_bytes is None
    assert cli.command.command_prefix is None
    assert cli.command._build_command() is None
    assert cli.command._encode_address(0) is None
    assert cli.command.gui is None
    assert cli.gui_width is None
    assert cli.gui_height is None
    assert cli.scale_by == 1.0
    assert cli.is_full_screen is False
    assert pytrain.initializations == [((None, None, 1), {"scope": CommandScope.SYSTEM, **connection})]
    gui_class.assert_not_called()
    pytrain.shutdown.assert_not_called()


@pytest.mark.parametrize("do_fire", [False, True])
def test_cli_honors_do_fire_and_forwards_connection_options(do_fire, pytrain, monkeypatch) -> None:
    fire = Mock()
    monkeypatch.setattr(RoutesGuiCmd, "fire", fire)

    cli = RoutesCli(cmd_line=["-server", "10.0.0.5", "-port", "/dev/ttyUSB1", "-baudrate", "19200"], do_fire=do_fire)

    assert isinstance(cli.command, RoutesGuiCmd)
    assert cli.do_fire is do_fire
    if do_fire:
        fire.assert_called_once_with(baudrate=19200, port="/dev/ttyUSB1", server="10.0.0.5")
    else:
        fire.assert_not_called()


def test_fire_runs_the_window_synchronously_on_the_main_thread_then_shuts_down(pytrain, gui_class, monkeypatch) -> None:
    calls = []
    gui = gui_class.return_value

    def create_window(**kwargs):
        assert threading.current_thread() is threading.main_thread()
        calls.append("create")
        return gui

    def run_window():
        assert threading.current_thread() is threading.main_thread()
        pytrain.shutdown.assert_not_called()
        calls.append("run_window")

    gui_class.side_effect = create_window
    gui.run_window.side_effect = run_window
    pytrain.shutdown.side_effect = lambda: calls.append("shutdown")
    wait_for_sync = Mock(side_effect=AssertionError("must not wait for synchronization"))
    send = Mock(side_effect=AssertionError("must not send requests"))
    monkeypatch.setattr(RoutesGuiCmd, "wait_for_sync", wait_for_sync)
    monkeypatch.setattr(mod.CommandBase, "send", send)

    cli = RoutesCli(cmd_line=["-client", "-width", "600", "-height", "900", "-scale_by", "1.5", "-full_screen"])

    assert (cli.gui_width, cli.gui_height, cli.scale_by, cli.is_full_screen) == (600, 900, 1.5, True)
    gui_class.assert_called_once_with(width=600, height=900, scale_by=1.5, full_screen=True)
    gui.run_window.assert_called_once_with()
    assert cli.command.gui is gui
    assert calls == ["create", "run_window", "shutdown"]
    pytrain.shutdown.assert_called_once_with()
    wait_for_sync.assert_not_called()
    send.assert_not_called()


@pytest.mark.parametrize("failure_point", ["create", "run_window"])
@pytest.mark.parametrize("error_type", [RuntimeError, ValueError, KeyboardInterrupt])
def test_send_shuts_down_when_window_creation_or_run_fails(failure_point, error_type, pytrain, gui_class) -> None:
    cli = RoutesCli(cmd_line=[], do_fire=False)
    error = error_type("window failed")
    if failure_point == "create":
        gui_class.side_effect = error
    else:
        gui_class.return_value.run_window.side_effect = error

    with pytest.raises(error_type) as exc:
        cli.command.send()

    assert exc.value is error
    pytrain.shutdown.assert_called_once_with()
    if failure_point == "create":
        assert cli.command.gui is None
        gui_class.return_value.run_window.assert_not_called()
    else:
        assert cli.command.gui is gui_class.return_value
        gui_class.return_value.run_window.assert_called_once_with()


def test_gui_import_is_lazy_and_import_failure_still_shuts_down(pytrain, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "src.pytrain.gui.controller.routes_gui", None)

    cli = RoutesCli(cmd_line=[], do_fire=False)
    pytrain.shutdown.assert_not_called()
    with pytest.raises(ModuleNotFoundError):
        cli.command.fire()

    pytrain.shutdown.assert_called_once_with()


def test_send_handles_an_absent_pytrain(pytrain, gui_class) -> None:
    cli = RoutesCli(cmd_line=[], do_fire=False)
    cli.command._pytrain = None

    cli.command.send()

    gui_class.assert_called_once_with(width=None, height=None, scale_by=1.0, full_screen=False)
    gui_class.return_value.run_window.assert_called_once_with()
    pytrain.shutdown.assert_not_called()


#
# Entrypoints
#
@pytest.mark.parametrize("args", [[], ["-client"], ["-base", "10.0.0.9"]])
def test_main_returns_zero_and_passes_its_arguments_through(args, monkeypatch) -> None:
    cli = Mock()
    monkeypatch.setattr(mod, "RoutesCli", cli)
    monkeypatch.setattr(mod.sys, "argv", ["pyroutes", "-full_screen"])

    assert main(args) == 0
    cli.assert_called_once_with(cmd_line=args)


def test_main_reads_sys_argv_when_given_nothing(monkeypatch) -> None:
    cli = Mock()
    monkeypatch.setattr(mod, "RoutesCli", cli)
    monkeypatch.setattr(mod.sys, "argv", ["pyroutes", "-base", "10.0.0.9"])

    assert main() == 0
    cli.assert_called_once_with(cmd_line=["-base", "10.0.0.9"])


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
@pytest.mark.parametrize("failure_point", ["create", "run_window"])
def test_main_reports_gui_errors_after_cleanup(error_type, failure_point, pytrain, gui_class) -> None:
    error = error_type("window failed")
    if failure_point == "create":
        gui_class.side_effect = error
    else:
        gui_class.return_value.run_window.side_effect = error

    with pytest.raises(SystemExit) as exc:
        main(["-client"])

    assert exc.value.code == f"{mod.__file__}: error: window failed\n"
    pytrain.shutdown.assert_called_once_with()


def test_main_reports_connection_initialization_errors(monkeypatch) -> None:
    monkeypatch.setattr(mod.CommandBase, "__init__", Mock(side_effect=RuntimeError("no base")))

    with pytest.raises(SystemExit) as exc:
        main(["-client"])

    assert exc.value.code == f"{mod.__file__}: error: no base\n"


@pytest.mark.parametrize("args, exit_code", [(["--help"], 0), (["-width", "wide"], 2)])
def test_main_preserves_parser_exit_codes_without_starting_pytrain(args, exit_code, pytrain) -> None:
    with pytest.raises(SystemExit) as exc:
        main(args)

    assert exc.value.code == exit_code
    assert pytrain.initializations == []


def test_source_launcher_uses_main(monkeypatch) -> None:
    entrypoint = Mock(return_value=0)
    monkeypatch.setattr(mod, "main", entrypoint)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    launcher = Path(__file__).resolve().parents[2] / "cli" / "pyroutes.py"

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(launcher), run_name="__main__")

    assert exc.value.code == 0
    entrypoint.assert_called_once_with()


@pytest.mark.parametrize("from_root", [False, True])
def test_source_launcher_help_without_pythonpath(from_root, tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    launcher = root / "cli" / "pyroutes.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(launcher), "--help"],
        cwd=root if from_root else tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Routes window options" in result.stdout
    assert "Window width, in pixels (640)" in result.stdout
    assert "Window height, in pixels (800)" in result.stdout
