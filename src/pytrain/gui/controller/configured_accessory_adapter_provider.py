#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
from threading import RLock

from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from ..accessories.configured_accessory import ConfiguredAccessory, ConfiguredAccessorySet
from ...utils.singleton import singleton

log = logging.getLogger(__name__)


@singleton
class ConfiguredAccessoryAdapterProvider:
    """
    Lazy provider for ConfiguredAccessoryAdapter objects.

    Key points:
      - does NOT read accessory_config.json (caller injects ConfiguredAccessorySet)
      - adapters are keyed by cfg.instance_id
      - adapters are created lazily (on demand)
      - maintains indexes:
          * instance_id -> ConfiguredAccessory
          * tmcc_id -> list[instance_id]
    """

    def __init__(self, configured_set: ConfiguredAccessorySet, host) -> None:
        """
        Args:
            configured_set: already-loaded ConfiguredAccessorySet
            host: EngineGui instance (used by ConfiguredAccessoryAdapter.host)
        """
        self._lock = RLock()

        self._configured = configured_set
        self._host = host

        # instance_id -> ConfiguredAccessory
        self._acc_by_instance_id: dict[str, ConfiguredAccessory] = {}

        # tmcc_id -> list[instance_id] (stable order: config order)
        self._instance_ids_by_tmcc_id: dict[int, list[str]] = {}

        # instance_id -> ConfiguredAccessoryAdapter (lazy cache)
        self._adapters: dict[str, ConfiguredAccessoryAdapter] = {}

        self.reindex(drop_adapters=True)

    # ---------------------------------------------------------------------
    # Injection / reindexing
    # ---------------------------------------------------------------------

    def set_host(self, host) -> None:
        """Swap EngineGui host (rare, but useful for tests)."""
        with self._lock:
            self._host = host
            # existing adapters still point at the old host; drop them.
            self._adapters.clear()

    def set_configured_set(self, configured_set: ConfiguredAccessorySet, *, drop_adapters: bool = True) -> None:
        """
        Swap ConfiguredAccessorySet (e.g., after reload elsewhere).
        """
        with self._lock:
            self._configured = configured_set
            self.reindex(drop_adapters=drop_adapters)

    def reindex(self, *, drop_adapters: bool = False) -> None:
        """
        Rebuild lookup indexes from the injected ConfiguredAccessorySet.

        This does not create adapters.
        """
        with self._lock:
            if drop_adapters:
                self._adapters.clear()

            accs = self._configured.configured_all()  # preserves config order

            acc_by_iid: dict[str, ConfiguredAccessory] = {}
            ids_by_tmcc: dict[int, list[str]] = {}

            for acc in accs:
                iid = acc.instance_id
                if not isinstance(iid, str) or not iid.strip():
                    raise ValueError(f"Configured accessory missing instance_id: {acc!r}")
                if iid in acc_by_iid:
                    raise ValueError(f"Duplicate instance_id in configured set: {iid!r}")

                acc_by_iid[iid] = acc

                # Index all TMCC ids referenced by this accessory (overall + operation ids)
                for tid in acc.tmcc_ids:
                    if isinstance(tid, int):
                        ids_by_tmcc.setdefault(tid, []).append(iid)

                if isinstance(acc.tmcc_id, int):
                    ids_by_tmcc.setdefault(acc.tmcc_id, []).append(iid)

            self._acc_by_instance_id = acc_by_iid
            self._instance_ids_by_tmcc_id = ids_by_tmcc

    # ---------------------------------------------------------------------
    # Core API (lazy adapter creation)
    # ---------------------------------------------------------------------

    def has(self, instance_id: str) -> bool:
        if not isinstance(instance_id, str) or not instance_id.strip():
            return False
        with self._lock:
            return instance_id in self._acc_by_instance_id

    def get(self, instance_id: str | ConfiguredAccessory) -> ConfiguredAccessoryAdapter:
        """
        Get (and lazily create) adapter by instance_id.
        """
        if isinstance(instance_id, ConfiguredAccessory):
            instance_id = instance_id.instance_id
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise KeyError("instance_id must be a non-empty string")

        with self._lock:
            cached = self._adapters.get(instance_id)
            if cached is not None:
                return cached

            acc = self._acc_by_instance_id.get(instance_id)
            if acc is None:
                raise KeyError(f"Unknown accessory instance_id: {instance_id!r}")

            adapter = ConfiguredAccessoryAdapter(cfg=acc, host=self._host)
            self._adapters[instance_id] = adapter
            return adapter

    def maybe_get(self, instance_id: str) -> ConfiguredAccessoryAdapter | None:
        try:
            return self.get(instance_id)
        except KeyError:
            return None

    def configured(self, instance_id: str) -> ConfiguredAccessory:
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise KeyError("instance_id must be a non-empty string")
        with self._lock:
            acc = self._acc_by_instance_id.get(instance_id)
            if acc is None:
                raise KeyError(f"Unknown accessory instance_id: {instance_id!r}")
            return acc

    # ---------------------------------------------------------------------
    # TMCC-centric queries (EngineGui-friendly)
    # ---------------------------------------------------------------------

    def instance_ids_for_tmcc_id(self, tmcc_id: int) -> tuple[str, ...]:
        """
        Returns instance_ids associated with this TMCC id (stable order).
        """
        if not isinstance(tmcc_id, int):
            return ()
        with self._lock:
            return tuple(self._instance_ids_by_tmcc_id.get(tmcc_id, ()))

    def adapters_for_tmcc_id(self, tmcc_id: int) -> list[ConfiguredAccessoryAdapter]:
        """
        Returns adapters that reference this TMCC id.
        Adapters are created lazily.
        """
        ids = self.instance_ids_for_tmcc_id(tmcc_id)
        return [self.get(iid) for iid in ids]

    # ---------------------------------------------------------------------
    # Label-based lookup (delegates to ConfiguredAccessorySet indexes)
    # ---------------------------------------------------------------------

    def configured_by_label_contains(self, text: str) -> list[ConfiguredAccessory]:
        """
        Case-insensitive substring match against resolved cfg.label (your disambiguated label).
        """
        return self._configured.configured_by_label_contains(text)

    def adapters_by_label_contains(self, text: str) -> list[ConfiguredAccessoryAdapter]:
        """
        Same as configured_by_label_contains(), but returns adapters (lazy-created).
        """
        accs = self.configured_by_label_contains(text)
        out: list[ConfiguredAccessoryAdapter] = []
        for acc in accs:
            if acc.instance_id:
                out.append(self.get(acc.instance_id))
        return out

    # ---------------------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------------------

    def all_instance_ids(self) -> tuple[str, ...]:
        """
        Stable, config-order listing of instance ids.
        """
        with self._lock:
            # _acc_by_instance_id is built in config order; preserve that order
            return tuple(self._acc_by_instance_id.keys())

    def drop_cached(self, instance_id: str) -> None:
        """
        Remove a cached adapter so it will be recreated on next get().
        Useful if you want to discard gui/overlay state.
        """
        if not isinstance(instance_id, str) or not instance_id.strip():
            return
        with self._lock:
            self._adapters.pop(instance_id, None)

    def drop_all_cached(self) -> None:
        """
        Clear all cached adapters.
        """
        with self._lock:
            self._adapters.clear()
