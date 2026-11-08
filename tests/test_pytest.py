import sys
from pathlib import Path
from types import ModuleType

import setuptools_scm

import src.pytrain as pytrain
from .test_base import TestBase


class TestPyTrain(TestBase):
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
            pytrain.importlib.metadata,
            "version",
            lambda _: (_ for _ in ()).throw(pytrain.PackageNotFoundError),
        )

        def fake_git_version(**kwargs):
            assert kwargs["root"] == str(Path(pytrain.__file__).resolve().parents[2])
            assert kwargs["version_scheme"] == "only-version"
            return "2.3.4+gabc123.d20260505"

        monkeypatch.setattr(setuptools_scm, "get_version", fake_git_version)

        assert pytrain.get_version() == "v2.3.4+"
