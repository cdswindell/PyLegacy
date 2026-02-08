from __future__ import annotations

import json
from threading import Event
from types import SimpleNamespace

import pytest

from src.pytrain.gui.accessories import accessory_gui as mod
from src.pytrain.gui.accessories.accessory_type import AccessoryType


class DummyGui:
    instances: list["DummyGui"] = []

    def __init__(
        self,
        *,
        variant: str | None = None,
        power: int | None = None,
        tmcc_id: int | None = None,
        instance_id: str | None = None,
        display_name: str | None = None,
        aggregator=None,
    ) -> None:
        self.variant = variant
        self.power = power
        self.tmcc_id = tmcc_id
        self.instance_id = instance_id
        self.display_name = display_name
        self.aggregator = aggregator
        self.destroy_complete = Event()
        DummyGui.instances.append(self)

    def join(self, timeout=None) -> None:
        return


@pytest.fixture(autouse=True)
def patch_accessory_gui(monkeypatch):
    DummyGui.instances.clear()

    class DummyEntry:
        accessory_type = AccessoryType.GAS_STATION

        @staticmethod
        def load_class() -> type:
            return DummyGui

    dummy_entry = DummyEntry()

    # noinspection PyUnusedLocal
    def fake_resolve(self, key: str) -> DummyEntry:
        return dummy_entry

    class DummyRegistry:
        @staticmethod
        def bootstrap() -> None:
            return

        # noinspection PyUnusedLocal
        @staticmethod
        def get_definition(gui_type, variant):
            return SimpleNamespace(variant=SimpleNamespace(title="Gas Station", image="gas.png"))

    monkeypatch.setattr(mod.AccessoryGuiCatalog, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(mod.AccessoryRegistry, "instance", classmethod(lambda cls: DummyRegistry()), raising=True)
    monkeypatch.setattr(mod, "find_file", lambda path: str(path), raising=True)
    monkeypatch.setattr(mod.AccessoryGui, "start", lambda self: None, raising=True)

    yield

    DummyGui.instances.clear()


def test_loads_config_and_disambiguates_labels(tmp_path) -> None:
    config = [
        {"gui": "gas", "variant": "v1", "tmcc_ids": {"power": 7}, "tmcc_id": 99},
        {"gui": "gas", "variant": "v1", "tmcc_ids": {"power": 8}, "instance_id": "A"},
    ]
    path = tmp_path / "accessory_config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    gui = mod.AccessoryGui(width=100, height=100, config_file=path)

    assert gui.guis == ["Gas Station", "Gas Station (A)"]
    assert gui._guis["Gas Station"][2]["power"] == 7
    assert gui._guis["Gas Station"][2]["tmcc_id"] == 99
    assert gui._guis["Gas Station (A)"][2]["instance_id"] == "A"
