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
from typing import Any, Mapping

from .accessory_registry import AccessoryDefinition, AccessoryRegistry, PortBehavior


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

    def image_for(self, key: str, default: str | None = None) -> str | None:
        op = self.operation(key)
        return op.image or default

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


def configure_accessory(
    definition: AccessoryDefinition,
    *,
    tmcc_ids: Mapping[str, int],
    operation_images: Mapping[str, Any] | None = None,
    instance_id: str | None = None,
    display_name: str | None = None,
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
        if key not in tmcc_ids:
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

        op_spec = registry.get_operation(spec, key)

        ops.append(
            ConfiguredOperation(
                key=key,
                label=op_spec.label,
                behavior=op_assets.behavior,
                tmcc_id=int(tmcc_ids[key]),
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
    )
