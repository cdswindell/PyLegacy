#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from .base_defs import print_registry_entry
from ..accessory_registry import (
    AccessoryRegistry,
    AccessoryTypeSpec,
    OperationSpec,
    PortBehavior,
    VariantSpec,
)
from ..accessory_type import AccessoryType

"""
Freight/Passenger Station accessory definition (GUI-agnostic).

Ports / operations:
  - power: latch (on/off)
  - platform:  latch (unloaded/loaded)

Load/unload images:
  - unloaded (OFF): "loaded.png"
  - loaded   (ON):  flavor-specific waiting image
      * brewing   -> "brews-waiting.png"
      * freight   -> "freight-waiting.jpg"
      * passenger -> "passengers-waiting.png"
"""

FLAVOR_FREIGHT = "freight"
FLAVOR_PASSENGER = "passenger"
FLAVOR_BREWING = "brewing"

# Source data you provided
_VARIANTS = {
    "adolph coors brewing co 30-9161": "Adolph-Coors-Brewing-Co-30-9161.jpg",
    "altoona brewing co 30-90191": "Altoona-Brewing-CO-30-90191.jpg",
    "budweiser 30-9171": "Budweiser-30-9171.jpg",
    "middletown freight station 30-9184": "Middletown-Freight-Station-30-9184.jpg",
    "middletown military station 30-9183": "Middletown-Military-Station-30-9183.jpg",
    "middletown passenger station 30-9125": "Middletown-Passenger-Station-30-9125.jpg",
    "new york central freight station 30-9151": "New-York-Central-Freight-Station-30-9151.jpg",
    "new york central passenger station 30-9164": "New-York-Central-Passenger-Station-30-9164.jpg",
    "old reading brewing co 30-90190": "Old-Reading-Brewing-Co-30-90190.jpg",
    "pennsylvania railroad prr passenger 30-9152": "Pennsylvania-Railroad-PRR-30-9152.jpg",
    "pittsburgh brewing co 30-90189": "Pittsburgh-Brewing-Co-30-90189.jpg",
}

_TITLES = {
    "Adolph-Coors-Brewing-Co-30-9161.jpg": "Adolph Coors Brewing Co.",
    "Altoona-Brewing-CO-30-90191.jpg": "Altoona Brewing Co.",
    "Budweiser-30-9171.jpg": "Budweiser",
    "Middletown-Freight-Station-30-9184.jpg": "Middletown Freight Station",
    "Middletown-Military-Station-30-9183.jpg": "Middletown Station",
    "Middletown-Passenger-Station-30-9125.jpg": "Middletown Station",
    "New-York-Central-Freight-Station-30-9151.jpg": "New York Central Freight Station",
    "New-York-Central-Passenger-Station-30-9164.jpg": "New York Central Station",
    "Old-Reading-Brewing-Co-30-90190.jpg": "Old Reading Brewing Co.",
    "Pennsylvania-Railroad-PRR-30-9152.jpg": "Pennsylvania Railroad",
    "Pittsburgh-Brewing-Co-30-90189.jpg": "Pittsburgh Brewing Co.",
}

_FREIGHT_IMAGES = {
    "Middletown-Freight-Station-30-9184.jpg",
    "New-York-Central-Freight-Station-30-9151.jpg",
}

_PASSENGER_IMAGES = {
    "Middletown-Passenger-Station-30-9125.jpg",
    "Middletown-Military-Station-30-9183.jpg",
    "New-York-Central-Passenger-Station-30-9164.jpg",
    "Pennsylvania-Railroad-PRR-30-9152.jpg",
}

_BREWING_IMAGES = {
    "Adolph-Coors-Brewing-Co-30-9161.jpg",
    "Altoona-Brewing-CO-30-90191.jpg",
    "Budweiser-30-9171.jpg",
    "Old-Reading-Brewing-Co-30-90190.jpg",
    "Pittsburgh-Brewing-Co-30-90189.jpg",
}

DEFAULT_STATION = "Middletown-Passenger-Station-30-9125.jpg"


def _variant_key_from_filename(filename: str) -> str:
    base = filename.rsplit(".", 1)[0]
    base = base.replace("-", " ").strip().lower()
    return "_".join(base.split())


def _aliases_from_legacy(legacy: str) -> tuple[str, ...]:
    """
    Expand a legacy key like 'adolph coors brewing co 30-9161' into friendly aliases:
      - progressive name phrases: 'adolph', 'adolph coors', 'adolph coors brewing', ...
      - part number: '30-9161', '309161', '9161'
      - full legacy string
    """
    s = " ".join(legacy.strip().lower().split())
    parts = s.split()
    if len(parts) < 2:
        return (s,)

    pn = parts[-1]  # e.g. 30-9161
    name_tokens = parts[:-1]  # e.g., adolph coors brewing co

    progressive = [" ".join(name_tokens[:i]) for i in range(1, len(name_tokens) + 1)]

    pn_nodash = pn.replace("-", "")
    pn_short = pn.split("-")[-1] if "-" in pn else pn

    # Dedup while preserving order
    out: list[str] = []
    for a in (*progressive, pn, pn_nodash, pn_short, s):
        if a and a not in out:
            out.append(a)

    return tuple(out)


def _flavor_for_image(filename: str) -> str:
    if filename in _BREWING_IMAGES:
        return FLAVOR_BREWING
    if filename in _PASSENGER_IMAGES:
        return FLAVOR_PASSENGER
    if filename in _FREIGHT_IMAGES:
        return FLAVOR_FREIGHT
    # Defensive default
    return FLAVOR_FREIGHT


def _load_on_image_for_flavor(flavor: str) -> str:
    if flavor == FLAVOR_BREWING:
        return "brews-waiting.png"
    if flavor == FLAVOR_PASSENGER:
        return "passengers-waiting.png"
    return "freight-waiting.jpg"


def register_station(registry: AccessoryRegistry) -> None:
    """
    Register the Freight / Passenger Station accessory type metadata.

    Assumed operations:
      - power: latch (on/off)
      - platform: latch (unloaded/loaded)
    """
    operations = (
        OperationSpec(
            key="power",
            label="Power",
            behavior=PortBehavior.LATCH,
        ),
        OperationSpec(
            key="platform",
            label="Load/Unload",
            behavior=PortBehavior.LATCH,
            # Default latch images (can be overridden per-variant)
            off_image="loaded.png",  # unloaded
            on_image="freight-waiting.jpg",  # loaded (freight default)
            width=72,
            height=72,
        ),
    )

    variants: list[VariantSpec] = []
    for legacy_name, filename in _VARIANTS.items():
        title = _TITLES[filename]
        flavor = _flavor_for_image(filename)

        # Per-variant override for the LOAD button ON image (loaded)
        load_on = _load_on_image_for_flavor(flavor)
        default = filename == DEFAULT_STATION

        variants.append(
            VariantSpec(
                key=_variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                flavor=flavor,
                default=default,
                aliases=tuple(
                    dict.fromkeys(
                        (
                            *_aliases_from_legacy(legacy_name),
                            title.lower(),
                            title,
                        )
                    )
                ),
                operation_images={
                    "platform": {"off": "loaded.png", "on": load_on},
                },
                operation_labels={
                    "platform": {"off": "Depart", "on": "Arrive"},
                },
            )
        )

    spec = AccessoryTypeSpec(
        type=AccessoryType.STATION,
        display_name="Station",
        operations=operations,
        variants=tuple(variants),
    )
    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    from ..accessory_registry import AccessoryRegistry

    reg = AccessoryRegistry.get()
    reg.reset_for_tests()
    register_station(reg)

    print_registry_entry("station")
