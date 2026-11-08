from pathlib import Path

from src.pytrain.utils.path_utils import cache_directory


def test_legacy_relative_cache_directory(monkeypatch):
    monkeypatch.delenv("PYTRAIN_CACHE_DIR", raising=False)
    monkeypatch.delenv("ENGINE_IMAGES_CACHE_DIR", raising=False)
    assert cache_directory("engine_images", "ENGINE_IMAGES_CACHE_DIR") == Path("cache/engine_images")


def test_unified_cache_root(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTRAIN_CACHE_DIR", str(tmp_path / ".var" / "cache"))
    monkeypatch.delenv("ENGINE_IMAGES_CACHE_DIR", raising=False)
    assert cache_directory("engine_images", "ENGINE_IMAGES_CACHE_DIR") == tmp_path / ".var" / "cache" / "engine_images"
    assert cache_directory("config", "CONFIG_CACHE_DIR") == tmp_path / ".var" / "cache" / "config"


def test_component_override_preserved(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTRAIN_CACHE_DIR", str(tmp_path / "shared"))
    monkeypatch.setenv("ENGINE_IMAGES_CACHE_DIR", str(tmp_path / "custom"))
    assert cache_directory("engine_images", "ENGINE_IMAGES_CACHE_DIR") == tmp_path / "custom"
