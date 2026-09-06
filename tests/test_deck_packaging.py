#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import importlib.util
import os
import sys
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import src.pytrain as pytrain_pkg
from src.pytrain import PROGRAM_PACKAGE, PROGRAM_PACKAGE_DECK, installed_package, is_package
from src.pytrain.cli.pytrain import REQUIREMENTS, REQUIREMENTS_NO_GPIO

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
BUILD_DECK = ROOT / "scripts" / "build_deck.py"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


@pytest.fixture
def build_deck() -> ModuleType:
    """The build script, imported by path: scripts/ is deliberately not a package."""
    spec = importlib.util.spec_from_file_location("build_deck", BUILD_DECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def config() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _deck(config: dict) -> dict:
    return config["tool"]["pytrain"]["deck"]


def _requirement_names(requirements: str) -> set[str]:
    """Distribution names in a requirements file, ignoring -r includes and comments."""
    names = set()
    for line in requirements.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        names.add(line.split(";")[0].strip().split("=")[0].strip("<>!~ ").lower().replace("_", "-"))
    return names


def test_pyproject_declares_the_deck_distribution(config) -> None:
    # The one pyproject.toml describes both distributions; scripts/build_deck.py is
    # nothing more than the mechanism that applies this table.
    deck = _deck(config)

    assert deck["name"] == PROGRAM_PACKAGE_DECK
    assert config["project"]["name"] == PROGRAM_PACKAGE
    assert deck["exclude-dependencies"]


def test_the_excluded_requirements_are_the_gpio_only_ones(config) -> None:
    # requirements.txt is requirements-nogpio.txt plus the GPIO-only distributions, so
    # the difference between the two is exactly what the Deck build has to drop. Pinning
    # it here means renaming or adding a GPIO dependency cannot quietly leave the Deck
    # package unbuildable on a Deck.
    gpio_only = _requirement_names((ROOT / REQUIREMENTS).read_text(encoding="utf-8"))
    gpio_free = _requirement_names((ROOT / REQUIREMENTS_NO_GPIO).read_text(encoding="utf-8"))
    excluded = {name.lower().replace("_", "-") for name in _deck(config)["exclude-dependencies"]}

    assert excluded == gpio_only - gpio_free


def test_every_excluded_requirement_is_actually_a_dependency(config) -> None:
    # An exclusion that matches nothing is a typo, not a no-op worth keeping.
    dependencies = {
        dependency.split(";")[0].strip().split("=")[0].strip("<>!~ ").lower().replace("_", "-")
        for dependency in config["project"]["dependencies"]
    }

    for name in _deck(config)["exclude-dependencies"]:
        assert name.lower().replace("_", "-") in dependencies


def test_the_deck_build_renames_the_project_and_drops_the_gpio_requirements(build_deck, config) -> None:
    overridden, deck = build_deck.deck_pyproject()
    project = tomllib.loads(overridden)["project"]

    assert deck["name"] == PROGRAM_PACKAGE_DECK
    assert project["name"] == PROGRAM_PACKAGE_DECK
    excluded = {build_deck.canonical_name(name) for name in deck["exclude-dependencies"]}
    installed = {build_deck.canonical_name(d.split(" ")[0].split(">")[0]) for d in project["dependencies"]}
    assert not excluded & installed
    # Nothing else may change: same requires-python, scripts, package data, and the
    # remaining dependencies in their original order.
    expected = build_deck.expected_project(config, deck)
    assert project == expected


def test_the_deck_build_leaves_the_pi_packaging_flow_alone(build_deck, config) -> None:
    # The Pi build must keep using plain setuptools, and generating the Deck overrides
    # must not touch pyproject.toml -- build_deck.py restores it itself, but the
    # override step has no business writing at all.
    before = PYPROJECT.read_bytes()
    overridden, _ = build_deck.deck_pyproject()

    assert PYPROJECT.read_bytes() == before
    assert tomllib.loads(overridden)["build-system"] == config["build-system"]
    assert config["build-system"]["build-backend"] == "setuptools.build_meta"


@pytest.fixture
def sandbox(build_deck, monkeypatch, tmp_path) -> Path:
    """A throwaway copy of pyproject.toml, so exercising main() never writes the real one."""
    project = tmp_path / "pyproject.toml"
    project.write_bytes(PYPROJECT.read_bytes())
    monkeypatch.setattr(build_deck, "PYPROJECT", project)
    monkeypatch.setattr(build_deck, "PROJECT_ROOT", tmp_path)
    return project


def _build(build_deck, monkeypatch, *args: str) -> dict:
    """Run main() with the build itself stubbed out, reporting what it would have run."""
    seen: dict = {}

    def fake_call(command, cwd=None, env=None) -> int:
        seen["command"] = command
        seen["env"] = env
        seen["pyproject"] = build_deck.PYPROJECT.read_bytes()
        return 0

    monkeypatch.setattr(build_deck.subprocess, "call", fake_call)
    monkeypatch.setattr(build_deck.sys, "argv", ["build_deck.py", *args])
    seen["returncode"] = build_deck.main()
    return seen


def test_the_deck_build_reads_the_version_before_it_rewrites_pyproject(build_deck, monkeypatch, sandbox) -> None:
    # This is what broke the first deck release: the rewrite turns pyproject.toml into a
    # modified tracked file, so setuptools_scm calls the tree dirty and stamps
    # 2.9.9+ga9779ccd.d20260906 on the artifacts -- and PyPI rejects every version with a
    # local segment. Reading the version first is the fix, so the ordering is pinned here.
    read_at: list[bytes] = []

    def fake_pristine_version() -> str:
        read_at.append(sandbox.read_bytes())
        return "2.9.9"

    monkeypatch.setattr(build_deck, "pristine_version", fake_pristine_version)

    seen = _build(build_deck, monkeypatch)

    assert read_at == [PYPROJECT.read_bytes()]
    # ...and the build still gets the overridden file, restored once it is done.
    assert f'name = "{PROGRAM_PACKAGE_DECK}"'.encode() in seen["pyproject"]
    assert sandbox.read_bytes() == PYPROJECT.read_bytes()


def test_the_build_is_pinned_to_the_version_of_the_clean_tree(build_deck, monkeypatch, sandbox) -> None:
    # Reading the version early only helps if the build is made to use it rather than
    # deriving its own from the tree it finds.
    monkeypatch.setattr(build_deck, "pristine_version", lambda: "2.9.9")

    seen = _build(build_deck, monkeypatch)

    assert seen["env"]["SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYTRAIN_OGR_DECK"] == "2.9.9"
    assert seen["env"]["SETUPTOOLS_SCM_PRETEND_VERSION"] == "2.9.9"
    # The build runs in this environment, so the rest of it has to survive.
    assert set(os.environ).issubset(seen["env"])


def test_a_local_version_is_refused_before_anything_is_built(build_deck, monkeypatch, sandbox) -> None:
    # A rejected upload burns the version, so a version PyPI cannot accept has to fail the
    # build job, not the publish job.
    ran: list[bool] = []
    monkeypatch.setattr(build_deck, "pristine_version", lambda: "2.9.9+ga9779ccdd.d20260906")
    monkeypatch.setattr(build_deck.subprocess, "call", lambda *_args, **_kwargs: ran.append(True))
    monkeypatch.setattr(build_deck.sys, "argv", ["build_deck.py"])

    with pytest.raises(SystemExit) as refusal:
        build_deck.main()

    assert "2.9.9+ga9779ccdd.d20260906" in str(refusal.value)
    assert ran == []
    assert sandbox.read_bytes() == PYPROJECT.read_bytes()


def test_a_local_version_can_still_be_built_on_request(build_deck, monkeypatch, sandbox) -> None:
    # Building a wheel from a work-in-progress tree to sideload onto a Deck is legitimate;
    # only uploading it is not.
    monkeypatch.setattr(build_deck, "pristine_version", lambda: "2.9.9+d20260906")

    seen = _build(build_deck, monkeypatch, "--allow-local-version")

    assert seen["returncode"] == 0
    assert seen["env"]["SETUPTOOLS_SCM_PRETEND_VERSION"] == "2.9.9+d20260906"


def test_the_pinned_version_follows_the_projects_setuptools_scm_settings(build_deck, monkeypatch, config) -> None:
    # Both distributions have to carry the same version, so the deck build cannot invent a
    # scheme of its own -- it reads the one [tool.setuptools_scm] table. All but
    # version_file: writing that is the build's business, not this script's.
    recorded: dict = {}

    def fake_get_version(**kwargs) -> str:
        recorded.update(kwargs)
        return "2.9.9"

    monkeypatch.setitem(sys.modules, "setuptools_scm", SimpleNamespace(get_version=fake_get_version))

    assert build_deck.pristine_version() == "2.9.9"
    assert recorded["version_scheme"] == config["tool"]["setuptools_scm"]["version_scheme"]
    assert Path(recorded["root"]) == ROOT
    assert "version_file" not in recorded


def test_the_release_workflow_builds_and_publishes_both_distributions() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "python3 scripts/build_deck.py --outdir dist-deck" in workflow
    # build_deck.py reads the version itself, outside the isolated build environment.
    assert "python3 -m pip install build setuptools-scm" in workflow
    assert f"https://pypi.org/p/{PROGRAM_PACKAGE}" in workflow
    assert f"https://pypi.org/p/{PROGRAM_PACKAGE_DECK}" in workflow
    # The two builds cannot share an artifact: PyPI mints an upload token per project.
    assert workflow.count("name: python-package-distributions\n") == 2
    assert workflow.count("name: python-package-distributions-deck\n") == 2


def _installed(monkeypatch, *packages: str) -> None:
    def fake_version(package: str) -> str:
        if package not in packages:
            raise PackageNotFoundError(package)
        return "2.9.8"

    monkeypatch.setattr(pytrain_pkg.importlib.metadata, "version", fake_version)


def test_installed_package_recognizes_the_deck_distribution(monkeypatch) -> None:
    # Without this, a Deck install looks like a git checkout to itself: is_package()
    # says no, and get_version() falls back to setuptools_scm with no repo to read.
    _installed(monkeypatch, PROGRAM_PACKAGE_DECK)

    assert installed_package() == PROGRAM_PACKAGE_DECK
    assert is_package() is True


def test_installed_package_recognizes_the_pi_distribution(monkeypatch) -> None:
    _installed(monkeypatch, PROGRAM_PACKAGE)

    assert installed_package() == PROGRAM_PACKAGE
    assert is_package() is True


def test_installed_package_reports_a_source_checkout(monkeypatch) -> None:
    _installed(monkeypatch)

    assert installed_package() is None
    assert is_package() is False
