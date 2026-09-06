#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import importlib.util
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import ModuleType

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


def test_the_release_workflow_builds_and_publishes_both_distributions() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "python3 scripts/build_deck.py --outdir dist-deck" in workflow
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
