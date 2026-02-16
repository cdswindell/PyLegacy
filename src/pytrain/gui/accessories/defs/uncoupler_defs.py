#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from .base_defs import aliases_from_legacy_key, dedup_preserve_order, print_registry_entry, variant_key_from_filename
from ..accessory_registry import (
    AccessoryRegistry,
    AccessoryTypeSpec,
    OperationSpec,
    PortBehavior,
    VariantSpec,
)
from ..accessory_type import AccessoryType

"""
Uncoupler Track

Ports / operations:
  - uncouple: momentary_hold (press/release)

This file uses the “interpret legacy dicts” pattern: keep the original VARIANTS/TITLES
data and transform it into VariantSpec entries at registration time.
"""

# Source data you provided
_VARIANTS = {
    "uncoupling track 6-12020": "Fastrack-Uncoupling-6-12020.jpg",
}

_TITLES = {
    "Fastrack-Uncoupling-6-12020.jpg": "Uncoupling Track",
}

_MOTION_IMAGE = {
    "Fastrack-Uncoupling-6-12020.jpg": "uncouple-motion.jpg",
}

ALIASES: dict[str, set[str]] = {
    "uncoupling track 6-12020": {"uncoupler", "uncoupler track"},
}

DEFAULT_CONSTRUCTION = "Fastrack-Uncoupling-6-12020.jpg"


def register_uncoupler(registry: AccessoryRegistry) -> None:
    """
    Register Construction Scene accessory type metadata.
    """
    operations = (
        OperationSpec(
            key="uncouple",
            label="Uncouple",
            behavior=PortBehavior.MOMENTARY_HOLD,
            width=72,
            height=72,
        ),
    )

    variants: list[VariantSpec] = []
    for legacy_name, filename in _VARIANTS.items():
        title = _TITLES.get(filename, filename.rsplit(".", 1)[0])
        motion_image = _MOTION_IMAGE.get(filename)

        legacy_aliases = aliases_from_legacy_key(legacy_name) if " " in legacy_name else (legacy_name.strip().lower(),)

        base_no_ext = filename.rsplit(".", 1)[0]
        extra_aliases = (title.lower(), base_no_ext.lower(), filename.lower())

        op_images = {"uncouple": motion_image} if motion_image else None

        variants.append(
            VariantSpec(
                key=variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                default=(filename == DEFAULT_CONSTRUCTION),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases)),
                operation_images=op_images,
            )
        )

    spec = AccessoryTypeSpec(
        type=AccessoryType.UNCOUPLER,
        display_name="Uncoupler Track",
        operations=operations,
        variants=tuple(variants),
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_uncoupler(reg)
    print_registry_entry("uncoupler")
