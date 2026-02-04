#
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
# pytrain/gui/accessories/defs/fire_station_def.py
from __future__ import annotations

from ..accessory_registry import AccessoryRegistry, AccessoryTypeSpec, OperationSpec, PortBehavior, VariantSpec
from ..accessory_type import AccessoryType

"""
Fire Station accessory definition (GUI-agnostic).

This module registers:
  - required operations (ports) and their behaviors
  - supported variants (title + primary image)

IMPORTANT:
  - No GUI imports here.
  - Only registry metadata lives in this module.
"""


def register_fire_station(registry: AccessoryRegistry) -> None:
    """
    Register the Fire Station accessory type metadata.

    Operations / ports:
      - power: latch (on/off)
      - alarm: momentary_hold (press=on, release=off)

    Variants:
      - MTH Fire Station (30-9157)
    """
    spec = AccessoryTypeSpec(
        type=AccessoryType.FIRE_STATION,
        display_name="Fire Station",
        operations=(
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
        ),
        variants=(
            VariantSpec(
                key="mth_fire_station",
                display="MTH Fire Station",
                title="MTH Fire Station",
                image="Fire-Station-MTH-30-9157.jpg",
                aliases=(
                    "mth fire station 30-9157",
                    "fire station 30-9157",
                    "30-9157",
                    "309157",
                    "mth fire station",
                    "fire station",
                ),
            ),
        ),
    )

    registry.register(spec)
