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
import src.pytrain.gui.accessories.configured_accessory as ca_mod
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
        # Force identical title/image so duplicate-label disambiguation is exercised.
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
def _patch_registry_and_catalog(monkeypatch):
    """
    Patch the *actual* symbols used by configured_accessory.py (no broad exceptions).

    - ConfiguredAccessorySet constructs AccessoryRegistry.get() and calls bootstrap()
    - ConfiguredAccessory calls catalog.resolve(gui_key).load_class()
    """
    # AccessoryRegistry.get() used inside configured_accessory.py
    monkeypatch.setattr(ca_mod.AccessoryRegistry, "get", classmethod(lambda cls: DummyRegistry()), raising=True)

    dummy_entry = DummyEntry()

    # AccessoryGuiCatalog.resolve() used inside configured_accessory.py
    # noinspection PyUnusedLocal
    def fake_resolve(self, key: str):
        return dummy_entry

    monkeypatch.setattr(ca_mod.AccessoryGuiCatalog, "resolve", fake_resolve, raising=True)

    yield


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_loads_config_and_disambiguates_labels(tmp_path: Path) -> None:
    """
    When two configured accessories resolve to the same registry title,
    ConfiguredAccessorySet.gui_specs() disambiguates duplicates using instance_id.
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
    # New behavior: both duplicates get suffixed (because both have instance_id)
    assert "Gas Station (A)" in labels
    assert "Gas Station (B)" in labels
    assert "Gas Station" not in labels


def test_uses_display_name_override(tmp_path: Path) -> None:
    """
    If display_name is provided, it becomes the menu label.
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
    Entries missing 'gui' should raise a ValueError when building GUI specs.
    (The loader only requires instance_id/type; GUI construction requires 'gui'.)
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

    with pytest.raises(ValueError, match=r"missing required 'gui'"):
        mod.AccessoryGui(width=100, height=100, config_file=path)


def test_empty_config_raises(tmp_path: Path) -> None:
    """
    If there are zero configured accessories, AccessoryGui should raise.
    """
    path = tmp_path / "accessory_config.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(ValueError, match="no GUIs configured"):
        mod.AccessoryGui(width=100, height=100, config_file=path)
