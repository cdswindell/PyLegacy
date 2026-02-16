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
Milk Loader accessory definition (GUI-agnostic).

Ports / operations:
  - power:    latch (on/off)
  - conveyor: latch (on/off)
  - eject:    momentary_hold (press=on, release=off)

This file uses the “interpret legacy dicts” pattern: keep the original VARIANTS/TITLES
data and transform it into VariantSpec entries at registration time.
"""

# -----------------------------------------------------------------------------
# Source data (easy to extend)
# -----------------------------------------------------------------------------

_VARIANTS = {
    "moose pond creamery 6-22660": "Moose-Pond-Creamery-6-22660.jpg",
    "dairymens league 6-14291": "Dairymens-League-6-14291.jpg",
    "mountain view creamery 6-21675": "Mountain-View-Creamery-6-21675.jpg",
}

_TITLES = {
    "Moose-Pond-Creamery-6-22660.jpg": "Moose Pond Creamery",
    "Dairymens-League-6-14291.jpg": "Dairymen's League",
    "Mountain-View-Creamery-6-21675.jpg": "Mountain View Creamery",
}

ALIASES = {
    "dairymens league 6-14291": {
        "dairymen's",
        "dairymens'",
        "dairymen's league",
        "dairymens' league",
        "league",
    },
}

DEFAULT_MILK_LOADER = "Moose-Pond-Creamery-6-22660.jpg"


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register_milk_loader(registry: AccessoryRegistry) -> None:
    """
    Register Milk Loader accessory type metadata.
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
            key="eject",
            label="Eject",
            behavior=PortBehavior.MOMENTARY_HOLD,
            image="depot-milk-can-eject.jpeg",
            width=72,
            height=72,
        ),
    )

    variants: list[VariantSpec] = []
    for legacy_name, filename in _VARIANTS.items():
        title = _TITLES.get(filename, filename.rsplit(".", 1)[0])

        # “legacy key style” aliases (handles numbers etc.)
        legacy_aliases = aliases_from_legacy_key(legacy_name) if " " in legacy_name else (legacy_name.strip().lower(),)

        # extra helpful aliases
        base_no_ext = filename.rsplit(".", 1)[0]
        extra_aliases = (title.lower(), base_no_ext.lower(), filename.lower())

        extra2 = extra_aliases_from_module(
            globals(),
            legacy_key=legacy_name,
            filename=filename,
            title=title,
        )

        variants.append(
            VariantSpec(
                key=variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                default=(filename == DEFAULT_MILK_LOADER),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases, *extra2)),
            )
        )

    spec = AccessoryTypeSpec(
        type=AccessoryType.MILK_LOADER,
        display_name="Milk Loader",
        operations=operations,
        variants=tuple(variants),
        op_btn_image="op-milk-loader.jpg",
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_milk_loader(reg)
    print_registry_entry("milk_loader")
