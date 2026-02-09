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
from typing import Any

from .accessory_gui import DEFAULT_CONFIG_FILE
from .accessory_registry import AccessoryRegistry
from .accessory_type import AccessoryType
from ...utils.path_utils import find_file
from ...utils.singleton import singleton


@singleton
class ConfiguredAccessorySet:
    """
    Singleton container for all configured accessories loaded from accessory_config.json.

    Responsibilities:
      - load + parse config file
      - build fast lookup indexes
      - provide read-only access for EngineGui
    """

    def __init__(self) -> None:
        self._path: Path | None = None
        self._raw: list[dict[str, Any]] = []

        # Indexes
        self._by_instance_id: dict[str, dict[str, Any]] = {}
        self._by_type: dict[AccessoryType, list[dict[str, Any]]] = {}
        self._by_tmcc_id: dict[int, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Construction / loading
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> ConfiguredAccessorySet:
        """
        Load accessory configuration from JSON and return the singleton instance.

        If no path is provided:
          - use DEFAULT_CONFIG_FILE
          - resolve via find_file if necessary
        """
        inst = cls()
        inst._load(path)
        return inst

    def _load(self, path: str | Path | None) -> None:
        """Loads accessory configuration from file or default path"""
        registry = AccessoryRegistry.get()
        registry.bootstrap()

        # Resolve path
        if path is None:
            path = DEFAULT_CONFIG_FILE

        if isinstance(path, str):
            resolved = find_file(path)
            self._path = Path(resolved) if resolved else Path(path)
        else:
            self._path = path

        if not self._path.exists():
            # Valid empty state
            self._raw = []
            self._rebuild_indexes()
            return

        try:
            obj = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            raise RuntimeError(f"Failed to read accessory config: {self._path}: {e}") from e

        if isinstance(obj, dict):
            accessories = obj.get("accessories", [])
            if not isinstance(accessories, list):
                raise ValueError("accessory_config.json: 'accessories' must be a list")
        elif isinstance(obj, list):
            accessories = obj
        else:
            raise ValueError("accessory_config.json: invalid JSON shape")

        # Minimal structural filtering (deeper validation can come later)
        self._raw = [a for a in accessories if isinstance(a, dict) and "instance_id" in a and "type" in a]

        self._rebuild_indexes()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _rebuild_indexes(self) -> None:
        self._by_instance_id.clear()
        self._by_type.clear()
        self._by_tmcc_id.clear()

        for acc in self._raw:
            instance_id = acc["instance_id"]
            self._by_instance_id[instance_id] = acc

            # Type index
            try:
                acc_type = AccessoryType[acc["type"].upper()]
            except Exception:
                continue

            self._by_type.setdefault(acc_type, []).append(acc)

            # TMCC ID index (overall)
            if isinstance(acc.get("tmcc_id"), int):
                self._by_tmcc_id.setdefault(acc["tmcc_id"], []).append(acc)

            # TMCC IDs per operation
            tmcc_ids = acc.get("tmcc_ids")
            if isinstance(tmcc_ids, dict):
                for v in tmcc_ids.values():
                    if isinstance(v, int):
                        self._by_tmcc_id.setdefault(v, []).append(acc)

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path | None:
        return self._path

    def all(self) -> list[dict[str, Any]]:
        """Return all configured accessories (raw dicts)."""
        return list(self._raw)

    def by_instance_id(self, instance_id: str) -> dict[str, Any] | None:
        return self._by_instance_id.get(instance_id)

    def by_type(self, acc_type: AccessoryType) -> list[dict[str, Any]]:
        return list(self._by_type.get(acc_type, []))

    def by_tmcc_id(self, tmcc_id: int) -> list[dict[str, Any]]:
        """
        Return all configured accessories that reference this TMCC ID.
        """
        return list(self._by_tmcc_id.get(tmcc_id, []))

    def has_any(self) -> bool:
        return bool(self._raw)

    # ------------------------------------------------------------------
    # Debug / introspection
    # ------------------------------------------------------------------

    def summary(self) -> str:
        return (
            f"ConfiguredAccessorySet("
            f"count={len(self._raw)}, "
            f"types={len(self._by_type)}, "
            f"tmcc_ids={len(self._by_tmcc_id)})"
        )
