#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Optional

from .accessories.accessory_type import AccessoryType


def _norm(s: str) -> str:
    return s.lower().strip().replace("'", "").replace("-", "").replace("_", "")


@dataclass(frozen=True)
class GuiCatalogEntry:
    """
    Maps an alias (e.g. 'milk') to a GUI class, optionally tied to an AccessoryType.

    - module: module to import lazily (relative to pytrain.gui)
    - attr: class name in that module
    - accessory_type: set for registry-backed GUIs, None for legacy GUIs
    """

    key: str
    module: str
    attr: str
    accessory_type: Optional[AccessoryType] = None

    def load_class(self) -> type:
        mod = import_module(self.module, package=__package__)
        return getattr(mod, self.attr)


class AccessoryGuiCatalog:
    """
    Lazy resolver from short string keys ('milk', 'gas', etc.) to GUI classes.

    Keeps AccessoryGui small and avoids importing every GUI module up front.
    """

    def __init__(self) -> None:
        # NOTE: module strings are relative to 'pytrain.gui'
        self._entries: dict[str, GuiCatalogEntry] = {}

        # ---- Legacy GUIs (no AccessoryType required; still have get_variant) ----
        self.register(GuiCatalogEntry("backhoe", ".backhoe_gui", "BackhoeGui"))
        self.register(GuiCatalogEntry("depot", ".freight_depot_gui", "FreightDepotGui"))
        self.register(GuiCatalogEntry("smoke", ".smoke_fluid_loader_gui", "SmokeFluidLoaderGui"))

        # ---- Registry-backed GUIs (AccessoryType present; no get_variant needed) ----
        self.register(GuiCatalogEntry("control", ".control_tower_gui", "ControlTowerGui", AccessoryType.CONTROL_TOWER))
        self.register(GuiCatalogEntry("culvert", ".culvert_gui", "CulvertGui", AccessoryType.CULVERT_HANDLER))
        self.register(GuiCatalogEntry("fire", ".fire_station_gui", "FireStationGui", AccessoryType.FIRE_STATION))
        self.register(GuiCatalogEntry("gas", ".gas_station_gui", "GasStationGui", AccessoryType.GAS_STATION))
        self.register(GuiCatalogEntry("hobby", ".hobby_shop_gui", "HobbyShopGui", AccessoryType.HOBBY_SHOP))
        self.register(GuiCatalogEntry("milk", ".milk_loader_gui", "MilkLoaderGui", AccessoryType.MILK_LOADER))
        self.register(GuiCatalogEntry("playground", ".playground_gui", "PlaygroundGui", AccessoryType.PLAYGROUND))
        # self.register(
        #     GuiCatalogEntry(
        #         "smoke",
        #         ".smoke_fluid_loader_gui",
        #         "SmokeFluidLoaderGui",
        #         AccessoryType.SMOKE_FLUID_LOADER,
        #     )
        # )
        self.register(GuiCatalogEntry("station", ".station_gui", "StationGui", AccessoryType.STATION))

    def register(self, entry: GuiCatalogEntry) -> None:
        nk = _norm(entry.key)
        if nk in self._entries:
            raise ValueError(f"Duplicate AccessoryGuiCatalog key: {entry.key}")
        self._entries[nk] = entry

    def resolve(self, key: str) -> GuiCatalogEntry:
        """
        Resolve by exact or substring match (keeps your old behavior).
        """
        if not isinstance(key, str):
            raise ValueError(f"Invalid GUI key: {key}")

        nk = _norm(key)

        # exact
        if nk in self._entries:
            return self._entries[nk]

        # substring match (legacy behavior)
        for k, entry in self._entries.items():
            if nk in k:
                return entry

        raise ValueError(f"Invalid GUI key: {key}")
