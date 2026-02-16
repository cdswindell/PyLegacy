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
from .accessory_registry import AccessoryRegistry, OperationAssets
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

    _label: str | None = None  # computed/disambiguated by ConfiguredAccessorySet

    def __repr__(self) -> str:
        # Resolve accessory type safely (may raise ValueError if misconfigured)
        try:
            acc_type = self.accessory_type.name
        except ValueError:
            acc_type = "<?>"

        # Resolve title safely (may raise ValueError via registry lookup)
        try:
            title = self.title
        except ValueError:
            title = "<?>"

        gui_key = self.gui_key
        variant = self.variant
        instance_id = self.instance_id
        display_name = self.display_name
        tmcc_id = self.tmcc_id

        # tmcc_ids property is deterministic and should not raise,
        # so we do NOT blanket-catch here.
        tmcc_ids = self.tmcc_ids

        parts: list[str] = [
            f"type={acc_type}",
            f"gui={gui_key!r}",
            f"title={title!r}",
        ]

        if variant is not None:
            parts.append(f"variant={variant!r}")
        if instance_id is not None:
            parts.append(f"instance_id={instance_id!r}")
        if display_name is not None:
            parts.append(f"display_name={display_name!r}")
        if tmcc_id is not None:
            parts.append(f"tmcc_id={tmcc_id}")
        if tmcc_ids:
            parts.append(f"tmcc_ids={tmcc_ids!r}")

        return f"ConfiguredAccessory({', '.join(parts)})"

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

        return tuple(sorted(out))

    def tmcc_id_for(self, op_key: str) -> int:
        """
        Return the TMCC id for a given operation key (e.g. 'power', 'eject').

        Case-insensitive match against configured tmcc_ids.
        Falls back to overall tmcc_id if no per-operation mapping exists
        and op_key matches 'accessory' or 'default'.

        Raises:
            KeyError  – if operation not found
            ValueError – if TMCC id is not properly configured
        """
        if not isinstance(op_key, str) or not op_key.strip():
            raise ValueError("tmcc_id_for requires a non-empty operation key")

        needle = op_key.strip().lower()

        # Per-operation TMCC IDs
        tmcc_ids = self.raw.get("tmcc_ids")
        if isinstance(tmcc_ids, dict):
            for key, value in tmcc_ids.items():
                if isinstance(key, str) and key.strip().lower() == needle:
                    if not isinstance(value, int):
                        raise ValueError(f"{self.label}: TMCC id for operation '{key}' is not an int")
                    return value

        # Optional fallback to overall tmcc_id
        if isinstance(self.tmcc_id, int):
            if needle in ("accessory", "default", "main") or needle in [k.key.lower() for k in self.operation_assets]:
                return self.tmcc_id

        available = ", ".join(tmcc_ids.keys()) if isinstance(tmcc_ids, dict) and tmcc_ids else "none"

        raise KeyError(f"{self.label}: operation '{op_key}' not found (available: {available})")

    @property
    def definition(self):
        """
        Registry definition for this accessory type and optional variant.
        """
        return self.registry.get_definition(self.accessory_type, self.variant)

    @property
    def operation_assets(self) -> list[OperationAssets]:
        return list(self.definition.operations)

    @property
    def configured_operation_assets(self) -> dict[int, OperationAssets | list[OperationAssets]]:
        co: dict[int, OperationAssets | list[OperationAssets]] = {}
        for op in self.operation_assets:
            tmcc_id = self.tmcc_id_for(op.key)
            if tmcc_id in co:
                if isinstance(co[tmcc_id], list):
                    co[tmcc_id].append(op)
                else:
                    co[tmcc_id] = [co[tmcc_id], op]
            else:
                co[tmcc_id] = op
        return co

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
    def op_btn_image_path(self) -> str | None:
        spec = self.registry.get_spec(self.accessory_type)
        img = spec.op_btn_image
        if isinstance(img, str) and img.strip():
            return img
        return "op-acc.jpg"

    @property
    def label(self) -> str:
        return self._label or self.display_name or self.title

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

    def label_disambiguator(self) -> str | None:
        """
        Prefer readable TMCC operation ids, e.g. "power=7, conveyor=8".
        Fallback to tmcc_id, then instance_id.
        """
        tmcc_ids = self.raw.get("tmcc_ids")
        if isinstance(tmcc_ids, dict) and tmcc_ids:
            parts: list[str] = []
            for k, v in tmcc_ids.items():
                if isinstance(k, str) and isinstance(v, int):
                    parts.append(f"{v}")
            if parts:
                return "/".join(parts)

        if isinstance(self.tmcc_id, int):
            return f"{self.tmcc_id}"

        return self.instance_id or None

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
        self._configured_all: list[ConfiguredAccessory] = []
        self._configured_by_instance_id: dict[str, ConfiguredAccessory] = {}
        self._configured_by_label: dict[str, list[ConfiguredAccessory]] = {}
        self._configured_by_tmcc_id: dict[int, list[ConfiguredAccessory]] = {}

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
    def _norm_label(s: str) -> str:
        # stable, case-insensitive, collapses whitespace
        return " ".join(str(s).strip().lower().split())

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

        # ---- Typed indexes (ConfiguredAccessory) ----
        accs = [ConfiguredAccessory(r, self._registry, self._catalog) for r in self._raw]
        self._configured_all = accs

        # Count *base* labels (NOT resolved labels) so we know when to disambiguate
        counts: dict[str, int] = {}
        for a in accs:
            base = a.display_name or a.title
            counts[base] = counts.get(base, 0) + 1

        by_instance: dict[str, ConfiguredAccessory] = {}
        by_label: dict[str, list[ConfiguredAccessory]] = {}
        by_tmcc: dict[int, list[ConfiguredAccessory]] = {}

        seen_labels: set[str] = set()

        for a in accs:
            iid = a.instance_id
            if iid:
                by_instance[iid] = a

            base = a.display_name or a.title

            # Compute resolved label:
            resolved_label = base
            if counts.get(base, 0) > 1:
                dis = a.label_disambiguator()  # e.g. "30/33/34" or "29"
                if dis:
                    resolved_label = f"{base} ({dis})"

            # If it still collides (same display name + same disambiguator),
            # suffix with stable numeric counter. No instance_id exposed.
            if resolved_label in seen_labels:
                base2 = resolved_label
                n = 2
                while resolved_label in seen_labels:
                    resolved_label = f"{base2} #{n}"
                    n += 1

            seen_labels.add(resolved_label)

            # ✅ actually store it on the frozen dataclass
            object.__setattr__(a, "_label", resolved_label)

            lk = self._norm_label(resolved_label)
            by_label.setdefault(lk, []).append(a)

            for tid in a.tmcc_ids:
                by_tmcc.setdefault(tid, []).append(a)

        self._configured_by_instance_id = by_instance
        self._configured_by_label = by_label
        self._configured_by_tmcc_id = by_tmcc

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
        return list(self._configured_all)

    def configured_labels(self) -> list[str]:
        return sorted([a.label for a in self._configured_all])

    def configured_by_instance_id(self, instance_id: str) -> ConfiguredAccessory | None:
        if not isinstance(instance_id, str) or not instance_id.strip():
            return None
        return self._configured_by_instance_id.get(instance_id)

    def configured_by_tmcc_id(self, tmcc_id: int) -> list[ConfiguredAccessory]:
        if not isinstance(tmcc_id, int):
            return []
        return list(self._configured_by_tmcc_id.get(tmcc_id, ()))

    def configured_by_type(self, acc_type: AccessoryType) -> list[ConfiguredAccessory]:
        return [ConfiguredAccessory(r, self._registry, self._catalog) for r in self.by_type(acc_type)]

    def configured_by_instance_id_map(self) -> Mapping[str, ConfiguredAccessory]:
        return self._configured_by_instance_id

    def configured_by_label_map(self) -> Mapping[str, list[ConfiguredAccessory]]:
        return self._configured_by_label

    def configured_by_label(self, label: str) -> list[ConfiguredAccessory]:
        """Returns configured accessories matching normalized label"""
        if not isinstance(label, str) or not label.strip():
            return []
        return list(self._configured_by_label.get(self._norm_label(label), ()))

    def configured_by_label_contains(self, text: str) -> list[ConfiguredAccessory]:
        """
        Case-insensitive substring match against the *label* (display_name-or-title).
        Returns results in stable order (config order).
        """
        if not isinstance(text, str) or not text.strip():
            return []
        needle = self._norm_label(text)

        # If the user typed an exact label, use the index fast-path
        exact = self._configured_by_label.get(needle)
        if exact:
            return list(exact)

        out: list[ConfiguredAccessory] = []
        for a in self._configured_all:
            if needle in self._norm_label(a.label):
                out.append(a)
        return out

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
                disambig = a.label_disambiguator()
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

    def preview(self) -> list[dict[str, Any]]:
        """
        Returns a fully resolved preview of configured accessories,
        including final label disambiguation and ctor specs.
        """
        previews: list[dict[str, Any]] = []

        specs = self.gui_specs()

        for spec in specs:
            previews.append(
                {
                    "label": spec.label,
                    "title": spec.title,
                    "image_path": spec.image_path,
                    "gui_class": spec.gui_class.__name__,
                    "accessory_type": spec.accessory_type.name,
                    "variant": spec.variant,
                    "instance_id": spec.instance_id,
                    "ctor_kwargs": dict(spec.kwargs),
                }
            )

        return previews

    def debug_dump(self) -> str:
        lines: list[str] = []
        specs = self.gui_specs()

        for spec in specs:
            lines.append(
                f"label: {spec.label}\n"
                f"  title: {spec.title}\n"
                f"  type: {spec.accessory_type.name}\n"
                f"  instance_id: {spec.instance_id}\n"
                f"  variant: {spec.variant}\n"
                f"  image: {spec.image_path}\n"
                f"  gui: {spec.gui_class.__name__}\n"
                f"  ctor kwargs: {spec.kwargs}\n"
            )

        return "\n".join(lines)


if __name__ == "__main__":
    cs = ConfiguredAccessorySet.from_file()
    print(cs.debug_dump())
