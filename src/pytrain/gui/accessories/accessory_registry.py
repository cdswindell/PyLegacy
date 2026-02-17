#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .accessory_type import AccessoryType
from ...protocol.constants import Mixins
from ...utils.singleton import singleton

_NORM_TOKEN_RE = re.compile(r"[^a-z0-9]+")

log = logging.getLogger(__name__)


def _variant_norm(s: str) -> str:
    # Treat underscores/hyphens/spaces/punct as equivalent separators
    return _NORM_TOKEN_RE.sub(" ", str(s).strip().lower()).strip()


class PortBehavior(Mixins):
    """
    Defines how an accessory operation behaves.

    - LATCH: on/off toggle (stateful)
    - MOMENTARY_HOLD: press=on, release=off
    - MOMENTARY_PULSE: press triggers an action (no release behavior)
    - COMMAND: tmcc command
    """

    LATCH = "latch"
    MOMENTARY_HOLD = "momentary_hold"
    MOMENTARY_PULSE = "momentary_pulse"
    COMMAND = "command"


@dataclass(frozen=True)
class OperationSpec:
    """
    Describes one operation (one ASC2 connection usage) for an accessory type.

    Each accessory instance provides a TMCC id per operation key.
    """

    key: str
    label: str
    behavior: PortBehavior

    # Default / momentary image
    image: str | None = None

    # LATCH-specific images (optional; GUI supplies global defaults if None)
    off_image: str | None = None
    on_image: str | None = None

    # Optional UI sizing hints
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class VariantSpec:
    """
    ...
    operation_images:
      - Optional per-variant overrides for specific operation images

    operation_labels:
    # Allow either a simple label override OR per-state overrides for latch buttons
    # - {"motion": "Swing"} # always "Swing"
    # - {"platform": {"off": "Depart", "on": "Arrive"}} # state-based

    NOTE:
      - operation_images affects filenames (bundled into OperationAssets)
      - operation_labels affects UI text (resolved via registry helpers)
    """

    key: str
    display: str
    title: str
    image: str
    aliases: tuple[str, ...] = ()
    flavor: str | None = None
    default: bool = False
    operation_images: dict[str, object] | None = None  # see docstring
    operation_labels: dict[str, object] | None = None  # NEW


@dataclass(frozen=True)
class AccessoryTypeSpec:
    """
    Formal definition of a friendly accessory type (GUI-agnostic metadata only).
    """

    type: AccessoryType
    display_name: str
    operations: tuple[OperationSpec, ...]
    variants: tuple[VariantSpec, ...]
    op_btn_image: str | None = "op-acc.jpg"


@dataclass(frozen=True)
class OperationAssets:
    """
    Pre-bundled, resolved image filenames for a single operation.

    This is still GUI-agnostic (filenames only). GUI layer resolves to paths
    (e.g., via find_file()) and decides when to display on/off images.
    """

    key: str
    behavior: PortBehavior

    # For momentary/default use
    image: str | None = None

    # For latch use
    off_image: str | None = None
    on_image: str | None = None

    # Pass-through UI hints
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class AccessoryDefinition:
    """
    A GUI-agnostic 'instance' returned from the registry for a given type+variant.

    This contains references (filenames) to all images needed to render a GUI for
    that type+variant:
      - main variant image (VariantSpec.image)
      - per-operation images bundled as OperationAssets
    """

    type: AccessoryType
    display_name: str
    variant: VariantSpec
    operations: tuple[OperationAssets, ...]


