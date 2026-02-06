#
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
Hobby Shop accessory definition (GUI-agnostic).

This module registers:
  - required operations (ports) and their behaviors
  - supported variants (title + primary image)

IMPORTANT:
  - No GUI imports here.
  - Only registry metadata lives in this module.
"""


def register_hobby_shop(registry: AccessoryRegistry) -> None:
    """
    Register the Hobby Shop accessory type metadata.

    Assumed operations:
      - power: latch (on/off)
      - action: momentary_pulse (trigger animation)

    If your HobbyShopGui uses different semantics, adjust the operation keys/behavior here.
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

    variants = (
        VariantSpec(
            key="lionelville_",
            display="Lionelville Hobby Shop",
            title="Lionelville Hobby Shop",
            image="Lionelville-Hobby-Shop-6-85294.jpg",
            aliases=(
                "lionelville hobby shop 6-85294",
                "lionelville hobby shop",
                "6-85294",
                "685294",
                "85294",
                "lionelville",
            ),
        ),
        VariantSpec(
            key="madison",
            display="Madison Hobby Shop",
            title="Madison Hobby Shop",
            image="Madison-Hobby-Shop-6-14133.jpg",
            aliases=(
                "madison hobby shop 6-14133",
                "madison hobby shop",
                "6-14133",
                "614133",
                "14133",
                "madison",
            ),
        ),
        VariantSpec(
            key="midtown_models",
            display="Midtown Models Hobby Shop",
            title="Midtown Models",
            image="Midtown-Models-Hobby-Shop-6-32998.jpg",
            aliases=(
                "midtown models hobby shop 6-32998",
                "midtown models hobby shop",
                "6-32998",
                "632998",
                "32998",
                "midtown models",
                "midtown",
            ),
            default=True,
        ),
    )

    # make sure aliases are unique across variants
    variants = prune_non_unique_variant_aliases(variants)

    spec = AccessoryTypeSpec(
        type=AccessoryType.HOBBY_SHOP,
        display_name="Hobby Shop",
        operations=operations,
        variants=variants,
    )

    registry.register(spec)
