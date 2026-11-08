from pathlib import Path

from src.pytrain.gui.accessories.configured_accessory import ConfiguredAccessorySet


def test_accessory_config_uses_shared_cache_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTRAIN_CACHE_DIR", str(tmp_path / ".var" / "cache"))
    monkeypatch.delenv("CONFIG_CACHE_DIR", raising=False)
    expected = tmp_path / ".var" / "cache" / "config" / "accessory_config.json"
    assert ConfiguredAccessorySet.resolve_config_path(None) == expected
    expected.parent.mkdir(parents=True)
    expected.write_text("{}", encoding="utf-8")
    assert ConfiguredAccessorySet.resolve_config_path(None) == expected


def test_accessory_config_keeps_pi_lookup(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTRAIN_CACHE_DIR", raising=False)
    monkeypatch.delenv("CONFIG_CACHE_DIR", raising=False)
    assert ConfiguredAccessorySet.resolve_config_path(None) == tmp_path / "accessory_config.json"
    cached = tmp_path / "cache" / "config" / "accessory_config.json"
    cached.parent.mkdir(parents=True)
    cached.write_text("{}", encoding="utf-8")
    assert ConfiguredAccessorySet.resolve_config_path(None) == cached
    (tmp_path / "accessory_config.json").write_text("{}", encoding="utf-8")
    assert ConfiguredAccessorySet.resolve_config_path(None) == tmp_path / "accessory_config.json"


def test_explicit_config_path_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTRAIN_CACHE_DIR", str(tmp_path / "shared"))
    assert ConfiguredAccessorySet.resolve_config_path(Path("other/config.json")) == Path("other/config.json")
