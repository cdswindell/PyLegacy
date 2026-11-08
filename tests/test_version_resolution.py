"""Resolve versions from the imported code even when another distribution is installed."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import pytrain


@pytest.fixture
def source_tree(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "checkout"
    package_dir = root / "src" / "pytrain"
    package_dir.mkdir(parents=True)
    (root / "pyproject.toml").touch()
    monkeypatch.setattr(pytrain, "__file__", str(package_dir / "__init__.py"))
    return root


@pytest.fixture
def bundled_version(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pytrain._version", SimpleNamespace(version="2.3.4"))


@pytest.mark.usefixtures("bundled_version")
@pytest.mark.parametrize("package", pytrain.PROGRAM_PACKAGES)
@pytest.mark.parametrize("git_file", [False, True], ids=["checkout", "worktree"])
def test_checkout_uses_live_git_version(source_tree, monkeypatch, tmp_path, package, git_file):
    git_path = source_tree / ".git"
    if git_file:
        git_path.write_text("gitdir: /another/location\n", encoding="utf-8")
    else:
        git_path.mkdir()

    def unrelated_metadata(name):
        if name == package:
            return "1.0.0"
        raise pytrain.PackageNotFoundError(name)

    calls = []

    def git_version(**kwargs):
        calls.append(kwargs)
        return "2.9.8.post0+gabc123"

    monkeypatch.setattr(pytrain.importlib.metadata, "version", unrelated_metadata)
    monkeypatch.setitem(sys.modules, "setuptools_scm", SimpleNamespace(get_version=git_version))
    monkeypatch.chdir(tmp_path)

    assert pytrain.source_root() == source_tree
    assert pytrain.installed_package() is None
    assert pytrain.is_package() is False
    assert pytrain.get_version() == "v2.9.8+"
    assert calls == [{"root": str(source_tree), "version_scheme": "only-version"}]


@pytest.mark.usefixtures("bundled_version")
def test_checkout_does_not_hide_git_failure(source_tree, monkeypatch):
    (source_tree / ".git").mkdir()
    monkeypatch.setattr(pytrain.importlib.metadata, "version", lambda _: "1.0.0")

    def git_version(**_kwargs):
        raise LookupError("No version tags")

    monkeypatch.setitem(sys.modules, "setuptools_scm", SimpleNamespace(get_version=git_version))

    with pytest.raises(LookupError, match="No version tags"):
        pytrain.get_version()


@pytest.mark.usefixtures("source_tree", "bundled_version")
def test_source_export_uses_its_bundled_version(monkeypatch):
    monkeypatch.setattr(pytrain.importlib.metadata, "version", lambda _: "1.0.0")
    monkeypatch.setitem(sys.modules, "setuptools_scm", None)

    assert pytrain.get_version() == "v2.3.4"
    assert pytrain.is_package() is False


@pytest.mark.usefixtures("bundled_version")
@pytest.mark.parametrize("package", pytrain.PROGRAM_PACKAGES)
def test_installed_code_uses_its_bundled_version(tmp_path, monkeypatch, package):
    # A process can be launched from a checkout while importing an installed wheel.
    (tmp_path / "src" / "pytrain").mkdir(parents=True)
    (tmp_path / "pyproject.toml").touch()
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pytrain, "__file__", str(tmp_path / "site-packages" / "pytrain" / "__init__.py"))

    def installed_metadata(name):
        if name == package:
            return "1.0.0"
        raise pytrain.PackageNotFoundError(name)

    monkeypatch.setattr(pytrain.importlib.metadata, "version", installed_metadata)
    monkeypatch.setitem(sys.modules, "setuptools_scm", None)

    assert pytrain.source_root() is None
    assert pytrain.installed_package() == package
    assert pytrain.is_package() is True
    assert pytrain.get_version() == "v2.3.4"


@pytest.mark.usefixtures("source_tree")
def test_source_export_without_version_does_not_use_unrelated_metadata(monkeypatch):
    monkeypatch.setattr(pytrain.importlib.metadata, "version", lambda _: "1.0.0")
    monkeypatch.setitem(sys.modules, "pytrain._version", None)

    with pytest.raises(ModuleNotFoundError, match="pytrain._version"):
        pytrain.get_version()
