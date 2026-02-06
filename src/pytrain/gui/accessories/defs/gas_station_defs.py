#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from .base_defs import prune_non_unique_variant_aliases
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

This module registers:
  - required operations (ports) and their behaviors
  - supported variants (title + primary image)

IMPORTANT:
  - No GUI imports here.
  - Only registry metadata lives in this module.
"""


def _variant_key_from_title(title: str) -> str:
    """
    Generate a stable variant key from a display title.

    Example:
        "BP Gas Station" -> "bp"
        "Route 66 Gas Station" -> "route_66"
    """
    t = title.strip().lower()
    if t.endswith(" gas station"):
        t = t[: -len(" gas station")]
    return "_".join(t.replace("-", " ").split())


def register_gas_station(registry: AccessoryRegistry) -> None:
    """
    Register the Gas Station accessory type metadata.

    NOTE:
      - The provided information defines variants only.
      - A single LATCH 'power' operation is declared as a placeholder.
      - Adjust operations when the real gas station behaviors are finalized.
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

    variants = (
        VariantSpec(
            key=_variant_key_from_title("Atlantic Gas Station"),
            display="Atlantic Gas Station",
            title="Atlantic Gas Station",
            image="Atlantic-Gas-Station-30-91003.jpg",
            aliases=(
                "atlantic gas station 30-91003",
                "atlantic gas station",
                "atlantic",
                "30-91003",
                "3091003",
                "91003",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("BP Gas Station"),
            display="BP Gas Station",
            title="BP Gas Station",
            image="BP-Gas-Station-30-9181.jpg",
            aliases=(
                "bp gas station 30-9181",
                "bp gas station",
                "30-9181",
                "309181",
                "9181",
                "bp",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Citgo Gas Station"),
            display="Citgo Gas Station",
            title="Citgo Gas Station",
            image="Citgo-Gas-Station-30-9113.jpg",
            aliases=(
                "citgo gas station 30-9113",
                "citgo gas station",
                "30-9113",
                "309113",
                "9113",
                "citgo",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Esso Gas Station"),
            display="Esso Gas Station",
            title="Esso Gas Station",
            image="Esso-Gas-Station-30-9106.jpg",
            aliases=(
                "esso gas station 30-9106",
                "esso gas station",
                "30-9106",
                "309106",
                "9106",
                "esso",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Gulf Gas Station"),
            display="Gulf Gas Station",
            title="Gulf Gas Station",
            image="Gulf-Gas-Station-30-9168.jpg",
            aliases=(
                "gulf gas station 30-9168",
                "gulf gas station",
                "30-9168",
                "309168",
                "9168",
                "gulf",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Mobile Gas Station"),
            display="Mobile Gas Station",
            title="Mobile Gas Station",
            image="Mobile-Gas-Station-30-9124.jpg",
            aliases=(
                "mobile gas station 30-9124",
                "mobile gas station",
                "30-9124",
                "309124",
                "9124",
                "mobile",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Route 66 Gas Station"),
            display="Route 66 Gas Station",
            title="Route 66 Gas Station",
            image="Route-66-Gas-Station-30-91002.jpg",
            aliases=(
                "route 66 gas station 30-91002",
                "route 66 gas station",
                "route_66",
                "30-91002",
                "3091002",
                "91002",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Shell Gas Station"),
            display="Shell Gas Station",
            title="Shell Gas Station",
            image="Shell-Gas-Station-30-9182.jpg",
            aliases=(
                "shell gas station 30-9182",
                "shell gas station",
                "30-9182",
                "309182",
                "9182",
                "shell",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Sinclair Gas Station"),
            display="Sinclair Gas Station",
            title="Sinclair Gas Station",
            image="Sinclair-Gas-Station-30-9101.jpg",
            aliases=(
                "sinclair gas station 30-9101",
                "sinclair gas station",
                "30-9101",
                "309101",
                "9101",
                "sinclair",
            ),
            default=True,
        ),
        VariantSpec(
            key=_variant_key_from_title("Sunoco Gas Station"),
            display="Sunoco Gas Station",
            title="Sunoco Gas Station",
            image="Sunoco-Gas-Station-30-9154.jpg",
            aliases=(
                "sunoco gas station 30-9154",
                "sunoco gas station",
                "30-9154",
                "309154",
                "9154",
                "sunoco",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Texaco Gas Station"),
            display="Texaco Gas Station",
            title="Texaco Gas Station",
            image="Texaco-Gas-Station-30-91001.jpg",
            aliases=(
                "texaco gas station 30-91001",
                "texaco gas station",
                "30-91001",
                "3091001",
                "91001",
                "texaco",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("Tidewater Oil Gas Station"),
            display="Tidewater Oil Gas Station",
            title="Tidewater Oil Gas Station",
            image="Tidewater-Oil-Gas-Station-30-9181.jpg",
            aliases=(
                "tidewater oil gas station 30-9181",
                "tidewater oil gas station",
                "30-9181",
                "309181",
                "9181",
                "tidewater oil",
                "tidewater",
            ),
        ),
    )

    # make sure aliases are unique across variants
    variants = prune_non_unique_variant_aliases(variants)

    spec = AccessoryTypeSpec(
        type=AccessoryType.GAS_STATION,
        display_name="Gas Station",
        operations=operations,
        variants=variants,
    )

    registry.register(spec)
