#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#
#
# pytrain/gui/accessories/accessory_type.py
from __future__ import annotations

from ...protocol.constants import Mixins


class AccessoryType(Mixins):
    """
    Represents a set of predefined accessory types.

    AccessoryType defines a collection of constants, each representing a specific
    type of accessory. It is used to categorize and standardize the naming of
    various accessories within the application. This class is primarily intended
    to serve as a centralized source of accessory type definitions, promoting
    consistency and reducing duplication of hardcoded values.

    Attributes:
        CONTROL_TOWER (str): Represents the control tower accessory type.
        CULVERT_HANDLER (str): Represents the culvert handler accessory type.
        FIRE_STATION (str): Represents the fire station accessory type.
        FREIGHT_DEPOT (str): Represents the freight depot accessory type.
        GAS_STATION (str): Represents the gas station accessory type.
        HOBBY_SHOP (str): Represents the hobby shop accessory type.
        MILK_LOADER (str): Represents the milk loader accessory type.
        PLAYGROUND (str): Represents the playground accessory type.
        SMOKE_FLUID_LOADER (str): Represents the smoke fluid loader accessory type.
        STATION (str): Represents the freight/passenger station accessory type.
    """

    CONTROL_TOWER = "control_tower"
    CULVERT_HANDLER = "culvert_handler"
    FIRE_STATION = "fire_station"
    FREIGHT_DEPOT = "freight_depot"
    GAS_STATION = "gas_station"
    HOBBY_SHOP = "hobby_shop"
    MILK_LOADER = "milk_loader"
    PLAYGROUND = "playground"
    SMOKE_FLUID_LOADER = "smoke_fluid_loader"
    STATION = "station"
