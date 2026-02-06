#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from .base_defs import print_registry_entry, prune_non_unique_variant_aliases
from ..accessory_registry import (
    AccessoryRegistry,
    AccessoryTypeSpec,
    OperationSpec,
    PortBehavior,
    VariantSpec,
)
from ..accessory_type import AccessoryType

"""
Control Tower accessory definition (GUI-agnostic).

This module registers:
  - required operations (ports) and their behaviors
  - supported variants (title + primary image)
"""


def _variant_key_from_title(title: str) -> str:
    """
    Generate a stable variant key from a display title.

    Example:
        "NASA Mission Control Tower" -> "nasa_mission_control"
    """
    t = title.strip().lower()
    if t.endswith(" control tower"):
        t = t[: -len(" control tower")]
    return "_".join(t.replace("-", " ").split())


def register_control_tower(registry: AccessoryRegistry) -> None:
    """
    Register the Control Tower accessory type metadata.

    NOTE:
      - Control towers typically have a single power/light operation.
      - Additional operations can be added later if needed.
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
            behavior=PortBehavior.MOMENTARY_PULSE,
            image="control_tower_animation.gif",
            width=72,
            height=72,
        ),
    )

    variants = (
        VariantSpec(
            key="yellow_192",
            display="192 Yellow Control Tower",
            title="Control Tower",
            image="192-Control-Tower-6-37996.jpg",
            aliases=(
                "192 yellow control tower 6-37996",
                "192 yellow control tower",
                "6-37996",
                "637996",
                "37996",
                "yellow",
            ),
        ),
        VariantSpec(
            key="orange_192",
            display="192 Orange Control Tower",
            title="Control Tower",
            image="192-Control-Tower-6-82014.jpg",
            aliases=(
                "192 orange control tower 6-82014",
                "192 orange control tower",
                "6-82014",
                "682014",
                "82014",
                "orange",
            ),
        ),
        VariantSpec(
            key="railroad_192r",
            display="192R Railroad Control Tower",
            title="Railroad Control Tower",
            image="192R-Railroad-Control-Tower-6-32988.jpg",
            aliases=(
                "192r red railroad control tower 6-32988",
                "192r railroad control tower",
                "railroad control tower",
                "6-32988",
                "632988",
                "32988",
                "red railroad",
                "railroad",
                "red",
            ),
        ),
        VariantSpec(
            key=_variant_key_from_title("NASA Mission Control Tower"),
            display="NASA Mission Control",
            title="NASA Mission Control",
            image="NASA-Mission-Control-Tower-2229040.jpg",
            aliases=(
                "nasa mission control tower 2229040",
                "nasa mission control tower",
                "2229040",
                "nasa",
            ),
            default=True,
        ),
        VariantSpec(
            key=_variant_key_from_title("Radio Control Tower"),
            display="Radio Control Tower",
            title="Radio Control Tower",
            image="Radio-Control-Tower-6-24153.jpg",
            aliases=(
                "radio control tower 6-24153",
                "radio control tower",
                "6-24153",
                "624153",
                "24153",
                "radio",
            ),
        ),
    )

    # make sure aliases are unique across variants
    variants = prune_non_unique_variant_aliases(variants)

    spec = AccessoryTypeSpec(
        type=AccessoryType.CONTROL_TOWER,
        display_name="Control Tower",
        operations=operations,
        variants=variants,
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    from ..accessory_registry import AccessoryRegistry

    reg = AccessoryRegistry.get()
    reg.reset_for_tests()
    register_control_tower(reg)

    print_registry_entry("control_tower")
