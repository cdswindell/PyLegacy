#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
Every module of the LCS configuration feature must import relatively, and none of them
may import the pytrain package root.

The package's __init__ imports EngineGui -- and through it the LCS panel -- before
it defines anything of its own, so a module the package imports cannot import the package
back. It fails as a circular import at start-up, and the workaround of hiding the import
inside a function only moves the breakage out of sight, so the rule is checked here
instead.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

import src.pytrain.cli.lcs as cli_lcs
import src.pytrain.gui.controller.lcs_config_panel as lcs_config_panel
import src.pytrain.gui.controller.lcs_device_registry as lcs_device_registry
import src.pytrain.gui.controller.lcs_gui as lcs_gui
import src.pytrain.gui.controller.lcs_id_map as lcs_id_map
import src.pytrain.gui.controller.lcs_sequence_builder as lcs_sequence_builder
import src.pytrain.utils.host_info as host_info

LCS_MODULES = (
    cli_lcs,
    lcs_config_panel,
    lcs_device_registry,
    lcs_gui,
    lcs_id_map,
    lcs_sequence_builder,
)


def _package_root(module: ModuleType) -> str:
    """The dotted name of the pytrain package itself, as this run imported it."""
    parts = module.__name__.split(".")
    return ".".join(parts[: parts.index("pytrain") + 1])


def _resolved_targets(module: ModuleType) -> list[tuple[int, str]]:
    """Every module a source file imports, as (line, absolute dotted name)."""
    package = module.__name__.split(".")[:-1]
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    targets: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                targets.append((node.lineno, node.module or ""))
                continue
            base = package[: len(package) - (node.level - 1)]
            targets.append((node.lineno, ".".join(base + ([node.module] if node.module else []))))
    return targets


@pytest.mark.parametrize("module", LCS_MODULES, ids=lambda m: m.__name__)
def test_no_lcs_module_imports_the_package_root(module: ModuleType) -> None:
    root = _package_root(module)
    offenders = [(line, target) for line, target in _resolved_targets(module) if target == root]

    assert not offenders, f"{module.__name__} imports the {root} package root at line(s) {offenders}"


@pytest.mark.parametrize("module", LCS_MODULES, ids=lambda m: m.__name__)
def test_every_lcs_project_import_is_relative(module: ModuleType) -> None:
    # An absolute "pytrain..." import binds the feature to one installed layout and, from
    # inside the package, reaches the root __init__ on the way in.
    root = _package_root(module)
    package = module.__name__.split(".")[:-1]
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders.extend(
                (node.lineno, alias.name) for alias in node.names if alias.name.split(".")[0] in {"pytrain", "src"}
            )
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level == 0 and name.split(".")[0] in {"pytrain", "src"}:
                offenders.append((node.lineno, name))
            elif node.level > len(package):
                offenders.append((node.lineno, f"{'.' * node.level}{name}"))

    assert not offenders, f"{module.__name__} does not import {root} relatively at line(s) {offenders}"


@pytest.mark.parametrize("module", LCS_MODULES, ids=lambda m: m.__name__)
def test_every_lcs_project_import_stays_inside_the_package(module: ModuleType) -> None:
    root = _package_root(module)
    stray = [
        (line, target)
        for line, target in _resolved_targets(module)
        if target.startswith(f"{root}.") is False and target.split(".")[0] in {"pytrain", "src"}
    ]

    assert not stray, f"{module.__name__} imports outside {root} at line(s) {stray}"


def test_the_panel_takes_is_linux_from_the_leaf_module() -> None:
    # host_info imports nothing of PyTrain's but .singleton, so the panel can import it at
    # module scope; the package root cannot be imported at all from here.
    assert lcs_config_panel.is_linux is host_info.is_linux


def test_the_package_root_re_exports_the_same_is_linux() -> None:
    # Anything outside the package -- and the CLI modules that already do it -- keeps
    # working, and there is only one definition of what "Linux" means.
    import src.pytrain as pytrain

    assert pytrain.is_linux is host_info.is_linux
