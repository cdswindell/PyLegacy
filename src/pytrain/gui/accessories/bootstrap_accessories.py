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

    from .defs.control_tower_defs import register_control_tower
    from .defs.culvert_handler_defs import register_culvert_handler
    from .defs.fire_station_defs import register_fire_station
    from .defs.gas_station_defs import register_gas_station
    from .defs.hobby_shop_defs import register_hobby_shop
    from .defs.milk_loader_defs import register_milk_loader
    from .defs.playground_defs import register_playground

    # from .defs.smoke_fluid_loader_defs import register_smoke_fluid_loader
    from .defs.station_defs import register_station

    register_control_tower(registry)
    register_culvert_handler(registry)
    register_fire_station(registry)
    register_gas_station(registry)
    register_hobby_shop(registry)
    register_milk_loader(registry)
    register_playground(registry)
    # register_smoke_fluid_loader(registry)
    register_station(registry)
