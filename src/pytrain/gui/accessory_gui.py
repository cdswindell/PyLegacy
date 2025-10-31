#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import inspect
import logging
from threading import Event, Thread
from typing import Any

from ..gpio.gpio_handler import GpioHandler

log = logging.getLogger(__name__)


def validate_constructor_args(cls, args=(), kwargs=None):
    kwargs = kwargs or {}
    sig = inspect.signature(cls.__init__)
    try:
        b = sig.bind(None, *args, **kwargs)
        b.apply_defaults()
        return True, None
    except TypeError as e:
        return False, f"{cls.__name__}{sig}: {e}"


def instantiate(
    cls,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    *,
    allow_partial: bool = False,
    apply_defaults: bool = True,
):
    """
    Validate (and optionally complete) constructor args, then instantiate `cls`.
    - If allow_partial=True, missing optional args are ok; missing required args will still error on actual call.
    - apply_defaults=True fills in defaulted parameters.
    """
    kwargs = kwargs or {}

    sig = inspect.signature(cls.__init__)
    # Pretend `self` is supplied; bind the rest
    try:
        # noinspection PyArgumentList
        binder = (sig.bind_partial if allow_partial else sig.bind)(None, *args, **kwargs)
    except TypeError as e:
        # Produce a friendly message that shows the signature
        raise TypeError(f"{cls.__name__}{sig}: {e}") from None

    if apply_defaults:
        binder.apply_defaults()

    # Drop the fake self
    bound_args = list(binder.args)[1:]  # skip the placeholder for self
    bound_kwargs = dict(binder.kwargs)

    # Now actually construct
    return cls(*bound_args, **bound_kwargs)


def coerce_value(value: str) -> Any:
    if value.isdecimal():
        value = int(value)
    elif value.lower() == "true":
        value = True
    elif value.lower() == "false":
        value = False
    else:
        try:
            value = float(value)
            return int(value) if value.is_integer() else value
        except ValueError:
            pass
    return value


class AccessoryGui(Thread):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        *args,
        width: int = None,
        height: int = None,
        scale_by: float = 1.0,
        initial: str = None,
    ) -> None:
        from .backhoe_gui import BackhoeGui
        from .control_tower_gui import ControlTowerGui
        from .culvert_gui import CulvertGui
        from .fire_station_gui import FireStationGui
        from .freight_depot_gui import FreightDepotGui
        from .freight_station_gui import FreightStationGui
        from .gas_station_gui import GasStationGui
        from .hobby_shop_gui import HobbyShopGui
        from .milk_loader_gui import MilkLoaderGui
        from .playground_gui import PlaygroundGui
        from .smoke_fluid_loader_gui import SmokeFluidLoaderGui

        super().__init__(daemon=True)
        self._ev = Event()

        self._gui_classes = {
            "backhoe": BackhoeGui,
            "control": ControlTowerGui,
            "culvert": CulvertGui,
            "depot": FreightDepotGui,
            "fire": FireStationGui,
            "gas": GasStationGui,
            "hobby": HobbyShopGui,
            "milk": MilkLoaderGui,
            "smoke": SmokeFluidLoaderGui,
            "station": FreightStationGui,
            "playground": PlaygroundGui,
        }

        # look for tuples in args; they define the guis we want
        self._guis = {}
        for gui in args:
            if isinstance(gui, tuple):
                gui_class, gui_args, gui_kwargs = self._parse_tuple(gui)
                variant_arg = gui_kwargs.get("variant", None)
                title, _ = gui_class.get_variant(variant_arg)
                if title in self._guis:
                    raise ValueError(f"Duplicate GUI variant: {gui[0]}: {title}")
                self._guis[title] = (gui_class, gui_args, gui_kwargs)

        self._sorted_guis = sorted(self._guis.keys(), key=lambda x: x[0])

        # verify requested GUI exists:
        if initial:
            # look for partial match
            for key in self._guis.keys():
                if initial.lower() in key.lower():
                    initial = key
                    break
            if initial not in self._guis.keys():
                raise ValueError(f"Invalid initial GUI: {initial}")
        else:
            initial = list(self._guis.keys())[0]

        if width is None or height is None:
            try:
                from tkinter import Tk

                root = Tk()
                self.width = root.winfo_screenwidth()
                self.height = root.winfo_screenheight()
                root.destroy()
            except Exception as e:
                log.exception("Error determining window size", exc_info=e)
        else:
            self.width = width
            self.height = height
        self._scale_by = scale_by
        self._gui = None
        self.requested_gui = initial

        self.start()

    def get_variant(self, variant: str):
        if not isinstance(variant, str):
            raise ValueError(f"Invalid GUI variant: {variant}")
        variant = variant.lower().strip().replace("'", "").replace("-", "")
        for k, v in self._gui_classes.items():
            if variant in k:
                return v
        raise ValueError(f"Invalid GUI variant: {variant}")

    def run(self) -> None:
        # create the initially requested gui
        gui = self._guis[self.requested_gui]
        gui[2]["aggrigator"] = self
        self._gui = instantiate(gui[0], gui[1], gui[2])

        # wait for user to request a different GUI
        while True:
            # Wait for request to change GUI
            self._ev.wait()
            self._ev.clear()

            # Close/destroy previous GUI
            GpioHandler.release_handler(self._gui)

            # wait for Gui to be destroyed
            self._gui.destroy_complete.wait(10)
            self._gui.join()
            # clean up state
            self._gui = None

            # create and display new gui
            gui = self._guis[self.requested_gui]
            gui[2]["aggrigator"] = self
            self._gui = instantiate(gui[0], gui[1], gui[2])

    def cycle_gui(self, gui: str):
        if gui in self._guis:
            self.requested_gui = gui
            self._ev.set()

    @property
    def guis(self) -> list[str]:
        return self._sorted_guis

    def _parse_tuple(self, gui: tuple) -> tuple[Any, tuple, dict]:
        if len(gui) < 2:
            raise ValueError(f"Invalid GUI tuple: {gui}")
        gui_class = self.get_variant(gui[0])
        gui_args = list()
        gui_kwargs: dict[str, Any] = dict()
        for arg in gui[1:]:
            if isinstance(arg, str):
                last_arg = arg.strip().split("=")
                if len(last_arg) == 1:
                    gui_args.append(last_arg[0])
                elif len(last_arg) == 2 and isinstance(last_arg[0], str):
                    gui_kwargs[last_arg[0]] = coerce_value(last_arg[1])
                else:
                    raise ValueError(f"Invalid variant argument format: {arg}")
            else:
                gui_args.append(arg)

            if isinstance(gui_args[-1], str) and "variant" not in gui_kwargs:
                gui_kwargs["variant"] = gui_args[-1]
                gui_args = gui_args[:-1]
        return gui_class, tuple(gui_args), gui_kwargs
