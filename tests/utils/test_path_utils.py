#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# tests/utils/test_path_utils.py
#
# Covers the indexed / pruned implementation of find_file / find_dir:
#   * resolution parity against a reference walk
#   * single-walk behavior via a counted os.walk
#   * miss caching (and the reset_path_index hook)
#   * the concrete-Path short-circuit
#   * the freshness escape hatch for non-default `places`
import os
from pathlib import Path

from src.pytrain.utils import path_utils
from src.pytrain.utils.path_utils import (
    EXCLUDE,
    find_dir,
    find_file,
    reset_path_index,
)


def norm(p: str | None) -> str | None:
    return os.path.normpath(p) if p is not None else None


def _reference_find_file(name: str, places) -> str | None:
    """Reference implementation mirroring the original first-match walk semantics.

    Deliberately does *not* apply virtualenv pruning; the trees used in the parity
    test contain no environment-style directories, so results must match exactly.
    """
    for d in places:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(os.fspath(d)):
            if root.startswith("./.") or root.startswith("./venv/"):
                continue
            root_path = Path(root).resolve()
            if any(p.startswith(".") or p in EXCLUDE for p in root_path.parts):
                continue
            for file in files:
                if file.startswith(".") or file in EXCLUDE:
                    continue
                if file == name:
                    return str(root_path / file)
    return None


def _make_tree(base: Path) -> None:
    (base / "a" / "b").mkdir(parents=True)
    (base / "c").mkdir(parents=True)
    (base / "a" / "b" / "foo.txt").write_text("foo")
    (base / "c" / "bar.txt").write_text("bar")
    # duplicate basename in two subtrees to exercise first-match ordering
    (base / "a" / "dup.txt").write_text("first")
    (base / "c" / "dup.txt").write_text("second")


def test_resolution_parity_against_reference(tmp_path: Path):
    reset_path_index()
    _make_tree(tmp_path)
    places = (str(tmp_path),)

    for name in ("foo.txt", "bar.txt", "dup.txt", "missing.txt"):
        assert norm(find_file(name, places)) == norm(_reference_find_file(name, places))


def test_first_match_ordering_across_places(tmp_path: Path):
    reset_path_index()
    root1 = tmp_path / "one"
    root2 = tmp_path / "two"
    root1.mkdir()
    root2.mkdir()
    (root1 / "shared.txt").write_text("one")
    (root2 / "shared.txt").write_text("two")

    # First place wins.
    assert norm(find_file("shared.txt", (str(root1), str(root2)))) == norm(str(root1 / "shared.txt"))
    # Reversing the order flips the winner.
    assert norm(find_file("shared.txt", (str(root2), str(root1)))) == norm(str(root2 / "shared.txt"))


def test_single_walk_for_default_places(tmp_path: Path, monkeypatch):
    reset_path_index()
    _make_tree(tmp_path)

    real_walk = os.walk
    calls = {"n": 0}

    def counting_walk(*args, **kwargs):
        calls["n"] += 1
        return real_walk(*args, **kwargs)

    # Point the default roots at our controlled tree and count top-level walks.
    monkeypatch.setattr(path_utils, "DEFAULT_PLACES", (str(tmp_path),))
    monkeypatch.setattr(path_utils.os, "walk", counting_walk)

    # Many file lookups against the default places must trigger exactly one walk.
    assert find_file("foo.txt", (str(tmp_path),)) is not None
    assert find_file("bar.txt", (str(tmp_path),)) is not None
    assert find_file("missing.txt", (str(tmp_path),)) is None
    assert find_file("dup.txt", (str(tmp_path),)) is not None
    assert calls["n"] == 1

    # find_dir builds its own (directory) index: one additional walk, then cached.
    assert find_dir("a", (str(tmp_path),)) is not None
    assert find_dir("c", (str(tmp_path),)) is not None
    assert calls["n"] == 2


def test_miss_is_cached_and_reset_hook(tmp_path: Path, monkeypatch):
    reset_path_index()
    (tmp_path / "seed").mkdir()
    monkeypatch.setattr(path_utils, "DEFAULT_PLACES", (str(tmp_path),))

    # Miss populates the index; the file created afterward is not seen (cached).
    assert find_file("late.txt", (str(tmp_path),)) is None
    (tmp_path / "late.txt").write_text("late")
    assert find_file("late.txt", (str(tmp_path),)) is None

    # Resetting the index re-walks and finds it.
    reset_path_index()
    assert norm(find_file("late.txt", (str(tmp_path),))) == norm(str(tmp_path / "late.txt"))


def test_non_default_places_are_fresh(tmp_path: Path):
    """The freshness escape hatch: non-default places re-walk every call."""
    reset_path_index()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    places = (Path.cwd(), cache_dir)  # prod_info-style, non-default

    assert find_file("engine.json", places) is None
    (cache_dir / "engine.json").write_text("{}")
    # No reset, no default places -> the freshly-written file is found immediately.
    assert norm(find_file("engine.json", places)) == norm(str(cache_dir / "engine.json"))


def test_concrete_path_short_circuit(tmp_path: Path):
    reset_path_index()
    f = tmp_path / "concrete.txt"
    f.write_text("x")

    # An existing concrete Path resolves directly, regardless of `places`.
    assert norm(find_file(f, (str(tmp_path / "nonexistent"),))) == norm(str(f.resolve()))

    d = tmp_path / "adir"
    d.mkdir()
    assert norm(find_dir(d, (str(tmp_path / "nonexistent"),))) == norm(str(d.resolve()))

    # A non-existing concrete Path falls through to the walk (and misses).
    assert find_file(tmp_path / "ghost.txt", (str(tmp_path),)) is None


def test_venv_style_dirs_are_pruned(tmp_path: Path, monkeypatch):
    """A site-packages tree under a recognized prefix is not searched."""
    reset_path_index()
    env_root = tmp_path / "env"
    site = env_root / "lib" / "site-packages"
    site.mkdir(parents=True)
    (site / "pkgfile.txt").write_text("pkg")

    # A genuine project asset with the same basename lives outside the env.
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "asset.txt").write_text("asset")

    monkeypatch.setattr(path_utils, "_VENV_ROOTS", {str(env_root.resolve())})

    # File buried in the pruned lib/site-packages is not found.
    assert find_file("pkgfile.txt", (str(tmp_path),)) is None
    # Legitimate project asset still resolves.
    assert norm(find_file("asset.txt", (str(tmp_path),))) == norm(str(proj / "asset.txt"))
