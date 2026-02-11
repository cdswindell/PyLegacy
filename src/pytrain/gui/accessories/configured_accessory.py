#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .accessory_gui_catalog import AccessoryGuiCatalog
from .accessory_registry import AccessoryRegistry
from .accessory_type import AccessoryType
from ...utils.path_utils import find_file
from ...utils.singleton import singleton

log = logging.getLogger(__name__)

DEFAULT_CONFIG_FILE = "accessory_config.json"


# -----------------------------------------------------------------------------
# Verification result
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigVerificationResult:
    valid: bool
    issue_count: int
    issues: tuple[str, ...]


# -----------------------------------------------------------------------------
# GUI construction spec + helper
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GuiCtorSpec:
    """
    Construction spec for a configured accessory GUI.

    EngineGui / PopupManager can hold onto this and instantiate lazily.
    Standalone AccessoryGui can also consume this spec directly.
    """

    label: str
    title: str
    image_path: str | None
    gui_class: type
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    accessory_type: AccessoryType
    variant: str | None
    instance_id: str | None


def _filter_kwargs_for_ctor(cls: type, kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    Filter kwargs down to only those accepted by cls.__init__ (excluding self).
    This lets config JSON include optional fields without breaking older GUIs.
    """
    sig = inspect.signature(cls.__init__)
    params = sig.parameters
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if accepts_kwargs:
        return dict(kwargs)

    allowed = {name for name in params.keys() if name != "self"}
    return {k: v for k, v in kwargs.items() if k in allowed}


def instantiate_gui(spec: GuiCtorSpec, *, extra_kwargs: Mapping[str, Any] | None = None) -> Any:
    """
    Instantiate a GUI from a GuiCtorSpec, optionally merging extra kwargs
    (e.g., aggregator=..., host=..., popup_manager=..., etc.)
    """
    kwargs = dict(spec.kwargs)
    if extra_kwargs:
        kwargs.update(extra_kwargs)

    # ✅ NEW: filter again after merging extra kwargs (width/height/etc. may be injected)
    kwargs = _filter_kwargs_for_ctor(spec.gui_class, kwargs)

    # Validate signature before calling (cleaner errors)
    sig = inspect.signature(spec.gui_class.__init__)
    try:
        sig.bind(None, *spec.args, **kwargs)  # fake self
    except TypeError as e:
        raise TypeError(f"{spec.gui_class.__name__}{sig}: {e}") from None

    return spec.gui_class(*spec.args, **kwargs)


# -----------------------------------------------------------------------------
# ConfiguredAccessory wrapper
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConfiguredAccessory:
    """
    Thin wrapper around a single configured accessory entry (raw dict).

    Exposes what EngineGui/PopupManager need:
      - stable title + image (via AccessoryRegistry definition)
      - user label for menus (display_name preferred)
      - tmcc_ids: tuple[int, ...] across overall and per-operation
      - build_gui_spec(): returns GuiCtorSpec to instantiate lazily
    """

    raw: dict[str, Any]
    registry: AccessoryRegistry
    catalog: AccessoryGuiCatalog

    @staticmethod
    def _get_str(d: Mapping[str, Any], key: str) -> str | None:
        v = d.get(key)
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return None

    @staticmethod
    def _get_int(d: Mapping[str, Any], key: str) -> int | None:
        v = d.get(key)
        return int(v) if isinstance(v, int) else None

    @property
    def instance_id(self) -> str | None:
        return self._get_str(self.raw, "instance_id")

    @property
    def display_name(self) -> str | None:
        return self._get_str(self.raw, "display_name")

    @property
    def gui_key(self) -> str | None:
        return self._get_str(self.raw, "gui")

    @property
    def variant(self) -> str | None:
        return self._get_str(self.raw, "variant")

    @property
    def accessory_type(self) -> AccessoryType:
        """
        Prefer GUI catalog mapping (gui -> AccessoryType). Fall back to raw['type'].
        Raises ValueError if we can't determine the type.
        """
        if self.gui_key:
            entry = self.catalog.resolve(self.gui_key)
            if entry.accessory_type is None:
                raise ValueError(f"{self.gui_key}: missing AccessoryType in catalog entry")
            return entry.accessory_type

        t = self._get_str(self.raw, "type")
        if t:
            try:
                return AccessoryType[t.upper()]
            except KeyError:
                raise ValueError(f"Unknown AccessoryType: {t!r}") from None

        raise ValueError(f"Accessory config entry missing 'gui' and 'type': {self.raw!r}")

    @property
    def tmcc_id(self) -> int | None:
        return self._get_int(self.raw, "tmcc_id")

    @property
    def tmcc_ids(self) -> tuple[int, ...]:
        """
        All TMCC IDs referenced by this accessory, deduped, stable order:
          1) tmcc_id (overall) if present
          2) values from tmcc_ids dict in iteration order
        """
        out: list[int] = []
        seen: set[int] = set()

        overall = self.tmcc_id
        if isinstance(overall, int) and overall not in seen:
            out.append(overall)
            seen.add(overall)

        d = self.raw.get("tmcc_ids")
        if isinstance(d, dict):
            for _, v in d.items():
                if isinstance(v, int) and v not in seen:
                    out.append(int(v))
                    seen.add(int(v))

        return tuple(out)

    @property
    def definition(self):
        """
        Registry definition for this accessory type and optional variant.
        """
        return self.registry.get_definition(self.accessory_type, self.variant)

    @property
    def title(self) -> str:
        return self.definition.variant.title

    @property
    def image_path(self) -> str | None:
        # Use whatever your definition exposes. Adjust if your API differs.
        # Common patterns: definition.variant.image or definition.variant.primary_image
        img = getattr(self.definition.variant, "image", None) or getattr(self.definition.variant, "primary_image", None)
        if isinstance(img, str) and img.strip():
            return img
        return None

    @property
    def label(self) -> str:
        return self.display_name or self.title

    def build_gui_spec(self, *, disambiguate_with: str | None = None) -> GuiCtorSpec:
        """
        Build the lazy ctor spec.

        - Pulls gui class from AccessoryGuiCatalog (by gui key)
        - Applies variant + tmcc_id + tmcc_ids(op_key->int) -> ctor kwargs
        - Filters kwargs against ctor signature
        - Computes label (optionally disambiguated)
        """
        gui_key = self.gui_key
        if not gui_key:
            raise ValueError(f"{self.raw!r}: missing required 'gui' key")

        entry = self.catalog.resolve(gui_key)
        gui_class = entry.load_class()
        acc_type = self.accessory_type  # validates

        # Registry supplies stable title/image identity
        title = self.title
        image_path = self.image_path

        # Label: prefer display_name, else registry title; optionally disambiguate
        label = self.label
        if disambiguate_with:
            label = f"{label} ({disambiguate_with})"

        ctor_kwargs: dict[str, Any] = {}

        # variant is passed when ctors accept it
        if self.variant is not None:
            ctor_kwargs["variant"] = self.variant

        # tmcc_ids dict -> ctor kwargs (legacy behavior: keys become ctor kw names)
        tmcc_ids = self.raw.get("tmcc_ids")
        if tmcc_ids is not None:
            if not isinstance(tmcc_ids, dict):
                raise ValueError(f"{gui_key}: tmcc_ids must be a dict if present")
            for k, v in tmcc_ids.items():
                if not isinstance(k, str):
                    raise ValueError(f"{gui_key}: tmcc_ids key must be str, got {k!r}")
                if not isinstance(v, int):
                    raise ValueError(f"{gui_key}: tmcc_ids[{k!r}] must be int, got {v!r}")
                ctor_kwargs[k] = int(v)

        # overall tmcc_id (optional)
        tmcc_id_overall = self.tmcc_id
        if tmcc_id_overall is not None:
            ctor_kwargs["tmcc_id"] = int(tmcc_id_overall)

        # Optional metadata (only used if ctors accept them)
        if self.instance_id:
            ctor_kwargs["instance_id"] = self.instance_id
        if self.display_name:
            ctor_kwargs["display_name"] = self.display_name

        ctor_kwargs = _filter_kwargs_for_ctor(gui_class, ctor_kwargs)

        return GuiCtorSpec(
            label=label,
            title=title,
            image_path=image_path,
            gui_class=gui_class,
            args=(),
            kwargs=ctor_kwargs,
            accessory_type=acc_type,
            variant=self.variant,
            instance_id=self.instance_id,
        )

    def create_gui(self, *, aggregator: Any, extra_kwargs: Mapping[str, Any] | None = None) -> Any:
        spec = self.build_gui_spec()
        # IMPORTANT: only pass kwargs that GUI ctors accept (you already filter spec.kwargs)
        merged = {"aggregator": aggregator}
        if extra_kwargs:
            merged.update(extra_kwargs)
        return instantiate_gui(spec, extra_kwargs=merged)


# -----------------------------------------------------------------------------
# ConfiguredAccessorySet
# -----------------------------------------------------------------------------


@singleton
class ConfiguredAccessorySet:
    """
    Singleton container for all configured accessories loaded from accessory_config.json.

    Responsibilities:
      - load + parse config file
      - build fast lookup indexes
      - provide typed access (ConfiguredAccessory) + GUI ctor specs for EngineGui
    """

    def __init__(self) -> None:
        self._path: Path | None = None
        self._raw: list[dict[str, Any]] = []

        self._registry = AccessoryRegistry.get()
        self._catalog = AccessoryGuiCatalog()

        # Indexes over raw dicts
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
        self._registry.bootstrap()

        # Resolve path
        if path is None:
            path = DEFAULT_CONFIG_FILE

        if isinstance(path, str):
            resolved = find_file(path)
            self._path = Path(resolved) if resolved else Path(path)
        else:
            self._path = path

        # Missing file → valid empty state
        if not self._path.exists():
            self._raw = []
            self._rebuild_indexes(validate=validate, verify=verify)
            return

        # Parse JSON (strict)
        try:
            text = self._path.read_text(encoding="utf-8")
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in accessory config '{self._path}': {e.msg} (line {e.lineno})") from e
        except OSError as e:
            raise RuntimeError(f"Failed to read accessory config '{self._path}': {e}") from e

        # Normalize top-level shape
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

        # Validate each accessory entry (structure only)
        raw: list[dict[str, Any]] = []
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
        by_instance_id: dict[str, dict[str, Any]] = {}
        by_type: dict[AccessoryType, list[dict[str, Any]]] = {}
        by_tmcc_id: dict[int, list[dict[str, Any]]] = {}

        def _warn(msg: str, *args) -> None:
            if validate:
                log.warning(msg, *args)
            if issues_out is not None:
                try:
                    issues_out.append(msg % args)
                except (TypeError, ValueError):
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
    # Raw query API (unchanged)
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path | None:
        return self._path

    def all(self) -> list[dict[str, Any]]:
        return list(self._raw)

    def by_instance_id(self, instance_id: str) -> dict[str, Any] | None:
        return self._by_instance_id.get(instance_id)

    def by_type(self, acc_type: AccessoryType) -> list[dict[str, Any]]:
        return list(self._by_type.get(acc_type, []))

    def by_tmcc_id(self, tmcc_id: int) -> list[dict[str, Any]]:
        return list(self._by_tmcc_id.get(tmcc_id, []))

    def has_any(self) -> bool:
        return bool(self._raw)

    # ------------------------------------------------------------------
    # Typed API (new)
    # ------------------------------------------------------------------

    def configured_all(self) -> list[ConfiguredAccessory]:
        return [ConfiguredAccessory(r, self._registry, self._catalog) for r in self._raw]

    def configured_by_instance_id(self, instance_id: str) -> ConfiguredAccessory | None:
        raw = self.by_instance_id(instance_id)
        return ConfiguredAccessory(raw, self._registry, self._catalog) if raw else None

    def configured_by_tmcc_id(self, tmcc_id: int) -> list[ConfiguredAccessory]:
        return [ConfiguredAccessory(r, self._registry, self._catalog) for r in self.by_tmcc_id(tmcc_id)]

    def configured_by_type(self, acc_type: AccessoryType) -> list[ConfiguredAccessory]:
        return [ConfiguredAccessory(r, self._registry, self._catalog) for r in self.by_type(acc_type)]

    def gui_specs(self) -> list[GuiCtorSpec]:
        """
        Build GUI ctor specs for every configured accessory, disambiguating duplicate labels.
        """
        accs = self.configured_all()
        specs: list[GuiCtorSpec] = []

        # First pass: compute base labels and count duplicates
        counts: dict[str, int] = {}
        for a in accs:
            counts[a.label] = counts.get(a.label, 0) + 1

        # Second pass: disambiguate duplicates
        for a in accs:
            disambig: str | None = None
            if counts.get(a.label, 0) > 1:
                disambig = a.instance_id or None
            specs.append(a.build_gui_spec(disambiguate_with=disambig))

        # Stable sort for menus
        specs.sort(key=lambda s: s.label.lower())
        return specs

    def verify_config(self) -> ConfigVerificationResult:
        issues: list[str] = []
        raw_snapshot = list(self._raw)

        self._build_indexes(
            raw_snapshot,
            validate=False,
            issues_out=issues,
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