@singleton
class AccessoryRegistry:
    """
    Singleton registry of known accessory type definitions.

    Use AccessoryRegistry.instance() to get the singleton.
    """

    @classmethod
    def get(cls) -> "AccessoryRegistry":
        """
        Return the singleton AccessoryRegistry instance.

        This is a convenience wrapper around the singleton metaclass
        and makes the API explicit and discoverable.
        """
        return cls()  # __call__ is overridden by the singleton metaclass

    def __init__(self) -> None:
        self._specs: dict[AccessoryType, AccessoryTypeSpec] = {}
        self._bootstrapped: bool = False

    # -------------------------------------------------------------------------
    # Bootstrap / lifecycle
    # -------------------------------------------------------------------------

    def bootstrap(self) -> None:
        if self._bootstrapped:
            return

        from .bootstrap_accessories import register_all_accessory_types  # local import

        register_all_accessory_types(self)
        self._bootstrapped = True

    @property
    def is_bootstrapped(self) -> bool:
        return self._bootstrapped

    def reset_for_tests(self) -> None:
        self._specs.clear()
        self._bootstrapped = False

    # -------------------------------------------------------------------------
    # Registration + lookup
    # -------------------------------------------------------------------------

    def register(self, spec: AccessoryTypeSpec) -> None:
        if spec.type in self._specs:
            raise ValueError(f"Accessory type already registered: {spec.type}")
        self._validate_spec(spec)
        self._specs[spec.type] = spec

    def get_spec(self, type_: AccessoryType | str) -> AccessoryTypeSpec:
        t = self._coerce_type(type_)
        return self._specs[t]

    def is_registered(self, type_: AccessoryType | str) -> bool:
        try:
            t = self._coerce_type(type_)
        except ValueError:
            return False
        return t in self._specs

    def all_specs(self) -> list[AccessoryTypeSpec]:
        return sorted(self._specs.values(), key=lambda s: str(s.type))

    def resolve_variant_key(self, acc_type: "AccessoryType", variant: str) -> str:
        """
        Resolve a user-provided variant string to the canonical VariantSpec.key.

        Accepts:
          - exact key
          - alias (normalized)
          - unique prefix of a key (normalized), e.g. "dairymens_league" -> "dairymens_league_6_14291"

        Raises:
          ValueError if unknown or ambiguous.
        """
        raw = str(variant).strip() if variant is not None else ""
        if not raw:
            raise ValueError("empty variant")

        spec = self.get_spec(acc_type)

        # 1) exact key
        for vs in spec.variants:
            if vs.key == raw:
                return vs.key

        v_norm = _variant_norm(raw)

        # 2) alias match
        for vs in spec.variants:
            aliases = getattr(vs, "aliases", None)
            if not aliases:
                continue
            for a in aliases:
                if _variant_norm(a) == v_norm:
                    return vs.key

        # 3) unique prefix match on key
        matches = [vs.key for vs in spec.variants if _variant_norm(vs.key).startswith(v_norm)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(f"ambiguous variant {variant!r} for type {acc_type.name}: {matches}")

        raise ValueError(f"unknown variant {variant!r} for type {acc_type.name}")

    def is_valid_variant(self, acc_type: "AccessoryType", variant: str) -> bool:
        try:
            _ = self.resolve_variant_key(acc_type, variant)
            return True
        except ValueError:
            return False

    # -------------------------------------------------------------------------
    # Definition retrieval (GUI-agnostic)
    # -------------------------------------------------------------------------

    def get_definition(self, type_: AccessoryType | str, variant: str | None = None) -> AccessoryDefinition:
        """
        Return a GUI-agnostic definition object for the given accessory type+variant.

        The returned object contains references (filenames) to all images needed to
        render the accessory GUI for that type+variant, bundled per operation.
        """
        spec = self.get_spec(type_)
        vs = self.resolve_variant(spec, variant)

        bundled_ops: list[OperationAssets] = []
        for op in spec.operations:
            bundled_ops.append(self._bundle_operation_assets(op, vs))

        return AccessoryDefinition(
            type=spec.type,
            display_name=spec.display_name,
            variant=vs,
            operations=tuple(bundled_ops),
        )

    # -------------------------------------------------------------------------
    # Label resolution helpers (NEW)
    # -------------------------------------------------------------------------

    def get_operation_label(
        self,
        spec: AccessoryTypeSpec,
        key: str,
        *,
        variant: VariantSpec | None = None,
    ) -> str:
        """
        Return the effective label for an operation key, optionally applying
        per-variant label overrides.

        If no override exists, returns the OperationSpec.label.
        """
        op = self.get_operation(spec, key)
        if variant is None:
            return op.label

        ov = self.variant_operation_label_override(variant, op.key)
        return ov if ov is not None else op.label

    def operation_labels(self, definition: AccessoryDefinition) -> dict[str, str]:
        """
        Convenience: return a dict of effective labels for a concrete definition.
        """
        spec = self.get_spec(definition.type)
        return {op.key: self.get_operation_label(spec, op.key, variant=definition.variant) for op in spec.operations}

    def get_operation_label_for_state(
        self,
        spec: AccessoryTypeSpec,
        key: str,
        *,
        variant: VariantSpec | None = None,
        is_on: bool | None = None,
    ) -> str:
        """
        Resolve an operation label, optionally state-aware.

        - If override is a string -> return it
        - If override is dict -> expects {"off": "...", "on": "..."}; uses is_on
        - Otherwise -> OperationSpec.label
        """
        op = self.get_operation(spec, key)
        if variant is None:
            return op.label

        ov = self.variant_operation_label_override(variant, op.key)
        if isinstance(ov, str):
            return ov

        if isinstance(ov, dict):
            if is_on is None:
                # caller didn't provide state; fall back to base label
                return op.label
            k = "on" if is_on else "off"
            v = ov.get(k)
            return v if isinstance(v, str) else op.label

        return op.label

    # -------------------------------------------------------------------------
    # Spec helpers
    # -------------------------------------------------------------------------

    # noinspection PyMethodMayBeStatic
    def operation_keys(self, spec: AccessoryTypeSpec) -> tuple[str, ...]:
        return tuple(op.key for op in spec.operations)

    def get_operation(self, spec: AccessoryTypeSpec, key: str) -> OperationSpec:
        k = self._norm(key)
        for op in spec.operations:
            if self._norm(op.key) == k:
                return op
        raise KeyError(f"Unknown operation '{key}' for type '{spec.type}'")

    # noinspection PyMethodMayBeStatic
    def default_variant(self, spec: AccessoryTypeSpec) -> VariantSpec:
        if not spec.variants:
            raise ValueError(f"Accessory type '{spec.type}' defines no variants")
        for v in spec.variants:
            if v.default:
                return v
        return spec.variants[0]

    def resolve_variant(self, spec: AccessoryTypeSpec, variant: str | None) -> VariantSpec:
        if variant is None:
            return self.default_variant(spec)

        v = self._norm(variant)

        for vs in spec.variants:
            if self._norm(vs.key) == v:
                return vs

        for vs in spec.variants:
            if self._norm(vs.display) == v or self._norm(vs.title) == v:
                return vs

        for vs in spec.variants:
            for a in vs.aliases:
                if self._norm(a) == v:
                    return vs

        for vs in spec.variants:
            hay = " | ".join([vs.key, vs.display, vs.title, *vs.aliases])
            if v in self._norm(hay) or self._norm(vs.key) in v:
                return vs

        raise ValueError(f"Unsupported variant '{variant}' for type '{spec.type}'")

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def variant_operation_label_override(variant: VariantSpec, op_key: str) -> object | None:
        if not variant.operation_labels:
            return None
        k = " ".join(op_key.strip().lower().split())
        for kk, vv in variant.operation_labels.items():
            if " ".join(kk.strip().lower().split()) == k:
                return vv
        return None

    def _bundle_operation_assets(self, op: OperationSpec, variant: VariantSpec) -> OperationAssets:
        """
        Bundle (resolve) image filenames for an operation, incorporating variant overrides.

        Returns filenames only; GUI layer resolves to paths and supplies global defaults
        for any None latch images.
        """
        # Start with spec defaults
        image = op.image
        off_image = op.off_image
        on_image = op.on_image

        # Apply variant overrides, if any
        ov = self._variant_operation_override(variant, op.key)
        if isinstance(ov, str):
            # momentary/default override
            image = ov
        elif isinstance(ov, dict):
            # latch override: expects keys "off" and/or "on"
            if "off" in ov and isinstance(ov["off"], str):
                off_image = ov["off"]
            if "on" in ov and isinstance(ov["on"], str):
                on_image = ov["on"]

        return OperationAssets(
            key=op.key,
            behavior=op.behavior,
            image=image,
            off_image=off_image,
            on_image=on_image,
            width=op.width,
            height=op.height,
        )

    @staticmethod
    def _variant_operation_override(variant: VariantSpec, op_key: str) -> object | None:
        """
        Return the raw variant override for an operation key.

        See VariantSpec.operation_images docstring for supported formats.
        """
        if not variant.operation_images:
            return None
        k = " ".join(op_key.strip().lower().split())
        for kk, vv in variant.operation_images.items():
            if " ".join(kk.strip().lower().split()) == k:
                return vv
        return None

    # noinspection PyMethodMayBeStatic
    def _coerce_type(self, type_: AccessoryType | str) -> AccessoryType:
        if isinstance(type_, AccessoryType):
            return type_
        return AccessoryType.by_name(type_)  # type: ignore[attr-defined]

    @staticmethod
    def _norm(s: str) -> str:
        return " ".join(s.strip().lower().split())

    def _validate_spec(self, spec: AccessoryTypeSpec) -> None:
        seen_ops: set[str] = set()
        for op in spec.operations:
            nk = self._norm(op.key)
            if nk in seen_ops:
                raise ValueError(f"Duplicate operation key '{op.key}' in type '{spec.type}'")
            seen_ops.add(nk)

        seen_vars: set[str] = set()
        for vs in spec.variants:
            nk = self._norm(vs.key)
            if nk in seen_vars:
                raise ValueError(f"Duplicate variant key '{vs.key}' in type '{spec.type}'")
            seen_vars.add(nk)

        valid_ops = {self._norm(op.key) for op in spec.operations}
        for vs in spec.variants:
            if vs.operation_labels:
                for k in vs.operation_labels.keys():
                    if self._norm(k) not in valid_ops:
                        log.warning(f"{spec.type} variant '{vs.key}' overrides unknown label op '{k}'")

        # check for default variant
        defaults = [v for v in spec.variants if v.default]
        if len(defaults) == 0 and len(spec.variants) > 1:
            log.warning(f"Accessory type '{spec.type}' should define exactly one default variant")
        if len(defaults) > 1:
            raise ValueError(f"Accessory type '{spec.type}' defines multiple default variants")
