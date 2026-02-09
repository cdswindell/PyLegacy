#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import import_module
from typing import Any

from .accessory_registry import AccessoryRegistry


def _import_register_fn(mod_path: str, fn_name: str) -> Callable[[AccessoryRegistry], None]:
    mod = import_module(mod_path, package=__package__)
    fn = getattr(mod, fn_name, None)
    if not callable(fn):
        raise AttributeError(f"{mod_path} does not export callable {fn_name}()")
    # We validated callability; cast to the specific signature we expect.
    return fn  # type: ignore[return-value]


def register_all_accessory_types(registry: AccessoryRegistry) -> None:
    """
    Import defs modules concurrently (faster), but register sequentially (safe).
    """
    items: tuple[tuple[str, str], ...] = (
        (".defs.construction_defs", "register_construction"),
        (".defs.control_tower_defs", "register_control_tower"),
        (".defs.culvert_handler_defs", "register_culvert_handler"),
        (".defs.fire_station_defs", "register_fire_station"),
        (".defs.freight_depot_defs", "register_freight_depot"),
        (".defs.gas_station_defs", "register_gas_station"),
        (".defs.hobby_shop_defs", "register_hobby_shop"),
        (".defs.milk_loader_defs", "register_milk_loader"),
        (".defs.playground_defs", "register_playground"),
        (".defs.smoke_fluid_loader_defs", "register_smoke_fluid_loader"),
        (".defs.station_defs", "register_station"),
    )

    register_fns: list[Callable[[AccessoryRegistry], None]] = [None] * len(items)  # type: ignore[list-item]

    # Parallelize only the import/lookup work. Keep registry mutations sequential.
    max_workers = min(8, max(1, len(items)))

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_to_idx: dict[Any, int] = {}
        for i, (mod_path, fn_name) in enumerate(items):
            fut = ex.submit(_import_register_fn, mod_path, fn_name)
            fut_to_idx[fut] = i

        for fut in as_completed(fut_to_idx):
            i = fut_to_idx[fut]
            mod_path, fn_name = items[i]
            try:
                register_fns[i] = fut.result()
            except (ImportError, AttributeError, TypeError) as e:
                # Fail fast with context; do not swallow real import/shape issues.
                raise RuntimeError(f"Failed importing {mod_path}:{fn_name}: {e}") from e

    for fn in register_fns:
        fn(registry)
