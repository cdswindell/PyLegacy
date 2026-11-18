"""Verify Deck launch selection without starting a client or contacting hardware."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Optional
from unittest.mock import Mock, patch

import pytest

from pytrain.cli.make_gui import MakeGui
from pytrain.gui.controller.engine_gui import EngineGui
from pytrain.gui.controller.steam_deck_gui import SteamDeckGui
from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt.pycab import QtCabCli, QtCabCommand


@pytest.mark.parametrize("deck_args", [[], ["--deck"]])
def test_cab_parser_accepts_debug_for_cab_and_deck(deck_args: list[str]) -> None:
    parser = QtCabCli.command_parser()
    assert parser.parse_args(deck_args).debug is False
    options = parser.parse_args([*deck_args, "-debug", "-echo"])
    assert options.debug is True
    assert options.echo is True


def test_deck_parser_preserves_profile_and_dimensions() -> None:
    options = QtCabCli.command_parser().parse_args(
        ["--deck", "--width", "1440", "--height", "900", "--controller-profile", "/profiles/My Deck.json"]
    )
    assert options.deck is True
    assert (options.width, options.height) == (1440, 900)
    assert options.controller_profile == "/profiles/My Deck.json"
    defaults = QtCabCli.command_parser().parse_args([])
    assert defaults.deck is False
    assert (defaults.width, defaults.height) == (1280, 800)


@pytest.mark.parametrize("flag", ["--width", "--height"])
@pytest.mark.parametrize("value", ["0", "-1", "1.5", "bad"])
def test_deck_parser_rejects_invalid_dimensions(flag: str, value: str) -> None:
    with pytest.raises((SystemExit, ValueError)):
        QtCabCli.command_parser().parse_args([flag, value])


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Requires the optional Qt presentation")
@pytest.mark.parametrize("deck", [False, True])
def test_launch_command_forwards_deck_options_and_shuts_down(deck: bool) -> None:
    options = SimpleNamespace(deck=deck, width=1440, height=900, controller_profile="/profiles/My Deck.json")
    command = Mock(spec=QtCabCommand, pytrain=Mock(admin_exit_requested=False))
    # Supply constructor-owned CLI state without starting networking.
    # noinspection PyProtectedMember
    command._cli = SimpleNamespace(scope=CommandScope.TRAIN, tmcc_id=7, args=options)
    with (
        patch("pytrain_ui.qt.app.run_deck", return_value=23) as run_deck,
        patch("pytrain_ui.qt.pycab.run_cab", return_value=23) as run_cab,
    ):
        assert QtCabCommand.send(command) == 23
    command.wait_for_sync.assert_called_once_with()
    command.pytrain.shutdown.assert_called_once_with()
    if deck:
        run_deck.assert_called_once_with(
            CommandScope.TRAIN, 7, [], width=1440, height=900, controller_profile="/profiles/My Deck.json"
        )
        run_cab.assert_not_called()
    else:
        run_cab.assert_called_once_with(CommandScope.TRAIN, 7, [])
        run_deck.assert_not_called()


# These fields normally come from the interactive constructor; isolate generation from installation.
# noinspection PyProtectedMember
def _launcher(gui_class: type, profile: Optional[str] = None) -> MakeGui:
    launcher = MakeGui.__new__(MakeGui)
    launcher._gui_class = gui_class
    launcher._args = SimpleNamespace(width=1280, height=800, controller_profile=profile)
    return launcher


def test_non_deck_generated_launch_has_no_qt_deck_block() -> None:
    assert _launcher(EngineGui).qt_deck_launch() == ""


@pytest.mark.parametrize(
    ("probe_status", "ser2", "cache_sync", "expected_qt"),
    [(0, "", "", True), (1, "", "", False), (0, " -ser2", "", False), (0, "", " -no_cache_sync", False)],
)
def test_generated_launcher_preserves_legacy_fallback_and_quotes_profile(
    tmp_path: Path, probe_status: int, ser2: str, cache_sync: str, expected_qt: bool
) -> None:
    marker = tmp_path / "must-not-exist"
    profile = f"/profiles/Deck $(touch {marker}).json"
    script = _launcher(SteamDeckGui, profile).qt_deck_launch()
    for key, value in {
        "___LCSSER2___": ser2,
        "___CACHE_SYNC___": cache_sync,
        "___CLIENT___": " -client",
        "___LIONELBASE___": " -base 192.0.2.1",
        "___ECHO___": " -echo",
    }.items():
        script = script.replace(key, value)
    assert "___" not in script
    assert "select_backend" in script
    script += "printf 'LEGACY\\n'\n"
    # A harmless executable captures arguments; no real Python client starts.
    executable = tmp_path / "python"
    executable.write_text('#!/bin/bash\nif [ "$1" = "-c" ]; then exit "$PROBE_STATUS"; fi\nprintf "%s\\n" "$@"\n')
    executable.chmod(0o755)
    syntax = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True, check=False)
    assert syntax.returncode == 0, syntax.stderr
    environment = dict(os.environ, PATH=f"{tmp_path}:{os.environ.get('PATH', '')}", PROBE_STATUS=str(probe_status))
    result = subprocess.run(["bash"], input=script, env=environment, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "Profile arguments must not execute shell substitutions"
    if expected_qt:
        assert result.stdout.splitlines() == [
            "-m",
            "pytrain_ui.qt.pycab",
            "--deck",
            "--width",
            "1280",
            "--height",
            "800",
            "--controller-profile",
            profile,
            "-client",
            "-base",
            "192.0.2.1",
            "-echo",
        ]
    else:
        assert result.stdout == "LEGACY\n"
