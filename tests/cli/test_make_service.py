#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import builtins
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest import mock

import pytest

import src.pytrain.cli.make_base as make_base
import src.pytrain.cli.make_service as mod
from src.pytrain.cli.make_service import MakeService

from ..test_base import TestBase


class TestMakeService(TestBase):
    def test_parser(self, monkeypatch: pytest.MonkeyPatch):
        # tests successful options
        with pytest.raises(SystemExit) as e:
            MakeService(["-version"])
        assert e.value.code == 0

        # Keep real version discovery above; other options only exercise parsing.
        # Patch the imported lookup at its use site, not the package export.
        # noinspection PyUnresolvedReferences
        monkeypatch.setattr(make_base, "get_version", lambda: "test-version")

        with pytest.raises(SystemExit) as e:
            MakeService(["-h"])
        assert e.value.code == 0

        with pytest.raises(SystemExit) as e:
            MakeService(["--help"])
        assert e.value.code == 0

        with mock.patch.object(builtins, "input", return_value="n"):
            # tests some positive cases
            assert MakeService("-client".split()) is not None
            assert MakeService("-client -echo".split()) is not None
            assert MakeService("-client -no_cache_sync".split()) is not None
            assert MakeService("-client -buttons".split()) is not None
            assert MakeService("-client -buttons -start".split()) is not None
            assert MakeService("-server -base -ser2 -echo -buttons_f".split()) is not None

            # tests some negative cases
            # neither client nor server specified
            with pytest.raises(SystemExit) as e:
                MakeService("-echo -buttons -start".split())
            assert e.value.code == 2

            # bad arguments
            with pytest.raises(SystemExit) as e:
                MakeService("-service".split())
            assert e.value.code == 2


def test_make_service_command_line_defaults_to_cache_sync_enabled() -> None:
    svc = MakeService.__new__(MakeService)
    svc._exe = "pytrain"
    svc._args = SimpleNamespace(mode="client", ser2=False)
    svc._base_ip = None
    svc._echo = False
    svc._buttons_file = None
    svc._no_cache_sync = False

    assert svc.command_line == "pytrain -headless -client"


def test_make_service_command_line_can_disable_cache_sync() -> None:
    svc = MakeService.__new__(MakeService)
    svc._exe = "pytrain"
    svc._args = SimpleNamespace(mode="client", ser2=False)
    svc._base_ip = None
    svc._echo = False
    svc._buttons_file = None
    svc._no_cache_sync = True

    assert svc.command_line == "pytrain -headless -client -no_cache_sync"


def test_make_service_shell_script_includes_cache_sync_switch_only_when_disabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    working_dir = tmp_path / "working"
    template_dir = working_dir / "src"
    template_dir.mkdir(parents=True)
    assert mod.__file__ is not None
    template = Path(mod.__file__).resolve().parents[1] / "installation" / "pytrain.bash.template"
    shutil.copy2(template, template_dir / template.name)
    monkeypatch.chdir(working_dir)
    svc = MakeService.__new__(MakeService)
    svc._home = tmp_path
    svc._args = SimpleNamespace(mode="client")
    svc._config = {
        "___ACTIVATE___": "/venv/bin/activate",
        "___BUTTONS___": "",
        "___CACHE_SYNC___": " -no_cache_sync",
        "___CLIENT___": " -client",
        "___ECHO___": "",
        "___LCSSER2___": "",
        "___LIONELBASE___": "",
        "___PYTRAIN___": "pytrain",
        "___PYTRAINHOME___": "/opt/pytrain",
    }

    path = svc.make_shell_script()

    assert path is not None
    assert "-no_cache_sync" in path.read_text(encoding="utf-8")

    svc._config["___CACHE_SYNC___"] = ""
    path = svc.make_shell_script()

    assert path is not None
    assert "-no_cache_sync" not in path.read_text(encoding="utf-8")
