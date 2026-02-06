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
Smoke Fluid Loader accessory definition (GUI-agnostic).

Ports / operations:
  - tmcc: command control accessory tmcc id
"""

# Source data you provided
_VARIANTS = {
    "advanced smoke fluid loader 6-37821": "Advanced-Smoke-Fluid-Loader-6-37821.jpg",
    "keystone smoke fluid loader 6-83634": "Keystone-Smoke-Fluid-Loader-6-83634.jpg",
}

_TITLES = {
    "Advanced-Smoke-Fluid-Loader-6-37821.jpg": "Advanced Fluid Co.",
    "Keystone-Smoke-Fluid-Loader-6-83634.jpg": "Keystone Fluid Co.",
}

DEFAULT_SMOKE_LOADER = "Keystone-Smoke-Fluid-Loader-6-83634.jpg"


def register_smoke_fluid_loader(registry: AccessoryRegistry) -> None:
    """
    Register Smoke Fluid Loader accessory type metadata.
    """
    operations = (
        OperationSpec(
            key="tmcc_id",
            label="TMCC ID",
            behavior=PortBehavior.COMMAND,
        ),
    )

    variants: list[VariantSpec] = []
    for legacy_name, filename in _VARIANTS.items():
        title = _TITLES.get(filename, filename.rsplit(".", 1)[0])

        # Allow both “legacy key style” and “filename as key” inputs
        legacy_aliases = aliases_from_legacy_key(legacy_name) if " " in legacy_name else (legacy_name.strip().lower(),)

        # Extra helpful aliases
        base_no_ext = filename.rsplit(".", 1)[0]
        extra_aliases = (title.lower(), base_no_ext.lower())

        variants.append(
            VariantSpec(
                key=variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                default=(filename == DEFAULT_SMOKE_LOADER),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases)),
            )
        )

    # Drop aliases that are not unique across variants (e.g., shared "smoke", "loader", etc.)
    variants = list(prune_non_unique_variant_aliases(variants))

    spec = AccessoryTypeSpec(
        type=AccessoryType.SMOKE_FLUID_LOADER,
        display_name="Smoke Fluid Loader",
        operations=operations,
        variants=tuple(variants),
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_smoke_fluid_loader(reg)
    print_registry_entry("smoke_fluid_loader")
