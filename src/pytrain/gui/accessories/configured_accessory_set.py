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
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .accessory_registry import AccessoryRegistry
from .accessory_type import AccessoryType
from ...utils.path_utils import find_file
from ...utils.singleton import singleton

log = logging.getLogger(__name__)

DEFAULT_CONFIG_FILE = "accessory_config.json"


@dataclass(frozen=True)
class ConfigVerificationResult:
    valid: bool
    issue_count: int
    issues: tuple[str, ...]


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
    def from_file(
        cls,
        path: str | Path | None = None,
        validate: bool = True,
        verify: bool = False,
    ) -> ConfiguredAccessorySet:
        """
        Load accessory configuration from JSON and return the singleton instance.

        If no path is provided:
          - use DEFAULT_CONFIG_FILE
          - resolve via find_file if necessary
        """
        inst = cls()
        inst._load(path, validate=validate, verify=verify)
        return inst

    def _load(
        self,
        path: str | Path | None,
        *,
        validate: bool = True,
        verify: bool = False,
    ) -> None:
        """
        Load accessory configuration from JSON.

        Rules:
          - Missing file → valid empty configuration
          - Existing file must be valid JSON
          - JSON must be:
              * dict with 'accessories': list[dict], OR
              * list[dict]
          - Each accessory entry must minimally contain:
              * instance_id (str)
              * type (str)

        Any violation raises immediately.
        """
        registry = AccessoryRegistry.get()
        registry.bootstrap()

        # ------------------------------------------------------------------
        # Resolve path
        # ------------------------------------------------------------------
        if path is None:
            path = DEFAULT_CONFIG_FILE

        if isinstance(path, str):
            resolved = find_file(path)
            self._path = Path(resolved) if resolved else Path(path)
        else:
            self._path = path

        # ------------------------------------------------------------------
        # Missing file → valid empty state
        # ------------------------------------------------------------------
        if not self._path.exists():
            self._raw = []
            self._rebuild_indexes(validate=validate, verify=verify)
            return

        # ------------------------------------------------------------------
        # Parse JSON (strict)
        # ------------------------------------------------------------------
        try:
            text = self._path.read_text(encoding="utf-8")
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in accessory config '{self._path}': {e.msg} (line {e.lineno})") from e
        except OSError as e:
            raise RuntimeError(f"Failed to read accessory config '{self._path}': {e}") from e

        # ------------------------------------------------------------------
        # Normalize top-level shape
        # ------------------------------------------------------------------
        if isinstance(obj, dict):
            accessories = obj.get("accessories")
            if accessories is None:
                raise ValueError(f"{self._path}: missing required key 'accessories'")
            if not isinstance(accessories, list):
                raise ValueError(f"{self._path}: 'accessories' must be a list")
        elif isinstance(obj, list):
            accessories = obj
        else:
            raise ValueError(f"{self._path}: top-level JSON must be an object or list")

        # ------------------------------------------------------------------
        # Validate each accessory entry (structure only)
        # ------------------------------------------------------------------
        raw: list[dict[str, Any]] = []

        # Validates accessory structure; accumulates raw entries
        for i, acc in enumerate(accessories):
            if not isinstance(acc, dict):
                raise ValueError(f"{self._path}: accessories[{i}] must be an object")

            instance_id = acc.get("instance_id")
            acc_type = acc.get("type")

            if not isinstance(instance_id, str) or not instance_id.strip():
                raise ValueError(f"{self._path}: accessories[{i}].instance_id must be a non-empty string")

            if not isinstance(acc_type, str) or not acc_type.strip():
                raise ValueError(f"{self._path}: accessories[{i}].type must be a non-empty string")

            raw.append(acc)

        # ------------------------------------------------------------------
        # Commit + index
        # ------------------------------------------------------------------
        self._raw = raw
        self._rebuild_indexes(validate=validate, verify=verify)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    @staticmethod
    def _build_indexes(
        raw: list[dict[str, Any]],
        *,
        validate: bool,
        issues_out: list[str] | None,
    ) -> tuple[
        dict[str, dict[str, Any]],
        dict[AccessoryType, list[dict[str, Any]]],
        dict[int, list[dict[str, Any]]],
    ]:
        """
        Build indexes from raw accessory dicts.

        If validate=True, warnings are logged.
        If issues_out is provided, all warnings are also appended as formatted strings.
        """
        by_instance_id: dict[str, dict[str, Any]] = {}
        by_type: dict[AccessoryType, list[dict[str, Any]]] = {}
        by_tmcc_id: dict[int, list[dict[str, Any]]] = {}

        def _warn(msg: str, *args) -> None:
            if validate:
                log.warning(msg, *args)
            if issues_out is not None:
                try:
                    # Normal %-formatting path
                    issues_out.append(msg % args)
                except (TypeError, ValueError):
                    # Defensive fallback if formatting arguments don't match
                    issues_out.append(f"{msg} {args!r}")

        for acc in raw:
            if not isinstance(acc, dict):
                _warn("Skipping accessory entry: not a dict (%r)", acc)
                continue

            instance_id = acc.get("instance_id")
            if not isinstance(instance_id, str) or not instance_id.strip():
                _warn("Skipping accessory with invalid or missing instance_id: %r", acc)
                continue

            by_instance_id[instance_id] = acc

            # Type index
            type_val = acc.get("type")
            if not isinstance(type_val, str) or not type_val.strip():
                _warn("Accessory %s has missing or invalid 'type'; type indexing skipped", instance_id)
            else:
                key = type_val.strip().upper()
                try:
                    acc_type = AccessoryType[key]
                except KeyError:
                    _warn("Accessory %s has unknown AccessoryType %r; type indexing skipped", instance_id, type_val)
                else:
                    by_type.setdefault(acc_type, []).append(acc)

            # TMCC ID index (overall)
            tmcc_id = acc.get("tmcc_id")
            if tmcc_id is not None and not isinstance(tmcc_id, int):
                _warn("Accessory %s has non-integer tmcc_id %r; ignoring", instance_id, tmcc_id)
            elif isinstance(tmcc_id, int):
                by_tmcc_id.setdefault(tmcc_id, []).append(acc)

            # TMCC IDs per operation
            tmcc_ids = acc.get("tmcc_ids")
            if tmcc_ids is not None and not isinstance(tmcc_ids, dict):
                _warn(
                    "Accessory %s has invalid tmcc_ids (expected dict, got %s); ignoring",
                    instance_id,
                    type(tmcc_ids).__name__,
                )
            elif isinstance(tmcc_ids, dict):
                for op_key, v in tmcc_ids.items():
                    if not isinstance(v, int):
                        _warn(
                            "Accessory %s operation %r has non-integer TMCC id %r; ignoring",
                            instance_id,
                            op_key,
                            v,
                        )
                        continue
                    by_tmcc_id.setdefault(v, []).append(acc)

        return by_instance_id, by_type, by_tmcc_id

    def _rebuild_indexes(self, *, validate: bool = True, verify: bool = False) -> None:
        issues: list[str] | None = [] if verify else None

        by_instance_id, by_type, by_tmcc_id = self._build_indexes(
            self._raw,
            validate=validate,
            issues_out=issues,
        )

        self._by_instance_id = by_instance_id
        self._by_type = by_type
        self._by_tmcc_id = by_tmcc_id

        if verify and issues:
            log.warning("Accessory config verification found %d issue(s)", len(issues))
            for msg in issues[:10]:
                log.warning("  - %s", msg)
            if len(issues) > 10:
                log.warning("  ... %d more", len(issues) - 10)

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

    def verify_config(self) -> ConfigVerificationResult:
        """
        Verify the currently loaded accessory configuration.

        - Does NOT modify self._raw
        - Does NOT rebuild indexes on the instance
        - Returns a structured summary of issues
        """
        issues: list[str] = []
        raw_snapshot = list(self._raw)

        # Build indexes purely, collecting issues without logging unless you want it.
        self._build_indexes(
            raw_snapshot,
            validate=False,  # don't log during verify_config()
            issues_out=issues,  # collect issues into the list
        )

        return ConfigVerificationResult(
            valid=(len(issues) == 0),
            issue_count=len(issues),
            issues=tuple(issues),
        )

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
