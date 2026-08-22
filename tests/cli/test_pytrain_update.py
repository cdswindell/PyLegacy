#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import subprocess
import sys
from pathlib import Path

import pytest

import src.pytrain.cli.pytrain as mod
from src.pytrain.cli.pytrain import REQUIREMENTS, REQUIREMENTS_NO_GPIO, PyTrain, PyTrainExitStatus
from src.pytrain.utils.host_info import PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM


def _pytrain() -> PyTrain:
    # requirements_file needs no instance state, so skip the CLI's __init__ entirely.
    return PyTrain.__new__(PyTrain)


@pytest.fixture
def commands(monkeypatch) -> list[list[str]]:
    """Capture argv lists instead of letting the CLI actually shell out.

    Every one of these methods runs apt, systemctl, pip or shutdown for real if the
    patch misses, so the seam is patched once here rather than per test.
    """
    recorded: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        recorded.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    return recorded


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


def test_source_update_installs_the_selected_requirements(monkeypatch, repo_root, commands) -> None:
    # The whole point of the property: it has to reach the pip command.
    monkeypatch.setenv(PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM)

    pytrain = _pytrain()
    pytrain._exit_status = None
    monkeypatch.setattr(type(pytrain), "is_server", property(lambda _self: True))
    monkeypatch.setattr(type(pytrain), "is_api", property(lambda _self: False))
    monkeypatch.setattr(type(pytrain), "relaunch", lambda _self, _status: None)
    # update() imports is_package() from the package root at call time, so it has to be
    # patched there rather than on this module.
    monkeypatch.setattr("src.pytrain.is_package", lambda: False)

    pytrain.update(do_inform=False)

    pip_installs = [c for c in commands if "install" in c and "-r" in c]
    assert len(pip_installs) == 1
    assert pip_installs[0][-2:] == ["-r", REQUIREMENTS_NO_GPIO]
    # The venv's own interpreter, not whatever bare `pip` resolves to on PATH.
    assert pip_installs[0][0] == sys.executable
    assert ["git", "pull"] in commands


def test_requirements_files_both_exist_in_the_repo() -> None:
    # requirements.txt includes the GPIO-free list by reference, so a rename would
    # break the default install as well as the Deck's.
    root = Path(__file__).resolve().parents[2]

    assert (root / REQUIREMENTS).is_file()
    assert (root / REQUIREMENTS_NO_GPIO).is_file()
    assert REQUIREMENTS_NO_GPIO in (root / REQUIREMENTS).read_text(encoding="utf-8")


def _shell_out_pytrain(monkeypatch, *, is_api: bool = False) -> PyTrain:
    """A PyTrain whose only remaining observable behaviour is what it shells out."""
    pytrain = _pytrain()
    pytrain._exit_status = None
    monkeypatch.setattr(type(pytrain), "is_server", property(lambda _self: True))
    monkeypatch.setattr(type(pytrain), "is_api", property(lambda _self: is_api))
    return pytrain


def test_reboot_asks_shutdown_to_restart(monkeypatch, commands) -> None:
    pytrain = _shell_out_pytrain(monkeypatch)

    pytrain.reboot(reboot=True)

    assert commands == [["sudo", "shutdown", "-r", "now"]]


def test_shutdown_omits_the_restart_flag(monkeypatch, commands) -> None:
    # The -r is the only difference between halting the machine and restarting it, so
    # it is worth pinning in both directions.
    pytrain = _shell_out_pytrain(monkeypatch)

    pytrain.reboot(reboot=False)

    assert commands == [["sudo", "shutdown", "now"]]


def _stub_update(monkeypatch, pytrain: PyTrain, commands: list[list[str]]) -> list[dict]:
    """Replace update() with a recorder that also marks its place in `commands`.

    upgrade() has to run the PyTrain update *before* the reboot, and ordering is the
    whole point, so the stub drops a sentinel into the same list the argv lists land in.
    """
    calls: list[dict] = []

    def fake_update(_self, do_inform: bool = True, relaunch: bool = True) -> None:
        calls.append({"do_inform": do_inform, "relaunch": relaunch})
        commands.append(["<pytrain update>"])

    monkeypatch.setattr(type(pytrain), "update", fake_update)
    return calls


def test_upgrade_updates_pytrain_before_touching_the_os(monkeypatch, commands) -> None:
    # Ordering matters: `sudo reboot` returns as soon as systemd accepts the job, so an
    # update sequenced after it would race the teardown.
    monkeypatch.delenv(PLATFORM_ENV_VAR, raising=False)
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod, "sleep", lambda _seconds: None)  # 5s of real sleeps otherwise
    pytrain = _shell_out_pytrain(monkeypatch)
    calls = _stub_update(monkeypatch, pytrain, commands)

    pytrain.upgrade()

    assert commands == [
        ["<pytrain update>"],
        ["sudo", "apt", "update"],
        ["sudo", "apt", "upgrade", "-y"],
        ["sudo", "apt", "autoremove", "-y"],
        ["sudo", "rpi-eeprom-update", "-a"],
        ["sudo", "reboot"],
    ]
    # The reboot is this path's relaunch; update() must not also relaunch.
    assert calls == [{"do_inform": False, "relaunch": False}]


