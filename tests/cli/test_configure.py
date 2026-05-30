from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.pytrain.cli import configure
from src.pytrain.cli.configure import Configure


class DummyRegistry:
    @staticmethod
    def get_spec(_accessory_type):
        return SimpleNamespace(operations=[])


def _config_payload() -> dict[str, object]:
    return {
        "schema": "pytrain.accessory_config.v1",
        "accessories": [
            {
                "gui": "gas",
                "type": "gas_station",
                "variant": "v1",
                "instance_id": "gas_v1_7",
            }
        ],
    }


def test_resolve_existing_path_prefers_top_level(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache" / "accessory_config"
    cache_dir.mkdir(parents=True)
    top_level = tmp_path / configure.DEFAULT_CONFIG_FILE
    cached = cache_dir / configure.DEFAULT_CONFIG_FILE
    top_level.write_text("{}", encoding="utf-8")
    cached.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert configure._resolve_existing_path(Path(configure.DEFAULT_CONFIG_FILE)) == Path(configure.DEFAULT_CONFIG_FILE)


def test_resolve_existing_path_falls_back_to_cache(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache" / "accessory_config"
    cache_dir.mkdir(parents=True)
    cached = cache_dir / configure.DEFAULT_CONFIG_FILE
    cached.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert configure._resolve_existing_path(Path(configure.DEFAULT_CONFIG_FILE)) == cached


def test_print_edit_target_reports_cache_file(tmp_path: Path, monkeypatch, capsys) -> None:
    cache_dir = tmp_path / "cache" / "accessory_config"
    cache_dir.mkdir(parents=True)
    cached = cache_dir / configure.DEFAULT_CONFIG_FILE
    cached.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    configure._print_edit_target(cached, Path(configure.DEFAULT_CONFIG_FILE))

    assert "Editing cache config file:" in capsys.readouterr().out


def test_copy_cache_to_local_keeps_cache_file(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache" / "accessory_config"
    cache_dir.mkdir(parents=True)
    cached = cache_dir / configure.DEFAULT_CONFIG_FILE
    cached.write_text('{"source": "cache"}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    copied = configure._copy_cache_to_local(Path(configure.DEFAULT_CONFIG_FILE))

    assert copied == tmp_path / configure.DEFAULT_CONFIG_FILE
    assert copied.read_text(encoding="utf-8") == '{"source": "cache"}'
    assert cached.exists()


def test_move_local_to_cache_removes_top_level_file(tmp_path: Path, monkeypatch) -> None:
    top_level = tmp_path / configure.DEFAULT_CONFIG_FILE
    top_level.write_text('{"source": "local"}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    moved = configure._move_local_to_cache(Path(configure.DEFAULT_CONFIG_FILE))

    assert moved == tmp_path / "cache" / "accessory_config" / configure.DEFAULT_CONFIG_FILE
    assert moved.read_text(encoding="utf-8") == '{"source": "local"}'
    assert not top_level.exists()


def test_copy_cache_to_local_command_line(tmp_path: Path, monkeypatch, capsys) -> None:
    cache_dir = tmp_path / "cache" / "accessory_config"
    cache_dir.mkdir(parents=True)
    cached = cache_dir / configure.DEFAULT_CONFIG_FILE
    cached.write_text('{"source": "cache"}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    Configure(["--copy-cache-to-local"])

    assert (tmp_path / configure.DEFAULT_CONFIG_FILE).read_text(encoding="utf-8") == '{"source": "cache"}'
    assert "Copied cache config to top level:" in capsys.readouterr().out


def test_copy_cache_to_local_requires_force_to_overwrite(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache" / "accessory_config"
    cache_dir.mkdir(parents=True)
    (cache_dir / configure.DEFAULT_CONFIG_FILE).write_text('{"source": "cache"}', encoding="utf-8")
    (tmp_path / configure.DEFAULT_CONFIG_FILE).write_text('{"source": "local"}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileExistsError):
        configure._copy_cache_to_local(Path(configure.DEFAULT_CONFIG_FILE))


def test_interactive_move_local_to_shared_cache(tmp_path: Path, monkeypatch) -> None:
    payload = _config_payload()
    top_level = tmp_path / configure.DEFAULT_CONFIG_FILE
    top_level.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    answers = iter(["s", "a"])
    monkeypatch.setattr(configure, "_ask", lambda _prompt, default=None: next(answers))

    resolved, existing = configure._startup_existing_file_flow(
        Path(configure.DEFAULT_CONFIG_FILE),
        registry=DummyRegistry(),
    )

    assert resolved == tmp_path / "cache" / "accessory_config" / configure.DEFAULT_CONFIG_FILE
    assert existing == payload["accessories"]
    assert resolved.exists()
    assert not top_level.exists()


def test_interactive_prompt_hides_cache_copy_when_cache_file_missing(tmp_path: Path, monkeypatch) -> None:
    top_level = tmp_path / configure.DEFAULT_CONFIG_FILE
    top_level.write_text(json.dumps(_config_payload()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    prompts: list[str] = []

    # noinspection PyUnusedLocal
    def fake_ask(prompt: str, *, default: str | None = None) -> str:
        prompts.append(prompt)
        return "a"

    monkeypatch.setattr(configure, "_ask", fake_ask)

    configure._startup_existing_file_flow(Path(configure.DEFAULT_CONFIG_FILE), registry=DummyRegistry())

    assert "copy cache to (L)ocal" not in prompts[0]
    assert "move local to (S)hared cache" in prompts[0]


def test_interactive_prompt_hides_cache_move_when_local_file_missing(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache" / "accessory_config"
    cache_dir.mkdir(parents=True)
    (cache_dir / configure.DEFAULT_CONFIG_FILE).write_text(json.dumps(_config_payload()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    prompts: list[str] = []

    # noinspection PyUnusedLocal
    def fake_ask(prompt: str, *, default: str | None = None) -> str:
        prompts.append(prompt)
        return "a"

    monkeypatch.setattr(configure, "_ask", fake_ask)

    configure._startup_existing_file_flow(Path(configure.DEFAULT_CONFIG_FILE), registry=DummyRegistry())

    assert "copy cache to (L)ocal" in prompts[0]
    assert "move local to (S)hared cache" not in prompts[0]
