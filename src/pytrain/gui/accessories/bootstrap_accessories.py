#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from .accessory_registry import AccessoryRegistry


# noinspection PyUnusedLocal
def register_all_accessory_types(registry: AccessoryRegistry) -> None:
    """
    Import and register all known accessory type specs.

    Keep this list explicit so adding a new accessory type is a deliberate code change.
    """
    # Local imports prevent circular import issues during module import time.
    # from .types.milk_loader import register_milk_loader
    # from .types.fire_station import register_fire_station
    # from .types.hobby_shop import register_hobby_shop
    # ...

    # register_milk_loader(registry)
    # register_fire_station(registry)
    # register_hobby_shop(registry)
