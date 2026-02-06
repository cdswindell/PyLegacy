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
Freight Depot accessory definition (GUI-agnostic).

Ports / operations:
  - power:    latch (on/off)
  - conveyor: latch (on/off)
  - load:    momentary_pulse (press triggers eject)

This file uses the “interpret legacy dicts” pattern: keep the original VARIANTS/TITLES
data and transform it into VariantSpec entries at registration time.
"""

# Source data you provided
_VARIANTS = {
    "k lineville freight depot k-42418": "K-Lineville-Freight-Depot-K-42418.jpg",
}

_TITLES = {
    "K-Lineville-Freight-Depot-K-42418.jpg": "Lineville Freight Depot",
}

DEFAULT_DEPOT = "K-Lineville-Freight-Depot-K-42418.jpg"


def register_freight_depot(registry: AccessoryRegistry) -> None:
    """
    Register Freight Depot accessory type metadata.
    """
    operations = (
        OperationSpec(
            key="power",
            label="Power",
            behavior=PortBehavior.LATCH,
        ),
        OperationSpec(
            key="conveyor",
            label="Conveyor",
            behavior=PortBehavior.LATCH,
        ),
        OperationSpec(
            key="load",
            label="Load",
            behavior=PortBehavior.MOMENTARY_PULSE,
            # image can be overridden per-variant later if needed
            image="Man-With-Handcart.png",
            width=72,
            height=72,
        ),
    )

    variants: list[VariantSpec] = []
    for legacy_name, filename in _VARIANTS.items():
        title = _TITLES.get(filename, filename.rsplit(".", 1)[0])

        legacy_aliases = aliases_from_legacy_key(legacy_name) if " " in legacy_name else (legacy_name.strip().lower(),)

        base_no_ext = filename.rsplit(".", 1)[0]
        extra_aliases = (title.lower(), base_no_ext.lower())

        variants.append(
            VariantSpec(
                key=variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                default=(filename == DEFAULT_DEPOT),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases)),
            )
        )

    spec = AccessoryTypeSpec(
        type=AccessoryType.FREIGHT_DEPOT,
        display_name="Freight Depot",
        operations=operations,
        variants=tuple(variants),
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_freight_depot(reg)
    print_registry_entry("freight_depot")
