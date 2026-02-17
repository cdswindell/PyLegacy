#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
# pytrain/gui/accessories/defs/fire_station_defs.py
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
Fire Station accessory definition (GUI-agnostic).

Ports / operations:
  - power: latch (on/off)
  - alarm: momentary_pulse (press triggers alarm)

This file uses the “interpret legacy dicts” pattern: keep the original VARIANTS/TITLES
data and transform it into VariantSpec entries at registration time.
"""

# -----------------------------------------------------------------------------
# Source data
# -----------------------------------------------------------------------------

_VARIANTS = {
    "engine company 49 fire station 30-9157": "Fire-Station-MTH-30-9157.jpg",
    "mth fire station 30-9112": "Gray-Fire-Station-MTH-30-9112.jpg",
}

_TITLES = {
    "Fire-Station-MTH-30-9157.jpg": "Engine Company 49",
    "Gray-Fire-Station-MTH-30-9112.jpg": "MTH Fire Station",
}

# If you later discover old hand-written tuple aliases that aren't naturally
# produced by aliases_from_legacy_key(), add them here.
ALIASES: dict[str, set[str]] = {
    "engine company 49 fire station 30-9157": {"Red Fire Station", "Red Station", "Company 49"},
    "mth fire station 30-9112": {"Gray Fire Station", "Gray Station", "Grey"},
}

DEFAULT_FIRE_STATION = "Fire-Station-MTH-30-9157.jpg"


def register_fire_station(registry: AccessoryRegistry) -> None:
    """
    Register Fire Station accessory type metadata.
    """
    operations = (
        OperationSpec(
            key="power",
            label="Power",
            behavior=PortBehavior.LATCH,
        ),
        OperationSpec(
            key="alarm",
            label="Alarm",
            behavior=PortBehavior.MOMENTARY_PULSE,
            image="red_light_off.jpg",
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

        extras = ALIASES.get(legacy_name, set()) | ALIASES.get(filename, set())
        extras2 = tuple(sorted(extras)) if extras else ()

        variants.append(
            VariantSpec(
                key=variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                default=(filename == DEFAULT_FIRE_STATION),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases, *extras2)),
            )
        )

    spec = AccessoryTypeSpec(
        type=AccessoryType.FIRE_STATION,
        display_name="Fire Station",
        operations=operations,
        variants=tuple(variants),
        op_btn_image="op-fire-station.jpg",
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_fire_station(reg)
    print_registry_entry("fire_station")
