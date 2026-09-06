#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Build the Steam Deck variant (pytrain-ogr-deck) of PyTrain.

The Steam Deck cannot install the GPIO-only requirements (rpi-lgpio, spidev) that
pytrain-ogr pulls in on Linux. Rather than maintain a second project file, the deck
variant is described by the [tool.pytrain.deck] table of the one and only
pyproject.toml. This script applies those overrides to pyproject.toml, runs the
regular build, and restores the file, so the pytrain-ogr build and install flows
are never affected.

Rewriting pyproject.toml leaves the working tree dirty, so the version is read before
anything is written and pinned for the build; see pristine_version().

Usage:

    python3 scripts/build_deck.py                    # build into ./dist-deck
    python3 scripts/build_deck.py -o /tmp/deck       # build into another directory
    python3 scripts/build_deck.py --dry-run          # show the overridden pyproject.toml

Any option this script does not recognize, such as --no-isolation, is handed to
'python -m build' as is.
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
DEFAULT_OUTDIR = "dist-deck"
PRETEND_KEY = "SETUPTOOLS_SCM_PRETEND_VERSION"

TABLE_RE = re.compile(r"^\s*\[\[?([^]]+)]]?\s*$")
KEY_RE = re.compile(r"^(\s*)([A-Za-z0-9_.\"'-]+)\s*=\s*(.*)$")
REQUIREMENT_RE = re.compile(r"""^\s*["']\s*([A-Za-z0-9][A-Za-z0-9._-]*)""")


def canonical_name(name: str) -> str:
    """Normalize a distribution name the way PyPI does (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def deck_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return the [tool.pytrain.deck] table, complaining if it is missing."""
    deck = config.get("tool", {}).get("pytrain", {}).get("deck", {})
    if not deck:
        raise SystemExit(f"{PYPROJECT.name} has no [tool.pytrain.deck] table; nothing to build")
    if "name" not in deck:
        raise SystemExit("[tool.pytrain.deck] must specify the distribution 'name'")
    return deck


def expected_project(config: Dict[str, Any], deck: Dict[str, Any]) -> Dict[str, Any]:
    """Build the [project] table the overridden pyproject.toml must end up with."""
    excluded = {canonical_name(name) for name in deck.get("exclude-dependencies", [])}
    project = copy.deepcopy(config["project"])
    project["name"] = deck["name"]
    if "description" in deck:
        project["description"] = deck["description"]
    project["dependencies"] = [
        dependency
        for dependency in project.get("dependencies", [])
        if canonical_name(re.split(r"[\s!<>=~;\[]", dependency.strip(), maxsplit=1)[0]) not in excluded
    ]
    return project


def override_pyproject(text: str, deck: Dict[str, Any]) -> str:
    """Rewrite the [project] table of pyproject.toml with the deck overrides."""
    excluded = {canonical_name(name) for name in deck.get("exclude-dependencies", [])}
    overrides = {"name": deck["name"]}
    if "description" in deck:
        overrides["description"] = deck["description"]

    lines: List[str] = []
    table: str | None = None
    in_dependencies = False
    for line in text.splitlines(keepends=True):
        table_match = TABLE_RE.match(line)
        if table_match:
            table = table_match.group(1).strip()
            in_dependencies = False
            lines.append(line)
            continue
        if in_dependencies:
            if line.lstrip().startswith("]"):
                in_dependencies = False
            else:
                requirement = REQUIREMENT_RE.match(line)
                if requirement and canonical_name(requirement.group(1)) in excluded:
                    continue
            lines.append(line)
            continue
        key_match = KEY_RE.match(line) if table == "project" else None
        if key_match:
            indent, key, value = key_match.groups()
            if key in overrides:
                lines.append(f'{indent}{key} = "{overrides[key]}"\n')
                continue
            if key == "dependencies" and value.startswith("[") and not value.rstrip().endswith("]"):
                in_dependencies = True
        lines.append(line)
    return "".join(lines)


