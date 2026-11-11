import sys
from importlib import metadata
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import src.pytrain as pytrain
from .test_base import TestBase


class TestPyTrain(TestBase):
    @pytest.fixture(autouse=True)
    def clear_version_cache(self):
        pytrain.get_version.cache_clear()
        yield
        pytrain.get_version.cache_clear()

    def test_get_version(self):
        assert pytrain.get_version() is not None
        assert pytrain.get_version().startswith("v")

    def test_get_version_strips_package_local_metadata(self, monkeypatch):
        monkeypatch.setattr(pytrain, "source_root", lambda: None)
        bundled = ModuleType(f"{pytrain.__name__}._version")
        bundled.version = "2.3.4+local"
        monkeypatch.setitem(sys.modules, bundled.__name__, bundled)

        assert pytrain.get_version() == "v2.3.4+"

    def test_get_version_strips_git_local_metadata(self, monkeypatch):
        monkeypatch.setattr(
            metadata,
            "version",
            lambda _: (_ for _ in ()).throw(pytrain.PackageNotFoundError),
        )

        def fake_git_version(**kwargs):
            module_file = pytrain.__file__
            assert module_file is not None
            assert kwargs["root"] == str(Path(module_file).resolve().parents[2])
            assert kwargs["version_scheme"] == "only-version"
            return "2.3.4+gabc123.d20260505"

        monkeypatch.setitem(sys.modules, "setuptools_scm", SimpleNamespace(get_version=fake_git_version))

        assert pytrain.get_version() == "v2.3.4+"
