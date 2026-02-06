#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from .base_defs import (
    aliases_from_legacy_key,
    dedup_preserve_order,
    extra_aliases_from_module,
    print_registry_entry,
    prune_non_unique_variant_aliases,
    variant_key_from_filename,
)
from ..accessory_registry import (
    AccessoryRegistry,
    AccessoryTypeSpec,
    OperationSpec,
    PortBehavior,
    VariantSpec,
)
from ..accessory_type import AccessoryType

"""
Culvert Loader/Unloader accessory definition (GUI-agnostic).

Ports / operations:
  - power:  latch (on/off)
  - action: momentary_hold (press/release)

Per-variant metadata:
  - flavor: "loader" or "unloader"

"""

FLAVOR_LOADER = "loader"
FLAVOR_UNLOADER = "unloader"

# Source data you provided
_VARIANTS = {
    "lionelville culvert loader 6-82029": "Lionelville-Culvert-Loader-6-82029.jpg",
    "lionelville culvert unloader 6-82030": "Lionelville-Culvert-Unloader-6-82030.jpg",
}

_TITLES = {
    "Lionelville-Culvert-Loader-6-82029.jpg": "Lionelville Culvert Loader",
    "Lionelville-Culvert-Unloader-6-82030.jpg": "Lionelville Culvert Unloader",
}

_LOADERS = {
    "Lionelville-Culvert-Loader-6-82029.jpg",
}

_UNLOADERS = {
    "Lionelville-Culvert-Unloader-6-82030.jpg",
}

_MOTION_IMAGE = {
    "Lionelville-Culvert-Unloader-6-82030.jpg": "unload_culvert.png",
    "Lionelville-Culvert-Loader-6-82029.jpg": "load_culvert.png",
}

_MOTION_TEXT = {
    "Lionelville-Culvert-Unloader-6-82030.jpg": "Unload",
    "Lionelville-Culvert-Loader-6-82029.jpg": "Load",
}

ALIASES = {
    "lionelville culvert loader 6-82029": {"lionelville loader", "loader"},
    "lionelville culvert unloader 6-82030": {"lionelville unloader", "unloader"},
}

DEFAULT_CULVERT = "Lionelville-Culvert-Loader-6-82029.jpg"


def _flavor_for_image(filename: str) -> str:
    if filename in _UNLOADERS:
        return FLAVOR_UNLOADER
    if filename in _LOADERS:
        return FLAVOR_LOADER
    # Defensive default
    return FLAVOR_LOADER


def register_culvert_handler(registry: AccessoryRegistry) -> None:
    """
    Register Culvert accessory type metadata.
    """
    operations = (
        OperationSpec(
            key="action",
            label="Action",
            behavior=PortBehavior.MOMENTARY_HOLD,
            # image/label can be overridden later if you add per-variant assets
            width=72,
            height=72,
        ),
    )

    variants: list[VariantSpec] = []
    for legacy_name, filename in _VARIANTS.items():
        title = _TITLES.get(filename, filename.rsplit(".", 1)[0])
        motion_image = _MOTION_IMAGE.get(filename)
        motion_label = _MOTION_TEXT.get(filename)
        flavor = _flavor_for_image(filename)

        # Allow both “legacy key style” and “filename as key” inputs
        legacy_aliases = aliases_from_legacy_key(legacy_name) if " " in legacy_name else (legacy_name.strip().lower(),)

        # Extra helpful aliases
        base_no_ext = filename.rsplit(".", 1)[0]
        extra_aliases = (title.lower(), base_no_ext.lower())

        extra2 = extra_aliases_from_module(
            globals(),
            legacy_key=legacy_name,
            filename=filename,
            title=title,
        )

        op_images = {"action": motion_image} if motion_image else None
        op_labels = {"action": motion_label} if motion_label else None

        variants.append(
            VariantSpec(
                key=variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                flavor=flavor,
                default=(filename == DEFAULT_CULVERT),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases, *extra2)),
                operation_images=op_images,
                operation_labels=op_labels,
            )
        )

    # make sure aliases are unique across variants
    variants_t = prune_non_unique_variant_aliases(variants)

    spec = AccessoryTypeSpec(
        type=AccessoryType.CULVERT_HANDLER,
        display_name="Culvert Loader/Unloader",
        operations=operations,
        variants=variants_t,
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_culvert_handler(reg)
    print_registry_entry("culvert_handler")
