#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from pathlib import Path

import pytest

from src.pytrain.cli.pytrain import REQUIREMENTS, REQUIREMENTS_NO_GPIO, PyTrain
from src.pytrain.utils.host_info import PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM


def _pytrain() -> PyTrain:
    # requirements_file needs no instance state, so skip the CLI's __init__ entirely.
    return PyTrain.__new__(PyTrain)


@pytest.fixture
def repo_root(monkeypatch, tmp_path) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / REQUIREMENTS).write_text("-r requirements-nogpio.txt\nrpi-lgpio>=0.6\n", encoding="utf-8")
    (tmp_path / REQUIREMENTS_NO_GPIO).write_text("guizero>=1.6.0\n", encoding="utf-8")
    return tmp_path


def test_update_uses_the_gpio_free_requirements_on_the_steam_deck(monkeypatch, repo_root) -> None:
    # The Deck has no GPIO hardware, and requirements.txt pulls in rpi-lgpio/spidev
    # gated only on sys_platform == 'linux' -- which the Deck satisfies, so they would
    # be attempted there.
    monkeypatch.setenv(PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM)

    assert _pytrain().requirements_file == REQUIREMENTS_NO_GPIO


def test_update_uses_the_default_requirements_elsewhere(monkeypatch, repo_root) -> None:
    monkeypatch.delenv(PLATFORM_ENV_VAR, raising=False)

    assert _pytrain().requirements_file == REQUIREMENTS


def test_update_falls_back_when_the_gpio_free_list_is_missing(monkeypatch, tmp_path) -> None:
    # An update must not abort on a checkout that predates requirements-nogpio.txt.
    monkeypatch.chdir(tmp_path)
    (tmp_path / REQUIREMENTS).write_text("guizero>=1.6.0\n", encoding="utf-8")
    monkeypatch.setenv(PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM)

    assert _pytrain().requirements_file == REQUIREMENTS


def test_source_update_installs_the_selected_requirements(monkeypatch, repo_root) -> None:
    # The whole point of the property: it has to reach the pip command.
    monkeypatch.setenv(PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM)
    commands: list[str] = []
    monkeypatch.setattr("src.pytrain.cli.pytrain.os.system", lambda command: commands.append(command) or 0)

    pytrain = _pytrain()
    pytrain._exit_status = None
    monkeypatch.setattr(type(pytrain), "is_server", property(lambda _self: True))
    monkeypatch.setattr(type(pytrain), "is_api", property(lambda _self: False))
    monkeypatch.setattr(type(pytrain), "relaunch", lambda _self, _status: None)
    # update() imports is_package() from the package root at call time, so it has to be
    # patched there rather than on this module.
    monkeypatch.setattr("src.pytrain.is_package", lambda: False)

    pytrain.update(do_inform=False)

    pip_installs = [c for c in commands if "pip install -r" in c]
    assert len(pip_installs) == 1
    assert pip_installs[0].endswith(f"pip install -r {REQUIREMENTS_NO_GPIO}")
    assert "git pull" in " ".join(commands)


def test_requirements_files_both_exist_in_the_repo() -> None:
    # requirements.txt includes the GPIO-free list by reference, so a rename would
    # break the default install as well as the Deck's.
    root = Path(__file__).resolve().parents[2]

    assert (root / REQUIREMENTS).is_file()
    assert (root / REQUIREMENTS_NO_GPIO).is_file()
    assert REQUIREMENTS_NO_GPIO in (root / REQUIREMENTS).read_text(encoding="utf-8")
