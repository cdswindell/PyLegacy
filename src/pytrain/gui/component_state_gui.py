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
from ..protocol.constants import PROGRAM_NAME

log = logging.getLogger(__name__)


class ComponentStateGui(Thread):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        label: str = None,
        initial: str = "Power Districts",
        width: int = None,
        height: int = None,
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
        screens: int | None = None,
        guis: dict[str, type] | None = None,
        full_screen: bool = True,
        x_offset: int = 0,
        y_offset: int = 0,
    ) -> None:
        from ..gui.accessories_gui import AccessoriesGui
        from ..gui.motors_gui import MotorsGui
        from ..gui.power_district_gui import PowerDistrictsGui
        from ..gui.routes_gui import RoutesGui
        from ..gui.switches_gui import SwitchesGui
        from .systems_gui import SystemsGui

        super().__init__(daemon=True)
        self._ev = Event()
        default_guis = {
            "Accessories": AccessoriesGui,
            "Motors": MotorsGui,
            "Power Districts": PowerDistrictsGui,
            "Routes": RoutesGui,
            "Switches": SwitchesGui,
            f"{PROGRAM_NAME} Administration": SystemsGui,
        }
        self._guis = guis if guis is not None else default_guis
        if not self._guis:
            raise ValueError("No GUIs defined")
        # verify requested GUI exists:
        if initial.lower() not in [x.lower() for x in self._guis.keys()]:
            raise ValueError(f"Invalid initial GUI: {initial}")

        # case-correct initial
        for key in self._guis.keys():
            if initial.lower() == key.lower():
                initial = key
                break

        if label is not None:
            label = label.title()

        self.label = label
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
        self._exclude_unnamed = exclude_unnamed
        self._screens = screens
        self._full_screen = full_screen
        self._x_offset = x_offset
        self._y_offset = y_offset
        self.requested_gui = initial
        self._shutdown_flag = Event()

        self.start()

    def _construct_gui(self, gui_name: str):
        gui_cls = self._guis[gui_name]
        kwargs: dict[str, Any] = {
            "label": self.label,
            "width": self.width,
            "height": self.height,
            "aggregator": self,
            "scale_by": self._scale_by,
            "exclude_unnamed": self._exclude_unnamed,
            "screens": self._screens,
            "full_screen": self._full_screen,
            "x_offset": self._x_offset,
            "y_offset": self._y_offset,
        }
        sig = inspect.signature(gui_cls.__init__)
        accepts_var_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values())
        if not accepts_var_kwargs:
            allowed = set(sig.parameters.keys())
            kwargs = {key: value for key, value in kwargs.items() if key in allowed}
        return gui_cls(**kwargs)

    def _close_current_gui(self) -> None:
        if self._gui is None:
            return
        GpioHandler.release_handler(self._gui)
        if hasattr(self._gui, "destroy_complete"):
            self._gui.destroy_complete.wait(10)
        if isinstance(self._gui, Thread) and self._gui.is_alive():
            self._gui.join(10)
        elif hasattr(self._gui, "join"):
            self._gui.join()
        self._gui = None

    def run(self) -> None:
        # create the initially requested gui
        self._gui = self._construct_gui(self.requested_gui)

        # wait for user to request a different GUI
        while not self._shutdown_flag.is_set():
            # Wait for request to change GUI
            self._ev.wait()
            self._ev.clear()
            if self._shutdown_flag.is_set():
                break

            # Close/destroy previous GUI
            self._close_current_gui()

            # create and display new gui
            # TODO: handle push_for argument for the sys admin stuff
            self._gui = self._construct_gui(self.requested_gui)

        self._close_current_gui()

    def cycle_gui(self, gui: str):
        if gui in self._guis:
            self.requested_gui = gui
            self._ev.set()

    def close(self) -> None:
        self._shutdown_flag.set()
        self._ev.set()

    def reset(self) -> None:
        self.close()

    @property
    def guis(self) -> list[str]:
        return list(self._guis.keys())
