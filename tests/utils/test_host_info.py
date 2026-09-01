#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import pytest

from src.pytrain.utils.host_info import (
    PLATFORM_ENV_VAR,
    STEAM_DECK_PLATFORM,
    installed_platform,
    is_linux,
    is_steam_deck,
)


def test_platform_is_empty_when_the_launcher_set_nothing(monkeypatch) -> None:
    monkeypatch.delenv(PLATFORM_ENV_VAR, raising=False)

    assert installed_platform() == ""
    assert is_steam_deck() is False


def test_platform_reports_the_steam_deck(monkeypatch) -> None:
    monkeypatch.setenv(PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM)

    assert installed_platform() == STEAM_DECK_PLATFORM
    assert is_steam_deck() is True


@pytest.mark.parametrize("value", ["SteamDeck", " steamdeck ", "STEAMDECK"])
def test_platform_is_normalized(monkeypatch, value) -> None:
    # The value comes from a shell variable, so tolerate case and stray whitespace.
    monkeypatch.setenv(PLATFORM_ENV_VAR, value)

    assert is_steam_deck() is True


def test_platform_is_read_live_rather_than_cached(monkeypatch) -> None:
    # Nothing may freeze the value at import or construction time: the launcher exports
    # it before PyTrain starts, but tests and embedders can change it later.
    monkeypatch.delenv(PLATFORM_ENV_VAR, raising=False)
    assert is_steam_deck() is False

    monkeypatch.setenv(PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM)

    assert is_steam_deck() is True


def test_an_unrelated_platform_is_not_the_steam_deck(monkeypatch) -> None:
    monkeypatch.setenv(PLATFORM_ENV_VAR, "raspberrypi")

    assert installed_platform() == "raspberrypi"
    assert is_steam_deck() is False


@pytest.mark.parametrize("system, expected", [("Linux", True), ("linux", True), ("Darwin", False), ("Windows", False)])
def test_is_linux_reports_the_running_system(monkeypatch, system: str, expected: bool) -> None:
    monkeypatch.setattr("platform.system", lambda: system, raising=True)

    assert is_linux() is expected


def test_is_linux_does_not_probe_the_hardware(monkeypatch) -> None:
    # It has to stay cheap enough for a GUI to call while laying itself out, which is why
    # it is a module function and not a HostInfo member: building that singleton shells out
    # to `cat` and `free`.
    def explode(*_args, **_kwargs):
        raise AssertionError("is_linux must not run a subprocess")

    monkeypatch.setattr("subprocess.run", explode, raising=True)

    assert is_linux() in (True, False)
