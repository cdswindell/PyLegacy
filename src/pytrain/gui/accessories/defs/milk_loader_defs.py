#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from ..accessory_registry import (
    AccessoryRegistry,
    AccessoryTypeSpec,
    OperationSpec,
    PortBehavior,
    VariantSpec,
)
from ..accessory_type import AccessoryType

"""
Milk Loader accessory definition (GUI-agnostic).

This module registers:
  - required operations (ports) and their behaviors
  - supported variants (title + primary image)
  - default operation images (and any per-variant overrides)

IMPORTANT:
  - No GUI imports here.
  - Only registry metadata lives in this module.
"""


def register_milk_loader(registry: AccessoryRegistry) -> None:
    """
    Register the Milk Loader accessory type metadata.

    Operations / ports:
      - power: latch (on/off)  -> uses default power off/on images unless overridden
      - conveyor: latch (on/off) -> uses default latch off/on images unless overridden
      - eject: momentary_hold (press/release) with default icon

    Variants:
      - Moose Pond Creamery (6-22660)
      - Dairymen's League (6-14291)
      - Mountain View Creamery (6-21675)
    """

    spec = AccessoryTypeSpec(
        type=AccessoryType.MILK_LOADER,
        display_name="Milk Loader",
        operations=(
            OperationSpec(
                key="power",
                label="Power",
                behavior=PortBehavior.LATCH,
            ),
            OperationSpec(
                key="conveyor",
                label="Conveyor",
                behavior=PortBehavior.LATCH,
                # Same idea: defaults handled by GUI layer unless overridden here.
            ),
            OperationSpec(
                key="eject",
                label="Eject",
                behavior=PortBehavior.MOMENTARY_HOLD,
                image="depot-milk-can-eject.jpeg",
                width=72,
                height=72,
            ),
        ),
        variants=(
            VariantSpec(
                key="moose_pond",
                display="Moose Pond Creamery",
                title="Moose Pond Creamery",
                image="Moose-Pond-Creamery-6-22660.jpg",
                aliases=(
                    "moose pond creamery 6-22660",
                    "6-22660",
                    "622660",
                    "moose pond",
                    "moose pond creamery",
                    "moose",
                ),
            ),
            VariantSpec(
                key="dairymens_league",
                display="Dairymen's League",
                title="Dairymen's League",
                image="Dairymens-League-6-14291.jpg",
                aliases=(
                    "dairymens league 6-14291",
                    "dairymen's league 6-14291",
                    "6-14291",
                    "614291",
                    "dairymens league",
                    "dairymen's league",
                    "dairymen'sdairymen",
                ),
            ),
            VariantSpec(
                key="mountain_view",
                display="Mountain View Creamery",
                title="Mountain View Creamery",
                image="Mountain-View-Creamery-6-21675.jpg",
                aliases=(
                    "mountain view creamery 6-21675",
                    "6-21675",
                    "621675",
                    "mountain view",
                    "mountain view creamery",
                    "mountain",
                ),
            ),
        ),
    )

    registry.register(spec)
