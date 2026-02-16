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
Hobby Shop accessory definition (GUI-agnostic).

Ports / operations:
  - power:  latch (on/off)
  - action: latch (on/off)   (adjust to MOMENTARY_* if your GUI expects momentary)

This file uses the “interpret legacy dicts” pattern: keep the original VARIANTS/TITLES
data and transform it into VariantSpec entries at registration time.
"""

# -----------------------------------------------------------------------------
# Source data (easy to extend)
# -----------------------------------------------------------------------------

# legacy-name -> primary image filename
_VARIANTS: dict[str, str] = {
    "lionelville hobby shop 6-85294": "Lionelville-Hobby-Shop-6-85294.jpg",
    "madison hobby shop 6-14133": "Madison-Hobby-Shop-6-14133.jpg",
    "midtown models hobby shop 6-32998": "Midtown-Models-Hobby-Shop-6-32998.jpg",
}

# filename -> display/title
_TITLES: dict[str, str] = {
    "Lionelville-Hobby-Shop-6-85294.jpg": "Lionelville Hobby Shop",
    "Madison-Hobby-Shop-6-14133.jpg": "Madison Hobby Shop",
    "Midtown-Models-Hobby-Shop-6-32998.jpg": "Midtown Models",
}

# optional extra aliases keyed by legacy key (same pattern as milk loader)
ALIASES: dict[str, set[str]] = {
    "midtown models hobby shop 6-32998": {"midtown", "midtown models"},
    "lionelville hobby shop 6-85294": {"lionelville"},
    "madison hobby shop 6-14133": {"madison"},
}

DEFAULT_HOBBY_SHOP = "Midtown-Models-Hobby-Shop-6-32998.jpg"


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register_hobby_shop(registry: AccessoryRegistry) -> None:
    """
    Register Hobby Shop accessory type metadata.
    """
    operations = (
        OperationSpec(
            key="power",
            label="Power",
            behavior=PortBehavior.LATCH,
        ),
        OperationSpec(
            key="action",
            label="Action",
            behavior=PortBehavior.LATCH,
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

        # pulls ALIASES plus any other module-provided alias helpers you use
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
                default=(filename == DEFAULT_HOBBY_SHOP),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases, *extra2)),
            )
        )

    spec = AccessoryTypeSpec(
        type=AccessoryType.HOBBY_SHOP,
        display_name="Hobby Shop",
        operations=operations,
        variants=tuple(variants),
        op_btn_image="op-hobby-shop.jpg",
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_hobby_shop(reg)
    print_registry_entry("hobby_shop")
