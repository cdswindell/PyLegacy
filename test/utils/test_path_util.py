#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# test/utils/path_utils_tests.py
import os
from pathlib import Path

from src.pytrain.utils.path_utils import EXCLUDE, find_dir, find_file


def norm(p: str) -> str:
    # Normalize to handle platform-specific separators and any mixed use of "/"
    return os.path.normpath(p) if p is not None else None


def test_find_installation_dir():
    result = find_dir("installation")
    assert norm(result).endswith(norm(os.path.join("src", "pytrain", "installation")))


def test_find_installation_files():
    result = find_file("pytrain.bash.template")
    assert norm(result).endswith(norm(os.path.join("src", "pytrain", "installation", "pytrain.bash.template")))

    result = find_file("pytrain.service.template")
    assert norm(result).endswith(norm(os.path.join("src", "pytrain", "installation", "pytrain.service.template")))


def test_find_dir_simple(tmp_path: Path):
    # tmp_path/
    #   a/
    #     b/
    #       target/
    a = tmp_path / "a" / "b" / "target"
    a.mkdir(parents=True)

    result = find_dir("target", (str(tmp_path),))
    assert norm(result) == norm(os.path.join(str(tmp_path / "a" / "b"), "target"))


def test_find_dir_skips_hidden_and_excluded_dirs(tmp_path: Path):
    # Create hidden and excluded dirs containing the target name
    hidden = tmp_path / ".hidden" / "target"
    hidden.mkdir(parents=True)
    excluded = tmp_path / "__pycache__" / "target"
    excluded.mkdir(parents=True)
    # Create a valid visible dir with target
    visible = tmp_path / "visible" / "target"
    visible.mkdir(parents=True)

    result = find_dir("target", (str(tmp_path),))
    assert norm(result) == norm(os.path.join(str(tmp_path / "visible"), "target"))


def test_find_file_simple(tmp_path: Path):
    # tmp_path/
    #   x/
    #     y/
    #       foo.txt
    p = tmp_path / "x" / "y"
    p.mkdir(parents=True)
    fpath = p / "foo.txt"
    fpath.write_text("hello")

    result = find_file("foo.txt", (str(tmp_path),))
    assert norm(result) == norm(str(fpath))


def test_find_file_skips_hidden_files(tmp_path: Path):
    # A hidden file should not be returned even if requested
    p = tmp_path / "data"
    p.mkdir()
    hidden_file = p / ".secret"
    hidden_file.write_text("secret")

    result = find_file(".secret", (str(tmp_path),))
    assert result is None


def test_find_file_skips_excluded_dirs(tmp_path: Path):
    # Put the same filename in an excluded dir and in a valid dir;
    # the one in excluded dir should be ignored.
    excluded_dir_name = "__pycache__"
    assert excluded_dir_name in EXCLUDE

    ex_dir = tmp_path / excluded_dir_name
    ex_dir.mkdir()
    (ex_dir / "sample.bin").write_bytes(b"\x00\x01")

    ok_dir = tmp_path / "ok"
    ok_dir.mkdir()
    ok_file = ok_dir / "sample.bin"
    ok_file.write_bytes(b"\x02\x03")

    result = find_file("sample.bin", (str(tmp_path),))
    assert norm(result) == norm(str(ok_file))


def test_find_dir_not_found(tmp_path: Path):
    (tmp_path / "a").mkdir()
    result = find_dir("does-not-exist", (str(tmp_path),))
    assert result is None


def test_find_file_not_found(tmp_path: Path):
    (tmp_path / "a").mkdir()
    result = find_file("nope.txt", (str(tmp_path),))
    assert result is None