def deck_pyproject() -> tuple[str, Dict[str, Any]]:
    """Return the overridden pyproject.toml content along with its deck configuration."""
    original = PYPROJECT.read_bytes().decode("utf-8")
    config = tomllib.loads(original)
    deck = deck_config(config)
    overridden = override_pyproject(original, deck)

    expected = expected_project(config, deck)
    actual = tomllib.loads(overridden).get("project", {})
    if actual != expected:
        raise SystemExit(
            f"Unable to apply the [tool.pytrain.deck] overrides to {PYPROJECT.name}.\n"
            "The [project] table must declare 'name', 'description', and one dependency per line."
        )
    return overridden, deck


def pristine_version() -> str:
    """Return the version setuptools_scm derives from the checkout as it stands now.

    This must be read before pyproject.toml is rewritten. A rewritten pyproject.toml is a
    modified tracked file, so setuptools_scm sees a dirty working tree and appends a local
    segment to the version -- 2.9.9 becomes 2.9.9+ga9779ccd.d20260906 -- and PyPI rejects
    every version that carries one. Pinning the version read here for the build gives the
    deck artifacts exactly the version the pytrain-ogr build produces from the same commit.

    The [tool.setuptools_scm] settings are taken from pyproject.toml so the two builds stay
    in step, all but version_file: writing it is the build's business, not this function's.
    """
    try:
        from setuptools_scm import get_version
    except ModuleNotFoundError:
        raise SystemExit(
            "setuptools_scm is needed to determine the version of the deck distribution.\n"
            "Install it with: python3 -m pip install setuptools-scm"
        ) from None

    scm = tomllib.loads(PYPROJECT.read_bytes().decode("utf-8")).get("tool", {}).get("setuptools_scm", {})
    options = {key: scm[key] for key in ("version_scheme", "local_scheme", "fallback_version") if key in scm}
    return get_version(root=str(PROJECT_ROOT), **options)


def pretend_version_env(name: str, version: str) -> Dict[str, str]:
    """Return the build environment, with the version setuptools_scm must report pinned."""
    env = dict(os.environ)
    # the distribution-specific variable is the documented one; the bare variable is set as
    # well, as older setuptools_scm releases normalize the distribution name differently
    env[PRETEND_KEY] = version
    env[f"{PRETEND_KEY}_FOR_{re.sub(r'[-_.]+', '_', name).upper()}"] = version
    return env


def check_publishable(version: str, allow_local: bool) -> None:
    """Fail on a version PyPI will not accept, rather than at upload time."""
    if "+" in version and not allow_local:
        local = version.split("+", 1)[1]
        raise SystemExit(
            f"Refusing to build {version}: PyPI rejects versions with a local segment (+{local}).\n"
            "Build from a tagged commit with no uncommitted changes, or pass --allow-local-version "
            "to build anyway (the artifacts cannot be uploaded to PyPI)."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the Steam Deck variant of the PyTrain package",
        epilog="Unrecognized arguments are passed on to 'python -m build'",
    )
    parser.add_argument(
        "-o",
        "--outdir",
        default=DEFAULT_OUTDIR,
        help=f"directory the distributions are written to (default: {DEFAULT_OUTDIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write the overridden pyproject.toml to stdout and exit without building",
    )
    parser.add_argument(
        "--allow-local-version",
        action="store_true",
        help="build even if the version carries a local segment, which PyPI will not accept",
    )
    args, build_args = parser.parse_known_args()

    overridden, deck = deck_pyproject()
    if args.dry_run:
        sys.stdout.write(overridden)
        return 0

    # read the version while the checkout is still pristine, see pristine_version()
    version = pristine_version()
    check_publishable(version, args.allow_local_version)

    outdir = Path(args.outdir)
    if not outdir.is_absolute():
        outdir = PROJECT_ROOT / outdir
    command = [sys.executable, "-m", "build", "--outdir", str(outdir), *build_args]

    print(f"Building {deck['name']} {version} into {outdir}")
    original = PYPROJECT.read_bytes()
    PYPROJECT.write_bytes(overridden.encode("utf-8"))
    try:
        return subprocess.call(command, cwd=PROJECT_ROOT, env=pretend_version_env(deck["name"], version))
    finally:
        PYPROJECT.write_bytes(original)
        print(f"Restored {PYPROJECT}")


if __name__ == "__main__":
    sys.exit(main())
