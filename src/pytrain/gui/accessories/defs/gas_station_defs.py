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
Gas Station accessory definition (GUI-agnostic).

Ports / operations:
  - power:  latch (on/off)
  - action: momentary_pulse (garage)

This file uses the “interpret legacy dicts” pattern: keep VARIANTS/TITLES/ALIASES
easy-to-edit, then transform into VariantSpec entries at registration time.
"""

# -----------------------------------------------------------------------------
# Source data (easy to extend)
# -----------------------------------------------------------------------------

# legacy-name -> primary image filename
_VARIANTS: dict[str, str] = {
    "atlantic gas station 30-91003": "Atlantic-Gas-Station-30-91003.jpg",
    "bp gas station 30-9181": "BP-Gas-Station-30-9181.jpg",
    "citgo gas station 30-9113": "Citgo-Gas-Station-30-9113.jpg",
    "esso gas station 30-9106": "Esso-Gas-Station-30-9106.jpg",
    "gulf gas station 30-9168": "Gulf-Gas-Station-30-9168.jpg",
    "mobile gas station 30-9124": "Mobile-Gas-Station-30-9124.jpg",
    "route 66 gas station 30-91002": "Route-66-Gas-Station-30-91002.jpg",
    "shell gas station 30-9182": "Shell-Gas-Station-30-9182.jpg",
    "sinclair gas station 30-9101": "Sinclair-Gas-Station-30-9101.jpg",
    "sunoco gas station 30-9154": "Sunoco-Gas-Station-30-9154.jpg",
    "texaco gas station 30-91001": "Texaco-Gas-Station-30-91001.jpg",
    "tidewater oil gas station 30-9181": "Tidewater-Oil-Gas-Station-30-9181.jpg",
}

# filename -> display/title
_TITLES: dict[str, str] = {
    "Atlantic-Gas-Station-30-91003.jpg": "Atlantic Gas Station",
    "BP-Gas-Station-30-9181.jpg": "BP Gas Station",
    "Citgo-Gas-Station-30-9113.jpg": "Citgo Gas Station",
    "Esso-Gas-Station-30-9106.jpg": "Esso Gas Station",
    "Gulf-Gas-Station-30-9168.jpg": "Gulf Gas Station",
    "Mobile-Gas-Station-30-9124.jpg": "Mobile Gas Station",
    "Route-66-Gas-Station-30-91002.jpg": "Route 66 Gas Station",
    "Shell-Gas-Station-30-9182.jpg": "Shell Gas Station",
    "Sinclair-Gas-Station-30-9101.jpg": "Sinclair Gas Station",
    "Sunoco-Gas-Station-30-9154.jpg": "Sunoco Gas Station",
    "Texaco-Gas-Station-30-91001.jpg": "Texaco Gas Station",
    "Tidewater-Oil-Gas-Station-30-9181.jpg": "Tidewater Oil Gas Station",
}

# optional extra aliases keyed by legacy key
ALIASES: dict[str, set[str]] = {
    "route 66 gas station 30-91002": {"route_66", "route66"},
    "tidewater oil gas station 30-9181": {"tidewater gas"},
}

DEFAULT_GAS_STATION = "Sinclair-Gas-Station-30-9101.jpg"


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register_gas_station(registry: AccessoryRegistry) -> None:
    """
    Register Gas Station accessory type metadata.
    """
    operations = (
        OperationSpec(
            key="power",
            label="Power",
            behavior=PortBehavior.LATCH,
        ),
        OperationSpec(
            key="action",
            label="Garage",
            behavior=PortBehavior.MOMENTARY_PULSE,
            image="gas-station-car.png",
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
                default=(filename == DEFAULT_GAS_STATION),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases, *extra2)),
            )
        )

    spec = AccessoryTypeSpec(
        type=AccessoryType.GAS_STATION,
        display_name="Gas Station",
        operations=operations,
        variants=tuple(variants),
        op_btn_image="op-gas-station.jpg",
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_gas_station(reg)
    print_registry_entry("gas_station")
