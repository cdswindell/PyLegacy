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
Control Tower accessory definition (GUI-agnostic).

Ports / operations:
  - power:  latch (on/off)
  - action: momentary_pulse (press triggers an action)

This file uses the “interpret legacy dicts” pattern: keep the original VARIANTS/TITLES
data and transform it into VariantSpec entries at registration time.

Alias policy:
  - aliases_from_legacy_key() provides a strong baseline
  - ALIASES is only for extra synonyms you had in the old hand-written tuples that
    the legacy-key parser would NOT naturally produce (e.g., colors like "yellow",
    "orange", "radio", "nasa", "railroad", etc.)
  - prune_non_unique_variant_aliases() removes aliases that collide across variants
"""

# -----------------------------------------------------------------------------
# Source data (easy to extend)
# -----------------------------------------------------------------------------

_VARIANTS = {
    "192 yellow control tower 6-37996": "192-Control-Tower-6-37996.jpg",
    "192 orange control tower 6-82014": "192-Control-Tower-6-82014.jpg",
    "192r red railroad control tower 6-32988": "192R-Railroad-Control-Tower-6-32988.jpg",
    "nasa mission control tower 2229040": "NASA-Mission-Control-Tower-2229040.jpg",
    "radio control tower 6-24153": "Radio-Control-Tower-6-24153.jpg",
}

_TITLES = {
    "192-Control-Tower-6-37996.jpg": "Yellow Control Tower",
    "192-Control-Tower-6-82014.jpg": "Orange Control Tower",
    "192R-Railroad-Control-Tower-6-32988.jpg": "Railroad Control Tower",
    "NASA-Mission-Control-Tower-2229040.jpg": "NASA Mission Control",
    "Radio-Control-Tower-6-24153.jpg": "Radio Control Tower",
}

# Optional extras that existed in the old tuples but may not be produced by
# aliases_from_legacy_key(). Keep these intentionally small and “real”.
ALIASES: dict[str, set[str]] = {
    # Keying can be by legacy name OR by filename (match is normalized).
    "192 yellow control tower 6-37996": {"yellow"},
    "192 orange control tower 6-82014": {"orange"},
    "192r red railroad control tower 6-32988": {"railroad", "red railroad", "red"},
    "nasa mission control tower 2229040": {"mission control", "mission control tower"},
    "radio control tower 6-24153": {"radio"},
}

DEFAULT_CONTROL_TOWER = "NASA-Mission-Control-Tower-2229040.jpg"


def register_control_tower(registry: AccessoryRegistry) -> None:
    """
    Register Control Tower accessory type metadata.
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

    variants: list[VariantSpec] = []
    for legacy_name, filename in _VARIANTS.items():
        title = _TITLES.get(filename, filename.rsplit(".", 1)[0])

        legacy_aliases = aliases_from_legacy_key(legacy_name) if " " in legacy_name else (legacy_name.strip().lower(),)

        base_no_ext = filename.rsplit(".", 1)[0]
        extra_aliases = (title.lower(), base_no_ext.lower(), filename.lower())

        # add ALIASES (by legacy key OR by filename)
        extras = ALIASES.get(legacy_name, set()) | ALIASES.get(filename, set())
        extra2 = tuple(sorted(extras)) if extras else ()

        variants.append(
            VariantSpec(
                key=variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                default=(filename == DEFAULT_CONTROL_TOWER),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases, *extra2)),
            )
        )

    # ensure aliases are unique across variants (drop collisions from all)
    # noinspection PyTypeChecker
    variants = prune_non_unique_variant_aliases(variants)

    spec = AccessoryTypeSpec(
        type=AccessoryType.CONTROL_TOWER,
        display_name="Control Tower",
        operations=operations,
        variants=tuple(variants),
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_control_tower(reg)
    print_registry_entry("control_tower")
