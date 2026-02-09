#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.pytrain.gui.accessories.accessory_gui as mod
from src.pytrain.gui.accessories.accessory_type import AccessoryType


# -----------------------------------------------------------------------------
# Test doubles
# -----------------------------------------------------------------------------


class DummyGui:
    instances: list["DummyGui"] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.destroy_complete = SimpleNamespace(wait=lambda timeout=None: True)
        DummyGui.instances.append(self)

    def join(self) -> None:
        return


class DummyEntry:
    key = "gas"
    accessory_type = AccessoryType.GAS_STATION

    @staticmethod
    def load_class() -> type:
        return DummyGui


class DummyRegistry:
    @staticmethod
    def bootstrap() -> None:
        return

    # noinspection PyUnusedLocal
    @staticmethod
    def get_definition(gui_type, variant):
        # title must be identical for both entries so AccessoryGui disambiguates labels
        return SimpleNamespace(variant=SimpleNamespace(title="Gas Station", image="gas.png"))


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """
    Keep the AccessoryGui thread from starting, and clear DummyGui instance tracking.
    """
    monkeypatch.setattr(mod.AccessoryGui, "start", lambda self: None, raising=True)
    DummyGui.instances.clear()
    yield
    DummyGui.instances.clear()


@pytest.fixture(autouse=True)
def _patch_catalog_and_registry(monkeypatch):
    """
    Patch catalog plus registry in BOTH modules that use them:
      - accessory_gui (menu building)
      - configured_accessory_set (strict loader calls AccessoryRegistry.get().bootstrap())
    """
    dummy_entry = DummyEntry()

    # Catalog resolve
    # noinspection PyUnusedLocal
    def fake_resolve(self, key: str):
        return dummy_entry

    monkeypatch.setattr(mod.AccessoryGuiCatalog, "resolve", fake_resolve, raising=True)

    # AccessoryGui uses AccessoryRegistry.get()
    monkeypatch.setattr(mod.AccessoryRegistry, "get", classmethod(lambda cls: DummyRegistry()), raising=True)

    # ConfiguredAccessorySet imports AccessoryRegistry too; patch it there as well
    monkeypatch.setattr(
        "src.pytrain.gui.accessories.configured_accessory_set.AccessoryRegistry.get",
        classmethod(lambda cls: DummyRegistry()),
        raising=True,
    )

    yield


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_loads_config_and_disambiguates_labels(tmp_path: Path) -> None:
    """
    When two configured accessories resolve to the same registry title,
    AccessoryGui should disambiguate using instance_id.
    """
    config = [
        {
            "gui": "gas",
            "type": "gas_station",
            "variant": "v1",
            "tmcc_ids": {"power": 7},
            "tmcc_id": 99,
            "instance_id": "A",
        },
        {
            "gui": "gas",
            "type": "gas_station",
            "variant": "v1",
            "tmcc_ids": {"power": 8},
            "instance_id": "B",
        },
    ]

    path = tmp_path / "accessory_config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    gui = mod.AccessoryGui(width=100, height=100, config_file=path)

    labels = gui.guis
    assert len(labels) == 2
    assert "Gas Station" in labels
    assert "Gas Station (B)" in labels
    assert "Gas Station (A)" not in labels  # current behavior: first stays plain


def test_uses_display_name_override(tmp_path: Path) -> None:
    """
    If display_name is provided, it becomes the menu label (no disambiguation needed).
    """
    config = [
        {
            "gui": "gas",
            "type": "gas_station",
            "variant": "v1",
            "tmcc_ids": {"power": 7},
            "instance_id": "X",
            "display_name": "My Custom Gas",
        }
    ]

    path = tmp_path / "accessory_config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    gui = mod.AccessoryGui(width=100, height=100, config_file=path)

    assert gui.guis == ["My Custom Gas"]


def test_missing_gui_raises(tmp_path: Path) -> None:
    """
    Entries missing 'gui' should raise a ValueError from AccessoryGui.
    (ConfiguredAccessorySet will load it fine as long as instance_id/type exist.)
    """
    config = [
        {
            "type": "gas_station",
            "variant": "v1",
            "instance_id": "A",
        }
    ]

    path = tmp_path / "accessory_config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="missing/invalid 'gui'"):
        mod.AccessoryGui(width=100, height=100, config_file=path)


def test_empty_config_raises(tmp_path: Path) -> None:
    """
    If there are zero configured accessories, AccessoryGui should raise.
    """
    path = tmp_path / "accessory_config.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(ValueError, match="no GUIs configured"):
        mod.AccessoryGui(width=100, height=100, config_file=path)
