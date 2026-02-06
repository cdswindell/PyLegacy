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
from dataclasses import dataclass
from typing import Any, Mapping

from .accessory_registry import AccessoryDefinition, AccessoryRegistry, PortBehavior

log = logging.getLogger(__name__)


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


@dataclass(frozen=True)
class ConfiguredOperation:
    """
    One operation bound to a concrete TMCC id and final image filenames.

    Filenames only; GUI layer resolves to paths (find_file()).
    """

    key: str
    label: str
    behavior: PortBehavior
    tmcc_id: int

    # Final resolved filenames for this instance
    image: str | None = None  # momentary/default
    off_image: str | None = None  # latch
    on_image: str | None = None  # latch

    # resolved labels
    label: str
    off_label: str | None = None
    on_label: str | None = None

    # UI sizing hints
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class ConfiguredAccessory:
    """
    A concrete accessory instance: definition + TMCC wiring + optional per-instance overrides.

    This is the object EngineGui and the renderer/builder modules should consume.
    """

    definition: AccessoryDefinition

    # Optional identity/display customizations (useful for lists and debugging)
    instance_id: str | None = None
    display_name: str | None = None

    # Operations in the same order as the definition/spec
    operations: tuple[ConfiguredOperation, ...] = ()

    # Original TMCC mapping (handy for serialization/debugging)
    tmcc_ids: Mapping[str, int] | None = None

    # TMCC ID of the accessory, if it has one
    tmcc_id: int | None = None

    def operation(self, key: str) -> ConfiguredOperation:
        """
        Look up a configured operation by key (case/space-insensitive).
        """
        nk = _norm(key)
        for op in self.operations:
            if _norm(op.key) == nk:
                return op
        raise KeyError(f"ConfiguredAccessory: operation not found: {key}")

    def tmcc_id_for(self, key: str) -> int:
        """
        Convenience: return TMCC id for the given operation key.
        """
        return self.operation(key).tmcc_id

    def label_for(self, key: str) -> str:
        """
        Convenience: return label for the given operation key.
        """
        return self.operation(key).label

    def off_label_for(self, key: str, default: str | None = None) -> str:
        """
        Convenience: return label for the given operation key.
        """
        return self.operation(key).off_label or self.operation(key).label or default

    def on_label_for(self, key: str, default: str | None = None) -> str:
        """
        Convenience: return label for the given operation key.
        """
        return self.operation(key).on_label or self.operation(key).label or default

    def image_for(self, key: str, default: str | None = None) -> str | None:
        op = self.operation(key)
        return op.image or default

    def images_for(self, *keys: str, default: str | None = None) -> tuple[str, ...]:
        return tuple(self.operation(k).image or default for k in keys)

    def off_image_for(self, key: str, default: str | None = None) -> str | None:
        op = self.operation(key)
        return op.off_image or default

    def on_image_for(self, key: str, default: str | None = None) -> str | None:
        op = self.operation(key)
        return op.on_image or default

    def size_for(self, key: str, default: int | None = None) -> tuple[int, int] | None:
        op = self.operation(key)
        return op.height or default, op.width or default

    def labels_for(self, *keys: str) -> tuple[str, ...]:
        return tuple(self.operation(k).label for k in keys)

    @property
    def type(self):
        return self.definition.type

    @property
    def title(self) -> str:
        return self.display_name or self.definition.variant.title

    @property
    def variant_key(self) -> str:
        return self.definition.variant.key

    @property
    def variant_flavor(self) -> str | None:
        return self.definition.variant.flavor


def configure_accessory(
    definition: AccessoryDefinition,
    *,
    tmcc_ids: Mapping[str, int],
    operation_images: Mapping[str, Any] | None = None,
    instance_id: str | None = None,
    display_name: str | None = None,
    tmcc_id: int | None = None,
) -> ConfiguredAccessory:
    """
    Bind TMCC ids and per-instance image overrides to a definition.

    operation_images supports:
      - {"eject": "custom.jpg"} for momentary/default operations
      - {"power": {"off": "...", "on": "..."}} for latch operations
    """
    registry = AccessoryRegistry.get()
    spec = registry.get_spec(definition.type)

    ops: list[ConfiguredOperation] = []

    for op_assets in definition.operations:
        key = op_assets.key
        if tmcc_ids and key not in tmcc_ids:
            raise ValueError(f"Missing TMCC id for operation '{key}' ({definition.type})")

        # Start from pre-bundled (variant-resolved) assets
        image = op_assets.image
        off_image = op_assets.off_image
        on_image = op_assets.on_image

        # Apply per-instance overrides (if any)
        if operation_images and key in operation_images:
            ov = operation_images[key]
            if isinstance(ov, str):
                image = ov
            elif isinstance(ov, dict):
                if "off" in ov and isinstance(ov["off"], str):
                    off_image = ov["off"]
                if "on" in ov and isinstance(ov["on"], str):
                    on_image = ov["on"]

        # Apply per-instance overrides (if any)
        ov = matched_key = None
        if operation_images:
            nk = _norm(key)
            for k2, v2 in operation_images.items():
                if _norm(k2) == nk:
                    ov = v2
                    matched_key = k2
                    break

            if isinstance(ov, str):
                image = ov
            elif isinstance(ov, dict):
                if "off" in ov and isinstance(ov["off"], str):
                    off_image = ov["off"]
                if "on" in ov and isinstance(ov["on"], str):
                    on_image = ov["on"]
            elif matched_key is not None:
                # Only warn if the key matched but the value was invalid
                log.warning(
                    "Invalid operation_images override for %s on %s: %r",
                    matched_key,
                    definition.type,
                    ov,
                )

        label = registry.get_operation_label(spec, key, variant=definition.variant)
        off_label = on_label = None
        ov = registry.variant_operation_label_override(definition.variant, key)
        if isinstance(ov, dict):
            off_label = ov.get("off") if isinstance(ov.get("off"), str) else None
            on_label = ov.get("on") if isinstance(ov.get("on"), str) else None

        ops.append(
            ConfiguredOperation(
                key=key,
                label=label,
                on_label=on_label,
                off_label=off_label,
                behavior=op_assets.behavior,
                tmcc_id=int(tmcc_ids[key]) if tmcc_ids else None,
                image=image,
                off_image=off_image,
                on_image=on_image,
                width=op_assets.width,
                height=op_assets.height,
            )
        )

    return ConfiguredAccessory(
        definition=definition,
        instance_id=instance_id,
        display_name=display_name,
        operations=tuple(ops),
        tmcc_ids=tmcc_ids,
        tmcc_id=tmcc_id,
    )