def test_upgrade_off_linux_updates_and_relaunches(monkeypatch, commands) -> None:
    # apt and rpi-eeprom-update do not exist on macOS/Windows; the guard is what keeps
    # a developer's machine from being handed sudo commands it cannot run. With no
    # reboot to serve as the relaunch, update() has to do it.
    monkeypatch.delenv(PLATFORM_ENV_VAR, raising=False)
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    monkeypatch.setattr(mod, "sleep", lambda _seconds: None)
    pytrain = _shell_out_pytrain(monkeypatch)
    calls = _stub_update(monkeypatch, pytrain, commands)

    pytrain.upgrade()

    assert commands == [["<pytrain update>"]]
    assert calls == [{"do_inform": False, "relaunch": True}]


def test_upgrade_in_api_mode_signals_without_acting(monkeypatch, commands) -> None:
    # API mode hands the host an exit status rather than doing anything destructive
    # itself -- so no apt, no reboot, and no update either.
    monkeypatch.delenv(PLATFORM_ENV_VAR, raising=False)
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod, "sleep", lambda _seconds: None)
    pytrain = _shell_out_pytrain(monkeypatch, is_api=True)
    calls = _stub_update(monkeypatch, pytrain, commands)

    with pytest.raises(mod.PyTrainExitException):
        pytrain.upgrade()

    assert commands == []
    assert calls == []
    assert pytrain.exit_status == PyTrainExitStatus.UPDATE


def test_relaunch_restarts_the_service_when_running_as_one(monkeypatch, commands) -> None:
    pytrain = _shell_out_pytrain(monkeypatch)
    monkeypatch.setattr(type(pytrain), "is_client", property(lambda _self: False))
    monkeypatch.setattr(type(pytrain), "is_service", property(lambda _self: True))

    pytrain.relaunch(PyTrainExitStatus.RESTART)

    assert commands == [["sudo", "systemctl", "restart", "pytrain_server.service"]]


def test_relaunch_execs_itself_when_not_a_service(monkeypatch, commands) -> None:
    # The non-service branch must not spawn a child: os.execv replaces this process, so
    # a subprocess here would leave the old interpreter running alongside the new one.
    execs: list[tuple[str, list[str]]] = []
    pytrain = _shell_out_pytrain(monkeypatch)
    monkeypatch.setattr(type(pytrain), "is_client", property(lambda _self: False))
    monkeypatch.setattr(type(pytrain), "is_service", property(lambda _self: False))
    monkeypatch.setattr(mod.os, "execv", lambda path, argv: execs.append((path, argv)))
    pytrain._echo = False
    pytrain._debug = False

    pytrain.relaunch(PyTrainExitStatus.RESTART)

    assert commands == []
    assert len(execs) == 1


@pytest.mark.parametrize(("returncode", "expected"), [(0, True), (3, False)])
def test_is_service_reads_the_systemctl_returncode(monkeypatch, returncode, expected) -> None:
    # `systemctl is-active --quiet` reports through its exit status only, so the
    # returncode is the entire answer -- 0 active, nonzero anything else.
    recorded: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        recorded.append(command)
        return subprocess.CompletedProcess(args=command, returncode=returncode)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr("src.pytrain.is_linux", lambda: True)
    pytrain = _shell_out_pytrain(monkeypatch)

    assert pytrain.is_service is expected
    assert recorded == [["systemctl", "is-active", "--quiet", "pytrain_server.service"]]


def test_is_service_is_false_off_linux(monkeypatch, commands) -> None:
    monkeypatch.setattr("src.pytrain.is_linux", lambda: False)
    pytrain = _shell_out_pytrain(monkeypatch)

    assert pytrain.is_service is False
    assert commands == []


def test_upgrade_skips_the_os_on_the_steam_deck(monkeypatch, commands) -> None:
    # SteamOS updates itself and its root filesystem is immutable. sys.platform is
    # "linux" on the Deck, so the platform check alone would have run apt there.
    monkeypatch.setenv(PLATFORM_ENV_VAR, STEAM_DECK_PLATFORM)
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod, "sleep", lambda _seconds: None)
    pytrain = _shell_out_pytrain(monkeypatch)
    calls = _stub_update(monkeypatch, pytrain, commands)

    pytrain.upgrade()

    # No apt, no eeprom, and above all no reboot -- but PyTrain itself still updates,
    # and with no reboot coming it has to relaunch itself.
    assert commands == [["<pytrain update>"]]
    assert calls == [{"do_inform": False, "relaunch": True}]


@pytest.mark.parametrize("relaunch", [True, False])
def test_update_relaunches_only_when_asked(monkeypatch, repo_root, commands, relaunch) -> None:
    monkeypatch.delenv(PLATFORM_ENV_VAR, raising=False)
    relaunches: list[PyTrainExitStatus] = []
    pytrain = _shell_out_pytrain(monkeypatch)
    monkeypatch.setattr(type(pytrain), "relaunch", lambda _self, status: relaunches.append(status))
    monkeypatch.setattr("src.pytrain.is_package", lambda: False)

    pytrain.update(do_inform=False, relaunch=relaunch)

    # Either way the update itself still runs -- the flag governs the restart only.
    assert ["git", "pull"] in commands
    assert relaunches == ([PyTrainExitStatus.UPDATE] if relaunch else [])
